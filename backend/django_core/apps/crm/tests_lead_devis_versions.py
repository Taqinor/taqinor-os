"""
QJR535 (Groupe QJR5) — la ligne devis de la fiche lead porte sa version et le
devis qui la remplace : le cockpit signale « Remplacé par … » au lieu de
laisser une V1 obsolète vivante et renvoyable.

Contrat partagé : ``apps/crm/contract_samples/lead_devis_ligne.json`` (QJR500,
clés ``is_active`` / ``version`` / ``superseded_by`` — ``is_active`` est servi
par QJR516). Aucun import de ``ventes.models`` côté crm : ``version`` et
``superseded_by`` sont des attributs de l'instance déjà chargée.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.crm.tests_lead_devis_versions"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class TestLeadDevisVersions(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR535 Co', slug='qjr535-co')
        self.user = User.objects.create_user(
            username='qjr535_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR535',
            email='qjr535@example.com', telephone='+212600000535')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead', prenom='QJR535',
            email='qjr535-lead@example.com', telephone='0612345535')

    def _devis(self, reference, **extra):
        return Devis.objects.create(
            company=self.company, reference=reference, lead=self.lead,
            client=self.client_obj, statut='envoye', taux_tva=20,
            remise_globale=0, created_by=self.user, **extra)

    def _lignes(self):
        r = self.api.get(f'/api/django/crm/leads/{self.lead.id}/')
        self.assertEqual(r.status_code, 200, r.content)
        return {row['id']: row for row in r.json()['devis']}

    def test_v1_remplacee_expose_is_active_false_version_et_superseded_by(self):
        v2 = self._devis('DEV-QJR535-2', version=2)
        v1 = self._devis('DEV-QJR535-1', version=1, is_active=False,
                         superseded_by=v2)
        lignes = self._lignes()
        self.assertFalse(lignes[v1.id]['is_active'])
        self.assertEqual(lignes[v1.id]['version'], 1)
        self.assertEqual(lignes[v1.id]['superseded_by'], v2.id)

    def test_version_courante_superseded_by_null(self):
        v2 = self._devis('DEV-QJR535-B2', version=2)
        self._devis('DEV-QJR535-B1', version=1, is_active=False,
                    superseded_by=v2)
        ligne = self._lignes()[v2.id]
        self.assertTrue(ligne['is_active'])
        self.assertEqual(ligne['version'], 2)
        self.assertIsNone(ligne['superseded_by'])
