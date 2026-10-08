/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      // Every color is a role backed by a CSS variable (see globals.css), so
      // light and dark values swap in one place.
      colors: {
        page: "var(--page)",
        surface: "var(--surface)",
        sunken: "var(--sunken)",
        ink: "var(--ink)",
        ink2: "var(--ink-2)",
        muted: "var(--muted)",
        line: "var(--line)",
        grid: "var(--grid)",
        axis: "var(--axis)",
        accent: "var(--accent)",
        "accent-ink": "var(--accent-ink)",
        "accent-wash": "var(--accent-wash)",
        up: "var(--up)",
        down: "var(--down)",
        warn: "var(--warn)",
        series1: "var(--series-1)",
        series2: "var(--series-2)",
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      boxShadow: {
        pop: "0 8px 24px -8px rgb(0 0 0 / 0.25), 0 0 0 1px var(--line)",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
