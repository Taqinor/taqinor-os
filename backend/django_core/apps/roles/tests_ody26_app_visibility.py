"""Tests ODY26 — axe « App visible » par rôle, porté par ``Role.permissions``.

DÉCISION TESTÉE ICI (pas seulement documentée) : aucun nouveau champ backend,
aucune migration. Les codes ``app_<clé>_voir`` sont acceptés PAR FORME et
restent HORS de ``ALL_PERMISSIONS`` — les y mettre restreindrait mécaniquement
le Directeur (dont les permissions en dérivent) à la liste d'apps du jour, et
énumérer les clés d'apps côté backend créerait un 2ᵉ registre que le Groupe ODY
interdit.

Couvre :
  * la forme des codes (fabrication, reconnaissance, non-collision avec les
    codes métier existants ``crm_voir``/``sav_voir``…) ;
  * la sémantique NARROWING OPT-IN (aucun marqueur = aucune restriction) ;
  * le sérialiseur de rôle accepte ces codes et refuse toujours un code
    réellement inconnu ;
  * ni le Directeur ni l'Administrateur ne les portent par défaut (zéro
    régression de visibilité au déploiement).
"""
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.roles.models import (
    ADMIN_PERMISSIONS, ALL_PERMISSIONS, DIRECTEUR_PERMISSIONS,
    RESPONSABLE_PERMISSIONS, UTILISATEUR_PERMISSIONS,
    cles_apps_autorisees, est_permission_app, permission_app,
)
from apps.roles.serializers import RoleSerializer


class FormeDesCodesTests(TestCase):
    def test_fabrication(self):
        self.assertEqual(permission_app('crm'), 'app_crm_voir')
        self.assertEqual(permission_app('gestion_projet'),
                         'app_gestion_projet_voir')

    def test_reconnaissance(self):
        self.assertTrue(est_permission_app('app_crm_voir'))
        self.assertTrue(est_permission_app('app_gestion_projet_voir'))

    def test_aucune_collision_avec_les_codes_metier(self):
        # Les codes existants finissent aussi par `_voir` : la famille ODY26 se
        # distingue par son PRÉFIXE `app_`, jamais par le suffixe seul.
        for code in ('crm_voir', 'sav_voir', 'journal_activite_voir',
                     'prix_achat_voir', 'roles_gerer', 'app_voir', 'app__voir',
                     'app_crm', ''):
            self.assertFalse(est_permission_app(code), code)

    def test_narrowing_opt_in(self):
        # Aucun marqueur → None (« pas de restriction »), jamais un ensemble
        # vide : « restreint à rien » n'existe pas côté données.
        self.assertIsNone(cles_apps_autorisees([]))
        self.assertIsNone(cles_apps_autorisees(None))
        self.assertIsNone(cles_apps_autorisees(['crm_voir', 'ventes_creer']))
        self.assertEqual(
            cles_apps_autorisees(['crm_voir', 'app_crm_voir', 'app_sav_voir']),
            {'crm', 'sav'})


class CatalogueIntactTests(TestCase):
    """Zéro régression de visibilité : personne ne porte ces codes par défaut."""

    def test_absents_du_catalogue(self):
        self.assertFalse([p for p in ALL_PERMISSIONS if est_permission_app(p)])

    def test_absents_des_jeux_par_defaut(self):
        for jeu in (DIRECTEUR_PERMISSIONS, ADMIN_PERMISSIONS,
                    RESPONSABLE_PERMISSIONS, UTILISATEUR_PERMISSIONS):
            self.assertFalse([p for p in jeu if est_permission_app(p)])
            # Donc aucun rôle livré n'est restreint : visibilité historique.
            self.assertIsNone(cles_apps_autorisees(jeu))


class SerializerValidationTests(TestCase):
    """Le sérialiseur accepte la famille ODY26 sans ouvrir la porte au reste.

    On appelle ``validate_permissions`` directement (c'est LA méthode changée) :
    pas de fixture société ni de contexte de requête à monter pour vérifier une
    règle de validation pure.
    """

    def _valider(self, permissions):
        return RoleSerializer(context={}).validate_permissions(permissions)

    def test_accepte_un_code_app(self):
        self.assertEqual(
            self._valider(['crm_voir', 'app_crm_voir']),
            ['crm_voir', 'app_crm_voir'])

    def test_refuse_toujours_un_code_inconnu(self):
        with self.assertRaises(ValidationError):
            self._valider(['crm_voir', 'nimporte_quoi'])

    def test_refuse_une_forme_approchante(self):
        # `app_crm` (sans suffixe) et `crm_app_voir` (sans préfixe) ne sont pas
        # de la famille : ils restent des codes inconnus.
        for code in ('app_crm', 'crm_app_voir'):
            with self.assertRaises(ValidationError, msg=code):
                self._valider([code])
