import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Btn, EmptyState, ErrorBanner, Panel, RowSkeleton, StatusPill } from "@/components/kit";
import { useAnomalies, useResolveAnomaly } from "@/lib/queries";
import { ApiError } from "@/lib/api";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/kingcey/anomalies")({
  head: () => ({
    meta: [
      { title: "Anomalies — AdsKinz admin" },
      { name: "description", content: "Traffic quality alerts flagged by AdsKinz fraud detection." },
      { property: "og:title", content: "Anomalies — AdsKinz admin" },
      { property: "og:description", content: "Investigate suspicious delivery patterns." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AnomaliesPage,
});

function AnomaliesPage() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useAnomalies();
  const resolve = useResolveAnomaly();
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const items = data ?? [];
  const open = items.filter((a) => !a.resolved);

  return (
    <AdminShell title={t("admin.nav.anomalies")} badges={{ anomalies: open.length }}>
      {isError && <ErrorBanner onRetry={refetch} />}
      {err && <p className="mb-3 text-sm font-semibold text-danger">{err}</p>}
      {isLoading ? (
        <Panel className="p-0"><RowSkeleton rows={5} /></Panel>
      ) : items.length === 0 ? (
        <Panel className="p-0"><EmptyState title="No anomalies detected" positive /></Panel>
      ) : (
        <Panel className="p-0">
          <ul className="divide-y divide-seam">
            {items.map((a) => (
              <li key={a.id} className="flex flex-wrap items-center gap-3 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{a.reason}</p>
                  <p className="num mt-1 text-xs text-paper-dim">
                    {a.kind} · {a.subject} · {a.detectedAt ?? "—"} · score {a.score}
                  </p>
                </div>
                <StatusPill status={a.resolved ? "approved" : "pending"} />
                {!a.resolved && (
                  <Btn
                    tone="bounty"
                    variant="secondary"
                    disabled={resolve.isPending && pendingId === a.id}
                    onClick={() => {
                      setErr(null);
                      setPendingId(a.id);
                      resolve.mutate(a.id, {
                        onError: (e) => setErr(e instanceof ApiError ? e.message : "Could not resolve."),
                        onSettled: () => setPendingId(null),
                      });
                    }}
                  >
                    {resolve.isPending && pendingId === a.id ? "Resolving…" : "Resolve"}
                  </Btn>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </AdminShell>
  );
}
