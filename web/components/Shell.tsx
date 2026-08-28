import type { ReactNode } from "react";
import { Clock } from "./Clock";
import { Icon, type IconName } from "./Icon";

/**
 * Header, left nav and right rail from the design.
 *
 * One departure from the mockup, deliberate: the "Panel cepat" toggles are
 * dropped. In the design they switch the alarm between clear/watch/blocked -- a
 * preview control for the mockup. On the real dashboard a switch that fakes the
 * alarm state is the most dangerous widget that could ship, so it does not.
 */
export type Screen = "operator" | "demo";

const NAV: { key: Screen; label: string; icon: IconName; href: string }[] = [
  { key: "operator", label: "Operator", icon: "dashboard", href: "/" },
  { key: "demo", label: "Demo", icon: "slideshow", href: "/demo" },
];

export function Shell({
  active,
  children,
  rail,
}: {
  active: Screen;
  children: ReactNode;
  rail?: ReactNode;
}) {
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">PintuAir</span>
        <Clock />
        <div className="spacer" />
        <span className="who">Halo, Operator</span>
        <div className="avatar" aria-hidden="true">
          OP
        </div>
      </header>

      <div className="body">
        <nav className="sidebar" aria-label="Halaman">
          {NAV.map((item) => (
            <a
              key={item.key}
              className="nav"
              href={item.href}
              aria-current={item.key === active ? "page" : undefined}
            >
              <Icon name={item.icon} />
              {item.label}
            </a>
          ))}
          <div className="spacer" />
        </nav>

        <main className="main">{children}</main>

        {rail !== undefined && <aside className="rail">{rail}</aside>}
      </div>
    </div>
  );
}
