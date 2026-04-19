import type { Game } from "../types";

const PrecisionChart = ({ games }: { games: Game[] }) => {
  const W = 720;
  const H = 220;
  const PAD = 32;
  if (!games.length) return null;

  const x = (i: number) =>
    PAD + (i / Math.max(1, games.length - 1)) * (W - PAD * 2);
  const y = (v: number) => H - PAD - ((v - 50) / 50) * (H - PAD * 2);

  const meLine = games
    .map((g, i) => (i === 0 ? "M" : "L") + x(i) + "," + y(g.myAcc))
    .join(" ");
  const advLine = games
    .map((g, i) => (i === 0 ? "M" : "L") + x(i) + "," + y(g.advAcc))
    .join(" ");
  const avgMe = games.reduce((s, g) => s + g.myAcc, 0) / games.length;
  const avgAdv = games.reduce((s, g) => s + g.advAcc, 0) / games.length;

  return (
    <div className="prec-chart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%">
        {[50, 60, 70, 80, 90, 100].map((v) => (
          <g key={v}>
            <line x1={PAD} y1={y(v)} x2={W - PAD} y2={y(v)} stroke="rgba(255,255,255,0.04)" />
            <text x={8} y={y(v) + 3} fontSize="9" fill="rgba(255,255,255,0.3)" fontFamily="var(--mono)">
              {v}%
            </text>
          </g>
        ))}
        <path
          d={advLine}
          stroke="var(--loss)"
          strokeWidth="2"
          fill="none"
          strokeOpacity="0.75"
          strokeDasharray="4 3"
        />
        <path d={meLine} stroke="var(--win)" strokeWidth="2.5" fill="none" />
        {games.map((g, i) => (
          <circle key={i} cx={x(i)} cy={y(g.myAcc)} r="2.5" fill="var(--win)" />
        ))}
      </svg>
      <div className="prec-legend">
        <span>
          <i className="sw sw-win" /> Duo · moy. {avgMe.toFixed(1)}%
        </span>
        <span>
          <i className="sw sw-loss" /> Adversaires · moy. {avgAdv.toFixed(1)}%
        </span>
      </div>
    </div>
  );
};

const RoundHistogram = ({ games }: { games: Game[] }) => {
  const buckets = [0, 0, 0, 0, 0];
  games.forEach((g) =>
    g.roundBuckets.forEach((v, i) => {
      buckets[i] += v;
    }),
  );
  const total = buckets.reduce((a, b) => a + b, 0);
  const labels = ["0–1k", "1–2k", "2–3k", "3–4k", "4–5k"];
  const max = Math.max(1, ...buckets);

  return (
    <div className="histo">
      <div className="histo-bars">
        {buckets.map((v, i) => {
          const pct = (v / max) * 100;
          const tone = i < 2 ? "loss" : i < 3 ? "neutral" : "win";
          return (
            <div key={i} className="histo-col">
              <div className="histo-val">{v}</div>
              <div className="histo-bar-wrap">
                <div className={`histo-bar histo-${tone}`} style={{ height: `${pct}%` }} />
              </div>
              <div className="histo-label">{labels[i]}</div>
              <div className="histo-pct">{total ? Math.round((v / total) * 100) : 0}%</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const PerfectsCounter = ({ games }: { games: Game[] }) => {
  const perfects = games.reduce((s, g) => s + g.perfects, 0);
  const totalRounds = games.reduce((s, g) => s + g.rounds, 0);
  const rate = totalRounds ? (perfects / totalRounds) * 100 : 0;

  return (
    <div className="perfects">
      <div className="perfects-lbl">Rounds parfaits</div>
      <div className="perfects-value">
        <span className="pv-num">{perfects}</span>
        <span className="pv-star">★</span>
      </div>
      <div className="perfects-sub">
        <b>5000 pts</b> · {rate.toFixed(1)}% des rounds
      </div>
      <div className="perfects-dots">
        {Array.from({ length: Math.min(perfects, 24) }).map((_, i) => (
          <span key={i} className="pdot" />
        ))}
        {perfects > 24 && <span className="pdot-more">+{perfects - 24}</span>}
      </div>
    </div>
  );
};

export default function BlockPrecision({ games }: { games: Game[] }) {
  return (
    <section className="block" id="block-precision">
      <div className="block-head">
        <h2 className="block-title">
          Précision <em>&amp; tir</em>
        </h2>
      </div>
      <div className="block-grid-prec">
        <div className="card card-prec">
          <div className="card-head">
            <span className="card-eyebrow">Duo vs Adversaires</span>
            <span className="card-meta">Précision par partie</span>
          </div>
          <PrecisionChart games={games} />
        </div>
        <div className="card card-histo">
          <div className="card-head">
            <span className="card-eyebrow">Distribution</span>
            <span className="card-meta">Score par round</span>
          </div>
          <RoundHistogram games={games} />
        </div>
        <div className="card card-perfect">
          <PerfectsCounter games={games} />
        </div>
      </div>
    </section>
  );
}
