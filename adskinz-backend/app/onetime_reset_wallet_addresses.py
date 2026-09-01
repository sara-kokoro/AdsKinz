"""Reinitialise l'adresse de depot de TOUS les annonceurs pour un reseau donne.

Supprime toutes les lignes WalletAddress existantes pour ce reseau, afin que
get_or_create_address en re-derive une nouvelle pour chacun, avec le
XPUB_BEP20 / XPUB_TRC20 / TON_DEPOSIT_ADDRESS actuellement configure.

ATTENTION - IRREVERSIBLE:
- Toute adresse deja communiquee a un annonceur (memorisee, copiee, ou avec
  des fonds deja envoyes/en attente) devient invalide et n'est plus liee a
  aucun compte apres ce script.
- N'utilise ce script que si tu es certain qu'aucun annonceur (meme un
  autre compte de test que celui dont tu parles) n'a de fonds en jeu sur
  son adresse actuelle.
- Ne touche a aucune cle privee ni aucun fonds: il supprime uniquement les
  lignes de cache d'adresses. Les Deposits et Bep20Sweep/Trc20Sweep deja
  enregistres restent intacts (historique conserve).

Usage (dry-run, liste ce qui serait supprime, ne modifie rien):
    python -m scripts.reset_all_wallet_addresses --network bnb

Usage (applique la suppression):
    python -m scripts.reset_all_wallet_addresses --network bnb --yes

Reseau "all" pour toucher ton, trc20 et bnb en une fois:
    python -m scripts.reset_all_wallet_addresses --network all --yes
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.database import SessionLocal
from app.models.accounts import Advertiser
from app.models.finance import WalletAddress

ALL_NETWORKS = ["ton", "trc20", "bnb"]


async def reset_all(network: str, confirmed: bool) -> None:
    networks = ALL_NETWORKS if network == "all" else [network]

    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(WalletAddress, Advertiser.email)
                .join(Advertiser, Advertiser.id == WalletAddress.advertiser_id)
                .where(WalletAddress.network.in_(networks))
            )
        ).all()

        if not rows:
            print(f"Aucune adresse en cache pour {networks}. Rien a faire.")
            return

        print(f"{len(rows)} adresse(s) en cache pour {networks}:\n")
        for wallet, email in rows:
            print(f"  {email:35s} {wallet.network:6s} {wallet.address}")

        if not confirmed:
            print("\nDry-run: rien n'a ete supprime.")
            print("Relance avec --yes pour confirmer la suppression de TOUTES ces lignes.")
            return

        for wallet, _email in rows:
            await session.delete(wallet)
        await session.commit()

        print(f"\n{len(rows)} ligne(s) supprimee(s). Chaque annonceur recevra une nouvelle "
              f"adresse (derivee de la config actuelle) a sa prochaine visite sur Depots.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", required=True, choices=["ton", "trc20", "bnb", "all"])
    parser.add_argument("--yes", action="store_true", help="Confirme la suppression")
    args = parser.parse_args()
    asyncio.run(reset_all(args.network, args.yes))


if __name__ == "__main__":
    main()
