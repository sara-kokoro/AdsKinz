"""Generate a brand-new BIP-39 mnemonic and derive account-level xprv/xpub
for TRC20 (TRON) and BEP20 (BNB Smart Chain).

RUN THIS LOCALLY, OFFLINE. Never on a server, never in a cloud sandbox,
never on a machine you don't fully control. Disconnect from the internet
before running it if you can.

Install once:
    pip install bip-utils

Usage:
    python3 generate_hd_wallet.py
"""

from bip_utils import (
    Bip39MnemonicGenerator,
    Bip39SeedGenerator,
    Bip39WordsNum,
    Bip44,
    Bip44Coins,
    Bip44Changes,
)

WORDS = Bip39WordsNum.WORDS_NUM_24


def account_keys(seed_bytes: bytes, coin: Bip44Coins, label: str) -> None:
    acct = Bip44.FromSeed(seed_bytes, coin).Purpose().Coin().Account(0)
    xprv = acct.PrivateKey().ToExtended()
    xpub = acct.PublicKey().ToExtended()
    first_address = (
        acct.Change(Bip44Changes.CHAIN_EXT).AddressIndex(0).PublicKey().ToAddress()
    )

    print(f"\n=== {label} ===")
    print(f"Account XPRV (put in ACCOUNT_XPRV{'' if label == 'BEP20 / BNB Smart Chain' else '_TRC20'} on Koyeb — NEVER commit, NEVER log):")
    print(f"  {xprv}")
    print(f"Account XPUB (put in XPUB_{'BEP20' if label == 'BEP20 / BNB Smart Chain' else 'TRC20'} on Koyeb — safe to store server-side, watch-only):")
    print(f"  {xpub}")
    print(f"Sanity check — derived address at index 0:")
    print(f"  {first_address}")


def main() -> None:
    mnemonic = Bip39MnemonicGenerator().FromWordsNumber(WORDS)
    print("=" * 70)
    print("NEW MNEMONIC — write this on paper NOW, in a safe place.")
    print("Do not screenshot it. Do not paste it anywhere. Do not save it")
    print("to a file, note app, password manager clipboard history, or")
    print("send it to anyone — including in this chat.")
    print("=" * 70)
    print(f"\n{mnemonic}\n")

    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()

    account_keys(seed_bytes, Bip44Coins.TRON, "TRC20 / TRON")
    account_keys(seed_bytes, Bip44Coins.BINANCE_SMART_CHAIN, "BEP20 / BNB Smart Chain")

    print("\n" + "=" * 70)
    print("Next steps:")
    print("1. Write the mnemonic on paper (or two copies, stored separately).")
    print("2. Set XPUB_TRC20 and XPUB_BEP20 on Koyeb to the two XPUB values above.")
    print("3. Set ACCOUNT_XPRV_TRC20 and ACCOUNT_XPRV to the two XPRV values above")
    print("   (only if you want automatic sweep — see note below).")
    print("4. Close this terminal. Clear your shell history if it captured output.")
    print("5. Never paste the mnemonic or the XPRV values into a chat, ticket,")
    print("   file, or repo — including to me (Claude). Only the XPUB values")
    print("   are safe to share if you ever need help debugging derivation.")
    print("=" * 70)


if __name__ == "__main__":
    main()
