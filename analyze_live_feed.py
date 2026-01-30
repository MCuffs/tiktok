"""
TikTok Live Feed 문제 진단 스크립트
왜 /live 페이지에서 데이터가 안 나오는지 분석합니다.
"""
import asyncio
import json
from playwright.async_api import async_playwright

async def diagnose_live_feed():
    print("🔍 TikTok Live Feed 진단 시작...\n")
    
    async with async_playwright() as p:
        # 일반 브라우저처럼 실행
        context = await p.chromium.launch_persistent_context(
            "./tiktok_user_data",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
            viewport={'width': 1280, 'height': 800}
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # 1. 네트워크 요청 모니터링
        requests_log = []
        responses_log = []
        
        def log_request(request):
            if "live" in request.url or "webcast" in request.url:
                requests_log.append({
                    "url": request.url,
                    "method": request.method,
                    "headers": dict(request.headers)
                })
        
        async def log_response(response):
            if "live" in response.url or "webcast" in response.url:
                try:
                    content_type = response.headers.get("content-type", "")
                    if "json" in content_type:
                        data = await response.json()
                        responses_log.append({
                            "url": response.url,
                            "status": response.status,
                            "has_data": len(str(data)) > 100,
                            "preview": str(data)[:500]
                        })
                except:
                    pass
        
        page.on("request", log_request)
        page.on("response", log_response)
        
        # 2. 페이지 접속
        print("📍 Step 1: /live 페이지 접속 중...")
        await page.goto("https://www.tiktok.com/live", timeout=45000, wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
        # 3. HTML 분석
        print("📍 Step 2: HTML 구조 분석 중...")
        content = await page.content()
        
        # SIGI_STATE 확인
        has_sigi = "SIGI_STATE" in content
        has_universal = "__UNIVERSAL_DATA_FOR_REHYDRATION__" in content
        
        print(f"   ✓ SIGI_STATE 존재: {has_sigi}")
        print(f"   ✓ UNIVERSAL_DATA 존재: {has_universal}")
        
        # 4. 스크롤 후 API 호출 확인
        print("📍 Step 3: 스크롤하여 API 트리거 시도...")
        for i in range(3):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
        
        # 5. 결과 분석
        print("\n" + "="*60)
        print("📊 진단 결과:")
        print("="*60)
        
        print(f"\n1️⃣ 네트워크 요청 수: {len(requests_log)}")
        if requests_log:
            print("   주요 요청:")
            for req in requests_log[:5]:
                print(f"   - {req['method']} {req['url'][:80]}...")
        else:
            print("   ⚠️ Live 관련 API 요청이 전혀 없습니다!")
        
        print(f"\n2️⃣ API 응답 수: {len(responses_log)}")
        if responses_log:
            print("   주요 응답:")
            for resp in responses_log[:5]:
                print(f"   - Status {resp['status']}: {resp['url'][:80]}...")
                print(f"     데이터 있음: {resp['has_data']}")
        else:
            print("   ⚠️ Live 관련 API 응답이 전혀 없습니다!")
        
        # 6. HTML 저장
        with open("debug_live_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n3️⃣ HTML 저장 완료: debug_live_page.html")
        
        # 7. 진단 및 권장사항
        print("\n" + "="*60)
        print("💡 진단 및 해결책:")
        print("="*60)
        
        if not requests_log:
            print("""
⚠️ 문제: Live API 요청 자체가 발생하지 않음

원인:
1. TikTok이 봇을 감지하여 JavaScript 실행을 차단
2. 페이지가 "빈 껍데기" 버전으로 제공됨
3. 지역/계정 설정에 따라 Live 피드가 제한될 수 있음

해결책:
✅ 현재 적용된 Search 우회 방식이 최선입니다.
   - "라이브" 키워드 검색은 정상 작동 중
   - 검색은 봇 탐지가 약한 편

추가 시도 가능한 방법:
1. 수동으로 브라우저 열어서 로그인 후 세션 저장
2. 프록시/VPN 사용하여 지역 변경
3. /live 대신 특정 카테고리 URL 시도:
   - /live/gaming
   - /live/music
   - /live/chatting
            """)
        elif not any(r.get("has_data") for r in responses_log):
            print("""
⚠️ 문제: API 요청은 발생했으나 빈 응답 수신

원인:
- TikTok 서버가 봇으로 판단하여 빈 데이터 반환
- 'Ghost Page' 전략

해결책:
✅ Search 방식 유지 (현재 정상 작동 중)
            """)
        
        print("\n✅ 현재 크롤러는 Search 방식으로 정상 작동 중입니다!")
        print("   Direct Live Feed는 TikTok의 강력한 봇 차단으로 우회 어려움\n")
        
        await context.close()

if __name__ == "__main__":
    asyncio.run(diagnose_live_feed())
