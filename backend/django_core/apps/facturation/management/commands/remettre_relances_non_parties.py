# -*- coding: utf-8 -*-
"""AMSG30 (C-AMSG-008, D-AMSG-5 = remettre_niveau_1) — rend leur relance aux
factures en retard dont les niveaux automatiques ont été consommés sans envoi.

    python manage.py remettre_relances_non_parties --jusqu-au 2026-10-08
    python manage.py remettre_relances_non_parties --jusqu-au 2026-10-08 \\
        --appliquer --factures 12 34

Le dry-run (défaut) liste les factures EN RETARD portant des ``RelanceLog``
automatiques e-mail (note « Relance automatique programmée (email). », sans
auteur) encore comptées dans la cadence et datées au plus tard de
``--jusqu-au``. ``--appliquer --factures <ids>`` passe ces seules traces à
``compte_dans_cadence=False`` (historique gardé, rien effacé) puis amorce la
cadence (``amorcer_cadence``) : la facture repart au niveau 1. Idempotente.
Jouée par Reda après lecture du dry-run.
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


def relances_non_parties(jusqu_au):
    """Les ``RelanceLog`` automatiques e-mail encore dans la cadence."""
    from apps.facturation.models import Facture, RelanceLog
    from apps.ventes.domain.recouvrement import RELANCE_AUTO_NOTE
    return RelanceLog.objects.filter(
        note=RELANCE_AUTO_NOTE, created_by__isnull=True,
        canal__in=('email', ''), compte_dans_cadence=True,
        date__lte=jusqu_au, facture__statut=Facture.Statut.EN_RETARD,
    ).select_related('facture', 'facture__client').order_by(
        'facture_id', 'date', 'id')


class Command(BaseCommand):
    help = ("AMSG30 — liste (dry-run) puis remet au niveau 1 les relances "
            "automatiques e-mail consignées sans envoi.")

    def add_arguments(self, parser):
        parser.add_argument('--jusqu-au', dest='jusqu_au', required=True,
                            help="Date AAAA-MM-JJ : relances consignées "
                                 "jusqu'à ce jour inclus.")
        parser.add_argument('--appliquer', action='store_true',
                            help="Écrire (exige --factures).")
        parser.add_argument('--factures', nargs='+', type=int, default=[],
                            help="Ids des factures à remettre au niveau 1.")

    def handle(self, *args, **opts):
        from apps.ventes.domain.recouvrement import amorcer_cadence
        try:
            jusqu_au = date.fromisoformat(opts['jusqu_au'])
        except ValueError:
            raise CommandError('--jusqu-au attend une date AAAA-MM-JJ.')
        if opts['appliquer'] and not opts['factures']:
            raise CommandError('--appliquer exige --factures <ids>.')
        par_facture = {}
        for log in relances_non_parties(jusqu_au):
            par_facture.setdefault(log.facture_id, []).append(log)
        self.stdout.write('id | référence | client | niveaux | dates')
        for logs in par_facture.values():
            f = logs[0].facture
            self.stdout.write(' | '.join([
                str(f.pk), f.reference, str(f.client or ''),
                ', '.join(str(r.niveau) for r in logs),
                ', '.join(r.date.isoformat() for r in logs)]))
        if not opts['appliquer']:
            self.stdout.write(f'DRY-RUN (aucune écriture) — '
                              f'{len(par_facture)} facture(s).')
            return
        remises = 0
        for fid in opts['factures']:
            logs = par_facture.get(fid)
            if not logs:
                continue
            with transaction.atomic():
                type(logs[0]).objects.filter(
                    pk__in=[r.pk for r in logs]).update(
                        compte_dans_cadence=False)
                amorcer_cadence(logs[0].facture)
            remises += 1
        self.stdout.write(f'APPLIQUÉ — {remises} facture(s) remise(s) '
                          f'au niveau 1.')
