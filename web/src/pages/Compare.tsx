import { useState } from "react";
import { FanStudio } from "../components/FanStudio";
import { Stage } from "../components/Stage";
import { Transport } from "../components/Transport";
import { useFeed } from "../lib/feed";
import { defaultProfile, type Profile } from "../lib/types";

export function Compare() {
  const [a, setA] = useState<Profile>(defaultProfile({ id: "left", mode: "analyst", language: "en", focus_metric: "pressing" }));
  const [b, setB] = useState<Profile>(defaultProfile({ id: "right", mode: "casual", language: "ar", favorite_team: "CAL" }));
  const fa = useFeed(a);
  const fb = useFeed(b);
  return (
    <div className="page">
      <div className="page-head">
        <h2 className="title-px">One match. <span className="y">Two fans.</span></h2>
        <p>Same feed, same moments, same verified facts. The Director re-cuts the graphics, the language and the voice for each viewer.</p>
      </div>
      <div className="compare">
        {[{ p: a, set: setA, f: fa }, { p: b, set: setB, f: fb }].map(({ p, set, f }) => (
          <div key={p.id}>
            <div className="card" style={{ marginBottom: 10 }}>
              <div className="body"><FanStudio profile={p} setProfile={set} match={f.match} compact /></div>
            </div>
            <Stage feed={f} favorite={p.favorite_player} cam="broadcast" lens={false} receipts={p.mode === "analyst"}
              rtl={p.language === "ar"} label={`${p.mode.replace("_", " ")} · ${p.language.toUpperCase()}`} />
          </div>
        ))}
      </div>
      <Transport feed={fa} />
    </div>
  );
}
