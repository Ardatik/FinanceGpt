import { LogOut, Mail, PenLine, PiggyBank, Target, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { apiRequest, formatMoney } from "../lib/api";

export default function SideMenu({ open, onClose, token, dashboard, onNavigate, onLogout, onRefresh }) {
  const [mailState, setMailState] = useState(null);
  const [mailPanelOpen, setMailPanelOpen] = useState(false);
  const [mailStatus, setMailStatus] = useState(null);
  const [mailboxEmail, setMailboxEmail] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || !token) return;
    apiRequest("/mail/status", { token })
      .then((status) => {
        setMailStatus(status);
        setMailboxEmail(status.mailbox_email || "");
      })
      .catch(() => {});
  }, [open, token]);

  if (!open) return null;

  async function connectMail(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const status = await apiRequest("/mail/connect", {
        method: "POST",
        token,
        body: { mailbox_email: mailboxEmail, app_password: appPassword }
      });
      setMailStatus(status);
      setAppPassword("");
      setMailState(`Почта подключена: ${status.mailbox_email}`);
      onRefresh?.();
    } catch (error) {
      setMailState(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function syncMail(useDemo = false) {
    setBusy(true);
    try {
      const sync = await apiRequest(useDemo ? "/mail/sync-demo" : "/mail/sync", { method: "POST", token });
      setMailState(sync.message);
      onRefresh?.();
    } catch (error) {
      setMailState(error.message);
    } finally {
      setBusy(false);
    }
  }

  const profile = dashboard?.profile;
  return (
    <div className="fixed inset-0 z-40">
      <button className="absolute inset-0 bg-slate-950/30" onClick={onClose} aria-label="Закрыть меню" />
      <aside className="absolute left-0 top-0 flex h-full w-[min(360px,92vw)] flex-col gap-4 bg-white p-4 shadow-soft">
        <div className="rounded-lg bg-slate-100 p-4">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-lg bg-teal-700 text-white">
              <UserRound size={20} />
            </div>
            <div>
              <p className="text-sm text-slate-500">Профиль</p>
              <h2 className="font-semibold">{profile?.name || dashboard?.email}</h2>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
            <div className="rounded-lg bg-white p-3">
              <p className="text-slate-500">Доход</p>
              <p className="font-semibold">{formatMoney(dashboard?.monthly_income || 0)}</p>
            </div>
            <div className="rounded-lg bg-white p-3">
              <p className="text-slate-500">Резерв</p>
              <p className="font-semibold">{formatMoney(dashboard?.reserved_cushion || 0)}</p>
            </div>
          </div>
        </div>

        <button className="btn-secondary justify-start" onClick={() => onNavigate("profile")}>
          <PenLine size={18} /> Анкета
        </button>
        <button className="btn-secondary justify-start" onClick={() => onNavigate("coach", `Объясни прогресс по цели: ${dashboard?.goal?.title}`)}>
          <Target size={18} /> Финансовая цель
        </button>
        <button className="btn-secondary justify-start" onClick={() => onNavigate("cushion")}>
          <PiggyBank size={18} /> Финансовая подушка
        </button>
        <button className="btn-secondary justify-start" onClick={onLogout}>
          <LogOut size={18} /> Выйти
        </button>
        <button className="btn-secondary justify-start" disabled={busy} onClick={() => setMailPanelOpen((value) => !value)}>
          <Mail size={18} /> Интеграция с почтой
        </button>
        {mailPanelOpen && (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="mb-3 text-sm">
              <p className="font-semibold">Mail.ru через IMAP</p>
              <p className="mt-1 text-slate-600">
                Введите почту и пароль для внешнего приложения. Обычный пароль от почты лучше не использовать.
              </p>
              {mailStatus?.connected && (
                <p className="mt-2 rounded-lg bg-teal-50 p-2 text-teal-900">Подключено: {mailStatus.mailbox_email}</p>
              )}
            </div>
            <form className="grid gap-2" onSubmit={connectMail}>
              <input
                className="input"
                type="email"
                placeholder="user@mail.ru"
                value={mailboxEmail}
                onChange={(event) => setMailboxEmail(event.target.value)}
                required
              />
              <input
                className="input"
                type="password"
                placeholder="пароль внешнего приложения"
                value={appPassword}
                onChange={(event) => setAppPassword(event.target.value)}
                required
              />
              <button className="btn-primary" disabled={busy}>
                Подключить
              </button>
            </form>
            <div className="mt-2 grid grid-cols-2 gap-2">
              <button className="btn-secondary px-2" disabled={busy || !mailStatus?.connected} onClick={() => syncMail(false)}>
                Синхронизировать
              </button>
              <button className="btn-secondary px-2" disabled={busy} onClick={() => syncMail(true)}>
                Демо-чек
              </button>
            </div>
          </div>
        )}
        {mailState && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{mailState}</p>}
      </aside>
    </div>
  );
}
