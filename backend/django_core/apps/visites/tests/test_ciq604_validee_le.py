"""CIQ604 — visite validée : date et auteur du feu vert enregistrés côté
serveur (``validee_le`` / ``validee_par``), exposés par
``releve_pour_calepinage``. Aucune reprise des anciennes visites (D-CIQ-21).
"""
import datetime

from django.utils import timezone

from apps.visites import selectors, services
from apps.visites.models import VisiteTerrain
from apps.visites.tests.test_visite_terrain import (
    BUREAU, VisiteTerrainBase, auth, make_user)


class ValideeLeTests(VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.valideur = make_user(self.company, 'ciq604-valideur', BUREAU)
        self.api_bureau = auth(self.valideur)

    def _visite_terminee(self):
        return VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.commercial,
            statut=VisiteTerrain.Statut.TERMINEE,
            mesures={'toiture': {'longueur_m': 12, 'largeur_m': 8}})

    def test_valider_pose_la_date_et_l_auteur(self):
        visite = self._visite_terminee()
        avant = timezone.now()
        services.valider_visite(visite, self.valideur)
        visite.refresh_from_db()
        self.assertEqual(visite.statut, VisiteTerrain.Statut.VALIDEE)
        self.assertIsNotNone(visite.validee_le)
        self.assertGreaterEqual(visite.validee_le, avant)
        self.assertLessEqual(visite.validee_le, timezone.now())
        self.assertEqual(visite.validee_par_id, self.valideur.id)

    def test_la_route_valider_pose_l_auteur_serveur(self):
        visite = self._visite_terminee()
        resp = self.api_bureau.post(
            f'/api/django/visites/visites/{visite.id}/valider/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        visite.refresh_from_db()
        self.assertEqual(visite.validee_par_id, self.valideur.id)
        self.assertIsNotNone(visite.validee_le)

    def test_le_corps_de_requete_ne_peut_pas_forcer_la_date(self):
        visite = self._visite_terminee()
        faux = (timezone.now() - datetime.timedelta(days=30)).isoformat()
        self.api_bureau.post(
            f'/api/django/visites/visites/{visite.id}/valider/',
            {'validee_le': faux, 'validee_par': self.commercial.id},
            format='json')
        visite.refresh_from_db()
        self.assertGreater(visite.validee_le,
                           timezone.now() - datetime.timedelta(minutes=5))
        self.assertEqual(visite.validee_par_id, self.valideur.id)

    def test_releve_pour_calepinage_renvoie_la_date(self):
        visite = self._visite_terminee()
        services.valider_visite(visite, self.valideur)
        visite.refresh_from_db()
        rendu = selectors.releve_pour_calepinage(self.lead)
        self.assertEqual(rendu['visite_id'], visite.id)
        self.assertEqual(rendu['validee_le'], visite.validee_le.isoformat())

    def test_une_visite_validee_avant_la_tache_garde_none(self):
        VisiteTerrain.objects.create(
            company=self.company, lead=self.lead,
            statut=VisiteTerrain.Statut.VALIDEE)
        rendu = selectors.releve_pour_calepinage(self.lead)
        self.assertIsNotNone(rendu['visite_id'])
        self.assertIsNone(rendu['validee_le'])

    def test_un_auteur_supprime_garde_la_date(self):
        visite = self._visite_terminee()
        services.valider_visite(visite, self.valideur)
        self.valideur.delete()
        visite.refresh_from_db()
        self.assertIsNone(visite.validee_par_id)
        self.assertIsNotNone(visite.validee_le)

    def test_renvoyer_retire_la_date_du_feu_vert(self):
        visite = self._visite_terminee()
        services.valider_visite(visite, self.valideur)
        visite.refresh_from_db()
        self.assertIsNotNone(visite.validee_le)
        services.renvoyer_visite(visite, self.valideur, motif='à refaire')
        visite.refresh_from_db()
        self.assertEqual(visite.statut, VisiteTerrain.Statut.A_REFAIRE)
        self.assertIsNone(visite.validee_le)
        self.assertIsNone(visite.validee_par_id)
