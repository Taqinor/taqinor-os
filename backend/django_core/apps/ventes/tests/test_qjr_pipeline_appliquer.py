# -*- coding: utf-8 -*-
"""QJR85 — `appliquer()` : l'ORDRE UNIQUE des huit étapes.

CE QUE CES TESTS VERROUILLENT, ET POURQUOI.

Constat QB85 (audit L3 du 29/08/2026) : les CINQ origines d'un devis
enchaînent les mêmes étapes, mais chacune dans SON ordre, avec SES oublis. Ce
n'est plus une divergence de RÈGLES — QJR80/QJR82/QJR83/QJR84 viennent de les
rendre communes — c'est une divergence d'ORDONNANCEMENT. Et un ordonnancement
qui diverge produit des devis qui divergent : QJR20 a documenté le cas le plus
cher, où les quatre études repartaient de la composition d'AVANT parce que
personne n'avait relu l'instance verrouillée, et où la conception électrique
PERSISTAIT alors un schéma que le devis ne vendait plus.

``appliquer`` est délibérément SANS RÈGLE PROPRE : elle appelle huit étapes
déjà en service, dans l'ordre, et c'est tout. Les trois tests qui comptent :

  · l'ORDRE des huit étapes est assertÉ (``test_les_huit_etapes_dans_l_ordre``) ;
  · la RELECTURE de l'instance verrouillée est prouvée AVANT les études
    (``test_les_etudes_partent_de_l_instance_relue``) ;
  · AUCUN des cinq chemins ne l'appelle encore
    (``test_aucun_chemin_de_production_n_appelle_appliquer``) — c'est la
    condition de sûreté de la vague M4 : les bascules sont M5, une par une,
    chacune avec son golden.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_qjr_pipeline_appliquer -v 2
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.domain import pipeline

RACINE_VENTES = Path(__file__).resolve().parent.parent


class _FauxDevis:
    """Le strict minimum : un ``pk``, un compteur de relectures, un cache."""

    def __init__(self, pk=1):
        self.pk = pk
        self.relectures = 0
        self.etude_params = {}
        self._prefetched_objects_cache = {'lignes': ['perime']}

    def refresh_from_db(self):
        self.relectures += 1


class _Etapes:
    """Remplace les huit étapes par des espions qui NOTENT leur passage."""

    def __init__(self, journal, *, refus=None, composition=()):
        self.journal = journal
        self.refus = refus
        self.composition = composition
        self.verrou = _FauxDevis()
        self._anciens = {}

    def __enter__(self):
        def _note(nom, retour=None):
            def _espion(*a, **k):
                self.journal.append(nom)
                return retour
            return _espion

        self._anciens = {
            nom: getattr(pipeline, nom) for nom in (
                'resoudre_entrees', 'decider_taille', 'composer', 'verifier',
                'ecrire_lignes', 'ecrire_etude_params', 'rafraichir_etudes',
                'finaliser', '_verrouiller', '_creer_brouillon')
        }
        pipeline.resoudre_entrees = _note('resoudre_entrees', 'entrees')
        pipeline.decider_taille = _note('decider_taille',
                                        pipeline.CibleDevis(nb_panneaux=9))
        pipeline.composer = _note('composer', self.composition)
        pipeline.verifier = _note('verifier', self.refus)
        pipeline.ecrire_lignes = _note('ecrire_lignes', [])
        pipeline.ecrire_etude_params = _note('ecrire_etude_params', {})
        pipeline.rafraichir_etudes = _note('rafraichir_etudes', {})
        pipeline.finaliser = _note('finaliser')
        pipeline._verrouiller = _note('_verrouiller', self.verrou)
        pipeline._creer_brouillon = _note('_creer_brouillon', self.verrou)
        return self

    def __exit__(self, *exc):
        for nom, valeur in self._anciens.items():
            setattr(pipeline, nom, valeur)
        return False


def _intention(**extra):
    champs = dict(origine=pipeline.ORIGINE_ECRAN, company=object(),
                  cible=pipeline.CibleDevis(nb_panneaux=9, panel_watt=710,
                                            kwc=6.39))
    champs.update(extra)
    return pipeline.IntentionDevis(**champs)


class LOrdreDesHuitEtapes(SimpleTestCase):
    """Le contrat central de QJR85 — aucune base requise."""

    def test_les_huit_etapes_dans_l_ordre(self):
        journal = []
        with _Etapes(journal):
            resultat = pipeline.appliquer(_FauxDevis(), _intention())

        # Le verrou se prend entre `verifier` et `ecrire_lignes` : refuser
        # AVANT d'écrire, verrouiller AVANT la première écriture.
        self.assertEqual(
            journal,
            ['resoudre_entrees', 'decider_taille', 'composer', 'verifier',
             '_verrouiller', 'ecrire_lignes', 'ecrire_etude_params',
             'rafraichir_etudes', 'finaliser'])
        # Le journal RENDU ne liste que les huit étapes déclarées.
        self.assertEqual(resultat['etapes'], list(pipeline.ETAPES))

    def test_sans_devis_le_pipeline_cree_un_brouillon(self):
        journal = []
        with _Etapes(journal) as etapes:
            resultat = pipeline.appliquer(None, _intention())
        self.assertIn('_creer_brouillon', journal)
        self.assertNotIn('_verrouiller', journal)
        self.assertIs(resultat['devis'], etapes.verrou)
        self.assertEqual(resultat['etapes'], list(pipeline.ETAPES))

    def test_un_refus_de_verification_arrete_AVANT_toute_ecriture(self):
        """Refuser vaut mieux que créer puis effacer : un devis effacé rendrait
        sa référence au compteur, et le numéro suivant la reprendrait."""
        journal = []
        with _Etapes(journal, refus=[pipeline.MSG_SANS_ONDULEUR_HYBRIDE]):
            with self.assertRaises(Exception) as leve:
                pipeline.appliquer(None, _intention())

        self.assertIn(pipeline.MSG_SANS_ONDULEUR_HYBRIDE, str(leve.exception))
        self.assertEqual(journal[-1], 'verifier')
        for interdit in ('_verrouiller', '_creer_brouillon', 'ecrire_lignes',
                         'ecrire_etude_params', 'rafraichir_etudes',
                         'finaliser'):
            self.assertNotIn(interdit, journal)

    def test_une_origine_inconnue_est_refusee_en_francais(self):
        journal = []
        with _Etapes(journal):
            with self.assertRaises(ValueError) as leve:
                pipeline.appliquer(None, _intention(origine='par-magie'))
        self.assertIn('Origine de devis inconnue', str(leve.exception))
        self.assertEqual(journal, [])

    def test_les_cinq_origines_sont_declarees(self):
        self.assertEqual(
            pipeline.ORIGINES,
            ('ecran', 'calepinage', 'auto', 'tunnel', 'resynchronisation'))


class LesModesNExecutentQueLeursEtapes(SimpleTestCase):
    """QJR93 — un mode DÉCLARE ses étapes, et ``appliquer`` n'en fait pas une
    de plus.

    C'est la propriété qui rend une bascule vérifiable : si le mode ``ecrire``
    pouvait atteindre ``composer``, brancher l'écran dessus recomposerait le
    devis depuis le catalogue et effacerait les prix tapés par le commercial.
    Le test l'interdit par CONSTRUCTION, pas par relecture.
    """

    def test_mode_ecrire_n_ecrit_que_les_lignes(self):
        journal = []
        with _Etapes(journal) as etapes:
            resultat = pipeline.appliquer(
                etapes.verrou,
                _intention(mode=pipeline.MODE_ECRIRE,
                           composition=[{'produit': 1}]))
        self.assertEqual(journal, ['ecrire_lignes'])
        self.assertEqual(resultat['etapes'],
                         list(pipeline.ETAPES_PAR_MODE[pipeline.MODE_ECRIRE]))
        self.assertIs(resultat['devis'], etapes.verrou)

    def test_mode_rafraichir_n_ecrit_aucune_ligne(self):
        journal = []
        with _Etapes(journal) as etapes:
            resultat = pipeline.appliquer(
                etapes.verrou, _intention(mode=pipeline.MODE_RAFRAICHIR))
        self.assertEqual(journal, ['rafraichir_etudes'])
        self.assertEqual(
            resultat['etapes'],
            list(pipeline.ETAPES_PAR_MODE[pipeline.MODE_RAFRAICHIR]))

    def test_le_mode_par_defaut_est_le_pipeline_complet(self):
        """Une intention qui ne dit rien se comporte comme avant QJR93."""
        self.assertEqual(pipeline.IntentionDevis(
            origine=pipeline.ORIGINE_ECRAN, company=object()).mode,
            pipeline.MODE_COMPOSER)
        self.assertEqual(pipeline.ETAPES_PAR_MODE[pipeline.MODE_COMPOSER],
                         pipeline.ETAPES)

    def test_un_mode_inconnu_est_refuse_en_francais(self):
        journal = []
        with _Etapes(journal):
            with self.assertRaises(ValueError) as leve:
                pipeline.appliquer(_FauxDevis(), _intention(mode='par-magie'))
        self.assertIn('Mode de pipeline inconnu', str(leve.exception))
        self.assertEqual(journal, [])

    def test_les_deux_modes_exigent_un_devis_existant(self):
        """Ils ne créent RIEN : seul le mode complet fait naître un brouillon.

        Sans cette garde, un appelant qui oublie son devis créerait
        silencieusement un second document — le contraire de ce que
        ``replace-lines`` promet."""
        for mode in (pipeline.MODE_ECRIRE, pipeline.MODE_RAFRAICHIR):
            journal = []
            with _Etapes(journal):
                with self.assertRaises(ValueError) as leve:
                    pipeline.appliquer(None, _intention(mode=mode))
            self.assertIn('exige un devis existant', str(leve.exception))
            self.assertEqual(journal, [])


class LesEtudesPartentDeLInstanceRelue(SimpleTestCase):
    """QJR20 — la relecture n'est pas une précaution, c'est l'étape 7."""

    def test_les_etudes_partent_de_l_instance_relue(self):
        vues = []
        ancien = pipeline.rafraichir_etudes_du_devis
        pipeline.rafraichir_etudes_du_devis = (
            lambda devis, force=False: vues.append(
                (devis, devis.relectures, devis._prefetched_objects_cache,
                 force)))
        try:
            verrou = _FauxDevis()
            pipeline.rafraichir_etudes(verrou)
        finally:
            pipeline.rafraichir_etudes_du_devis = ancien

        self.assertEqual(len(vues), 1)
        instance, relectures, cache, force = vues[0]
        self.assertIs(instance, verrou)
        # RELUE avant que la première étude ne parte…
        self.assertEqual(relectures, 1)
        # …et le cache de prefetch de l'appelant VIDÉ (ceinture explicite).
        self.assertEqual(cache, {})
        # QJR94 — sans consigne, c'est l'EMPREINTE qui décide (QJR43/44/47).
        self.assertFalse(force)

    def test_force_est_transmis_aux_quatre(self):
        """QJR94 — ``perform_update`` exigeait ``force=True`` de ses DEUX
        rafraîchisseurs ; il l'exige des QUATRE, et le dial reste un dial."""
        vus = []
        ancien = pipeline.rafraichir_etudes_du_devis
        pipeline.rafraichir_etudes_du_devis = (
            lambda devis, force=False: vus.append(force))
        try:
            pipeline.rafraichir_etudes(_FauxDevis(), force=True)
        finally:
            pipeline.rafraichir_etudes_du_devis = ancien
        self.assertEqual(vus, [True])


class LIntentionDevisEstGelee(SimpleTestCase):
    """Une intention arrêtée ne se retouche pas en cours de pipeline."""

    def test_intention_gelee(self):
        intention = _intention()
        with self.assertRaises(Exception):
            intention.scenario = 'avec'

    def test_cible_gelee(self):
        cible = pipeline.CibleDevis(nb_panneaux=9)
        with self.assertRaises(Exception):
            cible.nb_panneaux = 12

    def test_le_scenario_vide_vaut_les_deux(self):
        """U2 (fondateur 20/08/2026) — le silence veut dire « propose les
        deux », c'est le défaut du devis automatique."""
        self.assertEqual(pipeline._scenario_de(_intention()), 'les_deux')
        self.assertEqual(
            pipeline._scenario_de(_intention(scenario='sans')), 'sans')
        self.assertEqual(
            pipeline._scenario_de(_intention(scenario='n-importe-quoi')),
            'les_deux')

    def test_l_intention_de_composition_recopie_la_cible(self):
        """Pure traduction : aucun choix n'est fait à ce passage."""
        cible = pipeline.CibleDevis(nb_panneaux=12, panel_watt=550, kwc=6.6,
                                    dimensionnement_avec={'nb_panneaux': 16})
        intention = _intention(cible=cible, scenario='les_deux',
                               structure_type='aluminium', mppt_paires=3,
                               phase='monophase', taux_tva=Decimal('14'))
        compo = pipeline.intention_de_composition(intention, cible)

        self.assertEqual(compo.nb_panneaux, 12)
        self.assertEqual(compo.panel_watt, 550)
        self.assertEqual(compo.kwc, 6.6)
        self.assertEqual(compo.scenario, 'les_deux')
        self.assertEqual(compo.structure_type, 'aluminium')
        self.assertEqual(compo.mppt_paires, 3)
        self.assertEqual(compo.phase, 'monophase')
        self.assertEqual(compo.taux_tva, Decimal('14'))
        self.assertEqual(compo.dimensionnement_avec, {'nb_panneaux': 16})


#: QJR93+ (M5) — LE LEDGER DES CHEMINS BASCULÉS, par fichier de production.
#:
#: En M4 cette garde disait « AUCUN chemin n'appelle ``appliquer`` » : la
#: fonction était posée, pas branchée. M5 la branche, une bascule à la fois —
#: et la garde devient le LEDGER de ce qui a été branché. Elle compte les
#: appels PAR FICHIER (jamais par numéro de ligne : un numéro de ligne se périme
#: à la première insertion en amont, et la recaler à la main est exactement le
#: genre de bruit qui finit par masquer un vrai écart).
#:
#: UNE BASCULE DÉCLARE SON CHEMIN ICI, DANS LE MÊME COMMIT QUE SON GOLDEN.
#: Un appel qui apparaît sans cette déclaration est rouge — brancher un chemin
#: sans golden est exactement ce que cette garde interdit, hier comme
#: aujourd'hui.
CHEMINS_BASCULES = {
    # QJR93 — l'écran : ``atomic`` (écrire + rafraîchir) et ``replace-lines``
    # (écrire + rafraîchir). QJR94 — ``perform_update`` (rafraîchir).
    'views/devis.py': 5,
}


class LesCheminsBasculesSontDeclares(SimpleTestCase):
    """M5 — on ne branche un chemin qu'en le DÉCLARANT (avec son golden)."""

    def test_aucun_chemin_de_production_n_appelle_appliquer(self):
        appels = []
        for chemin in sorted(RACINE_VENTES.rglob('*.py')):
            parties = set(chemin.parts)
            if 'tests' in parties or 'migrations' in parties:
                continue
            if chemin.name.startswith(('test_', 'tests_')):
                continue
            if chemin.name == 'pipeline.py':
                continue  # la définition elle-même
            arbre = ast.parse(chemin.read_text(encoding='utf-8'),
                              filename=str(chemin))
            for noeud in ast.walk(arbre):
                if not isinstance(noeud, ast.Call):
                    continue
                cible = noeud.func
                nom = (cible.id if isinstance(cible, ast.Name)
                       else cible.attr if isinstance(cible, ast.Attribute)
                       else '')
                if nom == 'appliquer':
                    appels.append(
                        chemin.relative_to(RACINE_VENTES).as_posix())

        constate = {}
        for fichier in appels:
            constate[fichier] = constate.get(fichier, 0) + 1

        self.assertEqual(
            constate, CHEMINS_BASCULES,
            'le ledger des chemins basculés ne décrit plus le dépôt : '
            'constaté %s, déclaré %s. Une bascule M5 DÉCLARE son chemin dans '
            'CHEMINS_BASCULES, dans le MÊME commit que son test GOLDEN — '
            'brancher un chemin sans golden est exactement ce que cette garde '
            'interdit.' % (constate, CHEMINS_BASCULES))
