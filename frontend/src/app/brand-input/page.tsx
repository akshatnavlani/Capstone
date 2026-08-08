// Wireframe shell only — no state/validation/submit handler yet.
// Field shape documented in WIREFRAMES.md and src/types/index.ts (BrandInputRequest).
// Form wiring against mock data is a Weeks 5-6 objective, not Weeks 1-2.

export default function BrandInputPage() {
  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Brand Input</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Tell us about the product and target audience for this sponsorship.
        </p>
      </div>

      <div className="flex flex-col gap-6">
        <Field label="Product / Category" placeholder="e.g. Running shoes — fitness" />
        <Field label="Budget (INR)" placeholder="e.g. 200000" />
        <Field
          label="Target Region (proxy)"
          placeholder="e.g. bio/comment language, hashtags — no direct audience analytics"
        />
        <Field
          label="Target Demographic (proxy)"
          placeholder="e.g. posting-time/timezone and content-topic proxy"
        />

        <button
          disabled
          className="mt-2 w-fit rounded-full bg-foreground px-5 py-3 text-sm font-medium text-background opacity-50"
        >
          Get Recommendations
        </button>
      </div>
    </main>
  );
}

function Field({ label, placeholder }: { label: string; placeholder: string }) {
  return (
    <label className="flex flex-col gap-2 text-sm">
      <span className="font-medium">{label}</span>
      <input
        disabled
        placeholder={placeholder}
        className="rounded-md border border-zinc-300 bg-transparent px-3 py-2 text-sm placeholder:text-zinc-400 dark:border-zinc-700"
      />
    </label>
  );
}
