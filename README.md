# FinancePay

FinancePay — PWA для рационального управления личными финансами. MVP закрывает хакатонный сценарий: вход по почте, первичная анкета, финансовая диагностика, расчет лимитов, финансовая подушка, AI-коуч, челленджи, демо-оплата по СБП и парсинг демо-чека от `ООО "Яндекс Маркет"`.

## Стек

- Backend: Python 3.11+, FastAPI, async SQLAlchemy, PostgreSQL.
- Фоновые задачи: APScheduler `AsyncIOScheduler` внутри FastAPI lifespan.
- AI: Gemini API через асинхронный `httpx`, JSON-ответы для категоризации, портрета, челленджей и недельного синтеза.
- Frontend: React + Vite + Tailwind CSS, PWA.
- Демо-оплата: отдельный FastAPI-сервис `payment_service`.

## Запуск backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

В `.env` укажите `DATABASE_URL` PostgreSQL и `GEMINI_API_KEY`. Если `GEMINI_API_KEY` пустой, приложение работает в fallback-режиме для демонстрации.

## Запуск demo payment service

```bash
cd payment_service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

## Запуск frontend

```bash
cd frontend
npm install
npm run dev
```






