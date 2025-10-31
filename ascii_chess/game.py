from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

try:
    import chess
except ImportError:  # pragma: no cover - dependency to be installed by user
    chess = None  # type: ignore

from .ai import EngineConfig, StockfishAI
from .renderer import AsciiRenderer


DEFAULT_PROMPT = "Enter move in SAN (e.g. Nf3, O-O, cxd4, ff, help)."


@dataclass
class GameState:
    board: "chess.Board" = field(default_factory=lambda: chess.Board() if chess else None)
    move_history: List[str] = field(default_factory=list)
    time_control: Optional[int] = None  # None means unlimited time
    white_time: float = 0.0
    black_time: float = 0.0
    last_move_time: float = 0.0


class GameController:
    def __init__(
        self,
        renderer: Optional[AsciiRenderer] = None,
        ai: Optional[StockfishAI] = None,
        engine_config: Optional[EngineConfig] = None,
        time_control: Optional[int] = None,  # None means unlimited time
    ) -> None:
        if chess is None:
            raise RuntimeError("python-chess is required to run the game.")
            
        self.renderer = renderer or AsciiRenderer()
        self.ai = ai or StockfishAI(config=engine_config)
        self.state = GameState()
        
        # Set time control (None means unlimited time)
        self.state.time_control = time_control
        if time_control is not None:
            self.state.white_time = time_control
            self.state.black_time = time_control
        self.state.last_move_time = time.time()
        
        self.last_message = DEFAULT_PROMPT
        self.enemy_status = ""
        self._running = True
        self._resigned = False
        self._forfeited = False
        self._quit_requested = False
        self._forced_outcome: Optional[str] = None

    def run(self) -> None:
        # 레이팅 설정부터 재시작 여부 확인까지 전체 게임 흐름을 제어한다
        try:
            while self._running:
                # If time control wasn't set during initialization, prompt for it
                if self.state.time_control is None:
                    time_control_seconds = self._prompt_time_control()
                    self.state.time_control = time_control_seconds
                    self.state.white_time = time_control_seconds
                    self.state.black_time = time_control_seconds
                
                # Get rating
                rating = self._prompt_rating()
                self.ai.set_rating(rating)
                
                # Reset the timer
                self.state.last_move_time = time.time()
                
                # Start the game
                aborted = self._start_game_loop()
                if not self._running:
                    break
                if not aborted:
                    self._render()
                    if self._forced_outcome:
                        self._announce_forced_outcome(self._forced_outcome)
                        self._forced_outcome = None
                    else:
                        self._announce_result(self.state.board)
                if not self._prompt_play_again():
                    self._running = False
                else:
                    self._reset_state()
        finally:
            self.ai.close()

    def _prompt_time_control(self) -> int:
        # Time control is now handled in main.py
        return 600  # Default to 10 minutes if somehow this is called

    def _prompt_rating(self) -> int:
        # Get enemy rating from user
        self.renderer.render_title_screen()
        min_rating = self.ai.config.min_rating
        max_rating = self.ai.config.max_rating
        default_rating = self.ai.rating
        while True:
            try:
                rating_str = input(
                    f"Set Enemy Elo ({min_rating}-{max_rating}, default {default_rating}): "
                ).strip()
                if not rating_str:
                    return default_rating
                rating = int(rating_str)
                if min_rating <= rating <= max_rating:
                    return rating
                print(f"Please enter a rating between {min_rating} and {max_rating}.")
            except ValueError:
                print("Rating must be a number.")

    def _start_game_loop(self) -> bool:
        # 플레이어와 Enemy의 번갈아 둔 수를 처리한다
        board = self.state.board
        assert board is not None
        self._resigned = False
        self._forfeited = False
        self._quit_requested = False
        self.last_message = DEFAULT_PROMPT
        
        # Initialize last move time at the start of the game
        self.state.last_move_time = time.time()

        while not board.is_game_over(claim_draw=True):
            # Record the start of the turn
            turn_start_time = time.time()
            
            # Update the last move time
            self.state.last_move_time = turn_start_time
            
            # Check for time out before starting the turn
            if board.turn == chess.WHITE and self.state.white_time <= 0:
                self._forced_outcome = "Time out! Black wins!"
                return False
            elif board.turn == chess.BLACK and self.state.black_time <= 0:
                self._forced_outcome = "Time out! White wins!"
                return False
                
            # Render the board to show current times
            self._render()
            
            # Get the player's move
            move = self._prompt_move(board)
            if move is None:
                if self._forced_outcome:
                    forced_messages = {
                        "win": "Player wins!",
                        "lose": "Enemy wins!",
                        "draw": "Draw.",
                    }
                    self.last_message = forced_messages[self._forced_outcome]
                    self.enemy_status = ""
                    return False
                if self._quit_requested:
                    return True
                if self._resigned:
                    self.last_message = "Player forfeited."
                elif not self._running:
                    self.last_message = "Exiting game..."
                else:
                    self.last_message = "Game aborted."
                self.enemy_status = ""
                self._render()
                return True

            # Update time for the current player after their move
            move_end_time = time.time()
            time_used = move_end_time - self.state.last_move_time
            
            if self.state.time_control is not None:
                if board.turn == chess.WHITE:
                    self.state.white_time = max(0, self.state.white_time - time_used)
                else:
                    self.state.black_time = max(0, self.state.black_time - time_used)
            
            # Make the move
            player_san = board.san(move)
            board.push(move)
            self.state.move_history.append(player_san)
            
            # Update last move time for the next turn
            self.state.last_move_time = time.time()
            # Update status for AI's turn
            self.last_message = "Enemy is thinking..."
            self.enemy_status = "Calculating..."
            self._render()

            if board.is_game_over(claim_draw=True):
                self.enemy_status = ""
                break

            # Calculate AI thinking time (10% of remaining time, with min/max bounds)
            remaining_time = self.state.black_time if self.state.time_control is not None else 30.0  # Default to 30 seconds if unlimited time
            thinking_time = min(max(remaining_time * 0.1, 0.5), 3.0)  # 10% of remaining time, min 0.5s, max 3s
            
            # Update status and show thinking time
            self.enemy_status = f"Thinking... ({(thinking_time):.1f}s)"
            self._render()
            
            # Record time before AI starts thinking
            think_start_time = time.time()
            
            # Make the AI move (this might take some time)
            ai_move = self.ai.choose_move(board)
            
            # Ensure the move is legal
            if ai_move not in board.legal_moves:
                # If the move is not legal, get a random legal move as fallback
                legal_moves = list(board.legal_moves)
                if legal_moves:
                    ai_move = random.choice(legal_moves)
                else:
                    # No legal moves available (checkmate or stalemate)
                    self.enemy_status = "No legal moves!"
                    self._render()
                    return False
            
            ai_san = board.san(ai_move)
            
            # Calculate actual time taken for the move
            current_time = time.time()
            actual_thinking_time = current_time - think_start_time
            
            # If AI was too fast, wait to make it more realistic
            if actual_thinking_time < thinking_time:
                time.sleep(thinking_time - actual_thinking_time)
                current_time = time.time()
            
            # Calculate time elapsed for this move
            time_elapsed = current_time - self.state.last_move_time
            
            # Apply the move first
            board.push(ai_move)
            self.state.move_history.append(ai_san)
            
            # Then update the time
            self.state.black_time = max(0, self.state.black_time - time_elapsed)
            
            # Update last move time for the next turn
            self.state.last_move_time = time.time()
            
            # Clear status and reset prompt
            self.enemy_status = ""
            self.last_message = DEFAULT_PROMPT

        return False

    def _prompt_move(self, board: "chess.Board") -> Optional["chess.Move"]:
        # 사용자의 입력을 검사해 명령 또는 합법적인 수를 반환한다
        error_message = ""
        while True:
            prompt = error_message or DEFAULT_PROMPT
            self.last_message = prompt
            self._render()
            user_input = input("Player move (or command): ").strip()
            if not user_input:
                error_message = "Please enter a move."
                continue
            lowered = user_input.lower()
            if lowered in {"/win", "/lose", "/draw"}:
                mapping = {"/win": "win", "/lose": "lose", "/draw": "draw"}
                self._forced_outcome = mapping[lowered]
                return None
            if lowered in {"quit", "exit"}:
                self._running = False
                self._quit_requested = True
                return None
            if lowered == "ff":
                self._resigned = True
                self._forfeited = True
                return None
            if lowered == "help":
                print(
                    "\nCommands:\n"
                    "  help    - show this message\n"
                    "  ff      - forfeit the game\n"
                    "  quit    - exit the program immediately\n"
                    "Enter chess moves in Standard Algebraic Notation (SAN).\n"
                )
                error_message = ""
                continue
            try:
                move = board.parse_san(user_input)
                return move
            except ValueError:
                error_message = f"Illegal move: {user_input}."

    def _announce_result(self, board: "chess.Board") -> None:
        # 정상 종료된 게임의 결과를 출력한다
        outcome = board.outcome(claim_draw=True)
        if outcome is None:
            if self._resigned:
                print("\nPlayer forfeited. Enemy wins.")
            else:
                print("\nGame ended prematurely.")
            return
        if outcome.winner is None:
            message = "Draw."
        elif outcome.winner == chess.WHITE:
            message = "Player wins!"
        else:
            message = "Enemy wins!"
        print("\n" + message)
        if outcome.termination:
            print(f"Reason: {outcome.termination.name.replace('_', ' ').title()}")
        print(f"Result: {outcome.result()}")

    def _announce_forced_outcome(self, outcome: str) -> None:
        # 개발자 테스트용 강제 결과 메시지를 출력한다
        messages = {
            "win": "Player wins!",
            "lose": "Enemy wins!",
            "draw": "Draw.",
        }
        print("\n" + messages[outcome])

    def _prompt_play_again(self) -> bool:
        # 재시작 여부를 입력받는다
        while True:
            choice = input("Play again? (y/n): ").strip().lower()
            if choice in {"y", "yes"}:
                return True
            if choice in {"n", "no"}:
                return False
            print("Please answer with y or n.")

    def _reset_state(self) -> None:
        # 새 게임을 위한 상태를 초기화한다
        # Save the current time control
        current_time_control = self.state.time_control
        
        # Reset the game state
        self.state = GameState()
        
        # Restore the time control settings
        self.state.time_control = current_time_control
        if current_time_control is not None:
            self.state.white_time = current_time_control
            self.state.black_time = current_time_control
            
        self.state.last_move_time = time.time()
        self.last_message = DEFAULT_PROMPT
        self.enemy_status = ""
        self._running = True
        self._resigned = False
        self._forfeited = False
        self._quit_requested = False

    def _format_time(self, seconds: float) -> str:
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"

    def _render(self) -> None:
        # CLI 렌더러에 현재 상태를 전달한다
        board = self.state.board
        assert board is not None
        
        # Format time display
        if self.state.time_control is not None:
            white_time = self._format_time(self.state.white_time)
            black_time = self._format_time(self.state.black_time)
            time_display = f"Your time: {white_time}  |  Enemy time: {black_time}"
        else:
            time_display = "Unlimited Time"
        
        self.renderer.render_board(
            board=board,
            move_history=self.state.move_history,
            enemy_rating=self.ai.rating,
            enemy_status=self.enemy_status,
            prompt_text=f"{self.last_message}\n{time_display}",
        )
