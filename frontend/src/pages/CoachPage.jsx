import { ArrowLeft, Bot, Send, WalletCards } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { apiRequest, formatMoney, WS_BASE } from "../lib/api";

export default function CoachPage({ token, initialPrompt, onBack }) {
  const [messages, setMessages] = useState([]);
  const [context, setContext] = useState(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState("");
  const wsRef = useRef(null);

  useEffect(() => {
    apiRequest("/coach/history", { token }).then(setMessages).catch((err) => setError(err.message));
    apiRequest("/coach/context", { token }).then(setContext).catch(() => {});
  }, [token]);

  useEffect(() => {
    setInput(initialPrompt || "");
  }, [initialPrompt]);

  useEffect(() => {
    const socket = new WebSocket(`${WS_BASE}/coach/ws?token=${encodeURIComponent(token)}`);
    wsRef.current = socket;
    socket.onopen = () => {
      setError("");
    };
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "error") {
        setError(payload.message);
      }
      if (payload.type === "user_saved") {
        setMessages((current) => [...current, payload.message]);
      }
      if (payload.type === "token") {
        setStreaming(true);
        setMessages((current) => {
          const last = current[current.length - 1];
          if (last?.id === "stream") {
            return [...current.slice(0, -1), { ...last, content: last.content + payload.token }];
          }
          return [...current, { id: "stream", role: "assistant", content: payload.token, created_at: new Date().toISOString(), meta: {} }];
        });
      }
      if (payload.type === "done") {
        setStreaming(false);
        setMessages((current) => [...current.filter((message) => message.id !== "stream"), payload.message]);
      }
    };
    socket.onerror = () => {
      if (socket.readyState !== WebSocket.OPEN) {
        setError("Не удалось подключиться к чату");
      }
    };
    return () => socket.close();
  }, [token]);

  function send(text = input) {
    const clean = text.trim();
    if (!clean || wsRef.current?.readyState !== WebSocket.OPEN) return false;
    wsRef.current.send(JSON.stringify({ message: clean }));
    setInput("");
    return true;
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <div className="grid min-h-screen lg:grid-cols-[300px_1fr]">
        <aside className="border-r border-slate-200 bg-white p-4">
          <button className="btn-secondary mb-5" onClick={onBack}><ArrowLeft size={18} /> Назад</button>
          <div className="rounded-lg bg-teal-50 p-4">
            <div className="flex items-center gap-2 font-semibold text-teal-900">
              <WalletCards size={18} /> Этот месяц
            </div>
            <div className="mt-4 grid gap-3 text-sm">
              <Metric label="Доход" value={formatMoney(context?.monthly_income || 0)} />
              <Metric label="Траты" value={formatMoney(context?.monthly_spent || 0)} />
              <Metric label="Подушка" value={formatMoney(context?.reserved_cushion || 0)} />
              <Metric label="Свободно после резерва" value={formatMoney(context?.free_after_reserve || 0)} />
              <Metric label="Обязательные" value={formatMoney(context?.mandatory_expenses || 0)} />
              <Metric label="Оптимизируемые" value={formatMoney(context?.optimized_expenses || 0)} />
            </div>
          </div>
        </aside>

        <section className="flex min-h-screen flex-col">
          <header className="border-b border-slate-200 bg-white px-4 py-3">
            <div className="mx-auto flex max-w-3xl items-center gap-2">
              <Bot className="text-teal-700" />
              <div>
                <h1 className="font-semibold">AI-коуч</h1>
                <p className="text-xs text-slate-500">История сохраняется в PostgreSQL, ответы приходят потоково.</p>
              </div>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-4 py-5">
            <div className="mx-auto grid max-w-3xl gap-4">
              {messages.map((message) => (
                <Message key={message.id} message={message} />
              ))}
              {streaming && <p className="text-sm text-slate-500">Коуч печатает...</p>}
              {error && <p className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{error}</p>}
            </div>
          </div>

          <footer className="border-t border-slate-200 bg-white p-4">
            <div className="mx-auto flex max-w-3xl gap-2">
              <textarea
                className="input min-h-12 resize-none"
                placeholder="Напишите вопрос о цели, лимите, трате или челлендже"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    send();
                  }
                }}
              />
              <button className="btn-primary self-end px-3" onClick={() => send()} aria-label="Отправить">
                <Send size={18} />
              </button>
            </div>
          </footer>
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-lg bg-white px-3 py-2">
      <span className="text-slate-500">{label}</span>
      <b>{value}</b>
    </div>
  );
}

function Message({ message }) {
  const isUser = message.role === "user";
  return (
    <div className={isUser ? "flex justify-end" : "flex justify-start"}>
      <div className={isUser ? "max-w-[82%] rounded-lg bg-teal-700 px-4 py-3 text-sm text-white" : "max-w-[82%] rounded-lg bg-white px-4 py-3 text-sm text-slate-800 shadow-sm"}>
        <p className="whitespace-pre-wrap leading-6">{message.content}</p>
      </div>
    </div>
  );
}
