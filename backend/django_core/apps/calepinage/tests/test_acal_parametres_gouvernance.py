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
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    DIRECTEUR_PERMISSIONS, RESPONSABLE_PERMISSIONS,
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
        self.assertIn('reglages_societe', reponse.data)  # D-ACAL-104
        self.assertEqual(self._presets(), avant)
        self.assertFalse(self._journal().exists())

    def test_gerer_seul_ne_desactive_pas_l_approbation_exigee_ni_le_feu_vert(
            self):
        for cle in ('approbation_exigee', 'feu_vert_bureau_etudes'):
            with self.subTest(cle=cle):
                reponse = self._put_presets(self.api_resp, **{cle: False})
                self.assertEqual(reponse.status_code, 403, reponse.data)
                # D-ACAL-104 : le refus vient désormais d'AVANT la clé (écrire un réglage société exige
                # ``calepinage_approuver``) ; la garde par clé reste en seconde ligne pour un appel système.
                self.assertIn('reglages_societe', reponse.data)
                self.assertIs(self._presets()[cle], True)

    def test_section_recopiee_inchangee_passe(self):
        reponse = self._put_presets(
            self.api_dir, jeux=[{'id': 'std', 'nom': 'Standard v2'}])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._presets()['jeux'][0]['nom'], 'Standard v2')
        reponse = self.api_dir.put(
            URL, {'degagements': {'retrait_rive_m': 0.5}}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_approbateur_change_la_gouvernance(self):
        reponse = self._put_presets(self.api_dir,
                                    vue_restreinte_au_responsable=False)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIs(self._presets()['vue_restreinte_au_responsable'], False)

    def test_chaque_changement_est_journalise_avec_auteur_avant_apres(self):
        self._put_presets(self.api_dir, vue_restreinte_au_responsable=False)
        self.api_dir.put(URL, {'degagements': {'retrait_rive_m': 0.5}},
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
                         (self.dir.pk, '', '0.5'))

    def test_jeux_de_reglages_passent_par_le_put_fusionne(self):
        """ACAL347 (c) : un jeu s'ajoute par le PUT ``parametres/``, les
        jumeaux ``enregistrer_jeu`` / ``retirer_jeu`` n'existent plus."""
        from apps.calepinage.services import presets
        for nom in ('enregistrer_jeu', 'retirer_jeu'):
            self.assertFalse(hasattr(presets, nom), nom)
        jeux = self._presets()['jeux'] + [{'id': 'nouveau', 'nom': 'Nouveau'}]
        reponse = self._put_presets(self.api_dir, jeux=jeux)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual([jeu['id'] for jeu in self._presets()['jeux']],
                         ['std', 'nouveau'])

    def test_put_sans_changement_ne_journalise_rien(self):
        reponse = self._put_presets(self.api_dir)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(self._journal().exists())


class ReglagesSocieteReserveAuxApprobateursTest(TestCase):
    """D-ACAL-104 — « Managers only, both » : écrire un réglage de la SOCIÉTÉ exige le droit
    d'appliquer / retirer le profil de départ (``calepinage_approuver``) ; un Responsable
    (``calepinage_gerer`` sans approuver) LIT toujours et règle toujours SON calepinage."""

    BASE = '/api/django/calepinage/'

    def setUp(self):
        from apps.calepinage.models import Calepinage
        self.company = Company.objects.create(nom='Reserve Co', slug='acal104-reserve')
        responsable = Role.objects.create(
            company=self.company, nom='Responsable',
            permissions=list(RESPONSABLE_PERMISSIONS))
        directeur = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.resp = User.objects.create_user(
            username='acal104_resp', password='x', company=self.company, role=responsable)
        self.dir = User.objects.create_user(
            username='acal104_dir', password='x', company=self.company, role=directeur)
        self.api_resp = _client(self.resp)
        self.api_dir = _client(self.dir)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=9_999_999, titre='Projet')

    def _refuse(self, reponse):
        self.assertEqual(reponse.status_code, 403, getattr(reponse, 'data', None))
        self.assertIn('reglages_societe', reponse.data)

    def test_les_routes_d_ecriture_de_la_societe_refusent_qui_ne_peut_pas_approuver(self):
        b = self.BASE
        self._refuse(self.api_resp.put(b + 'parametres/', {'imagerie': {}}, format='json'))
        self._refuse(self.api_resp.put(b + 'parametres/profils-types/', {'profils': []}, format='json'))
        self._refuse(self.api_resp.post(b + 'gabarits-dossiers/', {}, format='json'))
        self._refuse(self.api_resp.patch(b + 'gabarits-dossiers/1/', {}, format='json'))
        self._refuse(self.api_resp.delete(b + 'gabarits-dossiers/1/'))
        self._refuse(self.api_resp.post(b + 'calepinages/systemes-fixation/', {}, format='json'))
        self._refuse(self.api_resp.patch(b + 'calepinages/systemes-fixation/1/', {}, format='json'))
        self._refuse(self.api_resp.delete(b + 'calepinages/systemes-fixation/1/'))

    def test_lire_reste_ouvert_a_qui_ne_peut_pas_approuver(self):
        b = self.BASE
        for chemin in ('parametres/', 'parametres/profils-types/', 'gabarits-dossiers/',
                       'calepinages/systemes-fixation/'):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.api_resp.get(b + chemin).status_code, 200, chemin)

    def test_un_approbateur_ecrit_toujours(self):
        b = self.BASE
        self.assertEqual(self.api_dir.put(b + 'parametres/', {'imagerie': {}}, format='json').status_code, 200)
        self.assertEqual(self.api_dir.put(
            b + 'parametres/profils-types/', {'profils': []}, format='json').status_code, 200)
        for reponse in (self.api_dir.post(b + 'gabarits-dossiers/', {}, format='json'),
                        self.api_dir.post(b + 'calepinages/systemes-fixation/', {}, format='json')):
            self.assertNotEqual(reponse.status_code, 403, reponse.data)

    def test_source_partagee_des_degagements_aller_retour(self):
        """D-ACAL-105 — UNE source (``degagements.source``) couvre l'allée par défaut et le retrait de
        bord par défaut : écrite, relue par ``GET parametres/`` ; vidée, elle disparaît (« non sourcée »)."""
        b = self.BASE + 'parametres/'
        corps = {'degagements': {'allee_technique_m': 0.9, 'retrait_rive_m': 0.5,
                                 'source': '  notice X  '}}
        self.assertEqual(self.api_dir.put(b, corps, format='json').status_code, 200)
        servi = self.api_resp.get(b).data['degagements']
        self.assertEqual(servi['source'], 'notice X')
        corps['degagements']['source'] = ''
        self.assertEqual(self.api_dir.put(b, corps, format='json').status_code, 200)
        self.assertNotIn('source', self.api_resp.get(b).data['degagements'])

    def test_le_reglage_d_un_calepinage_reste_a_qui_peut_gerer(self):
        """La ligne entre société et projet : `PATCH calepinages/<id>/` (le calepinage d'UN projet)
        reste ``calepinage_gerer`` ; les routes ``parametres/``, ``gabarits-dossiers/`` et
        ``systemes-fixation/`` sont la société."""
        reponse = self.api_resp.patch(
            f'{self.BASE}calepinages/{self.calepinage.pk}/', {'titre': 'Réglé par le vendeur'},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
