"""ADEV58 (C-ADEV-040) — ``conception-electrique`` et ``simuler`` gardés par
le prédicat de modifiabilité du devis (geste ETUDE).

* accepté / inactif : POST conception et POST simuler → 409, empreinte et
  étude inchangées (relues en base) ; GET → 200 avec l'étude STOCKÉE, sans
  écriture ;
* envoyé : POST qui réécrit l'étude → 200 + trace « corrigé après envoi »
  au chatter + jeton d'édition (``updated_at``) avancé ;
* brouillon : comportement inchangé (couvert par ``test_pv41``).

La tâche Celery de simulation est doublée (aucune exécution) ; le reste est
réel (rôles, prédicat, moteur électrique, base).

Test-du-test : retirer ``_refus_modifiabilite`` de ``conception_electrique``
⇒ ``test_post_accepte_409`` échoue.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, DevisActivity
from apps.ventes.tests import test_pv41_conception_electrique as pv41
from authentication.models import Company

User = get_user_model()


class ConceptionGardeeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom="Acme", slug="adev58-acme")
        self.user = User.objects.create_user(
            username="adev58_resp", password="x",
            role_legacy="responsable", company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.crm_client = Client.objects.create(
            company=self.company, nom="Client ADEV58",
            email="adev58@example.com")

    def _devis(self, **etat):
        devis = pv41.ConceptionElectriqueEndpointTest._make_devis(
            self, self.company)
        # Étude rangée AVANT le changement d'état (brouillon modifiable).
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 200)
        if etat:
            Devis.objects.filter(pk=devis.pk).update(**etat)
        devis.refresh_from_db()
        return devis

    @staticmethod
    def _url(devis, chemin="conception-electrique"):
        return "/api/django/ventes/devis/%s/%s/" % (devis.pk, chemin)

    def _etat(self, devis):
        d = Devis.objects.get(pk=devis.pk)
        return (d.electrical_design_hash, d.electrical_design,
                (d.etude_params or {}).get("simulation"))

    def test_post_accepte_409(self):
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        avant = self._etat(devis)
        resp = self.api.post(self._url(devis), {"ac_m": 41.0}, format="json")
        self.assertEqual(resp.status_code, 409)
        self.assertTrue(resp.data["revision_possible"])
        self.assertEqual(self._etat(devis), avant)

    def test_post_inactif_409(self):
        devis = self._devis(is_active=False)
        avant = self._etat(devis)
        resp = self.api.post(self._url(devis), {"ac_m": 41.0}, format="json")
        self.assertEqual(resp.status_code, 409)
        self.assertFalse(resp.data["revision_possible"])
        self.assertEqual(self._etat(devis), avant)

    def test_simuler_accepte_409(self):
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        avant = self._etat(devis)
        with mock.patch(
                "apps.ventes.tasks.task_simulate_bankable_study.apply_async"
        ) as tache:
            resp = self.api.post(self._url(devis, "simuler"), {},
                                 format="json")
        self.assertEqual(resp.status_code, 409)
        tache.assert_not_called()
        self.assertEqual(self._etat(devis), avant)

    def test_get_accepte_sans_ecriture(self):
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        # Témoin : une réécriture le ferait disparaître.
        design = dict(devis.electrical_design)
        Devis.objects.filter(pk=devis.pk).update(
            electrical_design={**design, "_temoin": True})
        avant = self._etat(devis)
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.get("_temoin"))
        self.assertEqual(self._etat(devis), avant)

    def test_get_accepte_sans_etude_rangee_ne_persiste_rien(self):
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        Devis.objects.filter(pk=devis.pk).update(
            electrical_design=None, electrical_design_hash=None)
        resp = self.api.get(self._url(devis))
        self.assertEqual(resp.status_code, 200)
        d = Devis.objects.get(pk=devis.pk)
        self.assertIsNone(d.electrical_design)
        self.assertIsNone(d.electrical_design_hash)

    def test_envoye_trace(self):
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        hash_avant = devis.electrical_design_hash
        jeton_avant = devis.updated_at
        nb_activites = DevisActivity.objects.filter(devis=devis).count()
        resp = self.api.post(self._url(devis), {"ac_m": 41.0}, format="json")
        self.assertEqual(resp.status_code, 200)
        d = Devis.objects.get(pk=devis.pk)
        self.assertNotEqual(d.electrical_design_hash, hash_avant)
        self.assertEqual(d.statut, Devis.Statut.ENVOYE)
        self.assertGreater(
            DevisActivity.objects.filter(devis=devis).count(), nb_activites)
        self.assertIn("resync_apres_envoi", d.etude_params or {})
        self.assertGreater(d.updated_at, jeton_avant)
