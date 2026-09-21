"""Lectures cross-app du module Notes de frais (``apps.frais``) — ODX15.

Point d'entrée ``selectors.py`` exigé par CLAUDE.md : un appelant d'une autre
app (``apps.paie`` pour le remboursement via bulletin, XPAI25) lit les frais
d'ici, sans importer ``apps.frais.models`` ni — surtout — ``apps.compta.models``.

Les implémentations restent celles de ``apps.compta.selectors`` (elles agrègent
des données comptables : montants postés, statuts de remboursement) — ré-export,
pas duplication.
"""

from apps.compta.selectors import (  # noqa: F401
    analyse_notes_frais,
    indemnites_chantier_remboursables_par_paie,
)

__all__ = [
    'analyse_notes_frais',
    'indemnites_chantier_remboursables_par_paie',
    'note_frais_par_id',
    'notes_frais_en_attente',
    'total_rembourse_par_categorie',
    'top_employes_par_montant_notes_frais',
    'delai_moyen_depense_remboursement_jours',
    'total_per_diem_par_destination',
]


def note_frais_par_id(company, note_id):
    """NTMOB7 — une ``NoteFrais`` par id, scopée société (``None`` si absente
    ou hors société). Point d'entrée en LECTURE pour un appelant externe (ex.
    ``reporting.approbations``, décision via jeton de notification push) qui
    ne doit importer ni ``apps.frais.models`` ni — surtout — jamais
    ``apps.compta.models`` directement (frontière ODX15)."""
    if company is None or not note_id:
        return None
    from apps.frais.models import NoteFrais
    return NoteFrais.objects.filter(company=company, id=note_id).first()


def notes_frais_en_attente(company):
    """NTP2P17 — ``{'count', 'montant_total'}`` des ``NoteFrais`` SOUMISES
    (en attente d'approbation) de la société. Point d'entrée en LECTURE pour
    le dashboard spend management (``apps.stock.selectors.
    tableau_bord_achats``) — jamais un import direct de ``NoteFrais`` hors de
    ce module."""
    from decimal import Decimal
    from django.db.models import Count, Sum
    from apps.frais.models import NoteFrais

    if company is None:
        return {'count': 0, 'montant_total': Decimal('0')}
    agg = NoteFrais.objects.filter(
        company=company, statut=NoteFrais.Statut.SOUMISE
    ).aggregate(count=Count('id'), montant_total=Sum('montant'))
    return {
        'count': agg['count'] or 0,
        'montant_total': agg['montant_total'] or Decimal('0'),
    }


# ── NTP2P47 — KPI notes de frais & per-diem (apps.reporting) ────────────────
# Quatre sélecteurs d'agrégation réutilisant les composants déjà en place
# pour ``NoteFrais``/``IndemniteChantier`` (mêmes modèles, même app — aucune
# frontière cross-app à traverser ici, contrairement aux fonctions ci-dessus).
# Consommés par ``apps.reporting.frais_kpi`` (dashboard KPI dédié, même
# patron que ``apps.reporting.p2p_kpi``).

def total_rembourse_par_categorie(company, *, debut=None, fin=None):
    """NTP2P47 — total ``montant`` des ``NoteFrais`` REMBOURSÉES par
    catégorie de dépense, borné sur ``date_remboursement`` (la période du
    KPI = quand le remboursement a eu lieu). Une catégorie sans note
    remboursée sur la période n'apparaît pas (jamais une ligne à 0
    inventée). Triée par montant décroissant."""
    from decimal import Decimal
    from django.db.models import Sum
    from apps.frais.models import NoteFrais

    if company is None:
        return []
    qs = NoteFrais.objects.filter(
        company=company, statut=NoteFrais.Statut.REMBOURSEE)
    if debut is not None:
        qs = qs.filter(date_remboursement__gte=debut)
    if fin is not None:
        qs = qs.filter(date_remboursement__lte=fin)
    lignes = (
        qs.values('categorie')
        .annotate(montant_total=Sum('montant'))
        .order_by('-montant_total'))
    labels = dict(NoteFrais.Categorie.choices)
    return [
        {
            'categorie': ligne['categorie'],
            'categorie_display': labels.get(
                ligne['categorie'], ligne['categorie']),
            'montant_total': ligne['montant_total'] or Decimal('0'),
        }
        for ligne in lignes
    ]


def top_employes_par_montant_notes_frais(company, *, debut=None, fin=None,
                                         limit=5):
    """NTP2P47 — top ``limit`` employés par montant TOTAL de notes de frais
    (tous statuts confondus — une activité, pas seulement le remboursé),
    borné sur ``date_frais``. Renvoie ``[]`` si aucune note sur la
    période."""
    from django.db.models import Sum
    from apps.frais.models import NoteFrais

    if company is None:
        return []
    qs = NoteFrais.objects.filter(company=company)
    if debut is not None:
        qs = qs.filter(date_frais__gte=debut)
    if fin is not None:
        qs = qs.filter(date_frais__lte=fin)
    lignes = (
        qs.values('employe_id', 'employe__username',
                  'employe__first_name', 'employe__last_name')
        .annotate(montant_total=Sum('montant'))
        .order_by('-montant_total')[:limit])
    resultat = []
    for ligne in lignes:
        nom_complet = (
            f"{ligne['employe__first_name']} {ligne['employe__last_name']}"
        ).strip()
        resultat.append({
            'employe_id': ligne['employe_id'],
            'employe_nom': nom_complet or ligne['employe__username'],
            'montant_total': ligne['montant_total'],
        })
    return resultat


def delai_moyen_depense_remboursement_jours(company, *, debut=None,
                                            fin=None):
    """NTP2P47 — délai MOYEN (en jours) entre la date de la dépense
    (``date_frais``) et sa date de remboursement (``date_remboursement``),
    sur les ``NoteFrais`` REMBOURSÉES de la période (bornée sur
    ``date_remboursement``, même filtre que ``total_rembourse_par_
    categorie``). ``None`` (jamais 0) si aucune note remboursée sur la
    période — critère d'acceptation NTP2P47 : soumise/dépensée le 1er,
    remboursée le 15 → 14 jours."""
    from apps.frais.models import NoteFrais

    if company is None:
        return None
    qs = NoteFrais.objects.filter(
        company=company, statut=NoteFrais.Statut.REMBOURSEE,
        date_remboursement__isnull=False)
    if debut is not None:
        qs = qs.filter(date_remboursement__gte=debut)
    if fin is not None:
        qs = qs.filter(date_remboursement__lte=fin)
    delais = [
        (date_remboursement - date_frais).days
        for date_frais, date_remboursement in qs.values_list(
            'date_frais', 'date_remboursement')
    ]
    if not delais:
        return None
    return round(sum(delais) / len(delais), 1)


def total_per_diem_par_destination(company, *, debut=None, fin=None):
    """NTP2P47 — total ``montant_per_diem`` des ``IndemniteChantier``
    (NTP2P12) REMBOURSÉES par destination (``libelle_chantier``), borné sur
    ``date_deplacement`` — même filtre de statut que son jumeau
    ``total_rembourse_par_categorie`` ci-dessus (une per-diem brouillon,
    soumise, validée ou rejetée n'est pas encore un coût réel remboursé).
    Une destination vide (``''``) regroupe les missions sans chantier
    renseigné. Triée par montant décroissant."""
    from decimal import Decimal
    from django.db.models import Sum
    from apps.frais.models import IndemniteChantier

    if company is None:
        return []
    qs = IndemniteChantier.objects.filter(
        company=company, statut=IndemniteChantier.Statut.REMBOURSEE)
    if debut is not None:
        qs = qs.filter(date_deplacement__gte=debut)
    if fin is not None:
        qs = qs.filter(date_deplacement__lte=fin)
    lignes = (
        qs.values('libelle_chantier')
        .annotate(montant_total=Sum('montant_per_diem'))
        .order_by('-montant_total'))
    return [
        {
            'destination': ligne['libelle_chantier'],
            'montant_total': ligne['montant_total'] or Decimal('0'),
        }
        for ligne in lignes
    ]
