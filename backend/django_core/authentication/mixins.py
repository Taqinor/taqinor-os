"""Back-compat shim — the real implementation now lives in ``core.mixins``.

Apps depend DOWN on ``core`` instead of sideways on ``authentication``. This
module re-exports ``TenantMixin`` so existing imports such as
``from authentication.mixins import TenantMixin`` keep working unchanged.
"""
from core.mixins import TenantMixin  # noqa: F401

__all__ = ['TenantMixin']
