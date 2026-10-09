"""DRY-RUN — devis envoyés dont les chiffres imprimés DIFFÉRERAIENT sous les
règles de calcul corrigées (décision fondateur 08/10/2026, « nouveaux rendus
seulement »).

Les devis envoyés avant la migration 0136 portent ``regles_calcul = 1`` et
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

#: Figures client comparées (clés du dict de rendu).
FIGURES = (
    'display_total', 'puissance_kwc', 'prod_kwh', 'roi_s', 'roi_a',
    'eco_s_ann', 'eco_a_ann', 'net_gain_s', 'net_gain_a', 'savings_method',
    'sans_bullets', 'avec_bullets', 'payment_terms', 'recommended',
    'eco_s_monthly', 'eco_a_monthly', 'cashflow_sans', 'cashflow_avec',
)


def _figures(data):
    out = {cle: data.get(cle) for cle in FIGURES}
    totaux = data.get('totaux_all') or {}
    if isinstance(totaux, dict):
        out['totaux_all.ttc'] = totaux.get('ttc')
    return out


def ecarts_du_devis(devis):
    """``{clé: (origine, corrigée)}`` des figures qui changent (vide sinon)."""
    from apps.ventes.domain.regles_calcul import REGLES_CORRIGEES
    from apps.ventes.quote_engine.builder import build_quote_data

    opts = {'pdf_mode': 'full'}
    avant = _figures(build_quote_data(devis, dict(opts)))
    stocke = devis.regles_calcul
    try:
        devis.regles_calcul = REGLES_CORRIGEES  # en mémoire seulement
        apres = _figures(build_quote_data(devis, dict(opts)))
    finally:
        devis.regles_calcul = stocke
    return {cle: (avant[cle], apres.get(cle))
            for cle in avant if avant[cle] != apres.get(cle)}


class Command(BaseCommand):
    help = ('DRY-RUN : devis envoyés (règles de calcul d\'origine) dont les '
            'chiffres imprimés changeraient sous les règles corrigées.')

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, default=None)
        parser.add_argument('--detail', action='store_true')

    def handle(self, *args, **opts):
        from apps.ventes.domain.regles_calcul import REGLES_ORIGINE
        from apps.ventes.models import Devis

        qs = Devis.objects.filter(regles_calcul=REGLES_ORIGINE).order_by('id')
        if opts['company']:
            qs = qs.filter(company_id=opts['company'])
        total = qs.count()
        concernes, erreurs = [], []
        with transaction.atomic():
            for devis in qs.iterator():
                try:
                    ecarts = ecarts_du_devis(devis)
                except Exception as exc:  # noqa: BLE001 — devis illisible signalé
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
