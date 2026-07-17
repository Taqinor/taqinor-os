"""NTIDE41 — ``manage.py export_feedback_produit [--company SLUG]
[--since YYYY-MM-DD] [--theme ux|performance|feature|bug|autre]
[--format json|csv] [--out-file PATH]``.

Exporte le feedback produit (canal founder, NTIDE36) — JAMAIS d'API
publique : ce canal est délibérément une commande manuelle, délivrée au
founder à la main (cf. critère d'acceptation NTIDE41), jamais un endpoint
HTTP exposé. Sans ``--company`` : exporte TOUTES les sociétés (chaque ligne
porte son propre slug de société, même convention que ``export_ideas``,
NTIDE24). Sans ``--out-file`` : écrit sur stdout (redirigeable).

Exemples :
  python manage.py export_feedback_produit --since=2026-07-01 --theme=feature
  python manage.py export_feedback_produit --format=csv --out-file=/tmp/fb.csv
"""
import csv
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.innovation.models import FeedbackProduit

FEEDBACK_FIELDS = (
    'titre', 'description', 'theme', 'statut', 'message_fermeture',
)


def _feedback_to_dict(feedback):
    data = {f: getattr(feedback, f) for f in FEEDBACK_FIELDS}
    data['company'] = feedback.company.slug
    data['auteur'] = (
        getattr(feedback.auteur, 'username', None)
        if feedback.auteur_id else None)
    data['annonce'] = feedback.annonce.titre if feedback.annonce_id else None
    data['date_creation'] = (
        feedback.created_at.isoformat() if feedback.created_at else None)
    return data


class Command(BaseCommand):
    help = (
        'Exporte le feedback produit (NTIDE36) en JSON/CSV — jamais via '
        'API publique, délivré au founder manuellement. --since filtre par '
        'date de création (>=) ; --theme filtre par thème ; --company '
        'filtre par slug société (vide = toutes).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug de la société à exporter (vide = toutes).')
        parser.add_argument(
            '--since', default=None,
            help='Date ISO (YYYY-MM-DD) : ne garde que le feedback créé '
                 'depuis cette date (incluse).')
        parser.add_argument(
            '--theme', default=None,
            choices=[v for v, _ in FeedbackProduit.Theme.choices],
            help='Filtre par thème (ux/performance/feature/bug/autre).')
        parser.add_argument(
            '--format', default='json', choices=['json', 'csv'],
            help='Format de sortie (défaut : json).')
        parser.add_argument(
            '--out-file', default=None,
            help='Fichier de sortie (défaut : stdout).')

    def handle(self, *args, **opts):
        from authentication.models import Company

        qs = FeedbackProduit.objects.select_related(
            'company', 'auteur', 'annonce').all()

        slug = opts.get('company')
        if slug:
            try:
                company = Company.objects.get(slug=slug)
            except Company.DoesNotExist:
                raise CommandError(f'Société introuvable : {slug}')
            qs = qs.filter(company=company)

        since = opts.get('since')
        if since:
            qs = qs.filter(created_at__date__gte=since)

        theme = opts.get('theme')
        if theme:
            qs = qs.filter(theme=theme)

        rows = [_feedback_to_dict(f)
                for f in qs.order_by('company_id', '-created_at')]

        out_file = opts.get('out_file')
        fmt = opts.get('format')
        stream = open(out_file, 'w', newline='', encoding='utf-8') if out_file \
            else sys.stdout

        try:
            if fmt == 'csv':
                fieldnames = (
                    ['company', 'auteur'] + list(FEEDBACK_FIELDS)
                    + ['annonce', 'date_creation'])
                writer = csv.DictWriter(stream, fieldnames=fieldnames)
                writer.writeheader()
                for row in rows:
                    writer.writerow(row)
            else:
                json.dump(rows, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
        finally:
            if out_file:
                stream.close()

        if out_file:
            self.stdout.write(self.style.SUCCESS(
                f'{len(rows)} feedback(s) exporté(s) → {out_file}'))
