import { ArrowLeft, Bot, Brain, CircleDollarSign, Layers3, ReceiptText, Store, WalletCards } from "lucide-react";
import { useEffect, useState } from "react";
import { apiRequest, formatMoney } from "../lib/api";

const kindLabels = {
  essential: "обязательные",
  optimizable: "оптимизируемые",
  unknown: "без типа"
};

export default function FinancialPortraitPage({ token, onBack, onNavigate }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apiRequest("/dashboard/portrait", { token })
      .then((payload) => {
        setData(payload);
        setError("");
      })
      .catch((err) => setError(err.message));
  }, [token]);

  if (!data && !error) {
    return <main className="grid min-h-screen place-items-center text-slate-600">Собираем финансовый портрет...</main>;
  }

  if (error) {
    return (
      <main className="min-h-screen px-4 py-5">
        <div className="mx-auto max-w-6xl">
          <button className="btn-secondary mb-5" onClick={onBack}><ArrowLeft size={18} /> Назад</button>
          <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>
        </div>
      </main>
    );
  }

  const metrics = data.metrics;
  const maxCategory = Math.max(...data.categories.map((category) => Number(category.amount || 0)), 1);

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-5">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <button className="btn-secondary mb-4" onClick={onBack}><ArrowLeft size={18} /> Назад</button>
            <div className="flex items-center gap-2 text-sm font-semibold text-teal-700">
              <Brain size={18} /> финансовая нагрузка
            </div>
            <h1 className="mt-2 text-3xl font-semibold">Финансовый портрет</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">{data.summary}</p>
          </div>
          <button
            className="btn-primary w-fit"
            onClick={() => onNavigate("coach", "Посмотри мой финансовый портрет и помоги понять, на какую категорию расходов стоит обратить внимание первой.")}
          >
            <Bot size={18} /> Обсудить с коучем
          </button>
        </header>

        <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Metric icon={WalletCards} label="Доход" value={formatMoney(metrics.monthly_income)} />
          <Metric icon={CircleDollarSign} label="Траты месяца" value={formatMoney(metrics.monthly_spent)} />
          <Metric icon={Layers3} label="Обязательная нагрузка" value={formatMoney(metrics.mandatory_expenses)} />
          <Metric icon={ReceiptText} label="Оптимизируемые траты" value={formatMoney(metrics.optimized_expenses)} />
        </section>

        <section className="mt-5 grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="card p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-semibold">Категории товаров</h2>
                <p className="mt-1 text-sm text-slate-600">Где сейчас концентрируются расходы по чекам и ручным транзакциям.</p>
              </div>
              <span className="rounded-lg bg-teal-50 px-3 py-1 text-sm font-semibold text-teal-800">{metrics.diagnosis_status}</span>
            </div>
            <div className="mt-5 grid gap-3">
              {data.categories.length === 0 ? (
                <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">Категории появятся после первых транзакций или СБП-чека.</p>
              ) : (
                data.categories.map((category) => (
                  <div key={category.name} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="font-semibold">{category.name}</p>
                        <p className="text-xs text-slate-500">{kindLabels[category.kind] || category.kind} · {category.count} покупок</p>
                      </div>
                      <div className="text-right">
                        <p className="font-semibold">{formatMoney(category.amount)}</p>
                        <p className="text-xs text-slate-500">{category.share_percent}% расходов</p>
                      </div>
                    </div>
                    <div className="mt-3 h-2 rounded-full bg-white">
                      <div className="h-2 rounded-full bg-teal-600" style={{ width: `${Math.max(4, (Number(category.amount || 0) / maxCategory) * 100)}%` }} />
                    </div>
                    {category.items.length > 0 && (
                      <div className="mt-3 grid gap-1 text-sm text-slate-600">
                        {category.items.map((item) => (
                          <div key={item.title} className="flex justify-between gap-3">
                            <span>{item.title}</span>
                            <span className="font-medium text-slate-800">{formatMoney(item.amount)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="grid gap-5">
            <div className="card p-5">
              <h2 className="text-xl font-semibold">Наблюдения портрета</h2>
              <PortraitList title="Сигналы расходов" items={data.spending_signals} />
              <PortraitList title="Гипотезы" items={data.psychological_hypotheses} />
              <PortraitList title="Фокусы для экспериментов" items={data.suggested_focuses} />
            </div>

            <div className="card p-5">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <Store size={16} /> Магазины
              </div>
              <div className="mt-3 grid gap-2">
                {data.merchants.length === 0 ? (
                  <p className="text-sm text-slate-500">Пока нет данных.</p>
                ) : (
                  data.merchants.map((merchant) => (
                    <div key={merchant.name} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                      <span>{merchant.name}</span>
                      <span className="font-semibold">{formatMoney(merchant.amount)}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="card mt-5 p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">История транзакций</h2>
              <p className="mt-1 text-sm text-slate-600">СБП-чек раскрывается по товарам, каждый товар хранится отдельной транзакцией.</p>
            </div>
          </div>
          <div className="mt-4 overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="py-2 pr-3 font-semibold">Дата</th>
                  <th className="py-2 pr-3 font-semibold">Товар</th>
                  <th className="py-2 pr-3 font-semibold">Магазин</th>
                  <th className="py-2 pr-3 font-semibold">Категория</th>
                  <th className="py-2 pr-3 text-right font-semibold">Сумма</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.transactions.map((transaction) => (
                  <tr key={transaction.id}>
                    <td className="py-3 pr-3 text-slate-500">{formatDate(transaction.purchased_at)}</td>
                    <td className="py-3 pr-3">
                      <p className="font-medium text-slate-900">{transaction.title}</p>
                      {transaction.description && <p className="mt-1 text-xs text-slate-500">{transaction.description}</p>}
                    </td>
                    <td className="py-3 pr-3 text-slate-600">{transaction.merchant}</td>
                    <td className="py-3 pr-3 text-slate-600">{transaction.category || "Без категории"}</td>
                    <td className="py-3 pr-3 text-right font-semibold">{formatMoney(transaction.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data.transactions.length === 0 && <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-600">История появится после первой покупки.</p>}
          </div>
        </section>
      </div>
    </main>
  );
}

function Metric({ icon: Icon, label, value }) {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Icon size={16} /> {label}
      </div>
      <p className="mt-2 text-2xl font-semibold">{value || "0 ₽"}</p>
    </div>
  );
}

function PortraitList({ title, items }) {
  if (!items?.length) return null;
  return (
    <div className="mt-4">
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      <div className="mt-2 grid gap-2">
        {items.map((item) => (
          <p key={item} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">{item}</p>
        ))}
      </div>
    </div>
  );
}

function formatDate(value) {
  return new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}
