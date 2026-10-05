"""ACAL219/ACAL220 - l'inventaire ``documents/`` dit VRAI.

Calepinage fabrique par les VRAIS ecrivains (``calepinage_simule_reel``) : la
disponibilite de chaque carte est calculee sur le resultat SERVI (lu UNE fois
par appel), jamais sur la colonne brute qui ne porte ni ``electrique`` ni
``troncons``.

Les lectures en base (``versions[]``, ``images[]``) sont doublees par ``[]`` :
elles relevent des essais en base de CALX322/CALX302, pas de ces essais.

Run :
    python manage.py test apps.calepinage.tests.test_acal_inventaire_vrai -v2
"""
import copy
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services.documents import inventaire_des_documents

from .acal_livrables_helpers import (
    LAYOUT_SIMULABLE, PivotSansBase, calepinage_simule_reel, patch_materiel,
)


class SansBase:
    def setUp(self):
        super().setUp()
        for cible in ('apps.calepinage.services.documents._versions_pour',
                      'apps.calepinage.services.documents._images_pour'):
            patcheur = mock.patch(cible, return_value=[])
            patcheur.start()
            self.addCleanup(patcheur.stop)


def _par_code(calepinage):
    with patch_materiel():
        servi = inventaire_des_documents(calepinage)
    return {d['code']: d for d in servi['documents']}


class InventaireSurResultatServiTest(SansBase, SimpleTestCase):
    def test_plan_cablage_disponible_quand_chainage_present(self):
        pivot = calepinage_simule_reel()
        # La colonne brute ne porte NI electrique NI troncons.
        self.assertNotIn('electrique', pivot.resultat)
        self.assertNotIn('troncons', pivot.resultat)
        document = _par_code(pivot)['plan_cablage']
        self.assertTrue(document['disponible'], document['manque'])
        self.assertEqual(document['manque'], [])

    def test_plan_cablage_indisponible_sans_chainage_avec_manque_nomme(self):
        # Conception + une entree (donc un resultat stocke) mais aucun
        # materiel designe : rien n'est chaine.
        pivot = PivotSansBase(copy.deepcopy(LAYOUT_SIMULABLE),
                              resultat={'entree_electrique': {}})
        with patch_materiel() as materiel:
            materiel.return_value = {
                'module': {}, 'onduleur': {}, 'optimiseur': None,
                'designations': {'module': '', 'onduleur': '',
                                 'optimiseur': ''},
                'absents': ('module PV non désigné',)}
            servi = inventaire_des_documents(pivot)
        document = {d['code']: d for d in servi['documents']}['plan_cablage']
        self.assertFalse(document['disponible'])
        self.assertEqual([m['champ'] for m in document['manque']],
                         ['electrique.chainage'])

    def test_inventaire_lit_le_servi_apres_simulation_reelle(self):
        pivot = calepinage_simule_reel()
        with patch_materiel(), mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                wraps=__import__(
                    'apps.calepinage.services.electrique',
                    fromlist=['resultat_calepinage']).resultat_calepinage
        ) as lecture:
            inventaire_des_documents(pivot)
        # UNE execution de resultat_calepinage pour les neuf cartes.
        self.assertEqual(lecture.call_count, 1)

    def test_diagramme_suit_la_cascade_servie_pas_la_colonne_brute(self):
        from .acal_livrables_helpers import modifier_la_conception

        frais = _par_code(calepinage_simule_reel())['diagramme_pertes']
        perime = _par_code(
            modifier_la_conception(calepinage_simule_reel()))['diagramme_pertes']
        self.assertTrue(frais['disponible'])
        # Simulation perimee : la cascade servie vaut null.
        self.assertFalse(perime['disponible'])
        self.assertEqual(perime['manque'][0]['champ'], 'cascade')

    def test_deux_lectures_donnent_les_memes_cartes(self):
        pivot = calepinage_simule_reel()
        self.assertEqual(_par_code(pivot), _par_code(pivot))
