"""ACAL102 — DRY-RUN : les devis dont la production (ou l'économie) IMPRIMÉE
changerait avec le passage de l'égalité devinée à la marque
``production_source`` (après le backfill de la migration ventes 0132).

Pour chaque devis portant un calepinage (``roof_layout.result``) :

* AVANT — l'ancien moteur (``builder.py`` @ 818241faa) : figure stockée
  absente ⇒ figure du layout recalée ; stockée ET égale à l'entier près
  (``_est_la_figure_du_calepinage``) ⇒ recalée ; sinon la stockée ;
* APRÈS — le moteur actuel : stockée absente ⇒ recalée ; marque
  ``production_source == 'calepinage'`` (déjà posée, ou posée par le
  backfill 0132 — même règle, importée de la migration) ⇒ recalée ; sinon la
  stockée.

Recalage = figure brute du layout × kWc des lignes / kWc du layout
(``domain.scenario.puissance_kwc_du_devis``, le propriétaire du kWc). Le
facteur est le MÊME des deux côtés : un écart ne naît que d'une DÉCISION
différente, ce que cette commande mesure.

LECTURE SEULE : tout s'exécute dans ``transaction.atomic()`` annulé
(``set_rollback(True)``) ; aucune écriture n'est faite.

    python manage.py dryrun_acal102 [--company <slug>]
"""
import importlib

from django.core.management.base import BaseCommand
from django.db import transaction

_BACKFILL = importlib.import_module(
    'apps.ventes.migrations.0132_acal102_backfill_production_source')

STATUTS_CLIENT = ('envoye', 'accepte')


def _nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return 0.0


def figures_avant_apres(devis, puissance_kwc):
    """``[(cle, avant, apres)]`` pour chaque figure du layout."""
    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else {}
    resultat = layout.get('result') or {}
    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    kwc_layout = _nombre(resultat.get('kwc'))
    facteur = (_nombre(puissance_kwc) / kwc_layout
               if kwc_layout > 0 and _nombre(puissance_kwc) > 0 else 1.0)
    marque = (etude.get(_BACKFILL.MARQUE) == 'calepinage'
              or _BACKFILL.doit_marquer(etude, layout))
    verdicts = _BACKFILL.verdicts_anciens(etude, layout)
    sortie = []
    for cle, cle_layout in _BACKFILL.FIGURES:
        brut = resultat.get(cle_layout)
        if not brut:
            continue
        recale = int(round(_nombre(brut) * facteur))
        stockee = etude.get(cle)
        if not stockee:
            sortie.append((cle, recale, recale))
            continue
        avant = recale if verdicts.get(cle) else stockee
        apres = recale if marque else stockee
        sortie.append((cle, avant, apres))
    return sortie


class Command(BaseCommand):
    help = ("ACAL102 — liste (sans rien écrire) les devis dont la production "
            "ou l'économie imprimée changerait.")

    def add_arguments(self, parser):
        parser.add_argument('--company', default=None,
                            help='slug de société (défaut : toutes).')

    def handle(self, *args, **options):
        from apps.ventes.domain.scenario import puissance_kwc_du_devis
        from apps.ventes.models import Devis

        ecarts = {'brouillon': 0, 'client': 0, 'autres': 0}
        examines = 0
        with transaction.atomic():
            qs = Devis.objects.exclude(roof_layout__isnull=True)
            if options.get('company'):
                qs = qs.filter(company__slug=options['company'])
            for devis in qs.iterator(chunk_size=200):
                layout = devis.roof_layout
                if not isinstance(layout, dict) or not layout.get('result'):
                    continue
                examines += 1
                figures = figures_avant_apres(
                    devis, puissance_kwc_du_devis(devis))
                differences = [(c, a, b) for c, a, b in figures if a != b]
                if not differences:
                    continue
                if devis.statut == 'brouillon':
                    ecarts['brouillon'] += 1
                elif devis.statut in STATUTS_CLIENT:
                    ecarts['client'] += 1
                else:
                    ecarts['autres'] += 1
                for cle, avant, apres in differences:
                    self.stdout.write(
                        '%s\t%s\t%s\tavant=%s\taprès=%s' % (
                            devis.reference or '#%s' % devis.pk,
                            devis.statut, cle, avant, apres))
            transaction.set_rollback(True)
        self.stdout.write(
            'ACAL102 dry-run : %d devis examinés ; écarts — brouillon : %d, '
            'envoyé/accepté : %d, autres statuts : %d.' % (
                examines, ecarts['brouillon'], ecarts['client'],
                ecarts['autres']))
