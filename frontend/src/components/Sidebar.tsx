"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

// Left navigation (1 Nov 2026 redesign). Icons are inline SVG so there is no icon library to install or break.
const ICONS: Record<string, React.ReactNode> = {
  home: <path d="M3 11.5 12 4l9 7.5M5.5 10v9h13v-9" />,
  brief: <path d="M5 4h14v16H5zM8.5 9h7M8.5 13h7M8.5 17h4" />,
  dashboard: <path d="M4 20V10m6 10V4m6 16v-7m4 7H3" />,
  passport: <path d="M6 3.5h12a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1zM12 9.5a2.2 2.2 0 1 0 0 .01M8.5 16c.6-1.8 2-2.7 3.5-2.7s2.9.9 3.5 2.7" />,
  insights: <path d="M4 18 9 12l4 3 7-9M4 21h16" />,
  monitoring: <path d="M12 3 3 19h18zM12 10v4.5M12 17.2v.1" />,
  explain: <path d="M6 7a2 2 0 1 0 0 .01M18 6a2 2 0 1 0 0 .01M12 18a2 2 0 1 0 0 .01M7.6 8.1l3.2 8.2M16.6 7.7l-3.4 8.6M8 6.4l8 .2" />,
  analysis: <path d="M4 20h16M7 20v-6m5 6V8m5 12v-9" />,
};

const GROUPS = [
  {
    label: "Work",
    items: [
      { href: "/", label: "Overview", icon: "home" },
      { href: "/brand-input", label: "New brief", icon: "brief" },
      { href: "/dashboard", label: "Ranked creators", icon: "dashboard" },
      { href: "/passport", label: "Creator Passport", icon: "passport" },
    ],
  },
  {
    label: "Evidence",
    items: [
      { href: "/insights", label: "Insights", icon: "insights" },
      { href: "/analysis", label: "Analysis", icon: "analysis" },
      { href: "/explainability", label: "Graph and scores", icon: "explain" },
      { href: "/monitoring", label: "Monitoring", icon: "monitoring" },
    ],
  },
];

function Icon({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {ICONS[name]}
    </svg>
  );
}

function Mark() {
  // a small network: one node reaching its neighbours (the project in one picture)
  return (
    <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden>
      <rect width="32" height="32" rx="8" fill="var(--accent)" />
      <g stroke="#1a1306" strokeWidth="1.6" strokeLinecap="round">
        <path d="M16 16 8.5 9M16 16l8-6M16 16l-6 8M16 16l8 7" />
      </g>
      <g fill="#1a1306">
        <circle cx="16" cy="16" r="3.2" />
        <circle cx="8.5" cy="9" r="2" />
        <circle cx="24" cy="10" r="2" />
        <circle cx="10" cy="24" r="2" />
        <circle cx="24" cy="23" r="2" />
      </g>
    </svg>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/"));

  const links = (
    <nav className="flex flex-col gap-6 px-3 py-4" aria-label="Main">
      {GROUPS.map((g) => (
        <div key={g.label}>
          <div className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-zinc-500">{g.label}</div>
          <ul className="flex flex-col gap-0.5">
            {g.items.map((it) => {
              const active = isActive(it.href);
              return (
                <li key={it.href}>
                  <Link
                    href={it.href}
                    onClick={() => setOpen(false)}
                    aria-current={active ? "page" : undefined}
                    className={`group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                      active ? "bg-accent-soft font-medium text-accent" : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-50"
                    }`}
                  >
                    {active && <span aria-hidden className="absolute -left-3 top-1.5 bottom-1.5 w-[3px] rounded-r bg-accent" />}
                    <span className={active ? "text-accent" : "text-zinc-500 transition-colors group-hover:text-signal"}>
                      <Icon name={it.icon} />
                    </span>
                    {it.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );

  const brand = (
    <Link href="/" className="flex items-center gap-3 px-5 py-5" onClick={() => setOpen(false)}>
      <Mark />
      <span className="leading-tight">
        <span className="block font-display text-[15px] font-semibold tracking-tight text-zinc-50" style={{ fontFamily: "var(--font-display)" }}>
          Spillover Studio
        </span>
        <span className="block text-[11px] text-zinc-500">Influencer–brand matching</span>
      </span>
    </Link>
  );

  return (
    <>
      {/* desktop: fixed rail */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-line bg-background/95 backdrop-blur lg:flex">
        {brand}
        <div className="flex-1 overflow-y-auto">{links}</div>
        <div className="border-t border-line px-5 py-4 text-[11px] leading-relaxed text-zinc-500">
          Capstone 011 · UE23CS441A
          <br />
          Real data, simulations labelled
        </div>
      </aside>

      {/* phone and tablet: top bar and a drawer */}
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-line bg-background/90 px-4 backdrop-blur lg:hidden">
        <Link href="/" className="flex items-center gap-2.5 py-3" onClick={() => setOpen(false)}>
          <Mark />
          <span className="text-sm font-semibold text-zinc-50" style={{ fontFamily: "var(--font-display)" }}>
            Spillover Studio
          </span>
        </Link>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label="Menu"
          className="rounded-md border border-line px-3 py-1.5 text-xs text-zinc-300 transition-colors hover:border-accent hover:text-accent"
        >
          {open ? "Close" : "Menu"}
        </button>
      </header>
      {open && (
        <div className="fixed inset-x-0 top-[57px] bottom-0 z-30 overflow-y-auto border-t border-line bg-background lg:hidden">{links}</div>
      )}
    </>
  );
}
