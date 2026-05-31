import { ArrowRight, BarChart3, Bot, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { apiRequest } from "../lib/api";

export default function Landing({ onLogin }) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState("email");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function requestCode(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiRequest("/auth/request-code", { method: "POST", body: { email } });
      setCode("");
      setStep("code");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function verifyCode(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await apiRequest("/auth/verify", { method: "POST", body: { email, code } });
      onLogin(response);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="mx-auto grid min-h-screen max-w-6xl items-center gap-8 px-4 py-8 lg:grid-cols-[1.2fr_0.8fr]">
        <div>
          <div className="inline-flex items-center gap-2 rounded-lg bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-800">
            <Sparkles size={16} /> FinancePay
          </div>
          <h1 className="mt-5 max-w-3xl text-4xl font-semibold tracking-normal text-slate-950 sm:text-5xl">
            Личный контроль денег без бухгалтерского интерфейса
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-600">
            Сервис помогает видеть траты, держать недельный лимит, формировать резерв и обсуждать финансовые решения с ИИ-коучем.
          </p>
          <div className="mt-8 grid gap-3 sm:grid-cols-3">
            {[
              [BarChart3, "Понятная аналитика", "Неделя расходов, остаток лимита и цель на одном экране."],
              [Bot, "ИИ-коуч", "Бережно объясняет расчеты и помогает выбрать небольшой шаг."],
              [ShieldCheck, "Финансовая подушка", "Добровольный резерв с кодовым словом и паузой перед снятием."]
            ].map(([Icon, title, text]) => (
              <div key={title} className="card p-4">
                <Icon className="text-teal-700" />
                <h2 className="mt-3 font-semibold">{title}</h2>
                <p className="mt-1 text-sm text-slate-600">{text}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950">
            Механика простая: пользователь проходит анкету, сервис считает доступный бюджет, платежи автоматически попадают в расходы, а коуч предлагает диагностику и челленджи.
          </div>
        </div>

        <div className="card p-5">
          <h2 className="text-xl font-semibold">Вход по почте</h2>
          <p className="mt-1 text-sm text-slate-600">Пароль не нужен. Мы отправим одноразовый код.</p>
          {step === "email" ? (
            <form className="mt-5 grid gap-3" onSubmit={requestCode}>
              <input className="input" type="email" placeholder="mail@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required />
              <button className="btn-primary" disabled={busy}>
                Получить код <ArrowRight size={18} />
              </button>
            </form>
          ) : (
            <form className="mt-5 grid gap-3" onSubmit={verifyCode}>
              <input className="input" inputMode="numeric" placeholder="Код из письма" value={code} onChange={(event) => setCode(event.target.value)} required />
              <button className="btn-primary" disabled={busy}>
                Войти <ArrowRight size={18} />
              </button>
              <button type="button" className="btn-ghost" onClick={() => setStep("email")}>Изменить почту</button>
            </form>
          )}
          {error && <p className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
        </div>
      </section>
    </main>
  );
}
