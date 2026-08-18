import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AdvShell } from "@/components/workspaces";
import { Btn, ErrorBanner, Field, FieldError, Panel, SectionTitle, inputCls } from "@/components/kit";
import { LanguageSelect, ThemeToggle } from "@/components/controls";
import { ApiError } from "@/lib/api";
import { useAuth, useAuthGuard } from "@/lib/auth";
import { useChangePassword, useMe, useUpdateProfile } from "@/lib/queries";

export const Route = createFileRoute("/traffic/settings")({
  head: () => ({
    meta: [
      { title: "Settings — AdsKinz traffic" },
      { name: "description", content: "Account, language and appearance settings for your AdsKinz advertiser workspace." },
      { property: "og:title", content: "Settings — AdsKinz traffic" },
      { property: "og:description", content: "Manage your advertiser account preferences." },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  useAuthGuard("advertiser");
  const { t } = useTranslation();
  const { logout } = useAuth();
  const { data: me, isLoading, isError, refetch } = useMe();
  const updateProfile = useUpdateProfile();
  const changePassword = useChangePassword();

  const [displayName, setDisplayName] = useState("");
  const [telegramUsername, setTelegramUsername] = useState("");
  const [country, setCountry] = useState("");
  const [profileMsg, setProfileMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    if (me) {
      setDisplayName(me.display_name ?? "");
      setTelegramUsername(me.telegram_username ?? "");
      setCountry(me.country ?? "");
    }
  }, [me]);

  const saveProfile = () => {
    setProfileMsg(null);
    updateProfile.mutate(
      { display_name: displayName || undefined, telegram_username: telegramUsername || undefined, country: country || undefined },
      {
        onSuccess: () => setProfileMsg({ ok: true, text: "Profile updated." }),
        onError: (err) => setProfileMsg({ ok: false, text: err instanceof ApiError ? err.message : "Update failed." }),
      },
    );
  };

  const savePassword = () => {
    setPwMsg(null);
    if (newPassword.length < 8) {
      setPwMsg({ ok: false, text: "New password must be at least 8 characters." });
      return;
    }
    changePassword.mutate(
      { current_password: currentPassword, new_password: newPassword },
      {
        onSuccess: () => {
          setPwMsg({ ok: true, text: "Password changed." });
          setCurrentPassword("");
          setNewPassword("");
        },
        onError: (err) => setPwMsg({ ok: false, text: err instanceof ApiError ? err.message : "Change failed." }),
      },
    );
  };

  return (
    <AdvShell title={t("adv.nav.settings")}>
      <div className="space-y-5">
        {isError && <ErrorBanner onRetry={() => void refetch()} />}

        <Panel className="max-w-xl">
          <SectionTitle>Account</SectionTitle>
          {isLoading ? (
            <div className="h-24 animate-pulse rounded-md bg-panel-2" />
          ) : (
            <div className="space-y-4">
              <p className="num text-sm text-paper-dim">{me?.email}</p>
              {profileMsg && (
                <p className={`text-xs font-semibold ${profileMsg.ok ? "text-success" : "text-danger"}`}>{profileMsg.text}</p>
              )}
              <Field label="Display name" htmlFor="dn">
                <input id="dn" value={displayName} onChange={(e) => setDisplayName(e.target.value)} className={inputCls()} />
              </Field>
              <Field label="Telegram username" htmlFor="tu">
                <input id="tu" value={telegramUsername} onChange={(e) => setTelegramUsername(e.target.value)} placeholder="@username" className={inputCls()} />
              </Field>
              <Field label="Country" htmlFor="co">
                <input id="co" value={country} onChange={(e) => setCountry(e.target.value)} className={inputCls()} />
              </Field>
              <Btn tone="bounty" onClick={saveProfile} disabled={updateProfile.isPending}>
                {updateProfile.isPending ? "…" : t("common.save")}
              </Btn>
            </div>
          )}
        </Panel>

        <Panel className="max-w-xl">
          <SectionTitle>Change password</SectionTitle>
          <div className="space-y-4">
            {pwMsg && <p className={`text-xs font-semibold ${pwMsg.ok ? "text-success" : "text-danger"}`}>{pwMsg.text}</p>}
            <Field label="Current password" htmlFor="cp">
              <input id="cp" type="password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} className={inputCls()} />
            </Field>
            <Field label="New password" hint="Minimum 8 characters" htmlFor="np">
              <input id="np" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} className={inputCls()} />
            </Field>
            <FieldError />
            <Btn tone="bounty" onClick={savePassword} disabled={changePassword.isPending}>
              {changePassword.isPending ? "…" : t("common.save")}
            </Btn>
          </div>
        </Panel>

        <Panel className="max-w-xl">
          <SectionTitle>{t("adv.nav.settings")}</SectionTitle>
          <div className="space-y-4">
            <div><p className="text-sm font-semibold">{t("common.language")}</p><div className="mt-2"><LanguageSelect /></div></div>
            <div><p className="text-sm font-semibold">{t("common.theme")}</p><div className="mt-2"><ThemeToggle /></div></div>
          </div>
        </Panel>

        <Panel className="max-w-xl">
          <Btn variant="secondary" tone="danger" onClick={logout}>Sign out</Btn>
        </Panel>
      </div>
    </AdvShell>
  );
}
