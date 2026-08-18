import { createFileRoute, Link } from "@tanstack/react-router";
import { useTranslation } from "react-i18next";
import { AdminShell } from "@/components/workspaces";
import { Btn, Panel, Quote, SectionTitle } from "@/components/kit";

export const Route = createFileRoute("/kingcey/disputes")({
  head: () => ({
    meta: [
      { title: "Disputes — AdsKinz admin" },
      { name: "description", content: "Advertiser and publisher disputes are handled manually via anomalies and the audit trail." },
      { property: "og:title", content: "Disputes — AdsKinz admin" },
      { property: "og:description", content: "How AdsKinz operators resolve delivery and billing disputes today." },
      { name: "robots", content: "noindex" },
    ],
  }),
  component: DisputesPage,
});

function DisputesPage() {
  const { t } = useTranslation();
  return (
    <AdminShell title={t("admin.nav.disputes")}>
      <div className="space-y-5">
        <Quote tone="bounty" label="No dedicated endpoint">
          The AdsKinz API has no disputes queue. Billing and delivery disagreements are surfaced instead through
          fraud anomalies and the operator audit log — use those tools to investigate and act.
        </Quote>
        <Panel>
          <SectionTitle sub="Suggested manual process for advertiser/publisher disputes.">
            How to resolve a dispute
          </SectionTitle>
          <ol className="list-decimal space-y-2 pl-5 text-sm text-paper-dim">
            <li>Check the Anomalies queue for automatically flagged traffic tied to the campaign or channel in question.</li>
            <li>Review the Audit log for every moderation and payout action already taken on the account.</li>
            <li>Contact the advertiser/publisher directly, then record the outcome (approve, reject, block) using the relevant queue or the Users page.</li>
          </ol>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link to="/kingcey/anomalies"><Btn variant="secondary">{t("admin.nav.anomalies")}</Btn></Link>
            <Link to="/kingcey/audit"><Btn variant="secondary">{t("admin.nav.audit")}</Btn></Link>
            <Link to="/kingcey/users"><Btn variant="secondary">{t("x.admin.users")}</Btn></Link>
          </div>
        </Panel>
      </div>
    </AdminShell>
  );
}
