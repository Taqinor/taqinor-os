"""T17 — garde d'approbation de remise avant envoi du devis.

QJR539 — ``_guard_discount_approval`` (vue) est supprimée : la garde est la
fonction de domaine ``domain/tarification.exiger_approbation_remise``.
QJR541 — ``statut`` n'est plus écrivable au PATCH : l'envoi passe ici par sa
VRAIE porte (``share-link`` avec ``envoi``) ; la clé {'statut'} historique
reste celle de la correction d'un envoyé (PATCH ``remise_globale``). Les autres
envois sont couverts par ``test_t17_garde_envoi.py``."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class TestDiscountGuard(TestCase):
    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug='dg-co', defaults={'nom': 'DG Co'})[0]
        self.resp = User.objects.create_user(
            username='dg_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.admin = User.objects.create_user(
            username='dg_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(company=self.company, nom='C')

    def _api(self, user):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _envoyer(self, user, d):
        return self._api(user).post(
            f'/api/django/ventes/devis/{d.id}/share-link/', {'envoi': True},
            format='json')

    def _devis(self, remise):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-DG-{remise}', client=self.client_obj,
            statut='brouillon', taux_tva=Decimal('20'), remise_globale=Decimal(remise))

    def test_threshold_off_by_default_allows_send(self):
        # Seuil non configuré → comportement inchangé : envoi autorisé.
        d = self._devis('30')
        r = self._envoyer(self.resp, d)
        self.assertEqual(r.status_code, 200, r.data)

    def test_over_threshold_blocks_responsable(self):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        d = self._devis('25')
        r = self._envoyer(self.resp, d)
        self.assertEqual(r.status_code, 400)
        d.refresh_from_db()
        self.assertEqual(d.statut, 'brouillon')  # non envoyé

    def test_admin_send_auto_approves(self):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        d = self._devis('25')
        r = self._envoyer(self.admin, d)
        self.assertEqual(r.status_code, 200, r.data)
        d.refresh_from_db()
        self.assertTrue(d.remise_approuvee)

    def test_over_threshold_error_key_statut_kept(self):
        # QJR539 — la clé d'erreur historique {'statut'} est CONSERVÉE sur la
        # correction d'un ENVOYÉ (QJR541 : le PATCH n'envoie plus).
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        d = self._devis('5')
        Devis.objects.filter(pk=d.pk).update(statut='envoye')
        r = self._api(self.resp).patch(f'/api/django/ventes/devis/{d.id}/',
                                       {'remise_globale': '26'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('statut', r.data)

    def test_approval_then_responsable_can_send(self):
        CompanyProfile.objects.update_or_create(
            company=self.company, defaults={'discount_approval_threshold': Decimal('10')})
        d = self._devis('25')
        self._api(self.admin).post(
            f'/api/django/ventes/devis/{d.id}/approuver-remise/')
        r = self._envoyer(self.resp, d)
        self.assertEqual(r.status_code, 200, r.data)
