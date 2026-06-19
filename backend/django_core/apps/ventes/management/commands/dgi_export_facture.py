"""N105 — Commande de gestion : export DGI local d'une facture, à la demande.

    python manage.py dgi_export_facture <reference> [--company <id|slug>]
        [--out <chemin.xml>] [--check-only]

Atteignable UNIQUEMENT par programme. La capacité est gardée par l'interrupteur
maître ``CompanyProfile.dgi_export_actif`` (défaut OFF) : tant qu'il est OFF
pour la société de la facture, la commande refuse de produire quoi que ce soit
et explique comment l'armer dans Paramètres — la capacité reste ainsi invisible
et sans effet tant que le founder ne l'arme pas.

  * Sans ``--check-only`` : valide PUIS imprime le XML UBL 2.1 (ou l'écrit dans
    ``--out``). Une facture non conforme produit quand même son XML, mais les
    problèmes sont signalés sur stderr (groundwork, jamais bloquant côté DGI).
  * Avec ``--check-only`` : n'imprime QUE le rapport de conformité.

Ne change AUCUN statut, n'écrit aucun champ sur la facture, ne transmet rien.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ("N105 — Export DGI local (UBL 2.1) + contrôle de conformité d'une "
            "facture, à la demande. Gardé par l'interrupteur maître "
            "dgi_export_actif (défaut OFF).")

    def add_arguments(self, parser):
        parser.add_argument('reference', help="Référence de la facture.")
        parser.add_argument(
            '--company', default=None,
            help="Société (id ou slug) si la référence n'est pas unique.")
        parser.add_argument(
            '--out', default=None,
            help="Écrire le XML dans ce fichier au lieu de stdout.")
        parser.add_argument(
            '--check-only', action='store_true',
            help="N'imprimer que le rapport de conformité (pas de XML).")

    def handle(self, *args, **options):
        from apps.ventes.models import Facture
        from apps.parametres.models import CompanyProfile
        from apps.ventes.dgi import (
            build_ubl_xml, validate_dgi_conformity, is_dgi_enabled)

        qs = Facture.objects.filter(reference=options['reference'])
        company_arg = options.get('company')
        if company_arg:
            from authentication.models import Company
            company = (Company.objects.filter(slug=company_arg).first()
                       or (Company.objects.filter(pk=company_arg).first()
                           if str(company_arg).isdigit() else None))
            if company is None:
                raise CommandError(f"Société inconnue : {company_arg}")
            qs = qs.filter(company=company)

        factures = list(qs)
        if not factures:
            raise CommandError(
                f"Facture introuvable : {options['reference']}")
        if len(factures) > 1:
            raise CommandError(
                "Plusieurs factures portent cette référence ; précisez "
                "--company.")
        facture = factures[0]

        # Interrupteur maître (par société). OFF ⇒ capacité invisible/inerte.
        if not is_dgi_enabled(facture.company):
            raise CommandError(
                "Capacité DGI locale désarmée pour cette société. Activez "
                "« dgi_export_actif » dans Paramètres (défaut OFF) avant "
                "d'exporter.")

        profile = CompanyProfile.get(company=facture.company)
        problemes = validate_dgi_conformity(facture, profile)
        if problemes:
            self.stderr.write("Conformité DGI — problèmes détectés :")
            for p in problemes:
                self.stderr.write(f"  - {p}")
        else:
            self.stderr.write("Conformité DGI : OK.")

        if options['check_only']:
            return

        xml = build_ubl_xml(facture, profile)
        if options['out']:
            with open(options['out'], 'w', encoding='utf-8') as fh:
                fh.write(xml)
            self.stderr.write(
                f"XML écrit dans {options['out']} ({facture.reference}).")
        else:
            self.stdout.write(xml)
