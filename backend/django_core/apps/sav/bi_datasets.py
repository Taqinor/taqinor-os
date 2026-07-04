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
interne (`cout`, gated `prix_achat_voir` — jamais renvoyé sans permission,
masqué par l'APPELANT), délai de résolution (jours, annotation SQL
`date_resolution − date(date_creation)`, NULL tant que non résolu — donc
agrégeable par `avg`/`min`/`max` comme n'importe quel champ)."""

# Liste blanche des champs interrogeables (core.data_explorer._check_fields).
DATASET_NAME = 'sav_tickets'
FIELDS = [
    'id', 'statut', 'priorite', 'type', 'technicien_responsable_id',
    'technicien_responsable__username', 'mois_ouverture', 'cout',
    'delai_resolution_jours',
]


def sav_tickets_queryset(company, user):
    """Queryset `sav.Ticket` DÉJÀ scopé société (la sécurité multi-tenant
    reste chez cette app, comme l'exige `register_dataset`).

    Le coût interne (`cout`) N'EST PAS masqué au niveau du queryset : le
    masquage est la responsabilité de l'APPELANT (vue/serializer), qui doit
    vérifier `user.can_view_buy_prices` avant d'exposer ce champ — cohérent
    avec le reste du repo (ex. `stock_report.valorisation_achat`, jamais
    filtré côté requête mais jamais renvoyé sans permission)."""
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


def register_dataset():
    """Enregistre `sav_tickets` dans `core.data_explorer` (idempotent :
    `register_dataset` écrase l'entrée existante sans erreur — appelable
    plusieurs fois, ex. tests, sans effet de bord)."""
    from core import data_explorer
    data_explorer.register_dataset(
        DATASET_NAME, 'Tickets SAV', FIELDS, sav_tickets_queryset)
