from __future__ import annotations

import asyncio
import json
import sys

import httpx
import websockets


BASE_URL = "http://127.0.0.1:8000/api"
WS_URL = "ws://127.0.0.1:8000/api/coach/ws"


async def check_websocket(token: str) -> str:
    answer = ""
    async with websockets.connect(f"{WS_URL}?token={token}") as websocket:
        await websocket.send(json.dumps({"message": "Объясни мой недельный лимит коротко"}))
        while True:
            payload = json.loads(await websocket.recv())
            if payload["type"] == "token":
                answer += payload["token"]
            if payload["type"] == "done":
                return answer.strip()
            if payload["type"] == "error":
                raise RuntimeError(payload["message"])


def main() -> int:
    client = httpx.Client(timeout=15)
    email = "demo@example.com"

    code_response = client.post(f"{BASE_URL}/auth/request-code", json={"email": email})
    code_response.raise_for_status()
    code = code_response.json()["demo_code"]

    token_response = client.post(f"{BASE_URL}/auth/verify", json={"email": email, "code": code})
    token_response.raise_for_status()
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    profile_payload = {
        "name": "Демо пользователь",
        "gender": "не хочу отвечать",
        "age": 28,
        "city": "Москва",
        "monthly_income": 120000,
        "income_bucket": "80-120",
        "income_sources": ["работа"],
        "family_status": "один",
        "debt_status": "нет",
        "situation": "стабильно без накоплений",
        "financial_goal": "своя цель",
        "custom_goal": "накопить на отпуск",
        "goal_target_amount": 100000,
        "goal_saved_amount": 25000,
        "goal_due_date": None,
        "fixed_expenses": {"жилье": 35000, "связь": 1000},
        "essential_monthly_expenses": 42000,
        "static_debt_payments": 0,
        "wants_challenges": True,
    }
    client.put(f"{BASE_URL}/profile", json=profile_payload, headers=headers).raise_for_status()

    dashboard = client.get(f"{BASE_URL}/dashboard", headers=headers)
    dashboard.raise_for_status()

    client.post(f"{BASE_URL}/cushion/setup", json={"code_word": "reserve"}, headers=headers).raise_for_status()
    unlock = client.post(f"{BASE_URL}/cushion/unlock", json={"code_word": "reserve"}, headers=headers)
    unlock.raise_for_status()
    cushion_token = unlock.json()["cushion_token"]
    client.put(
        f"{BASE_URL}/cushion/reserve",
        json={"reserved_amount": 15000},
        headers={**headers, "X-Cushion-Token": cushion_token},
    ).raise_for_status()

    client.post(
        f"{BASE_URL}/transactions",
        json={"merchant": "Кафе", "title": "Кофе с собой", "amount": 280},
        headers=headers,
    ).raise_for_status()

    payment = client.post(
        f"{BASE_URL}/payments/start",
        json={"bank": "sber", "amount": 1290, "merchant": 'ООО "Яндекс Маркет"'},
        headers=headers,
    )
    payment.raise_for_status()
    payment_id = payment.json()["id"]
    client.post(f"{BASE_URL}/payments/{payment_id}/confirm", headers=headers).raise_for_status()

    history = client.get(f"{BASE_URL}/coach/history", headers=headers)
    history.raise_for_status()
    ws_answer = asyncio.run(check_websocket(token))
    final_dashboard = client.get(f"{BASE_URL}/dashboard", headers=headers)
    final_dashboard.raise_for_status()
    data = final_dashboard.json()
    print(
        "OK",
        {
            "goal": data["goal"]["title"],
            "weekly_limit": data["limit"]["weekly_limit"],
            "reserved": data["reserved_cushion"],
            "history_messages": len(history.json()),
            "ws_answer_chars": len(ws_answer),
        },
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SMOKE FAILED: {exc}", file=sys.stderr)
        raise
