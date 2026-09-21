"""AUD606 — une cible « à lecteur propre » n'accuse plus le FICHIER.

Une cible « à lecteur propre » (déclarée importable par le registre
plateforme mais SANS entrée dans ``FIELD_MAPS`` : sa lecture vit dans son app
propriétaire, pas dans ``dataimport``) passait le contrôle « cible connue »,
puis explosait en ``KeyError`` sur ``FIELD_MAPS[target]`` — une exception non
prévue, attrapée par le ``except Exception`` générique de la vue, qui
répondait au client « Lecture du fichier impossible (format invalide ?) » sur
un fichier PARFAITEMENT valide.

Le diagnostic était FAUX : il envoyait l'utilisateur corriger un fichier qui
n'avait rien.

SOLMVP-sweep (2026-09-21) — les 4 cibles historiques qui illustraient ce cas
(``obstacles``/``chaines``/``avis`` via ``apps/ao``, ``avis_veille`` via
``apps/veille_ao``) ont disparu de ``TARGETS`` avec leurs apps, PARQUÉES par
le Groupe SOLMVP (MVP solaire) : plus aucune cible « à lecteur propre » ne
vit aujourd'hui parmi les apps KEPT (vérifié en shell Django —
``core.platform.import_specs()`` == ``FIELD_MAPS`` exactement). Le
MÉCANISME générique (``verifier_cible_importable``/
``module_proprietaire_de_cible``/``dry_run``) reste du code vivant — il sert
la PROCHAINE app qui déclarera une cible à lecteur propre — donc ces tests
continuent de le prouver, mais sur un manifeste FICTIF injecté (même patron
que ``TestNewManifestTargetAppearsWithoutTouchingServices`` d'ARC32) plutôt
que sur une app réelle aujourd'hui disparue.

Run :
    python manage.py test apps.dataimport.test_aud606_cible_a_lecteur_propre -v2
"""
from contextlib import contextmanager
from unittest import mock

from django.test import SimpleTestCase

from apps.dataimport import services

FICHIER_VALIDE = b'nom;email\nAlaoui;a@exemple.ma\n'

CIBLE_BIDON = 'cible_bidon_aud606'
MODULE_BIDON = 'bidon_aud606'


@contextmanager
def _avec_cible_a_lecteur_propre_fictive():
    """Injecte un manifeste plateforme fictif déclarant ``CIBLE_BIDON`` dans
    ``import_specs`` (donc dans ``TARGETS``) sans jamais toucher
    ``FIELD_MAPS`` — exactement la forme d'une cible à lecteur propre."""
    from core import platform as core_platform

    vrais = core_platform.collect_platform_manifests()
    faux = dict(vrais)
    faux[MODULE_BIDON] = {
        'module': MODULE_BIDON,
        'record_targets': [], 'searchable_models': [],
        'customfield_models': [], 'import_specs': [CIBLE_BIDON],
        'agent_actions_module': '', 'automation_state_fields': [],
        'kpi_providers': [],
    }
    with mock.patch(
            'core.platform.collect_platform_manifests',
            side_effect=lambda: faux):
        yield


class TestRefusExplicite(SimpleTestCase):
    def test_les_quatre_cibles_sont_bien_declarees_mais_sans_carte(self):
        """Le garde-fou du test : sans ça, il serait vert pour rien."""
        with _avec_cible_a_lecteur_propre_fictive():
            self.assertIn(CIBLE_BIDON, services.TARGETS)
            self.assertNotIn(CIBLE_BIDON, services.FIELD_MAPS)

    def test_le_dry_run_dit_le_VRAI_motif(self):
        with _avec_cible_a_lecteur_propre_fictive():
            with self.assertRaises(ValueError) as ctx:
                services.dry_run(FICHIER_VALIDE, 'contacts.csv', CIBLE_BIDON)
            message = str(ctx.exception)
            self.assertIn("écran d'import", message)
            self.assertIn("Le fichier n'est pas en cause", message)

    def test_le_motif_NOMME_le_module_proprietaire(self):
        with _avec_cible_a_lecteur_propre_fictive():
            with self.assertRaises(ValueError) as ctx:
                services.dry_run(FICHIER_VALIDE, 'releve.csv', CIBLE_BIDON)
            self.assertIn(MODULE_BIDON, str(ctx.exception))

    def test_une_cible_reellement_inconnue_garde_son_message(self):
        with self.assertRaises(ValueError) as ctx:
            services.dry_run(FICHIER_VALIDE, 'x.csv', 'bidon_inexistant')
        self.assertIn("inconnue", str(ctx.exception))

    def test_une_cible_generique_ne_declenche_rien(self):
        """Non-régression : les cibles servies ici passent le contrôle."""
        for cible in ('leads', 'clients', 'products'):
            with self.subTest(cible=cible):
                services.verifier_cible_importable(cible)


class TestModuleProprietaire(SimpleTestCase):
    def test_chaque_cible_a_lecteur_propre_nomme_son_app(self):
        with _avec_cible_a_lecteur_propre_fictive():
            self.assertEqual(
                services.module_proprietaire_de_cible(CIBLE_BIDON),
                MODULE_BIDON)

    def test_une_cible_inconnue_ne_nomme_personne(self):
        self.assertEqual(
            services.module_proprietaire_de_cible('bidon_inexistant'), '')
