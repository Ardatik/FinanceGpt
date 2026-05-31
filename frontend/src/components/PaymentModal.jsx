import { Camera, Check, QrCode, RotateCcw, ScanLine, X } from "lucide-react";
import jsQR from "jsqr";
import { useEffect, useRef, useState } from "react";
import { apiRequest, formatMoney } from "../lib/api";

const banks = [
  ["sber", "Сбер"],
  ["vtb", "ВТБ"],
  ["alfa", "Альфа"],
  ["tbank", "Т-Банк"]
];

function parseQrAmount(payload) {
  const keys = ["amount", "sum", "Sum", "AM", "am", "summ", "total"];
  try {
    const url = new URL(payload);
    for (const key of keys) {
      const raw = url.searchParams.get(key);
      const amount = normalizeQrAmount(raw, key);
      if (amount) return amount;
    }
  } catch {
    const compactMatch = payload.match(/(?:sum|amount|am|total)=?([0-9]+(?:[.,][0-9]{1,2})?)/i);
    if (compactMatch) return normalizeQrAmount(compactMatch[1], "sum");
  }
  return null;
}

function normalizeQrAmount(raw, key) {
  if (!raw) return null;
  const normalized = raw.replace(",", ".").replace(/[^\d.]/g, "");
  const value = Number(normalized);
  if (!Number.isFinite(value) || value <= 0) return null;
  const isKopeckField = key.toLowerCase() === "sum" || key.toLowerCase() === "am";
  const hasDecimal = normalized.includes(".");
  return isKopeckField && !hasDecimal ? Math.round(value / 100) : value;
}

export default function PaymentModal({ open, onClose, token, onDone, autoScan = false }) {
  const [bank, setBank] = useState("sber");
  const [amount, setAmount] = useState("");
  const [payment, setPayment] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scanStatus, setScanStatus] = useState("");
  const [qrPayload, setQrPayload] = useState("");
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  useEffect(() => {
    if (!open) {
      setScannerOpen(false);
      stopCamera();
      return;
    }
    setPayment(null);
    setMessage("");
    setScanStatus("");
    setQrPayload("");
    setAmount("");
    if (autoScan) {
      setScannerOpen(true);
    }
  }, [open, autoScan]);

  useEffect(() => {
    if (!open || !scannerOpen) {
      stopCamera();
      return undefined;
    }

    let stopped = false;

    async function runScanner() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setScanStatus("Браузер не дал доступ к камере. Для камеры нужен телефонный браузер с HTTPS-туннелем.");
        return;
      }
      try {
        setScanStatus("Открываем камеру...");
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            facingMode: { ideal: "environment" },
            width: { ideal: 1280 },
            height: { ideal: 720 }
          }
        });
        if (stopped) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        const video = videoRef.current;
        video.srcObject = stream;
        await video.play();
        setScanStatus("Наведите камеру на QR-код СБП.");

        let detector = null;
        if ("BarcodeDetector" in window) {
          try {
            detector = new window.BarcodeDetector({ formats: ["qr_code"] });
          } catch {
            detector = null;
          }
        }

        async function tick() {
          if (stopped || !scannerOpen) return;
          const payload = await detectQr(video, detector, canvasRef.current);
          if (payload) {
            handleQrPayload(payload);
            return;
          }
          window.setTimeout(tick, 250);
        }

        tick();
      } catch (error) {
        setScanStatus("Камера недоступна. Проверьте разрешение браузера или откройте приложение по HTTPS-туннелю.");
      }
    }

    runScanner();
    return () => {
      stopped = true;
      stopCamera();
    };
  }, [open, scannerOpen]);

  async function detectQr(video, detector, canvas) {
    if (!video || video.readyState < 2) return null;
    if (detector) {
      try {
        const codes = await detector.detect(video);
        return codes?.[0]?.rawValue || null;
      } catch {
        return null;
      }
    }
    if (!canvas || !video.videoWidth || !video.videoHeight) return null;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, imageData.width, imageData.height, { inversionAttempts: "attemptBoth" });
    return code?.data || null;
  }

  function handleQrPayload(payload) {
    setQrPayload(payload);
    const parsedAmount = parseQrAmount(payload);
    if (parsedAmount) {
      setAmount(String(parsedAmount));
      setMessage(`QR-код считан. Сумма заполнена: ${formatMoney(parsedAmount)}.`);
    } else {
      setMessage("QR-код считан. Сумму и состав покупки пришлет payment_service.");
    }
    setScannerOpen(false);
  }

  function useDemoQr() {
    handleQrPayload("https://qr.nspk.ru/demo?merchant=YandexMarket&sum=129000");
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function openBank(paymentData) {
    if (!paymentData?.deeplink) return;
    window.location.assign(paymentData.deeplink);
  }

  if (!open) return null;

  async function approvePayment() {
    if (!qrPayload) {
      setMessage("Сначала отсканируйте QR-код СБП.");
      setScannerOpen(true);
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const confirmed = await apiRequest("/payments/sbp/request", {
        method: "POST",
        token,
        body: { bank, qr_payload: qrPayload, amount_hint: amount ? Number(amount) : null }
      });
      setPayment(confirmed);
      setMessage("Оплата одобрена. Backend получил mock-чек от payment_service и записал расходы. Открываем банк...");
      onDone?.();
      openBank(confirmed);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/40 p-4">
      <div className="card w-full max-w-lg p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <QrCode className="text-teal-700" />
            <h2 className="text-lg font-semibold">QR-code СБП</h2>
          </div>
          <button className="btn-ghost p-2" onClick={onClose} aria-label="Закрыть">
            <X size={18} />
          </button>
        </div>
        <p className="mt-2 text-sm text-slate-600">
          Отсканируйте QR-код СБП, затем одобрите оплату. Mock-чек придет из payment_service и сразу попадет в расходы.
        </p>
        <div className="mt-4 grid gap-3">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <ScanLine size={16} /> Сканирование QR
              </div>
              <button
                className={scannerOpen ? "btn-secondary px-3 py-1.5" : "btn-primary px-3 py-1.5"}
                type="button"
                onClick={() => {
                  setMessage("");
                  setScannerOpen((value) => !value);
                }}
              >
                <Camera size={16} /> {scannerOpen ? "Остановить" : "Сканировать"}
              </button>
            </div>
            {scannerOpen && (
              <div className="mt-3 overflow-hidden rounded-lg bg-slate-950">
                <video ref={videoRef} className="aspect-video w-full object-cover" muted playsInline />
                <canvas ref={canvasRef} className="hidden" />
              </div>
            )}
            {scanStatus && scannerOpen && <p className="mt-2 text-sm text-slate-600">{scanStatus}</p>}
            {!qrPayload && (
              <button type="button" className="btn-ghost mt-2 px-3 py-1.5 text-xs" onClick={useDemoQr}>
                Демо QR
              </button>
            )}
            {qrPayload && !scannerOpen && (
              <p className="mt-2 break-all rounded-lg bg-white p-2 text-xs text-slate-500">
                QR: {qrPayload.slice(0, 180)}{qrPayload.length > 180 ? "..." : ""}
              </p>
            )}
          </div>
          {amount && (
            <div className="rounded-lg bg-teal-50 p-3 text-sm text-teal-900">
              Сумма из QR: <b>{formatMoney(amount)}</b>
            </div>
          )}
          <div className="grid grid-cols-4 gap-2">
            {banks.map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={id === bank ? "btn-primary px-2" : "btn-secondary px-2"}
                onClick={() => setBank(id)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        {payment && (
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
            <p>Платеж: {payment.status}</p>
            <p>Магазин: {payment.merchant}</p>
            <p>Сумма: {formatMoney(payment.amount)}</p>
            {payment.external_payload?.items?.length > 0 && (
              <div className="mt-2 grid gap-1 text-xs text-slate-600">
                {payment.external_payload.items.map((item) => (
                  <p key={`${item.title}-${item.amount}`}>
                    {item.title} x {item.quantity}: {formatMoney(item.amount)}
                  </p>
                ))}
              </div>
            )}
            {payment.deeplink && (
              <button type="button" className="btn-secondary mt-3 px-3 py-1.5" onClick={() => openBank(payment)}>
                Открыть банк
              </button>
            )}
          </div>
        )}
        {message && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">{message}</p>}
        <div className="mt-5 flex flex-wrap gap-2">
          <button className="btn-primary" disabled={busy || !qrPayload} onClick={approvePayment}>
            <Check size={18} /> Одобрить оплату
          </button>
          <button className="btn-secondary" disabled={busy} onClick={() => setScannerOpen(true)}>
            <RotateCcw size={18} /> Сканировать заново
          </button>
        </div>
      </div>
    </div>
  );
}
