import clsx from "clsx";

/** Material Symbols Outlined sarmalayıcı — Glacier tasarımındaki ikon setiyle birebir eşleşir. */
export default function Icon({ name, className, filled = false, style, ...props }) {
  return (
    <span
      className={clsx("material-symbols-outlined", filled && "fill", className)}
      style={style}
      {...props}
    >
      {name}
    </span>
  );
}
