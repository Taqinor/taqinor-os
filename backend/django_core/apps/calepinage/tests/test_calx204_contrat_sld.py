"""CALX204 — le contrat du schéma unifilaire ÉDITABLE.

CE QUE CE FICHIER GARDE
-----------------------
Le moteur de dessin accepte déjà des positions forcées
(`core/electrique/schema.py::rendre_schema`, `_positions`), mais aucune porte
ne les atteint : la capacité existe sans utilisateur. Ce contrat pose la
forme que l'écran d'édition et la vue liront, et ce test tient ses trois
promesses :

1. **Aucune clé de réponse ne disparaît jamais**, dans aucun état — la
   leçon PACT10 est déjà écrite dans `views/schema.py::CLES_SCHEMA`, ce
   fichier l'étend aux deux clés neuves (`blocs`, `edition`) et vérifie que
   la liste du serveur reste incluse dans celle du contrat.
2. **`edition` n'est pas une seconde source de vérité du dessin.** Tout ce
   que `edition` porte est DÉJÀ appliqué dans `blocs` : un libellé édité est
   le `titre` du bloc, un repère édité est son `repere`, une position forcée
   est son `x`/`y` et met `verrouille` à `true`. Deux surfaces qui se
   contredisent en restant vertes, c'est l'incident du 03/08/2026.
3. **L'édition ne crée aucun organe.** Une `clef` éditée qui n'est pas
   dessinée est un refus qui NOMME la clef.

Aucune base de données, aucun réseau : un fichier JSON et la constante de la
vue.

Run :
    python manage.py test apps.calepinage.tests.test_calx204_contrat_sld
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.views.schema import CLES_SCHEMA

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


SLD = charger('calepinage_sld.json')

#: Les états décrits : le GET, la réponse du POST, et la conception qui ne
#: permet pas de dessiner.
ETATS = ('exemple', 'exemple_apres_edition', 'exemple_vide')

#: Les six clés de la réponse — les quatre de `CLES_SCHEMA` (déjà servies)
#: plus les deux que cette tâche ajoute.
CLES_REPONSE = ['blocs', 'bloquants', 'calepinage', 'edition', 'manquantes',
                'svg']

#: Les sept champs d'un bloc dessiné.
CHAMPS_BLOC = {'clef', 'repere', 'titre', 'sous_titre', 'x', 'y',
               'verrouille'}

#: Un schéma est un document TECHNIQUE : aucun montant n'y a sa place
#: (`core/electrique/schema.py::rendre_schema`, D-CALX 5).
HORS_SUJET = ('prix', 'marge', 'montant', 'mad', 'tva', 'remise')


class EnveloppeTest(SimpleTestCase):
    """L'échantillon porte l'enveloppe PACT10 et vise la route existante."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, SLD,
                          f'calepinage_sld.json : clé « {cle} » absente.')

    def test_l_endpoint_est_la_route_deja_servie(self):
        verbe, _, route = SLD['endpoint'].partition(' ')
        self.assertEqual(verbe, 'GET')
        self.assertEqual(
            route,
            '/api/django/calepinage/calepinages/<int:pk>/schema-unifilaire/')

    def test_le_post_est_decrit_par_son_propre_etat(self):
        """`exemple_apres_edition` EST la réponse du POST."""
        self.assertIn('exemple_apres_edition', SLD)
        self.assertIn('POST', SLD['pourquoi'])


class ClesToujoursPresentesTest(SimpleTestCase):
    """Aucune clé ne disparaît, même quand le dessin ne sort pas."""

    def test_les_six_cles_dans_chaque_etat(self):
        for etat in ETATS:
            self.assertEqual(
                sorted(SLD[etat]), CLES_REPONSE,
                f'{etat} : les clés de réponse ont bougé — un écran qui '
                f'reçoit parfois six clés et parfois cinq finit par tester '
                f"l'absence de clé au lieu de l'absence de données.")

    def test_les_cles_deja_servies_par_la_vue_sont_toutes_la(self):
        """Le contrat ÉTEND `CLES_SCHEMA`, il n'en retire aucune."""
        self.assertEqual(sorted(set(CLES_SCHEMA) - set(CLES_REPONSE)), [],
                         'Le contrat oublie une clé que views/schema.py sert '
                         'déjà.')

    def test_les_trois_cles_d_edition_dans_chaque_etat(self):
        for etat in ETATS:
            self.assertEqual(sorted(SLD[etat]['edition']),
                             ['libelles', 'positions', 'reperes'],
                             f'{etat} : les clés de `edition` ont bougé.')


class FormeDesBlocsTest(SimpleTestCase):
    """Sept champs par bloc, et une clef stable par organe dessiné."""

    def test_sept_champs_par_bloc(self):
        for etat in ETATS:
            for bloc in SLD[etat]['blocs']:
                self.assertEqual(
                    set(bloc), CHAMPS_BLOC,
                    f"{etat} / bloc « {bloc.get('clef')} » : champs "
                    f"{sorted(set(bloc) ^ CHAMPS_BLOC)} en écart.")

    def test_les_clefs_sont_uniques(self):
        for etat in ETATS:
            clefs = [bloc['clef'] for bloc in SLD[etat]['blocs']]
            self.assertEqual(sorted(clefs), sorted(set(clefs)),
                             f'{etat} : deux blocs portent la même clef.')

    def test_un_noeud_de_topologie_n_invente_pas_de_repere(self):
        """`repere` vide = ce bloc ne correspond à aucun organe du bordereau."""
        reperes = {bloc['clef']: bloc['repere']
                   for bloc in SLD['exemple']['blocs']}
        self.assertEqual(reperes['champ'], '')
        self.assertEqual(reperes['onduleur'], '')
        self.assertTrue(reperes['disjoncteur_ac'])


class EditionAppliqueeTest(SimpleTestCase):
    """`edition` n'est jamais une seconde source de vérité du dessin."""

    def _blocs(self, etat):
        return {bloc['clef']: bloc for bloc in SLD[etat]['blocs']}

    def test_chaque_clef_editee_est_un_bloc_dessine(self):
        for etat in ETATS:
            blocs = self._blocs(etat)
            for rubrique in ('libelles', 'reperes', 'positions'):
                for clef in SLD[etat]['edition'][rubrique]:
                    self.assertIn(
                        clef, blocs,
                        f'{etat} / edition.{rubrique} : la clef « {clef} » '
                        f"n'est pas dessinée — l'édition ne crée aucun "
                        f'organe.')

    def test_un_libelle_edite_est_le_titre_du_bloc(self):
        for etat in ETATS:
            blocs = self._blocs(etat)
            for clef, texte in SLD[etat]['edition']['libelles'].items():
                self.assertEqual(blocs[clef]['titre'], texte,
                                 f'{etat} : le titre dessiné de « {clef} » '
                                 f"contredit l'édition.")

    def test_un_repere_edite_est_le_repere_du_bloc(self):
        for etat in ETATS:
            blocs = self._blocs(etat)
            for clef, texte in SLD[etat]['edition']['reperes'].items():
                self.assertEqual(blocs[clef]['repere'], texte,
                                 f'{etat} : le repère dessiné de « {clef} » '
                                 f"contredit l'édition.")

    def test_une_position_forcee_est_celle_du_bloc_et_le_verrouille(self):
        for etat in ETATS:
            blocs = self._blocs(etat)
            for clef, point in SLD[etat]['edition']['positions'].items():
                self.assertEqual(sorted(point), ['x', 'y'])
                self.assertEqual(blocs[clef]['x'], point['x'],
                                 f'{etat} : x de « {clef} ».')
                self.assertEqual(blocs[clef]['y'], point['y'],
                                 f'{etat} : y de « {clef} ».')
                self.assertTrue(
                    blocs[clef]['verrouille'],
                    f'{etat} : « {clef} » est déplacé mais pas verrouillé — '
                    f'le serpentin le recalculerait au prochain rendu.')

    def test_un_bloc_verrouille_a_forcement_une_position_forcee(self):
        """La réciproque : `verrouille` sans édition serait un dessin figé
        sans raison."""
        for etat in ETATS:
            forcees = SLD[etat]['edition']['positions']
            for bloc in SLD[etat]['blocs']:
                if bloc['verrouille']:
                    self.assertIn(bloc['clef'], forcees,
                                  f"{etat} : « {bloc['clef']} » est "
                                  f"verrouillé sans position éditée.")


class BlocDeplaceEtRepereRenommeTest(SimpleTestCase):
    """Ce que l'exemple DOIT montrer (Done de CALX204)."""

    def test_l_exemple_montre_un_bloc_deplace(self):
        self.assertTrue(SLD['exemple']['edition']['positions'],
                        "L'exemple doit montrer au moins un bloc déplacé.")

    def test_l_exemple_montre_un_repere_renomme(self):
        self.assertTrue(SLD['exemple']['edition']['reperes'],
                        "L'exemple doit montrer au moins un repère renommé.")

    def test_le_post_rend_le_document_avec_l_edition_appliquee(self):
        """Le POST ne rend pas `edition` seule : il rend le MÊME document."""
        avant = SLD['exemple']['edition']['positions']
        apres = SLD['exemple_apres_edition']['edition']['positions']
        neuves = set(apres) - set(avant)
        self.assertTrue(
            neuves,
            "`exemple_apres_edition` doit montrer une édition de PLUS que "
            "`exemple`, sinon il ne décrit aucun état nouveau.")
        blocs = {bloc['clef']: bloc
                 for bloc in SLD['exemple_apres_edition']['blocs']}
        for clef in neuves:
            self.assertEqual(blocs[clef]['x'], apres[clef]['x'])
            self.assertEqual(blocs[clef]['y'], apres[clef]['y'])
            self.assertTrue(blocs[clef]['verrouille'])

    def test_le_post_ne_perd_aucun_bloc(self):
        self.assertEqual(
            sorted(bloc['clef'] for bloc in SLD['exemple']['blocs']),
            sorted(bloc['clef']
                   for bloc in SLD['exemple_apres_edition']['blocs']),
            "Une édition déplace un organe, elle n'en supprime aucun.")


class PasDeDessinApproximatifTest(SimpleTestCase):
    """Fiche incomplète ⇒ aucun schéma, et la réponse DIT pourquoi."""

    def test_svg_absent_vaut_null_jamais_une_chaine_vide(self):
        vide = SLD['exemple_vide']
        self.assertIsNone(vide['svg'],
                          "Une chaîne vide se lirait « dessin sans organe » ; "
                          "`null` dit « pas de dessin ».")

    def test_sans_dessin_aucun_bloc_n_est_publie(self):
        self.assertEqual(SLD['exemple_vide']['blocs'], [])
        self.assertEqual(SLD['exemple_vide']['edition'],
                         {'libelles': {}, 'reperes': {}, 'positions': {}})

    def test_sans_dessin_la_reponse_nomme_ce_qui_manque(self):
        vide = SLD['exemple_vide']
        self.assertTrue(
            vide['manquantes'] or vide['bloquants'],
            "Un schéma absent sans motif est une page blanche : la réponse "
            'doit NOMMER la fiche ou le champ en cause.')
        for libelle in vide['manquantes']:
            self.assertIn(' : ', libelle,
                          'Chaque libellé nomme le champ fautif, puis dit '
                          'pourquoi.')

    def test_un_dessin_publie_porte_des_blocs(self):
        for etat in ('exemple', 'exemple_apres_edition'):
            self.assertTrue(SLD[etat]['svg'])
            self.assertTrue(SLD[etat]['blocs'])

    def test_le_refus_d_une_clef_inconnue_nomme_la_clef(self):
        for champ, message in SLD['refus_clef_inconnue'].items():
            self.assertTrue(champ.startswith('edition.'))
            self.assertIn(champ.rsplit('.', 1)[-1], message,
                          'Le message doit NOMMER la clef fautive.')


class AucunMontantTest(SimpleTestCase):
    """Le schéma est un document technique (D-CALX 5)."""

    def test_aucun_mot_d_argent_dans_les_etats_publies(self):
        for etat in ETATS:
            texte = json.dumps(SLD[etat], ensure_ascii=False).lower()
            for interdit in HORS_SUJET:
                self.assertNotIn(
                    interdit, texte,
                    f'{etat} : le schéma publie « {interdit} » — aucun '
                    f"montant n'a sa place sur une planche technique.")
