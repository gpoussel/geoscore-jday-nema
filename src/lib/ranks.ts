export const RANKS = {
  champion: { label: "Champion", shortLabel: "C", division: "champion", icon: "champion.webp" },
  master_i: { label: "Master I", shortLabel: "M1", division: "master", icon: "master_i.webp" },
  master_ii: { label: "Master II", shortLabel: "M2", division: "master", icon: "master_ii.webp" },
  gold_i: { label: "Gold I", shortLabel: "G1", division: "gold", icon: "gold_i.webp" },
  gold_ii: { label: "Gold II", shortLabel: "G2", division: "gold", icon: "gold_ii.webp" },
  gold_iii: { label: "Gold III", shortLabel: "G3", division: "gold", icon: "gold_iii.webp" },
  silver_i: { label: "Silver I", shortLabel: "S1", division: "silver", icon: "silver_i.webp" },
  silver_ii: { label: "Silver II", shortLabel: "S2", division: "silver", icon: "silver_ii.webp" },
  silver_iii: { label: "Silver III", shortLabel: "S3", division: "silver", icon: "silver_iii.webp" },
  bronze: { label: "Bronze", shortLabel: "B", division: "bronze", icon: "bronze.webp" },
} as const;

export type RankKey = keyof typeof RANKS;

const ALIASES: Record<string, RankKey> = {
  champion: "champion",
  "master 1": "master_i",
  "master i": "master_i",
  master_i: "master_i",
  master1: "master_i",
  "master 2": "master_ii",
  "master ii": "master_ii",
  master_ii: "master_ii",
  master2: "master_ii",
  "gold 1": "gold_i",
  "gold i": "gold_i",
  gold_i: "gold_i",
  gold1: "gold_i",
  "gold 2": "gold_ii",
  "gold ii": "gold_ii",
  gold_ii: "gold_ii",
  gold2: "gold_ii",
  "gold 3": "gold_iii",
  "gold iii": "gold_iii",
  gold_iii: "gold_iii",
  gold3: "gold_iii",
  "silver 1": "silver_i",
  "silver i": "silver_i",
  silver_i: "silver_i",
  silver1: "silver_i",
  "silver 2": "silver_ii",
  "silver ii": "silver_ii",
  silver_ii: "silver_ii",
  silver2: "silver_ii",
  "silver 3": "silver_iii",
  "silver iii": "silver_iii",
  silver_iii: "silver_iii",
  silver3: "silver_iii",
  bronze: "bronze",
};

export const normalizeRank = (rank: string): RankKey | undefined =>
  ALIASES[rank.trim().toLowerCase().replace(/-/g, "_").replace(/\s+/g, " ")];

export const rankLabel = (rank: string): string => {
  const key = normalizeRank(rank);
  return key ? RANKS[key].label : rank;
};

export const rankShortLabel = (rank: string): string => {
  const key = normalizeRank(rank);
  return key ? RANKS[key].shortLabel : rank;
};

export const rankIcon = (rank: string): string | undefined => {
  const key = normalizeRank(rank);
  return key ? RANKS[key].icon : undefined;
};

export const rankDivision = (rank: string): string => {
  const key = normalizeRank(rank);
  return key ? RANKS[key].division : rank.trim().split(/\s+/)[0].toLowerCase();
};
