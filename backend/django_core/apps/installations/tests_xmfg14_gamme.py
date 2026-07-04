"""
XMFG14 — Gamme légère : étapes d'assemblage avec instructions et temps.

Couvre :
  * un kit avec étapes affiche le mode opératoire sur l'ordre (instanciation
    à la volée) ;
  * chaque étape se coche avec un temps réel saisi (fait/par qui/quand posés
    côté serveur) ;
  * les totaux prévu/réel sur l'ordre sont corrects ;
  * un kit sans étape n'affiche rien (comportement inchangé).

Run :
    python manage.py test apps.installations.tests_xmfg14_gamme -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Kit, KitComposant, OrdreAssemblage, EtapeAssemblage

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg14-co-{n}', defaults={'nom': nom or f'XMFG14 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg14-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=0,
        quantite_stock=stock)


class TestGammeEtapes(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(self.company, nom='Disjoncteur', stock=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret', produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=1)

    def test_kit_sans_etape_liste_vide(self):
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-G1', kit=self.kit, quantite=1)
        resp = self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/etapes/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data, [])

    def test_kit_avec_etapes_affiche_mode_operatoire(self):
        EtapeAssemblage.objects.create(
            kit=self.kit, ordre=1, libelle='Câblage AC',
            instructions='Respecter le code couleur.', duree_attendue_min=15)
        EtapeAssemblage.objects.create(
            kit=self.kit, ordre=2, libelle='Test isolement',
            duree_attendue_min=5)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-G2', kit=self.kit, quantite=1)
        resp = self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/etapes/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data), 2)
        self.assertEqual(resp.data[0]['libelle'], 'Câblage AC')
        self.assertEqual(resp.data[0]['instructions'], 'Respecter le code couleur.')
        self.assertFalse(resp.data[0]['fait'])

    def test_cocher_etape_pose_fait_par_et_duree(self):
        etape = EtapeAssemblage.objects.create(
            kit=self.kit, ordre=1, libelle='Câblage AC', duree_attendue_min=15)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-G3', kit=self.kit, quantite=1)
        self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/etapes/')
        resp = self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/etapes/{etape.id}/cocher/',
            {'fait': 'true', 'duree_reelle_min': 18}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['fait'])
        self.assertEqual(resp.data['duree_reelle_min'], 18)
        self.assertEqual(resp.data['fait_par_nom'], self.user.username)
        self.assertIsNotNone(resp.data['fait_le'])

    def test_totaux_prevu_reel_sur_ordre(self):
        EtapeAssemblage.objects.create(
            kit=self.kit, ordre=1, libelle='Câblage AC', duree_attendue_min=15)
        etape2 = EtapeAssemblage.objects.create(
            kit=self.kit, ordre=2, libelle='Test isolement',
            duree_attendue_min=5)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-G4', kit=self.kit, quantite=1)
        self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/etapes/')
        self.api.post(
            f'{BASE}/ordres-assemblage/{ordre.id}/etapes/{etape2.id}/cocher/',
            {'fait': 'true', 'duree_reelle_min': 8}, format='json')
        resp = self.api.get(f'{BASE}/ordres-assemblage/{ordre.id}/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['temps_prevu_min'], 20)
        self.assertEqual(resp.data['temps_reel_min'], 8)
