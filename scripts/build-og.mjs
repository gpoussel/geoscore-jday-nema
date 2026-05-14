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
const latestSession = [...stats.sessions]
  .filter((s) => s.games > 0)
  .sort((a, b) => a.date.localeCompare(b.date) || a.id.localeCompare(b.id))
  .at(-1);
const duoRank = latestSession ? rankByWeek[latestSession.weekKey] : undefined;
if (!duoRank) throw new Error("Missing current duo rank in src/data/players.json");
const players = Object.values(playersFile.players).map((p) => p.name);

const rankLabels = {
  champion: "Champion",
  master_i: "Master I",
  master_ii: "Master II",
  gold_i: "Gold I",
  gold_ii: "Gold II",
  gold_iii: "Gold III",
  silver_i: "Silver I",
  silver_ii: "Silver II",
  silver_iii: "Silver III",
  bronze: "Bronze",
};
const normalizeRank = (rank) => rank.trim().toLowerCase().replace(/-/g, "_").replace(/\s+/g, " ");
const rankLabel = (rank) => {
  const normalized = normalizeRank(rank);
  const key = {
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
  }[normalized] ?? normalized;
  return rankLabels[key] ?? rank;
};

const fmtSigned = (n) => (n >= 0 ? `+${n}` : `${n}`);

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1a0d4a"/>
      <stop offset="100%" stop-color="#0a0524"/>
    </linearGradient>
    <radialGradient id="purpleGlow" cx="0" cy="0" r="1">
      <stop offset="0%" stop-color="#7950e5" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#7950e5" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="tealGlow" cx="1" cy="0" r="1">
      <stop offset="0%" stop-color="#3ae8bd" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="#3ae8bd" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="cardBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#ffffff" stop-opacity="0.02"/>
    </linearGradient>
    <linearGradient id="rankGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#3ae8bd"/>
      <stop offset="100%" stop-color="#7950e5"/>
    </linearGradient>
  </defs>

  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect width="1200" height="630" fill="url(#purpleGlow)" transform="translate(-100 -200) scale(1.4)"/>
  <rect width="1200" height="630" fill="url(#tealGlow)" transform="translate(400 -250) scale(1.3)"/>

  <text x="80" y="100" font-family="'Geist', 'Helvetica Neue', Arial, sans-serif"
        font-size="18" font-weight="600" fill="#3ae8bd" letter-spacing="6">
    GEOSCORE · DUO STATS
  </text>

  <text x="80" y="220" font-family="'Instrument Serif', Georgia, serif"
        font-style="italic" font-size="124" font-weight="400" fill="#ffffff">
    Road to Champion
  </text>

  <text x="80" y="285" font-family="'Geist', 'Helvetica Neue', Arial, sans-serif"
        font-size="34" font-weight="500" fill="#dcd6f5">
    ${players.join(" × ")} · GeoGuessr Duels
  </text>

  <line x1="80" y1="340" x2="1120" y2="340" stroke="#3a2a78" stroke-width="1"/>

  <g transform="translate(80 380)">
    <rect width="240" height="180" rx="14" fill="url(#cardBg)" stroke="#3a2a78" stroke-width="1"/>
    <text x="20" y="38" font-family="'Geist', Arial, sans-serif"
          font-size="13" font-weight="600" fill="#a89dc8" letter-spacing="3">ELO ACTUEL</text>
    <text x="20" y="118" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="68" font-weight="700" fill="#ffffff">${currentElo}</text>
    <text x="20" y="155" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="20" font-weight="500" fill="${eloNet >= 0 ? "#3ae8bd" : "#ff9966"}">
      ${fmtSigned(eloNet)} depuis le début
    </text>
  </g>

  <g transform="translate(340 380)">
    <rect width="240" height="180" rx="14" fill="url(#cardBg)" stroke="#3a2a78" stroke-width="1"/>
    <text x="20" y="38" font-family="'Geist', Arial, sans-serif"
          font-size="13" font-weight="600" fill="#a89dc8" letter-spacing="3">VICTOIRES</text>
    <text x="20" y="118" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="68" font-weight="700" fill="#ffffff">${winRate}<tspan font-size="40" fill="#a89dc8">%</tspan></text>
    <text x="20" y="155" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="20" font-weight="500" fill="#dcd6f5">
      ${wins} / ${games.length} parties
    </text>
  </g>

  <g transform="translate(600 380)">
    <rect width="240" height="180" rx="14" fill="url(#cardBg)" stroke="#3a2a78" stroke-width="1"/>
    <text x="20" y="38" font-family="'Geist', Arial, sans-serif"
          font-size="13" font-weight="600" fill="#a89dc8" letter-spacing="3">SESSIONS</text>
    <text x="20" y="118" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="68" font-weight="700" fill="#ffffff">${sessions}</text>
    <text x="20" y="155" font-family="'JetBrains Mono', 'Courier New', monospace"
          font-size="20" font-weight="500" fill="#dcd6f5">
      sur ${weeks} semaine${weeks > 1 ? "s" : ""}
    </text>
  </g>

  <g transform="translate(860 380)">
    <rect width="260" height="180" rx="14" fill="url(#cardBg)" stroke="#3a2a78" stroke-width="1"/>
    <text x="20" y="38" font-family="'Geist', Arial, sans-serif"
          font-size="13" font-weight="600" fill="#a89dc8" letter-spacing="3">RANG DUO</text>
    <rect x="20" y="62" width="220" height="6" rx="3" fill="url(#rankGrad)"/>
    <text x="20" y="130" font-family="'Instrument Serif', Georgia, serif"
          font-style="italic" font-size="60" font-weight="400" fill="#ffffff">${rankLabel(duoRank)}</text>
    <text x="20" y="160" font-family="'Geist', Arial, sans-serif"
          font-size="16" font-weight="500" fill="#a89dc8">objectif Champion</text>
  </g>
</svg>
`;

const resvg = new Resvg(svg, {
  fitTo: { mode: "width", value: 1200 },
  font: { loadSystemFonts: true },
  background: "#0a0524",
});
const png = resvg.render().asPng();

const outDir = resolve(root, "public");
mkdirSync(outDir, { recursive: true });
const outPath = resolve(outDir, "og.png");
writeFileSync(outPath, png);

console.log(`[og] wrote ${outPath} (${(png.length / 1024).toFixed(1)} KB)`);
console.log(`[og] elo=${currentElo} (${fmtSigned(eloNet)}) wins=${winRate}% sessions=${sessions} weeks=${weeks}`);
