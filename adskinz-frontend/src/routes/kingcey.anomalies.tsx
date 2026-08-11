import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Panel } from "@/components/kit";
import { anomalies } from "@/lib/mock-data";

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
  component: () => {
    const { t } = useTranslation();
    return (
      <AdminShell title={t("admin.nav.anomalies")} badges={{ anomalies: anomalies.length }}>
        <Panel className="p-0">
          <ul className="divide-y divide-seam">
            {anomalies.map((a) => (
              <li key={a.id} className="px-5 py-4">
                <p className="font-semibold">{a.reason}</p>
                <p className="num mt-1 text-xs text-paper-dim">{a.subject} · {a.detectedAt} · {a.score}</p>
              </li>
            ))}
          </ul>
        </Panel>
      </AdminShell>
    );
  },
});
