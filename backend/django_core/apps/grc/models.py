"""Modèles du module GRC & Conformité (Groupe NTGRC).

Convention du dépôt : tout modèle multi-société hérite de
``core.models.TenantModel`` (FK ``company`` + horodatage, ARC1). Les
références vers une AUTRE app sont déclarées en CHAÎNE (``'app.Model'``) ou
portées par un identifiant texte (``*_ref``) — jamais un import de ses
``models``.
"""
from core.models import TenantModel  # noqa: F401
