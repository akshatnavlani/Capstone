"use client";

import { useEffect, useState } from "react";
import { getAlerts, getCreators } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";
import type { AlertResponse } from "@/types";

// Names are resolved best-effort from GET /feature-store/creators. A creator_id
// with no match (deleted creator, stale test data, or the fetch failing) falls
// back to the raw id rather than blocking the alert from rendering.
function resolveName(id: string, namesById: Map<string, string>): string {
  return namesById.get(id) ?? id;
}

export default function MonitoringPage() {
  const [alerts, setAlerts] = useState<AlertResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [namesById, setNamesById] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    getAlerts()
      .then(setAlerts)
      .catch(() =>
        setError(
          "Couldn't reach the alerts API. Is the Track C backend running at " +
            (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000") +
            "?"
        )
      );
    getCreators()
      .then((creators) => setNamesById(new Map(creators.map((c) => [c.creator_id, c.name]))))
      .catch(() => {
        // Names are supplementary here; a failed fetch just leaves ids unresolved.
      });
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-6 py-16">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Monitoring &amp; Alerts</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Risk flags and sentiment alerts. Each alert shows what generated it
          (&quot;source&quot;) and, once the Temporal branch&apos;s sentiment
          propagation ships, which collaborator&apos;s controversy it
          propagated from.
        </p>
      </div>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {!error && alerts === null && (
        <p className="text-sm text-zinc-500">Loading…</p>
      )}

      {alerts !== null && alerts.length === 0 && (
        <p className="text-sm text-zinc-500">No alerts yet.</p>
      )}

      {alerts !== null && alerts.length > 0 && (
        <ul className="flex flex-col gap-3">
          {alerts.map((alert) => (
            <li key={alert.id} className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
              <div className="flex items-center justify-between">
                <SeverityBadge severity={alert.severity} />
                <span className="text-xs text-zinc-500">
                  {new Date(alert.created_at).toLocaleString()}
                </span>
              </div>
              <h2 className="mt-2 text-sm font-medium">creator: {resolveName(alert.creator_id, namesById)}</h2>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{alert.reason}</p>
              <p className="mt-1 text-xs text-zinc-500">source: {alert.source}</p>
              {alert.propagated_from_creator_id && (
                <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                  propagated from collaborator: {resolveName(alert.propagated_from_creator_id, namesById)}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
