# TikTok Live Crawler

이 프로젝트는 현재 방송 중인 틱톡 스트리머들의 ID를 수집하는 크롤러입니다.
Python과 Playwright를 사용하여 틱톡 라이브 페이지를 탐색하고 활성 사용자 ID를 추출합니다.

## 요구 사항

- Python 3.8 이상
- `pip` 패키지 관리자

## 설치 방법

1. 필요한 패키지를 설치합니다:

```bash
pip install -r requirements.txt
playwright install chromium
```

## 사용 방법

크롤러를 실행하려면 다음 명령어를 터미널에 입력하세요:

```bash
python crawler.py
```

기본적으로 브라우저 창이 열리면서 크롤링 과정을 볼 수 있습니다 (`headless=False`).
만약 백그라운드에서 실행하고 싶다면 다음 옵션을 추가하세요:

```bash
python crawler.py --headless
```

**주의사항**:
- 틱톡은 봇 탐지 시스템이 강력하여 자동화된 브라우저를 차단하거나 캡차(Captcha)를 요구할 수 있습니다.
- 브라우저가 열렸을 때 캡차가 나오면 직접 풀어주어야 크롤링이 계속될 수 있습니다.
- "No LIVE streams for you yet" 메시지가 나오면 로그인이 안 된 상태이거나 지역 제한일 수 있습니다.

## 결과물

크롤링이 완료되면 `active_streamers.txt` 파일에 수집된 스트리머들의 ID 목록이 저장됩니다.

## 프론트 화면

수집된 크리에이터 목록을 브라우저에서 보기 위해 간단한 대시보드를 추가했습니다.

```bash
python -m http.server 8000
```

브라우저에서 `http://localhost:8000/index.html`을 열면 목록과 상태/메모를 확인할 수 있습니다.
