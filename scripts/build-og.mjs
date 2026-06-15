import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Resvg } from "@resvg/resvg-js";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");

const stats = JSON.parse(readFileSync(resolve(root, "src/data/stats.json"), "utf8"));
const playersFile = JSON.parse(readFileSync(resolve(root, "src/data/players.json"), "utf8"));

const games = stats.games;
const wins = games.filter((g) => g.won).length;
const winRate = Math.round((wins / Math.max(1, games.length)) * 100);
const sortedByDate = [...games].sort((a, b) => Number(a.id) - Number(b.id));
const currentElo = sortedByDate[sortedByDate.length - 1]?.elo ?? 0;
const startingElo = sortedByDate[0]?.eloBefore ?? 0;
const eloNet = currentElo - startingElo;
const sessions = stats.sessions.length;
const weeks = new Set(games.map((g) => g.weekKey ?? `${g.year ?? ""}-W${String(g.week).padStart(2, "0")}`)).size;
const rankByWeek = playersFile.duoRanks;
if (!rankByWeek) throw new Error("Missing duoRanks in src/data/players.json");
// Match the site: current rank = latest week that has a rank entry.
const latestWeekKey = Object.keys(rankByWeek).sort().at(-1);
const duoRank = latestWeekKey ? rankByWeek[latestWeekKey] : undefined;
if (!duoRank) throw new Error("Missing current duo rank in src/data/players.json");
const players = Object.values(playersFile.players).map((p) => p.name);

const rankAliases = {
  "master 1": "master_i",
  "master i": "master_i",
  "master 2": "master_ii",
  "master ii": "master_ii",
  "gold 1": "gold_i",
  "gold i": "gold_i",
  "gold 2": "gold_ii",
  "gold ii": "gold_ii",
  "gold 3": "gold_iii",
  "gold iii": "gold_iii",
  "silver 1": "silver_i",
  "silver i": "silver_i",
  "silver 2": "silver_ii",
  "silver ii": "silver_ii",
  "silver 3": "silver_iii",
  "silver iii": "silver_iii",
};
const normalizeRank = (rank) => rank.trim().toLowerCase().replace(/-/g, "_").replace(/\s+/g, " ");
const rankKey = (rank) => {
  const normalized = normalizeRank(rank);
  return rankAliases[normalized] ?? normalized;
};

const fmtSigned = (n) => (n >= 0 ? `+${n}` : `${n}`);

const isChampion = rankKey(duoRank) === "champion";

// Theme mirrors the site: champion → blue palette from the rank icon,
// otherwise the default purple. Keeps the OG card in sync with the page.
const theme = isChampion
  ? {
      title: "Champion !",
      bgTop: "#0b2350",
      bgBottom: "#07172f",
      bgRender: "#07172f",
      glow1: "#2563eb",
      glow2: "#38bdf8",
      eyebrow: "#38bdf8",
      subtitle: "#cfe3ff",
      muted: "#8fb2e6",
      line: "#1d3a6b",
      pos: "#6ee7c7",
      neg: "#ffb38a",
    }
  : {
      title: "Road to Champion",
      rankNote: "objectif Champion",
      bgTop: "#1a0d4a",
      bgBottom: "#0a0524",
      bgRender: "#0a0524",
      glow1: "#7950e5",
      glow2: "#3ae8bd",
      eyebrow: "#3ae8bd",
      subtitle: "#dcd6f5",
      muted: "#a89dc8",
      line: "#3a2a78",
      pos: "#3ae8bd",
      neg: "#ff9966",
    };

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${theme.bgTop}"/>
      <stop offset="100%" stop-color="${theme.bgBottom}"/>
    </linearGradient>
    <radialGradient id="glow1" cx="0" cy="0" r="1">
      <stop offset="0%" stop-color="${theme.glow1}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="${theme.glow1}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="glow2" cx="1" cy="0" r="1">
      <stop offset="0%" stop-color="${theme.glow2}" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="${theme.glow2}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="cardBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.02"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect width="1200" height="630" fill="url(#glow1)" transform="translate(-100 -200) scale(1.4)"/>
  <rect width="1200" height="630" fill="url(#glow2)" transform="translate(400 -250) scale(1.3)"/>

  <text x="80" y="100" font-family="'Geist', 'Helvetica Neue', Arial, sans-serif"
        font-size="18" font-weight="600" fill="${theme.eyebrow}" letter-spacing="6">
    GEOSCORE · DUO STATS
  </text>

  <text x="80" y="220" font-family="'Instrument Serif', Georgia, serif"
        font-style="italic" font-size="124" font-weight="400" fill="#ffffff">
    ${theme.title}
  </text>

  <text x="80" y="285" font-family="'Geist', 'Helvetica Neue', Arial, sans-serif"
        font-size="34" font-weight="500" fill="${theme.subtitle}">
    ${players.join(" × ")} · GeoGuessr Duels
  </text>

  <line x1="80" y1="340" x2="1120" y2="340" stroke="${theme.line}" stroke-width="1"/>

  <g transform="translate(80 380)">
    <rect width="240" height="180" rx="14" fill="url(#cardBg)" stroke="${theme.line}" stroke-width="1"/>
    <text x="20" y="38" font-family="'Geist', Arial, sans-serif"
          font-size="13" font-weight="600" fill="${theme.muted}" letter-spacing="3">ELO ACTUEL</text>
    <text x="20" y="118" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="68" font-weight="700" fill="#ffffff">${currentElo}</text>
    <text x="20" y="155" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="20" font-weight="500" fill="${eloNet >= 0 ? theme.pos : theme.neg}">
      ${fmtSigned(eloNet)} depuis le début
    </text>
  </g>

  <g transform="translate(480 380)">
    <rect width="240" height="180" rx="14" fill="url(#cardBg)" stroke="${theme.line}" stroke-width="1"/>
    <text x="20" y="38" font-family="'Geist', Arial, sans-serif"
          font-size="13" font-weight="600" fill="${theme.muted}" letter-spacing="3">VICTOIRES</text>
    <text x="20" y="118" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="68" font-weight="700" fill="#ffffff">${winRate}<tspan font-size="40" fill="${theme.muted}">%</tspan></text>
    <text x="20" y="155" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="20" font-weight="500" fill="${theme.subtitle}">
      ${wins} / ${games.length} parties
    </text>
  </g>

  <g transform="translate(880 380)">
    <rect width="240" height="180" rx="14" fill="url(#cardBg)" stroke="${theme.line}" stroke-width="1"/>
    <text x="20" y="38" font-family="'Geist', Arial, sans-serif"
          font-size="13" font-weight="600" fill="${theme.muted}" letter-spacing="3">SESSIONS</text>
    <text x="20" y="118" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="68" font-weight="700" fill="#ffffff">${sessions}</text>
    <text x="20" y="155" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="20" font-weight="500" fill="${theme.subtitle}">
      sur ${weeks} semaine${weeks > 1 ? "s" : ""}
    </text>
  </g>
</svg>
`;

const resvg = new Resvg(svg, {
  fitTo: { mode: "width", value: 1200 },
  font: { loadSystemFonts: true },
  background: theme.bgRender,
});
const png = resvg.render().asPng();

const outDir = resolve(root, "public");
mkdirSync(outDir, { recursive: true });
const outPath = resolve(outDir, "og.png");
writeFileSync(outPath, png);

console.log(`[og] wrote ${outPath} (${(png.length / 1024).toFixed(1)} KB)`);
console.log(`[og] elo=${currentElo} (${fmtSigned(eloNet)}) wins=${winRate}% sessions=${sessions} weeks=${weeks}`);
