"""ERR-QJR667-GARDE-ACTIONS-SANS-ECRAN — toute ``@action`` de ``DevisViewSet``
a un appelant écran, ou porte un marqueur ``# api-only: <raison>``.

CE QUE LE ROUGE PROUVAIT. QJR667 (décision fondateur 01/10/2026) avait trouvé
des endpoints devis livrés sans aucun bouton (lots NTCPQ18,
ajouter-boq-electrique PV47, dupliquer, renouveler) et demandait une garde
pour que cela ne se reproduise plus ; la garde n'avait jamais été écrite.

LA RÈGLE. Pour chaque ``@action`` de ``DevisViewSet`` (``views/devis.py``),
son ``url_path`` (défaut DRF : le nom de la méthode) doit apparaître sous la
forme ``ventes/devis/[${…}/]<url_path>/`` dans un fichier source de
``frontend/src`` (``api/*.js`` d'abord, mais aussi un écran qui appelle
``api.post`` directement, ex. ``pages/ventes/ToitureDesign.jsx`` pour
``from-layout``/``layout``/``roof-image``) ou de ``apps/web/src`` — sinon le bloc de commentaires collé
au-dessus du décorateur (ou une ligne du décorateur) porte
``# api-only: <raison>`` avec une raison NON vide. Un marqueur posé sur une
action qui A un appelant est refusé aussi (marqueur périmé = mensonge).

Lecture de fichiers seulement (AST + texte) : aucune base.
"""
import ast
import os
import re

from django.test import SimpleTestCase

#: Racine du dépôt — remontée depuis backend/django_core/apps/ventes/tests/.
RACINE = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', '..'))
VUE = os.path.join(RACINE, 'backend', 'django_core', 'apps', 'ventes',
                   'views', 'devis.py')
FRONT_SRC = os.path.join(RACINE, 'frontend', 'src')
WEB_SRC = os.path.join(RACINE, 'apps', 'web', 'src')

MARQUEUR = re.compile(r'#\s*api-only\s*:\s*(\S.*)$')
GROUPE = re.compile(r'\(\?P<\w+>[^)]*\)')


def _nom_decorateur(dec):
    fonc = dec.func if isinstance(dec, ast.Call) else dec
    return getattr(fonc, 'id', None) or getattr(fonc, 'attr', None)


def actions_du_viewset(source):
    """[(nom, url_path, ligne_decorateur, ligne_def)] des @action."""
    arbre = ast.parse(source)
    classe = next(n for n in arbre.body
                  if isinstance(n, ast.ClassDef) and n.name == 'DevisViewSet')
    out = []
    for noeud in classe.body:
        if not isinstance(noeud, ast.FunctionDef):
            continue
        for dec in noeud.decorator_list:
            if _nom_decorateur(dec) != 'action':
                continue
            url_path = noeud.name
            if isinstance(dec, ast.Call):
                for kw in dec.keywords:
                    if kw.arg == 'url_path' and isinstance(
                            kw.value, ast.Constant):
                        url_path = kw.value.value
            out.append((noeud.name, url_path, dec.lineno, noeud.lineno))
    return out


def marqueur_api_only(lignes, ligne_dec, ligne_def):
    """La raison du ``# api-only:`` de l'action, ou ``None``.

    Cherche dans le bloc de commentaires CONTIGU juste au-dessus du
    décorateur, puis dans les lignes du décorateur lui-même."""
    candidates = []
    i = ligne_dec - 2  # index 0-based de la ligne au-dessus du décorateur
    while i >= 0 and lignes[i].strip().startswith('#'):
        candidates.append(lignes[i])
        i -= 1
    candidates.extend(lignes[ligne_dec - 1:ligne_def - 1])
    for ligne in candidates:
        m = MARQUEUR.search(ligne)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return None


def motif_appel(url_path):
    """Regex d'un appel ``ventes/devis/[${…}/]<url_path>/``."""
    morceaux, pos = [], 0
    for m in GROUPE.finditer(url_path):
        morceaux.append(re.escape(url_path[pos:m.start()]))
        morceaux.append(r'\$\{[^}]+\}')
        pos = m.end()
    morceaux.append(re.escape(url_path[pos:]))
    return re.compile(
        r'ventes/devis/(?:\$\{[^}]+\}/)?' + ''.join(morceaux) + r'/')


EXTENSIONS = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.astro')


def textes_appelants():
    """Sources (hors tests) de ``frontend/src`` et ``apps/web/src``."""
    textes = []
    for racine in (FRONT_SRC, WEB_SRC):
        for dossier, _, fichiers in os.walk(racine):
            for nom in sorted(fichiers):
                if (not nom.endswith(EXTENSIONS) or '.test.' in nom
                        or '.spec.' in nom):
                    continue
                with open(os.path.join(dossier, nom),
                          encoding='utf-8') as fh:
                    textes.append(fh.read())
    return textes


class ActionsDevisOntAppelantTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with open(VUE, encoding='utf-8') as fh:
            cls.source = fh.read()
        cls.lignes = cls.source.splitlines()
        cls.actions = actions_du_viewset(cls.source)
        cls.textes = textes_appelants()

    def _a_un_appelant(self, url_path):
        motif = motif_appel(url_path)
        return any(motif.search(t) for t in self.textes)

    def test_les_sources_existent(self):
        self.assertTrue(os.path.isdir(FRONT_SRC), FRONT_SRC)
        self.assertTrue(os.path.isdir(WEB_SRC), WEB_SRC)
        # Garde non vide : le viewset porte des dizaines d'@action.
        self.assertGreater(len(self.actions), 20)

    def test_le_motif_reconnait_un_appel_reel(self):
        self.assertTrue(self._a_un_appelant('generer-pdf'))
        self.assertTrue(self._a_un_appelant(
            r'simulation-status/(?P<token>[0-9a-f]{32})'))
        self.assertFalse(self._a_un_appelant('jamais-appelee-qjr667'))

    def test_toute_action_a_un_appelant_ou_un_marqueur(self):
        orphelines = [
            f'{nom} (url_path={url!r}, views/devis.py:{l_dec})'
            for nom, url, l_dec, l_def in self.actions
            if not self._a_un_appelant(url)
            and marqueur_api_only(self.lignes, l_dec, l_def) is None]
        self.assertEqual(
            orphelines, [],
            'Action(s) DevisViewSet sans appelant dans frontend/src ni '
            'apps/web/src : brancher un écran ou poser '
            '« # api-only: <raison> » au-dessus du décorateur.')

    def test_aucun_marqueur_perime(self):
        perimes = [
            f'{nom} (views/devis.py:{l_dec})'
            for nom, url, l_dec, l_def in self.actions
            if self._a_un_appelant(url)
            and marqueur_api_only(self.lignes, l_dec, l_def) is not None]
        self.assertEqual(perimes, [],
                         'Marqueur « api-only » sur une action appelée : '
                         'le retirer.')
