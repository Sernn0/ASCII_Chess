from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Optional

try:
    import chess
    import chess.engine
except ImportError:
    chess = None


DEFAULT_MIN_RATING = 1350
DEFAULT_MAX_RATING = 2850
DEFAULT_TIME = 0.5


# ===== 엔진 설정 =====
@dataclass
class EngineConfig:
    executable_path: Optional[str] = None
    min_rating: int = DEFAULT_MIN_RATING
    max_rating: int = DEFAULT_MAX_RATING
    default_think_time: float = DEFAULT_TIME


# ===== 스톡피시 AI =====
class StockfishAI:

    def __init__(self, config: EngineConfig | None = None) -> None:
        if chess is None:
            raise RuntimeError("python-chess is required for Stockfish integration.")

        self.config = config or EngineConfig()
        self._engine = self._launch_engine(self.config.executable_path)
        self._rating = max(self.config.min_rating, min(1500, self.config.max_rating))
        self.set_rating(self._rating)

    def _launch_engine(self, executable_path: Optional[str]):
        # 1. 사용자 지정 경로가 있으면 우선 사용
        if executable_path:
            # 상대 경로인 경우 절대 경로로 변환
            if not os.path.isabs(executable_path):
                executable_path = os.path.abspath(executable_path)
            if os.path.isfile(executable_path):
                print(f"사용자 지정 Stockfish 경로 사용: {executable_path}")
                return chess.engine.SimpleEngine.popen_uci(executable_path)
            else:
                print(f"[WARNING] 지정된 경로를 찾을 수 없습니다: {executable_path}")
        
        # 2. 가능한 Stockfish 경로 목록
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        possible_paths = [
            # Windows에서 일반적인 경로
            os.path.join(script_dir, "engines", "stockfish", "stockfish-windows-x86-64-avx2.exe"),
            os.path.join(script_dir, "engines", "stockfish", "stockfish.exe"),
            os.path.join(script_dir, "stockfish-windows-x86-64-avx2.exe"),
            os.path.join(script_dir, "stockfish.exe"),
            "stockfish-windows-x86-64-avx2.exe",
            "stockfish.exe"
        ]
        
        # 3. 가능한 경로들 확인
        for path in possible_paths:
            try:
                if os.path.isfile(path):
                    abs_path = os.path.abspath(path)
                    print(f"Stockfish를 찾았습니다: {abs_path}")
                    return chess.engine.SimpleEngine.popen_uci(abs_path)
            except Exception as e:
                print(f"[WARNING] {path} 확인 중 오류: {e}")
                continue
                
        # 4. 재귀적으로 stockfish로 시작하는 파일 검색
        search_dirs = [
            os.path.join(script_dir, "engines"),
            script_dir
        ]
        
        for search_dir in search_dirs:
            if os.path.isdir(search_dir):
                for root, _, files in os.walk(search_dir):
                    for file in files:
                        if file.lower().startswith('stockfish') and (file.lower().endswith('.exe') or not file.lower().endswith('.md')):
                            candidate = os.path.join(root, file)
                            try:
                                abs_path = os.path.abspath(candidate)
                                print(f"Stockfish를 찾았습니다: {abs_path}")
                                return chess.engine.SimpleEngine.popen_uci(abs_path)
                            except Exception as e:
                                print(f"[WARNING] {candidate} 실행 중 오류: {e}")
        
        # 4. 시스템 PATH에서 찾기 (마지막 시도)
        path = shutil.which("stockfish")
        if path:
            print(f"시스템 PATH에서 Stockfish를 찾았습니다: {path}")
            return chess.engine.SimpleEngine.popen_uci(path)
                
        # 모든 시도 실패
        raise FileNotFoundError(
            "Stockfish 실행 파일을 찾을 수 없습니다.\n"
            "다음 중 하나를 시도해 보세요:\n"
            f"1. {os.path.join(script_dir, 'engines')} 폴더에 Stockfish 실행 파일을 배치하거나\n"
            "2. --engine-path 인자로 정확한 경로를 지정하거나\n"
            "3. 시스템 PATH에 Stockfish를 추가하세요.\n"
            "4. 프로그램을 다시 실행하면 자동으로 Stockfish를 다운로드할 수 있습니다."
        )

    @property
    def rating(self) -> int:
        return self._rating

    def set_rating(self, rating: int) -> None:
        rating = max(self.config.min_rating, min(rating, self.config.max_rating))
        self._rating = rating
        try:
            self._engine.configure({
                "UCI_LimitStrength": True,
                "UCI_Elo": rating,
            })
        except chess.engine.EngineError as exc:
            raise RuntimeError(f"Failed to configure Stockfish: {exc}") from exc

    def choose_move(self, board: "chess.Board", think_time: Optional[float] = None) -> "chess.Move":
        if chess is None:
            raise RuntimeError("python-chess is required for Stockfish integration.")
        limit = chess.engine.Limit(time=think_time or self.config.default_think_time)
        result = self._engine.play(board, limit=limit)
        return result.move

    def get_hint(self, board: "chess.Board", think_time: Optional[float] = None) -> tuple["chess.Move", str]:
        if chess is None:
            raise RuntimeError("python-chess is required for Stockfish integration.")
        original_rating = self._rating
        try:
            self._engine.configure({
                "UCI_LimitStrength": False,
            })
            hint_time = (think_time or self.config.default_think_time) * 2
            limit = chess.engine.Limit(time=hint_time)
            result = self._engine.play(board, limit=limit)
            san_move = board.san(result.move)
            return result.move, san_move
        finally:
            self.set_rating(original_rating)

    def close(self) -> None:
        try:
            self._engine.quit()
        except Exception:
            pass

    def __enter__(self) -> "StockfishAI":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
