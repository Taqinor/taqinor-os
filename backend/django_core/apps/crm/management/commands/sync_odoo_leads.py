"""Odoo → ERP sans IA : rapatrie et aligne les leads sur le pipeline Odoo.

  python manage.py sync_odoo_leads --company <slug-ou-id> [--dry-run]

Enchaîne, via l'API JSON-2 uniquement (lecture seule côté Odoo) :
  1. rapatriement de TOUS les crm.lead (archivés compris) + tags ;
  2. import idempotent (réutilise ``import_odoo_leads`` : zéro doublon,
     jamais d'écrasement d'une saisie existante, société forcée) ;
  3. alignement des étapes ERP sur le pipeline Odoo EN AVANT SEULEMENT
     (D-CRX3, 02/09/2026), journalisé dans le chatter par la façade
     ``activity`` et émetteur de ``lead_stage_changed``. Une étape Odoo en
     retrait, ou hors table de correspondance, n'écrit RIEN : elle est
     signalée au rapport pour arbitrage humain.

Sans ODOO_SYNC_URL + ODOO_SYNC_API_KEY dans l'environnement, ne fait RIEN
(usage + sortie propre). ``--dry-run`` : compte tout, n'écrit rien.
"""
import json
import os
import tempfile

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.crm.odoo_sync import (
    OdooConfig, OdooSyncError, align_stages_from_rows, build_rows,
    fetch_odoo_leads)

# Plafond d'affichage des régressions détaillées (le total reste au rapport).
_MAX_REGRESSIONS_AFFICHEES = 50


class Command(BaseCommand):
    help = ("Odoo → ERP : rapatrie les leads via l'API JSON-2, importe "
            "(idempotent) puis aligne les étapes sur le pipeline Odoo.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', dest='company', default=None,
            help="Slug ou id de la société cible (obligatoire).")
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'écrit rien : compte créations, mises à jour et "
                 "déplacements d'étape.")

    def _resolve_company(self, raw):
        from authentication.models import Company
        if raw is None:
            return None
        company = Company.objects.filter(slug=raw).first()
        if company is None and str(raw).isdigit():
            company = Company.objects.filter(pk=int(raw)).first()
        return company

    def handle(self, *args, **options):
        config = OdooConfig()
        if config.incomplete:
            self.stdout.write(self.style.WARNING(
                "Config Odoo absente — rien à synchroniser.\n"
                "Renseigner ODOO_SYNC_URL et ODOO_SYNC_API_KEY (clé créée "
                "dans Odoo : Préférences ▸ Sécurité du compte ▸ Nouvelle "
                "clé API), puis relancer."))
            return
        company = self._resolve_company(options.get('company'))
        if company is None:
            raise CommandError(
                "--company <slug-ou-id> est obligatoire et doit correspondre "
                "à une société existante.")
        dry_run = options.get('dry_run')

        try:
            odoo_leads, tag_names = fetch_odoo_leads(config)
        except OdooSyncError as exc:
            raise CommandError(str(exc))
        self.stdout.write(
            f"{len(odoo_leads)} lead(s) rapatriés d'Odoo "
            f"({len(tag_names)} tag(s)).")

        rows = build_rows(odoo_leads, tag_names)

        # Fichier temporaire PII : jamais committé, supprimé quoi qu'il arrive.
        fd, path = tempfile.mkstemp(suffix='.json')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as fh:
                json.dump({'leads': rows}, fh, ensure_ascii=False)
            call_command(
                'import_odoo_leads', path,
                company=str(company.pk), dry_run=dry_run)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

        rapport = align_stages_from_rows(
            company, rows, apply_changes=not dry_run)
        prefix = '[dry-run] ' if dry_run else ''
        for (src, dst), n in sorted(rapport.moves.items()):
            self.stdout.write(f'{prefix}étape {src} → {dst} : {n}')
        if rapport.corbeille:
            self.stdout.write(self.style.WARNING(
                f"{prefix}{rapport.corbeille} lead(s) en corbeille ignoré(s) — "
                "jamais restauré(s) automatiquement."))
        if rapport.inconnus:
            self.stdout.write(self.style.WARNING(
                f"{prefix}{rapport.inconnus} lead(s) laissés intouchés : "
                "étape Odoo hors table de correspondance."))
        if rapport.doublons_odoo:
            self.stdout.write(self.style.WARNING(
                f"{prefix}{rapport.doublons_odoo} ligne(s) Odoo retombant sur "
                "une fiche ERP déjà traitée (doublons internes à Odoo) — la "
                "première ligne gagne."))
        # D-CRX3 — une étape Odoo EN RETRAIT ne fait JAMAIS reculer l'ERP :
        # elle est signalée pour arbitrage humain, sans aucune écriture.
        for pk, nom, stage_erp, stage_odoo, cible in \
                rapport.regressions[:_MAX_REGRESSIONS_AFFICHEES]:
            self.stdout.write(self.style.WARNING(
                f"{prefix}Régression NON appliquée — lead #{pk} « {nom} » : "
                f"ERP {stage_erp} / Odoo « {stage_odoo} » ({cible})."))
        reste = len(rapport.regressions) - _MAX_REGRESSIONS_AFFICHEES
        if reste > 0:
            self.stdout.write(self.style.WARNING(
                f"{prefix}… et {reste} autre(s) régression(s) non appliquée(s)."))
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}Alignement : {sum(rapport.moves.values())} avancé(s), "
            f"{rapport.deja_ok} déjà aligné(s), "
            f"{rapport.introuvables} non rapproché(s), "
            f"{rapport.corbeille} en corbeille, "
            f"{rapport.inconnus} étape Odoo inconnue, "
            f"{rapport.doublons_odoo} doublon(s) Odoo, "
            f"{len(rapport.regressions)} régression(s) signalée(s) "
            "(aucune écriture)."))
