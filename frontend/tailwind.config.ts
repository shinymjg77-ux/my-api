import type { Config } from "tailwindcss";


const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        panel: "0 18px 40px rgba(15, 23, 42, 0.08)",
      },
      colors: {
        shell: "var(--shell)",
        panel: "var(--panel)",
        panelStrong: "var(--panel-strong)",
        line: "var(--line)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        accent: "var(--accent)",
        accentSoft: "var(--accent-soft)",
        ok: "var(--ok)",
        okSoft: "var(--ok-soft)",
        warn: "var(--warn)",
        warnSoft: "var(--warn-soft)",
        danger: "var(--danger)",
        dangerSoft: "var(--danger-soft)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
    },
  },
  plugins: [],
};


export default config;
