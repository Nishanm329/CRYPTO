/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0b0c15",
          sidebar: "#0f1020",
          card: "#13141f",
          card2: "#1a1b2e",
          header: "#0e0f1d",
        },
        border: {
          DEFAULT: "#1e1f30",
          light: "#252640",
        },
        tx: {
          DEFAULT: "#e0e2f0",
          muted: "#5a5e7a",
          dim: "#3a3d5c",
        },
        brand: {
          green: "#00c896",
          red: "#ef4444",
          blue: "#3d7fff",
          amber: "#f59e0b",
          purple: "#a855f7",
          cyan: "#06d6d4",
          gold: "#f4b942",
        },
        // Keep compat aliases
        surface: {
          DEFAULT: "#0b0c15",
          1: "#13141f",
          2: "#1e1f30",
          3: "#252640",
        },
      },
      fontFamily: {
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
        sans: ["Inter", "ui-sans-serif", "system-ui"],
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fadeIn 0.3s ease-out",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: 0, transform: "translateY(4px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
