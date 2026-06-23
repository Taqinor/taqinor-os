"""U9 — Réservation de stock sur la facturation directe par échéancier.

Le stock matériel n'était décrémenté que lors de la livraison d'un bon de
commande (``marquer-livre``). Un devis accepté puis facturé EN DIRECT via
``generer-facture`` (échéancier) court-circuitait le BC et ne réservait aucun
stock — d'où une survente possible entre devis.

Couvre :
  * la facturation directe réserve/consomme le stock une fois (mouvement SORTIE
    par ligne du devis) ;
  * une 2e/3e tranche de l'échéancier ne re-décompte PAS (réservation unique
    par devis) ;
  * un devis dont le BC est déjà LIVRÉ (stock déjà consommé) n'est PAS re-
    décompté lors de la facturation directe ;
  * la garde de stock insuffisant refuse (400) et n'écrit rien (transaction
    annulée — ni facture ni mouvement).

Run :
    python manage.py test apps.ventes.tests.test_facture_stock_reservation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import MouvementStock, Produit
from apps.ventes.models import BonCommande, Devis, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='u9-co', nom='U9 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class U9StockReservationTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='u9_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='U9', prenom='Client',
            email='u9@example.com', telephone='+212600000003',
            adresse='Casablanca')
        # Deux produits : panneau (stock large), onduleur (stock juste).
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau PV 450W', sku='PV-450U9',
            prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('20.00'))
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur 5kW', sku='OND-5U9',
            prix_vente=Decimal('5000'), quantite_stock=3, tva=Decimal('20.00'))

    def _devis(self, ref, *, panneaux=10, onduleurs=1):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.cl,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20.00'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau PV 450W',
            quantite=Decimal(panneaux), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur, designation='Onduleur 5kW',
            quantite=Decimal(onduleurs), prix_unitaire=Decimal('5000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return devis

    def _gen(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')

    def _sorties(self, produit):
        return MouvementStock.objects.filter(
            company=self.company, produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE)

    def test_direct_invoice_reserves_stock_once(self):
        devis = self._devis(f'DEV-{MONTH}-9101')
        r = self._gen(devis)
        self.assertEqual(r.status_code, 201, r.data)
        self.panneau.refresh_from_db()
        self.onduleur.refresh_from_db()
        # Le stock est décrémenté de la quantité du devis (10 panneaux, 1 ond.).
        self.assertEqual(self.panneau.quantite_stock, 90)
        self.assertEqual(self.onduleur.quantite_stock, 2)
        self.assertEqual(self._sorties(self.panneau).count(), 1)
        self.assertEqual(self._sorties(self.onduleur).count(), 1)

    def test_subsequent_tranches_do_not_double_count(self):
        devis = self._devis(f'DEV-{MONTH}-9102')
        # 3 tranches (30/60/10) — le stock ne doit bouger qu'à la 1re.
        for _ in range(3):
            self.assertEqual(self._gen(devis).status_code, 201)
        self.panneau.refresh_from_db()
        self.onduleur.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 90)
        self.assertEqual(self.onduleur.quantite_stock, 2)
        # Une seule SORTIE par produit pour tout l'échéancier.
        self.assertEqual(self._sorties(self.panneau).count(), 1)
        self.assertEqual(self._sorties(self.onduleur).count(), 1)

    def test_no_double_count_when_bc_already_delivered(self):
        devis = self._devis(f'DEV-{MONTH}-9103')
        # Chemin BC : confirmer puis livrer → décrémente déjà le stock.
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-9103',
            devis=devis, client=self.cl, statut=BonCommande.Statut.CONFIRME)
        livr = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/marquer-livre/',
            {}, format='multipart')
        self.assertEqual(livr.status_code, 200, livr.content)
        self.panneau.refresh_from_db()
        self.onduleur.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 90)
        self.assertEqual(self.onduleur.quantite_stock, 2)
        # Facturation directe ensuite : NE DOIT PAS re-décompter.
        r = self._gen(devis)
        self.assertEqual(r.status_code, 201, r.data)
        self.panneau.refresh_from_db()
        self.onduleur.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 90)
        self.assertEqual(self.onduleur.quantite_stock, 2)
        # Toujours une seule SORTIE par produit (celle du BC).
        self.assertEqual(self._sorties(self.panneau).count(), 1)
        self.assertEqual(self._sorties(self.onduleur).count(), 1)

    def test_insufficient_stock_blocks_invoice_and_writes_nothing(self):
        # Onduleur demandé : 5 alors que stock = 3 → 400, rien écrit.
        devis = self._devis(f'DEV-{MONTH}-9104', panneaux=2, onduleurs=5)
        r = self._gen(devis)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Stock insuffisant', r.data['detail'])
        self.panneau.refresh_from_db()
        self.onduleur.refresh_from_db()
        # Transaction annulée : ni mouvement, ni facture.
        self.assertEqual(self.panneau.quantite_stock, 100)
        self.assertEqual(self.onduleur.quantite_stock, 3)
        self.assertEqual(self._sorties(self.panneau).count(), 0)
        self.assertEqual(self._sorties(self.onduleur).count(), 0)
        self.assertEqual(devis.factures.count(), 0)
