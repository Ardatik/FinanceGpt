import { formatMoney } from "../lib/api";

export default function StatChart({ days = [], hasTransactions }) {
  const maxValue = Math.max(...days.map((day) => Number(day.amount || 0)), 1);
  return (
    <div className="h-48">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Расходы за последние 7 дней</h3>
        {!hasTransactions && <span className="text-xs text-slate-500">данных пока нет</span>}
      </div>
      <div className="flex h-36 items-end gap-2 rounded-lg bg-slate-50 px-3 py-2">
        {days.map((day) => {
          const height = hasTransactions ? Math.max(8, (Number(day.amount || 0) / maxValue) * 112) : 4;
          return (
            <div key={day.date} className="flex flex-1 flex-col items-center justify-end gap-2">
              <div
                className="w-4 rounded-t bg-teal-600 transition-all"
                style={{ height: `${height}px`, opacity: Number(day.amount) > 0 ? 1 : 0.25 }}
                title={`${day.label}: ${formatMoney(day.amount)}`}
              />
              <span className="text-xs text-slate-500">{day.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
