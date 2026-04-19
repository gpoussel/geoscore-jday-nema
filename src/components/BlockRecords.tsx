import type { Game, Round } from "../types";

type Tone = "win" | "loss" | "neutral";

type TileProps = {
  label: string;
  value: string | number;
  unit?: string;
  meta: string;
  tone: Tone;
  icon: string;
  bigLabel?: string;
};

const RecordTile = ({ label, value, unit, meta, tone, icon, bigLabel }: TileProps) => (
  <div className={`record-tile record-${tone}`}>
    <div className="rt-icon">{icon}</div>
    <div className="rt-label">{label}</div>
    <div className="rt-big">
      <span className="rt-val">{value}</span>
      {unit && <span className="rt-unit">{unit}</span>}
    </div>
    {bigLabel && <div className="rt-biglabel">{bigLabel}</div>}
    <div className="rt-meta">{meta}</div>
  </div>
);

const fmtMult = (m: number) => (m === Math.floor(m) ? `${m}` : `${m}`);

export default function BlockRecords({
  games,
  rounds,
}: {
  games: Game[];
  rounds: Round[];
}) {
  const gameIds = new Set(games.map((g) => g.id));
  const gameRounds = rounds.filter((r) => gameIds.has(r.gameId));

  const bestHit = gameRounds
    .filter((r) => r.winner === "me")
    .reduce((best, r) => (r.damage > best.damage ? r : best), { damage: 0 } as Round);
  const worstHit = gameRounds
    .filter((r) => r.winner === "opp")
    .reduce((best, r) => (r.damage > best.damage ? r : best), { damage: 0 } as Round);

  let winStreak = 0;
  let lossStreak = 0;
  let curW = 0;
  let curL = 0;
  for (const g of games) {
    if (g.won) {
      curW++;
      curL = 0;
      winStreak = Math.max(winStreak, curW);
    } else {
      curL++;
      curW = 0;
      lossStreak = Math.max(lossStreak, curL);
    }
  }

  const longest = games.reduce(
    (a, b) => (b.rounds > a.rounds ? b : a),
    { rounds: 0, finalMyMult: 0, finalOppMult: 0 } as Game,
  );

  return (
    <section className="block" id="block-records">
      <div className="block-head">
        <h2 className="block-title">
          Records <em>&amp; faits d'armes</em>
        </h2>
      </div>
      <div className="records-grid">
        <RecordTile
          label="Coup parfait"
          value={bestHit.damage ? bestHit.damage.toLocaleString("fr-FR") : "—"}
          unit="HP"
          meta={`${bestHit.country || "—"} · mult. ×${bestHit.usedMult ? fmtMult(bestHit.usedMult) : "—"}`}
          tone="win"
          icon="⚡"
        />
        <RecordTile
          label="Mandale encaissée"
          value={worstHit.damage ? worstHit.damage.toLocaleString("fr-FR") : "—"}
          unit="HP"
          meta={`${worstHit.country || "—"} · adv. ×${worstHit.usedMult ? fmtMult(worstHit.usedMult) : "—"}`}
          tone="loss"
          icon="💥"
        />
        <RecordTile
          label="Série de victoires"
          value={winStreak}
          unit="W"
          meta="consécutives"
          tone="win"
          icon="▲"
        />
        <RecordTile
          label="Série de défaites"
          value={lossStreak}
          unit="L"
          meta="consécutives"
          tone="loss"
          icon="▼"
        />
        <RecordTile
          label="Plus longue partie"
          value={longest.rounds || "—"}
          unit="rounds"
          meta={`Duo ×${longest.finalMyMult ? fmtMult(longest.finalMyMult) : "—"} · Adv. ×${longest.finalOppMult ? fmtMult(longest.finalOppMult) : "—"}`}
          tone="neutral"
          icon="∞"
          bigLabel="ROUNDS"
        />
      </div>
    </section>
  );
}
