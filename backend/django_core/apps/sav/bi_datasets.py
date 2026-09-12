"""ZSAV7 — dataset BI `sav_tickets` pour l'explorateur/pivot du noyau (FG380/382).

Odoo expose les tickets au pivot/graph (équipe×statut, mesures Hours
Open/Rating/Count) ; ici seul le rapport service (comptes par statut)
existait. On DÉCLARE le dataset côté `sav` (cet app connaît son modèle) et il
est LU par le noyau via `core.data_explorer.run_query` — aucun import
inverse : `core` reste fondation, `data_explorer` ne connaît jamais
`apps.sav.models`.

Dimensions : statut, priorité, type (correctif/préventif — `categorie` ZSAV2
n'existe pas encore ; ce dataset sera étendu quand ce référentiel sera
construit), technicien, mois d'ouverture. Mesures : nombre (count), coût
interne (`cout`, gated `prix_achat_voir`), délai de résolution (jours,
annotation SQL `date_resolution − date(date_creation)`, NULL tant que non
résolu — donc agrégeable par `avg`/`min`/`max` comme n'importe quel champ).

AUD801 — le masquage de `cout` n'est PLUS « la responsabilité de l'appelant » :
aucun des huit consommateurs de `core.data_explorer.run_query` ne le faisait,
et l'un d'eux (l'extrait planifié vers SFTP/S3) appelle même le moteur avec
`user=None`. Le champ est donc déclaré `gated_fields` AU DATASET, et le moteur
l'écarte de toutes les positions de la spec (select, filtres, group_by, tris,
agrégats et projection par défaut) pour chaque lecteur sans
`can_view_buy_prices`."""

# Liste blanche des champs interrogeables (core.data_explorer._check_fields).
DATASET_NAME = 'sav_tickets'
FIELDS = [
    'id', 'statut', 'priorite', 'type', 'technicien_responsable_id',
    'technicien_responsable__username', 'mois_ouverture', 'cout',
    'delai_resolution_jours',
]
# AUD801 — champ -> attribut de permission du lecteur. `can_view_buy_prices`
# est la propriété qui porte `prix_achat_voir` (avec le repli légacy documenté
# côté `authentication.CustomUser`).
GATED_FIELDS = {'cout': 'can_view_buy_prices'}


def sav_tickets_queryset(company, user):
    """Queryset `sav.Ticket` DÉJÀ scopé société (la sécurité multi-tenant
    reste chez cette app, comme l'exige `register_dataset`).

    Le coût interne (`cout`) reste dans le queryset : AUD801 le masque au
    niveau du MOTEUR (`gated_fields`, cf. `GATED_FIELDS` ci-dessus), une seule
    fois pour les huit consommateurs — et non plus « par l'appelant », ce que
    personne ne faisait."""
    from django.db.models import F, ExpressionWrapper, DurationField
    from django.db.models.functions import Cast, TruncMonth
    from django.db.models.fields import DateField
    from .models import Ticket

    qs = Ticket.objects.filter(company=company, annule=False)
    qs = qs.annotate(mois_ouverture=TruncMonth('date_creation'))
    # date_resolution (DateField) − date_creation castée en DateField : Django
    # sait soustraire deux DateField en DurationField nativement (Postgres
    # inclus). NULL si date_resolution n'est pas encore renseignée (ticket
    # ouvert) — jamais d'exception, l'annotation dégrade proprement. La
    # valeur est un timedelta (agrégeable avg/min/max ; converti en jours par
    # l'appelant JSON, ex. reporting).
    return qs.annotate(
        delai_resolution_jours=ExpressionWrapper(
            F('date_resolution') - Cast('date_creation', output_field=DateField()),
            output_field=DurationField(),
        )
    )


# ── NTDATA4 — contrats de maintenance ───────────────────────────────────────
CONTRATS_DATASET_NAME = 'sav_contrats'
CONTRATS_FIELDS = [
    'id', 'statut', 'actif', 'frequence', 'mois_renouvellement',
    'valeur_annuelle', 'prix',
]
# NTDATA5 — libellé FR + nature par champ (dimension / mesure / temps).
CONTRATS_FIELD_META = {
    'id': {'label': 'Contrats', 'type': 'mesure'},
    'statut': {'label': 'Statut', 'type': 'dimension'},
    'actif': {'label': 'Actif', 'type': 'dimension'},
    'frequence': {'label': 'Fréquence', 'type': 'dimension'},
    'mois_renouvellement': {'label': 'Mois de renouvellement',
                            'type': 'temps'},
    'valeur_annuelle': {'label': 'Valeur annuelle', 'type': 'mesure'},
    'prix': {'label': 'Prix par période', 'type': 'mesure'},
}
# NTDATA5 — métadonnées des champs de `sav_tickets` (rétro-compatible : un
# champ absent resterait une dimension portant son nom).
FIELD_META = {
    'id': {'label': 'Tickets', 'type': 'mesure'},
    'statut': {'label': 'Statut', 'type': 'dimension'},
    'priorite': {'label': 'Priorité', 'type': 'dimension'},
    'type': {'label': 'Type', 'type': 'dimension'},
    'technicien_responsable_id': {'label': 'Technicien (id)',
                                  'type': 'dimension'},
    'technicien_responsable__username': {'label': 'Technicien',
                                         'type': 'dimension'},
    'mois_ouverture': {'label': "Mois d'ouverture", 'type': 'temps'},
    'cout': {'label': 'Coût interne', 'type': 'mesure'},
    'delai_resolution_jours': {'label': 'Délai de résolution',
                               'type': 'mesure'},
}


def sav_contrats_queryset(company, user):
    """Queryset `sav.ContratMaintenance` DÉJÀ scopé société.

    * `frequence` = `periodicite` (mensuel/trimestriel/semestriel/annuel) ;
    * `statut` — le modèle n'a PAS de colonne `statut` : son état EST le
      drapeau `actif`. On le TRADUIT en libellé ('actif' / 'inactif') pour
      qu'un pivot soit lisible, et `actif` reste exposé tel quel ;
    * `valeur_annuelle` = `prix × (12 / mois de la périodicité)`. `prix` est le
      montant TTC d'UNE période (c'est exactement ce que
      `ventes.domain.facturation_ops.creer_facture_contrat` facture à chaque
      cycle) ; les mois par périodicité viennent de `ContratMaintenance.MONTHS`,
      la table du modèle — aucune constante recopiée, aucun ratio inventé. Un
      contrat sans prix rend une valeur VIDE, jamais zéro (zéro serait un
      chiffre faux).
    """
    from decimal import Decimal

    from django.db.models import (
        Case, CharField, DecimalField, ExpressionWrapper, F, Value, When,
    )
    from django.db.models.functions import TruncMonth
    from .models import ContratMaintenance

    valeur_field = DecimalField(max_digits=14, decimal_places=2)
    # Multiplicateur annuel par périodicité, DÉRIVÉ de la table du modèle.
    facteur = Case(
        *[When(periodicite=cle,
               then=Value(Decimal(12) / Decimal(mois),
                          output_field=valeur_field))
          for cle, mois in ContratMaintenance.MONTHS.items()],
        default=Value(None, output_field=valeur_field),
        output_field=valeur_field,
    )
    return ContratMaintenance.objects.filter(company=company).annotate(
        frequence=F('periodicite'),
        mois_renouvellement=TruncMonth('date_renouvellement'),
        statut=Case(
            When(actif=True, then=Value('actif')),
            default=Value('inactif'),
            output_field=CharField(),
        ),
        valeur_annuelle=ExpressionWrapper(
            F('prix') * facteur, output_field=valeur_field),
    )


def register_dataset():
    """Enregistre `sav_tickets` et `sav_contrats` dans `core.data_explorer`
    (idempotent : `register_dataset` écrase l'entrée existante sans erreur —
    appelable plusieurs fois, ex. tests, sans effet de bord)."""
    from core import data_explorer
    data_explorer.register_dataset(
        DATASET_NAME, 'Tickets SAV', FIELDS, sav_tickets_queryset,
        gated_fields=GATED_FIELDS, field_meta=FIELD_META)
    data_explorer.register_dataset(
        CONTRATS_DATASET_NAME, 'Contrats de maintenance', CONTRATS_FIELDS,
        sav_contrats_queryset, field_meta=CONTRATS_FIELD_META)
