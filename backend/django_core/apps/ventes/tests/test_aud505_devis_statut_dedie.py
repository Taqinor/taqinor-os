"""AUD505 — ``Devis.statut`` n'est plus écrivable en PATCH vers ACCEPTE/
REFUSE/EXPIRE : ces trois valeurs ont chacune une porte dédiée et gardée
(``/accepter/`` → ``accept_devis`` : contrôle crédit XFAC28, avertissement
vente ZSAL9, événement ``devis_accepted`` — seul déclencheur de création de
Chantier ; ``/refuser/`` ; EXPIRE posé uniquement par le système
``domain/recouvrement.py``).

LE TROU FERMÉ. ``DevisWriteSerializer`` ne verrouillait pas ``statut`` :
un PATCH brut {statut: 'accepte'} sur un devis ENVOYE réussissait (200),
sans jamais appeler ``accept_devis`` — pourtant ``perform_update`` fait
INCONDITIONNELLEMENT avancer le funnel CRM du lead lié via
``avancer_stage_pour_devis`` sur la seule valeur du champ ``statut``
(voir ``apps/crm/tests_devis_auto.py::TestAvancerStagePourDevis`` pour la
preuve côté lead). Ce module prouve la garde côté devis seul, sans lead.

BROUILLON/ENVOYE restent écrivables (matrice d'approbation NTCPQ7/8, funnel
QUOTE_SENT) — la garde ne bloque QUE ACCEPTE/REFUSE/EXPIRE.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_aud505_devis_statut_dedie"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _company():
    company, _ = Company.objects.get_or_create(
        slug='aud505-co', defaults={'nom': 'AUD505 Co'})
    return company


def _user(company):
    return User.objects.create_user(
        username='aud505_resp', password='x', role_legacy='responsable',
        company=company)


def _client_obj(company):
    return Client.objects.create(
        company=company, nom='AUD505', prenom='Client',
        email='aud505@example.invalid', telephone='+212600000505')


class PatchStatutDedie(TestCase):
    def setUp(self):
        self.company = _company()
        self.user = _user(self.company)
        self.client_obj = _client_obj(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, num, statut):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-A505{num}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def _patch(self, devis_id, statut):
        return self.api.patch(
            f'/api/django/ventes/devis/{devis_id}/', {'statut': statut},
            format='json')

    def test_patch_vers_accepte_refuse(self):
        devis = self._devis(1, Devis.Statut.ENVOYE)
        resp = self._patch(devis.id, 'accepte')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('statut', resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_patch_vers_refuse_refuse(self):
        devis = self._devis(2, Devis.Statut.ENVOYE)
        resp = self._patch(devis.id, 'refuse')
        self.assertEqual(resp.status_code, 400, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_patch_vers_expire_refuse(self):
        devis = self._devis(3, Devis.Statut.ENVOYE)
        resp = self._patch(devis.id, 'expire')
        self.assertEqual(resp.status_code, 400, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_patch_vers_envoye_toujours_permis(self):
        """Non-régression — seules ACCEPTE/REFUSE/EXPIRE sont bloquées."""
        devis = self._devis(4, Devis.Statut.BROUILLON)
        resp = self._patch(devis.id, 'envoye')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_seul_accepter_fait_reussir_la_transition(self):
        """La porte dédiée reste ouverte : /accepter/ fonctionne toujours."""
        devis = self._devis(5, Devis.Statut.ENVOYE)
        resp = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Test'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
