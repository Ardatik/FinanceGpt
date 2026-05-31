from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any, AsyncIterator
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.prompts import COACH_SYSTEM_PROMPT


logger = logging.getLogger(__name__)


class CategorizedItem(BaseModel):
    category: str = Field(description="Короткая категория покупки")
    category_kind: str = Field(description="essential или optimizable")
    impulse_type: str | None = Field(default=None, description="Тип импульсивной траты, если применимо")
    confidence: float = Field(ge=0, le=1)


class WeeklySynthesisResult(BaseModel):
    summary_md: str
    patterns: list[str] = Field(default_factory=list)
    suggested_challenge: str | None = None
    risk_level: str = "normal"


class FinancialPortraitResult(BaseModel):
    summary: str
    spending_signals: list[str] = Field(default_factory=list)
    psychological_hypotheses: list[str] = Field(default_factory=list)
    financial_risks: list[str] = Field(default_factory=list)
    challenge_preferences: list[str] = Field(default_factory=list)
    suggested_focuses: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ChallengeOptionResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    title: str
    description: str
    duration_days: int = Field(ge=1, le=30)
    total_steps: int = Field(ge=1, le=30)
    expected_saving: Decimal = Field(ge=0)
    markers: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str


class ChallengeOptionsResult(BaseModel):
    options: list[ChallengeOptionResult] = Field(default_factory=list, max_length=3)


def fallback_category(title: str, merchant: str = "") -> CategorizedItem:
    text = f"{title} {merchant}".lower()
    essentials = ["еда", "продукт", "аптека", "лекар", "транспорт", "жкх", "связь", "молоко", "хлеб"]
    if any(word in text for word in essentials):
        return CategorizedItem(category="Обязательные траты", category_kind="essential", confidence=0.66)
    impulse = None
    if any(word in text for word in ["кофе", "кафе", "игра", "подписка", "маркет"]):
        impulse = "гедонистическая мотивация"
    return CategorizedItem(
        category="Оптимизируемые траты",
        category_kind="optimizable",
        impulse_type=impulse,
        confidence=0.58,
    )


def parse_json_text(text: str) -> Any:
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?", "", clean).strip()
        clean = re.sub(r"```$", "", clean).strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        start_candidates = [index for index in (clean.find("{"), clean.find("[")) if index >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        end = max(clean.rfind("}"), clean.rfind("]"))
        if end <= start:
            raise
        return json.loads(clean[start : end + 1])


def stream_text_chunks(text: str) -> AsyncIterator[str]:
    async def iterator() -> AsyncIterator[str]:
        for chunk in re.findall(r"\S+\s*", text):
            yield chunk

    return iterator()


def money_text(value: Any) -> str:
    try:
        amount = Decimal(str(value or 0)).quantize(Decimal("1"))
    except Exception:
        amount = Decimal("0")
    return f"{amount:,.0f}".replace(",", " ") + " ₽"


class AIService:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.gemini_api_key = settings.gemini_api_key
        self.gemini_model = settings.gemini_model
        self.gemini_base_url = settings.gemini_api_base_url.rstrip("/")

    @property
    def is_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    async def _gemini_generate(
        self,
        *,
        system: str,
        prompt: str,
        temperature: float = 0.4,
        expect_json: bool = False,
    ) -> str:
        if not self.gemini_api_key:
            raise RuntimeError("Gemini API key is not configured")
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": 4096,
        }
        if expect_json:
            generation_config["responseMimeType"] = "application/json"
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                f"{system.strip()}\n\n"
                                f"{prompt.strip()}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": generation_config,
        }
        url = f"{self.gemini_base_url}/models/{self.gemini_model}:generateContent"
        async with httpx.AsyncClient(timeout=self.settings.gemini_timeout_seconds) as client:
            response = await client.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "X-goog-api-key": self.gemini_api_key,
                },
                json=payload,
            )
            response.raise_for_status()
        data = response.json()
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts).strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response")
        return text

    async def _gemini_parse_model(
        self,
        *,
        model: type[BaseModel],
        system: str,
        prompt: str,
        temperature: float = 0.2,
    ) -> BaseModel:
        schema = model.model_json_schema()
        text = await self._gemini_generate(
            system=system,
            prompt=(
                f"{prompt}\n\n"
                "Верни только JSON без Markdown. JSON должен соответствовать этой схеме:\n"
                f"{json.dumps(schema, ensure_ascii=False)}"
            ),
            temperature=temperature,
            expect_json=True,
        )
        return model.model_validate(parse_json_text(text))

    async def categorize_purchase(self, *, title: str, merchant: str, amount: Decimal) -> CategorizedItem:
        if not self.is_enabled:
            return fallback_category(title, merchant)
        prompt = (
            "Категоризируй покупку для личных финансов. "
            "category_kind должен быть essential для жизненно важных расходов или optimizable для гибких расходов. "
            f"Магазин: {merchant}. Покупка: {title}. Сумма: {amount}."
        )
        try:
            parsed = await self._gemini_parse_model(
                model=CategorizedItem,
                system="Верни строго валидный JSON для CategorizedItem.",
                prompt=prompt,
            )
            return parsed
        except Exception:
            logger.exception("Gemini purchase categorization failed, using local fallback")
            return fallback_category(title, merchant)
        return fallback_category(title, merchant)

    async def weekly_synthesis(self, *, payload: dict[str, Any]) -> WeeklySynthesisResult:
        if not self.is_enabled:
            return WeeklySynthesisResult(
                summary_md=(
                    "### Недельный синтез\n"
                    "Данных достаточно для базового наблюдения. "
                    "Стоит сравнить обязательные и оптимизируемые траты и выбрать один небольшой эксперимент."
                ),
                patterns=["fallback-синтез без Gemini ключа"],
                suggested_challenge="7 дней отслеживать спонтанные покупки",
            )
        try:
            parsed = await self._gemini_parse_model(
                model=WeeklySynthesisResult,
                system=COACH_SYSTEM_PROMPT,
                prompt=(
                    "Сделай недельный синтез по финансовым данным. "
                    "Пиши без оценок и без советов в директивной форме.\n"
                    f"{json.dumps(payload, ensure_ascii=False, default=str)}"
                ),
            )
            return parsed
        except Exception:
            logger.exception("Gemini weekly synthesis failed")
        return WeeklySynthesisResult(
            summary_md="### Недельный синтез\nИИ временно недоступен. Данные сохранены для следующего анализа.",
            patterns=[],
            suggested_challenge=None,
        )

    async def update_financial_portrait(
        self,
        *,
        existing_portrait: dict[str, Any] | None,
        profile: dict[str, Any] | None,
        receipt: dict[str, Any],
    ) -> FinancialPortraitResult:
        if not self.is_enabled:
            return self._fallback_portrait(existing_portrait=existing_portrait, receipt=receipt)
        try:
            parsed = await self._gemini_parse_model(
                model=FinancialPortraitResult,
                system=(
                    "Ты обновляешь финансово-психологический портрет пользователя FinancePay. "
                    "Опирайся только на анкету, предыдущий портрет и товары в чеке. "
                    "Формулируй гипотезы осторожно: это наблюдения, а не диагнозы. "
                    "Ищи повторяющиеся типы трат, возможные потребности за покупками, "
                    "мягкие фокусы для будущих 7-дневных челленджей."
                ),
                prompt=json.dumps(
                    {
                        "previous_portrait": existing_portrait or {},
                        "profile": profile or {},
                        "receipt": receipt,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            )
            return parsed
        except Exception:
            logger.exception("Financial portrait update failed, using local fallback")
        return self._fallback_portrait(existing_portrait=existing_portrait, receipt=receipt)

    async def challenge_options(self, *, context: dict[str, Any]) -> ChallengeOptionsResult:
        if not self.is_enabled:
            return self._fallback_challenge_options(context)
        try:
            parsed = await self._gemini_parse_model(
                model=ChallengeOptionsResult,
                system=(
                    COACH_SYSTEM_PROMPT
                    + "\n\nСформулируй до 3 микро-челленджей. "
                    "Каждый челлендж — это добровольный эксперимент, а не обязанность. "
                    "Он должен опираться на финансовые цифры, психологические гипотезы портрета "
                    "и товары из последних чеков. Не выдумывай факты. "
                    "Не предлагай челлендж без связи с данными пользователя. "
                    "Пиши конкретно: что делать 7 дней, зачем это связано с целью, "
                    "какую потребность заменяем более мягкой альтернативой."
                ),
                prompt=json.dumps(context, ensure_ascii=False, default=str),
                temperature=0.6,
            )
            if parsed and parsed.options:
                return self._normalize_challenge_options(parsed)
        except Exception:
            logger.exception("Challenge option generation failed, using local fallback")
        return self._fallback_challenge_options(context)

    async def stream_coach(
        self,
        *,
        context: str,
        context_payload: dict[str, Any] | None = None,
        history: list[dict[str, str]],
        user_message: str,
    ) -> AsyncIterator[str]:
        if not self.is_enabled:
            async for chunk in stream_text_chunks(self.local_coach_answer(user_message, context_payload=context_payload)):
                yield chunk
            return

        history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history[-12:])
        try:
            answer = await self._gemini_generate(
                system=(
                    COACH_SYSTEM_PROMPT
                    + "\n\nОтвечай живо и по делу. Не повторяй шаблонные фразы. "
                    "Сначала пойми конкретное желание пользователя, затем используй цифры, портрет и покупки. "
                    "Если пользователь хочет экономить, помоги найти маленький реалистичный шаг."
                ),
                prompt=(
                    f"{context}\n\n"
                    f"Последняя история диалога:\n{history_text or 'пока нет'}\n\n"
                    f"Вопрос пользователя: {user_message}\n\n"
                    "Ответь на русском. 1-3 коротких абзаца. "
                    "Если есть цифры, покажи расчет. Заверши одним вопросом или конкретным следующим шагом."
                ),
                temperature=0.7,
            )
            async for chunk in stream_text_chunks(answer):
                yield chunk
        except httpx.HTTPError as exc:
            logger.warning("Gemini coach request failed, using local fallback: %s", exc.__class__.__name__)
            async for chunk in stream_text_chunks(self.local_coach_answer(user_message, context_payload=context_payload)):
                yield chunk
        except Exception:
            logger.exception("Unexpected coach stream error, using local fallback")
            async for chunk in stream_text_chunks(self.local_coach_answer(user_message, context_payload=context_payload)):
                yield chunk

    def local_coach_answer(self, user_message: str, *, context_payload: dict[str, Any] | None = None) -> str:
        context_payload = context_payload or {}
        text = user_message.lower()
        income = Decimal(str(context_payload.get("monthly_income") or 0))
        mandatory = Decimal(str(context_payload.get("mandatory_expenses") or 0))
        reserve = Decimal(str(context_payload.get("reserved_cushion") or 0))
        spent = Decimal(str(context_payload.get("monthly_spent") or 0))
        optimized = Decimal(str(context_payload.get("optimized_expenses") or 0))
        free = Decimal(str(context_payload.get("free_after_reserve") or max(Decimal("0"), income - mandatory - reserve)))
        portrait = context_payload.get("portrait") or {}
        recent = context_payload.get("recent_transactions") or []

        if any(word in text for word in ["доход", "зарплат", "сберечь", "эконом"]):
            remaining_after_spent = max(Decimal("0"), free - spent)
            return (
                f"Смотри по твоим данным: доход {money_text(income)}, обязательная нагрузка {money_text(mandatory)}, "
                f"резерв {money_text(reserve)}. После этого остается около {money_text(free)} на месяц. "
                f"Уже видно расходов на {money_text(spent)}, значит ориентир остатка сейчас около {money_text(remaining_after_spent)}.\n\n"
                "Чтобы сберечь к концу месяца, я бы начал не с жесткого запрета, а с одной границы: "
                "отделить обязательные покупки от свободных и поставить дневной коридор для свободных трат. "
                "Какую сумму в день тебе было бы реально держать без ощущения, что тебя зажали?"
            ).strip()
        if any(word in text for word in ["лимит", "остат", "нагруз"]):
            weekly = max(Decimal("0"), free / Decimal("4.345")) if free else Decimal("0")
            return (
                f"Формула такая: доход {money_text(income)} минус обязательные платежи {money_text(mandatory)} "
                f"минус резерв {money_text(reserve)}. Получается примерно {money_text(free)} свободного пространства на месяц, "
                f"или около {money_text(weekly)} в неделю.\n\n"
                f"Отдельно вижу оптимизируемые траты: {money_text(optimized)}. "
                "Именно там обычно есть место для экономии без риска тронуть базовые расходы. "
                "Хочешь, разложим оптимизируемые траты по последним покупкам?"
            ).strip()
        if any(word in text for word in ["цель", "накоп", "копить"]):
            return (
                "Прогресс по цели считается как уже накопленная сумма, деленная на сумму цели. "
                "Если суммы цели нет, прогресс будет приблизительным. "
                f"Сейчас для движения к цели важнее всего свободный остаток: около {money_text(free)} до учета текущих трат.\n\n"
                "Можно выбрать один мягкий рычаг: уменьшить повторяющуюся свободную покупку, "
                "или заранее отложить маленькую фиксированную сумму после дохода. Что тебе ближе?"
            ).strip()
        if any(word in text for word in ["портрет", "категор", "покуп", "чек", "товар", "трат"]):
            focus = ", ".join((portrait.get("suggested_focuses") or [])[:3]) or "пока фокус уточняется по новым чекам"
            last_items = ", ".join(transaction.get("title", "") for transaction in recent[:5] if transaction.get("title"))
            return (
                f"По портрету сейчас главный фокус: {focus}. "
                f"В последних покупках вижу: {last_items or 'пока мало товаров для уверенного вывода'}.\n\n"
                "Я бы смотрел не только на сумму, а на повторяемость: какие покупки возвращаются чаще всего "
                "и какую потребность они закрывают. Начнем с категории, где трата приятная, но не обязательная?"
            ).strip()
        if "челлендж" in text:
            focus = ", ".join((portrait.get("suggested_focuses") or [])[:2]) or "одна небольшая свободная трата"
            return (
                f"Челлендж лучше делать не как запрет, а как эксперимент. По текущему портрету можно взять фокус: {focus}.\n\n"
                "Хороший формат: 7 дней наблюдать одну повторяющуюся трату, пробовать замену и считать эффект. "
                "Если хочешь, нажми «Выбрать челлендж» на дашборде, и я предложу несколько вариантов."
            ).strip()
        return (
            f"Давай разберем это через твою текущую картину: доход {money_text(income)}, "
            f"обязательная нагрузка {money_text(mandatory)}, свободное пространство около {money_text(free)}. "
            "Для рациональных трат полезно выбрать одну зону, а не пытаться чинить все сразу.\n\n"
            "Что сейчас важнее: сохранить больше до конца месяца, понять последние покупки или найти одну категорию для экономии?"
        ).strip()

    def _normalize_challenge_options(self, result: ChallengeOptionsResult) -> ChallengeOptionsResult:
        normalized: list[ChallengeOptionResult] = []
        for option in result.options[:3]:
            option.id = option.id or uuid4().hex[:8]
            option.duration_days = max(1, min(30, option.duration_days))
            option.total_steps = max(1, min(30, option.total_steps))
            if not option.markers:
                option.markers = [{"label": str(index + 1), "completed": False} for index in range(option.total_steps)]
            normalized.append(option)
        return ChallengeOptionsResult(options=normalized)

    def _fallback_portrait(
        self,
        *,
        existing_portrait: dict[str, Any] | None,
        receipt: dict[str, Any],
    ) -> FinancialPortraitResult:
        items = receipt.get("items") or []
        titles = [str(item.get("title", "")).lower() for item in items]
        total = sum((Decimal(str(item.get("amount", 0))) for item in items), Decimal("0"))
        signals = [f"Последний чек: {receipt.get('merchant', 'магазин')} на {total} ₽."]
        if titles:
            signals.append("В чеке есть: " + ", ".join(title[:40] for title in titles[:6]) + ".")
        hypotheses: list[str] = []
        focuses: list[str] = []
        if any(word in " ".join(titles) for word in ["кофе", "кафе", "чай", "десерт"]):
            hypotheses.append("Похоже, часть свободных трат может быть связана с маленькими ритуалами удовольствия.")
            focuses.append("бережная замена регулярных покупок кофе или сладкого")
        if any(word in " ".join(titles) for word in ["скид", "акция", "маркет"]):
            hypotheses.append("Есть слабая гипотеза про чувствительность к акциям и покупкам по случаю.")
            focuses.append("пауза перед покупками по скидке")
        if not hypotheses:
            hypotheses.append("По одному чеку рано делать выводы, но его можно использовать как точку наблюдения.")
            focuses.append("7 дней замечать необязательные покупки без самокритики")
        previous = existing_portrait or {}
        previous_signals = previous.get("spending_signals") or []
        return FinancialPortraitResult(
            summary="Портрет обновлен по последнему чеку и сохраненным данным пользователя.",
            spending_signals=[*previous_signals[-4:], *signals][-8:],
            psychological_hypotheses=[*((previous.get("psychological_hypotheses") or [])[-3:]), *hypotheses][-6:],
            financial_risks=previous.get("financial_risks") or [],
            challenge_preferences=[
                "короткие эксперименты на 7 дней",
                "один маленький шаг без запрета и давления",
                "варианты с заменой потребности, а не просто отказом",
            ],
            suggested_focuses=[*((previous.get("suggested_focuses") or [])[-3:]), *focuses][-6:],
            confidence=0.55,
        )

    def _fallback_challenge_options(self, context: dict[str, Any]) -> ChallengeOptionsResult:
        portrait = context.get("portrait") or {}
        recent = context.get("recent_transactions") or []
        focus = (portrait.get("suggested_focuses") or ["замечать необязательные покупки"])[0]
        optimized = Decimal(str(context.get("optimized_expenses") or 0))
        saving = max(Decimal("300"), min(Decimal("2500"), (optimized * Decimal("0.15")).quantize(Decimal("1"))))
        base_reason = "Основано на анкете, последних тратах и сохраненном портрете."
        options = [
            ChallengeOptionResult(
                id="pause7",
                title="7 дней короткой паузы перед свободной покупкой",
                description=(
                    "Перед необязательной покупкой сделать паузу на 10 минут и записать, "
                    "какую потребность она закрывает. Это эксперимент, не запрет."
                ),
                duration_days=7,
                total_steps=7,
                expected_saving=saving,
                markers=[{"label": str(index + 1), "completed": False} for index in range(7)],
                rationale=f"{base_reason} Фокус: {focus}.",
            ),
            ChallengeOptionResult(
                id="replace7",
                title="7 дней мягкой замены одной повторяющейся траты",
                description=(
                    "Выбрать одну небольшую регулярную трату и 7 дней пробовать более дешевую замену. "
                    "Если не получится, это данные для анализа."
                ),
                duration_days=7,
                total_steps=7,
                expected_saving=max(Decimal("300"), saving * Decimal("0.8")),
                markers=[{"label": str(index + 1), "completed": False} for index in range(7)],
                rationale=base_reason,
            ),
        ]
        if recent:
            options.append(
                ChallengeOptionResult(
                    id="receipt7",
                    title="7 дней разбирать чек на обязательное и свободное",
                    description=(
                        "После покупки отметить в чеке, что было обязательным, а что свободным. "
                        "Цель — увидеть картину, а не ругать себя."
                    ),
                    duration_days=7,
                    total_steps=7,
                    expected_saving=max(Decimal("300"), saving * Decimal("0.6")),
                    markers=[{"label": str(index + 1), "completed": False} for index in range(7)],
                    rationale="Основано на появившихся товарах в чеках.",
                )
            )
        return ChallengeOptionsResult(options=options[:3])
