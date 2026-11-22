"""ACAL331 (D-ACAL-17, C-ACAL-145) — DRY-RUN « compte moteur vs compte du
devis », exigé AVANT de lever ``USE_MOTEUR_CALEPINAGE``.

Pour chaque devis BROUILLON lié à un calepinage : compte de panneaux STOCKÉ
(lignes du devis) / compte du MOTEUR partagé (``core/calepinage``) / écart, par
``ventes.selectors.comparaison_calepinage_devis`` — la seule lecture qui
confronte les deux, et qui REFUSE de comparer un devis déjà émis (« un devis
déjà émis n'est jamais recalculé »).

LECTURE SEULE : aucun devis, aucune ligne, aucun calepinage n'est écrit.

    python manage.py comparer_compte_moteur_calepinage [--company SLUG]
        [--devis REFERENCE] [--json] [--calepinages]
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
        parser.add_argument('--calepinages', action='store_true', default=False,
                            help='ACAL1173 — DESSIN de chaque calepinage actif vs moteur (lecture seule).')

    def _calepinages(self, options):
        """ACAL1173 — par calepinage actif : lead, dessin, moteur, écart, motif ; un total."""
        from apps.calepinage.selectors import calepinages_actifs, mesures_du_calepinage
        from apps.ventes.domain.geometrie import compte_moteur_du_layout, moteur_calepinage_actif
        from authentication.models import Company

        societes = Company.objects.order_by('pk')
        if options.get('company'):
            societes = societes.filter(slug=options['company'])
        lignes = []
        for societe in societes:
            for cal in calepinages_actifs(societe).order_by('pk'):
                dessin = mesures_du_calepinage(cal).get('modules')
                moteur = (compte_moteur_du_layout(cal.roof_layout, company=societe) or {}).get('modules')
                lignes.append({'societe': societe.slug, 'calepinage': cal.pk, 'lead': cal.lead_id,
                               'dessin': dessin, 'moteur': moteur,
                               'ecart': None if None in (moteur, dessin) else moteur - dessin,
                               'motif': '' if moteur is not None else 'aucune géométrie exploitable'})
        total = {'calepinages': len(lignes), 'ecart': sum(li['ecart'] or 0 for li in lignes)}
        if options.get('json'):
            self.stdout.write(json.dumps(
                {'drapeau_actif': moteur_calepinage_actif(), 'lecture_seule': True,
                 'calepinages': lignes, 'total': total}, ensure_ascii=False, indent=2))
            return
        self.stdout.write('DRY-RUN (lecture seule) — société | calepinage | lead | dessin | moteur | écart | motif')
        gabarit = '  {societe} | {calepinage} | {lead} | {dessin} | {moteur} | {ecart} | {motif}'
        for ligne in lignes:
            self.stdout.write(gabarit.format(**ligne))
        self.stdout.write('Calepinages comparés : {calepinages} ; écart total : {ecart}'.format(**total))

    def handle(self, *args, **options):
        if options.get('calepinages'):
            self._calepinages(options)
            return

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
