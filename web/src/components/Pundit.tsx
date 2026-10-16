import { useState } from "react";
import type { Feed } from "../lib/feed";
import type { Lang } from "../lib/types";

const SUGGEST: Record<Lang, string[]> = {
  en: ["Why are Northbridge winning the ball so high?", "Who is the best player so far?", "What are the chances of each side winning?", "Who is the fastest?"],
  es: ["¿Por qué presiona tanto el Northbridge?", "¿Quién es el mejor jugador?", "¿Qué probabilidad de victoria tiene cada equipo?"],
  fr: ["Pourquoi Northbridge presse-t-il si haut ?", "Qui est le meilleur joueur ?", "Qui contrôle le match ?"],
  ar: ["لماذا يضغط Northbridge عاليا؟", "من هو أفضل لاعب حتى الآن؟", "ما هي احتمالات الفوز؟"],
  pt: ["Por que o Northbridge pressiona tão alto?", "Quem é o melhor jogador?", "Qual a probabilidade de vitória?"],
};

interface Msg { me: boolean; text: string; tools?: string[]; model?: string; ms?: number }

export function Pundit({ feed, lang }: { feed: Feed; lang: Lang }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const rtl = lang === "ar";
  const ask = async (question: string) => {
    if (!question.trim() || busy) return;
    setMsgs((m) => [...m, { me: true, text: question }]);
    setQ("");
    setBusy(true);
    const res = await feed.ask(question);
    setBusy(false);
    setMsgs((m) => [...m, { me: false, text: res.answer, tools: res.tools, model: res.model, ms: res.ms }]);
  };
  return (
    <div className="stack">
      <div className="chat" aria-live="polite">
        {msgs.length === 0 && <div className="muted" style={{ fontSize: 13 }}>Ask the match anything, in your language. Answers come from the same tools exposed over MCP.</div>}
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.me ? "me" : ""} ${rtl ? "rtl" : ""}`}>
            {m.text}
            {!m.me && m.tools && (
              <div className="tools">
                {m.tools.map((t) => <span key={t}>{t}()</span>)}
                <span>{m.model}</span>
                {m.ms !== undefined && <span>{m.ms} ms</span>}
              </div>
            )}
          </div>
        ))}
        {busy && <div className="bubble muted">Checking the data…</div>}
      </div>
      <div className="chips">
        {SUGGEST[lang].map((s) => <button key={s} className={rtl ? "rtl" : ""} onClick={() => ask(s)}>{s}</button>)}
      </div>
      <form className="row" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask the Pundit…" dir={rtl ? "rtl" : "ltr"} style={{ flex: 1 }} aria-label="Question" />
        <button className="btn primary" type="submit" disabled={busy}>Ask</button>
      </form>
    </div>
  );
}
