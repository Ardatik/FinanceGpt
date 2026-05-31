import { Save } from "lucide-react";
import { useEffect, useState } from "react";
import { apiRequest } from "../lib/api";

const initial = {
  name: "",
  gender: "",
  age: "",
  city: "",
  monthly_income: "",
  income_bucket: "",
  income_sources: [],
  family_status: "",
  debt_status: "",
  situation: "",
  financial_goal: "",
  custom_goal: "",
  goal_target_amount: "",
  goal_saved_amount: "",
  goal_due_date: "",
  fixed_expenses: {},
  essential_monthly_expenses: "",
  static_debt_payments: "",
  wants_challenges: true
};

const goals = ["закрыть долги", "начать копить", "сформировать подушку", "разобраться с тратами", "увеличить доход", "чувствовать спокойствие", "своя цель"];

export default function ProfileForm({ token, onDone, onCancel }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiRequest("/profile", { token })
      .then((profile) => {
        if (!profile) return;
        setForm({ ...initial, ...profile, goal_due_date: profile.goal_due_date || "" });
      })
      .catch(() => {});
  }, [token]);

  function update(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        ...form,
        age: form.age ? Number(form.age) : null,
        monthly_income: Number(form.monthly_income || 0),
        goal_target_amount: Number(form.goal_target_amount || 0),
        goal_saved_amount: Number(form.goal_saved_amount || 0),
        essential_monthly_expenses: Number(form.essential_monthly_expenses || 0),
        static_debt_payments: Number(form.static_debt_payments || 0),
        goal_due_date: form.goal_due_date || null,
        custom_goal: form.financial_goal === "своя цель" ? form.custom_goal : form.custom_goal || null
      };
      await apiRequest("/profile", { method: "PUT", token, body: payload });
      onDone();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen px-4 py-6">
      <form className="mx-auto max-w-4xl" onSubmit={submit}>
        <div className="mb-5 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-teal-700">Анкета первого входа</p>
            <h1 className="text-2xl font-semibold">Финансовая картина</h1>
          </div>
          {onCancel && <button type="button" className="btn-secondary" onClick={onCancel}>Назад</button>}
        </div>

        <div className="card grid gap-4 p-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Имя"><input className="input" placeholder="Ваше имя" value={form.name} onChange={(e) => update("name", e.target.value)} required /></Field>
            <Field label="Город"><input className="input" placeholder="Город" value={form.city || ""} onChange={(e) => update("city", e.target.value)} /></Field>
            <Field label="Возраст"><input className="input" type="number" min="14" max="100" placeholder="Возраст" value={form.age || ""} onChange={(e) => update("age", e.target.value)} /></Field>
            <Field label="Пол"><input className="input" placeholder="Можно не отвечать" value={form.gender || ""} onChange={(e) => update("gender", e.target.value)} /></Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Доход после налогов"><input className="input" type="number" min="0" placeholder="Доход в месяц" value={form.monthly_income} onChange={(e) => update("monthly_income", e.target.value)} /></Field>
            <Field label="Обязательные траты"><input className="input" type="number" min="0" placeholder="Расходы в месяц" value={form.essential_monthly_expenses} onChange={(e) => update("essential_monthly_expenses", e.target.value)} /></Field>
            <Field label="Платежи по долгам"><input className="input" type="number" min="0" placeholder="Платежи в месяц" value={form.static_debt_payments} onChange={(e) => update("static_debt_payments", e.target.value)} /></Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Финансовая ситуация">
              <select className={selectClass(form.situation)} value={form.situation || ""} onChange={(e) => update("situation", e.target.value)}>
                <option value="" disabled>Выберите вариант</option>
                <option>не хочу отвечать</option>
                <option>тяжело, едва хватает</option>
                <option>трудно, но справляюсь</option>
                <option>стабильно без накоплений</option>
                <option>комфортно с накоплениями</option>
                <option>уверен, инвестирую</option>
              </select>
            </Field>
            <Field label="Кредиты или долги">
              <select className={selectClass(form.debt_status)} value={form.debt_status || ""} onChange={(e) => update("debt_status", e.target.value)}>
                <option value="" disabled>Выберите вариант</option>
                <option>не хочу отвечать</option>
                <option>нет</option>
                <option>один кредит</option>
                <option>несколько кредитов</option>
                <option>долги людям</option>
              </select>
            </Field>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Главная цель">
              <select className={selectClass(form.financial_goal)} value={form.financial_goal} onChange={(e) => update("financial_goal", e.target.value)} required>
                <option value="" disabled>Выберите цель</option>
                {goals.map((goal) => <option key={goal}>{goal}</option>)}
              </select>
            </Field>
            <Field label="Своя финансовая цель">
              <input className="input" value={form.custom_goal || ""} onChange={(e) => update("custom_goal", e.target.value)} placeholder="например: накопить 80 000 на поездку" />
            </Field>
            <Field label="Сумма цели"><input className="input" type="number" min="0" placeholder="Сколько нужно" value={form.goal_target_amount} onChange={(e) => update("goal_target_amount", e.target.value)} /></Field>
            <Field label="Уже накоплено"><input className="input" type="number" min="0" placeholder="Сколько уже есть" value={form.goal_saved_amount} onChange={(e) => update("goal_saved_amount", e.target.value)} /></Field>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.wants_challenges} onChange={(e) => update("wants_challenges", e.target.checked)} />
            Хочу получать челленджи по экономии
          </label>

          {error && <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
          <button className="btn-primary w-fit" disabled={busy}>
            <Save size={18} /> Сохранить
          </button>
        </div>
      </form>
    </main>
  );
}

function Field({ label, children }) {
  return (
    <label className="text-sm">
      <span className="mb-1 block text-slate-600">{label}</span>
      {children}
    </label>
  );
}

function selectClass(value) {
  return value ? "input" : "input text-slate-400";
}
