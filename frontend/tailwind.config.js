/** @type {import('tailwindcss').Config} */

/** CSS değişkenine bağlı renk üretici — hem düz renk hem `/opacity` modifikatörünü destekler. */
function withOpacity(variable) {
  return ({ opacityValue }) =>
    opacityValue === undefined
      ? `rgb(var(${variable}))`
      : `rgb(var(${variable}) / ${opacityValue})`;
}

const TOKENS = [
  "background", "on-background",
  "surface", "on-surface", "surface-dim", "surface-bright",
  "surface-container-lowest", "surface-container-low", "surface-container",
  "surface-container-high", "surface-container-highest", "surface-variant",
  "on-surface-variant", "outline", "outline-variant",
  "inverse-surface", "inverse-on-surface", "inverse-primary", "surface-tint",
  "primary", "on-primary", "primary-container", "on-primary-container",
  "primary-fixed", "primary-fixed-dim", "on-primary-fixed", "on-primary-fixed-variant",
  "secondary", "on-secondary", "secondary-container", "on-secondary-container",
  "secondary-fixed", "secondary-fixed-dim", "on-secondary-fixed", "on-secondary-fixed-variant",
  "tertiary", "on-tertiary", "tertiary-container", "on-tertiary-container",
  "tertiary-fixed", "tertiary-fixed-dim", "on-tertiary-fixed", "on-tertiary-fixed-variant",
  "error", "on-error", "error-container", "on-error-container",
];

const themeColors = Object.fromEntries(
  TOKENS.map((name) => [name, withOpacity(`--color-${name}`)])
);

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        headline: ["Inter", "sans-serif"],
        display: ["Inter", "sans-serif"],
        body: ["Inter", "sans-serif"],
        label: ["Inter", "sans-serif"],
      },
      colors: themeColors,
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "1rem",
        xl: "1.5rem",
        full: "9999px",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.08), 0 1px 3px 0 rgb(0 0 0 / 0.12)",
        pop: "0 10px 32px -8px rgb(0 0 0 / 0.35), 0 4px 12px -4px rgb(0 0 0 / 0.2)",
        glow: "0 0 30px rgb(var(--color-primary) / 0.05)",
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
        "pulse-box": {
          "0%, 100%": { borderColor: "rgb(var(--color-primary) / 0.4)", boxShadow: "0 0 5px rgb(var(--color-primary) / 0.2)" },
          "50%": { borderColor: "rgb(var(--color-primary) / 1)", boxShadow: "0 0 15px rgb(var(--color-primary) / 0.6)" },
        },
      },
      animation: {
        "slide-in": "slide-in 0.25s ease-out",
        "fade-up": "fade-up 0.3s ease-out",
        "pulse-box": "pulse-box 2s infinite",
      },
    },
  },
  plugins: [],
};
