"""AGR101 — fiches techniques typées « pompe » et « variateur de pompage ».

Contrat partagé : ``contract_samples/produit_pompage.json`` (clé ``fiches``).
Valeurs constructeur seulement : vide = « non publié », jamais 0.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
from apps.stock.models import FicheTechnique, Produit
from authentication.models import Company

User = get_user_model()

URL_FICHES = '/api/django/stock/fiches-techniques/'
CONTRAT = json.loads(
    (Path(__file__).parent / 'contract_samples' / 'produit_pompage.json')
    .read_text(encoding='utf-8'))


def api_for(user):
    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return client


class AGR101Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.get_or_create(
            slug='agr101-co', defaults={'nom': 'AGR101 Co'})[0]
        roles = {}
        for nom, perms in CANONICAL_SYSTEM_ROLES:
            roles[nom] = Role.objects.create(
                company=cls.company, nom=nom, permissions=list(perms),
                est_systeme=True)
        cls.user = User.objects.create_user(
            username='agr101_dir', password='x', company=cls.company,
            role=roles['Directeur'])
        cls.variateur = Produit.objects.create(
            company=cls.company, nom='Variateur test AGR101', prix_vente=1)
        cls.pompe = Produit.objects.create(
            company=cls.company, nom='Pompe test AGR101', prix_vente=1)


class TestTypesFiche(AGR101Base):
    def test_types_ajoutes_et_anciens_conserves(self):
        valeurs = [c[0] for c in FicheTechnique.TypeFiche.choices]
        for v in ('module', 'onduleur', 'batterie', 'optimiseur', 'autre',
                  'pompe', 'variateur_pompage'):
            self.assertIn(v, valeurs)

    def test_contrat_cles_fiches_presentes_sur_le_serializeur(self):
        from apps.stock.serializers import FicheTechniqueSerializer
        champs = set(FicheTechniqueSerializer().fields)
        for nom_fiche in ('pompe', 'variateur_pompage'):
            for cle in CONTRAT['fiches'][nom_fiche]['champs']:
                self.assertIn(cle, champs)
        for cle in CONTRAT['fiches']['variateur_pompage'][
                'champs_onduleur_reutilises']:
            self.assertIn(cle, champs)

    def test_fiche_vide_rend_null_jamais_zero(self):
        fiche = FicheTechnique.objects.create(
            company=self.company, produit=self.variateur,
            type_fiche='variateur_pompage')
        for cle in CONTRAT['fiches']['variateur_pompage']['champs']:
            self.assertIsNone(getattr(fiche, cle), cle)


class TestAllerRetourApi(AGR101Base):
    def test_fiche_variateur_aller_retour_identique(self):
        client = api_for(self.user)
        payload = {
            'produit': self.variateur.pk,
            'type_fiche': 'variateur_pompage',
            'ond_mppt_v_min': '200.0', 'ond_mppt_v_max': '800.0',
            'ond_v_max_abs': '850.0', 'ond_i_max_mppt_a': '15.0',
            'ond_phases': 3, 'ond_v_demarrage_v': '250.0',
            'var_voc_reco_min_v': '300.0', 'var_voc_reco_max_v': '750.0',
            'var_v_sortie_v': '380.0', 'var_i_sortie_nominal_a': '13.0',
            'var_protection_marche_a_sec': True,
            'var_rendement_mppt_pct': '99.00',
        }
        r = client.post(URL_FICHES, payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        url = f'{URL_FICHES}{r.data["id"]}/'
        avant = client.get(url).data
        for cle, val in payload.items():
            if cle == 'produit':
                continue
            self.assertEqual(str(avant[cle]), str(val), cle)
        # enregistrer sans toucher → objet serveur identique
        r = client.patch(url, {
            c: avant[c] for c in CONTRAT['fiches']['variateur_pompage'][
                'champs']}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        apres = client.get(url).data
        for cle in payload:
            self.assertEqual(avant[cle], apres[cle], cle)

    def test_fiche_pompe_aller_retour(self):
        client = api_for(self.user)
        payload = {
            'produit': self.pompe.pk, 'type_fiche': 'pompe',
            'pompe_i_nominal_a': '14.50', 'pompe_diametre_ext_mm': '98.0',
            'pompe_nb_etages': 12, 'pompe_immersion_min_m': '2.0',
            'pompe_rendement_pct': '62.50', 'pompe_q_nominal_m3h': '24.00',
            'pompe_hmt_nominale_m': '70.0',
        }
        r = client.post(URL_FICHES, payload, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        lu = client.get(f'{URL_FICHES}{r.data["id"]}/').data
        for cle, val in payload.items():
            if cle == 'produit':
                continue
            self.assertEqual(str(lu[cle]), str(val), cle)

    def test_fiche_module_existante_inchangee(self):
        fiche = FicheTechnique.objects.create(
            company=self.company, produit=self.pompe, type_fiche='module',
            pmax_wc=Decimal('550'), voc_v=Decimal('49.5'))
        lu = api_for(self.user).get(f'{URL_FICHES}{fiche.pk}/').data
        self.assertEqual(lu['type_fiche'], 'module')
        self.assertEqual(Decimal(str(lu['pmax_wc'])), Decimal('550'))
        self.assertEqual(Decimal(str(lu['voc_v'])), Decimal('49.5'))
        # les nouvelles clés sont servies « non publié » (null), jamais 0
        for cle in CONTRAT['fiches']['pompe']['champs']:
            self.assertIsNone(lu[cle], cle)
        for cle in CONTRAT['fiches']['variateur_pompage']['champs']:
            self.assertIsNone(lu[cle], cle)
