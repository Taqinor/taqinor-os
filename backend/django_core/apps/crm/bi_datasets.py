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
    'signe_num', 'montant_estime',
    # NTDATA16 — champs d'identité nécessaires au score de COMPLÉTUDE (un
    # lead sans téléphone n'est pas rappelable).
    'nom', 'telephone', 'email',
]

CLIENTS_DATASET = 'crm_clients'
# NTDATA14/16/17 — les champs d'IDENTITÉ (ICE, adresse, téléphone, email) sont
# exposés parce que la qualité de données travaille dessus : une règle de
# format ICE, un score de complétude et une détection de doublons ont besoin
# de la VALEUR, pas d'un drapeau. Ce sont exactement les champs que la fiche
# client rend déjà à tout utilisateur authentifié — aucune nouvelle exposition.
CLIENTS_FIELDS = [
    'id', 'ville', 'mois_creation', 'type', 'ice', 'adresse', 'telephone',
    'email', 'nom',
]

# NTDATA5 — libellé FR + nature par champ. Le LIBELLÉ d'une étape n'est PAS
# écrit ici (règle #2) : `stage` porte le libellé générique « Étape » et les
# valeurs sont traduites par `stage_labels()`, lu depuis STAGES.py.
LEADS_FIELD_META = {
    'id': {'label': 'Pistes', 'type': 'mesure'},
    'stage': {'label': 'Étape', 'type': 'dimension'},
    'canal': {'label': 'Canal', 'type': 'dimension'},
    'priorite': {'label': 'Priorité', 'type': 'dimension'},
    'ville': {'label': 'Ville', 'type': 'dimension'},
    'mois_creation': {'label': 'Mois de création', 'type': 'temps'},
    'type_installation': {'label': "Type d'installation",
                          'type': 'dimension'},
    'perdu_bool': {'label': 'Perdu', 'type': 'dimension'},
    'motif_perte': {'label': 'Motif de perte', 'type': 'dimension'},
    'owner_username': {'label': 'Responsable', 'type': 'dimension'},
    'signe_num': {'label': 'Signés (1/0)', 'type': 'mesure'},
    'montant_estime': {'label': 'Montant estimé', 'type': 'mesure'},
    'nom': {'label': 'Nom', 'type': 'dimension'},
    'telephone': {'label': 'Téléphone', 'type': 'dimension'},
    'email': {'label': 'Email', 'type': 'dimension'},
}
CLIENTS_FIELD_META = {
    'id': {'label': 'Clients', 'type': 'mesure'},
    'ville': {'label': 'Ville', 'type': 'dimension'},
    'mois_creation': {'label': 'Mois de création', 'type': 'temps'},
    'type': {'label': 'Type de client', 'type': 'dimension'},
    'ice': {'label': 'ICE', 'type': 'dimension'},
    'adresse': {'label': 'Adresse', 'type': 'dimension'},
    'telephone': {'label': 'Téléphone', 'type': 'dimension'},
    'email': {'label': 'Email', 'type': 'dimension'},
    'nom': {'label': 'Nom', 'type': 'dimension'},
}


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
    from django.db.models import Case, F, IntegerField, Q, Value, When
    from django.db.models.functions import TruncMonth

    from . import stages as stage_mod
    from .models import Lead

    return Lead.objects.filter(
        company=company, is_archived=False,
    ).annotate(
        mois_creation=TruncMonth('date_creation'),
        perdu_bool=F('perdu'),
        owner_username=F('owner__username'),
        # NTDATA11 — indicateur 1/0 « signé », pour que le TAUX DE CONVERSION
        # soit une somme SQL (somme(signe_num) / compte(id)) au lieu d'un
        # comptage conditionnel que le moteur ne sait pas exprimer. La règle
        # est celle du dépôt (`crm.selectors` : étape SIGNED ET non perdu) et
        # la clé d'étape est LUE de STAGES.py — jamais écrite ici (règle #2).
        signe_num=Case(
            When(Q(stage=stage_mod.SIGNED) & Q(perdu=False), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
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
        LEADS_DATASET, 'Pistes (leads)', LEADS_FIELDS, leads_queryset,
        field_meta=LEADS_FIELD_META)
    data_explorer.register_dataset(
        CLIENTS_DATASET, 'Clients', CLIENTS_FIELDS, clients_queryset,
        field_meta=CLIENTS_FIELD_META)
