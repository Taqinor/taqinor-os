"""Tests AUD140 — la preuve d'acceptation et la ligne de paiement portail
ne sont plus créables, modifiables ni supprimables depuis l'ERP.

Défaut d'origine : ``AcceptationDevisPortailViewSet`` et
``PaiementFacturePortailViewSet`` héritaient de ``_ComptaBaseViewSet``
(``TenantMixin`` + ``ModelViewSet``, ``permission_classes=[IsResponsableOrAdmin]``)
et n'overridaient ni ``create``, ni ``update``, ni ``destroy`` : POST/PATCH/
DELETE étaient exposés à tout Responsable. Or ``AcceptationDevisPortail`` ne
porte ni ``created_by``, ni chatter, ni soft-delete, alors que sa propre
docstring justifie le ``PROTECT`` sur ``devis`` par « cette ligne EST la preuve
d'acceptation électronique (signataire, IP, horodatage — loi 53-05) » : la
preuve était protégée contre la suppression du DEVIS, pas contre la sienne.
L'action ``signer`` posait de surcroît ``nom_signataire`` depuis le corps et
``signature_ip`` depuis le ``REMOTE_ADDR`` de l'utilisateur ERP — une signature
client fabriquée depuis l'ERP.

Ces tests étaient ROUGES avant le correctif (201/200/204).

Run :
    python manage.py test apps.portail.tests.test_aud140_preuve_lecture_seule -v2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.portail.models import AcceptationDevisPortail, PaiementFacturePortail
from authentication.models import Company, CustomUser

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_responsable(company, username):
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role_legacy='responsable')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PreuveAcceptationLectureSeuleTests(TestCase):
    RACINE = '/api/django/portail/acceptations-devis-portail/'

    def setUp(self):
        self.co = make_company('aud140-co', 'AUD140 Société')
        self.user = make_responsable(self.co, 'aud140-responsable')
        self.api = auth(self.user)
        self.preuve = AcceptationDevisPortail.objects.create(
            company=self.co, devis_id=140001, nom_signataire='Client Alpha',
            signature_ip='10.0.0.1', accepte=True)

    def test_post_refuse(self):
        """ROUGE avant AUD140 : 201."""
        res = self.api.post(
            self.RACINE,
            {'devis_id': 140002, 'nom_signataire': 'Faux signataire'},
            format='json')
        self.assertEqual(res.status_code, 405, res.content)
        self.assertFalse(
            AcceptationDevisPortail.objects.filter(devis_id=140002).exists())

    def test_patch_du_nom_signataire_refuse(self):
        """ROUGE avant AUD140 : 200, la preuve réécrite sans trace."""
        res = self.api.patch(
            f'{self.RACINE}{self.preuve.id}/',
            {'nom_signataire': 'Quelqu’un d’autre'}, format='json')
        self.assertEqual(res.status_code, 405, res.content)
        self.preuve.refresh_from_db()
        self.assertEqual(self.preuve.nom_signataire, 'Client Alpha')

    def test_put_refuse(self):
        res = self.api.put(
            f'{self.RACINE}{self.preuve.id}/',
            {'devis_id': 140001, 'nom_signataire': 'Écrasé'}, format='json')
        self.assertEqual(res.status_code, 405, res.content)

    def test_delete_refuse(self):
        """ROUGE avant AUD140 : 204, la preuve légale effacée."""
        res = self.api.delete(f'{self.RACINE}{self.preuve.id}/')
        self.assertEqual(res.status_code, 405, res.content)
        self.assertTrue(
            AcceptationDevisPortail.objects.filter(id=self.preuve.id).exists())

    def test_laction_signer_de_lerp_nexiste_plus(self):
        res = self.api.post(f'{self.RACINE}{self.preuve.id}/signer/',
                            {'nom_signataire': 'Fabriqué'}, format='json')
        self.assertIn(res.status_code, (404, 405), res.content)

    def test_la_lecture_reste_ouverte(self):
        res = self.api.get(self.RACINE)
        self.assertEqual(res.status_code, 200, res.content)


class PaiementPortailLectureSeuleTests(TestCase):
    RACINE = '/api/django/portail/paiements-facture-portail/'

    def setUp(self):
        self.co = make_company('aud140-co-b', 'AUD140 Société B')
        self.user = make_responsable(self.co, 'aud140-responsable-b')
        self.api = auth(self.user)
        self.paiement = PaiementFacturePortail.objects.create(
            company=self.co, facture_id=140010, montant=Decimal('9500.00'),
            methode=PaiementFacturePortail.Methode.VIREMENT)

    def test_post_refuse(self):
        """ROUGE avant AUD140 : 201."""
        res = self.api.post(
            self.RACINE,
            {'facture_id': 140011, 'montant': '1.00', 'methode': 'virement'},
            format='json')
        self.assertEqual(res.status_code, 405, res.content)
        self.assertFalse(
            PaiementFacturePortail.objects.filter(facture_id=140011).exists())

    def test_patch_du_montant_refuse(self):
        res = self.api.patch(f'{self.RACINE}{self.paiement.id}/',
                             {'montant': '1.00'}, format='json')
        self.assertEqual(res.status_code, 405, res.content)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('9500.00'))

    def test_delete_refuse(self):
        res = self.api.delete(f'{self.RACINE}{self.paiement.id}/')
        self.assertEqual(res.status_code, 405, res.content)
        self.assertTrue(
            PaiementFacturePortail.objects.filter(
                id=self.paiement.id).exists())

    def test_rapprocher_reste_disponible(self):
        """Le SEUL workflow serveur de cette ressource ne doit pas tomber."""
        res = self.api.post(f'{self.RACINE}{self.paiement.id}/rapprocher/',
                            {'reference': 'VIR-AUD140-1'}, format='json')
        self.assertEqual(res.status_code, 200, res.content)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut,
                         PaiementFacturePortail.Statut.PAYE)

    def test_la_lecture_reste_ouverte(self):
        res = self.api.get(self.RACINE)
        self.assertEqual(res.status_code, 200, res.content)
