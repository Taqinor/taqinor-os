"""NTGRC5 — journal de destruction APPEND-ONLY.

Garanties : chaque purge/anonymisation réelle crée une ligne IMMUABLE ; aucune
route d'update ni de delete n'est exposée ; la garde vit aussi au niveau du
modèle ; aucune donnée personnelle n'est stockée (seulement une empreinte).
"""
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Lead
from apps.grc.models import (
    JournalDestruction, JournalDestructionError, PolitiqueRetentionObjet,
)
from authentication.models import Company
from core import dsr
from core.models import DataSubjectRequest
from testkit.base import TenantAPITestCase


class ImmuabiliteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC5 SA', slug='ntgrc5')

    def _ligne(self):
        return JournalDestruction.objects.create(
            company=self.company, type_objet='crm_lead', objet_ref='42',
            action=JournalDestruction.ACTION_ANONYMISE, motif='Test')

    def test_une_ligne_ne_se_modifie_pas(self):
        ligne = self._ligne()
        ligne.motif = 'Réécrit'
        with self.assertRaises(JournalDestructionError):
            ligne.save()

    def test_une_ligne_ne_se_supprime_pas(self):
        ligne = self._ligne()
        with self.assertRaises(JournalDestructionError):
            ligne.delete()
        self.assertTrue(
            JournalDestruction.objects.filter(pk=ligne.pk).exists())


class EcrituresAutomatiquesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC5 B', slug='ntgrc5-b')

    def test_un_effacement_dsr_cree_une_ligne_immuable(self):
        Lead.objects.create(
            company=self.company, nom='Dupont', email='d@exemple.ma')
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='d@exemple.ma',
            kind=DataSubjectRequest.KIND_ERASURE)
        dsr.traiter_demande(demande)

        ligne = JournalDestruction.objects.get(
            company=self.company, type_objet='crm_lead')
        self.assertEqual(ligne.action, JournalDestruction.ACTION_ANONYMISE)
        self.assertEqual(ligne.demande_droit_ref, 'd@exemple.ma')
        self.assertEqual(len(ligne.empreinte_avant), 64)

    def test_le_journal_ne_contient_aucune_donnee_personnelle(self):
        Lead.objects.create(
            company=self.company, nom='Motdepasse', email='secret@exemple.ma',
            telephone='0600112233')
        demande = DataSubjectRequest.objects.create(
            company=self.company, subject_identifier='secret@exemple.ma',
            kind=DataSubjectRequest.KIND_ERASURE)
        dsr.traiter_demande(demande)

        ligne = JournalDestruction.objects.get(
            company=self.company, type_objet='crm_lead')
        rendu = ' '.join([
            ligne.type_objet, ligne.objet_ref, ligne.motif,
            ligne.empreinte_avant, ligne.politique_ref])
        self.assertNotIn('Motdepasse', rendu)
        self.assertNotIn('0600112233', rendu)

    def test_une_retention_qui_anonymise_journalise_aussi(self):
        from apps.crm.retention import sweep_objets

        lead = Lead.objects.create(
            company=self.company, nom='Vieux', email='vieux@exemple.ma')
        vieux = timezone.now() - timezone.timedelta(days=48 * 30)
        Lead.objects.filter(pk=lead.pk).update(date_creation=vieux)
        PolitiqueRetentionObjet.objects.create(
            company=self.company,
            type_objet=PolitiqueRetentionObjet.TYPE_CRM_LEAD,
            duree_conservation_mois=24,
            action_echeance=PolitiqueRetentionObjet.ACTION_ANONYMISER)

        avant = JournalDestruction.objects.count()
        sweep_objets(timezone.now(), True)
        self.assertEqual(JournalDestruction.objects.count(), avant + 1)

    def test_un_dry_run_ne_journalise_rien(self):
        from apps.crm.retention import sweep_objets

        lead = Lead.objects.create(
            company=self.company, nom='Vieux', email='v2@exemple.ma')
        vieux = timezone.now() - timezone.timedelta(days=48 * 30)
        Lead.objects.filter(pk=lead.pk).update(date_creation=vieux)
        PolitiqueRetentionObjet.objects.create(
            company=self.company,
            type_objet=PolitiqueRetentionObjet.TYPE_CRM_LEAD,
            duree_conservation_mois=24,
            action_echeance=PolitiqueRetentionObjet.ACTION_ANONYMISER)
        avant = JournalDestruction.objects.count()
        sweep_objets(timezone.now(), False)
        self.assertEqual(JournalDestruction.objects.count(), avant)


class EndpointJournalTests(TenantAPITestCase):
    BASE = '/api/django/grc/journal-destruction/'

    def setUp(self):
        super().setUp()
        self.ligne = JournalDestruction.objects.create(
            company=self.company, type_objet='crm_lead', objet_ref='7',
            action=JournalDestruction.ACTION_ANONYMISE, motif='Test')

    def _admin(self):
        return self.client_as(role='admin')

    def test_liste_scopee_societe(self):
        JournalDestruction.objects.create(
            company=self.other_company, type_objet='crm_lead',
            objet_ref='99', action=JournalDestruction.ACTION_ANONYMISE)
        r = self._admin().get(self.BASE)
        self.assertEqual(r.status_code, 200, r.content)
        lignes = r.data.get('results', r.data)
        self.assertEqual([le['objet_ref'] for le in lignes], ['7'])

    def test_aucune_route_dupdate_ni_de_delete(self):
        admin = self._admin()
        url = f'{self.BASE}{self.ligne.pk}/'
        self.assertEqual(admin.patch(url, {'motif': 'x'},
                                     format='json').status_code, 405)
        self.assertEqual(admin.put(url, {'motif': 'x'},
                                   format='json').status_code, 405)
        self.assertEqual(admin.delete(url).status_code, 405)

    def test_filtre_par_type_objet(self):
        JournalDestruction.objects.create(
            company=self.company, type_objet='stock_fournisseur',
            objet_ref='8', action=JournalDestruction.ACTION_ANONYMISE)
        r = self._admin().get(self.BASE, {'type_objet': 'stock_fournisseur'})
        lignes = r.data.get('results', r.data)
        self.assertEqual([le['objet_ref'] for le in lignes], ['8'])

    def test_creation_impose_societe_et_acteur(self):
        r = self._admin().post(
            self.BASE,
            {'type_objet': 'crm_client', 'objet_ref': '11',
             'action': 'anonymise', 'motif': 'Manuel'},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        ligne = JournalDestruction.objects.get(objet_ref='11')
        self.assertEqual(ligne.company, self.company)
        self.assertTrue(ligne.executee_par)
