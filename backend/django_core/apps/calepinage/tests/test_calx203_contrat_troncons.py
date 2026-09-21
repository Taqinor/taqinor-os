"""CALX203 — le contrat du métré et de la chute, TRONÇON PAR TRONÇON.

CE QUE CE FICHIER GARDE
-----------------------
Un DOCUMENT, pas un service : `GET calepinages/<pk>/troncons/` n'existe pas
encore (producteur `services/troncons.py`, CALX224-226). Ce qui peut être
affirmé aujourd'hui — et qui compte, puisque l'écran électrique, l'export
tableur et la nomenclature liront cet exemple TEL QUEL — tient en quatre
promesses :

1. **Les trois clés de réponse sont TOUJOURS là** (`troncons`, `totaux`,
   `omissions`), dans les deux états. Leçon PACT10 : un écran qui reçoit
   parfois trois clés et parfois deux finit par tester l'absence de clé au
   lieu de l'absence de données.
2. **Une grandeur non calculable vaut `null`, jamais `0`** — et chaque
   `null` structurant a son entrée dans `omissions[]`, qui NOMME le tronçon,
   le champ et le motif en français.
3. **Les tronçons sont ceux du document** (`electrical.cheminements[]`,
   CALX202) : mêmes identifiants, mêmes extrémités, mêmes origines de
   longueur. Un tronçon publié qui ne serait pas tracé serait une ligne
   inventée.
4. **Le métré par section se recompose depuis les tronçons**, la section
   omise comprise : la fondre dans une autre ligne la ferait disparaître.

Aucune base de données, aucun réseau : deux fichiers JSON.

Run :
    python manage.py test apps.calepinage.tests.test_calx203_contrat_troncons
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


TRONCONS = charger('calepinage_troncons.json')
CHEMINEMENTS = charger('electrique_cheminements.json')

#: Les quatorze champs d'un tronçon — l'ordre est libre, la présence non.
CHAMPS_TRONCON = {
    'id', 'cote', 'de', 'vers', 'longueur_m', 'longueur_origine',
    'nb_conducteurs', 'section_mm2', 'ib_a', 'iz_a', 'chute_pct',
    'chute_cumulee_pct', 'critere_dimensionnant', 'regle_source',
}

#: Les grandeurs qui valent `null` quand elles ne sont pas calculables —
#: jamais `0`, qui se lirait « calculé, et nul ».
GRANDEURS = ('section_mm2', 'ib_a', 'iz_a', 'chute_pct', 'chute_cumulee_pct')

#: Ce lot ne produit ni argent (D-CALX 5) ni énergie (W3).
HORS_SUJET = ('prix', 'marge', 'montant', 'mad', 'tva', 'kwh')


def troncons(etat='exemple'):
    return TRONCONS[etat]['troncons']


class EnveloppeTest(SimpleTestCase):
    """L'échantillon porte l'enveloppe PACT10 et vise la bonne route."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, TRONCONS,
                          f'calepinage_troncons.json : clé « {cle} » absente.')

    def test_l_endpoint_est_lisible_par_la_garde(self):
        """`check_api_shapes` n'accepte que « VERBE /chemin »."""
        verbe, _, route = TRONCONS['endpoint'].partition(' ')
        self.assertEqual(verbe, 'GET')
        self.assertEqual(
            route, '/api/django/calepinage/calepinages/<int:pk>/troncons/',
            'Une seule forme d’URL dans ce module (README des contrats) : '
            'sous-ressource en @action sous calepinages/<pk>/.')

    def test_les_trois_cles_sont_toujours_la(self):
        for etat in ('exemple', 'exemple_vide'):
            # CALX226 a ajouté `verdicts[]` (chute cumulée, un par côté).
            self.assertEqual(sorted(TRONCONS[etat]),
                             ['omissions', 'totaux', 'troncons', 'verdicts'],
                             f'{etat} : les clés de réponse ont bougé.')
            self.assertEqual(sorted(TRONCONS[etat]['totaux']),
                             ['ac_chute_pct', 'dc_chute_pct',
                              'metre_par_section'],
                             f'{etat} : les clés de `totaux` ont bougé.')


class FormeDesTronconsTest(SimpleTestCase):
    """Quatorze champs par tronçon, et une longueur jamais nue."""

    def test_quatorze_champs_par_troncon(self):
        for troncon in troncons():
            self.assertEqual(
                set(troncon), CHAMPS_TRONCON,
                f"tronçon « {troncon.get('id')} » : champs "
                f"{sorted(set(troncon) ^ CHAMPS_TRONCON)} en écart.")

    def test_une_longueur_publie_toujours_son_origine(self):
        """Discipline `Longueur` (services/cables.py) : jamais un nombre nu."""
        for troncon in troncons():
            self.assertIsNotNone(troncon['longueur_m'], troncon['id'])
            self.assertIn(troncon['longueur_origine'],
                          ('plan', 'saisie', 'mixte'),
                          f"tronçon « {troncon['id']} » : origine de longueur "
                          f"absente ou inconnue.")

    def test_les_trois_cotes_et_les_trois_origines_sont_exerces(self):
        self.assertEqual({troncon['cote'] for troncon in troncons()},
                         {'dc', 'ac', 'terre'})
        self.assertEqual({troncon['longueur_origine']
                          for troncon in troncons()},
                         {'plan', 'saisie', 'mixte'})

    def test_une_section_calculee_publie_sa_regle(self):
        for troncon in troncons():
            if troncon['section_mm2'] is not None:
                self.assertTrue(
                    troncon['regle_source'],
                    f"tronçon « {troncon['id']} » : une section publiée sans "
                    f"la référence de sa règle n'est pas remontable.")
                self.assertTrue(troncon['critere_dimensionnant'])


class NullJamaisZeroTest(SimpleTestCase):
    """`0 %` et « non calculable » sont deux états opposés."""

    def test_au_moins_un_troncon_sans_section(self):
        """Le cas réel du lot : la liaison de terre sans norme choisie."""
        omis = [troncon for troncon in troncons()
                if troncon['section_mm2'] is None]
        self.assertTrue(
            omis,
            "L'exemple doit porter au moins un tronçon dont la section est "
            'OMISE : c’est l’état que l’écran doit savoir afficher.')

    def test_un_troncon_sans_section_n_invente_aucune_grandeur(self):
        for troncon in troncons():
            if troncon['section_mm2'] is not None:
                continue
            for champ in GRANDEURS:
                self.assertIsNone(
                    troncon[champ],
                    f"tronçon « {troncon['id']} » : « {champ} » est rempli "
                    f"alors que la section est omise — un chiffre déduit "
                    f"d'une section inconnue est un chiffre inventé.")

    def test_aucune_grandeur_omise_n_est_publiee_a_zero(self):
        for troncon in troncons():
            for champ in GRANDEURS:
                self.assertNotEqual(
                    troncon[champ], 0,
                    f"tronçon « {troncon['id']} » : « {champ} » vaut 0 — une "
                    f"grandeur non mesurée vaut `null` (README des "
                    f"contrats, règle 3).")

    def test_un_calepinage_sans_troncon_n_a_pas_zero_pour_cent(self):
        totaux = TRONCONS['exemple_vide']['totaux']
        self.assertEqual(TRONCONS['exemple_vide']['troncons'], [])
        self.assertIsNone(totaux['dc_chute_pct'])
        self.assertIsNone(totaux['ac_chute_pct'])
        self.assertEqual(totaux['metre_par_section'], [])

    def test_l_etat_vide_dit_pourquoi(self):
        omissions = TRONCONS['exemple_vide']['omissions']
        self.assertTrue(omissions,
                        'Un état vide sans motif est une page blanche : il '
                        'doit NOMMER ce qui manque.')
        for omission in omissions:
            self.assertTrue(omission['champ'])
            self.assertTrue(omission['motif'].strip())


class OmissionsNommeesTest(SimpleTestCase):
    """Chaque omission nomme un tronçon, un champ, et un motif français."""

    def test_forme_des_omissions(self):
        for etat in ('exemple', 'exemple_vide'):
            for omission in TRONCONS[etat]['omissions']:
                self.assertEqual(sorted(omission),
                                 ['champ', 'motif', 'troncon'],
                                 f'{etat} : les clés d’une omission ont bougé.')

    def test_chaque_omission_pointe_un_champ_reellement_nul(self):
        par_id = {troncon['id']: troncon for troncon in troncons()}
        for omission in TRONCONS['exemple']['omissions']:
            troncon = par_id.get(omission['troncon'])
            self.assertIsNotNone(
                troncon,
                f"omission sur « {omission['troncon']} » : ce tronçon n'est "
                f"pas publié.")
            self.assertIn(omission['champ'], CHAMPS_TRONCON)
            self.assertIsNone(
                troncon[omission['champ']],
                f"omission sur « {omission['troncon']}."
                f"{omission['champ']} » : le champ est pourtant rempli.")

    def test_chaque_section_omise_a_son_motif(self):
        motives = {(omission['troncon'], omission['champ'])
                   for omission in TRONCONS['exemple']['omissions']}
        for troncon in troncons():
            if troncon['section_mm2'] is None:
                self.assertIn(
                    (troncon['id'], 'section_mm2'), motives,
                    f"tronçon « {troncon['id']} » : section omise SANS "
                    f"motif — l'écran n'aurait rien à afficher sous le "
                    f"champ.")

    def test_le_motif_nomme_ce_qui_manque(self):
        """D1 : `pays = ma` sans norme choisie fait OMETTRE, en le disant."""
        motifs = ' '.join(omission['motif']
                          for omission in TRONCONS['exemple']['omissions'])
        self.assertIn('norme', motifs.lower())
        self.assertIn('réglages', motifs.lower())


class CoherenceAvecLeDocumentTest(SimpleTestCase):
    """Un tronçon publié est un tracé du plan, jamais une ligne inventée."""

    def setUp(self):
        self.traces = {
            troncon['id']: troncon
            for troncon
            in CHEMINEMENTS['exemple']['electrical']['cheminements']}

    def test_chaque_troncon_correspond_a_un_cheminement(self):
        for troncon in troncons():
            trace = self.traces.get(troncon['id'])
            self.assertIsNotNone(
                trace,
                f"tronçon « {troncon['id']} » : aucun cheminement de ce nom "
                f"dans electrique_cheminements.json (CALX202).")
            for champ, attendu in (('cote', 'cote'), ('de', 'de'),
                                   ('vers', 'vers')):
                self.assertEqual(troncon[champ], trace[attendu],
                                 f"tronçon « {troncon['id']} » : « {champ} » "
                                 f"diverge du document.")
            self.assertEqual(troncon['longueur_origine'], trace['origine'])

    def test_tous_les_cheminements_sont_mesures(self):
        self.assertEqual(sorted(troncon['id'] for troncon in troncons()),
                         sorted(self.traces))


class TotauxTest(SimpleTestCase):
    """Les totaux se recomposent depuis les tronçons."""

    def test_le_metre_par_section_recompose_les_longueurs(self):
        attendu = {}
        for troncon in troncons():
            attendu.setdefault(troncon['section_mm2'], 0.0)
            attendu[troncon['section_mm2']] += troncon['longueur_m']
        publie = {ligne['section_mm2']: ligne['longueur_m']
                  for ligne in TRONCONS['exemple']['totaux']
                  ['metre_par_section']}
        self.assertEqual(sorted(publie, key=lambda s: (s is None, s)),
                         sorted(attendu, key=lambda s: (s is None, s)))
        for section, longueur in attendu.items():
            self.assertAlmostEqual(publie[section], longueur, places=6,
                                   msg=f'métré de la section {section}')

    def test_la_section_omise_garde_sa_ligne_de_metre(self):
        """La fondre dans une autre ligne ferait disparaître la longueur."""
        sections = [ligne['section_mm2'] for ligne
                    in TRONCONS['exemple']['totaux']['metre_par_section']]
        self.assertIn(None, sections)

    def test_la_chute_cumulee_progresse_le_long_de_chaque_cote(self):
        for cote in ('dc', 'ac'):
            cumulees = [troncon['chute_cumulee_pct']
                        for troncon in troncons()
                        if troncon['cote'] == cote]
            self.assertEqual(cumulees, sorted(cumulees),
                             f'côté {cote} : la chute cumulée doit croître '
                             f'le long du chemin.')

    def test_les_totaux_sont_la_chute_cumulee_finale(self):
        for cote, cle in (('dc', 'dc_chute_pct'), ('ac', 'ac_chute_pct')):
            cumulees = [troncon['chute_cumulee_pct']
                        for troncon in troncons()
                        if troncon['cote'] == cote]
            self.assertAlmostEqual(
                TRONCONS['exemple']['totaux'][cle], max(cumulees), places=6,
                msg=f'côté {cote} : le total doit être la chute cumulée '
                    f'en bout de chemin.')


class HorsSujetTest(SimpleTestCase):
    """Ni argent (D-CALX 5) ni énergie (W3) dans un métré."""

    def test_aucune_cle_d_argent_ni_d_energie(self):
        texte = json.dumps(TRONCONS['exemple'], ensure_ascii=False).lower()
        for interdit in HORS_SUJET:
            self.assertNotIn(
                f'"{interdit}', texte,
                f'Le métré publie « {interdit} » : le calepinage ne calcule '
                f'ni argent ni énergie.')
