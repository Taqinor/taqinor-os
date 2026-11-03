"""AMET10 (C-AMET-025) — garde statique de la table PA3 « Devis → signature ».

Sans base ni Django : ``apps/ventes/parcours/PA3.json`` est lue et chaque
référence ``fichier::Symbole`` résolue par AST avec LE résolveur du dépôt
(``core/parcours.py``, METHODE v3 §D.1) — aucune seconde implémentation.

Run :
    python -m unittest apps.ventes.tests.test_parcours_pa3
"""
import ast
import copy
import pathlib
import unittest

from core import parcours

TABLE = pathlib.Path(__file__).resolve().parents[1] / 'parcours' / 'PA3.json'
RACINE = pathlib.Path(__file__).resolve().parents[3]  # backend/django_core
#: fonctions dont chaque appelant (hors tests/management) DOIT être une porte de la table
FONCTIONS_A_PORTES = ('accept_devis', 'mark_devis_sent')
#: appelants de support de test hors de tests/ (pas une porte produit)
SUPPORTS_DE_TEST = ('apps/crm/parcours_suivi_outils.py',)
STATUTS_8221 = ('en_constitution', 'depose', 'en_instruction', 'complement_demande',
                'approuve', 'refuse', 'comptage_pose')


def _references(noeud):
    if isinstance(noeud, dict):
        for valeur in noeud.values():
            yield from _references(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from _references(valeur)
    elif parcours.est_une_reference(noeud):
        yield noeud


def _qualnames_avec_appels(chemin, noms):
    """``{qualname: {nom appelé}}`` pour chaque fonction de ``chemin`` qui appelle l'un de ``noms``."""
    arbre = ast.parse(chemin.read_text(encoding='utf-8'))
    trouve = {}

    def visite(noeud, pile):
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visite(enfant, pile + [enfant.name])
                continue
            if isinstance(enfant, ast.Call):
                f = enfant.func
                nom = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if nom in noms and pile:
                    trouve.setdefault('.'.join(pile), set()).add(nom)
            visite(enfant, pile)

    visite(arbre, [])
    return trouve


def _appelants_reels(nom):
    """Références ``fichier::qualname`` des fonctions hors tests/management qui appellent ``nom``."""
    refs = set()
    for chemin in (RACINE / 'apps').rglob('*.py'):
        rel = chemin.relative_to(RACINE).as_posix()
        morceaux = rel.split('/')
        if ('tests' in morceaux or 'management' in morceaux or 'migrations' in morceaux
                or morceaux[-1].startswith(('test_', 'tests_')) or rel in SUPPORTS_DE_TEST):
            continue
        texte = chemin.read_text(encoding='utf-8')
        if nom not in texte:
            continue
        trouve = _qualnames_avec_appels(chemin, {nom})
        if not trouve:
            continue
        # un relais interne (``_envoi_atomique``) est remplacé par ses propres appelants du fichier
        tous = _qualnames_avec_appels(chemin, {q.rsplit('.', 1)[-1] for q in trouve})
        for qualname in trouve:
            court = qualname.rsplit('.', 1)[-1]
            if court.startswith('_') and not court.startswith('__'):
                refs.update(f'{rel}::{q}' for q, appeles in tous.items() if court in appeles)
            else:
                refs.add(f'{rel}::{qualname}')
    return refs


def _portes_de_la_table(table):
    refs = {p['ref'] for p in table['portes']}
    for etape in parcours.etapes(table):
        refs.update(r for r in etape.get('portes', []) if parcours.est_une_reference(r))
    return refs


def _portes_manquantes(table):
    """Appelants réels d'``accept_devis`` / ``mark_devis_sent`` absents de la table (ADVS41)."""
    refs = _portes_de_la_table(table)
    return sorted(ref for nom in FONCTIONS_A_PORTES for ref in _appelants_reels(nom) if ref not in refs)


class ParcoursPA3Tests(unittest.TestCase):
    def setUp(self):
        self.table = parcours.charger_table(TABLE)

    def test_chaque_etape_est_complete_et_resolue(self):
        self.assertEqual(parcours.problemes_de_la_table(self.table), [])
        self.assertEqual(self.table['id'], 'PA3')
        ids = [etape['id'] for etape in parcours.etapes(self.table)]
        suites = {etape['suite'] for etape in parcours.etapes(self.table)}
        self.assertLessEqual(suites - {'fin'}, set(ids), 'suite vers une étape absente')
        motifs = [f'{ref} — {motif}' for ref in _references(self.table)
                  for ok, motif in [parcours.resoudre_symbole(ref)] if not ok]
        self.assertEqual(motifs, [])

    def test_portes_inventaire_des_appelants_reels(self):
        """ADVS41 — plus aucun compte figé : toute porte d'``accept_devis`` / ``mark_devis_sent``
        trouvée dans le code (AST) figure dans ``portes`` ou dans les ``portes`` d'une étape."""
        self.assertEqual(_portes_manquantes(self.table), [])
        self.assertGreaterEqual(len(_appelants_reels('accept_devis')), 4)
        self.assertGreaterEqual(len(_appelants_reels('mark_devis_sent')), 4)
        types = {p['type'] for p in self.table['portes']}
        self.assertTrue({'acceptation', 'envoi', 'creation', 'avenant'} <= types)
        etapes = parcours.etapes(self.table)
        creation = [e for e in etapes if e['id'] == 'PA3-01'][0]
        self.assertFalse(creation['fonction_entree'].endswith('.composition'),
                         'composition est un dry-run, jamais une entrée de création')
        accept = [e for e in etapes if e['fonction_entree'].endswith('::accept_devis')]
        self.assertGreaterEqual(len(accept), 3)

    def test_une_porte_retiree_de_la_table_fait_echouer_la_garde(self):
        mutant = copy.deepcopy(self.table)
        mutant['portes'] = [p for p in mutant['portes'] if not p['ref'].endswith('.accepter')
                            or 'devis_cycle' not in p['ref']]
        for etape in mutant['etapes']:
            etape['portes'] = [r for r in etape.get('portes', []) if 'DevisCycleActionsMixin.accepter' not in r]
        self.assertTrue(any('DevisCycleActionsMixin.accepter' in m for m in _portes_manquantes(mutant)))

    def test_82_21_et_moteur_qui_ne_fait_que_rendre(self):
        etapes = {e['id']: e for e in parcours.etapes(self.table)}
        for statut in STATUTS_8221:
            self.assertIn(statut, etapes['PA3-09']['provenance']['marqueur'])
        rendu = etapes['PA3-03']
        self.assertIn('quote_engine/', rendu['fonction_entree'])
        self.assertTrue(rendu['checkpoint']['persistance'].startswith('n/a'))

    def test_une_fonction_d_entree_cassee_fait_echouer_la_garde(self):
        mutant = copy.deepcopy(self.table)
        etape = mutant['etapes'][0]
        etape['fonction_entree'] += '_casse'
        erreurs = parcours.problemes_de_la_table(mutant)
        self.assertTrue(any(e.startswith(f"{etape['id']} : fonction_entree") for e in erreurs), erreurs)
