import type { Player, Session, Vod } from "../types";

const TwitchPath = (
  <path d="M4 2l-2 4v14h5v3h3l3-3h4l5-5V2H4z" />
);
const YoutubePath = (
  <path d="M23 6.2s-.2-1.6-.9-2.3c-.8-.9-1.8-.9-2.2-1C16.7 2.6 12 2.6 12 2.6s-4.7 0-7.9.3c-.4.1-1.4.1-2.2 1C1.2 4.6 1 6.2 1 6.2S.8 8 .8 9.9v4c0 1.8.2 3.7.2 3.7s.2 1.6.9 2.3c.8.9 2 .9 2.4 1 1.8.2 7.7.3 7.7.3s4.7 0 7.9-.3c.4-.1 1.4-.1 2.2-1 .7-.7.9-2.3.9-2.3s.2-1.8.2-3.7V9.9c0-1.8-.2-3.7-.2-3.7zM9.7 13.8V7.2l6.2 3.3-6.2 3.3z" />
);

const VodChip = ({ vod, players }: { vod: Vod; players: Record<string, Player> }) => {
  const player = vod.player ? players[vod.player] : null;
  const cls = `vod-chip vod-${vod.platform}`;
  const label = player ? player.name : vod.platform;
  return (
    <a
      className={cls}
      href={vod.url || "#"}
      target="_blank"
      rel="noreferrer"
      title={`VOD ${vod.platform} · ${label}`}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
        {vod.platform === "twitch" ? TwitchPath : YoutubePath}
      </svg>
      {player && <span className="vod-avatar">{player.name[0]}</span>}
    </a>
  );
};

const SessionCard = ({
  session,
  players,
}: {
  session: Session;
  players: Record<string, Player>;
}) => {
  const eloDelta = session.eloEnd - session.eloStart;
  const won = session.wins > session.losses;
  const date = new Date(session.date);
  const dateStr = Number.isNaN(date.getTime())
    ? session.date
    : date.toLocaleDateString("fr-FR", { day: "2-digit", month: "short" });

  return (
    <div className="session-card">
      <div className="sc-head">
        <span className="sc-date">{dateStr}</span>
        <span className="sc-week">S{session.week}</span>
      </div>
      <div className="sc-ranks">
        <div className="sc-rank">
          <span className="sc-rank-name">Rang duo</span>
          <span className="sc-rank-val">{session.duoRank}</span>
        </div>
      </div>
      <div className="sc-elo">
        <div className="sc-elo-row">
          <span>ELO</span>
          <b>
            {session.eloStart} → {session.eloEnd}
          </b>
        </div>
        <div className={"sc-elo-delta " + (eloDelta >= 0 ? "pos" : "neg")}>
          {eloDelta >= 0 ? "+" : ""}
          {eloDelta}
        </div>
      </div>
      <div className="sc-score">
        <span className="sc-score-w">{session.wins}</span>
        <span className="sc-score-sep">–</span>
        <span className="sc-score-l">{session.losses}</span>
        <span className="sc-score-lbl">{session.games} parties</span>
      </div>
      {session.vods.length > 0 && (
        <div className="sc-vods">
          {session.vods.map((vod, i) => (
            <VodChip key={i} vod={vod} players={players} />
          ))}
        </div>
      )}
      <div className={"sc-strip " + (won ? "sc-strip-win" : "sc-strip-loss")} />
    </div>
  );
};

export default function BlockSessions({
  sessions,
  players,
}: {
  sessions: Session[];
  players: Record<string, Player>;
}) {
  return (
    <section className="block" id="block-sessions">
      <div className="block-head">
        <h2 className="block-title">
          Sessions <em>&amp; replays</em>
        </h2>
      </div>
      <div className="sessions-timeline">
        {sessions.map((s) => (
          <SessionCard key={s.name} session={s} players={players} />
        ))}
      </div>
    </section>
  );
}
