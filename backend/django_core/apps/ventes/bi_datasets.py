"""NTDATA1 — datasets BI « ventes » pour l'explorateur de données du noyau.

Même patron que ``apps/sav/bi_datasets.py`` : c'est l'app PROPRIÉTAIRE des
données qui déclare ses datasets (elle seule connaît ses modèles et son
scoping multi-tenant), et ``core.data_explorer`` ne fait que les EXÉCUTER.
``core`` reste fondation : il n'importe jamais ``apps.ventes``.

Trois datasets :

* ``ventes_devis``     — dimensions statut / mode de marché / mois / responsable
  / canal d'origine (via le lead) ; mesure ``prix_par_kwc`` (prix CLIENT par kWc
  déjà GELÉ sur le devis) et dimension ``kwc``.
* ``ventes_factures``  — statut, mois d'émission, montants HT/TVA/TTC, reste dû
  et drapeau « échue ».
* ``ventes_paiements`` — mode, mois, montant.

``prix_achat`` / marge ne figurent dans AUCUN champ : ``Devis.marge_snapshot``
est délibérément ABSENT de la liste blanche (indicateur GÉNÉRATEUR, jamais
client — règle du dépôt).

POURQUOI ``ventes_devis`` N'EXPOSE PAS ``montant_ht`` / ``montant_ttc``
----------------------------------------------------------------------
Le montant d'un devis N'EST PAS une colonne : ``Devis.total_ht`` /
``total_ttc`` passent par ``apps.ventes.domain.argent.totaux(vue=NET)``, qui
applique l'option EFFECTIVE (décision fondateur D9), la règle QF9 des
accessoires orphelins (comparaison sur le NOM du produit lié) puis la remise
globale réconciliée au centime. Aucune de ces règles n'est exprimable en SQL :
une annotation ORM rendrait un nombre DIFFÉRENT de celui que le devis imprime.
La règle du dépôt est explicite — un agrégat vient des données réelles ou il
est OMIS, jamais approché. Les montants sont donc exposés là où ils sont
RÉELLEMENT stockés : ``ventes_factures`` (``montant_ht``/``montant_tva``/
``montant_ttc``, colonnes du modèle) et ``ventes_paiements`` (``montant``).
Le jour où un total HT net est dénormalisé sur ``Devis``, ce dataset l'expose.
"""
from __future__ import annotations

# ── ventes_devis ────────────────────────────────────────────────────────────
DEVIS_DATASET = 'ventes_devis'
DEVIS_FIELDS = [
    'id', 'statut', 'market_mode', 'mois_creation', 'responsable',
    'responsable_id', 'canal', 'kwc', 'prix_par_kwc', 'is_active',
]

# ── ventes_factures ─────────────────────────────────────────────────────────
FACTURES_DATASET = 'ventes_factures'
FACTURES_FIELDS = [
    'id', 'statut', 'type_facture', 'mois_emission', 'montant_ht',
    'montant_tva', 'montant_ttc', 'montant_paye', 'reste_du', 'echue_bool',
    # NTDATA16 — champs du score de COMPLÉTUDE : une facture sans client ni
    # échéance n'est pas recouvrable.
    'client', 'date_echeance',
]

# ── ventes_paiements ────────────────────────────────────────────────────────
PAIEMENTS_DATASET = 'ventes_paiements'
PAIEMENTS_FIELDS = ['id', 'mode', 'statut', 'mois', 'montant']

# NTDATA5 — métadonnées BI par champ (libellé FR + nature). Un champ absent de
# ces dicts reste une DIMENSION portant son propre nom : rétro-compatible.
DEVIS_FIELD_META = {
    'id': {'label': 'Devis', 'type': 'mesure'},
    'statut': {'label': 'Statut', 'type': 'dimension'},
    'market_mode': {'label': 'Marché', 'type': 'dimension'},
    'mois_creation': {'label': 'Mois de création', 'type': 'temps'},
    'responsable': {'label': 'Responsable', 'type': 'dimension'},
    'responsable_id': {'label': 'Responsable (id)', 'type': 'dimension'},
    'canal': {'label': 'Canal du lead', 'type': 'dimension'},
    'kwc': {'label': 'Puissance (kWc)', 'type': 'mesure'},
    'prix_par_kwc': {'label': 'Prix par kWc (TTC)', 'type': 'mesure'},
    'is_active': {'label': 'Version active', 'type': 'dimension'},
}
FACTURES_FIELD_META = {
    'id': {'label': 'Factures', 'type': 'mesure'},
    'statut': {'label': 'Statut', 'type': 'dimension'},
    'type_facture': {'label': 'Type de facture', 'type': 'dimension'},
    'mois_emission': {'label': "Mois d'émission", 'type': 'temps'},
    'montant_ht': {'label': 'Montant HT', 'type': 'mesure'},
    'montant_tva': {'label': 'TVA', 'type': 'mesure'},
    'montant_ttc': {'label': 'Montant TTC', 'type': 'mesure'},
    'montant_paye': {'label': 'Montant payé', 'type': 'mesure'},
    'reste_du': {'label': 'Reste dû', 'type': 'mesure'},
    'echue_bool': {'label': 'Échue', 'type': 'dimension'},
    'client': {'label': 'Client (id)', 'type': 'dimension'},
    'date_echeance': {'label': "Date d'échéance", 'type': 'temps'},
}
PAIEMENTS_FIELD_META = {
    'id': {'label': 'Paiements', 'type': 'mesure'},
    'mode': {'label': 'Mode de règlement', 'type': 'dimension'},
    'statut': {'label': 'Statut', 'type': 'dimension'},
    'mois': {'label': 'Mois', 'type': 'temps'},
    'montant': {'label': 'Montant', 'type': 'mesure'},
}

# Motif POSIX d'un nombre décimal — groupe NON capturant, sinon
# ``substring(texte, motif)`` de Postgres rendrait la capture (la partie
# décimale) au lieu du nombre entier.
_MOTIF_NOMBRE = r'^-?[0-9]+(?:\.[0-9]+)?$'


def _nombre_depuis_json(chemin_json, cle):
    """Valeur NUMÉRIQUE d'une clé d'un ``JSONField``, ou ``NULL``.

    ``etude_params`` est un JSON LIBRE : rien ne garantit que
    ``puissance_kwc`` y soit un nombre. Un ``CAST(... AS double precision)``
    direct ferait donc ÉCHOUER toute la requête sur une seule ligne mal
    formée. On extrait d'abord le texte (``->>``), on ne garde que ce qui EST
    un nombre (``substring`` POSIX — aucune correspondance ⇒ NULL), puis on
    caste. Une valeur non numérique devient VIDE, jamais une erreur et jamais
    un nombre inventé.
    """
    from django.db.models import FloatField, Func, TextField, Value
    from django.db.models.fields.json import KeyTextTransform
    from django.db.models.functions import Cast

    return Cast(
        Func(KeyTextTransform(cle, chemin_json), Value(_MOTIF_NOMBRE),
             function='SUBSTRING', output_field=TextField()),
        FloatField(),
    )


def devis_queryset(company, user):
    """Queryset ``ventes.Devis`` DÉJÀ scopé société.

    Aucun filtrage implicite : les versions supersédées restent visibles (le
    rapport ventes du dépôt les compte aussi) mais ``is_active`` est dans la
    liste blanche pour qui veut les écarter — on ne retire jamais des lignes
    en silence.
    """
    from django.db.models import F
    from django.db.models.functions import TruncMonth

    from .models import Devis

    return Devis.objects.filter(company=company).annotate(
        # Le « mode de marché » du devis EST ``mode_installation``
        # (résidentiel / industriel / commercial / agricole).
        market_mode=F('mode_installation'),
        mois_creation=TruncMonth('date_creation'),
        responsable=F('created_by__username'),
        responsable_id=F('created_by_id'),
        # Canal d'origine : porté par le LEAD (le devis n'en a pas).
        canal=F('lead__canal'),
        kwc=_nombre_depuis_json('etude_params', 'puissance_kwc'),
    )


def factures_queryset(company, user):
    """Queryset ``facturation.Facture`` DÉJÀ scopé société.

    ``montant_paye`` = somme des paiements ENCAISSÉS (un paiement rejeté sort
    du calcul, comme partout ailleurs dans le dépôt) via une sous-requête
    corrélée — jamais un ``Sum`` joint, qui multiplierait les lignes de la
    facture par ses paiements. ``reste_du`` en découle ; ``echue_bool`` est
    évalué à la date du jour, statuts payée/annulée exclus.
    """
    from datetime import date
    from decimal import Decimal

    from django.db.models import (
        BooleanField, Case, DecimalField, F, OuterRef, Q, Subquery, Sum, Value,
        When,
    )
    from django.db.models.functions import Coalesce, TruncMonth

    from .models import Facture, Paiement

    montant_field = DecimalField(max_digits=14, decimal_places=2)
    paye = Subquery(
        Paiement.objects
        .filter(facture=OuterRef('pk'), statut=Paiement.Statut.ENCAISSE)
        .values('facture')
        .annotate(total=Sum('montant'))
        .values('total')[:1],
        output_field=montant_field,
    )
    aujourdhui = date.today()
    return Facture.objects.filter(company=company).annotate(
        mois_emission=TruncMonth('date_emission'),
        montant_paye=Coalesce(paye, Value(Decimal('0'), montant_field),
                              output_field=montant_field),
    ).annotate(
        reste_du=Coalesce(F('montant_ttc'), Value(Decimal('0'), montant_field))
        - F('montant_paye'),
        echue_bool=Case(
            When(Q(date_echeance__lt=aujourdhui)
                 & ~Q(statut__in=[Facture.Statut.PAYEE,
                                  Facture.Statut.ANNULEE]),
                 then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        ),
    )


def paiements_queryset(company, user):
    """Queryset ``facturation.Paiement`` DÉJÀ scopé société."""
    from django.db.models.functions import TruncMonth

    from .models import Paiement

    return Paiement.objects.filter(company=company).annotate(
        mois=TruncMonth('date_paiement'))


def register_dataset():
    """Enregistre les trois datasets ventes (idempotent)."""
    from core import data_explorer

    data_explorer.register_dataset(
        DEVIS_DATASET, 'Devis', DEVIS_FIELDS, devis_queryset,
        field_meta=DEVIS_FIELD_META)
    data_explorer.register_dataset(
        FACTURES_DATASET, 'Factures', FACTURES_FIELDS, factures_queryset,
        field_meta=FACTURES_FIELD_META)
    data_explorer.register_dataset(
        PAIEMENTS_DATASET, 'Paiements', PAIEMENTS_FIELDS, paiements_queryset,
        field_meta=PAIEMENTS_FIELD_META)
