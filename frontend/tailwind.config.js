/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
      },
      colors: {
        // Açık tema tasarım token'ları (Faz 6 — 2026 yönetim paneli)
        canvas: "#f6f7f9",   // uygulama zemini
        surface: "#ffffff",  // kart/panel zemini
        line: "#e7e9ee",     // ayraç/çerçeve
        ink: {
          DEFAULT: "#0f172a", // birincil metin
          soft: "#475569",    // ikincil metin
          faint: "#94a3b8",   // ipucu/etiket metni
        },
        accent: {
          DEFAULT: "#4f46e5", // indigo-600
          soft: "#eef2ff",    // indigo-50
          strong: "#4338ca",  // indigo-700
        },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
        pop: "0 10px 32px -8px rgb(15 23 42 / 0.16), 0 4px 12px -4px rgb(15 23 42 / 0.08)",
      },
      keyframes: {
        "slide-in": {
          from: { opacity: "0", transform: "translateX(16px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "fade-up": {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "slide-in": "slide-in 0.25s ease-out",
        "fade-up": "fade-up 0.3s ease-out",
      },
    },
  },
  plugins: [],
};
