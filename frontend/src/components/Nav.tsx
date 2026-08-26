import Link from "next/link";

const links = [
  { href: "/brand-input", label: "Brand Input" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/monitoring", label: "Monitoring" },
  { href: "/explainability", label: "Explainability" },
];

export default function Nav() {
  return (
    <header className="border-b border-zinc-200 dark:border-zinc-800">
      <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
        <Link href="/" className="font-semibold">
          Influencer-Brand Matching
        </Link>
        <div className="flex gap-4 text-sm text-zinc-600 dark:text-zinc-400">
          {links.map((link) => (
            <Link key={link.href} href={link.href} className="hover:text-zinc-950 dark:hover:text-zinc-50">
              {link.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  );
}
