"""Tests FG229–FG244 — Portail client, partenaires, fidélité & abonnements.

Couvrent, par tâche (tous scopés société, ``company`` jamais lue du corps) :

* FG229 Acceptation/e-signature de devis (portail) — signature horodatée + IP.
* FG230 Paiement en ligne de facture (portail) — NO-OP gated (CMI OFF défaut).
* FG231 Dépôt de documents/factures ONEE par le client.
* FG232 Suivi d'avancement chantier côté client — jalons lecture-seule.
* FG233 Ticket SAV depuis le portail — création/suivi.
* FG234 Portail apporteurs / sous-revendeurs — soumission de leads + statut.
* FG235 Suivi des commissions partenaires.
* FG236 Gestion des territoires / zones commerciales.
* FG237 Annuaire & onboarding des installateurs partenaires.
* FG238 Enquêtes NPS / satisfaction — NO-OP gated + score consolidé.
* FG239 Capture d'avis + push Google Reviews — NO-OP gated.
* FG240 Programme de fidélité / parrainage étendu (points/paliers).
* FG241 Moteur d'upsell / cross-sell.
* FG244 Abonnements de monitoring (revenu récurrent).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import AcceptationDevisPortail

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


# ── FG229 — Acceptation / e-signature de devis (portail) ───────────────────

class AcceptationDevisPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg229', 'FG229')
        self.user = make_user(self.co, 'fg229-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/acceptations-devis-portail/', {
            'devis_id': 41001, 'option_choisie': 'Hybride 5 kWc',
            'nom_signataire': 'Reda K.',
            'company': 99999,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        acc = AcceptationDevisPortail.objects.get(id=resp.data['id'])
        self.assertEqual(acc.company_id, self.co.id)
        self.assertFalse(acc.accepte)
        self.assertIsNone(acc.signe_le)

    def test_signer_horodate_et_capture_ip(self):
        api = auth(self.user)
        acc = AcceptationDevisPortail.objects.create(
            company=self.co, devis_id=41002, nom_signataire='Sami')
        resp = api.post(
            f'/api/django/compta/acceptations-devis-portail/{acc.id}/signer/',
            {'nom_signataire': 'Sami B.'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        acc.refresh_from_db()
        self.assertTrue(acc.accepte)
        self.assertIsNotNone(acc.signe_le)
        self.assertEqual(acc.nom_signataire, 'Sami B.')
        self.assertIsNotNone(acc.signature_ip)

    def test_signer_idempotent(self):
        acc = AcceptationDevisPortail.objects.create(
            company=self.co, devis_id=41003, nom_signataire='X')
        services.signer_acceptation_devis(acc, nom='Premier', ip='10.0.0.1')
        premier_horodatage = acc.signe_le
        services.signer_acceptation_devis(acc, nom='Second', ip='10.0.0.2')
        acc.refresh_from_db()
        # Pas resigné : nom & horodatage figés à la première signature.
        self.assertEqual(acc.nom_signataire, 'Premier')
        self.assertEqual(acc.signe_le, premier_horodatage)

    def test_isolation_societe(self):
        autre = make_company('fg229-b', 'FG229B')
        AcceptationDevisPortail.objects.create(
            company=autre, devis_id=41004, nom_signataire='Autre')
        api = auth(self.user)
        resp = api.get('/api/django/compta/acceptations-devis-portail/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
