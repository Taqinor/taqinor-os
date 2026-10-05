"""SPL302 — golden d'EventType (109 membres) et de son lecteur par chemin.

Capture seule : aucun code de production n'est modifié. Le golden
``golden/types_evenements.json`` (les 109 triplets ``(nom, valeur, libellé)``
dans l'ordre) a été écrit UNE fois, sur le code ACTUEL, par ``capturer()`` ;
le test ne le réécrit JAMAIS. Régénération explicite uniquement :

    python manage.py shell -c "from apps.notifications.tests_spl302_types_evenements_golden import ecrire_golden; ecrire_golden()"

Plancher : le golden doit rester une sous-suite ORDONNÉE de l'énum vivante
(ajout en fin toléré ; jamais retrait, réordonnancement ni renommage).
"""
import ast
import importlib
import json
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

EMPLACEMENT = 'apps.notifications.models'
NOMS = ['EventType']
RACINE_DJANGO = Path(__file__).resolve().parents[2]
GOLDEN_PATH = (
    Path(__file__).resolve().parent / 'golden' / 'types_evenements.json')


def capturer(module=None):
    """Les triplets ``(nom, valeur, libellé)`` de l'énum VIVANTE."""
    m = module or importlib.import_module(EMPLACEMENT)
    return [[x.name, x.value, str(x.label)] for x in m.EventType]


def ecrire_golden():
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(capturer(), ensure_ascii=False, indent=1) + '\n',
        encoding='utf-8')


def charger_golden():
    return json.loads(GOLDEN_PATH.read_text(encoding='utf-8'))


def est_sous_suite(petit, grand):
    """Vrai si ``petit`` est une sous-suite ORDONNÉE de ``grand``."""
    it = iter(grand)
    return all(any(x == y for y in it) for x in petit)


# ── garde d'emplacement (AST, aucune exécution) ──────────────────────────


def _module_de(chemin):
    rel = chemin.relative_to(RACINE_DJANGO).with_suffix('')
    return '.'.join(rel.parts)


def _resoudre(chemin, node):
    """Module absolu visé par un ``ImportFrom`` (relatifs résolus)."""
    if not node.level:
        return node.module or ''
    parties = _module_de(chemin).split('.')[:-1]  # module -> son paquet
    if node.level > 1:
        parties = parties[:len(parties) - (node.level - 1)]
    if node.module:
        parties = parties + node.module.split('.')
    return '.'.join(parties)


def _pointe(noeud):
    """Chemin pointé d'une chaîne ``Name``/``Attribute`` (sinon ``None``)."""
    morceaux = []
    while isinstance(noeud, ast.Attribute):
        morceaux.append(noeud.attr)
        noeud = noeud.value
    if isinstance(noeud, ast.Name):
        morceaux.append(noeud.id)
        return '.'.join(reversed(morceaux))
    return None


def fautifs_emplacement(noms, emplacement, racine=None, exclure=None):
    """Violations de la garde d'emplacement : liste de ``(fichier, détail)``.

    (a) un nom défini au premier niveau (def/classe/affectation) ailleurs que
    dans le fichier de ``emplacement`` ; (b) un nom lu depuis un autre module
    que ``emplacement`` (``from … import NOM``, attribut ``alias.NOM``, ou
    ``import_module('<module>').NOM``). ``exclure(rel)`` écarte des fichiers
    (ex. migrations append-only).
    """
    racine = racine or RACINE_DJANGO
    noms = set(noms)
    fichier_ref = emplacement.replace('.', '/')
    fautifs = []
    for chemin in sorted(racine.rglob('*.py')):
        rel = chemin.relative_to(racine).as_posix()
        if exclure and exclure(rel):
            continue
        try:
            source = chemin.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue
        if not any(n in source for n in noms):
            continue
        try:
            arbre = ast.parse(source)
        except SyntaxError:
            continue
        est_ref = rel in (fichier_ref + '.py', fichier_ref + '/__init__.py')
        for noeud in arbre.body:  # (a) définitions de premier niveau
            cibles = []
            if (isinstance(noeud, (ast.FunctionDef, ast.ClassDef))
                    and noeud.name in noms):
                cibles = [noeud.name]
            elif isinstance(noeud, ast.Assign):
                cibles = [t.id for t in noeud.targets
                          if isinstance(t, ast.Name) and t.id in noms]
            if cibles and not est_ref:
                fautifs.append((rel, f'définit {sorted(cibles)}'))
        noeuds = list(ast.walk(arbre))
        liaisons = {}
        for noeud in noeuds:  # (b) imports
            if isinstance(noeud, ast.ImportFrom):
                cible = _resoudre(chemin, noeud)
                for alias in noeud.names:
                    if alias.name in noms:
                        if cible != emplacement:
                            fautifs.append(
                                (rel, f'importe {alias.name} depuis {cible}'))
                    elif alias.name != '*':
                        liaisons[alias.asname or alias.name] = (
                            f'{cible}.{alias.name}')
            elif isinstance(noeud, ast.Import):
                for alias in noeud.names:
                    liaisons[alias.asname or alias.name] = alias.name
        for noeud in noeuds:  # (b) attributs
            if not (isinstance(noeud, ast.Attribute) and noeud.attr in noms):
                continue
            cible = None
            valeur = noeud.value
            if (isinstance(valeur, ast.Call) and valeur.args
                    and isinstance(valeur.args[0], ast.Constant)
                    and isinstance(valeur.args[0].value, str)
                    and (_pointe(valeur.func) or '').endswith('import_module')):
                cible = valeur.args[0].value
            else:
                pointe = _pointe(valeur)
                if pointe in liaisons:
                    cible = liaisons[pointe]
            if cible is not None and cible != emplacement:
                fautifs.append((rel, f'lit {noeud.attr} via {cible}'))
    return fautifs


def _hors_perimetre(rel):
    """Migrations de notifications (append-only) et models.py lui-même."""
    return (rel.startswith('apps/notifications/migrations/')
            or rel == 'apps/notifications/models.py')


class TypesEvenementsGoldenTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.golden = charger_golden()
        cls.m = importlib.import_module(EMPLACEMENT)

    # (1) plancher ordonné
    def test_109_triplets_plancher(self):
        self.assertEqual(len(self.golden), 109)
        vivant = [[x.name, x.value, str(x.label)] for x in self.m.EventType]
        self.assertTrue(
            est_sous_suite(self.golden, vivant),
            'EventType : membre retiré, réordonné ou renommé',
        )

    # (2) les 3 champs portent l'énum vivante
    def test_champs_choices(self):
        for nom in ('Notification', 'NotificationPreference',
                    'NotificationRoutingRule'):
            champ = getattr(self.m, nom)._meta.get_field('event_type')
            with self.subTest(modele=nom):
                self.assertEqual(list(champ.choices),
                                 list(self.m.EventType.choices))

    # (3) le lecteur par chemin de event_coverage vise le bon fichier
    def test_event_coverage_lit_l_enum(self):
        from core import event_coverage
        declares, _produits = event_coverage.eventtype_coverage()
        self.assertTrue(declares, 'le lecteur par chemin rend {} (vide)')
        manquants = [n for n, _v, _l in self.golden if n not in declares]
        self.assertEqual(manquants, [])
        inconnus = event_coverage.unproduced_eventtypes() - declares
        self.assertEqual(inconnus, set())

    # (4) migrations
    def test_makemigrations_notifications_sans_changement(self):
        try:
            call_command('makemigrations', 'notifications', check=True,
                         dry_run=True, verbosity=0)
        except SystemExit:
            self.fail('makemigrations notifications détecte un changement')

    # (5) garde d'emplacement
    def test_garde_emplacement(self):
        self.assertIs(self.m.EventType,
                      importlib.import_module(EMPLACEMENT).EventType)
        fautifs = fautifs_emplacement(NOMS, EMPLACEMENT,
                                      exclure=_hors_perimetre)
        self.assertEqual(
            fautifs, [],
            'EventType défini/lu hors de %s :\n%s' % (
                EMPLACEMENT,
                '\n'.join(f'  {f} — {d}' for f, d in fautifs)),
        )
