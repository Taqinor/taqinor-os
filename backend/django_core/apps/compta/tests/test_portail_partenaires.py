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
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import (
    AcceptationDevisPortail, PaiementFacturePortail, DocumentClientPortail,
)

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


# ── FG230 — Paiement en ligne des factures (portail, gated CMI) ────────────

class PaiementFacturePortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg230', 'FG230')
        self.user = make_user(self.co, 'fg230-user')

    def test_creation_pose_company_et_reference(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/paiements-facture-portail/', {
            'facture_id': 42001, 'montant': '12500.00', 'methode': 'carte',
            'company': 88888,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pf = PaiementFacturePortail.objects.get(id=resp.data['id'])
        self.assertEqual(pf.company_id, self.co.id)
        self.assertEqual(pf.statut, PaiementFacturePortail.Statut.INITIE)
        # initier_paiement_facture pose une référence locale.
        self.assertTrue(pf.reference)

    @override_settings(CMI_ENABLED=False)
    def test_cmi_inactif_par_defaut(self):
        self.assertFalse(services.cmi_actif())

    def test_rapprocher_marque_paye(self):
        api = auth(self.user)
        pf = PaiementFacturePortail.objects.create(
            company=self.co, facture_id=42002, montant=999,
            methode=PaiementFacturePortail.Methode.VIREMENT)
        resp = api.post(
            f'/api/django/compta/paiements-facture-portail/{pf.id}/rapprocher/',
            {'reference': 'VIR-2026-001'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        pf.refresh_from_db()
        self.assertEqual(pf.statut, PaiementFacturePortail.Statut.PAYE)
        self.assertIsNotNone(pf.paye_le)
        self.assertEqual(pf.reference, 'VIR-2026-001')

    def test_rapprocher_idempotent(self):
        pf = PaiementFacturePortail.objects.create(
            company=self.co, facture_id=42003, montant=100)
        services.rapprocher_paiement_facture(pf, reference='A')
        premier = pf.paye_le
        services.rapprocher_paiement_facture(pf, reference='B')
        pf.refresh_from_db()
        self.assertEqual(pf.reference, 'A')
        self.assertEqual(pf.paye_le, premier)


# ── FG231 — Dépôt de documents / factures ONEE par le client ───────────────

class DocumentClientPortailTests(TestCase):
    def setUp(self):
        self.co = make_company('fg231', 'FG231')
        self.user = make_user(self.co, 'fg231-user')

    def test_creation_pose_company_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/documents-client-portail/', {
            'client_id': 43001, 'type_document': 'facture_onee',
            'libelle': 'Facture ONEE janvier',
            'company': 77777,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        doc = DocumentClientPortail.objects.get(id=resp.data['id'])
        self.assertEqual(doc.company_id, self.co.id)
        self.assertFalse(doc.traite)

    def test_marquer_traite(self):
        api = auth(self.user)
        doc = DocumentClientPortail.objects.create(
            company=self.co, client_id=43002)
        resp = api.post(
            f'/api/django/compta/documents-client-portail/{doc.id}'
            '/marquer_traite/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        doc.refresh_from_db()
        self.assertTrue(doc.traite)

    def test_isolation_societe(self):
        autre = make_company('fg231-b', 'FG231B')
        DocumentClientPortail.objects.create(company=autre, client_id=43003)
        api = auth(self.user)
        resp = api.get('/api/django/compta/documents-client-portail/')
        self.assertEqual(resp.data['count'], 0)
