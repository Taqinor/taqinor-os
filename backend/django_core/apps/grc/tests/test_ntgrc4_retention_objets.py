"""NTGRC4 — rétention par type d'objet, branchée sur `core.retention`.

Garanties : les 4 apps enregistrent leur politique ; un balayage DRY-RUN liste
les objets échus sans rien modifier ; `--commit` (apply_) exécute l'action et
`core` journalise chaque exécution dans `RetentionRun`.
"""
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client, Lead
from apps.grc.models import PolitiqueRetentionObjet
from authentication.models import Company
from core import retention
from core.models import RetentionRun


class RegistreDesPolitiquesTests(TestCase):
    def test_les_quatre_apps_enregistrent_leur_politique(self):
        noms = retention.list_retention_policies()
        for attendu in ('crm_objets_echus', 'ventes_factures_echues',
                        'sav_tickets_echus', 'audit_logs_echus'):
            self.assertIn(attendu, noms, f'politique manquante : {attendu}')


class BalayageCrmTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC4 SA', slug='ntgrc4')
        cls.autre = Company.objects.create(nom='NTGRC4 B', slug='ntgrc4-b')

    def _vieux_lead(self, company=None, mois=48):
        lead = Lead.objects.create(
            company=company or self.company, nom='Ancien',
            email='ancien@exemple.ma', telephone='0611111111')
        vieux = timezone.now() - timezone.timedelta(days=mois * 30)
        Lead.objects.filter(pk=lead.pk).update(date_creation=vieux)
        lead.refresh_from_db()
        return lead

    def _politique(self, company=None, **kw):
        params = {
            'type_objet': PolitiqueRetentionObjet.TYPE_CRM_LEAD,
            'duree_conservation_mois': 24,
            'action_echeance': PolitiqueRetentionObjet.ACTION_ANONYMISER,
            'actif': True,
        }
        params.update(kw)
        return PolitiqueRetentionObjet.objects.create(
            company=company or self.company, **params)

    def test_dry_run_liste_sans_rien_modifier(self):
        from apps.crm.retention import sweep_objets

        lead = self._vieux_lead()
        self._politique()
        compte = sweep_objets(timezone.now(), False)
        self.assertEqual(compte, 1)
        lead.refresh_from_db()
        self.assertEqual(lead.email, 'ancien@exemple.ma')

    def test_commit_anonymise_reellement(self):
        from apps.crm.retention import sweep_objets

        lead = self._vieux_lead()
        self._politique()
        compte = sweep_objets(timezone.now(), True)
        self.assertEqual(compte, 1)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'Anonymisé')
        self.assertIsNone(lead.email)

    def test_objet_dans_la_fenetre_nest_pas_echu(self):
        from apps.crm.retention import sweep_objets

        Lead.objects.create(
            company=self.company, nom='Recent', email='recent@exemple.ma')
        self._politique()
        self.assertEqual(sweep_objets(timezone.now(), False), 0)

    def test_politique_inactive_ne_balaie_rien(self):
        from apps.crm.retention import sweep_objets

        self._vieux_lead()
        self._politique(actif=False)
        self.assertEqual(sweep_objets(timezone.now(), False), 0)

    def test_action_signaler_ne_modifie_rien_meme_en_commit(self):
        from apps.crm.retention import sweep_objets

        lead = self._vieux_lead()
        self._politique(
            action_echeance=PolitiqueRetentionObjet.ACTION_SIGNALER)
        self.assertEqual(sweep_objets(timezone.now(), True), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.email, 'ancien@exemple.ma')

    def test_chaque_politique_reste_bornee_a_sa_societe(self):
        from apps.crm.retention import sweep_objets

        etranger = self._vieux_lead(company=self.autre)
        self._politique()  # politique de self.company UNIQUEMENT
        sweep_objets(timezone.now(), True)
        etranger.refresh_from_db()
        self.assertEqual(etranger.email, 'ancien@exemple.ma')

    def test_client_anonymise_nest_pas_rebalaye(self):
        from apps.crm.retention import sweep_objets

        client = Client.objects.create(
            company=self.company, nom='Vieux', email='vieux@exemple.ma')
        vieux = timezone.now() - timezone.timedelta(days=48 * 30)
        Client.objects.filter(pk=client.pk).update(date_creation=vieux)
        self._politique(
            type_objet=PolitiqueRetentionObjet.TYPE_CRM_CLIENT)
        self.assertEqual(sweep_objets(timezone.now(), True), 1)
        # Second passage : le client porte désormais `is_anonymized`.
        self.assertEqual(sweep_objets(timezone.now(), True), 0)


class JournalisationRetentionRunTests(TestCase):
    def test_run_all_policies_journalise_chaque_politique(self):
        avant = RetentionRun.objects.count()
        resultats = retention.run_all_policies(apply_=False)
        self.assertGreaterEqual(len(resultats), 4)
        self.assertEqual(
            RetentionRun.objects.count(), avant + len(resultats))
        noms = {r['name'] for r in resultats}
        self.assertIn('crm_objets_echus', noms)
        # DRY-RUN : chaque exécution est marquée comme telle.
        self.assertTrue(
            RetentionRun.objects.filter(
                policy_name='crm_objets_echus', dry_run=True).exists())


class UniciteParSocieteEtTypeTests(TestCase):
    def test_une_seule_politique_par_societe_et_type(self):
        from django.db import IntegrityError, transaction

        company = Company.objects.create(nom='NTGRC4 U', slug='ntgrc4-u')
        PolitiqueRetentionObjet.objects.create(
            company=company,
            type_objet=PolitiqueRetentionObjet.TYPE_CRM_LEAD)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PolitiqueRetentionObjet.objects.create(
                    company=company,
                    type_objet=PolitiqueRetentionObjet.TYPE_CRM_LEAD)
