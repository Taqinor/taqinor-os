"""DRY-RUN — devis envoyés dont les chiffres imprimés DIFFÉRERAIENT sous les
règles de calcul corrigées (décision fondateur 08/10/2026, « nouveaux rendus
seulement »).

Les devis envoyés avant la migration 0138 portent ``regles_calcul = 1`` et
restent rendus avec les règles d'origine. Cette commande rend chacun DEUX fois
en mémoire (règles d'origine, puis règles corrigées — l'attribut est changé
sur l'instance, jamais enregistré) et liste ceux dont une figure client
change : nombre + références + clés qui bougent.

LECTURE SEULE. Aucun mode d'écriture n'existe : tout se passe dans une
transaction annulée d'office, et rien n'est jamais réparé ici.

    python manage.py regles_calcul_ecarts_dryrun [--company <id>] [--detail]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from numbers import Number
import copy
import logging

logger = logging.getLogger(__name__)

#: Figures client comparées (clés du dict de rendu).
FIGURES = (
    'display_total', 'puissance_kwc', 'prod_kwh', 'roi_s', 'roi_a',
    'eco_s_ann', 'eco_a_ann', 'net_gain_s', 'net_gain_a', 'savings_method',
    'sans_bullets', 'avec_bullets', 'payment_terms', 'recommended',
    'eco_s_monthly', 'eco_a_monthly', 'cashflow_sans', 'cashflow_avec', 'nb_panneaux',
)
#: ACAL1000 — figures listées une par une par ``--niveau N``.
FIGURES_NIVEAU = ('prod_kwh', 'eco_s_ann', 'eco_a_ann', 'puissance_kwc', 'nb_panneaux', 'totaux_all.ttc')
#: ACAL1203 (D-ACAL-46) — figures du pompage RANGÉES dans ``etude_params``, relues par le PDF agricole.
FIGURES_POMPAGE = ('m3_jour', 'heures_pompage', 'production.m3_jour_mois', 'couverture_pct_mois',
                   'production.plan_irradiation.source')


def _figures_pompage(devis):
    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    production = etude.get('production') if isinstance(etude.get('production'), dict) else {}
    plan = production.get('plan_irradiation') if isinstance(production.get('plan_irradiation'), dict) else {}
    return {'m3_jour': etude.get('m3_jour'), 'heures_pompage': etude.get('heures_pompage'),
            'production.m3_jour_mois': production.get('m3_jour_mois'),
            'couverture_pct_mois': etude.get('couverture_pct_mois'),
            'production.plan_irradiation.source': plan.get('source')}


def _ecart(a, b):
    """Écart numérique, mois par mois pour deux listes de même longueur ; ``None`` sinon (figure absente)."""
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [_ecart(x, y) for x, y in zip(a, b)]
    return b - a if all(isinstance(v, Number) for v in (a, b)) else None


def _figures(data):
    out = {cle: data.get(cle) for cle in FIGURES}
    totaux = data.get('totaux_all') or {}
    if isinstance(totaux, dict):
        out['totaux_all.ttc'] = totaux.get('ttc')
    return out


def ecarts_du_devis(devis, niveau=None):
    """``{clé: (origine, corrigée)}`` des figures qui changent (vide sinon). ``niveau`` (ACAL1000) :
    niveau forcé, statut lu « brouillon », bloc horaire RECALCULÉ, transaction annulée."""
    from apps.ventes.domain.regles_calcul import REGLES_CORRIGEES
    from apps.ventes.quote_engine.builder import build_quote_data

    opts = {'pdf_mode': 'full'}
    agricole = bool(niveau) and (getattr(devis, 'mode_installation', '') or '') == 'agricole'  # ACAL1203
    avant = dict(_figures(build_quote_data(devis, dict(opts))),
                 **(copy.deepcopy(_figures_pompage(devis)) if agricole else {}))
    stocke = (devis.regles_calcul, devis.statut, copy.deepcopy(devis.etude_params))
    try:
        with transaction.atomic():
            devis.regles_calcul = niveau or REGLES_CORRIGEES  # en mémoire seulement
            if niveau:
                from apps.ventes.domain.etudes import rafraichir_etude_horaire_devis
                devis.statut = 'brouillon'
                rafraichir_etude_horaire_devis(devis, force=True)
                if agricole:  # le PDF agricole relit l'étude RANGÉE : elle est recalculée (écriture annulée)
                    from apps.ventes.domain.pompage import rafraichir_etude_pompage_devis
                    rafraichir_etude_pompage_devis(devis, force=True)
            apres = dict(_figures(build_quote_data(devis, dict(opts))),
                         **(_figures_pompage(devis) if agricole else {}))
            transaction.set_rollback(True)
    finally:
        devis.regles_calcul, devis.statut, devis.etude_params = stocke
    return {cle: (avant[cle], apres.get(cle))
            for cle in avant if avant[cle] != apres.get(cle)}


class Command(BaseCommand):
    help = ('DRY-RUN : devis envoyés (règles de calcul d\'origine) dont les '
            'chiffres imprimés changeraient sous les règles corrigées.')

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, default=None)
        parser.add_argument('--detail', action='store_true')
        parser.add_argument('--niveau', type=int, default=None)

    def handle(self, *args, **opts):
        from apps.ventes.domain.regles_calcul import REGLES_ORIGINE
        from apps.ventes.models import Devis

        if opts.get('niveau'):
            return self._niveau(Devis, opts['niveau'], opts['company'])
        qs = Devis.objects.filter(regles_calcul=REGLES_ORIGINE).order_by('id')
        if opts['company']:
            qs = qs.filter(company_id=opts['company'])
        total = qs.count()
        concernes, erreurs = [], []
        with transaction.atomic():
            for devis in qs.iterator():
                try:
                    ecarts = ecarts_du_devis(devis)
                except Exception as exc:  # noqa: BLE001 — devis illisible signalé (D-ENF22-BLE001)
                    logger.warning(
                        "regles_calcul_ecarts_dryrun.Command.handle : erreur ignorée (mode dégradé)", exc_info=True)
                    erreurs.append((devis.reference, type(exc).__name__))
                    continue
                if ecarts:
                    concernes.append((devis.reference, devis.statut, ecarts))
            transaction.set_rollback(True)  # garantie : aucune écriture
        self.stdout.write(
            f"{total} devis aux règles d'origine ; "
            f'{len(concernes)} changeraient sous les règles corrigées.')
        for ref, statut, ecarts in concernes:
            self.stdout.write(f'  {ref} [{statut}] : {", ".join(sorted(ecarts))}')
            if opts['detail']:
                for cle, (a, b) in sorted(ecarts.items()):
                    self.stdout.write(f'      {cle}: {a!r} -> {b!r}')
        for ref, err in erreurs:
            self.stdout.write(f'  {ref} : rendu impossible ({err})')

    def _niveau(self, Devis, niveau, company):
        """ACAL1000 — devis de niveau < N : écarts par figure, « changera » (brouillon jamais envoyé), totaux."""
        qs = Devis.objects.filter(regles_calcul__lt=niveau, **({'company_id': company} if company else {}))
        figures, agricoles = FIGURES_NIVEAU + FIGURES_POMPAGE, False
        totaux = dict.fromkeys(figures, 0.0)
        self.stdout.write('reference, statut, changera, figure, avant, après, écart')
        with transaction.atomic():
            for devis in qs.order_by('id').iterator():
                changera = 'oui' if (devis.statut == 'brouillon' and devis.date_envoi is None) else 'non'
                try:
                    ecarts = ecarts_du_devis(devis, niveau)
                except Exception as exc:  # noqa: BLE001 — devis illisible signalé (D-ENF22-BLE001)
                    logger.warning("regles_calcul_ecarts_dryrun --niveau : rendu impossible", exc_info=True)
                    self.stdout.write(f'{devis.reference}, rendu impossible ({type(exc).__name__})')
                    continue
                agricoles = agricoles or devis.mode_installation == 'agricole'
                for fig, (a, b) in ((f, ecarts[f]) for f in figures if f in ecarts):
                    e = _ecart(a, b)
                    totaux[fig] += float(sum(x or 0 for x in e) if isinstance(e, list) else (e or 0))
                    self.stdout.write(f'{devis.reference}, {devis.statut}, {changera}, {fig}, {a}, {b}, {e}')
            transaction.set_rollback(True)  # garantie : aucune écriture
        for fig in FIGURES_NIVEAU + (FIGURES_POMPAGE if agricoles else ()):
            self.stdout.write(f'TOTAL {fig} : {totaux[fig]}')
