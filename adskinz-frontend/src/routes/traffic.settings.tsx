import { createFileRoute } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { Panel, SectionTitle } from "@/components/kit";
import { LanguageSelect, ThemeToggle } from "@/components/controls";

export const Route = createFileRoute("/traffic/settings")({
  head: () => ({
    meta: [
      { title: "Settings — AdsKinz traffic" },
      { name: "description", content: "Account, language and appearance settings for your AdsKinz advertiser workspace." },
      { property: "og:title", content: "Settings — AdsKinz traffic" },
      { property: "og:description", content: "Manage your advertiser account preferences." },
    ],
  }),
  component: () => {
    const { t } = useTranslation();
    return (
      <AdvShell title={t("adv.nav.settings")}>
        <Panel className="max-w-xl">
          <SectionTitle>{t("adv.nav.settings")}</SectionTitle>
          <div className="space-y-4">
            <div>
              <p className="text-sm font-semibold">{t("common.language")}</p>
              <div className="mt-2"><LanguageSelect /></div>
            </div>
            <div>
              <p className="text-sm font-semibold">{t("common.theme")}</p>
              <div className="mt-2"><ThemeToggle /></div>
            </div>
            <div>
              <label className="text-sm font-semibold" htmlFor="em">{t("admin.email")}</label>
              <input id="em" className="mt-2 w-full rounded-xl border border-seam bg-transparent p-3 text-sm" defaultValue="ops@northline.xyz" />
            </div>
          </div>
        </Panel>
      </AdvShell>
    );
  },
});
