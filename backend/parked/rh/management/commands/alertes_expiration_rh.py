"""Commande d'alertes d'expiration RH (FG175).

Parcourt chaque société active, calcule les échéances RH unifiées (habilitations
FG173 + certifications FG174 + documents employé FG159) qui expirent dans
``--within`` jours (ou sont déjà expirées) via ``selectors.echeances_rh`` et
dispatche UNE notification in-app par échéance vers les responsables/RH de la
société, à travers le service de notifications partagé (``apps.notifications``).

Multi-société : tout est borné à la société (jamais d'utilisateur d'une autre
société). L'appel au service de notifications est un import FONCTION-LOCAL — on
ne référence jamais ``apps.notifications.models``/``views`` (frontière cross-app
respectée : notifications est un satellite partagé, on n'utilise que son
service public ``notify``). Best-effort : une notification qui échoue n'arrête
pas la commande.

Idempotence d'envoi : cette commande émet à chaque exécution (pas de dédoublon
historique) ; elle est conçue pour être appelée par un planificateur (cron /
Celery beat) à cadence raisonnable. La date du jour est lue ICI (``timezone``)
et passée au sélecteur pur, qui reste déterministe.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.rh import selectors


# Événement de notification réutilisé pour les expirations de titres RH. On
# reste sur un type EXISTANT du référentiel notifications (pas de nouveau type)
# proche sémantiquement (« quelque chose arrive à expiration »).
_EVENT_TYPE = 'warranty_expiring'


def _recipients(company):
    """Responsables/RH actifs de la société (destinataires des alertes).

    Réutilise la logique « managers » (palier admin/responsable) ; à défaut,
    tous les utilisateurs actifs de la société. Toujours borné à la société —
    jamais d'utilisateur d'une autre société. Best-effort.
    """
    try:
        from authentication.models import CustomUser
        base = list(
            CustomUser.objects.filter(company=company, is_active=True))
    except Exception:  # pragma: no cover - défensif
        return []
    managers = []
    for user in base:
        try:
            if getattr(user, 'is_admin_role', False) or \
                    getattr(user, 'role_tier', None) in (
                        'admin', 'responsable'):
                managers.append(user)
        except Exception:  # pragma: no cover - défensif
            continue
    return managers or base


def _libelle_echeance(row):
    """Phrase d'alerte lisible pour une ligne d'échéance (titre court)."""
    jours = row['jours_restants']
    if jours < 0:
        quand = f'expiré depuis {abs(jours)} j'
    elif jours == 0:
        quand = "expire aujourd'hui"
    else:
        quand = f'expire dans {jours} j'
    type_label = {
        'habilitation': 'Habilitation',
        'certification': 'Certification',
        'document': 'Document',
    }.get(row['type'], row['type'])
    # Borné à 255 (max_length du titre de la notification, tronqué côté service).
    return f"{type_label} {row['libelle']} — {row['employe']} ({quand})"[:255]


class Command(BaseCommand):
    help = (
        "Alertes d'expiration RH (FG175) : notifie les responsables/RH des "
        'habilitations, certifications et documents employé qui expirent.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--within', type=int, default=30,
            help="Fenêtre d'alerte en jours (défaut 30).")
        parser.add_argument(
            '--company', type=int, default=None,
            help='Limiter à une société (ID). Par défaut : toutes les sociétés '
                 'actives.')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Calcule et journalise sans émettre de notification.')

    def handle(self, *args, **options):
        # Import fonction-local du service partagé : frontière cross-app
        # respectée (jamais d'import des modèles/vues de notifications).
        from apps.notifications.services import notify

        within = options['within']
        company_id = options['company']
        dry_run = options['dry_run']
        today = timezone.localdate()

        from authentication.models import Company
        companies = Company.objects.all()
        if company_id is not None:
            companies = companies.filter(pk=company_id)

        total_echeances = 0
        total_notifs = 0
        for company in companies:
            rows = selectors.echeances_rh(
                company, within_days=within, today=today)
            if not rows:
                continue
            total_echeances += len(rows)
            recipients = _recipients(company)
            self.stdout.write(
                f'{company} : {len(rows)} échéance(s), '
                f'{len(recipients)} destinataire(s)')
            if dry_run or not recipients:
                continue
            for row in rows:
                titre = _libelle_echeance(row)
                corps = (
                    f"Échéance : {row['date_validite'].isoformat()} "
                    f"({row['jours_restants']} jours).")
                for user in recipients:
                    try:
                        notify(
                            user, _EVENT_TYPE, titre, body=corps,
                            company=company)
                        total_notifs += 1
                    except Exception as exc:  # pragma: no cover - défensif
                        self.stderr.write(
                            f'Notification échouée vers {user} : {exc}')

        self.stdout.write(self.style.SUCCESS(
            f'{total_echeances} échéance(s) RH traitée(s), '
            f'{total_notifs} notification(s) émise(s).'))
