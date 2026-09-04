"""AUD606 — une cible « à lecteur propre » n'accuse plus le FICHIER.

Quatre cibles (``obstacles``, ``chaines``, ``avis``, ``avis_veille``) sont
déclarées importables par le registre plateforme mais n'ont AUCUNE entrée dans
``FIELD_MAPS`` : leur lecture vit dans leur app propriétaire
(``apps/ao/imports.py``, ``apps/veille_ao/imports.py``). Elles passaient donc le
contrôle « cible connue », puis explosaient en ``KeyError`` sur
``FIELD_MAPS[target]`` — une exception non prévue, attrapée par le
``except Exception`` générique de la vue, qui répondait au client
« Lecture du fichier impossible (format invalide ?) » sur un fichier
PARFAITEMENT valide.

Le diagnostic était FAUX : il envoyait l'utilisateur corriger un fichier qui
n'avait rien.

Run :
    python manage.py test apps.dataimport.test_aud606_cible_a_lecteur_propre -v2
"""
from django.test import SimpleTestCase

from apps.dataimport import services

CIBLES_A_LECTEUR_PROPRE = ('obstacles', 'chaines', 'avis', 'avis_veille')

FICHIER_VALIDE = b'nom;email\nAlaoui;a@exemple.ma\n'


class TestRefusExplicite(SimpleTestCase):
    def test_les_quatre_cibles_sont_bien_declarees_mais_sans_carte(self):
        """Le garde-fou du test : sans ça, il serait vert pour rien."""
        for cible in CIBLES_A_LECTEUR_PROPRE:
            with self.subTest(cible=cible):
                self.assertIn(cible, services.TARGETS)
                self.assertNotIn(cible, services.FIELD_MAPS)

    def test_le_dry_run_dit_le_VRAI_motif(self):
        for cible in CIBLES_A_LECTEUR_PROPRE:
            with self.subTest(cible=cible):
                with self.assertRaises(ValueError) as ctx:
                    services.dry_run(FICHIER_VALIDE, 'contacts.csv', cible)
                message = str(ctx.exception)
                self.assertIn("écran d'import", message)
                self.assertIn("Le fichier n'est pas en cause", message)

    def test_le_motif_NOMME_le_module_proprietaire(self):
        with self.assertRaises(ValueError) as ctx:
            services.dry_run(FICHIER_VALIDE, 'releve.csv', 'obstacles')
        self.assertIn('ao', str(ctx.exception))

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
        attendu = {'obstacles': 'ao', 'chaines': 'ao', 'avis': 'ao',
                   'avis_veille': 'veille_ao'}
        for cible, module in attendu.items():
            with self.subTest(cible=cible):
                self.assertEqual(
                    services.module_proprietaire_de_cible(cible), module)

    def test_une_cible_inconnue_ne_nomme_personne(self):
        self.assertEqual(
            services.module_proprietaire_de_cible('bidon_inexistant'), '')
