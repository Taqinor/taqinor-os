"""XPUR22 — Portail fournisseur lecture seule + confirmation de date
d'arrivée.

Couvre :
  * un jeton valide voit SES documents (BCF/réceptions/factures) ;
  * l'isolation inter-fournisseurs est stricte (jamais les documents d'un
    autre fournisseur) ;
  * un jeton révoqué ou expiré est refusé (404, pas de fuite de données) ;
  * le fournisseur peut confirmer un BCF + proposer une date d'arrivée, en
    préservant la date DEMANDÉE d'origine (OTD, XPUR7) ;
  * confirmer un BCF d'un AUTRE fournisseur via ce jeton est refusé.

Run:
    python manage.py test apps.stock.test_xpur22_portail_fournisseur -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    PortailFournisseurToken, Produit,
)
from apps.stock.services import (
    confirmer_bcf_portail_fournisseur, generer_token_portail_fournisseur,
    portail_fournisseur_documents, resoudre_token_portail_fournisseur,
    revoquer_token_portail_fournisseur,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur22Base(TestCase):
    def setUp(self):
        self.company = _company('xpur22-co')
        self.user = _user(
            self.company, 'xpur22-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Portail X22')
        self.autre_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Autre Fournisseur X22')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X22', sku='OND-XPUR22',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf(self, fournisseur, statut=BonCommandeFournisseur.Statut.ENVOYE,
             date_livraison_prevue=None):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-X22-{fournisseur.id}',
            fournisseur=fournisseur, statut=statut,
            date_livraison_prevue=date_livraison_prevue,
            created_by=self.user)
        bc.lignes.create(
            produit=self.produit, quantite=2,
            prix_achat_unitaire=Decimal('1200'))
        return bc


class TestGenerationEtResolution(Xpur22Base):
    def test_generer_token_puis_resoudre(self):
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        resolved = resoudre_token_portail_fournisseur(token_obj.token)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.fournisseur_id, self.fournisseur.id)

    def test_token_inconnu_renvoie_none(self):
        self.assertIsNone(
            resoudre_token_portail_fournisseur('inconnu-xyz'))

    def test_token_revoque_invalide(self):
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        revoquer_token_portail_fournisseur(token_obj)
        self.assertIsNone(
            resoudre_token_portail_fournisseur(token_obj.token))

    def test_token_expire_invalide(self):
        token_obj = PortailFournisseurToken.objects.create(
            company=self.company, fournisseur=self.fournisseur,
            expires_at=timezone.now() - datetime.timedelta(days=1))
        self.assertIsNone(
            resoudre_token_portail_fournisseur(token_obj.token))


class TestDocumentsFournisseur(Xpur22Base):
    def test_documents_isoles_par_fournisseur(self):
        self._bcf(self.fournisseur)
        self._bcf(self.autre_fournisseur)
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        data = portail_fournisseur_documents(token_obj)
        self.assertEqual(len(data['bons_commande']), 1)
        self.assertEqual(
            data['bons_commande'][0]['reference'],
            f'BCF-X22-{self.fournisseur.id}')

    def test_factures_du_fournisseur_uniquement(self):
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-X22-MINE',
            fournisseur=self.fournisseur, montant_ttc=Decimal('1000'))
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-X22-AUTRE',
            fournisseur=self.autre_fournisseur, montant_ttc=Decimal('2000'))
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        data = portail_fournisseur_documents(token_obj)
        refs = {f['reference'] for f in data['factures']}
        self.assertEqual(refs, {'FF-X22-MINE'})

    def test_endpoint_public_documents(self):
        self._bcf(self.fournisseur)
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        resp = self.api.get(
            f'/api/django/public/stock/portail-fournisseur/'
            f'{token_obj.token}/')
        # AllowAny — fonctionne même SANS le jeton d'auth interne.
        anon = APIClient()
        resp = anon.get(
            f'/api/django/public/stock/portail-fournisseur/'
            f'{token_obj.token}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['bons_commande']), 1)

    def test_endpoint_public_jeton_invalide_404(self):
        anon = APIClient()
        resp = anon.get(
            '/api/django/public/stock/portail-fournisseur/bidon/')
        self.assertEqual(resp.status_code, 404)


class TestConfirmationArrivee(Xpur22Base):
    def test_confirmer_bcf_preserve_date_demandee(self):
        bc = self._bcf(
            self.fournisseur,
            date_livraison_prevue=datetime.date(2026, 7, 1))
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        confirmer_bcf_portail_fournisseur(
            token_obj, bc.id, date_confirmee='2026-07-10',
            numero_confirmation='CONF-001')
        bc.refresh_from_db()
        self.assertEqual(
            str(bc.date_confirmee_fournisseur), '2026-07-10')
        # La date DEMANDÉE d'origine n'est jamais écrasée (OTD).
        self.assertEqual(
            bc.date_livraison_prevue, datetime.date(2026, 7, 1))

    def test_confirmer_bcf_autre_fournisseur_refuse(self):
        bc_autre = self._bcf(self.autre_fournisseur)
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        with self.assertRaises(ValueError):
            confirmer_bcf_portail_fournisseur(
                token_obj, bc_autre.id, date_confirmee='2026-07-10')

    def test_endpoint_public_confirmer(self):
        bc = self._bcf(
            self.fournisseur,
            date_livraison_prevue=datetime.date(2026, 7, 1))
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        anon = APIClient()
        resp = anon.post(
            f'/api/django/public/stock/portail-fournisseur/'
            f'{token_obj.token}/bcf/{bc.id}/confirmer/',
            {'date_confirmee_fournisseur': '2026-07-15'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        bc.refresh_from_db()
        self.assertEqual(
            str(bc.date_confirmee_fournisseur), '2026-07-15')

    def test_endpoint_public_confirmer_autre_fournisseur_404(self):
        bc_autre = self._bcf(self.autre_fournisseur)
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        anon = APIClient()
        resp = anon.post(
            f'/api/django/public/stock/portail-fournisseur/'
            f'{token_obj.token}/bcf/{bc_autre.id}/confirmer/',
            {'date_confirmee_fournisseur': '2026-07-15'}, format='json')
        self.assertEqual(resp.status_code, 404)


class TestGestionTokensInterne(Xpur22Base):
    def test_generation_via_api(self):
        resp = self.api.post(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
            'portail-tokens/')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('token', resp.data)

    def test_liste_via_api(self):
        generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        resp = self.api.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
            'portail-tokens/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_revocation_via_api(self):
        token_obj = generer_token_portail_fournisseur(
            self.company, self.fournisseur, self.user)
        resp = self.api.post(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
            f'portail-tokens/{token_obj.id}/revoquer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        token_obj.refresh_from_db()
        self.assertTrue(token_obj.revoked)
