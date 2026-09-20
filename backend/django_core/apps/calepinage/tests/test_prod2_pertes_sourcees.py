"""CAL139 — les pertes du module : explicites, sourcées, additionnées UNE fois.

Trois garanties sont vérifiées ici :

1. **Aucune perte sans source AFFICHÉE** — un poste sans source est publié
   comme non sourcé (il ne disparaît pas, et il n'hérite d'aucune valeur).
2. **La valeur ``loss`` envoyée à PVGIS est EXACTEMENT la somme publiée** —
   test croisé avec le client CAL135, en relisant l'URL réellement construite.
3. **Aucun 14 % ni 20 % caché ne subsiste dans le module** — test de SURFACE
   sur les sources du paquet ``apps/calepinage``.

Tests PURS : aucune base, aucun réseau (le transport PVGIS est injecté).
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import unittest
import urllib.parse

from apps.calepinage.services.pertes import (
    CATALOGUE, CATALOGUE_PAR_POSTE, PertesInvalides, moyenne_mensuelle,
    politique_du_calepinage, postes_du_calepinage, valider_postes,
)
from apps.calepinage.services.pvgis_serie import (
    _Cache, ClientPvgis,
)

RACINE_MODULE = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = pathlib.Path(__file__).resolve().parent / 'fixtures_pvgis'


class FauxCalepinage:
    """Un double MINIMAL : ce service ne lit que ``pertes`` (et écrit dessus)."""

    def __init__(self, pertes=None):
        self.pk = 1
        self.pertes = pertes
        self.enregistrements = []

    def save(self, *args, **kwargs):
        self.enregistrements.append(kwargs.get('update_fields'))


class CatalogueTest(unittest.TestCase):

    def test_le_catalogue_ne_porte_aucune_valeur(self):
        """Un catalogue qui porterait des valeurs serait le forfait d'avant."""
        for entree in CATALOGUE:
            self.assertEqual(
                set(entree), {'poste', 'libelle', 'reference', 'mensuel'},
                entree['poste'])
            self.assertIsInstance(entree['mensuel'], bool)
            self.assertTrue(entree['reference'])

    def test_les_postes_pvsyst_et_la_ligne_nocturne_sont_la(self):
        attendus = {
            'iam', 'salissure', 'irradiance', 'thermique', 'lid',
            'qualite_module', 'mismatch', 'vieillissement', 'ohmique_dc',
            'ohmique_ac', 'transformateur', 'auxiliaires', 'indisponibilite',
            # La ligne que CAL139 ajoute à la liste PVsyst.
            'auxiliaires_nocturnes',
        }
        self.assertTrue(attendus.issubset(set(CATALOGUE_PAR_POSTE)))

    def test_la_salissure_est_le_poste_mensuel(self):
        self.assertTrue(CATALOGUE_PAR_POSTE['salissure']['mensuel'])
        self.assertFalse(CATALOGUE_PAR_POSTE['thermique']['mensuel'])


class ValidationTest(unittest.TestCase):

    def test_un_poste_sans_source_est_publie_non_source(self):
        postes = valider_postes([{'poste': 'mismatch', 'pct': 2.0}])
        self.assertEqual(len(postes), 1)
        self.assertIsNone(postes[0]['source'])
        # Le libellé et la référence du catalogue complètent l'affichage sans
        # inventer la moindre VALEUR.
        self.assertEqual(postes[0]['libelle'], 'Dispersion (mismatch)')
        self.assertIn('PVsyst', postes[0]['reference'])

    def test_un_poste_hors_catalogue_reste_admis(self):
        postes = valider_postes(
            [{'poste': 'perte_maison', 'pct': 1.0, 'source': 'mesure'}])
        self.assertEqual(postes[0]['libelle'], '')
        self.assertEqual(postes[0]['source'], 'mesure')

    def test_une_source_inconnue_est_refusee_en_nommant_le_poste(self):
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'soiling', 'pct': 2, 'source': 'ouï'}])
        self.assertEqual(refus.exception.champ, 'soiling')
        self.assertIn('soiling', str(refus.exception))

    def test_un_poste_sans_valeur_est_refuse_en_le_nommant(self):
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'thermique', 'source': 'fiche'}])
        self.assertEqual(refus.exception.champ, 'thermique')

    def test_un_doublon_de_poste_est_refuse(self):
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'iam', 'pct': 1.0},
                            {'poste': 'iam', 'pct': 1.0}])
        self.assertIn('deux fois', str(refus.exception))

    def test_la_salissure_mensuelle_donne_la_moyenne_des_douze_mois(self):
        mois = [1.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 6.0, 4.0, 2.0, 1.0, 1.0]
        postes = valider_postes([
            {'poste': 'salissure', 'mensuel': mois, 'source': 'societe'}])
        self.assertAlmostEqual(postes[0]['pct'], sum(mois) / 12.0, places=9)
        self.assertEqual(postes[0]['mensuel'], mois)

    def test_onze_mois_sont_refuses(self):
        with self.assertRaises(PertesInvalides) as refus:
            moyenne_mensuelle([1.0] * 11, champ='salissure')
        self.assertEqual(refus.exception.champ, 'salissure.mensuel')

    def test_un_mois_illisible_nomme_le_mois(self):
        mois = [1.0] * 12
        mois[7] = 'beaucoup'
        with self.assertRaises(PertesInvalides) as refus:
            valider_postes([{'poste': 'salissure', 'mensuel': mois}])
        self.assertIn('août', str(refus.exception))


class PolitiqueDuCalepinageTest(unittest.TestCase):

    def test_sans_poste_aucune_politique_donc_aucune_simulation(self):
        with self.assertRaises(PertesInvalides) as refus:
            politique_du_calepinage(FauxCalepinage([]))
        self.assertEqual(refus.exception.champ, 'pertes')

    def test_aucun_poste_n_est_ajoute_d_office(self):
        cal = FauxCalepinage([{'poste': 'onduleur', 'pct': 2.5,
                               'source': 'fiche'}])
        self.assertEqual([p['poste'] for p in postes_du_calepinage(cal)],
                         ['onduleur'])

    def test_la_somme_publiee_est_celle_des_postes(self):
        cal = FauxCalepinage([
            {'poste': 'onduleur', 'pct': 2.5, 'source': 'fiche'},
            {'poste': 'ohmique_dc', 'pct': 1.25, 'source': 'saisie'},
            {'poste': 'salissure', 'mensuel': [3.0] * 12,
             'source': 'societe'},
        ])
        politique = politique_du_calepinage(cal)
        self.assertAlmostEqual(politique.total_pct, 6.75, places=6)
        self.assertEqual(len(politique.publication()['pertes']), 3)


class LossEnvoyeeAPvgisTest(unittest.TestCase):
    """CAL139 × CAL135/CAL238 — la perte PARTIE est la perte PUBLIÉE."""

    def setUp(self):
        self.charge = json.loads(
            (FIXTURES / 'seriescalc_casablanca_sud.json')
            .read_text(encoding='utf-8'))
        self.urls = []

    def transport(self, url, timeout_s):
        self.urls.append(url)
        return 200, json.dumps(self.charge)

    def test_la_valeur_loss_de_l_url_est_la_somme_publiee(self):
        cal = FauxCalepinage([
            {'poste': 'thermique', 'pct': 7.4, 'source': 'fiche'},
            {'poste': 'salissure', 'mensuel': [2.0, 2.0, 3.0, 4.0, 5.0, 6.0,
                                               6.0, 6.0, 4.0, 3.0, 2.0, 2.0],
             'source': 'societe'},
            {'poste': 'onduleur', 'pct': 2.5, 'source': 'fiche'},
        ])
        politique = politique_du_calepinage(cal)
        client = ClientPvgis(self.transport, cache=_Cache(),
                             dormir=lambda _s: None)
        resultat = client.serie_horaire(
            lat=33.5731, lon=-7.5898, inclinaison_deg=15.0, aspect_deg=0.0,
            politique=politique, annee_debut=2020, annee_fin=2020)

        requete = urllib.parse.parse_qs(
            urllib.parse.urlparse(self.urls[0]).query)
        loss_partie = requete['loss'][0]
        self.assertEqual(loss_partie, politique.valeur_loss)
        self.assertEqual(float(loss_partie), resultat['loss_passee_pct'])
        somme = sum(poste['pct'] for poste in resultat['pertes'])
        self.assertAlmostEqual(float(loss_partie), somme, places=3)

    def test_chaque_poste_republie_porte_sa_source(self):
        cal = FauxCalepinage([
            {'poste': 'thermique', 'pct': 7.4, 'source': 'fiche'},
            {'poste': 'mismatch', 'pct': 2.0},
        ])
        politique = politique_du_calepinage(cal)
        client = ClientPvgis(self.transport, cache=_Cache(),
                             dormir=lambda _s: None)
        resultat = client.serie_horaire(
            lat=33.5731, lon=-7.5898, inclinaison_deg=15.0, aspect_deg=0.0,
            politique=politique, annee_debut=2020, annee_fin=2020)
        sources = {p['poste']: p['source'] for p in resultat['pertes']}
        self.assertEqual(sources['thermique'], 'fiche')
        self.assertIsNone(sources['mismatch'])
        self.assertEqual(resultat['pertes_non_sourcees'], ['mismatch'])


class SurfaceAucunForfaitCacheTest(unittest.TestCase):
    """CAL139 — ni 14 %, ni 20 %, ni aucun forfait de perte dans le module."""

    #: Les deux noms du site public sont INTERDITS de séjour ici (déjà refusés
    #: par CAL238) ; on y ajoute les constantes de l'écran devis.
    NOMS_INTERDITS = ('SYSTEM_LOSS_TOTAL', 'PVGIS_BUILTIN_LOSS',
                      'DEFAULT_LOSS_FACTORS', 'PERTE_SYSTEME')

    #: Un NOM de constante de perte. Une constante nommée ainsi et affectée à
    #: un nombre EN DUR est exactement ce que CAL139 supprime. On refuse par
    #: MOTIF de nom, pas par liste de valeurs : un 0,14 dans un tout autre
    #: calcul (un coefficient géométrique, par exemple) est légitime.
    NOM_DE_PERTE = re.compile(r'(PERTE|LOSS|SALISSURE|SOILING)')

    def fichiers(self):
        for chemin in RACINE_MODULE.rglob('*.py'):
            if 'tests' in chemin.parts or 'migrations' in chemin.parts:
                continue
            yield chemin

    def test_aucune_constante_de_perte_en_dur(self):
        """La surface est lue par l'AST — un NOM cité en prose n'est pas un
        forfait ; seul un identifiant réellement employé en est un."""
        fautifs = []
        for chemin in self.fichiers():
            arbre = ast.parse(chemin.read_text(encoding='utf-8'),
                              filename=str(chemin))
            identifiants = set()
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Name):
                    identifiants.add(noeud.id)
                elif isinstance(noeud, ast.Attribute):
                    identifiants.add(noeud.attr)
                elif isinstance(noeud, ast.alias):
                    identifiants.add(noeud.name.split('.')[-1])
                    if noeud.asname:
                        identifiants.add(noeud.asname)
                elif isinstance(noeud, ast.Assign):
                    for cible in noeud.targets:
                        if (isinstance(cible, ast.Name)
                                and cible.id.isupper()
                                and self.NOM_DE_PERTE.search(cible.id)
                                and isinstance(noeud.value, ast.Constant)
                                and isinstance(noeud.value.value,
                                               (int, float))):
                            fautifs.append(
                                f'{chemin.name} : {cible.id} = '
                                f'{noeud.value.value}')
            for nom in self.NOMS_INTERDITS:
                if nom in identifiants:
                    fautifs.append(f'{chemin.name} : {nom}')
        self.assertEqual(fautifs, [], '; '.join(fautifs))

    def test_le_module_ne_fabrique_aucune_politique_par_defaut(self):
        """Le SEUL chemin vers ``loss`` est la liste persistée du calepinage."""
        cal = FauxCalepinage(None)
        self.assertEqual(postes_du_calepinage(cal), [])
        with self.assertRaises(PertesInvalides):
            politique_du_calepinage(cal)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
