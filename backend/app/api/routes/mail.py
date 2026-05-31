from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.security import encrypt_secret
from app.db.session import get_session
from app.models import MailIntegration, User
from app.schemas.mail import MailImapConnectIn, MailOAuthUrlOut, MailStatusOut, MailSyncOut
from app.services.mail import (
    build_mail_oauth_url,
    create_demo_market_transactions,
    get_active_mail_integration,
    sync_mailru_imap,
    test_mailru_imap_credentials,
)


router = APIRouter()


@router.get("/status", response_model=MailStatusOut)
async def status(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    integration = await get_active_mail_integration(session, current_user.id)
    return {
        "connected": bool(integration),
        "provider": "mailru_imap",
        "mailbox_email": integration.mailbox_email if integration else None,
    }


@router.post("/connect", response_model=MailStatusOut)
async def connect_imap(
    payload: MailImapConnectIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    try:
        await test_mailru_imap_credentials(payload.mailbox_email, payload.app_password)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Не удалось подключиться к Mail.ru. Проверьте почту и пароль для внешнего приложения. "
                "Обычный пароль от почты обычно не подходит."
            ),
        ) from exc

    result = await session.execute(
        select(MailIntegration).where(
            MailIntegration.user_id == current_user.id,
            MailIntegration.provider == "mailru_imap",
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        integration = MailIntegration(user_id=current_user.id, provider="mailru_imap")
        session.add(integration)
    integration.mailbox_email = payload.mailbox_email.lower()
    integration.access_token = encrypt_secret(payload.app_password)
    integration.refresh_token = None
    integration.expires_at = None
    integration.is_active = True
    await session.commit()
    return {"connected": True, "provider": "mailru_imap", "mailbox_email": integration.mailbox_email}


@router.post("/sync", response_model=MailSyncOut)
async def sync_mail(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    integration = await get_active_mail_integration(session, current_user.id)
    if not integration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала подключите почту Mail.ru")
    created = await sync_mailru_imap(session, user_id=current_user.id, integration=integration)
    return {
        "created_transactions": created,
        "source": 'ООО "Яндекс Маркет"',
        "message": (
            f"Синхронизация завершена. Новых транзакций: {created}."
            if created
            else "Подключение работает, но подходящих писем Яндекс Маркета пока не найдено."
        ),
    }


@router.get("/oauth/url", response_model=MailOAuthUrlOut)
async def oauth_url(current_user: User = Depends(get_current_user)) -> dict:
    url = build_mail_oauth_url(state=str(current_user.id))
    if not url:
        return {
            "url": "",
            "enabled": False,
            "message": "OAuth2 Mail.ru не настроен. В демо-режиме можно запустить синхронизацию вручную.",
        }
    return {"url": url, "enabled": True, "message": None}


@router.get("/oauth/callback")
async def oauth_callback(request: Request) -> dict:
    return {
        "message": "OAuth callback получен. Для MVP токены можно сохранить здесь после обмена code на token.",
        "query": dict(request.query_params),
    }


@router.post("/sync-demo", response_model=MailSyncOut)
async def sync_demo(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    created = await create_demo_market_transactions(session, user_id=current_user.id)
    return {
        "created_transactions": created,
        "source": 'ООО "Яндекс Маркет"',
        "message": "Демо-чек прочитан и записан в транзакции.",
    }
