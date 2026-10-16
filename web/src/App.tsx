import { useEffect, useState } from "react";
import { api } from "./lib/feed";
import { defaultProfile, type Profile } from "./lib/types";
import { Broadcast } from "./pages/Broadcast";
import { Compare } from "./pages/Compare";
import { ControlRoom } from "./pages/ControlRoom";
import { Lab } from "./pages/Lab";
import { OverlayOnly } from "./pages/OverlayOnly";
import { Recap } from "./pages/Recap";

const ROUTES = [
  { path: "/", label: "Broadcast" },
  { path: "/compare", label: "Two fans" },
  { path: "/ops", label: "Control room" },
  { path: "/recap", label: "Recap" },
  { path: "/lab", label: "Data lab" },
];

function useHashRoute() {
  const read = () => {
    const h = location.hash.replace(/^#/, "") || "/";
    const [path, qs] = h.split("?");
    return { path, query: new URLSearchParams(qs ?? "") };
  };
  const [r, setR] = useState(read);
  useEffect(() => {
    const on = () => setR(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}

function loadProfile(): Profile {
  try {
    const raw = localStorage.getItem("regista.profile");
    if (raw) return { ...defaultProfile(), ...JSON.parse(raw) };
  } catch { /* storage unavailable */ }
  return defaultProfile({ mode: "casual", language: "en" });
}

export function App() {
  const { path, query } = useHashRoute();
  const [profile, setProfileState] = useState<Profile>(loadProfile);
  const [health, setHealth] = useState<any>(null);
  const setProfile = (p: Profile) => {
    setProfileState(p);
    try { localStorage.setItem("regista.profile", JSON.stringify(p)); } catch { /* ignore */ }
  };
  useEffect(() => {
    const load = () => api("/api/health").then(setHealth).catch(() => setHealth(null));
    load();
    const id = window.setInterval(load, 5000);
    return () => window.clearInterval(id);
  }, []);
  if (path === "/overlay") return <OverlayOnly query={query} />;
  const breaker = health?.breaker?.state;
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="#/" aria-label="Regista home">
          <img className="mark" src="/favicon.svg" alt="" width={40} height={40} />
          <span className="word"><b className="title-px">Regi<span className="y">sta</span></b><small>Match director</small></span>
        </a>
        <nav className="nav">
          {ROUTES.map((r) => <a key={r.path} href={`#${r.path}`} className={path === r.path ? "active" : ""}>{r.label}</a>)}
        </nav>
        <div className="right">
          <span className={`pill ${!health ? "bad" : breaker === "open" ? "bad" : breaker === "half_open" ? "warn" : ""}`}>
            <span className="dot" />{health ? `${health.llm.offline ? "Offline agents" : health.llm.model.replace(/^foundry:/, "Foundry · ")}` : "API offline"}
          </span>
          {health && <span className="pill">{health.bus} · {health.viewers} viewer{health.viewers === 1 ? "" : "s"}</span>}
          <a className="pill" href="#/overlay?mode=casual&lang=en" target="_blank" rel="noreferrer">Overlay for OBS ↗</a>
        </div>
      </header>
      <main>
        {path === "/" && <Broadcast profile={profile} setProfile={setProfile} />}
        {path === "/compare" && <Compare />}
        {path === "/ops" && <ControlRoom />}
        {path === "/recap" && <Recap lang={profile.language} />}
        {path === "/lab" && <Lab />}
      </main>
    </div>
  );
}
