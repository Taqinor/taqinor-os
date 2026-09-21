"""CAD133 — le score regarde enfin ce que le client FAIT.

Audit L3 du 21/09/2026, section CAD-K. ``compute_score`` n'additionnait que
des DÉCLARATIONS de capture ; pire, la composante fraîcheur comptait l'âge du
LEAD, si bien qu'un prospect qui répond aujourd'hui après quatre mois de
silence recevait 1 point sur 12, comme un dossier mort.

Ce fichier verrouille les deux moitiés du Done :

  * un lead qui ROUVRE sa proposition voit son score monter — et à
    l'INSTANT, pas au passage nocturne ;
  * la fraîcheur repart de la DERNIÈRE interaction, pas de la création.

Plus trois garde-fous : aucun signal n'est capté en plus (tout vient de la
base), `ventes` est lu par son selector (jamais ses modèles), et un signal
illisible vaut « absent » — un badge de score ne fait jamais tomber une fiche.
"""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from testkit.time import frozen

from apps.crm import horaires, scoring, services, signaux, stages
from apps.crm.models import Lead, LeadActivity
from apps.parametres.models import CompanyProfile

User = get_user_model()

#: Mardi 15 septembre 2026, 10 h à Casablanca.
MAINTENANT = datetime.datetime(2026, 9, 15, 10, 0, tzinfo=horaires.CASABLANCA)

#: Ce que le selector de `ventes` renvoie quand rien n'a été ouvert.
RIEN_OUVERT = {'ouverte': False, 'vues': 0, 'lue_en_detail': False,
               'derniere_vue': None}


def _engagement(**extra):
    base = dict(RIEN_OUVERT)
    base.update(extra)
    return base


class SignauxTests(TestCase):
    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad133', defaults={'nom': 'cad133'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username='cad133-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', stage=stages.CONTACTED,
            owner=self.acteur, telephone='0600000061')

    def test_aucun_signal_sur_un_lead_neuf(self):
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement()):
            lus = signaux.signaux_comportement(self.lead)
        self.assertFalse(any(lus.values()), lus)

    def test_une_seule_vue_nest_pas_une_reouverture(self):
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement(ouverte=True, vues=1)):
            lus = signaux.signaux_comportement(self.lead)
        self.assertTrue(lus['proposition_ouverte'])
        self.assertFalse(lus['proposition_rouverte'])

    def test_deux_vues_valent_une_reouverture(self):
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement(ouverte=True, vues=2)):
            lus = signaux.signaux_comportement(self.lead)
        self.assertTrue(lus['proposition_rouverte'])

    def test_rappel_demande_est_lu_sur_le_lead(self):
        self.lead.contact_preference_set_at = MAINTENANT
        self.lead.save(update_fields=['contact_preference_set_at'])
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement()):
            self.assertTrue(
                signaux.signaux_comportement(self.lead)['rappel_demande'])

    def test_issue_jointe_est_lue_dans_le_chatter(self):
        LeadActivity.objects.create(
            company=self.company, lead=self.lead, user=self.acteur,
            kind=LeadActivity.Kind.APPEL, body='Appel.', outcome='joint')
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement()):
            self.assertTrue(
                signaux.signaux_comportement(self.lead)['client_joint'])

    def test_un_selector_en_echec_vaut_absent_jamais_une_exception(self):
        with patch('apps.ventes.selectors.engagement_proposition_du_lead',
                   side_effect=RuntimeError('ventes indisponible')):
            lus = signaux.signaux_comportement(self.lead)
        self.assertFalse(lus['proposition_ouverte'])


class ScoreComportementTests(TestCase):
    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad133-score', defaults={'nom': 'cad133-score'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Chraibi', stage=stages.QUOTE_SENT,
            telephone='0600000062')

    def test_rouvrir_sa_proposition_fait_monter_le_score(self):
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement()):
            avant = scoring.compute_score(self.lead)
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement(ouverte=True, vues=3)):
            apres = scoring.compute_score(self.lead)
        self.assertGreater(apres, avant)

    def test_lire_en_detail_pese_plus_quouvrir(self):
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement(ouverte=True, vues=1)):
            ouverte = scoring.compute_score(self.lead)
        with patch.object(
                signaux, '_engagement_proposition',
                return_value=_engagement(ouverte=True, vues=1,
                                         lue_en_detail=True)):
            lue = scoring.compute_score(self.lead)
        self.assertGreater(lue, ouverte)

    def test_les_poids_sont_nommes_et_ordonnes_par_force(self):
        """Revenir sur sa proposition dit plus que l'avoir ouverte une fois."""
        poids = scoring._W_COMPORTEMENT
        self.assertGreater(poids['proposition_rouverte'],
                           poids['proposition_ouverte'])
        self.assertTrue(all(p > 0 for p in poids.values()))

    def test_le_score_reste_borne_a_cent(self):
        with patch.object(
                signaux, '_engagement_proposition',
                return_value=_engagement(ouverte=True, vues=9,
                                         lue_en_detail=True)):
            self.lead.contact_preference_set_at = MAINTENANT
            self.assertLessEqual(scoring.compute_score(self.lead), 100)


class FraicheurTests(TestCase):
    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad133-frais', defaults={'nom': 'cad133-frais'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Tazi', stage=stages.CONTACTED,
            telephone='0600000063')
        # Un lead créé il y a quatre mois.
        Lead.objects.filter(pk=self.lead.pk).update(
            date_creation=MAINTENANT - datetime.timedelta(days=120))
        self.lead.refresh_from_db()

    def test_sans_interaction_la_fraicheur_part_de_la_creation(self):
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement()):
            self.assertIsNone(signaux.derniere_interaction(self.lead))
            vieux = scoring._recency_score(self.lead)
        self.assertLessEqual(vieux, 3)

    def test_une_reponse_daujourdhui_rend_le_dossier_frais(self):
        """LE cas de l'audit : quatre mois de silence puis une réponse."""
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement()):
            vieux = scoring._recency_score(self.lead)
            LeadActivity.objects.create(
                company=self.company, lead=self.lead, user=None,
                kind=LeadActivity.Kind.NOTE, body='Le client a répondu.')
            frais = scoring._recency_score(self.lead)
        self.assertGreater(frais, vieux)

    def test_la_derniere_vue_de_la_proposition_compte_aussi(self):
        hier = MAINTENANT - datetime.timedelta(days=1)
        with patch.object(
                signaux, '_engagement_proposition',
                return_value=_engagement(ouverte=True, vues=1,
                                         derniere_vue=hier)):
            self.assertEqual(signaux.derniere_interaction(self.lead), hier)


class RecalculImmediatTests(TestCase):
    """« Le badge ne ment plus jusqu'au passage nocturne. »"""

    def setUp(self):
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
        self.company, _ = Company.objects.get_or_create(
            slug='cad133-live', defaults={'nom': 'cad133-live'})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Sekkat', stage=stages.QUOTE_SENT,
            telephone='0600000064')

    def test_une_ouverture_recalcule_le_score_sur_le_champ(self):
        with patch.object(services, 'recompute_lead_score') as recalcul:
            services.noter_devis_ouvert('DV-1', self.lead)
        recalcul.assert_called_once_with(self.lead)

    def test_une_reouverture_recalcule_le_score_sur_le_champ(self):
        with patch.object(services, 'recompute_lead_score') as recalcul:
            services.noter_devis_reouvert('DV-1', self.lead, vues=3)
        recalcul.assert_called_once_with(self.lead)

    def test_le_score_persiste_monte_apres_une_reouverture(self):
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement()):
            services.recompute_lead_score(self.lead)
        self.lead.refresh_from_db()
        avant = self.lead.score
        with patch.object(signaux, '_engagement_proposition',
                          return_value=_engagement(ouverte=True, vues=3)):
            services.noter_devis_reouvert('DV-1', self.lead, vues=3)
        self.lead.refresh_from_db()
        self.assertGreater(self.lead.score, avant)
