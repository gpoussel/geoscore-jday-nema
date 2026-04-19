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
  startedAt: string;
  date: string;
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
  duoRank: string;
  eloStart: number;
  eloEnd: number;
  games: number;
  wins: number;
  losses: number;
  vods: Vod[];
};

export type Players = Record<string, Player>;

export type Stats = {
  generatedAt: string;
  duoRank: string;
  games: RawGame[];
  rounds: Round[];
  sessions: Session[];
};

export type Period = "week1" | "all";

export type CountryStat = {
  seen: number;
  acc: number;
  advAcc: number;
  gap: number;
  score: number;
};
