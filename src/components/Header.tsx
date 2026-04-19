import type { Player, Period } from "../types";

const RANK_ICONS: Record<string, string> = {
  "Master 1": "/ranks/master1.webp",
};

type HeaderStats = {
  games: number;
  winRate: number;
  eloNet: number;
  avgAcc: number;
  recordDamage: number;
};

type Props = {
  period: Period;
  setPeriod: (p: Period) => void;
  players: Record<string, Player>;
  duoRank: string;
  stats: HeaderStats;
};

const TwitchIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
    <path d="M4 2l-2 4v14h5v3h3l3-3h4l5-5V2H4zm16 10l-3 3h-4l-3 3v-3H7V4h13v8zM17 6h-2v5h2V6zm-5 0h-2v5h2V6z" />
  </svg>
);

const YoutubeIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
    <path d="M23 6.2s-.2-1.6-.9-2.3c-.8-.9-1.8-.9-2.2-1C16.7 2.6 12 2.6 12 2.6s-4.7 0-7.9.3c-.4.1-1.4.1-2.2 1C1.2 4.6 1 6.2 1 6.2S.8 8 .8 9.9v1.8c0 1.8.2 3.7.2 3.7s.2 1.6.9 2.3c.8.9 2 .9 2.4 1 1.8.2 7.7.3 7.7.3s4.7 0 7.9-.3c.4-.1 1.4-.1 2.2-1 .7-.7.9-2.3.9-2.3s.2-1.8.2-3.7V9.9c0-1.8-.2-3.7-.2-3.7zM9.7 13.8V7.2l6.2 3.3-6.2 3.3z" />
  </svg>
);

const GeoguessrIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="10" r="3" />
    <path d="M12 2a8 8 0 0 0-8 8c0 5.5 8 12 8 12s8-6.5 8-12a8 8 0 0 0-8-8z" />
  </svg>
);

const TeamMember = ({ player }: { player: Player }) => (
  <div className="team-member">
    <div className="tm-avatar">
      {player.avatar ? (
        <img src={player.avatar} alt={player.name} />
      ) : (
        <span className="tm-initial">{player.name[0]}</span>
      )}
    </div>
    <div className="tm-meta">
      <div className="tm-name">{player.name}</div>
      <div className="tm-socials">
        {player.twitch && (
          <a
            className="social twitch"
            href={`https://twitch.tv/${player.twitch}`}
            target="_blank"
            rel="noreferrer"
          >
            <TwitchIcon />
            {player.twitch}
          </a>
        )}
        {player.youtube && (
          <a
            className="social youtube"
            href={`https://youtube.com/${player.youtube}`}
            target="_blank"
            rel="noreferrer"
          >
            <YoutubeIcon />
            {player.youtube}
          </a>
        )}
        {player.geoguessr && (
          <a
            className="social geoguessr"
            href={player.geoguessr}
            target="_blank"
            rel="noreferrer"
          >
            <GeoguessrIcon />
            GeoGuessr
          </a>
        )}
      </div>
    </div>
  </div>
);

type KpiProps = {
  label: string;
  value: string | number;
  unit?: string;
  tone?: "win" | "loss";
  big?: boolean;
};

const Kpi = ({ label, value, unit, tone, big }: KpiProps) => (
  <div className={`kpi ${big ? "kpi-big " : ""}${tone ? `kpi-${tone}` : ""}`}>
    <div className="kpi-label">{label}</div>
    <div className="kpi-value">
      {value}
      {unit && <span className="kpi-unit">{unit}</span>}
    </div>
  </div>
);

export default function Header({ period, setPeriod, players, duoRank, stats }: Props) {
  const playerList = Object.values(players);

  return (
    <header className="header">
      <div className="team-card">
        <div className="team-left">
          <div className="team-title-row">
            <div className="team-names">
              {playerList.map((p, i) => (
                <span key={p.name} style={{ display: "contents" }}>
                  {i > 0 && <span className="team-amp">&amp;</span>}
                  <span className="team-name">{p.name}</span>
                </span>
              ))}
            </div>
            <div className="team-rank" title={duoRank}>
              {RANK_ICONS[duoRank] ? (
                <img
                  className="team-rank-icon"
                  src={RANK_ICONS[duoRank]}
                  alt={duoRank}
                />
              ) : (
                <span className="team-rank-val">{duoRank}</span>
              )}
              <span className="team-rank-tooltip">{duoRank}</span>
            </div>
          </div>
        </div>

        <div className="team-players">
          {playerList.map((p) => (
            <TeamMember key={p.name} player={p} />
          ))}
        </div>
      </div>

      <div className="period-bar">
        <span className="tp-label">Période</span>
        <div className="vs-period">
          <button
            className={period === "week1" ? "period-btn active" : "period-btn"}
            onClick={() => setPeriod("week1")}
          >
            Semaine 1
          </button>
          <button
            className={period === "all" ? "period-btn active" : "period-btn"}
            onClick={() => setPeriod("all")}
          >
            Tout
          </button>
        </div>
      </div>

      <div className="kpi-row">
        <Kpi label="Parties jouées" value={stats.games} />
        <Kpi
          label="Win-rate"
          value={`${stats.winRate}%`}
          tone={stats.winRate >= 50 ? "win" : "loss"}
        />
        <Kpi
          label="ELO net"
          value={`${stats.eloNet >= 0 ? "+" : ""}${stats.eloNet}`}
          tone={stats.eloNet >= 0 ? "win" : "loss"}
          big
        />
        <Kpi label="Précision moy." value={`${stats.avgAcc.toFixed(1)}%`} />
        <Kpi
          label="Record de dégâts"
          value={stats.recordDamage.toLocaleString("fr-FR")}
          unit="HP"
        />
      </div>
    </header>
  );
}
