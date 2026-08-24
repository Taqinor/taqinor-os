"""
BUGFIX (24/08/2026) — badge de niveau L-NIV absent au chargement de la fiche.

L'anticopie deux niveaux (`ShareLink.niveau` standard/confiance, PR #560)
n'alimentait le badge/sélecteur de l'onglet Devis (DevisTab.jsx) qu'APRÈS un
POST explicite sur `share-link/` (mint ou re-mint) : le serveur connaissait
déjà le niveau du lien mais l'UI ne le relisait jamais au montage, donc rien
ne s'affichait tant que le commercial n'avait pas re-cliqué.

Ce test vérifie le côté serveur du correctif : le détail du lead
(`GET /crm/leads/<id>/`) expose désormais, PAR devis, l'état du ShareLink déjà
existant (`share_link: {niveau, otp_lecture}`) SANS jamais en minter un —
via le sélecteur cross-app en lecture seule
`apps.ventes.selectors.share_link_niveau_map` (CLAUDE.md : les lectures
inter-app passent par le `selectors.py` de l'app CIBLE, jamais ses modèles).

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_lniv_share_link_lecture -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.selectors import share_link_niveau_map

User = get_user_model()


def make_company(slug='lniv-lect-co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_client(company, slug):
    return Client.objects.create(
        company=company, nom='Client', prenom=slug,
        email=f'{slug}@example.com', telephone='+212600000020')


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestShareLinkNiveauMapSelector(TestCase):
    """(a) le sélecteur cross-app pur : jamais de mint, jamais de token exposé."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='lniv_lect_u', password='x',
            role_legacy='responsable', company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lect', prenom='Test',
            email='lniv-lect@example.com', telephone='0612345678')
        self.client_obj = make_client(self.company, 'lniv-lect-a')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-LNIV-LECT1', lead=self.lead,
            client=self.client_obj,
            statut='envoye', taux_tva=20, remise_globale=0,
            created_by=self.user)

    def test_returns_empty_for_devis_without_link(self):
        self.assertEqual(share_link_niveau_map([self.devis.id]), {})

    def test_returns_niveau_otp_for_existing_link_without_minting(self):
        ShareLink.objects.create(
            company=self.company, devis=self.devis,
            niveau=ShareLink.NIVEAU_CONFIANCE, otp_lecture=True)
        before = ShareLink.objects.count()
        result = share_link_niveau_map([self.devis.id])
        after = ShareLink.objects.count()
        self.assertEqual(after, before, 'la lecture ne doit jamais minter de lien')
        self.assertEqual(result, {
            self.devis.id: {'niveau': 'confiance', 'otp_lecture': True},
        })
        self.assertNotIn('token', result[self.devis.id])

    def test_empty_ids_returns_empty_dict(self):
        self.assertEqual(share_link_niveau_map([]), {})
        self.assertEqual(share_link_niveau_map(None), {})


class TestLeadDetailExposesShareLinkState(TestCase):
    """(b) bout en bout : GET fiche lead → devis[].share_link."""

    def setUp(self):
        self.company = make_company('lniv-lect-e2e')
        self.user = User.objects.create_user(
            username='lniv_lect_e2e', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='E2E', prenom='Lect',
            email='lniv-lect-e2e@example.com', telephone='0612345678')
        self.client_obj = make_client(self.company, 'lniv-lect-b')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-LNIV-LECT2', lead=self.lead,
            client=self.client_obj,
            statut='envoye', taux_tva=20, remise_globale=0,
            created_by=self.user)
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 5kW',
            prix_achat=0, prix_vente=8000, quantite_stock=10)
        LigneDevis.objects.create(
            devis=self.devis, produit=produit, designation='Onduleur réseau 5kW',
            quantite=1, prix_unitaire=8000, remise=0)

    def _devis_row(self, resp):
        return next(d for d in resp.data['devis'] if d['id'] == self.devis.id)

    def test_devis_without_share_link_carries_null(self):
        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(self._devis_row(resp)['share_link'])

    def test_devis_with_existing_share_link_exposes_niveau_without_minting(self):
        ShareLink.objects.create(
            company=self.company, devis=self.devis,
            niveau=ShareLink.NIVEAU_CONFIANCE, otp_lecture=True)
        links_before = ShareLink.objects.filter(devis=self.devis).count()

        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')

        self.assertEqual(resp.status_code, 200)
        row = self._devis_row(resp)
        self.assertEqual(row['share_link'], {'niveau': 'confiance', 'otp_lecture': True})
        # Simple lecture : aucun nouveau ShareLink créé par le chargement de la fiche.
        self.assertEqual(
            ShareLink.objects.filter(devis=self.devis).count(), links_before)

    def test_switching_niveau_via_share_link_action_reflects_in_lead_detail(self):
        """Le POST share-link (déjà couvert par test_l_niv_niveau.py) change le
        niveau ; ce test prouve que la LECTURE fiche lead voit bien ce
        changement — le chaînon qui manquait côté écran."""
        post = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/share-link/',
            {'niveau': 'confiance', 'otp_lecture': True}, format='json')
        self.assertEqual(post.status_code, 200, post.data)

        resp = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        row = self._devis_row(resp)
        self.assertEqual(row['share_link'], {'niveau': 'confiance', 'otp_lecture': True})
