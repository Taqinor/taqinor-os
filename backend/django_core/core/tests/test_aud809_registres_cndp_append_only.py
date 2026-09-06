"""AUD809 — les trois registres CNDP / loi 09-08 étaient librement modifiables
ET supprimables par API, sans immuabilité ni trace d'audit.

Constat d'origine : ``ConsentRecordViewSet``, ``DataSubjectRequestViewSet`` et
``RegistreTraitementViewSet`` étaient des ``ModelViewSet`` COMPLETS gardés
seulement par ``IsAdminOrResponsableTier``, sans ``perform_destroy`` ni
``http_method_names`` ; ``ConsentRecordSerializer`` laissait ``granted`` /
``occurred_at`` / ``version_texte`` / ``ip_confirmation`` — les preuves du
double opt-in — en écriture ; et AUCUN des trois modèles n'était dans
``apps.audit.signals.TRACKED_MODELS``. Un Responsable pouvait donc fabriquer
une preuve de consentement, ou supprimer une ``DataSubjectRequest`` pour
masquer un dépassement de délai légal, sans laisser une ligne.

Après correctif : les trois sont append-only (GET/POST seulement), les champs
de preuve d'un ``ConsentRecord`` DÉJÀ CRÉÉ sont en lecture seule (un retrait de
consentement = une NOUVELLE ligne ``granted=False``), et les trois modèles sont
suivis par le Journal d'activité.

La moitié « TRACKED_MODELS » est vérifiée dans
``apps/audit/tests_aud8_journal.py`` : ``core`` n'importe jamais ``apps.audit``,
pas même depuis ses tests (contrat import-linter
``core-foundation-is-a-base-layer``).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core.models import ConsentRecord, DataSubjectRequest, RegistreTraitement
from core.serializers import ConsentRecordSerializer
from core.views import (
    ConsentRecordViewSet,
    DataSubjectRequestViewSet,
    RegistreTraitementViewSet,
)

User = get_user_model()


class Aud809RegistresCndpAppendOnlyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='AUD809 SARL')
        # Palier admin : il FRANCHIT la garde de la classe — le refus observé
        # est donc bien le 405 append-only, jamais un 403 de permission.
        cls.admin = User.objects.create_user(
            username='aud809_admin', password='x', company=cls.company,
            role_legacy='admin')
        cls.factory = APIRequestFactory()

    def setUp(self):
        self.consent = ConsentRecord.objects.create(
            company=self.company, subject_identifier='client@example.ma',
            purpose='marketing', granted=False,
            version_texte='v1-2026-07', ip_confirmation='10.0.0.1')
        self.dsr = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='client@example.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        self.registre = RegistreTraitement.objects.create(
            company=self.company, code='aud809', finalite='Prospection')

    def _appeler(self, viewset, methode, action, pk, corps=None):
        chemin = f'/registre/{pk}/'
        requete = getattr(self.factory, methode)(
            chemin, corps or {}, format='json')
        force_authenticate(requete, user=self.admin)
        return viewset.as_view({methode: action})(requete, pk=pk)

    # ── DELETE refusé sur les trois registres ─────────────────────────────
    def test_delete_consentement_refuse(self):
        resp = self._appeler(
            ConsentRecordViewSet, 'delete', 'destroy', self.consent.pk)
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(
            ConsentRecord.objects.filter(pk=self.consent.pk).exists())

    def test_delete_demande_personne_concernee_refuse(self):
        resp = self._appeler(
            DataSubjectRequestViewSet, 'delete', 'destroy', self.dsr.pk)
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(
            DataSubjectRequest.objects.filter(pk=self.dsr.pk).exists())

    def test_delete_registre_traitements_refuse(self):
        resp = self._appeler(
            RegistreTraitementViewSet, 'delete', 'destroy', self.registre.pk)
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(
            RegistreTraitement.objects.filter(pk=self.registre.pk).exists())

    # ── PATCH d'une preuve refusé ─────────────────────────────────────────
    def test_patch_ip_confirmation_refuse(self):
        resp = self._appeler(
            ConsentRecordViewSet, 'patch', 'partial_update', self.consent.pk,
            {'ip_confirmation': '203.0.113.9', 'granted': True})
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.consent.refresh_from_db()
        self.assertEqual(self.consent.ip_confirmation, '10.0.0.1')
        self.assertFalse(self.consent.granted)

    def test_champs_de_preuve_lecture_seule_sur_une_ligne_existante(self):
        """Défense en profondeur : même si un chemin d'écriture réapparaissait,
        les preuves d'une ligne DÉJÀ CRÉÉE ne sont plus modifiables."""
        ser = ConsentRecordSerializer(instance=self.consent)
        for nom in ('granted', 'occurred_at', 'version_texte',
                    'ip_confirmation'):
            self.assertTrue(
                ser.fields[nom].read_only,
                f'{nom} doit être en lecture seule sur une ligne existante')

    def test_champs_de_preuve_ecrivables_a_la_creation(self):
        ser = ConsentRecordSerializer()
        for nom in ('granted', 'occurred_at', 'version_texte',
                    'ip_confirmation'):
            self.assertFalse(
                ser.fields[nom].read_only,
                f'{nom} doit rester écrivable à la création')

    # ── Le chemin légitime reste ouvert ───────────────────────────────────
    def test_retrait_de_consentement_par_une_nouvelle_ligne(self):
        requete = self.factory.post('/consent-records/', {
            'subject_identifier': 'client@example.ma',
            'purpose': 'marketing', 'granted': False,
        }, format='json')
        force_authenticate(requete, user=self.admin)
        resp = ConsentRecordViewSet.as_view({'post': 'create'})(requete)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            ConsentRecord.objects.filter(
                company=self.company,
                subject_identifier='client@example.ma').count(), 2)

    def test_lecture_et_action_traiter_inchangees(self):
        requete = self.factory.get('/registre-traitements/')
        force_authenticate(requete, user=self.admin)
        resp = RegistreTraitementViewSet.as_view({'get': 'list'})(requete)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        requete = self.factory.post(f'/dsr-requests/{self.dsr.pk}/traiter/')
        force_authenticate(requete, user=self.admin)
        resp = DataSubjectRequestViewSet.as_view(
            {'post': 'traiter'})(requete, pk=self.dsr.pk)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
