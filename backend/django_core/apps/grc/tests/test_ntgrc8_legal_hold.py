"""NTGRC8 — mise sous séquestre TRANSVERSE (legal hold au-delà de la GED).

Garanties : un séquestre couvrant un client empêche son anonymisation DSR
(409 explicite) jusqu'à la levée ; un document déjà gelé côté GED apparaît
aussi dans `objets_sous_hold` ; la purge de rétention saute les objets gelés.
"""
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client, Lead
from apps.grc.models import LegalHold, PolitiqueRetentionObjet
from apps.grc.selectors import est_sous_hold, objets_sous_hold
from authentication.models import Company
from core import dsr
from core.models import DataSubjectRequest

EMAIL = 'gele@exemple.ma'


class PerimetreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC8 SA', slug='ntgrc8')
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Gelé', email=EMAIL)

    def _hold(self, **kw):
        params = {
            'nom': 'Contentieux 2026',
            'perimetre': [{'type_objet': 'crm_client',
                           'filtre': {'identifiant': EMAIL}}],
        }
        params.update(kw)
        return LegalHold.objects.create(company=self.company, **params)

    def test_le_perimetre_est_resolu_par_le_selector_du_crm(self):
        self._hold()
        couverture = objets_sous_hold(self.company)
        self.assertIn(self.client_obj.pk, couverture['crm_client'])
        self.assertTrue(
            est_sous_hold(self.company, 'crm_client', self.client_obj.pk))

    def test_filtre_par_ids_explicites(self):
        lead = Lead.objects.create(company=self.company, nom='L', email=EMAIL)
        self._hold(perimetre=[{'type_objet': 'crm_lead',
                               'filtre': {'ids': [lead.pk]}}])
        self.assertIn(lead.pk, objets_sous_hold(self.company)['crm_lead'])

    def test_un_hold_leve_ne_gele_plus(self):
        hold = self._hold()
        hold.statut = LegalHold.STATUT_LEVE
        hold.save()
        self.assertEqual(objets_sous_hold(self.company), {})

    def test_un_hold_echu_ne_gele_plus(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        self._hold(date_fin=hier)
        self.assertEqual(objets_sous_hold(self.company), {})

    def test_un_perimetre_inconnu_ne_gele_rien(self):
        self._hold(perimetre=[{'type_objet': 'inconnu',
                               'filtre': {'identifiant': EMAIL}}])
        self.assertEqual(objets_sous_hold(self.company), {})

    def test_un_hold_ne_franchit_pas_la_frontiere_societe(self):
        autre = Company.objects.create(nom='NTGRC8 B', slug='ntgrc8-b')
        self._hold()
        self.assertEqual(objets_sous_hold(autre), {})


class CompositionAvecGedTests(TestCase):
    """Un document déjà gelé côté GED apparaît aussi dans objets_sous_hold."""

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC8 G', slug='ntgrc8-g')

    def test_les_documents_ged_geles_sont_composes(self):
        from unittest.mock import MagicMock, patch

        faux_hold = MagicMock()
        faux_hold.document_id = 77
        qs = MagicMock()
        qs.filter.return_value = [faux_hold]
        with patch('apps.ged.selectors.legal_holds_for_company',
                   return_value=qs):
            couverture = objets_sous_hold(self.company)
        self.assertEqual(couverture.get('ged_document'), {77})


class GardeEffacementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC8 E', slug='ntgrc8-e')

    def setUp(self):
        super().setUp()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Gelé', email=EMAIL)
        self.hold = LegalHold.objects.create(
            company=self.company, nom='Litige',
            perimetre=[{'type_objet': 'crm_client',
                        'filtre': {'identifiant': EMAIL}}])

    def _demande(self):
        return DataSubjectRequest.objects.create(
            company=self.company, subject_identifier=EMAIL,
            kind=DataSubjectRequest.KIND_ERASURE)

    def test_effacement_refuse_tant_que_le_sequestre_est_actif(self):
        demande = self._demande()
        with self.assertRaises(dsr.EffacementBloque):
            dsr.traiter_demande(demande)
        # RIEN n'a été modifié : un effacement à moitié fait serait pire.
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.email, EMAIL)
        self.assertFalse(self.client_obj.is_anonymized)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DataSubjectRequest.STATUT_RECUE)

    def test_effacement_repasse_apres_la_levee(self):
        self.hold.statut = LegalHold.STATUT_LEVE
        self.hold.save()
        demande = self._demande()
        dsr.traiter_demande(demande)
        self.client_obj.refresh_from_db()
        self.assertTrue(self.client_obj.is_anonymized)

    def test_un_acces_nest_jamais_bloque_par_un_sequestre(self):
        """Le séquestre gèle la DESTRUCTION, pas le droit d'accès."""
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier=EMAIL,
            kind=DataSubjectRequest.KIND_ACCESS)
        dsr.traiter_demande(demande)
        self.assertEqual(demande.statut, DataSubjectRequest.STATUT_TRAITEE)

    def test_la_garde_est_enregistree_dans_core(self):
        self.assertIn('grc_legal_hold', dsr.list_erasure_guards())


class PurgeRetentionSauteLesGelesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC8 R', slug='ntgrc8-r')

    def test_un_lead_gele_nest_pas_purge(self):
        from apps.crm.retention import sweep_objets

        lead = Lead.objects.create(
            company=self.company, nom='Vieux', email='vieux8@exemple.ma')
        vieux = timezone.now() - timezone.timedelta(days=48 * 30)
        Lead.objects.filter(pk=lead.pk).update(date_creation=vieux)
        PolitiqueRetentionObjet.objects.create(
            company=self.company,
            type_objet=PolitiqueRetentionObjet.TYPE_CRM_LEAD,
            duree_conservation_mois=24,
            action_echeance=PolitiqueRetentionObjet.ACTION_ANONYMISER)
        LegalHold.objects.create(
            company=self.company, nom='Litige',
            perimetre=[{'type_objet': 'crm_lead',
                        'filtre': {'ids': [lead.pk]}}])

        maintenant = timezone.now()
        self.assertEqual(sweep_objets(maintenant, True), 0)
        lead.refresh_from_db()
        self.assertEqual(lead.email, 'vieux8@exemple.ma')
