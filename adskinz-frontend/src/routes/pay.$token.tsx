/**
 * AdsKinz — Page de dépôt relayé pour JessiKaPay
 * ====================================================
 * Route publique (aucune auth adskinz) : l'utilisateur y arrive depuis
 * la mini app Telegram JessiKaPay. Le {token} porte toutes les infos du
 * dépôt, signées côté JessiKaPay — cette page ne fait qu'appeler le
 * backend adskinz pour lancer le paiement MoneyFusion et suivre son statut.
 *
 * Ne PAS confondre avec un flux adskinz natif : cette page ne touche à
 * aucun compte annonceur/éditeur, elle ne fait que relayer.
 */
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";

export const Route = createFileRoute("/pay/$token")({
  component: RelayPaymentPage,
});

type RelayState =
  | { phase: "init" }
  | { phase: "redirecting" }
  | { phase: "polling"; amount: number }
  | { phase: "success"; amount: number }
  | { phase: "failed"; message: string };

const POLL_INTERVAL_MS = 3000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes — au-delà, on affiche un message d'attente

function RelayPaymentPage() {
  const { token } = Route.useParams();
  const [state, setState] = useState<RelayState>({ phase: "init" });
  const pollStarted = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    async function start() {
      try {
        const res = await apiFetch<{
          status: string;
          payment_url?: string;
          already_initiated: boolean;
        }>(`/pay/${token}/init`, { method: "POST", auth: false });

        if (cancelled) return;

        if (res.status === "success" || res.status === "failed") {
          // Déjà résolu (rafraîchissement de page tardif)
          setState(
            res.status === "success"
              ? { phase: "success", amount: 0 }
              : { phase: "failed", message: "Ce dépôt a échoué." }
          );
          return;
        }

        if (res.payment_url) {
          setState({ phase: "redirecting" });
          window.location.href = res.payment_url;
          return;
        }

        // already_initiated sans payment_url : on passe direct au polling
        pollStarted.current = Date.now();
        setState({ phase: "polling", amount: 0 });
        poll();
      } catch (e: any) {
        if (!cancelled) {
          setState({ phase: "failed", message: e?.message || "Impossible d'initier le dépôt." });
        }
      }
    }

    async function poll() {
      if (cancelled) return;
      try {
        const res = await apiFetch<{ status: string; amount: number }>(
          `/pay/${token}/status`,
          { auth: false }
        );
        if (cancelled) return;

        if (res.status === "success") {
          setState({ phase: "success", amount: res.amount });
          return;
        }
        if (res.status === "failed") {
          setState({ phase: "failed", message: "Le paiement a échoué ou a été annulé." });
          return;
        }

        const elapsed = Date.now() - (pollStarted.current || Date.now());
        if (elapsed > POLL_TIMEOUT_MS) {
          setState({
            phase: "failed",
            message: "Le paiement prend plus de temps que prévu. Vérifie ton historique sur JessiKaPay dans quelques minutes.",
          });
          return;
        }
        pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch {
        pollTimer = setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    start();
    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm text-center">
        {state.phase === "init" && <p>Initialisation du dépôt…</p>}
        {state.phase === "redirecting" && <p>Redirection vers ton opérateur mobile money…</p>}
        {state.phase === "polling" && <p>Paiement en cours de vérification…</p>}
        {state.phase === "success" && (
          <div>
            <p className="text-lg font-semibold">Dépôt réussi ✅</p>
            <p className="mt-2 text-sm opacity-80">Retourne sur JessiKaPay, ton solde est déjà mis à jour.</p>
          </div>
        )}
        {state.phase === "failed" && (
          <div>
            <p className="text-lg font-semibold">Dépôt non abouti</p>
            <p className="mt-2 text-sm opacity-80">{state.message}</p>
          </div>
        )}
      </div>
    </div>
  );
}
