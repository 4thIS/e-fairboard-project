# E-FairBoard 백엔드

하드웨어 없이 동작하는 가상 모드가 기본이다. `TRANSPORT_MODE=serial`은
하드웨어 도착 후 활성화(스펙 §10).

## 실행

```powershell
cd server/backend
python -m venv .venv ; .venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # ADMIN_PASSWORD 수정
uvicorn app.main:create_app --factory --reload --port 8000
```

- API 문서: http://localhost:8000/docs
- 로그인: `POST /api/auth/login {"password": "..."}` → 이후 `Authorization: Bearer <token>`
- 가상 노드 2개(0x01, 0x02)가 서버와 함께 뜬다. 손실률·전원은 `/api/sim/*`로 조작.

## 테스트

```powershell
python -m pytest -q
```

## 구조

`app/protocol`(패킷·CRC16·COBS·링크 — 펌웨어 레퍼런스), `app/transport`(가상/시리얼),
`app/simulator`(가상 게이트웨이·노드), `app/services`(배포·예약·모니터·통계),
`app/routers`(REST API), `app/store.py`(메모리+JSON 스냅샷).
설계 문서: `docs/web/2026-07-08-web-design.md`
