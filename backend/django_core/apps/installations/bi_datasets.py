"""NTDATA4 — dataset BI « chantiers » pour l'explorateur du noyau.

Même patron que ``apps/sav/bi_datasets.py`` : l'app PROPRIÉTAIRE déclare, le
noyau exécute. ``core`` reste fondation et n'importe jamais
``apps.installations``.

Le « chantier » du dépôt est le modèle ``installations.Installation`` (le
libellé métier est « Chantiers » — cf. ``InstallationsConfig.verbose_name``).

Dimensions : statut, ville du site, mois de signature, mois de réception,
installateur (technicien responsable). Mesure : ``kwc`` (puissance installée,
colonne RÉELLE ``puissance_installee_kwc``).

Les chantiers ANNULÉS ne sont pas retirés en silence : le drapeau ``annule``
est dans la liste blanche, à l'utilisateur de l'exclure s'il le veut.
"""
from __future__ import annotations

CHANTIERS_DATASET = 'chantiers'
CHANTIERS_FIELDS = [
    'id', 'statut', 'ville', 'kwc', 'mois_signature', 'mois_reception',
    'installateur', 'type_installation', 'annule',
]

# NTDATA5 — libellé FR + nature par champ (dimension / mesure / temps).
CHANTIERS_FIELD_META = {
    'id': {'label': 'Chantiers', 'type': 'mesure'},
    'statut': {'label': 'Statut', 'type': 'dimension'},
    'ville': {'label': 'Ville du site', 'type': 'dimension'},
    'kwc': {'label': 'Puissance installée (kWc)', 'type': 'mesure'},
    'mois_signature': {'label': 'Mois de signature', 'type': 'temps'},
    'mois_reception': {'label': 'Mois de réception', 'type': 'temps'},
    'installateur': {'label': 'Installateur', 'type': 'dimension'},
    'type_installation': {'label': "Type d'installation",
                          'type': 'dimension'},
    'annule': {'label': 'Annulé', 'type': 'dimension'},
}


def chantiers_queryset(company, user):
    """Queryset ``installations.Installation`` DÉJÀ scopé société."""
    from django.db.models import F
    from django.db.models.functions import TruncMonth

    from .models_installation import Installation

    return Installation.objects.filter(company=company).annotate(
        ville=F('site_ville'),
        kwc=F('puissance_installee_kwc'),
        mois_signature=TruncMonth('date_signature'),
        mois_reception=TruncMonth('date_reception'),
        installateur=F('technicien_responsable__username'),
    )


def register_dataset():
    """Enregistre le dataset ``chantiers`` (idempotent)."""
    from core import data_explorer

    data_explorer.register_dataset(
        CHANTIERS_DATASET, 'Chantiers', CHANTIERS_FIELDS, chantiers_queryset,
        field_meta=CHANTIERS_FIELD_META)
