"""ACAL1955 (D-ACAL-89) — les calepinages restés sur un brouillon jamais envoyé
alors que leur lead a un devis ENVOYÉ (ou accepté), et leur re-liaison.

SANS option : LISTE seulement (aucune écriture), une ligne par calepinage :

    calepinage | devis lié (brouillon) | devis envoyé

``--appliquer`` : re-lie chacun au devis envoyé (``services.liens.
suivre_devis_envoye`` — la même règle que l'abonné de ``devis_sent``), ligne de
journal comprise. Le brouillon quitté ne garde rien.

    python manage.py relier_calepinages_devis_envoye [--company <slug>] [--appliquer]
"""
from __future__ import annotations

from django.apps import apps as registre
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('ACAL1955 — liste (ou, avec --appliquer, re-lie) les calepinages '
            'restés sur un brouillon alors que le lead a un devis envoyé.')

    def add_arguments(self, parser):
        parser.add_argument('--company', default=None,
                            help='Slug de société (défaut : toutes les sociétés).')
        parser.add_argument('--appliquer', action='store_true',
                            help='Re-lie (sans cette option : liste seulement).')

    def handle(self, *args, **options):
        from apps.calepinage.services.liens import (
            LiaisonRefusee, candidat_suivi_devis_envoye, dernier_devis_recu,
            suivre_devis_envoye,
        )

        Calepinage = registre.get_model('calepinage', 'Calepinage')
        qs = (Calepinage.objects.filter(devis__isnull=False, lead_id__isnull=False)
              .select_related('company').order_by('company_id', 'pk'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])
        appliquer = bool(options.get('appliquer'))
        ecrire = self.stdout.write
        ecrire('ACAL1955 — %s' % ('RE-LIAISON' if appliquer else 'LISTE (aucune écriture)'))
        ecrire('calepinage | devis lié | devis envoyé')
        vus, total = set(), 0
        for calepinage in qs.iterator(chunk_size=200):
            cle = (calepinage.company_id, calepinage.lead_id)
            if cle in vus:
                continue
            vus.add(cle)
            envoye = dernier_devis_recu(calepinage.company, calepinage.lead_id)
            candidat = candidat_suivi_devis_envoye(envoye) if envoye is not None else None
            if candidat is None:
                continue
            ouvert, lie = candidat
            total += 1
            ligne = '%s | %s | %s' % (ouvert.pk, lie.pk, envoye.pk)
            if appliquer:
                try:
                    suivre_devis_envoye(envoye)
                    ligne += ' | re-lié'
                except LiaisonRefusee as refus:
                    ligne += ' | refusé : %s' % refus
            ecrire(ligne)
        ecrire('%d calepinage(s) %s.' % (total, 'traité(s)' if appliquer else 'à re-lier'))
