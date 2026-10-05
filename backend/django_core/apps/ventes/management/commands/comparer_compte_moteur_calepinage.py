"""ACAL331 (D-ACAL-17, C-ACAL-145) — DRY-RUN « compte moteur vs compte du
devis », exigé AVANT de lever ``USE_MOTEUR_CALEPINAGE``.

Pour chaque devis BROUILLON lié à un calepinage : compte de panneaux STOCKÉ
(lignes du devis) / compte du MOTEUR partagé (``core/calepinage``) / écart, par
``ventes.selectors.comparaison_calepinage_devis`` — la seule lecture qui
confronte les deux, et qui REFUSE de comparer un devis déjà émis (« un devis
déjà émis n'est jamais recalculé »).

LECTURE SEULE : aucun devis, aucune ligne, aucun calepinage n'est écrit.

    python manage.py comparer_compte_moteur_calepinage [--company SLUG]
        [--devis REFERENCE] [--json]
"""
import json

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('ACAL331 — compare (lecture seule) le compte de panneaux des '
            'devis brouillons au compte du moteur de calepinage.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')
        parser.add_argument(
            '--devis', default=None,
            help="Référence d'UN devis (un devis non brouillon est refusé, "
                 'jamais recalculé).')
        parser.add_argument(
            '--json', action='store_true', default=False,
            help='Sortie JSON (une liste de lignes).')

    def handle(self, *args, **options):
        from apps.calepinage.selectors import calepinage_du_devis
        from apps.ventes.domain.geometrie import moteur_calepinage_actif
        from apps.ventes.models import Devis
        from apps.ventes.selectors import comparaison_calepinage_devis

        qs = (Devis.objects.select_related('company')
              .prefetch_related('lignes').order_by('company_id', 'reference'))
        if options.get('devis'):
            qs = qs.filter(reference=options['devis'])
        else:
            qs = qs.filter(statut=Devis.Statut.BROUILLON)
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        lignes = []
        for devis in qs.iterator(chunk_size=200):
            calepinage = calepinage_du_devis(devis.pk, devis.company)
            if calepinage is None and not options.get('devis'):
                continue
            comparaison = comparaison_calepinage_devis(devis) or {}
            lignes.append({
                'societe': devis.company.slug if devis.company_id else None,
                'devis': devis.reference,
                'statut': devis.statut,
                'calepinage': getattr(calepinage, 'pk', None),
                'recalculable': comparaison.get('recalculable'),
                'compte_stocke': comparaison.get('compte_stocke'),
                'compte_moteur': comparaison.get('compte_moteur'),
                'ecart': comparaison.get('ecart'),
                'motif': comparaison.get('motif') or '',
            })

        if options.get('json'):
            self.stdout.write(json.dumps(
                {'drapeau_actif': moteur_calepinage_actif(),
                 'lecture_seule': True, 'devis': lignes},
                ensure_ascii=False, indent=2))
            return
        self.stdout.write(
            'DRY-RUN (lecture seule) — USE_MOTEUR_CALEPINAGE %s.'
            % ('LEVÉ' if moteur_calepinage_actif() else 'baissé (défaut)'))
        self.stdout.write(
            'société | devis | statut | calepinage | stocké | moteur | écart '
            '| motif')
        for ligne in lignes:
            self.stdout.write(
                '  {societe} | {devis} | {statut} | {calepinage} | '
                '{compte_stocke} | {compte_moteur} | {ecart} | {motif}'
                .format(**ligne))
        self.stdout.write('Devis comparés : %d' % len(lignes))
