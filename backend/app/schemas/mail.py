from pydantic import BaseModel, EmailStr, Field


class MailOAuthUrlOut(BaseModel):
    url: str
    enabled: bool
    message: str | None = None


class MailImapConnectIn(BaseModel):
    mailbox_email: EmailStr
    app_password: str = Field(min_length=4, max_length=255)


class MailStatusOut(BaseModel):
    connected: bool
    provider: str = "mailru_imap"
    mailbox_email: EmailStr | None = None


class MailSyncOut(BaseModel):
    created_transactions: int
    source: str
    message: str
