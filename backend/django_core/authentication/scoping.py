"""Back-compat shim — the real implementation now lives in ``core.scoping``.

Apps depend DOWN on ``core`` instead of sideways on ``authentication``. This
module re-exports the public scoping helpers so existing imports such as
``from authentication.scoping import scope_queryset`` keep working unchanged.
"""
from core.scoping import (  # noqa: F401
    record_scope_for,
    subtree_user_ids,
    peer_user_ids,
    visible_user_ids,
    scope_queryset,
    scope_client_queryset,
)

__all__ = [
    'record_scope_for',
    'subtree_user_ids',
    'peer_user_ids',
    'visible_user_ids',
    'scope_queryset',
    'scope_client_queryset',
]
