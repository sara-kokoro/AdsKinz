"""Create one admin user interactively; this script is never imported by the API."""

from __future__ import annotations

import asyncio
from getpass import getpass

from sqlalchemy import select

from app.core.security import generate_totp_secret, hash_password, totp_provisioning_uri
from app.database import SessionLocal
from app.models import AdminUser


async def create_admin() -> None:
    """Prompt the operator and insert an admin user through the async session factory."""
    email = input("Admin email: ").strip().lower()
    if not email:
        raise SystemExit("An email address is required.")

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    if not password:
        raise SystemExit("A password is required.")

    password_hash = hash_password(password)
    del password, confirmation
    totp_secret = generate_totp_secret()

    async with SessionLocal() as session:
        existing_id = await session.scalar(select(AdminUser.id).where(AdminUser.email == email))
        if existing_id is not None:
            raise SystemExit(f"An admin user already exists for {email}.")

        session.add(
            AdminUser(
                email=email,
                password_hash=password_hash,
                totp_secret=totp_secret,
                totp_confirmed=False,
                is_active=True,
            )
        )
        await session.commit()

    print("\nAdmin user created.")
    print("Scan this one-time provisioning URI with an authenticator application:")
    print(totp_provisioning_uri(totp_secret, email))
    print("Store the URI securely until the initial TOTP confirmation is complete.")


if __name__ == "__main__":
    asyncio.run(create_admin())
