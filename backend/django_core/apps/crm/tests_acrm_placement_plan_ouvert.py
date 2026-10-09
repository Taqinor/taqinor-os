"""ACRM46 — ``deja_en_cadence`` du placement ne compte qu'un lead portant une
touche À FAIRE (prédicat partagé ``_q_plan_ouvert`` d'``initialiser_plan_
relance``, TREADMILL-1538) : un lead aux touches toutes closes redevient
candidat — rejoue la sonde LSVC4-8.

Test-du-test : retirer ``statut=A_FAIRE`` du filtre ⇒
test_touches_closes_candidat échoue.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm import stages
from apps.crm.models import Lead, RelanceEtape
from apps.crm.services import _decider_placements


class PlacementPlanOuvertTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM46 Solaire', slug='acrm46-placement')
        self.maintenant = timezone.now()

    def _vieux_lead(self, nom, statut_touche):
        lead = Lead.objects.create(
            company=self.company, nom=nom, stage=stages.QUOTE_SENT)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=self.maintenant - datetime.timedelta(days=60))
        quand = self.maintenant - datetime.timedelta(days=50)
        RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 1',
            due_at=quand, due_date=quand.date(), statut=statut_touche)
        return lead

    def test_touches_closes_candidat(self):
        lead = self._vieux_lead('Clos', RelanceEtape.Statut.ANNULEE)
        decisions, ignores, _ = _decider_placements(
            self.company, self.maintenant)
        par_lead = {d['lead'].pk: d for d in decisions}
        self.assertIn(lead.pk, par_lead)
        self.assertEqual(par_lead[lead.pk]['code'], 'dormant_devis')
        self.assertEqual(ignores['deja_en_cadence'], 0)

    def test_touche_ouverte_ecarte(self):
        lead = self._vieux_lead('Ouvert', RelanceEtape.Statut.A_FAIRE)
        decisions, ignores, _ = _decider_placements(
            self.company, self.maintenant)
        self.assertNotIn(lead.pk, {d['lead'].pk for d in decisions})
        self.assertEqual(ignores['deja_en_cadence'], 1)
