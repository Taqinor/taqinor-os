"""CIQ664 — l'étage MT dans le brouillon v1 (``single_line_diagram``) et le
passage du relevé de visite MT VALIDÉ à l'``EtageMt``.

Le relevé vient du VRAI sélecteur de ``apps.visites`` (jamais mocké) ; sans
visite validée, sans niveau constaté ``mt``, rien n'est dessiné.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.crm.models import Lead
from apps.ventes import single_line_diagram as sld
from apps.visites import selectors as visites_selectors
from apps.visites.models import VisiteTerrain
from authentication.models import Company
from core.electrique.types import EtageMt, TransformateurMt

User = get_user_model()

RELEVE_MT = {
    'validee_le': '2026-10-05T10:00:00+00:00',
    'niveau_tension': {'declare': 'mt', 'constate': 'mt', 'ecart': False},
    'poste_mt': {
        'cellule_protection': 'cellule disjoncteur existante',
        'transformateurs': [{'nb': 1, 'kva': 400.0}],
    },
}


class EtageDepuisReleve(SimpleTestCase):
    def test_releve_mt_valide_donne_l_etage(self):
        etage = sld.etage_mt_depuis_releve(RELEVE_MT)
        self.assertEqual(etage.transformateurs,
                         (TransformateurMt(1, 400.0, ''),))
        self.assertEqual(etage.cellule, 'cellule disjoncteur existante')
        self.assertFalse(etage.injection_limitee)

    def test_injection_limitee_vient_de_l_appelant(self):
        etage = sld.etage_mt_depuis_releve(RELEVE_MT, injection_limitee=True)
        self.assertTrue(etage.injection_limitee)

    def test_non_valide_ou_bt_ou_non_releve_ne_donne_rien(self):
        self.assertIsNone(sld.etage_mt_depuis_releve(
            dict(RELEVE_MT, validee_le=None)))
        self.assertIsNone(sld.etage_mt_depuis_releve(dict(
            RELEVE_MT, niveau_tension={'constate': 'bt'})))
        self.assertIsNone(sld.etage_mt_depuis_releve(dict(
            RELEVE_MT, niveau_tension={'constate': None,
                                       'non_releve': 'site_ferme'})))
        self.assertIsNone(sld.etage_mt_depuis_releve(None))
        self.assertIsNone(sld.etage_mt_depuis_releve({}))

    def test_site_mt_valide_sans_poste_dessine_quand_meme_un_etage_vide(self):
        etage = sld.etage_mt_depuis_releve(dict(RELEVE_MT, poste_mt=None))
        self.assertEqual(etage, EtageMt())

    def test_un_transformateur_inexploitable_est_ignore(self):
        etage = sld.etage_mt_depuis_releve(dict(RELEVE_MT, poste_mt={
            'transformateurs': [{'nb': 0, 'kva': 400}, {'nb': 1}, 'x',
                                {'nb': 2, 'kva': 630}]}))
        self.assertEqual(etage.transformateurs,
                         (TransformateurMt(2, 630.0, ''),))


class BrouillonV1(SimpleTestCase):
    PARAMS = {'n_panneaux': 20, 'puissance_panneau_wc': 550, 'phases': 3}

    def test_sans_etage_mt_le_svg_et_les_parametres_sont_inchanges(self):
        self.assertNotIn('etage_mt', sld.normalize_diagram_params(self.PARAMS))
        svg = sld.build_single_line_svg(self.PARAMS)
        self.assertEqual(svg, sld.build_single_line_svg(
            dict(self.PARAMS, etage_mt=None)))
        self.assertIn('viewBox="0 0 980 260"', svg)
        self.assertNotIn('Transformateur', svg)

    def test_avec_etage_mt_les_blocs_a_confirmer_sont_dessines(self):
        etage = sld.etage_mt_depuis_releve(RELEVE_MT, injection_limitee=True)
        svg = sld.build_single_line_svg(dict(self.PARAMS, etage_mt=etage))
        for texte in ('Transformateur MT/BT', 'Cellule MT',
                      'Protection découplage', "Limiteur d&#x27;injection",
                      'à confirmer', 'distributeur'):
            self.assertIn(texte, svg)
        # L'étage s'insère AVANT le réseau.
        self.assertLess(svg.index('Transformateur MT/BT'),
                        svg.index('ONEE (réseau)'))

    def test_un_dict_tolerant_est_accepte(self):
        cfg = sld.normalize_diagram_params(dict(self.PARAMS, etage_mt={
            'transformateurs': [{'nb': '1', 'kva': '400'}],
            'cellule': 'x', 'injection_limitee': 1}))
        self.assertEqual(cfg['etage_mt']['transformateurs'],
                         [{'nb': 1, 'kva': 400.0, 'rapport': ''}])
        self.assertTrue(cfg['etage_mt']['injection_limitee'])
        self.assertIsNone(sld.normalize_diagram_params(
            dict(self.PARAMS, etage_mt='n importe quoi')).get('etage_mt'))


class ReleveDeLaVisite(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ664 Co', slug='ciq664')
        self.bureau = User.objects.create_user(
            username='ciq664_bureau', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Usine', type_installation='industriel')

    def _visite(self, niveau, statut=VisiteTerrain.Statut.VALIDEE, **poste):
        mesures = {'comptage': {'type_compteur': 'MT',
                                'niveau_tension_constate': niveau}}
        if poste:
            mesures['poste_mt'] = poste
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='ci',
            statut=statut, mesures=mesures,
            validee_le=(timezone.now() if statut
                        == VisiteTerrain.Statut.VALIDEE else None),
            date_prevue=datetime.date(2026, 10, 5))

    def test_visite_mt_validee_dessine_l_etage_du_poste_releve(self):
        self._visite('mt', cellule_protection='cellule disjoncteur',
                     transformateurs=[{'nb': 1, 'kva': 400.0}])
        releve = visites_selectors.releve_ci_pour_lead(self.lead)
        etage = sld.etage_mt_depuis_releve(releve)
        self.assertEqual(etage.transformateurs,
                         (TransformateurMt(1, 400.0, ''),))
        self.assertEqual(etage.cellule, 'cellule disjoncteur')

    def test_visite_bt_validee_ne_dessine_rien(self):
        self._visite('bt', transformateurs=[{'nb': 1, 'kva': 400.0}])
        releve = visites_selectors.releve_ci_pour_lead(self.lead)
        self.assertIsNone(releve['poste_mt'])
        self.assertIsNone(sld.etage_mt_depuis_releve(releve))

    def test_visite_mt_non_validee_ne_dessine_rien(self):
        visite = self._visite('mt', statut=VisiteTerrain.Statut.TERMINEE,
                              transformateurs=[{'nb': 1, 'kva': 400.0}])
        releve = visites_selectors.releve_ci_de_visite(visite)
        self.assertIsNone(releve['validee_le'])
        self.assertIsNone(sld.etage_mt_depuis_releve(releve))
        self.assertIsNone(visites_selectors.releve_ci_pour_lead(self.lead))
