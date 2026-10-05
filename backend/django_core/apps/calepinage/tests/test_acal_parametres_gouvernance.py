"""ACAL302 — clés de gouvernance = ``calepinage_approuver`` ; chaque
changement de réglage calepinage est journalisé (auteur, avant, après).

Constat C-ACAL-069 (audit 2026-10-04) : un porteur de ``calepinage_gerer``
seul pouvait, par un simple PUT, couper la vue restreinte au responsable,
l'approbation exigée ou le feu vert bureau d'études — et aucun changement
de réglage n'était tracé.

Rôles RÉELS (``Responsable`` : gérer sans approuver ; ``Directeur`` :
approbateur), route réelle, ``SettingsAuditLog`` réel — aucun mock.

Run :
    python manage.py test apps.calepinage.tests.test_acal_parametres_gouvernance -v2
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import ParametresCalepinage
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.parametres.models_audit import SettingsAuditLog
from apps.roles.models import (
    DIRECTEUR_PERMISSIONS, RESPONSABLE_PERMISSIONS, Role,
)
from authentication.models import Company

User = get_user_model()
URL = '/api/django/calepinage/parametres/'

GOUVERNANCE = {'vue_restreinte_au_responsable': True,
               'approbation_exigee': True,
               'feu_vert_bureau_etudes': True}


def _client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class GouvernanceTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Gouvernance Co',
                                              slug='acal302-gouv')
        responsable = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=list(RESPONSABLE_PERMISSIONS))
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.resp = User.objects.create_user(
            username='acal302_resp', password='x', company=self.company,
            role=responsable)
        self.dir = User.objects.create_user(
            username='acal302_dir', password='x', company=self.company,
            role=directeur)
        self.api_resp = _client(self.resp)
        self.api_dir = _client(self.dir)
        enregistrer_parametres(self.company, {'presets': dict(
            GOUVERNANCE, jeux=[{'id': 'std', 'nom': 'Standard'}])})
        SettingsAuditLog.objects.filter(company=self.company).delete()

    def _presets(self):
        return ParametresCalepinage.objects.get(company=self.company).presets

    def _journal(self):
        return SettingsAuditLog.objects.filter(company=self.company,
                                               section='calepinage')

    def _put_presets(self, api, **changes):
        presets = dict(self._presets(), **changes)
        return api.put(URL, {'presets': presets}, format='json')

    def test_gerer_seul_ne_desactive_pas_la_vue_restreinte(self):
        avant = self._presets()
        reponse = self._put_presets(self.api_resp,
                                    vue_restreinte_au_responsable=False)
        self.assertEqual(reponse.status_code, 403, reponse.data)
        self.assertIn('vue_restreinte_au_responsable', reponse.data)
        self.assertEqual(self._presets(), avant)
        self.assertFalse(self._journal().exists())

    def test_gerer_seul_ne_desactive_pas_l_approbation_exigee_ni_le_feu_vert(
            self):
        for cle in ('approbation_exigee', 'feu_vert_bureau_etudes'):
            with self.subTest(cle=cle):
                reponse = self._put_presets(self.api_resp, **{cle: False})
                self.assertEqual(reponse.status_code, 403, reponse.data)
                self.assertIn(cle, reponse.data)
                self.assertIs(self._presets()[cle], True)

    def test_section_recopiee_inchangee_passe(self):
        reponse = self._put_presets(
            self.api_resp, jeux=[{'id': 'std', 'nom': 'Standard v2'}])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._presets()['jeux'][0]['nom'], 'Standard v2')
        reponse = self.api_resp.put(
            URL, {'degagements': {'retrait_rive_m': 0.5}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_approbateur_change_la_gouvernance(self):
        reponse = self._put_presets(self.api_dir,
                                    vue_restreinte_au_responsable=False)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIs(self._presets()['vue_restreinte_au_responsable'], False)

    def test_chaque_changement_est_journalise_avec_auteur_avant_apres(self):
        self._put_presets(self.api_dir, vue_restreinte_au_responsable=False)
        self.api_resp.put(URL, {'degagements': {'retrait_rive_m': 0.5}},
                          format='json')
        lignes = {ligne.field: ligne for ligne in self._journal()}
        self.assertEqual(sorted(lignes), [
            'degagements.retrait_rive_m',
            'presets.vue_restreinte_au_responsable'])
        gouv = lignes['presets.vue_restreinte_au_responsable']
        self.assertEqual((gouv.user_id, gouv.old_value, gouv.new_value),
                         (self.dir.pk, 'True', 'False'))
        allee = lignes['degagements.retrait_rive_m']
        self.assertEqual((allee.user_id, allee.old_value, allee.new_value),
                         (self.resp.pk, '', '0.5'))

    def test_put_sans_changement_ne_journalise_rien(self):
        reponse = self._put_presets(self.api_resp)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(self._journal().exists())
