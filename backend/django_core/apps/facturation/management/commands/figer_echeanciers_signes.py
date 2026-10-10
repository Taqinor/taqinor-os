# -*- coding: utf-8 -*-
"""AMET3 (C-AMET-003, D-ECH-FIGE) — fige l'échéancier des devis DÉJÀ signés.

    python manage.py figer_echeanciers_signes --dry-run      # défaut : lecture seule
    python manage.py figer_echeanciers_signes --appliquer

Un devis accepté SANS échéancier propre lit encore les conditions société EN
DIRECT (``tranches_normalisees``) : changer les réglages réécrit ses tranches.
AMET1 fige à l'acceptation ; cette commande rattrape les devis acceptés avant.
Le dry-run liste référence | tranches actuelles | tranches figées ;
``--appliquer`` copie les conditions société du jour via ``figer_echeancier``
(survivant unique). Idempotente : un devis figé n'est plus listé.
Jouée une fois par Reda après lecture du dry-run.
"""
from django.core.management.base import BaseCommand, CommandError


def _sans_echeancier_propre(devis):
    from apps.ventes.utils.echeancier import (
        EcheancierInvalide, valider_echeancier,
    )
    propre = getattr(devis, 'echeancier', None)
    if not propre:
        return True
    try:
        return not valider_echeancier(propre, controler_somme=False)
    except EcheancierInvalide:
        return True


def _texte(tranches):
    from apps.ventes.utils.echeancier import UNITE_PCT
    return ' / '.join(
        f"{t['key']} {t['valeur']}{' %' if t.get('unite', UNITE_PCT) == UNITE_PCT else ' DH'}"
        for t in tranches)


class Command(BaseCommand):
    help = ("AMET3 — fige l'échéancier des devis acceptés sans échéancier "
            "propre (conditions société du jour). --dry-run par défaut ; "
            "--appliquer pour écrire.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="Lister sans rien écrire (comportement par défaut).")
        parser.add_argument(
            '--appliquer', action='store_true',
            help="Figer réellement les échéanciers listés.")

    def handle(self, *args, **opts):
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import (
            figer_echeancier, tranches_normalisees,
        )
        if opts['dry_run'] and opts['appliquer']:
            raise CommandError("--dry-run et --appliquer sont exclusifs.")
        appliquer = bool(opts['appliquer'])
        cibles = [d for d in Devis.objects.filter(statut=Devis.Statut.ACCEPTE)
                  .order_by('pk') if _sans_echeancier_propre(d)]
        self.stdout.write('référence | tranches actuelles | tranches figées')
        figes = 0
        for devis in cibles:
            actuelles = tranches_normalisees(devis)
            if appliquer:
                figer_echeancier(devis)
                figes += 1
                figees = tranches_normalisees(devis)
            else:
                figees = actuelles  # copie des conditions société du jour
            self.stdout.write(
                f'{devis.reference} | {_texte(actuelles)} | {_texte(figees)}')
        mode = 'APPLIQUÉ' if appliquer else 'DRY-RUN (aucune écriture)'
        self.stdout.write(
            f'{mode} — {len(cibles)} devis sans échéancier propre, '
            f'{figes} figé(s).')
