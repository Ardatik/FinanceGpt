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

По умолчанию frontend ходит в относительный `/api`, а Vite проксирует запросы и WebSocket в `http://127.0.0.1:8000`. Это удобно для туннелей и мобильной проверки.

## Запуск через туннель

Для Tuna/ngrok/localtunnel достаточно пробросить только frontend-порт `5173`:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

```bash
cd payment_service
uvicorn app.main:app --reload --port 8001
```

```bash
cd frontend
npm run dev:tunnel
```

```bash
tuna http 5173
```

Открывайте публичный URL туннеля. Запросы `/api/*` и WebSocket `/api/coach/ws` пройдут через Vite proxy в локальный backend.
Команда `dev:tunnel` отключает Vite HMR websocket, чтобы мобильный браузер не перезагружал страницу при нестабильном websocket-соединении через туннель.

Если хотите пробрасывать backend отдельным туннелем, укажите публичный backend URL в `frontend/.env`:

```env
VITE_API_URL=https://your-backend-tunnel.example/api
```

И добавьте frontend tunnel origin в `BACKEND_CORS_ORIGINS` в `backend/.env`.

## Основные сценарии

1. Неавторизованный пользователь видит краткую страницу проекта и входит по одноразовому коду.
2. При первом входе доступна только анкета. В цели можно выбрать готовый вариант или написать свою.
3. Главный экран показывает цель, недельную статистику, диагностику, лимит, AI-коуча, СБП и челлендж.
4. Интеграция с почтой работает простым путем: пользователь вводит Mail.ru и пароль для внешнего приложения, backend подключается к `imap.mail.ru:993`, ищет письма Яндекс Маркета и создает транзакции.
5. Финансовая подушка требует кодовое слово, поддерживает восстановление через почту и вычитает резерв из доступного бюджета.
6. Чат AI-коуча работает через WebSocket, стримит ответ и сохраняет историю.
7. APScheduler каждое воскресенье в 23:59 собирает недельный AI-синтез и подмешивает его в контекст коуча.
8. СБП-модалка поддерживает сканирование QR-кода с камеры. Для телефона нужен `https`-туннель или `localhost`, иначе браузер может не дать доступ к камере.

## Mail.ru IMAP

Для MVP OAuth не нужен. Пользователь должен создать пароль для внешнего приложения в настройках Mail.ru и ввести его в боковом меню FinancePay.

Backend использует:

```env
MAIL_IMAP_HOST=imap.mail.ru
MAIL_IMAP_PORT=993
MAIL_IMAP_SSL=true
```

Пароль внешнего приложения хранится в таблице `mail_integrations.access_token` в зашифрованном виде. Синхронизация читает последние письма из `INBOX`, фильтрует только разрешенных отправителей Яндекс Маркета и парсит позиции чека.
