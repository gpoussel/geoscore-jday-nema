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
  year: number;
  week: number;
  weekKey: string;
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
  year: number;
  week: number;
  weekKey: string;
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

export type MapDistribution = {
  id: string;
  name: string;
  source: string;
  counts?: Record<string, number>;
  countsFromMapId?: string;
};

export type MapAssignment = {
  division: string;
  mapId: string;
  from?: string;
  to?: string;
};

export type Distribution = MapDistribution & {
  counts: Record<string, number>;
  assignment: MapAssignment;
};

export type DistributionsFile = {
  maps: MapDistribution[];
  assignments: MapAssignment[];
};

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
