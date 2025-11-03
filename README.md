# ASCII Chess

HANNAM Univ. Embedded system Fall - Vibe coding

team. holycow (20222328 윤여명, 20222305 지민우, 20222319 정재석)

---
Stockfish 엔진 기반의 봇을 상대로 플레이하는 Tkinter GUI 체스 게임 프로그램입니다. SAN 표기(SAN move notation)로 수를 입력해 게임을 진행합니다.

## 요구 사항
- Python 3.10 이상
- Stockfish 엔진 파일

## 실행 방법
```bash
python main.py [옵션]
or
python3 main.py [옵션]
```
실행 시 자동으로 아래 의존성 존재 여부 검사 및 없을 경우 설치를 진행합니다.
- `pip install python-chess`
- `ascii_chess/fonts/menlo-regular.ttf`

또한 자동으로 stockfish 웹사이트에서 사용자의 운영체제에 맞는 엔진을 설치 및 압축 해제하여 `engines/` 안에 위치시킵니다.

오류로 엔진이 설치되지 않거나, 인식되지 않는 경우엔 아래 절차에 따라 수동으로 엔진을 추가해주세요.

1. [Stockfish 공식 사이트](https://stockfishchess.org/download/)에서 운영체제에 맞는 패키지를 내려받습니다.
2. 압축을 해제한 뒤 실행 파일이 포함된 폴더 전체를 `engines/` 경로에 `stockfish/` 이름으로 복사합니다.  
   ```text
   ASCII_Chess/
     engines/
       stockfish/
         <stockfish binary>
   ```
3. 실행 파일 이름에 `stockfish`가 포함되어 있어야 하며, macOS/Linux는 `chmod +x`로 실행 권한을 부여해야 합니다.
4. 다른 이름의 하위 폴더·실행 파일이라도 이름에 `stockfish`가 포함돼 있으면 자동 탐색 대상에 포함됩니다.


릴리즈 버전의 실행에 관해서는 릴리즈 내 안내사항을 참고해주세요.

---
### 옵션
- `--engine-path /path/to/stockfish` : 수동으로 엔진 경로 지정 (지정하지 않으면 `engines/stockfish/` 및 하위 항목을 자동 탐색)
- `--ascii-only` : 유니코드 대신 ASCII 기물 사용
- `--no-auto-install` : `python-chess` 자동 설치 시도 비활성화

## 조작 요약
- 인트로 화면: `↑ / ↓`로 메뉴 이동, `Enter`로 선택
- 테마 설정: `Enter`로 세부 항목 진입, `Esc`로 이전 화면 복귀
- 게임 시작 순서: Enemy Elo 입력 → 게임 모드 선택 [1: Rapid(10분), 2: Blitz(3분), 3: Practice(무제한)] 선택
- 게임 중 명령어  
  - 일반 수: SAN 표기(`Nf3`, `O-O`, `cxd4` 등)  
  - `ff`: 기권  
  - `quit`: 즉시 프로그램 종료  
  - `undo` / `redo`: 직전 양측 수 되돌리기 / 다시 실행  
  - `hint`: 엔진 기반 최선의 수 제안 (해당 칸이 붉은색으로 점멸)

## 프로젝트 구조
- `main.py` : 실행 진입점 및 의존성 확인
- `ascii_chess/gui.py` : Tkinter GUI, 테마, 게임 진행 로직
- `ascii_chess/ai.py` : Stockfish 제어 래퍼
- `ascii_chess/deps.py` : python-chess 확인 및 엔진 자동 탐색
- `ascii_chess/fonts/` : Menlo 폰트 보관
- `engines/stockfish/` : 사용자 환경별 Stockfish 바이너리 위치 (버전 관리 제외)
