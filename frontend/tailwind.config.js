/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#1e293b",
        border: "#334155",
        accent: "#3b82f6",
        danger: "#ef4444",
        warn: "#f59e0b",
        ok: "#22c55e",
      },
    },
  },
  plugins: [],
};
