"""NTGRC6 — registre des violations de données + délai légal de 72 h.

Garanties : l'échéance vaut détection + 72 h, une violation non notifiée
au-delà remonte dans le selector, la référence VD est race-safe (jamais
count()+1), le statut ne s'écrit pas au champ et tout reste scopé société.
"""
from django.test import TestCase
from django.utils import timezone

from apps.grc.models import ViolationDonnees
from apps.grc.selectors import violations_echeance_72h_depassee
from apps.grc.services import (
    TransitionViolationInterdite, changer_statut_violation, creer_violation,
    notifier_cndp,
)
from authentication.models import Company
from testkit.base import TenantAPITestCase


class Echeance72hTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC6 SA', slug='ntgrc6')
        cls.autre = Company.objects.create(nom='NTGRC6 B', slug='ntgrc6-b')

    def _violation(self, company=None, detection=None, **kw):
        return creer_violation(
            company or self.company,
            date_detection=detection or timezone.now(), **kw)

    def test_echeance_vaut_detection_plus_72h(self):
        detection = timezone.now()
        violation = self._violation(detection=detection)
        self.assertEqual(
            violation.date_echeance_72h,
            detection + timezone.timedelta(hours=72))

    def test_echeance_calculee_sur_la_detection_pas_sur_lincident(self):
        incident = timezone.now() - timezone.timedelta(days=10)
        detection = timezone.now()
        violation = self._violation(
            detection=detection, date_incident=incident)
        self.assertEqual(
            violation.date_echeance_72h,
            detection + timezone.timedelta(hours=72))

    def test_echeance_jamais_reculee(self):
        violation = self._violation()
        posee = violation.date_echeance_72h
        violation.date_detection = timezone.now() + timezone.timedelta(days=5)
        violation.save()
        violation.refresh_from_db()
        self.assertEqual(violation.date_echeance_72h, posee)

    def test_violation_non_notifiee_au_dela_remonte(self):
        vieille = timezone.now() - timezone.timedelta(hours=100)
        en_retard = self._violation(detection=vieille)
        self._violation()  # détectée à l'instant : pas en retard
        resultats = list(violations_echeance_72h_depassee(self.company))
        self.assertEqual([v.pk for v in resultats], [en_retard.pk])

    def test_violation_notifiee_nest_plus_en_retard(self):
        vieille = timezone.now() - timezone.timedelta(hours=100)
        violation = self._violation(detection=vieille)
        notifier_cndp(violation)
        self.assertEqual(
            list(violations_echeance_72h_depassee(self.company)), [])

    def test_notification_non_requise_nest_jamais_en_retard(self):
        vieille = timezone.now() - timezone.timedelta(hours=100)
        self._violation(detection=vieille, notification_cndp_requise=False)
        self.assertEqual(
            list(violations_echeance_72h_depassee(self.company)), [])

    def test_selector_borne_a_la_societe(self):
        vieille = timezone.now() - timezone.timedelta(hours=100)
        self._violation(company=self.autre, detection=vieille)
        self.assertEqual(
            list(violations_echeance_72h_depassee(self.company)), [])


class ReferenceEtCycleDeVieTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTGRC6 R', slug='ntgrc6-r')

    def test_reference_incremente_sans_jamais_compter_les_lignes(self):
        v1 = creer_violation(self.company, date_detection=timezone.now())
        v2 = creer_violation(self.company, date_detection=timezone.now())
        self.assertTrue(v1.reference.startswith('VD-'))
        self.assertNotEqual(v1.reference, v2.reference)
        # La suppression d'une ligne ne fait PAS reculer la numérotation
        # (le piège de count()+1, qui a collisionné en production).
        ViolationDonnees.objects.filter(pk=v1.pk).delete()
        v3 = creer_violation(self.company, date_detection=timezone.now())
        self.assertNotIn(v3.reference, {v1.reference, v2.reference})

    def test_transition_illegale_est_refusee(self):
        violation = creer_violation(
            self.company, date_detection=timezone.now())
        changer_statut_violation(
            violation, ViolationDonnees.STATUT_CLOTUREE)
        with self.assertRaises(TransitionViolationInterdite) as ctx:
            changer_statut_violation(
                violation, ViolationDonnees.STATUT_EN_ANALYSE)
        self.assertIn('Clôturée', str(ctx.exception))

    def test_double_notification_est_refusee(self):
        violation = creer_violation(
            self.company, date_detection=timezone.now())
        notifier_cndp(violation)
        with self.assertRaises(TransitionViolationInterdite):
            notifier_cndp(violation)


class EndpointViolationsTests(TenantAPITestCase):
    BASE = '/api/django/grc/violations-donnees/'

    def _admin(self):
        return self.client_as(role='admin')

    def test_creation_impose_societe_reference_et_echeance(self):
        detection = timezone.now()
        r = self._admin().post(
            self.BASE,
            {'date_detection': detection.isoformat(),
             'nature': 'confidentialite', 'gravite': 'elevee',
             'nombre_personnes_estime': 120},
            format='json')
        self.assertEqual(r.status_code, 201, r.content)
        violation = ViolationDonnees.objects.get(pk=r.data['id'])
        self.assertEqual(violation.company, self.company)
        self.assertTrue(violation.reference.startswith('VD-'))
        self.assertIsNotNone(violation.date_echeance_72h)

    def test_le_statut_ne_s_ecrit_pas_au_champ(self):
        violation = creer_violation(
            self.company, date_detection=timezone.now())
        r = self._admin().patch(
            f'{self.BASE}{violation.pk}/', {'statut': 'cloturee'},
            format='json')
        self.assertEqual(r.status_code, 200, r.content)
        violation.refresh_from_db()
        self.assertEqual(violation.statut, ViolationDonnees.STATUT_OUVERTE)

    def test_action_notifier_cndp_puis_doublon_renvoie_400(self):
        violation = creer_violation(
            self.company, date_detection=timezone.now())
        url = f'{self.BASE}{violation.pk}/notifier-cndp/'
        r = self._admin().post(url, {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['statut'], ViolationDonnees.STATUT_NOTIFIEE)
        r2 = self._admin().post(url, {}, format='json')
        self.assertEqual(r2.status_code, 400)
        self.assertIn('statut', r2.data)

    def test_endpoint_echeance_depassee(self):
        vieille = timezone.now() - timezone.timedelta(hours=100)
        creer_violation(self.company, date_detection=vieille)
        r = self._admin().get(f'{self.BASE}echeance-depassee/')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(len(r.data['results']), 1)
        self.assertTrue(r.data['results'][0]['echeance_72h_depassee'])

    def test_incident_posterieur_a_la_detection_est_refuse(self):
        detection = timezone.now()
        r = self._admin().post(
            self.BASE,
            {'date_detection': detection.isoformat(),
             'date_incident': (
                 detection + timezone.timedelta(days=1)).isoformat()},
            format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('date_incident', r.data)

    def test_liste_scopee_societe(self):
        creer_violation(self.other_company, date_detection=timezone.now())
        r = self._admin().get(self.BASE)
        lignes = r.data.get('results', r.data)
        self.assertEqual(lignes, [])
