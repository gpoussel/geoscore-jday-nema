// Simplified world map as a grid of country tiles — each country is a small
// rect on a 1000x500 viewbox. Not geographically perfect but readable as a
// world map for infographic purposes.

export type WorldTile = {
  c: string;
  n: string;
  x: number;
  y: number;
  w: number;
  h: number;
};

export const WORLD: WorldTile[] = [
  // Europe
  { c: "IS", n: "Islande",     x: 445, y: 105, w: 22, h: 14 },
  { c: "IE", n: "Irlande",     x: 455, y: 145, w: 14, h: 14 },
  { c: "GB", n: "Royaume-Uni", x: 473, y: 140, w: 16, h: 20 },
  { c: "PT", n: "Portugal",    x: 460, y: 195, w: 10, h: 18 },
  { c: "ES", n: "Espagne",     x: 473, y: 195, w: 22, h: 20 },
  { c: "FR", n: "France",      x: 497, y: 170, w: 20, h: 22 },
  { c: "BE", n: "Belgique",    x: 500, y: 155, w: 10, h: 8 },
  { c: "NL", n: "Pays-Bas",    x: 511, y: 150, w: 10, h: 8 },
  { c: "DE", n: "Allemagne",   x: 519, y: 160, w: 16, h: 18 },
  { c: "DK", n: "Danemark",    x: 519, y: 140, w: 10, h: 10 },
  { c: "NO", n: "Norvège",     x: 519, y: 105, w: 14, h: 30 },
  { c: "SE", n: "Suède",       x: 534, y: 105, w: 12, h: 30 },
  { c: "FI", n: "Finlande",    x: 547, y: 105, w: 14, h: 28 },
  { c: "CH", n: "Suisse",      x: 519, y: 180, w: 10, h: 8 },
  { c: "AT", n: "Autriche",    x: 530, y: 180, w: 12, h: 8 },
  { c: "IT", n: "Italie",      x: 525, y: 193, w: 14, h: 22 },
  { c: "PL", n: "Pologne",     x: 543, y: 160, w: 16, h: 14 },
  { c: "CZ", n: "Tchéquie",    x: 543, y: 175, w: 14, h: 8 },
  { c: "HU", n: "Hongrie",     x: 545, y: 185, w: 14, h: 8 },
  { c: "RO", n: "Roumanie",    x: 560, y: 185, w: 16, h: 12 },
  { c: "GR", n: "Grèce",       x: 548, y: 205, w: 14, h: 12 },
  { c: "TR", n: "Turquie",     x: 565, y: 200, w: 28, h: 14 },
  { c: "UA", n: "Ukraine",     x: 562, y: 165, w: 24, h: 16 },
  { c: "RU", n: "Russie",      x: 590, y: 120, w: 180, h: 42 },

  // Middle East
  { c: "IL", n: "Israël",  x: 575, y: 220, w: 8,  h: 10 },
  { c: "AE", n: "Émirats", x: 605, y: 240, w: 14, h: 8 },
  { c: "EG", n: "Égypte",  x: 566, y: 235, w: 16, h: 16 },

  // Africa
  { c: "MA", n: "Maroc",          x: 474, y: 222, w: 18, h: 14 },
  { c: "KE", n: "Kenya",          x: 585, y: 285, w: 14, h: 14 },
  { c: "ZA", n: "Afrique du Sud", x: 565, y: 345, w: 24, h: 20 },

  // Asia
  { c: "IN", n: "Inde",         x: 670, y: 230, w: 28, h: 32 },
  { c: "TH", n: "Thaïlande",    x: 720, y: 245, w: 14, h: 22 },
  { c: "VN", n: "Vietnam",      x: 736, y: 240, w: 10, h: 28 },
  { c: "MY", n: "Malaisie",     x: 730, y: 275, w: 18, h: 8 },
  { c: "SG", n: "Singapour",    x: 738, y: 285, w: 6,  h: 5 },
  { c: "ID", n: "Indonésie",    x: 735, y: 295, w: 40, h: 14 },
  { c: "PH", n: "Philippines",  x: 760, y: 255, w: 14, h: 18 },
  { c: "TW", n: "Taïwan",       x: 758, y: 235, w: 8,  h: 10 },
  { c: "JP", n: "Japon",        x: 780, y: 195, w: 18, h: 28 },
  { c: "KR", n: "Corée du Sud", x: 766, y: 210, w: 12, h: 12 },

  // Oceania
  { c: "AU", n: "Australie",        x: 760, y: 320, w: 56, h: 32 },
  { c: "NZ", n: "Nouvelle-Zélande", x: 830, y: 360, w: 14, h: 14 },

  // Americas
  { c: "CA", n: "Canada",     x: 180, y: 105, w: 130, h: 40 },
  { c: "US", n: "États-Unis", x: 180, y: 155, w: 130, h: 40 },
  { c: "MX", n: "Mexique",    x: 195, y: 205, w: 40, h: 22 },
  { c: "CO", n: "Colombie",   x: 255, y: 245, w: 18, h: 18 },
  { c: "PE", n: "Pérou",      x: 255, y: 275, w: 18, h: 22 },
  { c: "CL", n: "Chili",      x: 268, y: 305, w: 10, h: 42 },
  { c: "AR", n: "Argentine",  x: 280, y: 305, w: 24, h: 50 },
  { c: "BR", n: "Brésil",     x: 290, y: 245, w: 48, h: 52 },
];
