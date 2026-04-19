import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://gpoussel.github.io",
  base: "/geoscore-jday-nema",
  output: "static",
  vite: {
    build: {
      assetsInlineLimit: 0,
    },
  },
});
