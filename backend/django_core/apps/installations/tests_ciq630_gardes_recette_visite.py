"""CIQ630 — site pro : recette passée avant « Réceptionné » et visite
technique validée avant le montage, même sans gates amorcés.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.installations.models import Installation, InstallationActivity
from apps.installations.services import (
    AVERTISSEMENT_SANS_VISITE_CI, ESSAIS_RECETTE, RAISON_CI_SANS_RECETTE,
    RAISON_MT_SANS_VISITE, TransitionRefusee, changer_statut_chantier,
    ensure_commissioning_record, stages_configures,
)
from apps.visites.models import VisiteTerrain
from authentication.models import Company

User = get_user_model()


class GardesRecetteVisiteTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ630', slug='ciq630-co')
        self.directeur = User.objects.create_superuser(
            username='ciq630_dir', password='x', email='d@example.com',
            company=self.company)
        self.responsable = User.objects.create_user(
            username='ciq630_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='CIQ630',
            type_installation='industriel')
        self._n = 0

    def _chantier(self, statut, type_installation='industriel',
                  niveau=None):
        # Régime « non concerné » : on isole les gardes CIQ630 de la
        # convention 82-21 (CIQ621).
        self._n += 10
        return Installation.objects.create(
            company=self.company, reference=f'CHT-CIQ630-{self._n}',
            lead=self.lead, type_installation=type_installation,
            regime_8221='non_concerne', niveau_tension=niveau, statut=statut)

    def _recette_passee(self, chantier):
        record = ensure_commissioning_record(chantier)
        for champ in ESSAIS_RECETTE:
            setattr(record, champ, True)
        record.resultat = 'conforme'
        record.save()

    def test_societe_non_amorcee_ci_sans_recette_reception_refusee(self):
        self.assertFalse(stages_configures(self.company))
        chantier = self._chantier(Installation.Statut.INSTALLE)
        with self.assertRaises(TransitionRefusee) as ctx:
            changer_statut_chantier(chantier, Installation.Statut.RECEPTIONNE,
                                    self.responsable)
        self.assertIn(RAISON_CI_SANS_RECETTE, ctx.exception.raisons)
        self._recette_passee(chantier)
        changer_statut_chantier(chantier, Installation.Statut.RECEPTIONNE,
                                self.responsable)
        chantier.refresh_from_db()
        self.assertEqual(chantier.statut, Installation.Statut.RECEPTIONNE)

    def test_mt_sans_visite_validee_en_cours_refuse(self):
        chantier = self._chantier(Installation.Statut.PLANIFIE, niveau='mt')
        with self.assertRaises(TransitionRefusee) as ctx:
            changer_statut_chantier(chantier, Installation.Statut.EN_COURS,
                                    self.responsable)
        self.assertIn(RAISON_MT_SANS_VISITE, ctx.exception.raisons)
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='ci',
            statut=VisiteTerrain.Statut.VALIDEE,
            mesures={'comptage': {'niveau_tension_constate': 'mt'}})
        changer_statut_chantier(chantier, Installation.Statut.EN_COURS,
                                self.responsable)

    def test_mt_visite_non_validee_ne_compte_pas(self):
        chantier = self._chantier(Installation.Statut.PLANIFIE, niveau='mt')
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, gabarit='ci',
            mesures={})
        with self.assertRaises(TransitionRefusee):
            changer_statut_chantier(chantier, Installation.Statut.EN_COURS,
                                    self.responsable)

    def test_bt_sans_visite_autorise_avec_avertissement(self):
        chantier = self._chantier(Installation.Statut.PLANIFIE, niveau='bt')
        recu = changer_statut_chantier(
            chantier, Installation.Statut.EN_COURS, self.responsable)
        self.assertEqual(recu['effets']['avertissements'],
                         [AVERTISSEMENT_SANS_VISITE_CI])
        self.assertTrue(InstallationActivity.objects.filter(
            installation=chantier,
            body=AVERTISSEMENT_SANS_VISITE_CI).exists())

    def test_derogation_directeur_journalisee(self):
        chantier = self._chantier(Installation.Statut.PLANIFIE, niveau='mt')
        changer_statut_chantier(
            chantier, Installation.Statut.EN_COURS, self.directeur,
            motif_derogation_8221='Visite faite, saisie en retard')
        notes = list(InstallationActivity.objects.filter(
            installation=chantier).values_list('body', flat=True))
        self.assertTrue(any('dérogation Directeur' in n
                            and 'Visite faite' in n for n in notes), notes)

    def test_responsable_ne_peut_pas_deroger(self):
        chantier = self._chantier(Installation.Statut.PLANIFIE, niveau='mt')
        with self.assertRaises(TransitionRefusee):
            changer_statut_chantier(
                chantier, Installation.Statut.EN_COURS, self.responsable,
                motif_derogation_8221='Motif')

    def test_residentiel_identique(self):
        chantier = self._chantier(Installation.Statut.INSTALLE,
                                  type_installation='residentiel', niveau='mt')
        recu = changer_statut_chantier(
            chantier, Installation.Statut.RECEPTIONNE, self.responsable)
        self.assertEqual(recu['effets']['avertissements'], [])
        chantier.refresh_from_db()
        self.assertEqual(chantier.statut, Installation.Statut.RECEPTIONNE)
