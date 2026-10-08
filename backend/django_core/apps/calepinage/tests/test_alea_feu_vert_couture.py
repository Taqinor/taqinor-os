"""ALEA37 — la porte feu vert lit ``visites.selectors.visite_feu_vert``.

Avec l'option ``feu_vert_bureau_etudes``, une variante n'est retenable que si
la visite la PLUS RÉCENTE du lead est VALIDÉE ; la porte se referme au
renvoi. Le parcours de visite est joué par les vrais endpoints HTTP des
visites (aucun lead fabriqué avec ``visite_effectuee=True``).

Run :
    python manage.py test apps.calepinage.tests.test_alea_feu_vert_couture -v2
"""
from rest_framework.exceptions import ValidationError

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.calepinage.services.variantes import retenir_variante
from apps.visites.tests.test_visite_terrain import VisiteTerrainBase, auth


class ParcoursVisiteMixin:
    """Gestes réels de visite (HTTP) — réutilisé par
    ``test_cal206_feu_vert``."""

    def visite_creer_terminer(self, lead=None):
        lead = lead or self.lead
        resp = self.api.post('/api/django/visites/visites/',
                             {'lead': lead.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        visite_id = resp.data['id']
        self.remplir(visite_id)
        resp = self.api.post(
            f'/api/django/visites/visites/{visite_id}/terminer/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return visite_id

    def visite_valider(self, visite_id):
        resp = auth(self.bureau).post(
            f'/api/django/visites/visites/{visite_id}/valider/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def visite_renvoyer(self, visite_id):
        resp = auth(self.bureau).post(
            f'/api/django/visites/visites/{visite_id}/renvoyer/',
            {'photos': [], 'mesures': [], 'motif': 'Reprendre la toiture.'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)


class FeuVertCoutureTests(ParcoursVisiteMixin, VisiteTerrainBase):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk)
        self.variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='V1')

    def _active(self):
        enregistrer_parametres(
            self.company, {'presets': {'feu_vert_bureau_etudes': True}})

    def _retenir_refuse(self):
        with self.assertRaises(ValidationError) as ctx:
            retenir_variante(self.variante)
        self.assertIn('feu_vert', ctx.exception.detail)
        # Persistance : le refus n'a rien écrit.
        self.variante.refresh_from_db()
        self.assertFalse(self.variante.retenue)

    def _retenir_passe(self):
        retenir_variante(self.variante)
        self.variante.refresh_from_db()
        self.assertTrue(self.variante.retenue)

    def test_terminee_refuse(self):
        self._active()
        self.visite_creer_terminer()
        # Le lead est « visite effectuée » côté CRM, mais PAS validée.
        self._retenir_refuse()

    def test_validee_passe(self):
        self._active()
        visite_id = self.visite_creer_terminer()
        self.visite_valider(visite_id)
        self._retenir_passe()

    def test_renvoyee_refuse(self):
        self._active()
        visite_id = self.visite_creer_terminer()
        self.visite_valider(visite_id)
        self.visite_renvoyer(visite_id)
        self._retenir_refuse()

    def test_option_inactive_passe(self):
        self.visite_creer_terminer()
        self._retenir_passe()
