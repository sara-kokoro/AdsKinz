# AdsKinz — backend API

## Présentation

AdsKinz est le backend FastAPI de la plateforme publicitaire Telegram et Mini Apps.
Il gère les comptes annonceurs et éditeurs, les campagnes, la modération, le suivi
des impressions et clics, les dépôts USDT et les retraits. La cible de production
est Python 3.12 dans un conteneur Docker unique sur Koyeb.

## Stack

- Python 3.12, FastAPI, Uvicorn et Gunicorn ;
- SQLAlchemy asynchrone, asyncpg, PostgreSQL/Neon et Alembic ;
- Redis pour le cache, les verrous distribués, les limites de débit et le buffer de dépense ;
- aiogram et Kurigram pour Telegram/MTProto ;
- bip-utils, TronGrid, BscScan et TonCenter pour les intégrations blockchain ;
- APScheduler pour les tâches planifiées.

## Arborescence

```text
app/
  config.py           Configuration Pydantic, uniquement via l'environnement
  database.py         Moteur SQLAlchemy asynchrone et sessions
  models/             Modèles SQLAlchemy et schéma PostgreSQL
  routers/            Routes FastAPI
  services/           Règles métier et intégrations
  jobs/               Tâches APScheduler
  bot/                Bot Telegram
  mtproto/            Client MTProto
alembic/              Migrations de base de données
scripts/              Outils manuels, exclus de l'image Docker
```

## Variables d'environnement

Copier le modèle, puis remplir chaque valeur localement :

```bash
cp .env.example .env
```

Les variables sont regroupées dans `.env.example` : exécution et URLs publiques,
PostgreSQL, Redis, JWT/TOTP et limites de débit, Telegram/MTProto, Groq, wallets et
prestataires blockchain, SMTP, règles métier et intervalles des tâches. En
production, les mêmes clés sont configurées comme secrets Koyeb ; `.env` ne doit
jamais être commité.

Pour Compose local, utiliser notamment :

```dotenv
DATABASE_URL=postgresql+asyncpg://adskinz:adskinz@db:5432/adskinz
REDIS_URL=redis://redis:6379/0
```

## Lancement local (Docker Compose)

```bash
docker compose up --build
docker compose exec api alembic upgrade head
```

L'API est alors disponible sur `http://localhost:8000`. Le volume `./app:/app/app`
active le rechargement Uvicorn pour le développement. Compose est strictement
réservé au développement local.

## Migrations Alembic

La migration initiale `0001_initial_schema` contient les 22 tables, leurs
contraintes et indexes, ainsi que la séquence `hd_wallet_index_seq`.

```bash
# Appliquer toutes les migrations
alembic upgrade head

# Vérifier la révision courante
alembic current

# Générer une migration après une modification volontaire des modèles
alembic revision --autogenerate -m "description_courte"
```

Toujours examiner une migration générée avant de l'appliquer. Alembic récupère
`DATABASE_URL` depuis la configuration applicative, sans URL codée dans
`alembic.ini`.

## Déploiement Koyeb

1. Créer un service Koyeb depuis ce dépôt avec le `Dockerfile`.
2. Définir toutes les variables nécessaires dans les secrets Koyeb, en particulier
   `DATABASE_URL` Neon, `REDIS_URL`, `JWT_SECRET`, `IP_HASH_SALT` et les clés des
   prestataires effectivement activés.
3. Exécuter `alembic upgrade head` dans une étape de déploiement contrôlée avant la
   mise en service de la nouvelle version.
4. Koyeb exécute un **seul conteneur** applicatif ; PostgreSQL est fourni par Neon.
   Ne pas déployer `docker-compose.yml`, PostgreSQL local, Redis local ni `scripts/`.
5. Vérifier `GET /health` après le déploiement.

## Liste des endpoints

Les routes sont documentées par OpenAPI dès que l'application est lancée
(`GET /docs` et `GET /openapi.json`). La surface fonctionnelle attendue est :

- `GET /health` ;
- authentification : inscription, connexion, profil, changement de mot de passe,
  connexion administrateur et validation TOTP ;
- annonceur : statistiques, création/lecture/mise à jour des campagnes, génération
  de texte et consultation des traductions ;
- facturation : solde, adresse de dépôt, historique des dépôts et grand livre ;
- éditeur : chaînes Telegram, Mini Apps, clé Kinz-ID, statut du bot, statistiques et
  demandes de retrait ;
- SDK : sélection et diffusion d'une création pour une Mini App ;
- tracking : redirection par identifiant de suivi ;
- administration : files de modération, décisions, retraits, finances, anomalies,
  audit et blocage de compte.

Consulter `/openapi.json` pour les chemins HTTP et les modèles exacts de la version
déployée : les routeurs sont maintenus séparément de cette infrastructure.

## Les 9 crons

APScheduler planifie les neuf traitements suivants, aux intervalles configurables
dans les variables `JOB_*` :

1. suppression des posts Telegram expirés (`JOB_AUTO_DELETE_MINUTES`, 5 min) ;
2. lecture des vues via MTProto (`JOB_VIEWS_POLLING_MINUTES`, 15 min) ;
3. surveillance des dépôts (`JOB_DEPOSIT_WATCHER_MINUTES`, 2 min) ;
4. expiration des fenêtres de confiance des chaînes (`JOB_TRUST_EXPIRY_MINUTES`, 60 min) ;
5. vérification quotidienne des droits administrateur du bot (`JOB_BOT_ADMIN_CHECK_HOURS`, 24 h) ;
6. alerte de faible solde (`JOB_LOW_BALANCE_MINUTES`, 60 min) ;
7. allocation des budgets (`JOB_BUDGET_ALLOCATION_MINUTES`, 10 min) ;
8. envoi des posts planifiés (`JOB_POST_DISPATCH_MINUTES`, 5 min) ;
9. flush du buffer Redis des dépenses (`JOB_SPEND_FLUSH_MINUTES`, 1 min).

## Sécurité

- La seed/mnemonic n'est **jamais** stockée par le backend. Le service emploie des
  XPUB en lecture seule pour les adresses de dépôt.
- Aucun sweep automatique n'existe. `scripts/sweep.py` est un outil local,
  interactif, exclu du conteneur et exige une confirmation textuelle pour chaque
  transaction.
- La session string MTProto est générée manuellement, une seule fois, en local ;
  elle est ensuite placée comme secret et n'est jamais générée en production.
- PayPal n'est jamais proposé ni intégré.
- Aucune fausse donnée de démonstration ne doit être ajoutée aux environnements
  réels, aux migrations ou aux réponses API.
