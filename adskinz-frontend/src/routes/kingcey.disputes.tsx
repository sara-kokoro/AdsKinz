import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { EmptyState, Panel } from "@/components/kit";

export const Route = createFileRoute("/kingcey/disputes")({
  head: () => ({
    meta: [
      { title: "Disputes — AdsKinz admin" },
      { name: "description", content: "Advertiser and publisher disputes awaiting an operator decision." },
      { property: "og:title", content: "Disputes — AdsKinz admin" },
      { property: "og:description", content: "Resolve delivery and billing disputes." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: () => {
    const { t } = useTranslation();
    return (
      <AdminShell title={t("admin.nav.disputes")}>
        <Panel className="p-0"><EmptyState title={t("admin.disputesEmpty")} /></Panel>
      </AdminShell>
    );
  },
});
