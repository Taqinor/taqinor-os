"""Sélecteurs (lecture) du module ``apps.douane``.

NTLOG13/NTLOG21 (calculs de valeur en douane / droits & taxes estimés) sont
BLOCKED — ils dépendent de ``DossierImport`` (NTLOG10, BLOCKED, voir
``apps/douane/apps.py``). Aucun sélecteur n'est encore nécessaire côté
``DossierExport`` (NTLOG14) : sa seule lecture est la liste/detail standard
DRF déjà couverte par ``DossierExportViewSet``."""
