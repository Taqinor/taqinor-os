# -*- coding: utf-8 -*-
"""QJR639 (D-QJR5-2) — un devis ACCEPTÉ ne se supprime plus définitivement.

Constat : un DELETE admin effaçait en CASCADE la signature électronique
(DevisSignature : nom, IP, consentement), le lien client (ShareLink), les
lignes et le chatter. Désormais : 409 « archivez-le », rien n'est effacé ; un
brouillon garde le comportement actuel (204).

Run :
    python manage.py test apps.ventes.tests.test_qjr5_suppression_devis_accepte -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Devis, DevisSignature, ShareLink
from authentication.models import Company

User = get_user_model()


class SuppressionDevisAccepte(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='QJR639', slug='qjr639')
        cls.admin = User.objects.create_user(
            username='qjr639_admin', password='x', role_legacy='admin',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='QJR639',
            email='qjr639@example.com')

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _devis(self, reference, statut):
        return Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20.00'), created_by=self.admin)

    def test_accepte_signe_409_et_rien_n_est_efface(self):
        devis = self._devis('DEV-QJR639-ACC', Devis.Statut.ACCEPTE)
        DevisSignature.objects.create(
            company=self.company, devis=devis, signataire_nom='M. Client',
            consentement_explicite=True, ip_address='10.0.0.1',
            signed_at=timezone.now())
        lien = ShareLink.for_devis(devis)
        r = self.api.delete(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('archivez-le', r.data['detail'])
        self.assertTrue(Devis.objects.filter(pk=devis.pk).exists())
        self.assertTrue(DevisSignature.objects.filter(devis=devis).exists())
        self.assertTrue(ShareLink.objects.filter(pk=lien.pk).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)

    def test_brouillon_supprime_comme_avant(self):
        devis = self._devis('DEV-QJR639-BRO', Devis.Statut.BROUILLON)
        r = self.api.delete(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(Devis.objects.filter(pk=devis.pk).exists())

    # QJR661 (décision fondateur 01/10) — archivage SEUL : seul un brouillon
    # se supprime ; envoyé / refusé / expiré → 409 « archivez-le », le devis
    # et son lien client (ShareLink) restent intacts.
    def _assert_409_intact(self, statut, reference):
        devis = self._devis(reference, statut)
        lien = ShareLink.for_devis(devis)
        r = self.api.delete(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('archivez-le', r.data['detail'])
        self.assertTrue(Devis.objects.filter(pk=devis.pk).exists())
        self.assertTrue(ShareLink.objects.filter(pk=lien.pk).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.statut, statut)

    def test_qjr661_envoye_409(self):
        self._assert_409_intact(Devis.Statut.ENVOYE, 'DEV-QJR661-ENV')

    def test_qjr661_refuse_409(self):
        self._assert_409_intact(Devis.Statut.REFUSE, 'DEV-QJR661-REF')

    def test_qjr661_expire_409(self):
        self._assert_409_intact(Devis.Statut.EXPIRE, 'DEV-QJR661-EXP')
