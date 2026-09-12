"""NTUX39/NTUX40 — lectures cross-app de `apps.uxviews` (point d'entrée
lecture, frontière inter-apps CLAUDE.md — jamais un import direct de
`apps.uxviews.models` par une autre app)."""
from datetime import date, timedelta


def kpi_adoption_ux(company):
    """NTUX40 — tuiles KPI d'adoption UX pour l'endpoint reporting fédéré
    (ARC40, `apps/reporting/reports.py::kpi_federes`, déclaré dans
    `apps/uxviews/platform.py` — le reporting n'importe JAMAIS les modèles
    uxviews, il appelle ce sélecteur). Chaque tuile suit la forme normalisée
    `{id, label, valeur, unite?}`. Lecture seule, scopé société.

    Trois indicateurs :
      * % d'écrans (parmi ceux qui ont AU MOINS une vue sauvegardée) portant
        une vue par défaut de rôle définie (NTUX2) ;
      * nombre moyen de vues personnelles par utilisateur ACTIF ;
      * taux d'utilisation de l'édition en masse vs l'édition ligne-par-ligne
        sur les 30 derniers jours — dérivé de `audit.AuditLog` (jamais une
        nouvelle table de compteurs) : une édition en masse (NTUX5/core
        `BulkEditViewSet`) journalise un détail préfixé « Édition en masse »
        (`apps/audit/receivers.py::_record_bulk_edit`), distinct des UPDATE
        ligne-par-ligne classiques.
    """
    from django.contrib.auth import get_user_model

    from apps.audit.models import AuditLog

    from .models import SavedView

    User = get_user_model()

    # ── % d'écrans avec une vue par défaut de rôle définie ──────────────────
    ecrans_avec_vues = set(
        SavedView.objects.filter(company=company).values_list('ecran', flat=True))
    ecrans_avec_defaut = set(
        SavedView.objects.filter(company=company, est_defaut_role=True)
        .values_list('ecran', flat=True))
    pct_ecrans_avec_defaut = (
        round(100 * len(ecrans_avec_defaut) / len(ecrans_avec_vues), 1)
        if ecrans_avec_vues else 0)

    # ── Nombre moyen de vues personnelles par utilisateur actif ─────────────
    utilisateurs_actifs = User.objects.filter(company=company, is_active=True).count()
    vues_personnelles = SavedView.objects.filter(
        company=company, visibilite=SavedView.Visibilite.PERSONNELLE).count()
    moyenne_vues_perso = (
        round(vues_personnelles / utilisateurs_actifs, 2)
        if utilisateurs_actifs else 0)

    # ── Taux d'utilisation édition en masse vs ligne-par-ligne (30 j) ───────
    depuis = date.today() - timedelta(days=30)
    updates_recentes = AuditLog.objects.filter(
        company=company, action=AuditLog.Action.UPDATE, timestamp__date__gte=depuis)
    nb_masse = updates_recentes.filter(detail__startswith='Édition en masse').count()
    nb_total = updates_recentes.count()
    taux_masse = round(100 * nb_masse / nb_total, 1) if nb_total else 0

    return [
        {'id': 'ux_pct_ecrans_defaut_role', 'label': "Écrans avec vue par défaut de rôle",
         'valeur': pct_ecrans_avec_defaut, 'unite': '%'},
        {'id': 'ux_moyenne_vues_personnelles', 'label': 'Vues personnelles par utilisateur actif',
         'valeur': moyenne_vues_perso, 'unite': 'vues'},
        {'id': 'ux_taux_edition_masse', 'label': 'Édition en masse (30 derniers jours)',
         'valeur': taux_masse, 'unite': '%'},
    ]
