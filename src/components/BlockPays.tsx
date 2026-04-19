import { useState } from "react";
import type { CountryStat } from "../types";
import { WORLD } from "../data/world";

type Props = { countryStats: Record<string, CountryStat> };

const WorldMap = ({ countryStats }: Props) => {
  const [hover, setHover] = useState<string | null>(null);

  const colorFor = (code: string) => {
    const s = countryStats[code];
    if (!s || s.seen < 2) return "var(--map-unseen)";
    const t = Math.max(0, Math.min(1, (s.acc - 55) / 40));
    if (t < 0.5) {
      const k = t * 2;
      return `color-mix(in oklch, var(--loss) ${(1 - k) * 100}%, var(--map-mid) ${k * 100}%)`;
    }
    const k = (t - 0.5) * 2;
    return `color-mix(in oklch, var(--map-mid) ${(1 - k) * 100}%, var(--win) ${k * 100}%)`;
  };

  return (
    <div className="worldmap-wrap">
      <svg
        viewBox="0 0 1000 500"
        width="100%"
        className="worldmap"
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <pattern id="wmgrid" width="20" height="20" patternUnits="userSpaceOnUse">
            <path d="M 20 0 L 0 0 0 20" fill="none" stroke="rgba(255,255,255,0.025)" strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect x="150" y="90" width="720" height="310" fill="url(#wmgrid)" rx="4" />

        {WORLD.map((country) => {
          const s = countryStats[country.c];
          const seen = s?.seen ?? 0;
          const isHovered = hover === country.c;
          return (
            <rect
              key={country.c}
              x={country.x}
              y={country.y}
              width={country.w}
              height={country.h}
              rx="1.5"
              fill={colorFor(country.c)}
              stroke={isHovered ? "white" : "rgba(255,255,255,0.1)"}
              strokeWidth={isHovered ? 1.5 : 0.5}
              onMouseEnter={() => setHover(country.c)}
              style={{ cursor: seen >= 2 ? "pointer" : "default", transition: "stroke 0.15s" }}
            />
          );
        })}
      </svg>

      <div className="wm-legend">
        <span className="wml-label">Précision moyenne</span>
        <div className="wml-scale">
          <span style={{ background: "var(--loss)" }} />
          <span style={{ background: "color-mix(in oklch, var(--loss) 50%, var(--map-mid))" }} />
          <span style={{ background: "var(--map-mid)" }} />
          <span style={{ background: "color-mix(in oklch, var(--map-mid) 50%, var(--win))" }} />
          <span style={{ background: "var(--win)" }} />
        </div>
        <div className="wml-ticks">
          <span>55%</span>
          <span>75%</span>
          <span>95%</span>
        </div>
        <div className="wml-note">Pays vus &lt; 2× non colorés</div>
      </div>

      {hover && countryStats[hover] && (
        <div className="wm-tooltip">
          <div className="wmt-code">{hover}</div>
          <div className="wmt-name">{WORLD.find((c) => c.c === hover)?.n}</div>
          <div className="wmt-rows">
            <div>
              <span>Apparitions</span>
              <b>{countryStats[hover].seen}</b>
            </div>
            <div>
              <span>Duo</span>
              <b style={{ color: "var(--win)" }}>{countryStats[hover].acc.toFixed(1)}%</b>
            </div>
            <div>
              <span>Adv.</span>
              <b style={{ color: "var(--loss)" }}>{countryStats[hover].advAcc.toFixed(1)}%</b>
            </div>
            <div>
              <span>Écart</span>
              <b>
                {countryStats[hover].gap >= 0 ? "+" : ""}
                {countryStats[hover].gap.toFixed(1)}
              </b>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const TopFlopList = ({
  countryStats,
  mode,
}: {
  countryStats: Record<string, CountryStat>;
  mode: "top" | "flop";
}) => {
  const entries = Object.entries(countryStats).filter(([, s]) => s.seen >= 2);
  entries.sort((a, b) => (mode === "top" ? b[1].acc - a[1].acc : a[1].acc - b[1].acc));
  const top5 = entries.slice(0, 5);
  const title = mode === "top" ? "Top 5" : "Flop 5";

  return (
    <div className="topflop">
      <div className="tf-title">
        {title}
        <span className="tf-sub">{mode === "top" ? "meilleurs" : "pires"}</span>
      </div>
      <ol className="tf-list">
        {top5.map(([code, s], i) => {
          const country = WORLD.find((c) => c.c === code);
          return (
            <li key={code}>
              <span className="tf-rank">{i + 1}</span>
              <span className="tf-flag">{code}</span>
              <span className="tf-name">{country?.n || code}</span>
              <span className="tf-app">×{s.seen}</span>
              <span className={"tf-acc " + (mode === "top" ? "tf-win" : "tf-loss")}>
                {s.acc.toFixed(0)}%
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
};

const BeteNoire = ({ countryStats }: Props) => {
  const entries = Object.entries(countryStats).filter(([, s]) => s.seen >= 2);
  entries.sort((a, b) => a[1].gap - b[1].gap);
  const worst = entries[0];
  if (!worst) return null;
  const [code, s] = worst;
  const country = WORLD.find((c) => c.c === code);

  return (
    <div className="bete-noire">
      <div className="bn-eyebrow">Bête noire</div>
      <div className="bn-country">
        <div className="bn-code">{code}</div>
        <div className="bn-name">{country?.n}</div>
      </div>
      <div className="bn-gap">
        <div className="bn-gap-val">{s.gap.toFixed(1)}</div>
        <div className="bn-gap-lbl">
          écart moyen
          <br />
          vs adversaire
        </div>
      </div>
      <div className="bn-detail">
        <div>
          <span>Duo</span>
          <b>{s.acc.toFixed(1)}%</b>
        </div>
        <div>
          <span>Adversaire</span>
          <b>{s.advAcc.toFixed(1)}%</b>
        </div>
        <div>
          <span>Apparitions</span>
          <b>{s.seen}</b>
        </div>
      </div>
    </div>
  );
};

export default function BlockPays({ countryStats }: Props) {
  return (
    <section className="block" id="block-pays">
      <div className="block-head">
        <h2 className="block-title">
          Pays <em>&amp; terrain</em>
        </h2>
      </div>
      <div className="block-grid-pays">
        <div className="card card-map">
          <div className="card-head">
            <span className="card-eyebrow">Carte</span>
          </div>
          <WorldMap countryStats={countryStats} />
        </div>
        <div className="pays-side">
          <div className="card card-top">
            <TopFlopList countryStats={countryStats} mode="top" />
          </div>
          <div className="card card-flop">
            <TopFlopList countryStats={countryStats} mode="flop" />
          </div>
          <div className="card card-bn">
            <BeteNoire countryStats={countryStats} />
          </div>
        </div>
      </div>
    </section>
  );
}
