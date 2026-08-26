/**
 * Inline SVG icons.
 *
 * The design calls for Material Symbols, which is an icon *font* loaded from a
 * CDN. This deployment is a laptop in a gatehouse that may have no internet: a
 * failed icon font renders its ligatures as literal words ("water_drop") across
 * the whole page. Inline paths cannot fail that way.
 *
 * Stroke-based on purpose -- one rule (currentColor) makes every icon inherit
 * the colour of whatever it sits in.
 */
export type IconName =
  | "dashboard"
  | "monitoring"
  | "slideshow"
  | "settings"
  | "water"
  | "rain"
  | "layers"
  | "check"
  | "warning"
  | "block"
  | "help";

const PATHS: Record<IconName, React.ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </>
  ),
  monitoring: (
    <>
      <path d="M3 3v18h18" />
      <path d="M7 15l4-5 3 3 5-7" />
    </>
  ),
  slideshow: (
    <>
      <rect x="3" y="4" width="18" height="13" rx="2" />
      <path d="M10 8.5l4.5 2.5L10 13.5z" />
      <path d="M8 21h8" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.2 2.2M16.9 16.9l2.2 2.2M19.1 4.9l-2.2 2.2M7.1 16.9l-2.2 2.2" />
    </>
  ),
  water: <path d="M12 3s6 6.5 6 10.5a6 6 0 0 1-12 0C6 9.5 12 3 12 3z" />,
  rain: (
    <>
      <path d="M7 15a4 4 0 0 1 .6-7.96 5.5 5.5 0 0 1 10.5 1.6A3.5 3.5 0 0 1 17.5 15z" />
      <path d="M8 18l-1 3M12.5 18l-1 3M17 18l-1 3" />
    </>
  ),
  layers: (
    <>
      <path d="M12 3l9 5-9 5-9-5 9-5z" />
      <path d="M3 13l9 5 9-5" />
    </>
  ),
  check: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M8 12.5l2.5 2.5L16 9.5" />
    </>
  ),
  warning: (
    <>
      <path d="M12 3.5L21.5 20H2.5L12 3.5z" />
      <path d="M12 10v4.5" />
      <circle cx="12" cy="17.2" r="0.9" fill="currentColor" stroke="none" />
    </>
  ),
  block: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M5.6 5.6l12.8 12.8" />
    </>
  ),
  help: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.4 9.3a2.7 2.7 0 0 1 5.2.9c0 1.8-2.6 2.1-2.6 3.9" />
      <circle cx="12" cy="17.3" r="0.9" fill="currentColor" stroke="none" />
    </>
  ),
};

export function Icon({
  name,
  size = 21,
  color,
}: {
  name: IconName;
  size?: number;
  color?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke={color ?? "currentColor"}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ flex: "none", display: "block" }}
    >
      {PATHS[name]}
    </svg>
  );
}
