"""NTMKT34 — Tâche Celery beat « recalcul quotidien du score de maturité »
(pénalité d'inactivité 30j, étend NTMKT18).

Couvre : un lead inactif 31 jours voit son score baisser au lendemain du
seuil, no-op si le paramètre société NTMKT18 est resté désactivé (aucun
``ScoreMaturite`` n'existe jamais), l'événement ``lead_maturite_changee``
est émis UNIQUEMENT quand la valeur change, et la tâche beat est joignable.
"""
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Lead, PointContact
from apps.marketing import services as mkt_services
from apps.marketing.models import Campagne, EnvoiCampagne, ScoreMaturite
from core import events


class RecalculScoreMaturiteInactiviteTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='ntmkt34', nom='NTMKT34')
        parametres = mkt_services.parametres_marketing_pour(self.co)
        parametres.score_maturite_actif = True
        parametres.save(update_fields=['score_maturite_actif'])
        self.lead = Lead.objects.create(company=self.co, nom='Lead A')

    def _donne_un_score_initial(self, quand):
        campagne = Campagne.objects.create(company=self.co, nom='C')
        EnvoiCampagne.objects.create(
            company=self.co, campagne=campagne, destinataire='a@b.ma',
            contact_ref=f'lead:{self.lead.id}', ouvert_le=quand)
        PointContact.objects.create(
            company=self.co, lead=self.lead, canal='meta_ads',
            date_contact=quand, ordre=1)
        return mkt_services.recalculer_score_maturite(self.co, self.lead.id)

    def test_no_op_sans_aucun_score_maturite_existant(self):
        # Aucun ScoreMaturite créé (jamais d'événement NTMKT18) -> rien à
        # balayer, comportement par défaut inchangé.
        changes = mkt_services.recalculer_scores_maturite_inactivite(self.co)
        self.assertEqual(changes, [])
        self.assertEqual(ScoreMaturite.objects.filter(company=self.co).count(), 0)

    def test_lead_inactif_31_jours_voit_son_score_baisser(self):
        now = timezone.now()
        score_initial = self._donne_un_score_initial(now - timezone.timedelta(days=31))
        self.assertEqual(score_initial.valeur, 2)  # 1 ouverture, pondération défaut

        changes = mkt_services.recalculer_scores_maturite_inactivite(
            self.co, now=now)
        self.assertEqual(changes, [self.lead.id])
        score = ScoreMaturite.objects.get(company=self.co, lead_id=self.lead.id)
        self.assertEqual(score.valeur, 0)  # 2 - 10 (pénalité), clampé à 0

    def test_lead_actif_recemment_ne_change_pas(self):
        now = timezone.now()
        self._donne_un_score_initial(now - timezone.timedelta(days=5))
        changes = mkt_services.recalculer_scores_maturite_inactivite(
            self.co, now=now)
        self.assertEqual(changes, [])

    def test_evenement_emis_uniquement_sur_changement_reel(self):
        now = timezone.now()
        self._donne_un_score_initial(now - timezone.timedelta(days=31))
        recu = []

        def _handler(sender, **kwargs):
            recu.append(kwargs)
        events.lead_maturite_changee.connect(_handler)
        try:
            mkt_services.recalculer_scores_maturite_inactivite(self.co, now=now)
        finally:
            events.lead_maturite_changee.disconnect(_handler)
        self.assertEqual(len(recu), 1)
        self.assertEqual(recu[0]['lead_id'], self.lead.id)
        self.assertEqual(recu[0]['ancienne_valeur'], 2)
        self.assertEqual(recu[0]['nouvelle_valeur'], 0)

        # Un second recalcul le même jour (pas de nouveau franchissement) ne
        # rejoue pas l'événement.
        recu.clear()
        events.lead_maturite_changee.connect(_handler)
        try:
            mkt_services.recalculer_scores_maturite_inactivite(self.co, now=now)
        finally:
            events.lead_maturite_changee.disconnect(_handler)
        self.assertEqual(recu, [])

    def test_la_tache_beat_est_joignable(self):
        from apps.marketing.tasks import recalculer_scores_maturite_inactivite_task
        resultat = recalculer_scores_maturite_inactivite_task()
        self.assertIn('scores_changes', resultat)
