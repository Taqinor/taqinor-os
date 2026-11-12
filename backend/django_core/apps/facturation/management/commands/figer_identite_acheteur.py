# -*- coding: utf-8 -*-
"""ASUP1 (C-ASUP-001) — fige l'identité de l'acheteur des factures DÉJÀ émises.

    python manage.py figer_identite_acheteur              # défaut : lecture seule
    python manage.py figer_identite_acheteur --appliquer

Une facture non brouillon SANS instantané ``identite_acheteur`` (émise avant
AARG27) relit le client VIVANT : « Anonymiser (RGPD) » effacerait l'acheteur
de son PDF, de son UBL et de l'export DGI. Le dry-run liste
référence | client | statut ; les factures d'un client déjà anonymisé sont
listées à part (« identité déjà perdue ») et jamais figées. ``--appliquer``
copie l'identité du jour via ``figer_identite_acheteur_manquante`` (survivant
unique). Idempotente : une facture figée n'est plus listée. Jouée une fois par
Reda après lecture du dry-run.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ("ASUP1 — fige l'identité de l'acheteur des factures non brouillon "
            "qui n'en ont pas. Lecture seule par défaut ; --appliquer pour "
            "écrire.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--appliquer', action='store_true',
            help="Figer réellement les identités listées.")

    def _ligne(self, facture):
        client = facture.client
        nom = ' '.join(p for p in (client.nom, client.prenom) if p)
        self.stdout.write(f'{facture.reference} | {nom} | {facture.statut}')

    def handle(self, *args, **opts):
        from apps.facturation.services import (
            figer_identite_acheteur_manquante,
        )
        appliquer = bool(opts['appliquer'])
        a_figer, perdues = figer_identite_acheteur_manquante(
            appliquer=appliquer)
        self.stdout.write('référence | client | statut')
        for facture in a_figer:
            self._ligne(facture)
        if perdues:
            self.stdout.write('identité déjà perdue (client anonymisé) :')
            for facture in perdues:
                self._ligne(facture)
        mode = 'APPLIQUÉ' if appliquer else 'DRY-RUN (aucune écriture)'
        self.stdout.write(
            f'{mode} — {len(a_figer)} facture(s) sans identité figée, '
            f'{len(a_figer) if appliquer else 0} figée(s), '
            f'{len(perdues)} à identité déjà perdue.')
