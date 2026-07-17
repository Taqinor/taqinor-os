"""Lectures de `apps.adminops`."""
from datetime import timedelta

from django.utils import timezone

from .models import ConfigPackage, EvenementUsage, SandboxEnvironment


def adoption_par_module(company, jours=30):
    """NTADM17 — agrège `EvenementUsage` en (module -> nb utilisateurs actifs
    / nb événements / dernière utilisation)."""
    depuis = timezone.now() - timedelta(days=jours)
    qs = EvenementUsage.objects.filter(company=company, horodatage__gte=depuis)
    par_module = {}
    for module in qs.values_list('module', flat=True).distinct():
        evts = qs.filter(module=module)
        par_module[module] = {
            'nb_evenements': evts.count(),
            'nb_utilisateurs_actifs': evts.exclude(
                utilisateur__isnull=True).values('utilisateur').distinct().count(),
            'derniere_utilisation': evts.order_by('-horodatage').values_list(
                'horodatage', flat=True).first(),
        }
    return par_module


def adoption_par_utilisateur(company, jours=30):
    """NTADM17 — (utilisateur -> écrans visités / dernière connexion)."""
    depuis = timezone.now() - timedelta(days=jours)
    qs = EvenementUsage.objects.filter(
        company=company, horodatage__gte=depuis, utilisateur__isnull=False)
    par_user = {}
    for uid in qs.values_list('utilisateur_id', flat=True).distinct():
        evts = qs.filter(utilisateur_id=uid)
        par_user[uid] = {
            'ecrans_visites': list(evts.values_list('ecran', flat=True).distinct()),
            'derniere_connexion': evts.order_by('-horodatage').values_list(
                'horodatage', flat=True).first(),
        }
    return par_user


def taux_adoption_moyen(company, jours=30):
    """NTADM48 — % moyen (simplifié : ratio d'utilisateurs actifs distincts
    sur `jours` vs. l'effectif total actif de la société)."""
    from authentication.models import CustomUser
    depuis = timezone.now() - timedelta(days=jours)
    total_users = CustomUser.objects.filter(company=company, is_active=True).count()
    if not total_users:
        return 0
    actifs = EvenementUsage.objects.filter(
        company=company, horodatage__gte=depuis,
        utilisateur__isnull=False).values('utilisateur').distinct().count()
    return round(min(actifs / total_users, 1) * 100)


def kpi_adminops(company):
    """NTADM48 (partiel — le tuile-registre `reporting.dashboard_config_api`
    hors périmètre de cette lane reste BLOQUÉ, cf. rapport) : 3 tuiles
    « Santé & adoption » exposées via l'endpoint KPI fédéré `reporting` déjà
    existant (ARC40, `apps/reporting/reports.py::kpi_federes`), même patron
    que `apps.credit.selectors.kpi_credit`. Lecture seule, scopé société."""
    from .health_score import calculer_health_score
    from .models import HealthScoreSnapshot

    dernier = HealthScoreSnapshot.objects.filter(
        company=company).order_by('-calcule_le').first()
    score = dernier.score if dernier else calculer_health_score(company)['score']

    from authentication.models import CustomUser
    sieges_utilises = CustomUser.objects.filter(company=company, is_active=True).count()

    return [
        {'id': 'adminops_health_score', 'label': 'Health score', 'valeur': score,
         'unite': '/100'},
        {'id': 'adminops_taux_adoption', 'label': "Taux d'adoption (30j)",
         'valeur': taux_adoption_moyen(company), 'unite': '%'},
        {'id': 'adminops_sieges_utilises', 'label': 'Sièges utilisés',
         'valeur': sieges_utilises},
    ]


def diagnostic_tenant(company):
    """NTADM23 — instantané non-sensible du tenant courant, strictement
    scopé société."""
    from django.db.migrations.recorder import MigrationRecorder

    from authentication.models import CustomUser

    try:
        derniere_migration = MigrationRecorder.Migration.objects.order_by(
            '-applied').values_list('app', 'name', 'applied').first()
    except Exception:
        derniere_migration = None

    derniere_connexion = CustomUser.objects.filter(
        company=company, last_login__isnull=False).order_by(
        '-last_login').values_list('username', 'last_login').first()

    nb_erreurs = []
    try:
        from apps.audit.models import AuditLog
        nb_erreurs = list(AuditLog.objects.filter(
            company=company, action=AuditLog.Action.SECURITY_ALERT
        ).order_by('-created_at').values_list('detail', 'created_at')[:5])
    except Exception:
        pass

    return {
        'derniere_migration': derniere_migration,
        'nb_utilisateurs': CustomUser.objects.filter(company=company).count(),
        'derniere_connexion': derniere_connexion,
        'sandbox_actifs': SandboxEnvironment.objects.filter(
            company=company,
            statut__in=[SandboxEnvironment.Statut.EN_CREATION,
                        SandboxEnvironment.Statut.PRET]).count(),
        'config_packages_exportes': ConfigPackage.objects.filter(
            company=company).count(),
        'dernieres_erreurs_audit': nb_erreurs,
    }
