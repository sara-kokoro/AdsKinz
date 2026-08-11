import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { PubShell } from "@/components/workspaces";
import { Panel, SectionTitle } from "@/components/kit";
import { LanguageSelect, ThemeToggle } from "@/components/controls";

export const Route = createFileRoute("/partner/settings")({
  head: () => ({
    meta: [
      { title: "Settings — AdsKinz partner" },
      { name: "description", content: "Publisher account, payout language and appearance preferences." },
      { property: "og:title", content: "Settings — AdsKinz partner" },
      { property: "og:description", content: "Manage your publisher account preferences." },
    ],
  }),
  component: () => {
    const { t } = useTranslation();
    return (
      <PubShell title={t("pub.nav.settings")}>
        <Panel className="max-w-xl">
          <SectionTitle>{t("pub.nav.settings")}</SectionTitle>
          <div className="space-y-4">
            <div><p className="text-sm font-semibold">{t("common.language")}</p><div className="mt-2"><LanguageSelect /></div></div>
            <div><p className="text-sm font-semibold">{t("common.theme")}</p><div className="mt-2"><ThemeToggle /></div></div>
          </div>
        </Panel>
      </PubShell>
    );
  },
});
