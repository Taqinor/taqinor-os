"""CAL245 — le bloc « calepinage retenu » sur le détail chantier (endpoint).

Couvre :
  * ``InstallationSerializer.calepinage`` sert le bloc
    ``{calepinage_id, kwc, nb_modules, planche_url, plan_pose_url}`` pour un
    chantier issu d'un calepinage RETENU, ``None`` sinon (contrat
    ``apps/installations/contract_samples/calepinage_retenu.json``, PACT10) ;
  * aucune migration n'accompagne cette lane : ``Installation`` ne gagne
    aucun champ calepinage (règle fondateur 12/09/2026).

Run :
    python manage.py test apps.installations.tests_cal245_bloc_calepinage -v2
"""
import itertools
import json
import pathlib
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.variantes import bascule_autorisee
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.installations.serializers import InstallationSerializer
from apps.ventes.models import Devis
from authentication.models import Company

_seq = itertools.count(1)


def make_company():
    n = next(_seq)
    return Company.objects.create(nom=f'CAL245 Co {n}', slug=f'cal245-co-{n}')


def make_client(company):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='CAL245',
        email=f'cal245-{company.id}-{n}@example.invalid')


def make_devis(company, client):
    n = next(_seq)
    return Devis.objects.create(
        company=company, reference=f'DEV-CAL245-{n}', client=client,
        taux_tva=Decimal('20'))


def make_installation(company, client, devis=None):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CHT-CAL245-{n}', client=client,
        devis=devis)


class TestBlocCalepinageSerializer(TestCase):
    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)

    def test_chantier_sans_devis_rend_null(self):
        chantier = make_installation(self.company, self.client_obj)
        data = InstallationSerializer(chantier).data
        self.assertIsNone(data['calepinage'])

    def test_chantier_avec_devis_sans_calepinage_rend_null(self):
        chantier = make_installation(self.company, self.client_obj, self.devis)
        data = InstallationSerializer(chantier).data
        self.assertIsNone(data['calepinage'])

    def test_chantier_issu_d_un_calepinage_rend_le_bloc(self):
        # ACAL107 — le kWc / les modules se lisent sur la CONCEPTION du
        # calepinage (retenir une variante l'y écrit), plus sur la variante.
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.devis,
            resultat={'pose': {'kwc': 8.64, 'total_modules': 12}})
        with bascule_autorisee():
            CalepinageVariante.objects.create(
                company=self.company, calepinage=calepinage, nom='V1',
                retenue=True)
        chantier = make_installation(self.company, self.client_obj, self.devis)

        data = InstallationSerializer(chantier).data
        bloc = data['calepinage']
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['calepinage_id'], calepinage.id)
        self.assertEqual(bloc['kwc'], 8.64)
        self.assertEqual(bloc['nb_modules'], 12)
        self.assertEqual(bloc['planche_url'], f'/calepinage/{calepinage.id}')
        self.assertEqual(
            bloc['plan_pose_url'], f'/ventes/devis/{self.devis.id}/3d')
        # ACAL903 — le PDF du plan de pose, en plus de la page 3D inchangée.
        self.assertEqual(
            bloc['plan_pose_pdf_url'],
            f'/calepinage/calepinages/{calepinage.id}/plan-pose.pdf/')

    def test_installation_ne_gagne_aucun_champ_calepinage(self):
        """Aucune migration chantier n'accompagne CAL245 : le bloc est un
        SerializerMethodField calculé, jamais une colonne persistée."""
        noms_champs = {f.name for f in Installation._meta.get_fields()}
        for interdit in ('calepinage', 'calepinage_id', 'calepinage_retenu'):
            self.assertNotIn(interdit, noms_champs)


class TestBlocChantierKwcVendu(TestCase):
    """ACAL274 (C-ACAL-118) — le bloc du chantier affiche le kWc et les
    modules VENDUS (lignes du devis) et le dessin comme tel, avec l'écart.

    Test rouge d'abord : avant ACAL274 le bloc lisait le ``pose`` du
    calepinage (8,52 kWc dessinés) au lieu des 12 × 550 W vendus (6,6 kWc).
    Hébergé ici (module du bloc chantier existant, CAL245) plutôt que dans un
    fichier ``test_acal_chantier_kwc_vendu.py`` par tâche (garde de placement).
    """

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)

    def _vendre_12_panneaux_550(self):
        produit = Produit.objects.create(
            company=self.company, nom='Panneau Solar 550W',
            sku=f'ACAL274-PAN-{self.devis.pk}', prix_vente=Decimal('1000'),
            prix_achat=Decimal('1'), quantite_stock=500)
        self.devis.lignes.create(
            produit=produit, designation='Panneau Solar 550W',
            quantite=Decimal('12'), prix_unitaire=Decimal('1000'))

    def _retenir_dessin_8_52(self):
        document = {
            'areas': [{'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
                       'obstacles': [], 'roofType': 'flat', 'pitch': 10,
                       'azimuth': 180}],
            'scenario': 'reseau',
            'result': {'panels': 12, 'kwc': 8.52,
                       'annualKwh': 10800, 'savings': 9200},
        }
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.devis,
            roof_layout=document,
            resultat={'pose': {'kwc': 8.52, 'total_modules': 12}})
        with bascule_autorisee():
            CalepinageVariante.objects.create(
                company=self.company, calepinage=calepinage, nom='V1',
                retenue=True)
        return calepinage

    def test_bloc_chantier_kwc_vendu(self):
        self._vendre_12_panneaux_550()
        self._retenir_dessin_8_52()
        chantier = make_installation(self.company, self.client_obj, self.devis)

        bloc = InstallationSerializer(chantier).data['calepinage']
        self.assertEqual(bloc['kwc'], 6.6)
        self.assertEqual(bloc['nb_modules'], 12)
        self.assertEqual(bloc['kwc_source'], 'devis')
        self.assertEqual(bloc['dessin_kwc'], 8.52)
        self.assertEqual(bloc['ecart_kwc'], 1.92)

    def test_sans_ligne_vendue_le_bloc_garde_la_conception(self):
        self._retenir_dessin_8_52()
        chantier = make_installation(self.company, self.client_obj, self.devis)

        bloc = InstallationSerializer(chantier).data['calepinage']
        self.assertEqual(bloc['kwc_source'], 'calepinage')
        self.assertEqual(bloc['kwc'], 8.52)
        self.assertIsNone(bloc['ecart_kwc'])


class TestContratRecetteValeursAttendues(SimpleTestCase):
    """ACAL666 — forme de ``recette_valeurs_attendues.json`` (contrat posé
    seul, avant le serveur ACAL667 et l'écran ACAL668)."""

    CHAMPS_CHAINE = {'chaine', 'modules', 'voc_attendu_v', 'isc_attendu_a',
                     'pmax_attendu_w', 'sources', 'corrigee',
                     'isc_corrige_motif'}

    def setUp(self):
        chemin = (pathlib.Path(__file__).resolve().parent / 'contract_samples'
                  / 'recette_valeurs_attendues.json')
        self.contrat = json.loads(chemin.read_text(encoding='utf-8'))

    def test_forme_de_l_exemple(self):
        exemple = self.contrat['exemple']
        self.assertEqual(set(exemple), {'installation', 'chaines',
                                        'temperature_c', 'eclairement_w_m2'})
        self.assertTrue(exemple['chaines'])
        for chaine in exemple['chaines']:
            self.assertEqual(set(chaine), self.CHAMPS_CHAINE)
            self.assertIsInstance(chaine['sources'], list)
            self.assertTrue(chaine['sources'])

    def test_valeurs_derivees_a_la_main_de_la_fiche(self):
        chaine = self.contrat['exemple']['chaines'][0]
        self.assertEqual(chaine['voc_attendu_v'], 10 * 49.5)
        self.assertEqual(chaine['modules'], 10)
        self.assertIn('10 × 49,5 V = 495 V', self.contrat['pourquoi'])

    def test_sans_calepinage_liste_vide_et_motif_nomme(self):
        vide = self.contrat['exemple_sans_calepinage']
        self.assertEqual(vide['chaines'], [])
        self.assertTrue(vide['motif'])


def _contrat_valeurs_attendues():
    chemin = (pathlib.Path(__file__).resolve().parent / 'contract_samples'
              / 'recette_valeurs_attendues.json')
    return json.loads(chemin.read_text(encoding='utf-8'))


#: La fiche RÉELLE du contrat ACAL666 (Voc 49,5 V, Isc 13,9 A, Pmax 550 W).
FICHE_CONTRAT = {'voc_v': 49.5, 'isc_a': 13.9, 'pmax_wc': 550}
#: Une chaîne publiée de 10 modules (une ligne par module).
AFFECTATION_10 = [{'module': f'm{n}', 'chaine': 1} for n in range(10)]


def _valeurs_du_selecteur(*_a, temperature_c=None, eclairement_w_m2=None):
    """Le VRAI calcul d'ACAL665 sur la fiche du contrat (base non lue)."""
    from apps.calepinage.services.valeurs_attendues import valeurs_attendues

    return valeurs_attendues(AFFECTATION_10, FICHE_CONTRAT,
                             '« Module PV 550 Wc »', temperature_c=temperature_c,
                             eclairement_w_m2=eclairement_w_m2)[0]


class ValeursAttenduesFormeTest(SimpleTestCase):
    """ACAL667 — ``valeurs_attendues_du_chantier`` rend le contrat d'ACAL666."""

    def _servir(self, bloc, **params):
        from apps.installations.selectors_recette import (
            valeurs_attendues_du_chantier,
        )

        chantier = SimpleNamespace(pk=31, devis_id=7, company='societe')
        with mock.patch('apps.calepinage.selectors.calepinage_retenu_pour_devis',
                        return_value=bloc), \
                mock.patch('apps.calepinage.selectors_chantier.'
                           'valeurs_attendues_par_chaine',
                           side_effect=_valeurs_du_selecteur):
            return valeurs_attendues_du_chantier(chantier, **params)

    def test_dix_modules_a_49_5_v_rendent_495_v(self):
        servi = self._servir({'id': 12})
        exemple = _contrat_valeurs_attendues()['exemple']
        self.assertEqual(set(servi), set(exemple))
        self.assertEqual(set(servi['chaines'][0]), set(exemple['chaines'][0]))
        chaine = servi['chaines'][0]
        self.assertEqual((chaine['chaine'], chaine['modules'], chaine['voc_attendu_v'],
                          chaine['isc_attendu_a'], chaine['pmax_attendu_w']),
                         ('CH1', 10, 495.0, 13.9, 5500.0))
        self.assertIn('calepinage retenu #12 : chaîne CH1 de 10 modules',
                      chaine['sources'])
        self.assertFalse(chaine['corrigee'])
        self.assertEqual((servi['temperature_c'], servi['eclairement_w_m2']),
                         (exemple['temperature_c'], exemple['eclairement_w_m2']))

    def test_sans_calepinage_retenu_liste_vide_et_motif(self):
        servi = self._servir(None)
        vide = _contrat_valeurs_attendues()['exemple_sans_calepinage']
        self.assertEqual(set(servi), set(vide))
        self.assertEqual(servi['chaines'], [])
        self.assertEqual(servi['motif'], vide['motif'])


User = get_user_model()


class ValeursAttenduesRecetteTest(TestCase):
    """ACAL667 — l'action ``valeurs-attendues`` : lecture tout rôle, bornée
    à la société du demandeur (mutant « lire un autre chantier » ⇒ 404)."""

    def setUp(self):
        from apps.installations.services import ensure_commissioning_record

        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.user = User.objects.create_user(
            username=f'acal667-{self.company.pk}', password='x',
            role_legacy='technicien', company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        chantier = make_installation(self.company, self.client_obj, self.devis)
        self.record = ensure_commissioning_record(chantier, self.user)
        self.url = (f'/api/django/installations/recettes-commissioning/'
                    f'{self.record.pk}/valeurs-attendues/')

    def test_sans_calepinage_retenu_chaines_vides_et_motif(self):
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['chaines'], [])
        self.assertEqual(reponse.data['motif'],
                         _contrat_valeurs_attendues()['exemple_sans_calepinage']['motif'])

    def test_calepinage_retenu_dix_modules_rend_495_v(self):
        with mock.patch('apps.calepinage.selectors.calepinage_retenu_pour_devis',
                        return_value={'id': 12}), \
                mock.patch('apps.calepinage.selectors_chantier.'
                           'valeurs_attendues_par_chaine',
                           side_effect=_valeurs_du_selecteur):
            reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['chaines'][0]['voc_attendu_v'], 495.0)

    def test_fiche_d_une_autre_societe_refusee(self):
        autre = make_company()
        intrus = User.objects.create_user(
            username=f'acal667-intrus-{autre.pk}', password='x',
            role_legacy='responsable', company=autre)
        api = APIClient()
        api.force_authenticate(intrus)
        self.assertEqual(api.get(self.url).status_code, 404)


def _contrat_plan_pose():
    chemin = (pathlib.Path(__file__).resolve().parent / 'contract_samples'
              / 'calepinage_plan_pose.json')
    return json.loads(chemin.read_text(encoding='utf-8'))


class PlanPoseDuChantierFormeTest(SimpleTestCase):
    """ACAL589 — ``plan_pose_du_chantier`` rend la forme du contrat."""

    def _servir(self, plan, devis_id=7):
        from apps.installations.calepinage_retenu import plan_pose_du_chantier

        chantier = SimpleNamespace(pk=31, devis_id=devis_id, company='societe')
        with mock.patch('apps.calepinage.selectors_chantier.plan_pose_svg_pour_devis',
                        return_value=plan) as lecture:
            return plan_pose_du_chantier(chantier), lecture

    def test_le_plan_et_l_empreinte_sont_servis(self):
        exemple = _contrat_plan_pose()['exemple']
        servi, lecture = self._servir({
            'calepinage_id': exemple['calepinage_id'], 'svg': exemple['plan_pose_svg'],
            'empreinte': exemple['empreinte'], 'motif': ''})
        self.assertEqual(servi, exemple)
        lecture.assert_called_once_with(7, 'societe')

    def test_sans_calepinage_plan_null_et_motif(self):
        servi, _lecture = self._servir(None)
        self.assertEqual(servi, _contrat_plan_pose()['exemple_sans_plan'])

    def test_sans_devis_rien_n_est_lu(self):
        servi, lecture = self._servir(None, devis_id=None)
        self.assertIsNone(servi['plan_pose_svg'])
        lecture.assert_not_called()

    def test_conception_changee_motif_tel_que_servi(self):
        from apps.calepinage.selectors_chantier import MOTIF_CONCEPTION_CHANGEE

        changee = _contrat_plan_pose()['exemple_conception_changee']
        self.assertEqual(changee['motif'], MOTIF_CONCEPTION_CHANGEE)
        servi, _lecture = self._servir({
            'calepinage_id': 12, 'svg': None, 'empreinte': changee['empreinte'],
            'motif': MOTIF_CONCEPTION_CHANGEE})
        self.assertEqual(servi, changee)


class PlanPoseRouteTest(TestCase):
    """ACAL589 — ``GET chantiers/<pk>/plan-pose/`` : tout rôle, borné société."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.client_obj)
        self.chantier = make_installation(self.company, self.client_obj, self.devis)
        self.user = User.objects.create_user(
            username=f'acal589-{self.company.pk}', password='x',
            role_legacy='technicien', company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = f'/api/django/installations/chantiers/{self.chantier.pk}/plan-pose/'

    def test_la_route_rend_le_svg_et_l_empreinte(self):
        exemple = _contrat_plan_pose()['exemple']
        with mock.patch('apps.calepinage.selectors_chantier.plan_pose_svg_pour_devis',
                        return_value={'calepinage_id': 12, 'svg': exemple['plan_pose_svg'],
                                      'empreinte': exemple['empreinte'], 'motif': ''}):
            reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['plan_pose_svg'], exemple['plan_pose_svg'])
        self.assertEqual(reponse.data['empreinte'], exemple['empreinte'])

    def test_sans_calepinage_plan_null_et_motif(self):
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data, _contrat_plan_pose()['exemple_sans_plan'])

    def test_chantier_d_une_autre_societe_404(self):
        autre = make_company()
        intrus = User.objects.create_user(
            username=f'acal589-intrus-{autre.pk}', password='x',
            role_legacy='responsable', company=autre)
        api = APIClient()
        api.force_authenticate(intrus)
        self.assertEqual(api.get(self.url).status_code, 404)
