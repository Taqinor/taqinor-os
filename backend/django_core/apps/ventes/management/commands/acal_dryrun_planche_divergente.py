"""ACAL46 (C-ACAL-112) — DRY-RUN : les devis ENVOYÉS dont la planche de
calepinage disparaîtra du prochain PDF.

Le moteur PDF omet désormais la planche (et l'affiche) quand le calepinage
LIÉ a divergé du devis (``Calepinage.layout_hash != Devis.layout_hash``).
Cette commande liste, AVANT le merge, les devis envoyés concernés — la page
« Calepinage » sera retirée à leur prochain rendu — pour la décision du
fondateur : société / référence / mode / calepinage / panneaux devis →
calepinage / quand la planche s'imprimait (AUTO en industriel, sur demande
explicite en résidentiel — QJR666).

LECTURE SEULE. ``--dry-run`` est le défaut ET le seul mode : aucun devis
n'est réécrit, aucun PDF régénéré.

    python manage.py acal_dryrun_planche_divergente [--company <slug>]
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('ACAL46 — liste (lecture seule) les devis envoyés dont le '
            'calepinage lié a divergé (planche retirée au prochain rendu).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', default=True,
            help="Défaut et seul mode : rien n'est jamais écrit.")
        parser.add_argument(
            '--company', default=None,
            help='Slug de société (défaut : toutes les sociétés).')

    def handle(self, *args, **options):
        from apps.calepinage.selectors import calepinage_du_devis
        from apps.ventes.models import Devis
        from apps.ventes.selectors import peremption_layout_devis

        qs = (Devis.objects.filter(statut=Devis.Statut.ENVOYE)
              .exclude(layout_hash='').exclude(layout_hash__isnull=True)
              .select_related('company').order_by('company_id', 'reference'))
        if options.get('company'):
            qs = qs.filter(company__slug=options['company'])

        self.stdout.write('DRY-RUN (lecture seule) — aucune écriture.')
        self.stdout.write(
            'société | référence | mode | calepinage | panneaux devis → '
            'calepinage | planche imprimée')
        nb = 0
        for devis in qs.iterator(chunk_size=200):
            calepinage = calepinage_du_devis(devis.pk, devis.company)
            if calepinage is None:
                continue
            verdict = peremption_layout_devis(devis, calepinage=calepinage)
            if not verdict.get('conception_divergente'):
                continue
            nb += 1
            mode = getattr(devis, 'mode_installation', '') or 'residentiel'
            quand = ('AUTO' if mode == 'industriel'
                     else 'sur demande explicite')
            self.stdout.write(
                f'  {devis.company.slug} | {devis.reference} | {mode} | '
                f'#{calepinage.pk} | {verdict.get("layout_nb_panneaux")} → '
                f'{verdict.get("calepinage_nb_panneaux")} | {quand}')
        self.stdout.write(f'Devis concernés : {nb}')
