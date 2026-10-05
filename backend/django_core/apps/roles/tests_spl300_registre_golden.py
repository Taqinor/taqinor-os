"""SPL300 — golden du registre des droits (apps/roles/models.py), AVANT tout déplacement.

Capture seule : aucun code de production n'est modifié. Le golden
``golden/registre_permissions.json`` a été écrit UNE fois, sur le code ACTUEL,
par ``capturer()`` ; le test ne le réécrit JAMAIS. Régénération (à ne faire que
sur décision explicite, jamais pour « faire passer » le test) :

    python manage.py shell -c "from apps.roles.tests_spl300_registre_golden import ecrire_golden; ecrire_golden()"

Les listes sont un PLANCHER : le golden doit rester une sous-suite ORDONNÉE de
la liste vivante (ajout toléré, jamais retrait ni réordonnancement — un
réordonnancement réécrirait les rôles système de chaque société, cf. AUD407).
"""
import ast
import importlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from django.core.management import call_command
from django.test import TestCase

EMPLACEMENT = 'apps.roles.models'

NOMS_41 = [
    'APP_VISIBILITY_PREFIX', 'APP_VISIBILITY_SUFFIX', 'EST_PERMISSION_APP',
    'est_permission_app', 'permission_app', 'cles_apps_autorisees',
    'ALL_PERMISSIONS', 'PERMISSION_MODULE', 'SCOPE_TEAM', 'SCOPE_SUBTREE',
    'ELEVATED_PERMISSIONS',
    'RESPONSABLE_PERMISSIONS', 'UTILISATEUR_PERMISSIONS',
    'DIRECTEUR_PERMISSIONS', 'ADMIN_PERMISSIONS',
    'COMMERCIAL_RESP_PERMISSIONS', 'COMMERCIAL_PERMISSIONS',
    'COMMERCIAL_TERRAIN_PERMISSIONS', 'TECHNICIEN_RESP_PERMISSIONS',
    'TECHNICIEN_PERMISSIONS', 'VIEWER_PERMISSIONS',
    'ADMIN_RH_PERMISSIONS', 'ADMIN_VENTES_PERMISSIONS',
    'ROLE_ADMIN_RH', 'ROLE_ADMIN_VENTES',
    'PERIMETRE_RH', 'PERIMETRE_VENTES', 'PERIMETRE_CHOICES',
    'PERIMETRE_PERMISSIONS', 'SYSTEM_ROLE_PERIMETRES',
    'perimetre_de', 'permissions_hors_perimetre',
    'CANONICAL_DELEGUE_ROLES',
    'PORTAIL_CLIENT_PERMISSIONS', 'PORTAIL_FOURNISSEUR_PERMISSIONS',
    'PORTAIL_PARTENAIRE_PERMISSIONS',
    'ROLE_PORTAIL_CLIENT', 'ROLE_PORTAIL_FOURNISSEUR',
    'ROLE_PORTAIL_PARTENAIRE',
    'CANONICAL_PORTAIL_ROLES', 'CANONICAL_SYSTEM_ROLES',
]

LISTES = [
    'ALL_PERMISSIONS',
    'RESPONSABLE_PERMISSIONS', 'UTILISATEUR_PERMISSIONS',
    'DIRECTEUR_PERMISSIONS', 'ADMIN_PERMISSIONS',
    'COMMERCIAL_RESP_PERMISSIONS', 'COMMERCIAL_PERMISSIONS',
    'COMMERCIAL_TERRAIN_PERMISSIONS', 'TECHNICIEN_RESP_PERMISSIONS',
    'TECHNICIEN_PERMISSIONS', 'VIEWER_PERMISSIONS',
    'ADMIN_RH_PERMISSIONS', 'ADMIN_VENTES_PERMISSIONS',
    'PORTAIL_CLIENT_PERMISSIONS', 'PORTAIL_FOURNISSEUR_PERMISSIONS',
    'PORTAIL_PARTENAIRE_PERMISSIONS',
]
DICTS = ['PERMISSION_MODULE', 'SYSTEM_ROLE_PERIMETRES']
REGISTRES_ROLES = [
    'CANONICAL_SYSTEM_ROLES', 'CANONICAL_PORTAIL_ROLES',
    'CANONICAL_DELEGUE_ROLES',
]
SCALAIRES = [
    'APP_VISIBILITY_PREFIX', 'APP_VISIBILITY_SUFFIX', 'SCOPE_TEAM',
    'SCOPE_SUBTREE', 'ROLE_ADMIN_RH', 'ROLE_ADMIN_VENTES',
    'ROLE_PORTAIL_CLIENT', 'ROLE_PORTAIL_FOURNISSEUR',
    'ROLE_PORTAIL_PARTENAIRE', 'PERIMETRE_RH', 'PERIMETRE_VENTES',
]
FONCTIONS = [
    'est_permission_app', 'permission_app', 'cles_apps_autorisees',
    'permissions_hors_perimetre', 'perimetre_de',
]

GOLDEN_PATH = Path(__file__).resolve().parent / 'golden' / 'registre_permissions.json'
RACINE_DJANGO = Path(__file__).resolve().parents[2]

# Entrées figées des fonctions du registre (le golden en garde les sorties).
ENTREES_EST_PERMISSION_APP = [
    'app_crm_voir', 'app_a_voir', 'crm_voir', '', None, 'app__voir',
    'app_Crm_voir', 'app_crm_voir_x',
]
ENTREES_PERMISSION_APP = ['crm', 'sav', 'devis_x']
ENTREES_CLES_APPS = [
    ['crm_voir'], ['app_crm_voir', 'app_sav_voir', 'crm_voir'], None, [],
    ['app_visites_voir'],
]
ENTREES_HORS_PERIMETRE = [
    ['rh', ['roles_gerer', 'records_scope_equipe', 'app_x_voir', 'crm_voir']],
    ['ventes', ['roles_gerer', 'crm_voir', 'crm_voir']],
    [None, ['roles_gerer']],
    ['inconnu', ['roles_gerer']],
    ['rh', []],
    ['rh', None],
]


def _val(valeur):
    """Valeur sérialisable JSON, déterministe (frozenset -> liste triée)."""
    if isinstance(valeur, (set, frozenset)):
        return sorted(valeur)
    if isinstance(valeur, dict):
        return {k: _val(v) for k, v in valeur.items()}
    if isinstance(valeur, (list, tuple)):
        return [_val(v) for v in valeur]
    return valeur


def capturer(module=None):
    """Construit le golden à partir du registre VIVANT (``module``)."""
    m = module or importlib.import_module(EMPLACEMENT)
    golden = {
        'listes': {n: list(getattr(m, n)) for n in LISTES},
        'dicts': {n: dict(getattr(m, n)) for n in DICTS},
        'registres_roles': {
            n: [[nom, list(perms)] for nom, perms in getattr(m, n)]
            for n in REGISTRES_ROLES
        },
        'elevated': sorted(m.ELEVATED_PERMISSIONS),
        'perimetre_permissions': {
            k: sorted(v) for k, v in m.PERIMETRE_PERMISSIONS.items()
        },
        'perimetre_choices': [list(c) for c in m.PERIMETRE_CHOICES],
        'scalaires': {n: getattr(m, n) for n in SCALAIRES},
        'est_permission_app_pattern': m.EST_PERMISSION_APP.pattern,
        'signatures': {
            n: str(inspect.signature(getattr(m, n))) for n in FONCTIONS
        },
        'comportement': {
            'est_permission_app': [
                [e, m.est_permission_app(e)] for e in ENTREES_EST_PERMISSION_APP
            ],
            'permission_app': [
                [e, m.permission_app(e)] for e in ENTREES_PERMISSION_APP
            ],
            'cles_apps_autorisees': [
                [e, _val(m.cles_apps_autorisees(e))] for e in ENTREES_CLES_APPS
            ],
            'permissions_hors_perimetre': [
                [e, m.permissions_hors_perimetre(e[0], e[1])]
                for e in ENTREES_HORS_PERIMETRE
            ],
        },
    }
    return golden


def ecrire_golden():
    """Écrit le JSON golden (régénération explicite uniquement)."""
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN_PATH.write_text(
        json.dumps(capturer(), ensure_ascii=False, indent=1, sort_keys=False)
        + '\n',
        encoding='utf-8',
    )


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


def fautifs_emplacement(noms, emplacement, racine=None):
    """Violations de la garde d'emplacement : liste de ``(fichier, détail)``.

    (a) un nom défini au premier niveau ailleurs que dans le fichier de
    ``emplacement`` ; (b) un nom lu depuis un autre module que ``emplacement`` :
    ``from … import NOM``, attribut ``alias.NOM`` d'un module importé, ou forme
    chaîne ``import_module('<module>').NOM``.
    """
    racine = racine or RACINE_DJANGO
    noms = set(noms)
    fichier_ref = emplacement.replace('.', '/')
    fautifs = []
    for chemin in sorted(racine.rglob('*.py')):
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
        rel = chemin.relative_to(racine).as_posix()
        est_ref = rel in (fichier_ref + '.py', fichier_ref + '/__init__.py')
        for noeud in arbre.body:  # (a) définitions de premier niveau
            cibles = []
            if isinstance(noeud, ast.FunctionDef) and noeud.name in noms:
                cibles = [noeud.name]
            elif isinstance(noeud, ast.Assign):
                cibles = [t.id for t in noeud.targets
                          if isinstance(t, ast.Name) and t.id in noms]
            elif (isinstance(noeud, ast.AnnAssign)
                  and isinstance(noeud.target, ast.Name)
                  and noeud.target.id in noms):
                cibles = [noeud.target.id]
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


class RegistrePermissionsGoldenTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.golden = charger_golden()
        cls.m = importlib.import_module(EMPLACEMENT)

    # (1) présence des 41 noms
    def test_41_noms_presents(self):
        self.assertEqual(len(NOMS_41), 41)
        manquants = [n for n in NOMS_41 if not hasattr(self.m, n)]
        self.assertEqual(manquants, [])

    # (2) plancher : sous-suites ordonnées, sur les valeurs vivantes
    def test_listes_plancher(self):
        for nom, attendu in self.golden['listes'].items():
            with self.subTest(liste=nom):
                self.assertTrue(
                    est_sous_suite(attendu, list(getattr(self.m, nom))),
                    f'{nom} : retrait ou réordonnancement',
                )

    def test_perimetre_permissions_plancher(self):
        vivant = self.m.PERIMETRE_PERMISSIONS
        for cle, attendu in self.golden['perimetre_permissions'].items():
            with self.subTest(perimetre=cle):
                self.assertIn(cle, vivant)
                self.assertTrue(est_sous_suite(attendu, sorted(vivant[cle])))

    def test_registres_de_roles_plancher(self):
        for nom, attendu in self.golden['registres_roles'].items():
            vivant = [(n, list(p)) for n, p in getattr(self.m, nom)]
            with self.subTest(registre=nom):
                self.assertTrue(
                    est_sous_suite([a[0] for a in attendu],
                                   [v[0] for v in vivant]),
                    f'{nom} : noms de rôles retirés ou réordonnés',
                )
                par_nom = dict(vivant)
                for role, perms in attendu:
                    self.assertTrue(
                        est_sous_suite(perms, par_nom[role]),
                        f'{nom}/{role} : droits retirés ou réordonnés',
                    )

    def test_dictionnaires_plancher(self):
        for nom in DICTS:
            vivant = getattr(self.m, nom)
            with self.subTest(dict=nom):
                for k, v in self.golden['dicts'][nom].items():
                    self.assertIn(k, vivant)
                    self.assertEqual(vivant[k], v)

    def test_elevated_surensemble(self):
        manquants = set(self.golden['elevated']) - set(
            self.m.ELEVATED_PERMISSIONS)
        self.assertEqual(manquants, set())

    def test_scalaires_egaux(self):
        for nom, valeur in self.golden['scalaires'].items():
            with self.subTest(scalaire=nom):
                self.assertEqual(getattr(self.m, nom), valeur)
        self.assertEqual(self.m.EST_PERMISSION_APP.pattern,
                         self.golden['est_permission_app_pattern'])
        self.assertEqual(
            [list(c) for c in self.m.PERIMETRE_CHOICES],
            self.golden['perimetre_choices'],
        )

    # (3) comportement et signatures
    def test_signatures_figees(self):
        for nom, sig in self.golden['signatures'].items():
            with self.subTest(fonction=nom):
                self.assertEqual(str(inspect.signature(getattr(self.m, nom))),
                                 sig)

    def test_comportement_des_fonctions(self):
        comp = self.golden['comportement']
        for e, s in comp['est_permission_app']:
            self.assertEqual(self.m.est_permission_app(e), s, e)
        for e, s in comp['permission_app']:
            self.assertEqual(self.m.permission_app(e), s, e)
        for e, s in comp['cles_apps_autorisees']:
            self.assertEqual(_val(self.m.cles_apps_autorisees(e)), s, e)
        for (perimetre, perms), s in comp['permissions_hors_perimetre']:
            self.assertEqual(
                self.m.permissions_hors_perimetre(perimetre, perms), s,
                (perimetre, perms),
            )

    def test_perimetre_de_sur_vrais_modeles(self):
        from authentication.models import User
        role_rh = self.m.Role(nom='SPL300 rh', perimetre='rh')
        role_global = self.m.Role(nom='SPL300 global')
        self.assertEqual(self.m.perimetre_de(User(role=role_rh)), 'rh')
        self.assertIsNone(self.m.perimetre_de(User(role=role_global)))
        self.assertIsNone(self.m.perimetre_de(User()))  # sans rôle
        self.assertIsNone(self.m.perimetre_de(None))
        self.assertIsNone(self.m.perimetre_de(SimpleNamespace(
            is_authenticated=False, role=role_rh)))

    # (4) modèle et migrations
    def test_choices_du_champ_perimetre(self):
        choix = self.m.Role._meta.get_field('perimetre').choices
        self.assertEqual([list(c) for c in choix],
                         self.golden['perimetre_choices'])

    def test_makemigrations_roles_sans_changement(self):
        try:
            call_command('makemigrations', 'roles', check=True, dry_run=True,
                         verbosity=0)
        except SystemExit:
            self.fail('makemigrations roles détecte un changement de modèle')

    # (5) garde d'emplacement
    def test_garde_emplacement(self):
        fautifs = fautifs_emplacement(NOMS_41, EMPLACEMENT)
        self.assertEqual(
            fautifs, [],
            'noms du registre définis/lus hors de %s :\n%s' % (
                EMPLACEMENT,
                '\n'.join(f'  {f} — {d}' for f, d in fautifs),
            ),
        )
