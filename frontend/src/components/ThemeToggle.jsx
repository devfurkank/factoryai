import clsx from "clsx";
import { useTheme } from "../context/ThemeContext";
import Icon from "./Icon";

/** Açık/koyu tema geçiş düğmesi. */
export default function ThemeToggle({ className }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggleTheme}
      title={isDark ? "Açık temaya geç" : "Koyu temaya geç"}
      aria-label={isDark ? "Açık temaya geç" : "Koyu temaya geç"}
      className={clsx(
        "text-on-surface-variant hover:text-primary transition-all p-2 rounded-full hover:bg-primary/5",
        className
      )}
    >
      <Icon name={isDark ? "light_mode" : "dark_mode"} />
    </button>
  );
}
