#!/bin/sh
# Applies any pending Alembic migration before the API starts, so a missing
# migration can never again cause "column does not exist" errors in
# production - every deploy self-heals the schema first.
set -e

echo "entrypoint: ensuring alembic_version.version_num is wide enough..."
python -c "
import asyncio
import asyncpg
from app.config import settings

async def main():
    url = settings.DATABASE_URL.replace('?ssl=require', '').replace('&ssl=require', '')
    url = url.replace('postgresql+asyncpg://', 'postgresql://', 1)
    url = url.replace('postgresql://', 'postgres://', 1)
    ssl = 'require' if 'ssl=require' in settings.DATABASE_URL else None
    conn = await asyncpg.connect(url, ssl=ssl, statement_cache_size=0)
    try:
        await conn.execute(
            'ALTER TABLE IF EXISTS alembic_version '
            'ALTER COLUMN version_num TYPE VARCHAR(255)'
        )
    finally:
        await conn.close()

asyncio.run(main())
"
echo "entrypoint: alembic_version column check done."

echo "entrypoint: running 'alembic upgrade head'..."
alembic upgrade head
echo "entrypoint: migrations up to date, starting the API."

if [ "${RUN_WALLET_ADDRESS_RESET:-}" = "1" ]; then
  RESET_NETWORK="${RUN_WALLET_ADDRESS_RESET_NETWORK:-all}"
  echo "entrypoint: RUN_WALLET_ADDRESS_RESET=1 (network=$RESET_NETWORK) -> resetting wallet addresses..."
  python -m app.onetime_reset_wallet_addresses --network "$RESET_NETWORK" --yes
  echo "entrypoint: wallet address reset done."
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
