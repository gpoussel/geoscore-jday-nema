import countries from "i18n-iso-countries";
import fr from "i18n-iso-countries/langs/fr.json";
import { WORLD } from "../data/world";

countries.registerLocale(fr);

const overrides = new Map<string, string>(WORLD.map((c) => [c.c.toUpperCase(), c.n]));

export function countryName(code: string | undefined | null): string {
  if (!code) return "—";
  const upper = code.toUpperCase();
  const override = overrides.get(upper);
  if (override) return override;
  const name = countries.getName(upper, "fr", { select: "official" });
  return name ?? upper;
}
