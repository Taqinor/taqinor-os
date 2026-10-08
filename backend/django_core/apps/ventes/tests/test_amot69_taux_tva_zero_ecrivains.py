"""AMOT69 (C-AMOT-006) — les écrivains de lignes du domaine devis ne
remplacent plus un taux 0 % EXPLICITE par 20 % (``taux_tva or 20`` →
``is None``) : 0 % reste 0 %, un taux absent garde 20 %.

Source réelle : ``creation_auto.composer_devis_residentiel`` sur le
catalogue du montage QJR80 (produits sans taux propre ⇒ taux demandé).

Test-du-test : remettre ``or 20`` ⇒ ``test_zero_explicite_reste_zero``
échoue.
"""
import ast
from pathlib import Path

from decimal import Decimal

from apps.ventes.domain import creation_auto
from apps.ventes.tests import test_qjr_pipeline_composer as qjr80

VENTES = Path(__file__).resolve().parents[1]


class TauxTvaZeroEcrivainsTests(qjr80._Base):
    slug = 'amot69-tva'

    def _taux(self, taux_tva):
        charge = creation_auto.composer_devis_residentiel(
            company=self.company, nb_panneaux=qjr80.NB_PANNEAUX,
            panel_watt=qjr80.PANEL_WATT, scenario='sans', taux_tva=taux_tva)
        return {ligne['taux_tva'] for ligne in charge['lignes']}

    def test_zero_explicite_reste_zero(self):
        self.assertEqual(self._taux(Decimal('0')), {'0'})

    def test_absent_vaut_vingt(self):
        self.assertEqual(self._taux(None), {'20'})

    def test_aucun_repli_or_20_dans_les_ecrivains(self):
        """Garde : aucun ``taux_tva or 20`` dans les deux écrivains."""
        for chemin in ('domain/creation_auto.py',
                       'management/commands/acal_dryrun_ligne_par_modele.py'):
            arbre = ast.parse((VENTES / chemin).read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if (isinstance(noeud, ast.BoolOp)
                        and isinstance(noeud.op, ast.Or)
                        and any(getattr(v, 'attr', getattr(v, 'id', None))
                                == 'taux_tva' for v in noeud.values)
                        and any(isinstance(v, ast.Constant) and v.value == 20
                                for v in noeud.values)):
                    self.fail('%s:%s — repli « taux_tva or 20 »'
                              % (chemin, noeud.lineno))
