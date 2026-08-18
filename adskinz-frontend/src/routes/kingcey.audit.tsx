import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { EmptyState, ErrorBanner, Panel, RowSkeleton } from "@/components/kit";
import { useAudit } from "@/lib/queries";
import { useAuthGuard } from "@/lib/auth";

export const Route = createFileRoute("/kingcey/audit")({
  head: () => ({
    meta: [
      { title: "Audit log — AdsKinz admin" },
      { name: "description", content: "Every moderation and finance action taken by AdsKinz operators." },
      { property: "og:title", content: "Audit log — AdsKinz admin" },
      { property: "og:description", content: "Traceable operator activity." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: AuditPage,
});

function AuditPage() {
  useAuthGuard("admin");
  const { t } = useTranslation();
  const { data, isLoading, isError, refetch } = useAudit();
  const items = data ?? [];

  return (
    <AdminShell title={t("admin.nav.audit")}>
      {isError && <ErrorBanner onRetry={refetch} />}
      {isLoading ? (
        <Panel className="p-0"><RowSkeleton rows={6} /></Panel>
      ) : items.length === 0 ? (
        <Panel className="p-0"><EmptyState title="No audit entries yet" /></Panel>
      ) : (
        <Panel className="p-0">
          <ul className="divide-y divide-seam">
            {items.map((a) => (
              <li key={a.id} className="flex flex-wrap gap-3 px-5 py-3 text-sm">
                <span className="num text-paper-dim">{a.createdAt ?? "—"}</span>
                <span className="font-semibold">{a.actor}</span>
                <span>{a.action}</span>
                <span className="num ml-auto text-paper-dim">{a.target ?? a.targetId ?? ""}</span>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </AdminShell>
  );
}
