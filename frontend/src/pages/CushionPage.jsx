import { ArrowLeft, KeyRound, RotateCcw, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { apiRequest, formatMoney } from "../lib/api";

export default function CushionPage({ token, onBack }) {
  const [state, setState] = useState(null);
  const [codeWord, setCodeWord] = useState("");
  const [newCodeWord, setNewCodeWord] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");
  const [demoCode, setDemoCode] = useState("");
  const [cushionToken, setCushionToken] = useState("");
  const [reserved, setReserved] = useState(0);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const data = await apiRequest("/cushion", { token });
    setState(data);
    setReserved(Number(data.reserved_amount || 0));
  }

  useEffect(() => {
    load().catch((err) => setMessage(err.message));
  }, [token]);

  async function setup(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const data = await apiRequest("/cushion/setup", { method: "POST", token, body: { code_word: codeWord } });
      setState(data);
      setMessage("Кодовое слово сохранено. Теперь резерв можно открыть только после подтверждения.");
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function unlock(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const data = await apiRequest("/cushion/unlock", { method: "POST", token, body: { code_word: codeWord } });
      setCushionToken(data.cushion_token);
      setMessage(`Доступ открыт на ${data.expires_in_minutes} минут.`);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveReserve() {
    setBusy(true);
    try {
      const data = await apiRequest("/cushion/reserve", {
        method: "PUT",
        token,
        headers: { "X-Cushion-Token": cushionToken },
        body: { reserved_amount: Number(reserved) }
      });
      setState(data);
      setMessage("Резерв обновлен. Эта сумма больше не участвует в доступном бюджете месяца.");
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function requestRecoveryWithEmail(email) {
    setBusy(true);
    try {
      const data = await apiRequest("/cushion/recovery/request", { method: "POST", token, body: { email } });
      setDemoCode(data.demo_code || "");
      setMessage(data.message);
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function verifyRecovery(event) {
    event.preventDefault();
    setBusy(true);
    try {
      const data = await apiRequest("/cushion/recovery/verify", {
        method: "POST",
        token,
        body: { code: recoveryCode, new_code_word: newCodeWord }
      });
      setState(data);
      setMessage("Кодовое слово обновлено.");
    } catch (err) {
      setMessage(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (!state) {
    return <main className="grid min-h-screen place-items-center text-slate-600">Загружаем подушку...</main>;
  }

  return (
    <main className="min-h-screen px-4 py-5">
      <div className="mx-auto max-w-4xl">
        <button className="btn-secondary mb-5" onClick={onBack}><ArrowLeft size={18} /> Назад</button>
        <section className="card p-5">
          <div className="flex items-start gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-lg bg-teal-700 text-white">
              <ShieldCheck />
            </div>
            <div>
              <p className="text-sm font-semibold text-teal-700">Финансовая подушка</p>
              <h1 className="text-2xl font-semibold">Добровольный резерв средств</h1>
              <p className="mt-2 text-sm text-slate-600">
                Это не блокировка денег. Резерв создает дополнительный шаг подтверждения, чтобы решение о снятии было осознанным.
              </p>
            </div>
          </div>

          {!state.is_configured ? (
            <form className="mt-6 grid max-w-md gap-3" onSubmit={setup}>
              <label className="text-sm">
                <span className="mb-1 block text-slate-600">Придумайте кодовое слово</span>
                <input className="input" value={codeWord} onChange={(e) => setCodeWord(e.target.value)} minLength={4} required />
              </label>
              <button className="btn-primary" disabled={busy}><KeyRound size={18} /> Сохранить кодовое слово</button>
            </form>
          ) : !cushionToken ? (
            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              <form className="grid gap-3" onSubmit={unlock}>
                <label className="text-sm">
                  <span className="mb-1 block text-slate-600">Кодовое слово</span>
                  <input className="input" value={codeWord} onChange={(e) => setCodeWord(e.target.value)} required />
                </label>
                <button className="btn-primary" disabled={busy}><KeyRound size={18} /> Открыть подушку</button>
              </form>
              <RecoveryForm
                busy={busy}
                demoCode={demoCode}
                recoveryCode={recoveryCode}
                newCodeWord={newCodeWord}
                onEmail={requestRecoveryWithEmail}
                onSubmit={verifyRecovery}
                onRecoveryCode={setRecoveryCode}
                onNewCodeWord={setNewCodeWord}
              />
            </div>
          ) : (
            <div className="mt-6">
              <div className="grid gap-3 sm:grid-cols-3">
                <Info title="Доход из анкеты" value={formatMoney(state.monthly_income)} />
                <Info title="Текущий резерв" value={formatMoney(state.reserved_amount)} />
                <Info title="Доступно после резерва" value={formatMoney(Math.max(0, Number(state.monthly_income) - Number(reserved)))} />
              </div>
              <div className="mt-6 rounded-lg bg-slate-50 p-4">
                <label className="text-sm font-semibold">Какую сумму вы хотите зарезервировать?</label>
                <input
                  className="mt-4 w-full accent-teal-700"
                  type="range"
                  min="0"
                  max={Number(state.monthly_income || 0)}
                  step="100"
                  value={reserved}
                  onChange={(e) => setReserved(e.target.value)}
                />
                <div className="mt-2 flex justify-between text-sm text-slate-500">
                  <span>0 ₽</span>
                  <b className="text-slate-950">{formatMoney(reserved)}</b>
                  <span>{formatMoney(state.monthly_income)}</span>
                </div>
                <button className="btn-primary mt-4" disabled={busy} onClick={saveReserve}>Зафиксировать резерв</button>
              </div>
            </div>
          )}

          {message && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{message}</p>}
        </section>
      </div>
    </main>
  );
}

function RecoveryForm({ busy, demoCode, recoveryCode, newCodeWord, onEmail, onSubmit, onRecoveryCode, onNewCodeWord }) {
  const [email, setEmail] = useState("");
  return (
    <form className="grid gap-3 rounded-lg border border-slate-200 p-4" onSubmit={onSubmit}>
      <div className="flex items-center gap-2 text-sm font-semibold"><RotateCcw size={16} /> Забыли кодовое слово?</div>
      <input className="input" type="email" placeholder="почта аккаунта" value={email} onChange={(e) => setEmail(e.target.value)} />
      <button type="button" className="btn-secondary" disabled={busy || !email} onClick={() => onEmail(email)}>Восстановить</button>
      {demoCode && <p className="rounded-lg bg-slate-100 p-2 text-sm">Демо-код: <b>{demoCode}</b></p>}
      <input className="input" placeholder="код из письма" value={recoveryCode} onChange={(e) => onRecoveryCode(e.target.value)} />
      <input className="input" placeholder="новое кодовое слово" value={newCodeWord} onChange={(e) => onNewCodeWord(e.target.value)} />
      <button className="btn-primary" disabled={busy}>Сохранить новое слово</button>
    </form>
  );
}

function Info({ title, value }) {
  return (
    <div className="rounded-lg bg-slate-50 p-4">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 font-semibold">{value}</p>
    </div>
  );
}
