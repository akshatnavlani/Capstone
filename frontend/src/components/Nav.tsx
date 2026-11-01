"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/brand-input", label: "Brand Input" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/passport", label: "Passport" },
  { href: "/monitoring", label: "Monitoring" },
  { href: "/explainability", label: "Explainability" },
  { href: "/analysis", label: "Analysis" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-30 border-b border-zinc-200 bg-background/80 backdrop-blur dark:border-zinc-800">
      <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-3">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span aria-hidden className="grid h-6 w-6 place-items-center rounded-md bg-accent text-[11px] font-bold text-background">IB</span>
          Influencer-Brand Matching
        </Link>
        <div className="flex flex-wrap gap-1 text-sm">
          {links.map((link) => {
            const active = pathname === link.href || pathname.startsWith(link.href + "/");
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-md px-2.5 py-1 transition-colors ${
                  active
                    ? "bg-accent-soft font-medium text-accent"
                    : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-950 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-50"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
