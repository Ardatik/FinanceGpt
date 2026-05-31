import { Bot, Calculator, CheckCircle2, Menu, PiggyBank, QrCode, ReceiptText, Sparkles, Target } from "lucide-react";
import { useEffect, useState } from "react";
import PaymentModal from "../components/PaymentModal";
import SideMenu from "../components/SideMenu";
import StatChart from "../components/StatChart";
import { apiRequest, formatMoney, isMobileDevice } from "../lib/api";

export default function Dashboard({ token, onNavigate, onLogout }) {
  const [dashboard, setDashboard] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [mobileUi, setMobileUi] = useState(() => isMobileDevice());
  const [challengeProposal, setChallengeProposal] = useState(null);
  const [challengeBusy, setChallengeBusy] = useState(false);
  const [challengeError, setChallengeError] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      const data = await apiRequest("/dashboard", { token });
      setDashboard(data);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, [token]);

  useEffect(() => {
    function detectDevice() {
      setMobileUi(isMobileDevice());
    }
    detectDevice();
    window.addEventListener("resize", detectDevice);
    return () => window.removeEventListener("resize", detectDevice);
  }, []);

  async function loadChallengeOptions() {
    setChallengeBusy(true);
    setChallengeError("");
    try {
      const data = await apiRequest("/challenges/options", { method: "POST", token });
      setChallengeProposal(data);
    } catch (err) {
      setChallengeError(err.message);
    } finally {
      setChallengeBusy(false);
    }
  }

  async function selectChallenge(optionId) {
    if (!challengeProposal) return;
    setChallengeBusy(true);
    setChallengeError("");
    try {
      await apiRequest("/challenges/select", {
        method: "POST",
        token,
        body: { proposal_id: challengeProposal.proposal_id, option_id: optionId }
      });
      setChallengeProposal(null);
      await load();
    } catch (err) {
      setChallengeError(err.message);
    } finally {
      setChallengeBusy(false);
    }
  }

  if (!dashboard) {
    return <main className="grid min-h-screen place-items-center text-slate-600">Загружаем финансовую картину...</main>;
  }

  const stats = dashboard.stats;
  const challenge = dashboard.challenge;

  return (
    <main className="min-h-screen px-4 py-5">
      <div className="mx-auto max-w-6xl">
        <header className="flex items-start justify-between gap-3">
          <button className="btn-secondary" onClick={() => setMenuOpen(true)}>
            <Menu size={18} /> {dashboard.email}
          </button>
          <div className="card w-full max-w-md p-4">
            <div className="flex items-center gap-2 text-sm font-semibold text-teal-700">
              <Target size={16} /> цель — {dashboard.goal.title}
            </div>
            <div className="mt-3">
              <div className="mb-1 flex justify-between text-xs text-slate-500">
                <span>прогресс</span>
                <span>{dashboard.goal.progress_percent}%</span>
              </div>
              <div className="h-2 rounded-full bg-slate-100">
                <div className="h-2 rounded-full bg-teal-600" style={{ width: `${dashboard.goal.progress_percent}%` }} />
              </div>
            </div>
            <button
              className="mt-3 text-sm font-semibold text-teal-700"
              onClick={() => onNavigate("coach", `Покажи, как считается прогресс по моей цели "${dashboard.goal.title}". ${dashboard.goal.explanation}`)}
            >
              посмотреть, как он считается
            </button>
          </div>
        </header>

        {error && <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}

        <section className="card mt-5 p-4">
          <div className="grid gap-4 lg:grid-cols-[1.35fr_0.85fr]">
            <StatChart days={stats.days} hasTransactions={stats.has_transactions} />
            <button
              className="rounded-lg border border-teal-100 bg-teal-50 p-4 text-left transition hover:border-teal-300"
              onClick={() => onNavigate("portrait")}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-teal-800">Финансовая нагрузка</span>
                <span className="rounded-lg bg-white px-2 py-1 text-xs text-slate-600">{dashboard.diagnosis.status}</span>
              </div>
              <p className="mt-3 text-sm text-slate-700">{dashboard.diagnosis.summary}</p>
              <div className="mt-4 h-2 rounded-full bg-white">
                <div className="h-2 rounded-full bg-amber-500" style={{ width: `${dashboard.diagnosis.score}%` }} />
              </div>
            </button>
          </div>
          <div className="mt-4 grid gap-3 border-t border-slate-100 pt-4 sm:grid-cols-2">
            <InfoLine title="Потрачено вчера" value={stats.spent_yesterday === null ? "" : formatMoney(stats.spent_yesterday)} />
            <InfoLine title="Осталось до конца недельного лимита" value={stats.weekly_limit_remaining === null ? "" : formatMoney(stats.weekly_limit_remaining)} />
          </div>
        </section>

        <section className="mt-5 grid gap-4 md:grid-cols-3">
          <div className="card p-4">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Calculator size={16} /> Лимит
            </div>
            <p className="mt-2 text-2xl font-semibold">{formatMoney(dashboard.limit.weekly_limit)}</p>
            <p className="text-sm text-slate-500">на неделю</p>
            <button
              className="mt-3 text-sm font-semibold text-teal-700"
              onClick={() => onNavigate("coach", `Объясни, как считается мой недельный лимит. ${dashboard.limit.explanation}`)}
            >
              посмотреть, как это считается
            </button>
          </div>

          <button className="card p-4 text-left transition hover:border-teal-300" onClick={() => onNavigate("coach")}>
            <Bot className="text-teal-700" />
            <p className="mt-5 text-xl font-semibold">AI-коуч</p>
            <p className="mt-1 text-sm text-slate-600">Чат с историей и расчетами за месяц.</p>
          </button>

          {mobileUi ? (
            <button className="card p-4 text-left transition hover:border-teal-300" onClick={() => setPaymentOpen(true)}>
              <QrCode className="text-teal-700" />
              <p className="mt-5 text-xl font-semibold">QR-code СБП</p>
              <p className="mt-1 text-sm text-slate-600">Камера откроется сразу, дальше останется одобрить оплату.</p>
            </button>
          ) : (
            <button className="card p-4 text-left transition hover:border-teal-300" onClick={() => setMenuOpen(true)}>
              <ReceiptText className="text-teal-700" />
              <p className="mt-5 text-xl font-semibold">Чеки из почты</p>
              <p className="mt-1 text-sm text-slate-600">На компьютере удобнее подключить почту и подтянуть расходы из писем.</p>
            </button>
          )}
        </section>

        <section className="card mt-5 overflow-hidden">
          {challenge.id ? (
            <div className="grid lg:grid-cols-[2fr_1fr]">
              <div className="p-5">
                <div className="flex items-center gap-2 text-sm font-semibold text-teal-700">
                  <PiggyBank size={16} /> челлендж
                </div>
                <h2 className="mt-2 text-2xl font-semibold">{challenge.title}</h2>
                {challenge.description && <p className="mt-2 text-sm text-slate-600">{challenge.description}</p>}
                <div className="mt-5">
                  <div className="mb-2 flex justify-between text-xs text-slate-500">
                    <span>{challenge.completed_steps} из {challenge.total_steps}</span>
                    <span>{challenge.progress_percent}%</span>
                  </div>
                  <div className="relative h-3 rounded-full bg-slate-100">
                    <div className="h-3 rounded-full bg-teal-600" style={{ width: `${challenge.progress_percent}%` }} />
                  </div>
                  <div className="mt-3 grid gap-2" style={{ gridTemplateColumns: `repeat(${challenge.total_steps}, minmax(0, 1fr))` }}>
                    {challenge.markers.map((marker, index) => (
                      <div key={`${marker.label}-${index}`} className="flex flex-col items-center gap-1">
                        <span className={marker.completed ? "h-3 w-3 rounded-full bg-teal-600" : "h-3 w-3 rounded-full bg-slate-300"} />
                        <span className="text-xs text-slate-500">{marker.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <div className="grid border-t border-slate-100 lg:border-l lg:border-t-0">
                <div className="border-b border-slate-100 p-4">
                  <p className="text-sm text-slate-500">продолжительность</p>
                  <p className="mt-1 text-xl font-semibold">{challenge.duration_days} дней</p>
                </div>
                <div className="bg-amber-50 p-4">
                  <p className="text-sm text-amber-900">расчетная экономия эксперимента</p>
                  <p className="mt-1 text-2xl font-semibold text-amber-950">{formatMoney(challenge.expected_saving)}</p>
                  <p className="mt-5 text-sm font-semibold text-amber-900">Гипотеза</p>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-teal-700">
                <PiggyBank size={16} /> челлендж
              </div>
              <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <h2 className="text-2xl font-semibold">Челлендж не выбран</h2>
                  <p className="mt-2 max-w-2xl text-sm text-slate-600">
                    Коуч предложит несколько коротких экспериментов по твоей анкете, расходам и товарам из чеков.
                  </p>
                </div>
                <button className="btn-primary w-fit" disabled={challengeBusy} onClick={loadChallengeOptions}>
                  <Sparkles size={18} /> Выбрать челлендж
                </button>
              </div>
              {challengeError && <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{challengeError}</p>}
              {challengeProposal?.options?.length > 0 && (
                <div className="mt-5 grid gap-3 lg:grid-cols-3">
                  {challengeProposal.options.map((option) => (
                    <div key={option.id} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                      <h3 className="font-semibold">{option.title}</h3>
                      <p className="mt-2 text-sm text-slate-600">{option.description}</p>
                      <p className="mt-3 text-xs text-slate-500">{option.rationale}</p>
                      <div className="mt-4 flex items-center justify-between text-sm">
                        <span>{option.duration_days} дней</span>
                        <span>{formatMoney(option.expected_saving)}</span>
                      </div>
                      <button className="btn-secondary mt-4 w-full" disabled={challengeBusy} onClick={() => selectChallenge(option.id)}>
                        <CheckCircle2 size={18} /> Выбрать
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      <SideMenu
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        token={token}
        dashboard={dashboard}
        onRefresh={load}
        onLogout={onLogout}
        onNavigate={(page, prompt) => {
          setMenuOpen(false);
          onNavigate(page, prompt);
        }}
      />
      <PaymentModal open={paymentOpen} onClose={() => setPaymentOpen(false)} token={token} onDone={load} autoScan={mobileUi} />
    </main>
  );
}

function InfoLine({ title, value }) {
  return (
    <div className="rounded-lg bg-slate-50 p-4">
      <p className="text-sm text-slate-500">{title}</p>
      <p className="mt-1 text-xl font-semibold">{value || "—"}</p>
    </div>
  );
}
