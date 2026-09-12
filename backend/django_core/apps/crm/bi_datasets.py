"""NTDATA2 — datasets BI « CRM » pour l'explorateur de données du noyau.

Même patron que ``apps/sav/bi_datasets.py`` et ``apps/ventes/bi_datasets.py`` :
l'app PROPRIÉTAIRE déclare, ``core.data_explorer`` exécute. ``core`` reste
fondation et n'importe jamais ``apps.crm``.

* ``crm_leads``   — étape de pipeline, canal, priorité, ville, mois de création,
  type d'installation, drapeau « perdu » et motif de perte.
* ``crm_clients`` — ville (via le répertoire unifié ``tiers``), mois de création
  et type de client.

RÈGLE #2 — LES NOMS D'ÉTAPES NE SONT JAMAIS ÉCRITS ICI. ``Lead.stage`` est une
simple colonne : le dataset l'expose telle quelle, et les LIBELLÉS viennent de
``apps.crm.stages`` (qui charge le ``STAGES.py`` de la racine). Aucune liste
d'étapes n'est recopiée dans ce module — un test le vérifie.

``crm_clients`` — POURQUOI ``ville`` PASSE PAR ``tiers``
-------------------------------------------------------
``crm.Client`` ne porte PAS de colonne ``ville`` (seulement une ``adresse``
libre). La ville RÉELLE d'un client est celle de sa fiche du répertoire
unifié ``tiers.Tiers`` (pont ARC18, miroir one-way ``Client`` → ``Tiers``). On
expose donc cette valeur telle quelle — jamais une ville devinée en découpant
l'adresse libre, ce qui inventerait une donnée.
"""
from __future__ import annotations

LEADS_DATASET = 'crm_leads'
LEADS_FIELDS = [
    'id', 'stage', 'canal', 'priorite', 'ville', 'mois_creation',
    'type_installation', 'perdu_bool', 'motif_perte', 'owner_username',
]

CLIENTS_DATASET = 'crm_clients'
CLIENTS_FIELDS = ['id', 'ville', 'mois_creation', 'type']


def stage_labels():
    """Libellés FR des étapes, LUS depuis ``STAGES.py`` (jamais recopiés)."""
    from . import stages as stage_mod
    return dict(stage_mod.STAGE_LABELS)


def leads_queryset(company, user):
    """Queryset ``crm.Lead`` DÉJÀ scopé société.

    Les leads ARCHIVÉS sont exclus, exactement comme le rapport ventes du
    dépôt (``reporting.reports`` filtre ``is_archived=False``) — cohérence de
    population entre les deux surfaces, pas un filtrage silencieux
    supplémentaire.
    """
    from django.db.models import F
    from django.db.models.functions import TruncMonth

    from .models import Lead

    return Lead.objects.filter(
        company=company, is_archived=False,
    ).annotate(
        mois_creation=TruncMonth('date_creation'),
        perdu_bool=F('perdu'),
        owner_username=F('owner__username'),
    )


def clients_queryset(company, user):
    """Queryset ``crm.Client`` DÉJÀ scopé société."""
    from django.db.models import F
    from django.db.models.functions import TruncMonth

    from .models import Client

    return Client.objects.filter(company=company).annotate(
        mois_creation=TruncMonth('date_creation'),
        ville=F('tiers__ville'),
        type=F('type_client'),
    )


def register_dataset():
    """Enregistre les deux datasets CRM (idempotent)."""
    from core import data_explorer

    data_explorer.register_dataset(
        LEADS_DATASET, 'Pistes (leads)', LEADS_FIELDS, leads_queryset)
    data_explorer.register_dataset(
        CLIENTS_DATASET, 'Clients', CLIENTS_FIELDS, clients_queryset)
