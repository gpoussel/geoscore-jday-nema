export type Player = {
  name: string;
  twitch: string | null;
  youtube: string | null;
  geoguessr: string | null;
  avatar: string | null;
};

export type Vod = {
  platform: "twitch" | "youtube";
  player: string | null;
  url: string;
};

export type RawGame = {
  id: string;
  session: string;
  week: number;
  gameNum: number;
  rounds: number;
  won: boolean;
  margin: "tight" | "clean" | "crush";
  elo: number;
  eloBefore: number;
  eloDelta: number;
  roundBuckets: number[];
  perfects: number;
  finalMyHp: number;
  finalOppHp: number;
  finalMyMult: number;
  finalOppMult: number;
};

export type Game = RawGame & {
  myAcc: number;
  advAcc: number;
};

export type Round = {
  gameId: string;
  roundNum: number;
  country: string;
  myScore: number;
  oppScore: number;
  winner: "me" | "opp" | "tie";
  damage: number;
  usedMult: number;
};

export type Session = {
  id: string;
  week: number;
  num: number;
  date: string;
  time: string;
  eloStart: number;
  eloEnd: number;
  games: number;
  wins: number;
  losses: number;
  vods: Vod[];
};

export type Players = Record<string, Player>;

export type PlayersFile = {
  duoRank: string;
  players: Players;
};

export type Distribution = {
  map: string;
  source: string;
  from?: string;
  to?: string;
  counts: Record<string, number>;
};

export type DistributionsFile = { distributions: Distribution[] };

export type Stats = {
  generatedAt: string;
  games: RawGame[];
  rounds: Round[];
  sessions: Session[];
};

export type Period = "current" | "all";

export type CountryStat = {
  seen: number;
  acc: number;
  advAcc: number;
  gap: number;
  score: number;
  expectedShare: number;
  deviation: number | null;
};
