import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Panel } from "@/components/kit";
import { auditLog } from "@/lib/mock-data";

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
  component: () => {
    const { t } = useTranslation();
    return (
      <AdminShell title={t("admin.nav.audit")}>
        <Panel className="p-0">
          <ul className="divide-y divide-seam">
            {auditLog.map((a) => (
              <li key={a.id} className="flex flex-wrap gap-3 px-5 py-3 text-sm">
                <span className="num text-paper-dim">{a.at}</span>
                <span className="font-semibold">{a.actor}</span>
                <span>{a.action}</span>
                <span className="num ml-auto text-paper-dim">{a.target}</span>
              </li>
            ))}
          </ul>
        </Panel>
      </AdminShell>
    );
  },
});
