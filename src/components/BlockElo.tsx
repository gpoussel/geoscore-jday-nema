import { useState } from "react";
import type { Game } from "../types";

const EloChart = ({ games }: { games: Game[] }) => {
  const [hover, setHover] = useState<number | null>(null);
  const W = 720;
  const H = 260;
  const PAD = 32;
  if (!games.length) return null;

  const elos = games.map((g) => g.elo);
  const minE = Math.min(...elos) - 15;
  const maxE = Math.max(...elos) + 15;
  const highIdx = elos.indexOf(Math.max(...elos));
  const lowIdx = elos.indexOf(Math.min(...elos));

  const x = (i: number) =>
    PAD + (i / Math.max(1, games.length - 1)) * (W - PAD * 2);
  const y = (e: number) =>
    H - PAD - ((e - minE) / (maxE - minE)) * (H - PAD * 2);

  const path = games
    .map((g, i) => (i === 0 ? "M" : "L") + x(i) + "," + y(g.elo))
    .join(" ");
  const area = `${path} L ${x(games.length - 1)},${H - PAD} L ${x(0)},${H - PAD} Z`;

  const gridY: { y: number; v: number }[] = [];
  const steps = 4;
  for (let i = 0; i <= steps; i++) {
    const v = minE + (maxE - minE) * (i / steps);
    gridY.push({ y: y(v), v: Math.round(v) });
  }

  return (
    <div className="elo-chart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" onMouseLeave={() => setHover(null)}>
        <defs>
          <linearGradient id="eloArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {gridY.map((g, i) => (
          <g key={i}>
            <line x1={PAD} y1={g.y} x2={W - PAD} y2={g.y} stroke="rgba(255,255,255,0.05)" />
            <text x={8} y={g.y + 3} fill="rgba(255,255,255,0.35)" fontSize="10" fontFamily="var(--mono)">
              {g.v}
            </text>
          </g>
        ))}
        <path d={area} fill="url(#eloArea)" />
        <path d={path} stroke="rgba(255,255,255,0.4)" strokeWidth="1.5" fill="none" />
        {games.map((g, i) => (
          <g key={i} onMouseEnter={() => setHover(i)}>
            <circle
              cx={x(i)}
              cy={y(g.elo)}
              r={hover === i ? 6 : 3.5}
              fill={g.won ? "var(--win)" : "var(--loss)"}
              stroke={i === highIdx || i === lowIdx ? "white" : "transparent"}
              strokeWidth="2"
            />
            {(i === highIdx || i === lowIdx) && (
              <text
                x={x(i)}
                y={y(g.elo) + (i === highIdx ? -14 : 20)}
                textAnchor="middle"
                fontSize="10"
                fontFamily="var(--mono)"
                fill="white"
                fontWeight="600"
              >
                {i === highIdx ? "HIGH " : "LOW "}
                {g.elo}
              </text>
            )}
            <rect x={x(i) - 10} y={0} width={20} height={H} fill="transparent" />
          </g>
        ))}
        {hover !== null && (
          <line
            x1={x(hover)}
            y1={PAD}
            x2={x(hover)}
            y2={H - PAD}
            stroke="rgba(255,255,255,0.2)"
            strokeDasharray="2 3"
          />
        )}
      </svg>
      {hover !== null && (
        <div
          className="elo-tooltip"
          style={{ left: `${(x(hover) / W) * 100}%` }}
        >
          <div className="tt-row">
            <span>Partie #{hover + 1}</span>
          </div>
          <div
            className="tt-big"
            style={{ color: games[hover].won ? "var(--win)" : "var(--loss)" }}
          >
            {games[hover].won ? "Victoire" : "Défaite"} ·{" "}
            {games[hover].eloDelta > 0 ? "+" : ""}
            {games[hover].eloDelta}
          </div>
          <div className="tt-row">
            <span>ELO</span>
            <b>{games[hover].elo}</b>
          </div>
          <div className="tt-row">
            <span>Rounds</span>
            <b>{games[hover].rounds}</b>
          </div>
          <div className="tt-row">
            <span>Précision</span>
            <b>{games[hover].myAcc}%</b>
          </div>
        </div>
      )}
    </div>
  );
};

const Donut = ({ wins, losses, games }: { wins: number; losses: number; games: Game[] }) => {
  const total = wins + losses;
  const winPct = total ? (wins / total) * 100 : 0;
  const R = 70;
  const C = 2 * Math.PI * R;
  const shortGames = games.filter((g) => g.rounds <= 7);
  const longGames = games.filter((g) => g.rounds > 7);
  const shortWR = shortGames.length
    ? Math.round((shortGames.filter((g) => g.won).length / shortGames.length) * 100)
    : 0;
  const longWR = longGames.length
    ? Math.round((longGames.filter((g) => g.won).length / longGames.length) * 100)
    : 0;

  return (
    <div className="donut-block">
      <div className="donut-wrap">
        <svg viewBox="0 0 200 200" width="180" height="180">
          <circle cx="100" cy="100" r={R} fill="none" stroke="var(--loss)" strokeWidth="22" />
          <circle
            cx="100"
            cy="100"
            r={R}
            fill="none"
            stroke="var(--win)"
            strokeWidth="22"
            strokeDasharray={`${(winPct / 100) * C} ${C}`}
            transform="rotate(-90 100 100)"
            strokeLinecap="butt"
          />
          <text x="100" y="96" textAnchor="middle" fontFamily="var(--serif)" fontSize="36" fill="white" fontStyle="italic">
            {Math.round(winPct)}
            <tspan fontSize="20">%</tspan>
          </text>
          <text x="100" y="115" textAnchor="middle" fontFamily="var(--sans)" fontSize="10" fill="rgba(255,255,255,0.5)" letterSpacing="2">
            WIN-RATE
          </text>
        </svg>
      </div>
      <div className="donut-legend">
        <div className="dl-row">
          <span className="dot win" /> Victoires <b>{wins}</b>
        </div>
        <div className="dl-row">
          <span className="dot loss" /> Défaites <b>{losses}</b>
        </div>
        <div className="dl-split">
          <div>
            <div className="dl-lbl">Parties courtes</div>
            <div className="dl-val">
              <b>{shortWR}%</b> <span>({shortGames.length})</span>
            </div>
          </div>
          <div>
            <div className="dl-lbl">Parties longues</div>
            <div className="dl-val">
              <b>{longWR}%</b> <span>({longGames.length})</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const MarginBars = ({ games }: { games: Game[] }) => {
  const categories = [
    { key: "crush-w", label: "V. écrasantes", count: games.filter((g) => g.won && g.margin === "crush").length, tone: "win", weight: "strong" },
    { key: "clean-w", label: "V. propres",    count: games.filter((g) => g.won && g.margin === "clean").length, tone: "win", weight: "med" },
    { key: "tight-w", label: "V. serrées",    count: games.filter((g) => g.won && g.margin === "tight").length, tone: "win", weight: "light" },
    { key: "tight-l", label: "D. serrées",    count: games.filter((g) => !g.won && g.margin === "tight").length, tone: "loss", weight: "light" },
    { key: "clean-l", label: "D. propres",    count: games.filter((g) => !g.won && g.margin === "clean").length, tone: "loss", weight: "med" },
    { key: "crush-l", label: "D. larges",     count: games.filter((g) => !g.won && g.margin === "crush").length, tone: "loss", weight: "strong" },
  ];
  const max = Math.max(1, ...categories.map((c) => c.count));

  return (
    <div className="margin-bars">
      {categories.map((c) => (
        <div key={c.key} className="mb-row">
          <div className="mb-label">{c.label}</div>
          <div className="mb-track">
            <div
              className={`mb-fill mb-${c.tone} mb-w-${c.weight}`}
              style={{ width: `${(c.count / max) * 100}%` }}
            >
              <span className="mb-count">{c.count}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default function BlockElo({ games }: { games: Game[] }) {
  const wins = games.filter((g) => g.won).length;
  const losses = games.length - wins;
  return (
    <section className="block" id="block-elo">
      <div className="block-head">
        <h2 className="block-title">
          ELO <em>&amp; résultats</em>
        </h2>
      </div>
      <div className="block-grid-elo">
        <div className="card card-elo">
          <div className="card-head">
            <span className="card-eyebrow">Évolution</span>
            <span className="card-meta">{games.length} parties</span>
          </div>
          <EloChart games={games} />
        </div>
        <div className="card card-donut">
          <div className="card-head">
            <span className="card-eyebrow">Bilan</span>
          </div>
          <Donut wins={wins} losses={losses} games={games} />
        </div>
        <div className="card card-margin">
          <div className="card-head">
            <span className="card-eyebrow">Marges</span>
          </div>
          <MarginBars games={games} />
        </div>
      </div>
    </section>
  );
}
