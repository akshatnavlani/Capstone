"use client";

import { useEffect, useState } from "react";
import { getAlerts } from "@/lib/api";
import SeverityBadge from "@/components/SeverityBadge";
import type { AlertResponse } from "@/types";

export default function MonitoringPage() {
  const [alerts, setAlerts] = useState<AlertResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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
              <h2 className="mt-2 text-sm font-medium">creator: {alert.creator_id}</h2>
              <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">{alert.reason}</p>
              <p className="mt-1 text-xs text-zinc-500">source: {alert.source}</p>
              {alert.propagated_from_creator_id && (
                <p className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                  propagated from collaborator: {alert.propagated_from_creator_id}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
