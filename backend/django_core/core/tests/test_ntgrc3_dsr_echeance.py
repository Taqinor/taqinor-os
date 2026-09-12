"""NTGRC3 — échéance légale 30 jours + garde de transition sur les DSR.

``core`` reste FONDATION : ce module n'importe AUCUNE app métier.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company
from core import dsr
from core.models import DataSubjectRequest
from core.views import DataSubjectRequestViewSet

User = get_user_model()


class EcheanceLegaleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC3 SA', slug='ntgrc3')

    def test_echeance_posee_a_la_creation(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        self.assertIsNotNone(demande.date_echeance)
        ecart = (demande.date_echeance - demande.created_at).total_seconds()
        self.assertAlmostEqual(ecart, 30 * 24 * 3600, delta=5)

    def test_echeance_jamais_recalculee(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        posee = demande.date_echeance
        demande.subject_identifier = 'autre@b.ma'
        demande.save()
        demande.refresh_from_db()
        self.assertEqual(demande.date_echeance, posee)

    def test_demande_en_retard_remonte_dans_le_selector(self):
        passe = timezone.now() - timezone.timedelta(days=1)
        en_retard = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='retard@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS, date_echeance=passe)
        DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a_temps@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        resultats = list(dsr.demandes_en_retard(self.company))
        self.assertEqual([d.pk for d in resultats], [en_retard.pk])

    def test_demande_close_nest_plus_en_retard(self):
        passe = timezone.now() - timezone.timedelta(days=1)
        DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='close@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS, date_echeance=passe,
            statut=DataSubjectRequest.STATUT_TRAITEE)
        self.assertEqual(list(dsr.demandes_en_retard(self.company)), [])

    def test_selector_borne_a_la_societe(self):
        autre = Company.objects.create(nom='NTGRC3 B', slug='ntgrc3-b')
        passe = timezone.now() - timezone.timedelta(days=1)
        DataSubjectRequest.objects.create(
            company=autre, subject_identifier='x@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS, date_echeance=passe)
        self.assertEqual(list(dsr.demandes_en_retard(self.company)), [])


class MachineAEtatsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC3 M', slug='ntgrc3-m')

    def _demande(self, **kw):
        return DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS, **kw)

    def test_recue_passe_en_verification(self):
        demande = self._demande()
        dsr.prendre_en_charge(demande)
        demande.refresh_from_db()
        self.assertEqual(demande.statut,
                         DataSubjectRequest.STATUT_EN_VERIFICATION)

    def test_prise_en_charge_deux_fois_est_interdite(self):
        demande = self._demande()
        dsr.prendre_en_charge(demande)
        with self.assertRaises(dsr.TransitionInterdite):
            dsr.prendre_en_charge(demande)

    def test_demande_traitee_ne_se_retraite_pas(self):
        demande = self._demande(statut=DataSubjectRequest.STATUT_TRAITEE)
        with self.assertRaises(dsr.TransitionInterdite):
            dsr.traiter_demande(demande)

    def test_refus_est_terminal(self):
        demande = self._demande()
        dsr.refuser_demande(demande, motif='Identité non prouvée.')
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DataSubjectRequest.STATUT_REFUSEE)
        with self.assertRaises(dsr.TransitionInterdite):
            dsr.prendre_en_charge(demande)

    def test_message_derreur_nomme_les_deux_statuts(self):
        demande = self._demande(statut=DataSubjectRequest.STATUT_TRAITEE)
        with self.assertRaises(dsr.TransitionInterdite) as ctx:
            dsr.prendre_en_charge(demande)
        message = str(ctx.exception)
        self.assertIn('Traitée', message)
        self.assertIn("En vérification d'identité", message)


class EndpointTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC3 E', slug='ntgrc3-e')
        cls.admin = User.objects.create_user(
            username='ntgrc3_admin', password='x', role_legacy='admin',
            company=cls.company)

    def _post(self, demande, action_name):
        factory = APIRequestFactory()
        request = factory.post(f'/dsr-requests/{demande.pk}/{action_name}/')
        force_authenticate(request, user=self.admin)
        view = DataSubjectRequestViewSet.as_view(
            {'post': action_name.replace('-', '_')})
        return view(request, pk=demande.pk)

    def test_prendre_en_charge_puis_transition_illegale_renvoie_400(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        r = self._post(demande, 'prendre-en-charge')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'],
                         DataSubjectRequest.STATUT_EN_VERIFICATION)

        r2 = self._post(demande, 'prendre-en-charge')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn('statut', r2.data)

    def test_lechance_est_exposee_en_lecture_seule(self):
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='a@b.ma',
            kind=DataSubjectRequest.KIND_ACCESS)
        r = self._post(demande, 'prendre-en-charge')
        self.assertIn('date_echeance', r.data)
        from core.serializers import DataSubjectRequestSerializer
        self.assertTrue(
            DataSubjectRequestSerializer().fields['date_echeance'].read_only)
