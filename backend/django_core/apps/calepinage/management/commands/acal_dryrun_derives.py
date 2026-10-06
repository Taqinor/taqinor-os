"""ACAL191 (D-ACAL-13) — DRY-RUN : les calepinages dont le GPS du lead a été
corrigé après le tracé (dérive du repère), à soumettre au fondateur.

Liste, calepinage par calepinage (seuls ceux en dérive) :

    calepinage | ancien pin → nouveau pin | écart (m) | état | devis lié

LECTURE SEULE : aucun calepinage, aucun devis n'est réécrit (la translation
ne part que du geste « Recentrer » de l'atelier).

    python manage.py acal_dryrun_derives [--company <slug>]
"""
from __future__ import annotations

from django.apps import apps as registre
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('ACAL191 — liste (lecture seule) les calepinages dont le repère '
            'du lead a dérivé depuis le tracé.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        from apps.calepinage.services.repere import inventaire_derives

        Calepinage = registre.get_model('calepinage', 'Calepinage')
        qs = (Calepinage.objects.exclude(roof_layout__isnull=True)
              .select_related('company').order_by('company_id', 'pk'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        ecrire = self.stdout.write
        ecrire('DRY-RUN ACAL191 (lecture seule) — aucune écriture.')
        ecrire('calepinage | ancien pin → nouveau pin | écart (m) | état | '
               'devis lié')
        lignes = inventaire_derives(qs.iterator(chunk_size=200))
        for ligne in lignes:
            ecrire('%s | %s → %s | %s | %s | %s' % (
                ligne['calepinage'], ligne['ancien_pin'], ligne['nouveau_pin'],
                ligne['ecart_m'], ligne['etat'], ligne['devis'] or '—'))
        ecrire('%d calepinage(s) en dérive.' % len(lignes))
