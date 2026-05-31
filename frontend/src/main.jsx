import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}

if ("serviceWorker" in navigator && import.meta.env.DEV) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.getRegistrations?.()
      .then((registrations) => registrations.forEach((registration) => registration.unregister()))
      .catch(() => {});
    window.caches?.keys()
      .then((keys) => keys.filter((key) => key.startsWith("financepay")).forEach((key) => window.caches.delete(key)))
      .catch(() => {});
  });
}

createRoot(document.getElementById("root")).render(<App />);
