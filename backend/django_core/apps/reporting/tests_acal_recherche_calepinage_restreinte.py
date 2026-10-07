"""ACAL296 — la recherche globale ne rend que les calepinages VISIBLES.

Constat C-ACAL-014 (audit 2026-10-04) : ``_spec_calepinage`` partait de
``Calepinage.objects.filter(company=...)`` — la vue restreinte au
responsable (``presets.vue_restreinte_au_responsable``) filtrait la liste du
module mais la barre de recherche du haut exposait le titre et le client
d'un calepinage hors vue.

Tenu ici avec le réglage ÉCRIT par ``enregistrer_parametres`` (jamais un
mock) et des permissions réelles : U (voir + gérer, sans approuver) ne
trouve pas K (dont il n'est ni responsable ni créateur) ; un porteur de
``calepinage_approuver`` le trouve.

Run :
    python manage.py test \
        apps.reporting.tests_acal_recherche_calepinage_restreinte -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.calepinage.permissions import CAL_APPROUVER, CAL_GERER, CAL_VOIR
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.crm.models import Client, Lead
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/reporting/search/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class RechercheCalepinageRestreinteTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACAL296 Co',
                                              slug='acal296-co')
        role_u = Role.objects.create(company=self.company,
                                     nom='Concepteur296',
                                     permissions=[CAL_VOIR, CAL_GERER])
        role_appro = Role.objects.create(
            company=self.company, nom='Approbateur296',
            permissions=[CAL_VOIR, CAL_GERER, CAL_APPROUVER])
        self.u = User.objects.create_user(
            username='acal296_u', password='x', company=self.company,
            role=role_u)
        self.proprietaire = User.objects.create_user(
            username='acal296_proprio', password='x', company=self.company,
            role=role_u)
        self.approbateur = User.objects.create_user(
            username='acal296_appro', password='x', company=self.company,
            role=role_appro)
        lead = Lead.objects.create(company=self.company, nom='Toiture QA')
        self.client_k = Client.objects.create(company=self.company,
                                              nom='Client Secret K')
        self.k = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='QA-RECH-K',
            client=self.client_k, responsable=self.proprietaire,
            cree_par=self.proprietaire)
        self.m = Calepinage.objects.create(
            company=self.company, lead_id=lead.pk, titre='QA-RECH-M',
            responsable=self.u, cree_par=self.u)
        enregistrer_parametres(self.company, {
            'presets': {'vue_restreinte_au_responsable': True}})

    def _groupe_calepinage(self, user):
        reponse = _api(user).get(URL, {'q': 'QA-RECH'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        groupes = {g['type']: g for g in reponse.data.get('groups', [])}
        return reponse, groupes.get('calepinage')

    def test_calepinage_hors_vue_absent_de_la_recherche(self):
        reponse, groupe = self._groupe_calepinage(self.u)
        # U voit son propre calepinage (le groupe existe, la recherche marche)…
        self.assertIsNotNone(groupe, reponse.data)
        ids = [r['id'] for r in groupe['results']]
        self.assertIn(self.m.pk, ids)
        # … mais jamais K, ni son titre ni son client, nulle part.
        self.assertNotIn(self.k.pk, ids)
        self.assertNotIn('QA-RECH-K', str(reponse.data))
        self.assertNotIn('Client Secret K', str(reponse.data))
        # Par le nom du client non plus.
        reponse = _api(self.u).get(URL, {'q': 'Client Secret K'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertNotIn('calepinage',
                         [g['type'] for g in reponse.data['groups']])

    def test_approbateur_le_trouve(self):
        reponse, groupe = self._groupe_calepinage(self.approbateur)
        self.assertIsNotNone(groupe, reponse.data)
        resultats = {r['id']: r for r in groupe['results']}
        self.assertIn(self.k.pk, resultats)
        self.assertIn(self.m.pk, resultats)
        self.assertEqual(resultats[self.k.pk]['label'], 'QA-RECH-K')
        self.assertEqual(resultats[self.k.pk]['sublabel'], 'Client Secret K')
