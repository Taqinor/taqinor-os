"""Ingestion e-mail entrante : crée des tâches depuis l'alias d'un projet (ZPRJ12).

Réutilise le MÊME mécanisme d'ingestion que ``apps.ventes.inbound_email``
(no-op propre sans clé/hôte configuré) — voir
``apps.gestion_projet.services.ingest_email_projet`` (parsing pur, sans appel
réseau ici : ce squelette de commande est le point d'entrée pour un futur
webhook/poll IMAP, il ne fait rien de plus qu'appeler la fonction pure avec les
messages qu'on lui passe).

Run (dans le conteneur django_core ou avec les variables DB) :
  python manage.py ingest_emails_projets --company taqinor-demo \\
      --to alias@taqinor.ma --subject "Objet" --body "Corps" \\
      --from client@example.com
"""
from django.core.management.base import BaseCommand, CommandError

from apps.gestion_projet.services import (
    ingest_email_projet, is_email_ingestion_configured,
)


class Command(BaseCommand):
    help = (
        "Ingère UN e-mail entrant (paramètres --to/--subject/--body/--from) "
        "vers l'alias d'un projet de --company : crée une Tache du bon "
        "projet/société si l'alias est reconnu. No-op propre si l'ingestion "
        "e-mail n'est pas configurée, ou si l'alias est inconnu."
    )

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True,
                            help="Slug de la société.")
        parser.add_argument('--to', required=True, dest='to',
                            help="Adresse e-mail destinataire (alias projet).")
        parser.add_argument('--subject', default='', help="Objet du mail.")
        parser.add_argument('--body', default='', help="Corps du mail.")
        parser.add_argument('--from', default='', dest='from',
                            help="Adresse e-mail expéditrice.")

    def handle(self, *args, **options):
        from authentication.models import Company

        if not is_email_ingestion_configured():
            self.stdout.write(self.style.WARNING(
                "Ingestion e-mail non configurée — no-op."))
            return

        slug = options['company']
        try:
            company = Company.objects.get(slug=slug)
        except Company.DoesNotExist:
            raise CommandError(f"Company with slug '{slug}' not found.")

        tache = ingest_email_projet(
            company, to_alias=options['to'],
            subject=options['subject'], body=options['body'],
            from_email=options['from'])

        if tache is None:
            self.stdout.write(self.style.WARNING(
                "Alias inconnu ou ingestion non configurée — aucune tâche "
                "créée."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"Tâche #{tache.id} créée sur le projet {tache.projet.code}."))
