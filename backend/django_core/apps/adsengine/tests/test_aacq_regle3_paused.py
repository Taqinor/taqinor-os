"""AACQ75 — Garde permanente règle #3 (CLAUDE.md) : toute création Meta naît
PAUSED, sur TOUS les chemins, et aucun autre module ne crée vers Graph.

1. Les méthodes de création de ``MetaClient`` sont ÉNUMÉRÉES par AST (toute
   méthode qui POST vers une arête ``campaigns``/``adsets``/``ads``/``copies``,
   plus celles qui appellent une telle méthode — duplication, boost…) : la
   liste paramétrée ``APPELS`` doit les couvrir TOUTES, sinon la garde échoue
   en français (une méthode ajoutée n'échappe jamais à la garde).
2. Chacune est appelée sur un VRAI ``MetaClient`` (transport httpx simulé à la
   frontière réseau seulement) avec ``status=ACTIVE`` glissé dans chaque
   ``*extra_fields`` : chaque requête de création capturée porte
   ``status=PAUSED``.
3. Aucun module adsengine hors ``meta_client.py`` ne POST de création vers
   Graph (AST).

Complète — sans les remplacer — les tests PAUSED par méthode
(``test_meta_client.py``, ``test_duplication.py``, ``test_object_story_spec.py``,
``test_creation_chain.py``, ``test_pub117_adcreative_write.py``…).
"""
import ast
import inspect
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from django.test import SimpleTestCase

from apps.adsengine import meta_client as mc

APP_DIR = Path(mc.__file__).resolve().parent
ARETES_CREATION = {'campaigns', 'adsets', 'ads', 'copies'}

# Arguments minimaux de chaque méthode de création (hors ``*extra_fields``,
# injectés par le test avec ``status=ACTIVE``).
APPELS = {
    'create_campaign': {'name': 'C', 'objective': 'OUTCOME_LEADS'},
    'create_adset': {'name': 'S', 'campaign_id': '11'},
    'create_ad': {'name': 'A', 'adset_id': '22'},
    'duplicate_adset_with_ad': {
        'campaign_id': '11', 'new_adset_name': 'S2', 'new_ad_name': 'A2',
        'creative_id': '33'},
    'create_ad_with_object_story_spec': {
        'name': 'A', 'adset_id': '22',
        'object_story_spec': {'page_id': 'p1', 'link_data': {'message': 'm'}}},
    'create_ad_with_asset_feed_spec': {
        'name': 'A', 'adset_id': '22',
        'asset_feed_spec': {'bodies': [{'text': 't'}]},
        'object_story_spec': {'page_id': 'p1'}},
    'boost_page_post': {'post_id': 'p1_9', 'adset_id': '22', 'name': 'B'},
}


def _chaines(noeud):
    return [n.value for n in ast.walk(noeud)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _vise_arete_creation(noeud):
    return any(s.strip('/').split('/')[-1] in ARETES_CREATION
               for s in _chaines(noeud))


def methodes_de_creation(source):
    """Méthodes de ``MetaClient`` qui créent (POST direct vers une arête de
    création, ou appel d'une telle méthode), par AST — aucune liste à la main."""
    arbre = ast.parse(source)
    classe = next(n for n in arbre.body
                  if isinstance(n, ast.ClassDef) and n.name == 'MetaClient')
    methodes = {f.name: f for f in classe.body
                if isinstance(f, ast.FunctionDef)}
    creation = set()
    for nom, fonction in methodes.items():
        for n in ast.walk(fonction):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == '_request' and len(n.args) > 1
                    and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == 'POST'
                    and _vise_arete_creation(n.args[1])):
                creation.add(nom)
    change = True
    while change:
        change = False
        for nom, fonction in methodes.items():
            if nom in creation:
                continue
            for n in ast.walk(fonction):
                if (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and isinstance(n.func.value, ast.Name)
                        and n.func.value.id == 'self'
                        and n.func.attr in creation):
                    creation.add(nom)
                    change = True
                    break
    return creation


def _client(capture):
    def handler(request):
        capture.append(request)
        return httpx.Response(200, json={'id': f'id{len(capture)}'})
    return mc.MetaClient(
        access_token='tok', ad_account_id='act_1', page_id='p1',
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=0, backoff_base=0)


class Regle3TousCheminsTests(SimpleTestCase):
    def test_liste_couvre_toutes_les_methodes_de_creation(self):
        source = (APP_DIR / 'meta_client.py').read_text(encoding='utf-8')
        trouvees = methodes_de_creation(source)
        self.assertTrue(trouvees, "Aucune méthode de création trouvée par AST.")
        manquantes = sorted(trouvees - set(APPELS))
        self.assertEqual(
            manquantes, [],
            "Règle #3 : méthode(s) de création Meta non couverte(s) par la "
            f"garde PAUSED : {manquantes} — ajoutez-les à APPELS.")
        disparues = sorted(set(APPELS) - trouvees)
        self.assertEqual(
            disparues, [],
            f"Méthode(s) de APPELS absente(s) de MetaClient : {disparues}.")

    def test_methode_factice_detectee(self):
        # Test-du-test : une méthode qui POST vers /ads sans forcer est vue.
        source = (
            "class MetaClient:\n"
            "    def create_ad_v2(self, *, name):\n"
            "        return self._request('POST', self._account_edge('ads'),"
            " data={'name': name})\n")
        self.assertEqual(methodes_de_creation(source), {'create_ad_v2'})

    def test_chaque_creation_part_paused_malgre_extra_fields_active(self):
        for nom, kwargs in APPELS.items():
            with self.subTest(methode=nom):
                capture = []
                client = _client(capture)
                methode = getattr(client, nom)
                appel = dict(kwargs)
                for param in inspect.signature(methode).parameters:
                    if param.endswith('extra_fields'):
                        appel[param] = {'status': 'ACTIVE'}
                methode(**appel)
                creations = [
                    r for r in capture if r.method == 'POST'
                    and r.url.path.rstrip('/').split('/')[-1]
                    in ARETES_CREATION]
                self.assertTrue(creations, f'{nom} : aucune création capturée.')
                for requete in creations:
                    corps = parse_qs(requete.content.decode('utf-8'))
                    self.assertEqual(corps.get('status'), ['PAUSED'],
                                     f'{nom} → {requete.url.path}')
                    self.assertNotIn('ACTIVE', requete.content.decode('utf-8'))

    def test_aucun_autre_module_ne_cree_vers_graph(self):
        fautifs = []
        for fichier in sorted(APP_DIR.rglob('*.py')):
            relatif = fichier.relative_to(APP_DIR).as_posix()
            if (relatif == 'meta_client.py' or relatif.startswith('tests/')
                    or relatif.startswith('migrations/')
                    or '/tests/' in relatif or relatif.startswith('test')):
                continue
            arbre = ast.parse(fichier.read_text(encoding='utf-8'))
            for n in ast.walk(arbre):
                if not (isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)):
                    continue
                attr = n.func.attr
                est_post = attr == 'post' or (
                    attr in ('request', '_request') and n.args
                    and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == 'POST')
                if attr == '_account_edge' and _vise_arete_creation(n):
                    fautifs.append(f'{relatif}:{n.lineno}')
                elif est_post and any(_vise_arete_creation(a)
                                      for a in n.args[:2]):
                    fautifs.append(f'{relatif}:{n.lineno}')
        self.assertEqual(
            fautifs, [],
            "Règle #3 : création Meta hors de meta_client.py (le seul chemin "
            f"qui force PAUSED) : {fautifs}.")
