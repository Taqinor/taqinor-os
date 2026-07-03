"""
XMFG3 — Assembler-à-la-commande : ordre d'assemblage depuis un devis/chantier
+ suggestion réappro-assemblage.

Couvre :
  * depuis un devis contenant un composite (produit_compose d'un kit actif) on
    crée l'ordre lié en un clic ;
  * l'appel est idempotent (get_or_create par devis+kit) ;
  * le coût du chantier lié voit l'ordre (lecture, via `chantier` FK) ;
  * la suggestion réappro (FG54) distingue acheter vs assembler.

Run :
    python manage.py test apps.installations.tests_xmfg3_ato -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.installations.models import Kit, KitComposant, OrdreAssemblage, Installation

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xmfg3-co-{n}', defaults={'nom': nom or f'XMFG3 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'xmfg3-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_produit(company, nom='Disjoncteur', stock=100, seuil=0):
    from apps.stock.models import Produit
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-{company.id}-{n}',
        prix_vente=200, prix_achat=0, quantite_stock=stock, seuil_alerte=seuil)


def make_devis_with_lines(company, lines):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'xmfg3-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-XMFG3-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    return devis


class TestAssemblerALaCommande(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.composite = make_produit(self.company, nom='Coffret', stock=0)
        self.comp1 = make_produit(self.company, nom='Disjoncteur', stock=50)
        self.kit = Kit.objects.create(
            company=self.company, nom='Coffret AC/DC',
            produit_compose=self.composite)
        KitComposant.objects.create(kit=self.kit, produit=self.comp1, quantite=2)

    def test_depuis_devis_cree_ordre_lie(self):
        devis = make_devis_with_lines(self.company, [(self.composite, 3)])
        resp = self.api.post(f'{BASE}/ordres-assemblage/depuis-devis/', {
            'devis': devis.id,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(len(resp.data), 1)
        ordre = OrdreAssemblage.objects.get(devis=devis, kit=self.kit)
        self.assertEqual(ordre.quantite, 3)
        self.assertTrue(ordre.reference.startswith('ASM-'))

    def test_depuis_devis_idempotent(self):
        devis = make_devis_with_lines(self.company, [(self.composite, 2)])
        r1 = self.api.post(f'{BASE}/ordres-assemblage/depuis-devis/', {
            'devis': devis.id,
        }, format='json')
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self.api.post(f'{BASE}/ordres-assemblage/depuis-devis/', {
            'devis': devis.id,
        }, format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(
            OrdreAssemblage.objects.filter(devis=devis, kit=self.kit).count(), 1)

    def test_devis_sans_composite_ne_cree_rien(self):
        autre = make_produit(self.company, nom='Simple SKU')
        devis = make_devis_with_lines(self.company, [(autre, 1)])
        resp = self.api.post(f'{BASE}/ordres-assemblage/depuis-devis/', {
            'devis': devis.id,
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data, [])

    def test_chantier_lie_voit_ordre(self):
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'xmfg3-chantier-{self.company.id}@example.invalid')
        chantier = Installation.objects.create(
            company=self.company, reference='CH-XMFG3-1', client=client)
        ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-CH-1', kit=self.kit,
            quantite=1, chantier=chantier)
        self.assertEqual(chantier.ordres_assemblage.count(), 1)
        self.assertEqual(chantier.ordres_assemblage.first().id, ordre.id)

    def test_reappro_distingue_acheter_vs_assembler(self):
        from apps.stock.services import produits_a_reapprovisionner
        self.composite.seuil_alerte = 5
        self.composite.save(update_fields=['seuil_alerte'])
        autre = make_produit(self.company, nom='Simple SKU', stock=0, seuil=5)
        result = produits_a_reapprovisionner(self.company)
        by_id = {r['produit_id']: r for r in result}
        self.assertEqual(by_id[self.composite.id]['action'], 'assembler')
        self.assertEqual(by_id[self.composite.id]['kit_id'], self.kit.id)
        self.assertEqual(by_id[autre.id]['action'], 'acheter')
        self.assertIsNone(by_id[autre.id]['kit_id'])
