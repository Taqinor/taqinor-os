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


# ═══════════════════════════════════════════════════════════════════════════
# ACAL220 - chaque carte dit vrai
# ═══════════════════════════════════════════════════════════════════════════

class CartesVraiesTest(SansBase, SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pivot = calepinage_simule_reel()

    def _cartes(self, gabarit=None):
        with mock.patch(
                'apps.calepinage.services.documents.manuel_proprietaire.'
                'gabarit_manuel_actif', return_value=gabarit):
            return _par_code(self.pivot)

    def test_toute_carte_disponible_se_telecharge_au_bon_format(self):
        # Le format annonce est celui de la route resolue : extension de
        # l'endpoint == format, et le diagramme est un SVG (plus le JSON
        # d'inventaire sous le nom d'un PNG).
        import re

        cartes = self._cartes(gabarit=object())
        for code, carte in cartes.items():
            if carte['code'] == 'dossier_fin_chantier':
                continue  # POST, verifie par le test dedie
            self.assertTrue(
                carte['endpoint'].rstrip('/').endswith(
                    '.' + carte['format']), code)
            self.assertIsNone(re.search(r'/documents/$', carte['endpoint']))
        self.assertEqual(cartes['diagramme_pertes']['format'], 'svg')
        self.assertTrue(cartes['diagramme_pertes']['endpoint'].endswith(
            'diagramme-pertes.svg/'))

    def test_dossier_fin_chantier_est_post_et_la_route_se_resout(self):
        from apps.calepinage.views import documents as vue

        carte = self._cartes()['dossier_fin_chantier']
        self.assertEqual(carte['methode'], 'POST')
        self.assertTrue(carte['endpoint'].endswith('dossier-fin-chantier/'))
        self.assertTrue(carte['disponible'])
        # La route existe bien, en POST (declaration de l'@action).
        self.assertEqual(vue.dossier_fin_chantier.url_path,
                         'dossier-fin-chantier')
        self.assertIn('post', vue.dossier_fin_chantier.mapping)

    def test_manuel_indisponible_sans_gabarit_avec_manque_nomme(self):
        sans = self._cartes(gabarit=None)['manuel_proprietaire']
        avec = self._cartes(gabarit=object())['manuel_proprietaire']
        self.assertFalse(sans['disponible'])
        self.assertEqual([m['champ'] for m in sans['manque']], ['gabarit'])
        self.assertIn('Réglages > Calepinage > Gabarits',
                      sans['manque'][0]['ou_saisir'])
        self.assertTrue(avec['disponible'])

    def test_asbuilt_disponible_avec_conception_et_resultat(self):
        carte = self._cartes()['document_asbuilt']
        self.assertTrue(carte['disponible'])
        self.assertEqual(carte['manque'], [])

    def test_langues_publiees_par_entree(self):
        cartes = self._cartes()
        for code in ('rapport_etude', 'rapport_ombrage', 'diagramme_pertes'):
            self.assertEqual(cartes[code]['langues'], ['fr', 'en'], code)
        for code in ('export_projet_json', 'plan_cablage',
                     'manuel_proprietaire', 'document_asbuilt',
                     'dossier_fin_chantier', 'presentation_compacte'):
            self.assertEqual(cartes[code]['langues'], ['fr'], code)

    def test_apercu_et_autres_formats_publies(self):
        from apps.calepinage.services.documents import MISES_EN_PAGE

        cartes = self._cartes()
        for code, carte in cartes.items():
            self.assertEqual(carte['apercu'], code in MISES_EN_PAGE, code)
        self.assertEqual(
            [f['format'] for f in cartes['plan_cablage']['autres_formats']],
            ['dxf'])
        self.assertTrue(cartes['plan_cablage']['autres_formats'][0]
                        ['endpoint'].endswith('plan-cablage.dxf/'))

    def test_chaque_manque_publie_un_onglet_du_registre_ou_null(self):
        onglets = {'production', 'affectation', 'equipements-electriques',
                   'documents'}
        vide = _par_code(PivotSansBase(None))
        sans_chainage = _par_code(PivotSansBase(
            copy.deepcopy(LAYOUT_SIMULABLE),
            resultat={'entree_electrique': {}}))
        for cartes in (vide, sans_chainage):
            for carte in cartes.values():
                for manque in carte['manque']:
                    self.assertIn('onglet', manque)
                    self.assertTrue(manque['onglet'] is None
                                    or manque['onglet'] in onglets)
