import Link from "next/link";

export default function Home() {
  return (
    <main className="mx-auto flex max-w-5xl flex-1 flex-col items-start justify-center gap-6 px-6 py-24">
      <h1 className="text-3xl font-semibold tracking-tight">
        Influencer-Brand Matching
      </h1>
      <p className="max-w-xl text-zinc-600 dark:text-zinc-400">
        Score influencer recommendations by ROI and spillover effects for
        sponsorship decisions. Start by describing the brand&apos;s product
        and target audience.
      </p>
      <Link
        href="/brand-input"
        className="rounded-full bg-foreground px-5 py-3 text-sm font-medium text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc]"
      >
        Start a new brand request
      </Link>
    </main>
  );
}
