"""YSERV13 — contrôle d'intégrité inter-documents (états orphelins entre apps).

Parcourt chaque société (ou une seule ``--company`` slug), exécute TOUTES les
familles de `apps.reporting.integrity.controle_integrite` et notifie
(``notify_many``, best-effort) seulement si AU MOINS UNE anomalie est
détectée. Lecture seule : ne corrige RIEN automatiquement.

Pensé pour être exécuté à la demande ou par Celery Beat (hebdomadaire).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py controle_integrite                       # toutes sociétés
  python manage.py controle_integrite --company taqinor-demo  # une société
"""
from django.core.management.base import BaseCommand, CommandError

from apps.reporting.integrity import controle_integrite, total_anomalies


class Command(BaseCommand):
    help = (
        "Détecte les états orphelins inter-documents (devis accepté sans "
        "chantier, chantier réceptionné sans parc, réservation non libérée, "
        "intervention non terminée d'un chantier clos, ticket clôturé avec "
        "intervention ouverte, contrat de maintenance expiré, facture payée "
        "avec solde) et notifie si ≥1 anomalie est trouvée. Lecture seule."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug d'une seule société à contrôler (défaut : toutes).",
        )

    def handle(self, *args, **options):
        from authentication.models import Company

        slug = options.get('company')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                "No company to process — nothing done."))
            return

        total = 0
        for company in companies:
            result = controle_integrite(company)
            n = total_anomalies(result)
            total += n
            if n:
                _notify_anomalies(company, result, n)

        self.stdout.write(self.style.SUCCESS(
            f"Contrôle d'intégrité exécuté pour {len(companies)} société(s) : "
            f"{total} anomalie(s) au total (aucune correction automatique)."))


def _notify_anomalies(company, result, n):
    """Notifie les admins/responsables de la société — best-effort, ne lève
    jamais (une erreur de diffusion n'interrompt jamais le contrôle des
    sociétés suivantes)."""
    try:
        from django.contrib.auth import get_user_model
        from apps.notifications.services import notify_many
        from apps.notifications.models import EventType

        User = get_user_model()
        familles_en_anomalie = [
            v['label'] for v in result.values() if v['ids']]
        titre = f"Contrôle d'intégrité : {n} anomalie(s) détectée(s)"
        corps = 'Familles concernées : ' + '; '.join(familles_en_anomalie)
        recipients = User.objects.filter(
            company=company, is_active=True,
            role_legacy__in=['admin', 'responsable'])
        notify_many(recipients, EventType.DIGEST, titre, body=corps,
                    company=company)
    except Exception:  # pragma: no cover - défensif, best-effort
        pass
