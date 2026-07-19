"""PUB38 — Rapport d'incrémentalité geo-holdout (zone tenue vs zones actives).

    python manage.py geo_holdout_report --company <slug-ou-id> \\
        --villes "Agadir,Essaouira" \\
        --baseline-debut 2026-01-01 --baseline-fin 2026-03-31 \\
        --test-debut 2026-04-01 --test-fin 2026-06-30

Compare, sur données ERP RÉELLES (leads/signatures par ville), l'évolution de
la zone TENUE (villes où la pub a été coupée MANUELLEMENT par le fondateur —
cette commande ne pause RIEN) à celle de la zone ACTIVE (le reste des villes
connues de la société), entre une fenêtre de référence (baseline) et une
fenêtre test. **N'ÉCRIT RIEN, ne modifie AUCUNE campagne** — lecture seule,
délègue tout le calcul à ``apps.adsengine.incrementality.geo_holdout_report``.
"""
import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Rapport LECTURE SEULE d\'incrémentalité geo-holdout (zone tenue '
            'vs zones actives, données ERP réelles). Aucune action auto.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', required=True,
            help='Slug ou id de la société.')
        parser.add_argument(
            '--villes', dest='villes', required=True,
            help='Villes de la zone tenue, séparées par des virgules '
                 '(ex. "Agadir,Essaouira").')
        parser.add_argument(
            '--baseline-debut', dest='baseline_debut', required=True,
            help='Début de la période de référence (YYYY-MM-DD).')
        parser.add_argument(
            '--baseline-fin', dest='baseline_fin', required=True,
            help='Fin de la période de référence (YYYY-MM-DD).')
        parser.add_argument(
            '--test-debut', dest='test_debut', required=True,
            help='Début de la période test (YYYY-MM-DD).')
        parser.add_argument(
            '--test-fin', dest='test_fin', required=True,
            help='Fin de la période test (YYYY-MM-DD).')
        parser.add_argument(
            '--json', dest='as_json', action='store_true',
            help='Imprime le rapport complet en JSON (en plus du résumé FR).')

    def _resolve_company(self, raw):
        from authentication.models import Company
        company = Company.objects.filter(slug=raw).first()
        if company is None and str(raw).isdigit():
            company = Company.objects.filter(pk=int(raw)).first()
        return company

    def handle(self, *args, **options):
        from apps.adsengine.incrementality import (
            _parse_iso_date, geo_holdout_report,
        )

        company = self._resolve_company(options['company'])
        if company is None:
            raise CommandError(f"Société « {options['company']} » introuvable.")

        villes = [v.strip() for v in options['villes'].split(',') if v.strip()]
        report = geo_holdout_report(
            company, held_villes=villes,
            baseline_start=_parse_iso_date(options['baseline_debut']),
            baseline_end=_parse_iso_date(options['baseline_fin']),
            test_start=_parse_iso_date(options['test_debut']),
            test_end=_parse_iso_date(options['test_fin']))

        if not report['valide']:
            raise CommandError(report['erreur_fr'])

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Rapport geo-holdout — ' + company.nom))
        self.stdout.write(report['message_fr'])
        self.stdout.write('')
        if options.get('as_json'):
            self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False))
