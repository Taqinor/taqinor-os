"""NTMKT18 — Score de maturité marketing multi-signal (additif à QJ6).

Couvre : no-op par défaut (module désactivé), calcul à partir des signaux
(ouverture/clic), historique des variations consultable, le seuil MQL peut
se déclencher aussi sur le score de maturité (jamais sur le score de qualité
lui-même), et l'endpoint REST.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Lead
from apps.crm.services import maybe_assign_mql
from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne, EnvoiCampagne, ScoreMaturite

from testkit.base import TenantAPITestCase


class ScoreMaturiteServiceTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt18', nom='NTMKT18')
        self.lead = Lead.objects.create(company=self.co, nom='Client A')

    def test_no_op_par_defaut_module_desactive(self):
        self.assertIsNone(
            mkt_services.recalculer_score_maturite(self.co, self.lead.id))
        self.assertEqual(ScoreMaturite.objects.filter(company=self.co).count(), 0)

    def test_ouverture_fait_progresser_le_score_sans_toucher_qj6(self):
        parametres = mkt_services.parametres_marketing_pour(self.co)
        parametres.score_maturite_actif = True
        parametres.save(update_fields=['score_maturite_actif'])
        self.lead.score = 42
        self.lead.save(update_fields=['score'])

        campagne = Campagne.objects.create(company=self.co, nom='C')
        EnvoiCampagne.objects.create(
            company=self.co, campagne=campagne, destinataire='a@b.ma',
            contact_ref=f'lead:{self.lead.id}', ouvert_le=timezone.now())

        score = mkt_services.recalculer_score_maturite(self.co, self.lead.id)
        self.assertEqual(score.valeur, 2)  # pondération par défaut = 2 pts
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.score, 42)  # QJ6 strictement inchangé

    def test_historique_des_variations_consultable(self):
        parametres = mkt_services.parametres_marketing_pour(self.co)
        parametres.score_maturite_actif = True
        parametres.save(update_fields=['score_maturite_actif'])
        campagne = Campagne.objects.create(company=self.co, nom='C')
        EnvoiCampagne.objects.create(
            company=self.co, campagne=campagne, destinataire='a@b.ma',
            contact_ref=f'lead:{self.lead.id}', ouvert_le=timezone.now())
        mkt_services.recalculer_score_maturite(self.co, self.lead.id)
        historique = mkt_services.historique_maturite(self.co, self.lead.id)
        self.assertEqual(len(historique), 1)
        self.assertEqual(historique[0].delta, 2)
        self.assertEqual(historique[0].valeur_apres, 2)

    def test_recalcul_sans_changement_ne_rejoue_pas_l_historique(self):
        parametres = mkt_services.parametres_marketing_pour(self.co)
        parametres.score_maturite_actif = True
        parametres.save(update_fields=['score_maturite_actif'])
        mkt_services.recalculer_score_maturite(self.co, self.lead.id)
        mkt_services.recalculer_score_maturite(self.co, self.lead.id)
        # Aucun signal -> valeur reste 0 aux deux appels -> aucune variation
        # journalisée (la valeur initiale 0 == défaut de création).
        self.assertEqual(
            mkt_services.historique_maturite(self.co, self.lead.id), [])


class MqlSurScoreMaturiteTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt18b', nom='NTMKT18b')
        from apps.parametres.models import CompanyProfile
        CompanyProfile.objects.create(company=self.co, seuil_mql=50)

    def _lead_sous_le_seuil(self):
        return Lead.objects.create(company=self.co, nom='Lead', score=10)

    def test_defaut_score_qualite_seul_inchange(self):
        lead = self._lead_sous_le_seuil()
        self.assertFalse(maybe_assign_mql(lead))
        lead.refresh_from_db()
        self.assertIsNone(lead.mql_assigned_at)

    def test_flag_actif_et_maturite_haute_declenche_le_mql(self):
        parametres = mkt_services.parametres_marketing_pour(self.co)
        parametres.score_maturite_actif = True
        parametres.mql_sur_score_maturite = True
        parametres.ponderation_maturite_ouverture = 60
        parametres.save(update_fields=[
            'score_maturite_actif', 'mql_sur_score_maturite',
            'ponderation_maturite_ouverture'])
        lead = self._lead_sous_le_seuil()
        campagne = Campagne.objects.create(company=self.co, nom='C')
        EnvoiCampagne.objects.create(
            company=self.co, campagne=campagne, destinataire='a@b.ma',
            contact_ref=f'lead:{lead.id}', ouvert_le=timezone.now())
        self.assertTrue(maybe_assign_mql(lead))
        lead.refresh_from_db()
        self.assertIsNotNone(lead.mql_assigned_at)

    def test_flag_inactif_maturite_haute_ne_declenche_rien(self):
        # score_maturite_actif reste False -> maturite_valeur toujours 0,
        # jamais consultée : comportement XMKT21 inchangé.
        lead = self._lead_sous_le_seuil()
        self.assertFalse(maybe_assign_mql(lead))


class ScoreMaturiteEndpointTests(TenantAPITestCase):
    def test_endpoint_module_desactive_renvoie_zero(self):
        lead = Lead.objects.create(company=self.company, nom='Lead')
        res = self.client_as().get(
            f'/api/django/marketing/scores-maturite/{lead.id}/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data['actif'])
        self.assertEqual(data['valeur'], 0)
        self.assertEqual(data['historique'], [])

    def test_endpoint_module_actif_renvoie_le_score(self):
        parametres = mkt_services.parametres_marketing_pour(self.company)
        parametres.score_maturite_actif = True
        parametres.save(update_fields=['score_maturite_actif'])
        lead = Lead.objects.create(company=self.company, nom='Lead')
        campagne = Campagne.objects.create(company=self.company, nom='C')
        EnvoiCampagne.objects.create(
            company=self.company, campagne=campagne, destinataire='a@b.ma',
            contact_ref=f'lead:{lead.id}', ouvert_le=timezone.now())
        res = self.client_as().get(
            f'/api/django/marketing/scores-maturite/{lead.id}/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['actif'])
        self.assertEqual(data['valeur'], 2)
        self.assertEqual(len(data['historique']), 1)

    def test_endpoint_exige_une_authentification(self):
        lead = Lead.objects.create(company=self.company, nom='Lead')
        res = self.client.get(
            f'/api/django/marketing/scores-maturite/{lead.id}/')
        self.assertIn(res.status_code, (401, 403))
