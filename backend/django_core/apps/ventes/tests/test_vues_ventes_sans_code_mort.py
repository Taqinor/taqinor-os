"""QJR650 — vues ventes sans code mort : plus de ``_resolve_accepted_option``
(``accept_devis`` résout l'option) ni d'imports ``# noqa: F401`` hérités du
découpage du monolithe qui masquaient les noms réellement utilisés.

ROUGE AVANT : la méthode existait sans aucune référence ; ``views/devis.py``
portait 20 marqueurs F401 et ``views/ligne_devis.py`` 13.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_vues_ventes_sans_code_mort"
"""
import ast
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.views.devis import DevisViewSet

VUES = Path(__file__).resolve().parent.parent / 'views'
#: SPL130 — ``views/devis.py`` + ses modules de découpe ``views/devis_*.py``
#: (SPL134-SPL142) + ``ligne_devis.py`` : la garde suit le code déplacé.
MODULES = ('devis.py',
           *sorted(p.name for p in VUES.glob('devis_*.py')),
           'ligne_devis.py')

#: Noms importés DEPUIS ces modules ailleurs (tests compris) : ils restent
#: même s'ils n'y sont pas lus.
IMPORTES_AILLEURS = {
    'DevisViewSet', 'LigneDevisViewSet', '_company_qs',
    '_emettre_layout_finalise',
}
#: Hors périmètre (QJR655) : ``scope_queryset`` et ``_company_qs``.
HORS_PERIMETRE = {'scope_queryset'}


def _imports_non_lus(chemin):
    arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    importes = {}
    for noeud in ast.walk(arbre):
        if isinstance(noeud, (ast.Import, ast.ImportFrom)):
            for alias in noeud.names:
                nom = (alias.asname or alias.name).split('.')[0]
                importes.setdefault(nom, noeud.lineno)
    lus = {n.id for n in ast.walk(arbre) if isinstance(n, ast.Name)}
    return {nom: ligne for nom, ligne in importes.items()
            if nom not in lus and nom not in IMPORTES_AILLEURS
            and nom not in HORS_PERIMETRE}


class VuesVentesSansCodeMort(SimpleTestCase):

    def test_resolve_accepted_option_supprime(self):
        self.assertFalse(hasattr(DevisViewSet, '_resolve_accepted_option'))

    def test_chaque_nom_importe_est_utilise(self):
        for module in MODULES:
            with self.subTest(module=module):
                self.assertEqual(_imports_non_lus(VUES / module), {})

    def test_aucun_marqueur_f401_hors_perimetre(self):
        for module in MODULES:
            for numero, ligne in enumerate(
                    (VUES / module).read_text(encoding='utf-8').splitlines(),
                    start=1):
                if 'F401' in ligne and 'scope_queryset' not in ligne:
                    self.fail(f'{module}:{numero} garde un « noqa: F401 » : '
                              f'{ligne.strip()}')
