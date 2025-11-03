from __future__ import annotations

import importlib
import os
import shutil
import ssl
import sys
import subprocess
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ===== 의존성 상태 =====
@dataclass
class DependencyStatus:
    python_chess_ok: bool
    stockfish_path: Optional[str]


# ===== python-chess 확인 =====
def ensure_python_chess(auto_install: bool = True) -> bool:
    try:
        importlib.import_module("chess")
        return True
    except ModuleNotFoundError:
        if not auto_install:
            return False
        return _attempt_install_python_chess()


def _attempt_install_python_chess() -> bool:
    python_executable = sys.executable
    if not python_executable:
        return False
    result = subprocess.run(
        [python_executable, "-m", "pip", "install", "python-chess"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stdout)
        sys.stderr.write(result.stderr)
        return False
    try:
        importlib.import_module("chess")
    except ModuleNotFoundError:
        return False
    return True


# ===== 스톡피시 탐색 =====
def locate_stockfish(explicit_path: Optional[str]) -> Optional[str]:
    if explicit_path:
        resolved = _resolve_candidate(explicit_path)
        if resolved:
            return resolved

    # 시스템 PATH에서 찾기
    discovered = shutil.which("stockfish")
    if discovered:
        return discovered

    # 번들된 후보들에서 찾기
    for candidate in _bundled_candidates():
        resolved = _resolve_candidate(candidate)
        if resolved:
            return resolved
    
    # 아무것도 찾지 못한 경우 다운로드 시도
    print("\n🔍 Stockfish를 찾을 수 없어 다운로드를 시도합니다...")
    return _download_stockfish()


def _resolve_candidate(path: str) -> Optional[str]:
    expanded = os.path.abspath(os.path.expanduser(path))
    if os.path.isdir(expanded):
        return _find_executable_in_dir(expanded)
    if os.path.isfile(expanded):
        if _is_executable(expanded):
            return expanded
        if expanded.lower().endswith(".exe") and sys.platform.startswith("win"):
            return expanded
    located = shutil.which(expanded)
    if located:
        return located
    return None


def _find_executable_in_dir(directory: str) -> Optional[str]:
    for entry in sorted(os.listdir(directory)):
        full = os.path.join(directory, entry)
        if os.path.isdir(full):
            nested = _find_executable_in_dir(full)
            if nested:
                return nested
            continue
        if "stockfish" in entry.lower() and _is_executable(full):
            return full
        if "stockfish" in entry.lower() and sys.platform.startswith("win") and entry.lower().endswith(".exe"):
            return full
    return None


def _is_executable(path: str) -> bool:
    return os.access(path, os.X_OK)


# tqdm이 설치되어 있지 않으면 설치
try:
    # Python 3.4+
    from importlib import util as importlib_util
    has_tqdm = importlib_util.find_spec('tqdm') is not None
except (ImportError, AttributeError):
    # 이전 버전 호환성을 위한 폴백
    try:
        import pkg_resources
        has_tqdm = pkg_resources.get_distribution('tqdm') is not None
    except (ImportError, pkg_resources.DistributionNotFound):
        has_tqdm = False

if not has_tqdm:
    import subprocess
    import sys
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "tqdm"])
        print("✓ tqdm 패키지 설치 완료")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ tqdm 설치 실패: {e}")

class ProgressBar:
    def __init__(self, total_size: int) -> None:
        from tqdm import tqdm

        total = total_size if total_size > 0 else None
        self.pbar = tqdm(
            total=total,
            unit='iB',
            unit_scale=True,
            unit_divisor=1024,
            ncols=70,
            bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
        )

    def update(self, amount: int) -> None:
        if self.pbar:
            self.pbar.update(amount)

    def close(self) -> None:
        if self.pbar:
            self.pbar.close()
            self.pbar = None


def _ensure_certifi_context() -> Optional[ssl.SSLContext]:
    try:
        import certifi
    except ImportError:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "certifi"])
            import certifi  # type: ignore[redefined]
            print("✓ certifi 패키지를 설치했습니다.")
        except Exception as exc:
            print(f"⚠️ certifi 설치 실패: {exc}")
            return None

    try:
        return ssl.create_default_context(cafile=certifi.where())
    except Exception as exc:
        print(f"⚠️ certifi 기반 SSL 컨텍스트 생성 실패: {exc}")
        return None


def _open_url_with_ssl_fallback(url: str):
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ascii-chess/stockfish-downloader"
        },
    )

    try:
        return urllib.request.urlopen(request, timeout=30)
    except urllib.error.URLError as exc:
        if not isinstance(exc.reason, ssl.SSLError):
            raise

        certifi_context = _ensure_certifi_context()
        if certifi_context is None:
            raise
        return urllib.request.urlopen(request, context=certifi_context, timeout=30)

def _download_stockfish() -> Optional[str]:
    """GitHub 릴리스에서 Stockfish 다운로드"""
    import zipfile
    import tempfile
    import platform
    import os
    import tarfile
    from urllib.error import URLError
    
    base_dir = Path(__file__).resolve().parent.parent / "engines"
    base_dir.mkdir(exist_ok=True)
    
    # 시스템에 맞는 파일 선택
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "windows":
        if "arm" in machine:
            return None  # Windows ARM은 지원 안 함
        url = "https://github.com/official-stockfish/Stockfish/releases/download/sf_17.1/stockfish-windows-x86-64-avx2.zip"
        binary_name = "stockfish-windows-x86-64-avx2.exe"
    elif system == "darwin":  # macOS
        if "arm" in machine:
            # Apple Silicon (M1/M2) Mac
            url = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-macos-m1-apple-silicon.tar"
            binary_name = "stockfish"
        else:
            # Intel Mac
            url = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-macos-x86-64-avx2.tar"
            binary_name = "stockfish"
    elif system == "linux":
        # Linux with AVX2 support
        url = "https://github.com/official-stockfish/Stockfish/releases/latest/download/stockfish-ubuntu-x86-64-avx2.tar"
        binary_name = "stockfish"
    else:
        return None
    
    # stockfish 하위 디렉토리 생성
    stockfish_dir = base_dir / "stockfish"
    stockfish_dir.mkdir(parents=True, exist_ok=True)
    
    # 타겟 경로를 stockfish/stockfish.exe로 설정 (Windows) 또는 stockfish/stockfish (기타 OS)
    target_name = "stockfish.exe" if system == "windows" else "stockfish"
    target_path = stockfish_dir / target_name
    
    # 이미 파일이 있고 실행 가능하면 그대로 반환
    if target_path.exists() and os.access(target_path, os.X_OK):
        return str(target_path)
    
    print(f"\n📥 Stockfish 17.1 다운로드 중... ({system} {machine})")
    
    try:
        # 임시 파일로 다운로드
        archive_suffix = ''.join(Path(url).suffixes) or ('.zip' if system == 'windows' else '.tar')
        with tempfile.NamedTemporaryFile(delete=False, suffix=archive_suffix) as tmp_file:
            tmp_path = tmp_file.name
        
        # 파일 다운로드 (진행률 표시 및 SSL 인증서 문제 처리)
        print(f"다운로드: {url}")
        with closing(_open_url_with_ssl_fallback(url)) as response:
            total_size = getattr(response, "length", None)
            if not total_size:
                content_length = response.headers.get("Content-Length")
                total_size = int(content_length) if content_length else 0
            progress = ProgressBar(total_size)
            try:
                with open(tmp_path, "wb") as download_file:
                    while True:
                        chunk = response.read(32 * 1024)
                        if not chunk:
                            break
                        download_file.write(chunk)
                        progress.update(len(chunk))
            finally:
                progress.close()
        
        # 압축 해제 (진행률 표시)
        print("\n압축 해제 중...")
        if system == 'windows':
            with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                zip_ref.extractall(base_dir)
        else:
            # Determine the correct mode for tarfile
            if tmp_path.endswith('.tar.xz'):
                mode = 'r:xz'
            elif tmp_path.endswith('.tar.gz') or tmp_path.endswith('.tgz'):
                mode = 'r:gz'
            elif tmp_path.endswith('.tar'):
                mode = 'r:'
            else:
                mode = 'r:*'

            with tarfile.open(tmp_path, mode) as tar_ref:
                members = tar_ref.getmembers()
                total_members = len(members)
                for i, member in enumerate(members, 1):
                    tar_ref.extract(member, base_dir)
                    print(f"\r진행률: {i}/{total_members} 파일 처리 중...", end='')
            print()
        
        # 압축 해제된 파일 찾기
        # Windows의 경우 압축을 풀면 stockfish/stockfish-windows-x86-64-avx2.exe 구조로 풀릴 수 있음
        possible_paths = [
            base_dir / "stockfish" / f"stockfish-{machine}.exe",
            base_dir / f"stockfish-{machine}.exe",
            base_dir / binary_name,
            base_dir / "stockfish" / binary_name
        ]
        
        # 가능한 경로 중 존재하는 파일 찾기
        downloaded_path: Optional[Path] = None
        for path in possible_paths:
            if path.is_file():
                downloaded_path = path
                break
        
        if downloaded_path is None:
            # stockfish로 시작하는 파일이 있는지 재검색
            for f in base_dir.glob("**/stockfish*"):
                if f.is_file() and (f.suffix == '.exe' or 'stockfish' in f.name.lower()):
                    downloaded_path = f
                    break
        
        if downloaded_path is None or not downloaded_path.exists():
            raise FileNotFoundError(
                f"다운로드한 Stockfish 파일을 찾을 수 없습니다. 다음 위치에서 찾았습니다:\n" +
                "\n".join(f"- {p}" for p in possible_paths)
            )
        
        # 최종 경로 설정 (stockfish/stockfish.exe)
        final_path = stockfish_dir / target_name
        downloaded_path = downloaded_path.resolve()
        final_path_resolved = final_path.resolve()
        
        # 기존 파일이 있으면 삭제
        if final_path.exists() and final_path_resolved != downloaded_path:
            try:
                final_path.unlink()
            except Exception as e:
                print(f"⚠️ 기존 파일 삭제 중 오류: {e}")
        
        # stockfish 디렉토리 생성
        stockfish_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일 이동 및 권한 설정
        if downloaded_path != final_path_resolved:
            shutil.move(str(downloaded_path), str(final_path))
        final_path = final_path.resolve()
        if system != 'windows':
            final_path.chmod(0o755)
        
        print(f"✅ Stockfish가 성공적으로 설치되었습니다: {final_path}")
        return str(final_path)
        
    except (URLError, ssl.SSLError) as e:
        print(f"❌ 다운로드 실패: {e}")
        return None
    except Exception as e:
        print(f"❌ 다운로드 실패: {e}")
        return None
    finally:
        # 임시 파일 정리
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)

def _bundled_candidates() -> list[str]:
    base_dir = Path(__file__).resolve().parent.parent / "engines"
    if not base_dir.exists():
        # 엔진 디렉토리가 없으면 다운로드 시도
        downloaded = _download_stockfish()
        if downloaded:
            return [downloaded]
        return []

    candidates: list[str] = []
    for entry in sorted(base_dir.iterdir()):
        if "stockfish" in entry.name.lower():
            candidates.append(str(entry))
    
    # 후보가 없으면 다운로드 시도
    if not candidates:
        downloaded = _download_stockfish()
        if downloaded:
            return [downloaded]
    
    return candidates


# ===== 종합 결과 =====
def collect_dependency_status(engine_path: Optional[str], auto_install: bool = True) -> DependencyStatus:
    python_chess_ok = ensure_python_chess(auto_install=auto_install)
    stockfish_path = locate_stockfish(engine_path)
    return DependencyStatus(
        python_chess_ok=python_chess_ok,
        stockfish_path=stockfish_path,
    )
