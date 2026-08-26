import type { AlertSeverity } from "@/types";

const styles: Record<AlertSeverity, string> = {
  low: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  high: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export default function SeverityBadge({ severity }: { severity: AlertSeverity }) {
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${styles[severity]}`}>
      {severity} severity
    </span>
  );
}
