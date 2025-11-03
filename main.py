from __future__ import annotations
import platform
import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

def is_admin():
    """Check if the script is running with administrator privileges (Windows only)"""
    if platform.system() != "Windows":
        return True
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        print(f"관리자 권한 확인 중 오류: {e}")
        return False

def check_and_install_package(package_name):
    # python-chess의 실제 임포트 이름은 'chess'이므로 처리
    import_name = package_name.replace('-', '_')
    if package_name == "python-chess":
        import_name = "chess"
    
    try:
        __import__(import_name)
        print(f"{package_name} 패키지가 이미 설치되어 있습니다.")
        return True
    except ImportError:
        print(f"{package_name} 패키지가 설치되어 있지 않아 설치를 시도합니다...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"{package_name} 패키지 설치 완료")
            return True
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] {package_name} 패키지 설치 실패: {e}")
            return False

def is_font_installed(font_name="menlo-regular.ttf"):
    """Check if the specified font is already installed"""
    if platform.system() != "Windows":
        return True  # Non-Windows systems are assumed to have the font
        
    try:
        import winreg
        # Check Windows Fonts directory
        font_dir = os.path.join(os.environ['WINDIR'], 'Fonts')
        if os.path.exists(os.path.join(font_dir, font_name)):
            # Check Windows registry
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts',
                    0, winreg.KEY_READ
                )
                try:
                    # Try to find the font in the registry
                    for i in range(winreg.QueryInfoKey(key)[1]):
                        name, value, _ = winreg.EnumValue(key, i)
                        if font_name.lower() in value.lower():
                            return True
                finally:
                    winreg.CloseKey(key)
            except WindowsError:
                pass
    except Exception as e:
        print(f"[WARNING] 폰트 확인 중 오류: {e}")
    return False

def install_font():
    if platform.system() == "Windows":
        font_name = "menlo-regular.ttf"
        # Check if font is already installed
        if is_font_installed(font_name):
            print(f"{font_name} 폰트가 이미 설치되어 있습니다.")
            return True
            
        # 폰트 경로 확인
        font_path = os.path.join("ascii_chess", "fonts", font_name)
        if not os.path.exists(font_path):
            font_path = os.path.join("fonts", font_name)
        
        if not os.path.exists(font_path):
            print(f"[ERROR] {font_path} 파일을 찾을 수 없습니다.")
            return False
            
        try:
            import ctypes
            import winreg
            
            font_dir = os.path.join(os.environ['WINDIR'], 'Fonts')
            target_path = os.path.join(font_dir, font_name)
            
            # 관리자 권한이 없으면 시도조차 하지 않음
            if not is_admin():
                print(f"[WARNING] {font_name} 폰트 설치를 위해 관리자 권한이 필요합니다.")
                return False
                
            # 폰트 복사
            try:
                shutil.copy2(font_path, font_dir)
                
                # 폰트 등록
                if not ctypes.windll.gdi32.AddFontResourceW(target_path):
                    print("[ERROR] 폰트 등록에 실패했습니다.")
                    return False
                    
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001D, 0, 0)
                
                # 레지스트리에 등록
                try:
                    key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, 
                                         r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts')
                    winreg.SetValueEx(key, font_name, 0, winreg.REG_SZ, font_name)
                    winreg.CloseKey(key)
                except WindowsError as e:
                    print(f"[ERROR] 레지스트리 등록 실패: {e}")
                    return False
                    
                print(f"{font_name} 폰트가 성공적으로 설치되었습니다.")
                return True
                
            except Exception as e:
                print(f"[ERROR] 폰트 설치 중 오류 발생: {e}")
                return False
            
        except Exception as e:
            print(f"[ERROR] 폰트 설치 중 오류 발생: {e}")
            return False
    
    elif platform.system() == "Darwin":  # macOS
        print("macOS는 기본적으로 Menlo 폰트가 설치되어 있습니다.")
        return True
    
    else:
        print(f"[ERROR] {platform.system()} 시스템은 자동 설치를 지원하지 않습니다.")
        return False

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ASCII Chess GUI vs Stockfish")
    parser.add_argument("--engine-path", default=None, help="Path to Stockfish executable.")
    parser.add_argument("--min-rating", type=int, default=1350, help="Minimum Stockfish Elo.")
    parser.add_argument("--max-rating", type=int, default=2850, help="Maximum Stockfish Elo.")
    parser.add_argument("--think-time", type=float, default=0.5, help="Default think time per AI move.")
    parser.add_argument("--ascii-only", action="store_true", help="Use ASCII pieces instead of Unicode.")
    parser.add_argument("--no-auto-install", action="store_true", help="Skip python-chess auto-installation.")
    parser.add_argument("--skip-fonts", action="store_true", help="Skip font installation.")
    parser.add_argument("--skip-stockfish", action="store_true", help=argparse.SUPPRESS)  # 내부용
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> int:
    # 스크립트 디렉토리로 작업 디렉토리 변경 (관리자 모드에서도 올바른 경로 유지)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    args = parse_args(argv or sys.argv[1:])

    print("\n[INFO] 프로그램 초기화 중...")
    
    # 필요한 패키지 설치
    if not check_and_install_package("python-chess"):
        print("\n[ERROR] python-chess 패키지 설치에 실패했습니다.")
        if platform.system() == "Windows":
            input("계속하려면 엔터 키를 누르세요...")
        return 1

    # Stockfish 확인 (관리자 권한 없이도 가능)
    stockfish_path = None # Initialize stockfish_path
    if not args.skip_stockfish:
        print("\n[INFO] Chess Engine을 확인 중입니다...")
        from ascii_chess.deps import collect_dependency_status, _download_stockfish
        
        try:
            # Stockfish 경로 확인
            if args.engine_path:
                stockfish_path = args.engine_path
            else:
                # engines/stockfish/stockfish.exe 또는 engines/stockfish.exe 경로 확인
                possible_paths = [
                    os.path.join("engines", "stockfish", "stockfish.exe"),
                    os.path.join("engines", "stockfish.exe"),
                    "stockfish.exe"
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        stockfish_path = os.path.abspath(path)
                        break
                
                # 찾지 못한 경우 다운로드 시도
                if not stockfish_path:
                    print("Stockfish를 찾을 수 없어 다운로드를 시도합니다...")
                    stockfish_path = _download_stockfish()
            
            if not stockfish_path or not os.path.exists(stockfish_path):
                print("\n[ERROR] Chess Engine을 찾을 수 없습니다.")
                if platform.system() == "Windows":
                    input("계속하려면 엔터 키를 누르세요...")
                return 1
                
            print(f"Chess Engine이 준비되었습니다: {stockfish_path}")
        except Exception as e:
            print(f"\n[WARNING] Chess Engine 확인 중 오류 발생: {e}")
            if platform.system() == "Windows":
                input("계속하려면 엔터 키를 누르세요...")
            return 1

    # 폰트 설치 (관리자 권한 필요)
    if not args.skip_fonts and platform.system() == "Windows":
        print("\n[INFO] 필요한 폰트를 확인 중입니다...")
        try:
            if is_font_installed():
                print("필요한 폰트가 이미 설치되어 있습니다.")
            elif is_admin():
                # 관리자 모드로 실행된 경우
                install_font()
            else:
                print("\n[WARNING] 폰트 설치를 위해 관리자 권한이 필요합니다.")
                print("관리자 권한으로 다시 실행하시겠습니까? (Y/N): ", end='')
                if input().strip().lower() == 'y':
                    import ctypes
                    script = os.path.abspath(__file__)
                    params = ' '.join(['--skip-stockfish'] + [arg for arg in sys.argv[1:] if arg != '--skip-stockfish'])
                    print(f"\n[INFO] 관리자 권한으로 다시 실행합니다...")
                    result = ctypes.windll.shell32.ShellExecuteW(
                        None, "runas", sys.executable, f'"{script}" {params}', None, 1
                    )
                    if result <= 32:  # ShellExecute 실패 시
                        print("[WARNING] 관리자 권한을 얻지 못했습니다. 기본 폰트로 계속 진행합니다.")
                    else:
                        return 0  # 관리자 권한으로 새 프로세스가 시작되므로 종료
                else:
                    print("[WARNING] 기본 폰트로 계속 진행합니다.")
        except Exception as e:
            print(f"[WARNING] 폰트 확인/설치 중 오류 발생: {e}")
            print("[WARNING] 기본 폰트로 계속 진행합니다.")

    # GUI 실행
    try:
        import tkinter as tk
        from ascii_chess.ai import EngineConfig
        from ascii_chess.gui import ChessGUI

        print("\n[INFO] 체스 게임을 시작합니다...")
        
        engine_config = EngineConfig(
            executable_path=stockfish_path,
            min_rating=args.min_rating,
            max_rating=args.max_rating,
            default_think_time=args.think_time,
        )

        root = tk.Tk()
        ChessGUI(root, engine_config=engine_config, use_unicode=not args.ascii_only)
        root.mainloop()
        return 0
        
    except Exception as e:
        print(f"\n[ERROR] GUI 실행 중 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()
        if platform.system() == "Windows":
            input("\n계속하려면 엔터 키를 누르세요...")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"\n[ERROR] 치명적 오류가 발생했습니다: {e}")
        import traceback
        traceback.print_exc()
        if platform.system() == "Windows":
            input("\n계속하려면 엔터 키를 누르세요...")
        sys.exit(1)
