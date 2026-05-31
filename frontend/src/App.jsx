import { useEffect, useState } from "react";
import { apiRequest, clearAuthSession, getAccessToken, getStoredUser, saveAuthSession } from "./lib/api";
import CoachPage from "./pages/CoachPage";
import CushionPage from "./pages/CushionPage";
import Dashboard from "./pages/Dashboard";
import FinancialPortraitPage from "./pages/FinancialPortraitPage";
import Landing from "./pages/Landing";
import ProfileForm from "./pages/ProfileForm";

export default function App() {
  const [token, setToken] = useState(() => getAccessToken());
  const [user, setUser] = useState(() => getStoredUser());
  const [page, setPage] = useState("dashboard");
  const [coachPrompt, setCoachPrompt] = useState("");
  const [checking, setChecking] = useState(Boolean(token));

  useEffect(() => {
    function handleAuthUpdate(event) {
      const nextToken = getAccessToken();
      setToken(nextToken);
      if (event.detail?.user) {
        setUser(event.detail.user);
      }
      if (!nextToken) {
        setUser(null);
        setPage("dashboard");
      }
    }
    window.addEventListener("financepay:auth-updated", handleAuthUpdate);
    return () => window.removeEventListener("financepay:auth-updated", handleAuthUpdate);
  }, []);

  useEffect(() => {
    if (!token) {
      setChecking(false);
      return;
    }
    apiRequest("/auth/me", { token })
      .then((data) => {
        setUser(data);
        localStorage.setItem("financepay_user", JSON.stringify(data));
      })
      .catch(() => logout())
      .finally(() => setChecking(false));
  }, [token]);

  function login(response) {
    saveAuthSession(response);
    setToken(response.access_token);
    setUser(response.user);
    setPage(response.user.onboarding_completed ? "dashboard" : "profile");
  }

  function logout() {
    clearAuthSession();
    setToken("");
    setUser(null);
    setPage("dashboard");
  }

  async function refreshUser(nextPage = "dashboard") {
    const data = await apiRequest("/auth/me", { token });
    setUser(data);
    localStorage.setItem("financepay_user", JSON.stringify(data));
    setPage(nextPage);
  }

  function navigate(nextPage, prompt = "") {
    setCoachPrompt(prompt);
    setPage(nextPage);
  }

  if (checking) {
    return <main className="grid min-h-screen place-items-center text-slate-600">Проверяем сессию...</main>;
  }

  if (!token || !user) {
    return <Landing onLogin={login} />;
  }

  if (!user.onboarding_completed || page === "profile") {
    return <ProfileForm token={token} onDone={() => refreshUser("dashboard")} onCancel={user.onboarding_completed ? () => setPage("dashboard") : null} />;
  }

  if (page === "coach") {
    return <CoachPage token={token} initialPrompt={coachPrompt} onBack={() => setPage("dashboard")} />;
  }

  if (page === "cushion") {
    return <CushionPage token={token} onBack={() => setPage("dashboard")} />;
  }

  if (page === "portrait") {
    return <FinancialPortraitPage token={token} onBack={() => setPage("dashboard")} onNavigate={navigate} />;
  }

  return <Dashboard token={token} onNavigate={navigate} onLogout={logout} />;
}
