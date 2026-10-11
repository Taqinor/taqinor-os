"""AMET24 — garde statique de la table de parcours PA7 « Monitoring et abonnement ».

La table ``apps/sav/parcours/PA7.json`` décrit le parcours équipement du parc ->
abonnement -> relevés -> sous-performance -> SLA -> crédit -> résiliation. Cette
garde la confronte au CODE par analyse AST, sans base de données :

* chaque ``declencheur.source``, ``fonction_entree``, ``checkpoint.persistance``
  et ``regles_aval[].source`` d'une étape PRÉSENTE désigne un symbole qui existe ;
* chaque étape porte 1 déclencheur, 1 entrée, 1 checkpoint, >= 1 règle aval ;
* une étape déclarée ``manquante`` doit le rester VRAIMENT : sa ``preuve_absence``
  (motif cherché dans le code vivant, hors migrations et tests) ne trouve rien
  hors des fichiers autorisés — sinon l'étape a été câblée et la table est à
  mettre à jour (jamais un trou silencieux, jamais une étape fantôme).

Lancer : ``python -m unittest apps.sav.test_parcours_pa7`` (depuis
``backend/django_core``).
"""
import ast
import json
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]  # backend/django_core
TABLE = json.loads(
    (Path(__file__).resolve().parent / 'parcours' / 'PA7.json')
    .read_text(encoding='utf-8'))

TYPES_DECLENCHEUR = {'signal', 'tache', 'http', 'manuel'}


def _symbole_existe(reference):
    """``chemin.py::Classe.methode`` ou ``chemin.py::fonction`` -> bool (AST)."""
    chemin, _, nom = reference.partition('::')
    fichier = RACINE / chemin
    if not nom or not fichier.is_file():
        return False
    arbre = ast.parse(fichier.read_text(encoding='utf-8'))
    portee = arbre
    for morceau in nom.split('.'):
        trouve = None
        for noeud in getattr(portee, 'body', []):
            if isinstance(noeud, (ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef)) \
                    and noeud.name == morceau:
                trouve = noeud
                break
        if trouve is None:
            return False
        portee = trouve
    return True


def _fichiers_vivants(racine):
    """Fichiers du code vivant sous ``racine`` : hors migrations et tests."""
    for fichier in (RACINE / racine).rglob('*.py'):
        relatif = fichier.relative_to(RACINE).as_posix()
        nom = fichier.name
        if '/migrations/' in relatif or '/tests/' in relatif \
                or nom.startswith(('test_', 'tests')):
            continue
        yield relatif, fichier


def _fichiers_qui_contiennent(motif, racine):
    regex = re.compile(motif)
    return {
        relatif for relatif, fichier in _fichiers_vivants(racine)
        if regex.search(fichier.read_text(encoding='utf-8'))
    }


class ParcoursPA7Tests(unittest.TestCase):

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertTrue(TABLE['etapes'])
        ids = [e['id'] for e in TABLE['etapes']]
        self.assertEqual(len(ids), len(set(ids)), 'identifiants dupliqués')
        for etape in TABLE['etapes']:
            ident = etape['id']
            manquante = etape.get('manquante') is True
            for cle in ('declencheur', 'fonction_entree', 'checkpoint',
                        'regles_aval'):
                self.assertIn(cle, etape, f'{ident} : « {cle} » absent')

            declencheur = etape['declencheur']
            entree = etape['fonction_entree']
            if manquante:
                # Une étape manquante n'a ni déclencheur ni entrée : elle le
                # DIT (`manquant: true`) et la preuve d'absence le démontre.
                self.assertEqual(declencheur, {'manquant': True}, ident)
                self.assertEqual(entree, {'manquant': True}, ident)
            else:
                self.assertIn(declencheur.get('type'), TYPES_DECLENCHEUR,
                              f'{ident} : type de déclencheur')
                self.assertTrue(
                    _symbole_existe(declencheur['source']),
                    f'{ident} : déclencheur introuvable '
                    f'{declencheur["source"]}')
                self.assertTrue(
                    _symbole_existe(entree),
                    f'{ident} : fonction_entree introuvable {entree}')

            persistance = etape['checkpoint']['persistance']
            self.assertTrue(
                _symbole_existe(persistance),
                f'{ident} : checkpoint.persistance introuvable {persistance}')

            regles = etape['regles_aval']
            self.assertGreaterEqual(len(regles), 1, f'{ident} : règle aval')
            for regle in regles:
                self.assertTrue(regle['regle'].strip(), ident)
                self.assertTrue(
                    _symbole_existe(regle['source']),
                    f'{ident} : règle aval introuvable {regle["source"]}')

    def test_les_etapes_manquantes_le_sont_vraiment(self):
        manquantes = [e for e in TABLE['etapes'] if e.get('manquante')]
        # Les coutures sans émetteur/abonné/appelant du constat C-AMET-025 :
        # déclarées, pas devinées. ASAV100 a câblé la création d'abonnement et
        # la résiliation (émetteur vivant) : elles sont désormais PRÉSENTES.
        self.assertEqual(
            {e['id'] for e in manquantes},
            {'sla_disponibilite', 'monitoring_suit_remplacement'})
        for etape in manquantes:
            self.assertTrue(etape['raison'].strip(), etape['id'])
            self.assertTrue(etape['attendu'].strip(), etape['id'])
            self.assertTrue(etape['preuves_absence'], etape['id'])
            for preuve in etape['preuves_absence']:
                trouves = _fichiers_qui_contiennent(
                    preuve['motif'], preuve['racine'])
                self.assertLessEqual(
                    trouves, set(preuve['fichiers_autorises']),
                    f'{etape["id"]} : l\'étape semble câblée '
                    f'({sorted(trouves - set(preuve["fichiers_autorises"]))})'
                    ' — mettre la table PA7 à jour')

    def test_les_etapes_presentes_ne_portent_pas_de_preuve_d_absence(self):
        for etape in TABLE['etapes']:
            if not etape.get('manquante'):
                self.assertNotIn('preuves_absence', etape, etape['id'])


if __name__ == '__main__':
    unittest.main()
