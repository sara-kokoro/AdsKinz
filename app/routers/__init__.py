"""HTTP routers.

The paths registered here are part of the public contract with the frontend
and must not be renamed.
"""

from app.routers import (
    admin,
    advertiser,
    auth,
    billing,
    publisher,
    sdk,
    tracking,
)

__all__ = [
    "admin",
    "advertiser",
    "auth",
    "billing",
    "publisher",
    "sdk",
    "tracking",
]
