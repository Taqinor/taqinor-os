"""ZMFG10 — Bon d'assemblage imprimable (worksheet atelier PDF).

Odoo imprime un document d'ordre de fabrication + une feuille d'opération ;
`OrdreAssemblage` n'avait AUCUN imprimable. Couvre :

  * le PDF liste composants + étapes + zones série/signature ;
  * se génère pour un ordre planifié (200, `application/pdf`) ;
  * dégrade proprement sans étapes de gamme (XMFG14 absent — pas de section
    vide, aucune erreur) ;
  * non-régression : aucun prix (`prix_achat`/`prix_vente`) dans le contexte
    de rendu ni dans le code source du module.

Run :
    python manage.py test \
        apps.installations.tests_zmfg10_bon_assemblage_pdf -v2
"""
import itertools
import inspect

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, EtapeAssemblage,
)
from apps.installations import assembly_pdf

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'zmfg10-co-{n}', defaults={'nom': f'ZMFG10 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zmfg10-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Disjoncteur'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=200, prix_achat=90,
        quantite_stock=50)


class TestBonAssemblagePdf(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret AC/DC', created_by=self.user)
        self.produit = make_produit(self.company)
        KitComposant.objects.create(
            kit=self.kit, produit=self.produit, quantite=2)
        self.ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ZMFG10-0001',
            kit=self.kit, quantite=3,
            statut=OrdreAssemblage.Statut.PLANIFIE)

    def test_endpoint_renvoie_un_pdf(self):
        r = self.api.get(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/bon-pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_degrade_sans_etapes_gamme(self):
        """Aucune EtapeAssemblage sur le kit -> pas de section gamme, pas
        d'erreur (dégrade proprement)."""
        self.assertEqual(assembly_pdf._etapes_payload(self.ordre), [])
        r = self.api.get(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/bon-pdf/')
        self.assertEqual(r.status_code, 200)

    def test_avec_etapes_gamme(self):
        EtapeAssemblage.objects.create(
            kit=self.kit, ordre=1, libelle='Câblage DC',
            instructions='Respecter le code couleur.')
        etapes = assembly_pdf._etapes_payload(self.ordre)
        self.assertEqual(len(etapes), 1)
        self.assertEqual(etapes[0]['libelle'], 'Câblage DC')
        r = self.api.get(
            f'{BASE}/ordres-assemblage/{self.ordre.id}/bon-pdf/')
        self.assertEqual(r.status_code, 200)

    def test_composants_repli_bom_kit_sans_lignes(self):
        composants = assembly_pdf._composants_payload(self.ordre)
        self.assertEqual(len(composants), 1)
        self.assertEqual(composants[0]['designation'], self.produit.nom)
        self.assertEqual(composants[0]['quantite'], 6)  # 2 × quantite(3)

    def test_aucun_prix_dans_le_contexte_ni_le_code(self):
        composants = assembly_pdf._composants_payload(self.ordre)
        for c in composants:
            self.assertNotIn('prix_achat', c)
            self.assertNotIn('prix_vente', c)
            self.assertNotIn('cout', c)
        source = inspect.getsource(assembly_pdf)
        self.assertNotIn('prix_achat', source)
        self.assertNotIn('prix_vente', source)
