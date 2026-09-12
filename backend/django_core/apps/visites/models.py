"""Modèles du module « Visites terrain » (``apps.visites``).

VTA1 pose le squelette ; VTA2 y reloge ``VisiteTerrain``/``VisiteMedia``
depuis ``apps.crm`` en STATE-ONLY (tables physiques ``crm_visiteterrain`` /
``crm_visitemedia`` conservées, FK ``lead`` en référence STRING
``'crm.Lead'``).
"""
from core.models import TenantModel  # noqa: F401
