"""QJR227 — lot de câblage de finition : trois cavaliers, zéro changement client.

(a) ``domain/overrides`` — la docstring du module faisait TROIS affirmations
    fausses dans cet arbre (« il ne persiste rien », « la colonne
    ``Devis.overrides`` n'existe pas encore », « aucun appelant n'est
    branché »). Réécrite sur l'état réel ; les faits qu'elle énonce sont
    vérifiés ici plutôt que crus sur parole.
(b) ``domain/pipeline`` — ``IntentionDevis.force_etudes`` n'était transmis que
    par la branche ``MODE_RAFRAICHIR`` : un appelant qui demandait des études
    FORCÉES sur un compose/create recevait les études EN CACHE.
(c) ``domain/pipeline`` — ``IntentionDevis.overrides`` était déclaré et
    documenté, POSÉ par personne et LU par personne : supprimé (arbitrage
    « câbler ou supprimer »).

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr227_cavaliers_cablage -v 2
"""
import dataclasses
import inspect

from django.test import SimpleTestCase

from apps.ventes.domain import overrides as registre
from apps.ventes.domain import pipeline


class CavalierADocstringDuRegistre(SimpleTestCase):
    """(a) — les trois affirmations fausses ont disparu, et ce qu'elles
    remplacent est VRAI (vérifié, pas affirmé)."""

    def _doc(self):
        return registre.__doc__ or ''

    def test_les_trois_affirmations_fausses_ont_disparu(self):
        doc = self._doc()
        for mensonge in (
                "Il ne PERSISTE rien",
                "n'existe pas encore",
                "aucun appelant n'est branché"):
            with self.subTest(mensonge=mensonge):
                self.assertNotIn(mensonge, doc)

    def test_la_colonne_existe_vraiment(self):
        from apps.ventes.models import Devis

        champs = {f.name for f in Devis._meta.get_fields()}
        self.assertIn('overrides', champs)

    def test_ecrire_colonne_est_le_seul_ecrivain_et_il_persiste(self):
        """``ecrire_colonne`` écrit par un UPDATE d'UNE SEULE colonne — jamais
        ``Devis.save`` (ni ``updated_at`` ni le gel ``prix_par_kwc``)."""
        source = inspect.getsource(registre.ecrire_colonne)
        self.assertIn('.update(overrides=registre)', source)
        self.assertNotIn('.save(', source)

    def test_les_constructeurs_de_registre_restent_purs(self):
        for fonction in (registre.poser, registre.regenerer,
                         registre.fusionner):
            with self.subTest(fonction=fonction.__name__):
                source = inspect.getsource(fonction)
                self.assertNotIn('.save(', source)
                self.assertNotIn('.update(', source)

    def test_la_preseance_a_bien_un_appelant_de_production(self):
        """La docstring l'affirme — on le vérifie sur le code réel."""
        from apps.ventes.domain import scenario

        source = inspect.getsource(scenario.puissance_kwc_du_devis)
        self.assertIn('preseance_nb_panneaux', source)


class CavalierBForceEtudesSurTousLesModes(SimpleTestCase):
    """(b) — ``force_etudes`` atteint les études sur le mode COMPOSER aussi."""

    def test_le_mode_composer_transmet_force_etudes(self):
        source = inspect.getsource(pipeline.appliquer)
        self.assertIn('rafraichir_etudes(verrou, force=intention.force_etudes)',
                      source)

    def test_le_mode_rafraichir_le_transmettait_deja(self):
        source = inspect.getsource(pipeline._appliquer_sur_devis_existant)
        self.assertIn('rafraichir_etudes(devis, force=intention.force_etudes)',
                      source)

    def test_aucun_rafraichissement_du_pipeline_n_ignore_le_drapeau(self):
        """La garde qui rougira si un troisième site oublie de le passer."""
        source = inspect.getsource(pipeline)
        appels = [ligne.strip() for ligne in source.splitlines()
                  if ligne.strip().startswith('rafraichir_etudes(')]
        self.assertEqual(len(appels), 2, appels)
        for appel in appels:
            with self.subTest(appel=appel):
                self.assertIn('force=intention.force_etudes', appel)


class CavalierCIntentionSansOverrides(SimpleTestCase):
    """(c) — le champ qui mentait a été SUPPRIMÉ, pas laissé en place."""

    def test_le_champ_a_disparu_de_l_intention(self):
        champs = {f.name for f in dataclasses.fields(pipeline.IntentionDevis)}
        self.assertNotIn('overrides', champs)

    def test_construire_une_intention_avec_overrides_leve(self):
        with self.assertRaises(TypeError):
            pipeline.IntentionDevis(
                origine=pipeline.ORIGINE_ECRAN, company=object(),
                overrides={'taille.nb_panneaux': {'valeur': 14}})

    def test_la_docstring_ne_le_promet_plus(self):
        doc = pipeline.IntentionDevis.__doc__ or ''
        self.assertNotIn(
            '``overrides`` — le patch de surcharges déclarées', doc)

    def test_les_champs_restants_sont_intacts(self):
        """Non-régression : seul ``overrides`` part."""
        champs = {f.name for f in dataclasses.fields(pipeline.IntentionDevis)}
        for attendu in ('origine', 'company', 'lead', 'client', 'entrees',
                        'cible', 'scenario', 'layout', 'exact', 'mode',
                        'composition', 'etude_initiale', 'force_etudes'):
            with self.subTest(champ=attendu):
                self.assertIn(attendu, champs)
