"""NTGRC15 — revues périodiques du risque (cadence + journal).

Garanties : enregistrer une revue AVANCE la prochaine date de revue du
risque, les risques dus remontent dans `risques_a_revoir`, et tout reste
scopé société.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import RevueRisque, RisqueEntreprise
from apps.grc.selectors import risques_a_revoir
from apps.grc.services import creer_risque, enregistrer_revue
from authentication.models import Company
from testkit.base import TenantAPITestCase


class CadenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC15 SA', slug='ntgrc15')
        cls.autre = Company.objects.create(nom='NTGRC15 B', slug='ntgrc15-b')

    def test_une_revue_avance_la_prochaine_date_du_risque(self):
        risque = creer_risque(self.company, titre='R')
        prochaine = timezone.now().date() + timezone.timedelta(days=90)
        enregistrer_revue(
            self.company, risque, date_revue=timezone.now().date(),
            prochaine_revue=prochaine)
        risque.refresh_from_db()
        self.assertEqual(risque.date_revue_prevue, prochaine)

    def test_une_revue_sans_prochaine_date_ne_touche_pas_la_cadence(self):
        depart = timezone.now().date() + timezone.timedelta(days=10)
        risque = creer_risque(
            self.company, titre='R', date_revue_prevue=depart)
        enregistrer_revue(
            self.company, risque, date_revue=timezone.now().date())
        risque.refresh_from_db()
        self.assertEqual(risque.date_revue_prevue, depart)

    def test_une_decision_clos_clot_aussi_le_risque(self):
        risque = creer_risque(self.company, titre='R')
        enregistrer_revue(
            self.company, risque, date_revue=timezone.now().date(),
            decision=RevueRisque.DECISION_CLOS)
        risque.refresh_from_db()
        self.assertEqual(risque.statut, RisqueEntreprise.STATUT_CLOS)

    def test_les_revues_sont_un_journal_cumulatif(self):
        risque = creer_risque(self.company, titre='R')
        for jours in (1, 2):
            enregistrer_revue(
                self.company, risque,
                date_revue=timezone.now().date() -
                timezone.timedelta(days=jours))
        self.assertEqual(risque.revues.count(), 2)


class RisquesARevoirTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC15 R', slug='ntgrc15-r')

    def test_un_risque_du_remonte(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        du = creer_risque(self.company, titre='Dû', date_revue_prevue=hier)
        creer_risque(
            self.company, titre='Plus tard',
            date_revue_prevue=timezone.now().date() +
            timezone.timedelta(days=60))
        self.assertEqual(
            [r.pk for r in risques_a_revoir(self.company)], [du.pk])

    def test_la_fenetre_within_elargit_la_selection(self):
        dans_30 = timezone.now().date() + timezone.timedelta(days=30)
        risque = creer_risque(
            self.company, titre='R', date_revue_prevue=dans_30)
        self.assertEqual(list(risques_a_revoir(self.company)), [])
        self.assertEqual(
            [r.pk for r in risques_a_revoir(self.company, within=45)],
            [risque.pk])

    def test_un_risque_sans_cadence_ne_remonte_pas(self):
        creer_risque(self.company, titre='Sans cadence')
        self.assertEqual(list(risques_a_revoir(self.company, within=999)), [])

    def test_un_risque_clos_ne_remonte_pas(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        risque = creer_risque(
            self.company, titre='Clos', date_revue_prevue=hier)
        risque.statut = RisqueEntreprise.STATUT_CLOS
        risque.save()
        self.assertEqual(list(risques_a_revoir(self.company)), [])

    def test_selector_borne_a_la_societe(self):
        autre = Company.objects.create(nom='NTGRC15 X', slug='ntgrc15-x')
        hier = timezone.now().date() - timezone.timedelta(days=1)
        creer_risque(autre, titre='Etranger', date_revue_prevue=hier)
        self.assertEqual(list(risques_a_revoir(self.company)), [])


class EndpointRevuesTests(TenantAPITestCase):
    BASE = '/api/django/grc/revues-risque/'

    def setUp(self):
        super().setUp()
        self.risque = creer_risque(self.company, titre='R')

    def _admin(self):
        return self.client_as(role='admin')

    def test_creer_une_revue_avance_la_cadence(self):
        prochaine = timezone.now().date() + timezone.timedelta(days=120)
        r = self._admin().post(
            self.BASE,
            {'risque': self.risque.pk,
             'date_revue': timezone.now().date().isoformat(),
             'prochaine_revue': prochaine.isoformat()},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        self.risque.refresh_from_db()
        self.assertEqual(self.risque.date_revue_prevue, prochaine)

    def test_une_prochaine_revue_anterieure_est_refusee(self):
        aujourdhui = timezone.now().date()
        r = self._admin().post(
            self.BASE,
            {'risque': self.risque.pk,
             'date_revue': aujourdhui.isoformat(),
             'prochaine_revue': (
                 aujourdhui - timezone.timedelta(days=1)).isoformat()},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('prochaine_revue', r.data)

    def test_une_revue_ne_se_reecrit_pas(self):
        revue = enregistrer_revue(
            self.company, self.risque, date_revue=timezone.now().date())
        r = self._admin().patch(
            f'{self.BASE}{revue.pk}/', {'commentaire': 'x'}, format='json')
        self.assertEqual(r.status_code, 405)

    def test_endpoint_risques_a_revoir(self):
        hier = timezone.now().date() - timezone.timedelta(days=1)
        self.risque.date_revue_prevue = hier
        self.risque.save()
        r = self._admin().get(f'{self.BASE}risques-a-revoir/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['results']), 1)
