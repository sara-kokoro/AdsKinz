# AdsKinz — Audit complet des mocks frontend

> Statut : rapport de phase 1 — aucun code modifié.  
> Objectif : identifier chaque donnée factice, proposer le wiring API backend réel, et lister les types TypeScript manquants.

---

## Légende

- 🔴 Mock de données métier (doit être remplacé par un appel API)
- 🟡 Constante produit / UI (acceptable en l’état, mais à surveiller)
- 🟢 Déjà câblé sur l’API (pas de mock)
- ⚠️ Backend endpoint inexistant — à créer avant le wiring frontend

---

## 1. Fichiers globaux / partagés

### `adskinz-frontend/src/lib/mock-data.ts`
**Statut : 🔴 Mock legacy, fichier entièrement à supprimer.**

| Données mockées | Type | Endpoint backend attendu | Types TS manquants |
|-----------------|------|--------------------------|--------------------|
| `campaigns` | `Campaign[]` | `GET /advertiser/campaigns` | déjà dans `types.ts` |
| `adminCampaignQueue` | `QueueCampaign[]` | `GET /admin/queue/campaigns` | `QueueCampaign` local dans `kingcey.campaigns.tsx` |
| `channels` | `Channel[]` | `GET /publisher/channels` | déjà dans `types.ts` |
| `adminChannelQueue` | `QueueChannel[]` | `GET /admin/queue/channels` | `QueueChannel` local dans `kingcey.channels.tsx` |
| `miniApps` | `MiniApp[]` | `GET /publisher/mini-apps` | déjà dans `types.ts` |
| `adminMiniAppQueue` | `QueueMiniApp[]` | `GET /admin/queue/mini-apps` | `QueueMiniApp` local dans `kingcey.mini-apps.tsx` |
| `withdrawals` | `Withdrawal[]` | `GET /publisher/withdrawals` (admin via `/admin/queue/withdrawals`) | déjà dans `types.ts` |
| `platformUsers` | `PlatformUser[]` | ⚠️ aucun endpoint listing de comptes | `PlatformUser` à créer si on ajoute `/admin/accounts` |
| `deposits` | `Deposit[]` | `GET /billing/deposits` | déjà dans `types.ts` |
| `anomalies` | `Anomaly[]` | `GET /admin/anomalies` | déjà dans `types.ts` |
| `auditLog` | `AuditEntry[]` | `GET /admin/audit` | déjà dans `types.ts` |
| `advertiserSummary` | objet | `GET /advertiser/stats` | `AdvertiserStats` déjà défini |
| `publisherSummary` | objet | `GET /publisher/stats` | `PublisherStats` déjà défini |
| `financeSummary` | objet | `GET /admin/finances` | `Finances` déjà défini |
| `placementStats` / `statsFor` | `PlacementStats[]` | ⚠️ pas d’endpoint dédié aux stats par placement | `PlacementStats` à créer ou fusionner dans `/publisher/channels/:id/stats` |

**Action :** supprimer `mock-data.ts` ; aucun fichier actuel ne l’importe (`grep` confirmé).

### `adskinz-frontend/src/lib/constants.ts`
**Statut : 🟡 Constantes produit légitimes.**

| Données | Nature | Commentaire |
|---------|--------|-------------|
| `BUTTON_LABELS` | liste de CTA | vient alimenter le wizard campagne ; peut rester en dur ou être servie par `GET /advertiser/languages` si elle devient dynamique |
| `AD_LANGUAGES` | liste de langues | idem ; le backend a `SUPPORTED_TRANSLATION_LANGS` mais pas d’endpoint public de langues complètes |
| Types `CampaignStatus`, `ChannelStatus`, etc. | enums front | à garder, ils reflètent les contraintes DB (`app/core/enums.py`) |

### `adskinz-frontend/src/lib/i18n.ts`
**Statut : 🟡 Mock marketing / landing page.**

| Clé | Usage | Action |
|-----|-------|--------|
| `landing.mock.*` | illustration Telegram sur la landing | acceptable tant que c’est du copy marketing ; pas un appel API |
| `landing.stats.*` | chiffres marketing ($2.00 CPM, 12 langues, 3 formats) | soit laisser en dur, soit les servir depuis `/config` ou `/stats/public` si on veut du dynamique |

### `adskinz-frontend/src/components/kit.tsx`
**Statut : 🟡 Utilitaire de loading factice.**

- `useFakeLoad(ms = 700)` : retourne un état loading après un `setTimeout`. Utilisé pour les skeletons.  
  **Action :** remplacer par les états réels des hooks TanStack Query (`isLoading`) partout où il est utilisé.

---

## 2. Routes — état route par route

### Auth

| Fichier | Mock ? | Endpoint backend | Commentaire |
|---------|--------|------------------|-------------|
| `src/routes/login.tsx` | 🟢 | `POST /auth/login`, `POST /auth/register` | déjà câblé via `useAuth` |
| `src/routes/kingcey.index.tsx` | 🟢 | `POST /admin/auth/login`, `POST /admin/auth/totp` | déjà câblé via `useAuth` |

**Manque côté auth :**
- Gestion d’un **refresh token** (`refresh_token`) dans `AuthContext` ⚠️ backend n’a pas encore `/auth/refresh`.
- Intercepteur global 401 → refresh → logout.
- Vérification synchrone du token avant rendu des routes protégées (actuellement `useAuthGuard` redirige après le 1er rendu).

### Advertiser (`/traffic/*`)

| Fichier | Mock ? | Endpoint utilisé | Remarque |
|---------|--------|------------------|----------|
| `src/routes/traffic.index.tsx` | 🟢 | `GET /advertiser/stats`, `GET /advertiser/campaigns` | — |
| `src/routes/traffic.campaigns.index.tsx` | 🟢 | `GET /advertiser/campaigns` | — |
| `src/routes/traffic.campaigns.new.tsx` | 🟢 | `POST /advertiser/campaigns`, `POST /advertiser/creatives/generate` | — |
| `src/routes/traffic.campaigns.$id.tsx` | 🟢 | `GET /advertiser/campaigns/:id`, `GET /advertiser/campaigns/:id/translations`, `PATCH /advertiser/campaigns/:id` | — |
| `src/routes/traffic.deposits.tsx` | 🟢 | `GET /billing/deposit-address`, `GET /billing/deposits` | — |
| `src/routes/traffic.settings.tsx` | 🔴 | `defaultValue="ops@northline.xyz"` | doit lire `GET /auth/me` ; l’écran settings advertiseur est quasi vide |

### Publisher (`/partner/*`)

| Fichier | Mock ? | Endpoint utilisé | Remarque |
|---------|--------|------------------|----------|
| `src/routes/partner.index.tsx` | 🟢 | `GET /publisher/stats` | — |
| `src/routes/partner.channels.tsx` | 🟢 | `GET /publisher/channels`, `POST`, `PATCH`, `POST /start`, `GET /publisher/channels/bot-status` | — |
| `src/routes/partner.mini-apps.tsx` | 🟢 | `GET /publisher/mini-apps`, `POST`, `GET /publisher/mini-apps/:id/key` | — |
| `src/routes/partner.withdrawals.tsx` | 🟢 | `GET /publisher/withdrawals`, `POST /publisher/withdrawals` | — |
| `src/routes/partner.settings.tsx` | 🟢 | `GET /auth/me`, `PATCH /auth/me`, `POST /auth/password` | — |

### Admin (`/kingcey/*`)

| Fichier | Mock ? | Endpoint utilisé | Remarque |
|---------|--------|------------------|----------|
| `src/routes/kingcey.overview.tsx` | 🟢 | `GET /admin/overview` | — |
| `src/routes/kingcey.campaigns.tsx` | 🟢 | `GET /admin/queue/campaigns`, `POST /admin/queue/campaigns/:id/{approve,reject}` | — |
| `src/routes/kingcey.channels.tsx` | 🟢 | `GET /admin/queue/channels`, `POST /admin/queue/channels/:id/{approve,reject}` | — |
| `src/routes/kingcey.mini-apps.tsx` | 🟢 | `GET /admin/queue/mini-apps`, `POST /admin/queue/mini-apps/:id/{approve,reject}` | — |
| `src/routes/kingcey.withdrawals.tsx` | 🟢 | `GET /admin/queue/withdrawals`, `POST /admin/queue/withdrawals/:id/{approve,reject,mark-paid}` | — |
| `src/routes/kingcey.users.tsx` | 🟢 partiel | `GET /admin/overview`, `GET /admin/finances`, `POST /admin/accounts/:role/:id/block` | Pas de vrai listing utilisateur (choix métier documenté) |
| `src/routes/kingcey.finances.tsx` | 🟢 | `GET /admin/finances` | — |
| `src/routes/kingcey.anomalies.tsx` | 🟢 | `GET /admin/anomalies`, `POST /admin/anomalies/:id/resolve` | — |
| `src/routes/kingcey.audit.tsx` | 🟢 | `GET /admin/audit` | — |
| `src/routes/kingcey.disputes.tsx` | 🔴 | à vérifier | pas encore lu |

### Landing / docs

| Fichier | Mock ? | Action |
|---------|--------|--------|
| `src/routes/index.tsx` | 🟡 | `stats` et `formats` sont du copy marketing ; laisser ou servir via un endpoint public |
| `src/routes/docs.*.tsx` | 🟡 | contenus statiques de documentation ; acceptable |

---

## 3. Types TypeScript manquants / à clarifier

1. **`QueueCampaign`, `QueueChannel`, `QueueMiniApp`, `QueueWithdrawal`** : définis localement dans chaque route admin. À centraliser dans `src/lib/types.ts` pour correspondre exactement aux schémas backend (`app/schemas/admin.py`).
2. **`PlatformUser`** : n’existe que dans `mock-data.ts` ; inutile tant qu’il n’y a pas d’endpoint `/admin/accounts`.
3. **`PlacementStats`** : n’existe que dans `mock-data.ts` ; à créer si on ajoute un endpoint `/publisher/placements/:id/stats`.
4. **Tokens** : ajouter `refresh_token: string` dans `TokenResponse` (et éventuellement `AdminSessionResponse`).
5. **`TokenRefreshResponse`** : `{ access_token: string; refresh_token?: string; expires_in: number }`.

---

## 4. Checklist des fichiers à modifier dans les prochaines sessions

### Phase A — Nettoyage des mocks legacy
- [ ] Supprimer `adskinz-frontend/src/lib/mock-data.ts`
- [ ] Vérifier qu’aucun import n’est cassé (`npm run build`)

### Phase B — Auth robuste (access + refresh)
Backend :
- [ ] Ajouter `REFRESH_TOKEN_TTL_DAYS` dans `app/config.py`
- [ ] Ajouter `create_refresh_token()` et `decode_refresh_token()` dans `app/core/security.py`
- [ ] Ajouter `POST /auth/refresh` dans `app/routers/auth.py`
- [ ] Retourner `refresh_token` dans `TokenResponse` et `AdminSessionResponse`
- [ ] Ajouter `RefreshTokenRequest` / `TokenRefreshResponse` dans `app/schemas/auth.py`
- [ ] Protéger `/auth/refresh` contre la réutilisation (stockage en DB ou Redis deny-list)

Frontend :
- [ ] Renommer `VITE_API_BASE` → `VITE_API_URL` ou supporter les deux dans `src/lib/api.ts`
- [ ] Stocker `refresh_token` en plus de `access_token`
- [ ] Implémenter l’intercepteur 401 : silence → `/auth/refresh` → logout si échec
- [ ] Ajouter `useVerifyToken()` ou vérification synchrone dans `AuthProvider`
- [ ] Renforcer `useAuthGuard` pour éviter le flash de route protégée
- [ ] Ajouter `TokenRefreshResponse` dans `src/lib/types.ts`

### Phase C — Mock restant settings advertiser
- [ ] Câbler `src/routes/traffic.settings.tsx` sur `useMe()` / `useUpdateProfile()` / `useChangePassword()` comme `partner.settings.tsx`
- [ ] Supprimer `defaultValue="ops@northline.xyz"`

### Phase D — Sweep BEP20 (backend)
- [ ] Ajouter `ACCOUNT_XPRV`, `BSC_GAS_WALLET_PRIVATE_KEY`, `BSC_TREASURY_ADDRESS` dans `app/config.py`
- [ ] Créer `app/services/bep20_sweep_service.py` avec web3 (dérivation HD privée, envoi BNB, envoi USDT)
- [ ] Ajouter le modèle `Bep20Sweep` dans `app/models/finance.py`
- [ ] Brancher le sweep dans `app/jobs/deposits.py` après `billing_service.credit_deposit()` pour les dépôts `bnb`
- [ ] Ajouter endpoint(s) admin de monitoring `/admin/sweeps` (optionnel)
- [ ] Mettre à jour `.env.example`

### Phase E — Qualité
- [ ] `npm run lint` / `npm run build` dans `adskinz-frontend`
- [ ] `pytest` + `ruff check` dans `adskinz-backend`

---

## 5. Résumé exécutif

- **La grande majorité du frontend est déjà câblée sur le backend FastAPI.** Le fichier `mock-data.ts` est un vestige non importé.
- **Le seul mock métier actif** est l’email par défaut dans `src/routes/traffic.settings.tsx`.
- **L’auth frontend fonctionne mais est minimaliste** : pas de refresh token, pas d’intercepteur 401, et les routes protégées peuvent flasher avant la redirection.
- **Le backend n’a pas encore `/auth/refresh`** : il faut le créer pour honorer la spec JWT demandée.
- **Le sweep BEP20 nécessite une nouvelle branche de code backend** car l’architecture actuelle est volontairement *watch-only*.
