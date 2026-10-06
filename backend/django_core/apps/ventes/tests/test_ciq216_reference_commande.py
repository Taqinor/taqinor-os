"""CIQ216 — référence de commande du client portée par le devis, héritée par
la facture de BC et chaque facture de tranche, imprimée sur la facture.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_ciq216_reference_commande"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()

ECHEANCIER = [
    {'type': 'acompte', 'pct_or_montant': 40},
    {'type': 'solde', 'pct_or_montant': 60},
]


class _Base(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='ciq216-co', defaults={'nom': 'CIQ216 Co'})[0]
        self.client_obj = Client.objects.create(
            company=self.company, nom='Usine', prenom='CIQ216',
            email='ciq216@example.com')
        self.user = User.objects.create_user(
            username='ciq216_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, ref, statut='accepte', reference_client=''):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20.00'),
            mode_installation='commercial', echeancier=ECHEANCIER,
            reference_commande_client=reference_client)
        from apps.stock.models import Produit
        # Une ligne PRODUIT référence toujours un produit (l'API le refuse
        # sinon, ``LigneDevisSerializer``) — et ``LigneFacture.produit`` est
        # NOT NULL : sans lui, la facture de BC recopiant la ligne lève 500.
        produit = Produit.objects.create(
            company=self.company, nom='Centrale PV',
            prix_vente=Decimal('50000'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Centrale PV',
            quantite=Decimal('1'),
            prix_unitaire=Decimal('50000'), remise=Decimal('0'),
            taux_tva=Decimal('20.00'))
        return devis

    def _html(self, facture):
        from apps.ventes.utils.pdf import _company_context, _render_html
        ctx = _company_context(company=self.company)
        ctx['facture'] = facture
        return _render_html('facture.html', ctx)


class ReferenceSurDevisTest(_Base):
    def test_patch_entete_puis_vide_par_defaut(self):
        devis = self._devis('DEV-CIQ216-0010', statut='brouillon')
        self.assertEqual(devis.reference_commande_client, '')
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/',
                           {'reference_commande_client': 'BC-2026-0457'},
                           format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.reference_commande_client, 'BC-2026-0457')

    def test_plus_de_60_caracteres_refuse(self):
        devis = self._devis('DEV-CIQ216-0020', statut='brouillon')
        r = self.api.patch(f'/api/django/ventes/devis/{devis.id}/',
                           {'reference_commande_client': 'X' * 61},
                           format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('reference_commande_client', r.data)


class HeritageFacturesTest(_Base):
    def test_chaque_tranche_porte_la_reference(self):
        from apps.ventes.models import Facture
        devis = self._devis('DEV-CIQ216-0030',
                            reference_client='BC-2026-0457')
        for _ in ECHEANCIER:
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/generer-facture/')
            self.assertEqual(r.status_code, 201, r.data)
            facture = Facture.objects.get(pk=r.data['id'])
            self.assertEqual(facture.reference_commande_client,
                             'BC-2026-0457')
            self.assertIn('BC-2026-0457', self._html(facture))

    def test_facture_de_bc_porte_la_reference(self):
        from apps.ventes.models import BonCommande, Facture
        devis = self._devis('DEV-CIQ216-0040',
                            reference_client='OF-2026-118')
        bc = BonCommande.objects.create(
            company=self.company, reference='BC-CIQ216-0040', devis=devis,
            client=self.client_obj, statut=BonCommande.Statut.CONFIRME)
        r = self.api.post(
            f'/api/django/ventes/bons-commande/{bc.id}/creer-facture/',
            {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(bon_commande=bc)
        self.assertEqual(facture.reference_commande_client, 'OF-2026-118')
        self.assertEqual(r.data['reference_commande_client'], 'OF-2026-118')
        self.assertIn('Votre commande : OF-2026-118', self._html(facture))

    def test_vide_rien_imprime(self):
        from apps.ventes.models import Facture
        devis = self._devis('DEV-CIQ216-0050')
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/')
        self.assertEqual(r.status_code, 201, r.data)
        facture = Facture.objects.get(pk=r.data['id'])
        self.assertEqual(facture.reference_commande_client, '')
        self.assertNotIn('Votre commande', self._html(facture))
