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
import ast
import dataclasses
import inspect
import textwrap

from django.test import SimpleTestCase

from apps.ventes.domain import overrides as registre
from apps.ventes.domain import pipeline


class CavalierADocstringDuRegistre(SimpleTestCase):
    """(a) — les trois affirmations fausses ont disparu, et ce qu'elles
    remplacent est VRAI (vérifié, pas affirmé)."""

    #: Bornes de la RÉTRACTATION : la docstring réécrite CITE les trois phrases
    #: fausses pour annoncer qu'elles ont cessé d'être vraies. Chercher les
    #: phrases dans la docstring ENTIÈRE ferait rougir la garde sur sa propre
    #: correction — elle porte donc sur le texte HORS de cette citation.
    DEBUT_RETRACTATION = 'CE PARAGRAPHE DISAIT TROIS'
    FIN_RETRACTATION = 'Les trois ont cessé'

    def _doc(self):
        return registre.__doc__ or ''

    def _doc_hors_retractation(self):
        doc = self._doc()
        debut = doc.find(self.DEBUT_RETRACTATION)
        if debut == -1:
            return doc
        fin = doc.find(self.FIN_RETRACTATION, debut)
        self.assertNotEqual(
            fin, -1,
            "la rétractation est ouverte sans être refermée : borne à revoir")
        return doc[:debut] + doc[fin:]

    def test_les_trois_affirmations_fausses_ont_disparu(self):
        """Elles ne sont plus AFFIRMÉES — seulement citées comme démenties."""
        doc = self._doc_hors_retractation().lower()
        for mensonge in (
                "il ne persiste rien",
                "n'existe pas encore",
                "aucun appelant n'est branché"):
            with self.subTest(mensonge=mensonge):
                self.assertNotIn(mensonge, doc)

    def test_la_colonne_existe_vraiment(self):
        from apps.ventes.models import Devis

        champs = {f.name for f in Devis._meta.get_fields()}
        self.assertIn('overrides', champs)

    @staticmethod
    def _corps(fonction):
        """La source SANS sa docstring.

        Ces gardes portent sur ce que le code FAIT. Les docstrings de ce module
        EXPLIQUENT pourquoi ``Devis.save`` est écarté et citent donc l'appel :
        les inclure ferait rougir la garde sur son propre commentaire.

        Le découpage passe par l'AST, jamais par ``source.replace(__doc__)`` :
        depuis Python 3.13 le compilateur DÉSINDENTE ``__doc__``, qui n'est
        alors plus un sous-texte de la source — la garde deviendrait muette
        selon la version de l'interpréteur.
        """
        source = textwrap.dedent(inspect.getsource(fonction))
        noeud = ast.parse(source).body[0]
        premier = noeud.body[0] if noeud.body else None
        if not (isinstance(premier, ast.Expr)
                and isinstance(premier.value, ast.Constant)
                and isinstance(premier.value.value, str)):
            return source
        lignes = source.splitlines(keepends=True)
        del lignes[premier.lineno - 1:premier.end_lineno]
        return ''.join(lignes)

    def test_ecrire_colonne_est_le_seul_ecrivain_et_il_persiste(self):
        """``ecrire_colonne`` écrit par un UPDATE d'UNE SEULE colonne — jamais
        ``Devis.save`` (ni ``updated_at`` ni le gel ``prix_par_kwc``)."""
        corps = self._corps(registre.ecrire_colonne)
        self.assertIn('.update(overrides=registre)', corps)
        self.assertNotIn('.save(', corps)

    def test_les_constructeurs_de_registre_restent_purs(self):
        for fonction in (registre.poser, registre.regenerer,
                         registre.fusionner):
            with self.subTest(fonction=fonction.__name__):
                corps = self._corps(fonction)
                self.assertNotIn('.save(', corps)
                self.assertNotIn('.update(', corps)

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
