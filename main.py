from __future__ import annotations

import argparse
import sys

from ascii_chess.deps import collect_dependency_status


def parse_args(argv: list[str]) -> argparse.Namespace:
    # 명령줄 인자 정의 및 파싱
    parser = argparse.ArgumentParser(description="ASCII CLI Chess vs Stockfish")
    parser.add_argument(
        "--engine-path",
        help="Path to Stockfish executable (defaults to checking PATH).",
        default=None,
    )
    parser.add_argument(
        "--min-rating",
        type=int,
        default=1350,
        help="Minimum Elo allowed for the AI (default: 1350, Stockfish limit).",
    )
    parser.add_argument(
        "--max-rating",
        type=int,
        default=2850,
        help="Maximum Elo allowed for the AI (default: 2850).",
    )
    parser.add_argument(
        "--think-time",
        type=float,
        default=0.5,
        help="Default thinking time per AI move in seconds (default: 0.5).",
    )
    parser.add_argument(
        "--time-control",
        type=int,
        default=10,
        help="Time control in minutes per player (default: 10).",
    )
    parser.add_argument(
        "--ascii-only",
        action="store_true",
        help="Force ASCII board rendering instead of Unicode chess glyphs.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the classic CLI experience instead of the GUI.",
    )
    parser.add_argument(
        "--no-auto-install",
        action="store_true",
        help="Skip automatic installation attempt for python-chess.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    # 실행 환경 점검 후 CLI 또는 GUI 진입점을 수행
    args = parse_args(argv or sys.argv[1:])

    deps = collect_dependency_status(
        engine_path=args.engine_path,
        auto_install=not args.no_auto_install,
    )

    if not deps.python_chess_ok:
        print(
            "python-chess could not be imported. "
            "Install it manually with `pip install python-chess` and re-run.",
            file=sys.stderr,
        )
        return 1

    if deps.stockfish_path is None:
        hint = (
            "Stockfish executable not found. Download it from "
            "https://stockfishchess.org/download/ and provide the path with "
            "--engine-path /path/to/stockfish."
        )
        print(hint, file=sys.stderr)
        return 1

    from ascii_chess.ai import EngineConfig
    from ascii_chess.game import GameController
    from ascii_chess.renderer import AsciiRenderer

    engine_config = EngineConfig(
        executable_path=deps.stockfish_path,
        min_rating=args.min_rating,
        max_rating=args.max_rating,
        default_think_time=args.think_time,
    )

    if args.cli:
        renderer = AsciiRenderer(use_unicode=not args.ascii_only)
        
        # Time control menu
        print("\n=== Chess Time Control ===")
        print("1. 3-minute Blitz")
        print("2. 10-minute Rapid")
        print("3. Unlimited Time")
        
        time_control = None
        while True:
            choice = input("\nSelect (1-3): ").strip()
            if choice == "1":
                time_control = 180  # 3 minutes
                break
            elif choice == "2":
                time_control = 600  # 10 minutes
                break
            elif choice == "3":
                time_control = None  # Unlimited
                break
            else:
                print("Invalid choice. Please enter a number between 1-3.")
        
        try:
            controller = GameController(
                renderer=renderer, 
                engine_config=engine_config, 
                time_control=time_control
            )
        except RuntimeError as exc:
            print(f"게임 초기화 실패: {exc}", file=sys.stderr)
            return 1
            
        controller.run()
        return 0

    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover - Tk may be missing
        print(f"Failed to load Tkinter: {exc}", file=sys.stderr)
        return 1

    from ascii_chess.gui import ChessGUI

    root = tk.Tk()
    try:
        gui = ChessGUI(root, engine_config, use_unicode=not args.ascii_only, time_control=args.time_control * 60)
        root.mainloop()
    except Exception as exc:  # pragma: no cover - unexpected errors
        print(f"Unexpected error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
