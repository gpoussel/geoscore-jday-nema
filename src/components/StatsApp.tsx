import { useMemo, useState } from "react";
import type { CountryStat, Period, Stats } from "../types";
import Header from "./Header";
import BlockElo from "./BlockElo";
import BlockPrecision from "./BlockPrecision";
import BlockPays from "./BlockPays";
import BlockRecords from "./BlockRecords";
import BlockSessions from "./BlockSessions";

export default function StatsApp({ data }: { data: Stats }) {
  const [period, setPeriod] = useState<Period>("week1");

  const games = useMemo(
    () =>
      period === "week1"
        ? data.games.filter((g) => g.week === 1)
        : data.games,
    [data.games, period],
  );

  const sessions = useMemo(
    () =>
      period === "week1"
        ? data.sessions.filter((s) => s.week === 1)
        : data.sessions,
    [data.sessions, period],
  );

  const filteredRounds = useMemo(() => {
    const gids = new Set(games.map((g) => g.id));
    return data.rounds.filter((r) => gids.has(r.gameId));
  }, [data.rounds, games]);

  const countryStats = useMemo<Record<string, CountryStat>>(() => {
    const agg: Record<string, { seen: number; mySum: number; advSum: number }> = {};
    for (const r of filteredRounds) {
      const k = r.country;
      if (!agg[k]) agg[k] = { seen: 0, mySum: 0, advSum: 0 };
      agg[k].seen++;
      agg[k].mySum += (r.myScore / 5000) * 100;
      agg[k].advSum += (r.oppScore / 5000) * 100;
    }
    const out: Record<string, CountryStat> = {};
    for (const k in agg) {
      const a = agg[k];
      const acc = a.mySum / a.seen;
      const advAcc = a.advSum / a.seen;
      out[k] = { seen: a.seen, acc, advAcc, gap: acc - advAcc };
    }
    return out;
  }, [filteredRounds]);

  const headerStats = useMemo(() => {
    const wins = games.filter((g) => g.won).length;
    const eloNet = games.reduce((s, g) => s + g.eloDelta, 0);
    const avgAcc = games.length
      ? games.reduce((s, g) => s + g.myAcc, 0) / games.length
      : 0;
    const recordDamage = filteredRounds.reduce(
      (m, r) => (r.winner === "me" ? Math.max(m, r.damage) : m),
      0,
    );
    return {
      games: games.length,
      winRate: Math.round((wins / Math.max(1, games.length)) * 100),
      eloNet,
      avgAcc,
      recordDamage,
    };
  }, [games, filteredRounds]);

  return (
    <div className="app">
      <Header
        period={period}
        setPeriod={setPeriod}
        players={data.players}
        duoRank={data.duoRank}
        stats={headerStats}
      />
      <BlockElo games={games} />
      <BlockPrecision games={games} />
      <BlockPays countryStats={countryStats} />
      <BlockRecords games={games} rounds={filteredRounds} />
      <BlockSessions sessions={sessions} players={data.players} />

      <footer className="footer">
        <span>JDAY × NÉMA · DUO STATS</span>
        <span>
          {period === "week1" ? "SEMAINE 1" : "GLOBAL"} · {games.length} PARTIES
        </span>
        <span>MAJ {new Date(data.generatedAt).toLocaleDateString("fr-FR")}</span>
      </footer>
    </div>
  );
}
