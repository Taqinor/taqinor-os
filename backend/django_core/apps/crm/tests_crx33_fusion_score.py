"""CRX33 — deux écritures massives de lead ne recalculaient pas le score.

``merge_leads`` complète les champs VIDES du survivant depuis les leads
absorbés (téléphone, e-mail, ville, facture, orientation… — autant de
composantes du score) et ``questionnaire.appliquer_section`` écrit exactement
les champs que le client vient de renseigner. Ni l'une ni l'autre ne
rappelait ``recompute_lead_score`` : la fiche s'enrichissait, la colonne
``score`` restait celle d'avant, et le badge comme le tri « par score »
mentaient jusqu'à la prochaine édition manuelle.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm import questionnaire as quest
from apps.crm import stages
from apps.crm.models import Lead, QuestionnaireLien
from apps.crm.scoring import compute_score
from apps.crm.services import merge_leads, recompute_lead_score
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


class FusionRecalculeLeScoreTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX33 fusion', slug='taqinor-crx33-fusion')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial CRX33',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_crx33', password='x', company=self.company,
            role=self.role)
        # Survivant PAUVRE : presque aucune composante de score.
        self.survivant = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.NEW)
        recompute_lead_score(self.survivant)
        self.survivant.refresh_from_db()
        # Absorbé RICHE : il apporte tout ce qui manque au survivant.
        self.absorbe = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.NEW,
            telephone='0612345678', email='benali@exemple.ma',
            ville='Casablanca', facture_hiver=4200,
            type_installation='residentiel', canal='reference',
            surface_toiture_m2=120, orientation='sud',
            regularisation_8221=True)

    def test_le_survivant_herite_bien_des_champs(self):
        """Contrôle d'assiette : sans enrichissement, il n'y a rien à
        recalculer et le test suivant ne prouverait rien."""
        merge_leads(self.survivant, [self.absorbe], self.user)
        self.survivant.refresh_from_db()
        self.assertEqual(self.survivant.telephone, '0612345678')
        self.assertEqual(self.survivant.facture_hiver, 4200)

    def test_le_score_du_survivant_est_recalcule(self):
        score_avant = self.survivant.score

        merge_leads(self.survivant, [self.absorbe], self.user)

        self.survivant.refresh_from_db()
        self.assertEqual(self.survivant.score, compute_score(self.survivant))
        self.assertGreater(self.survivant.score, score_avant)

    def test_fusion_sans_absorbe_ne_change_rien(self):
        """``merge_leads`` sort tôt quand il n'y a personne à absorber : pas
        d'écriture surprise du score."""
        avant = self.survivant.score
        merge_leads(self.survivant, [], self.user)
        self.survivant.refresh_from_db()
        self.assertEqual(self.survivant.score, avant)


class QuestionnaireRecalculeLeScoreTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX33 quest', slug='taqinor-crx33-quest')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect questionnaire',
            stage=stages.NEW)
        recompute_lead_score(self.lead)
        self.lead.refresh_from_db()
        self.lien = QuestionnaireLien.objects.create(
            company=self.company, lead=self.lead,
            questions={'energie': True, 'contact': True})

    def test_section_energie_recalcule_le_score(self):
        score_avant = self.lead.score

        enregistrees = quest.appliquer_section(
            self.lien, 'energie', reponses={'facture_hiver': 5200})

        self.assertIn('facture_hiver', enregistrees)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.score, compute_score(self.lead))
        self.assertGreater(self.lead.score, score_avant)

    def test_section_contact_recalcule_aussi(self):
        """La complétude du profil est une composante du score : une section
        « coordonnées » la fait bouger comme une autre."""
        score_avant = self.lead.score

        quest.appliquer_section(
            self.lien, 'contact',
            reponses={'email': 'prospect@exemple.ma', 'ville': 'Agadir'})

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.score, compute_score(self.lead))
        self.assertGreater(self.lead.score, score_avant)

    def test_reponse_vide_n_ecrit_rien_et_ne_touche_pas_au_score(self):
        score_avant = self.lead.score

        enregistrees = quest.appliquer_section(
            self.lien, 'energie', reponses={})

        self.assertEqual(enregistrees, [])
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.score, score_avant)
