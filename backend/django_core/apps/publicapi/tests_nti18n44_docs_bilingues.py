"""NTI18N44 — documentation de l'API publique consultable en FR ou EN.

CRITÈRE D'ACCEPTATION : un intégrateur peut lire la doc des endpoints
``publicapi`` en anglais SANS PERDRE DE CHAMP. Vérifié par comparaison de
l'arbre EN à l'arbre FR (mêmes clés, mêmes longueurs de listes, mêmes valeurs
non textuelles) sur la référence ET sur le document OpenAPI, plus une
couverture exigeant qu'aucune description d'endpoint, de scope, d'évènement ou
de champ ne reste sans version anglaise.
"""
import json

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from . import docs_i18n
from .constants import EVENT_CHOICES
from .docs import public_api_reference, reference_langue
from .openapi import build_openapi_document, build_openapi_schema
from .portees import SCOPE_CHOICES

GROUPES = ('endpoints_ecriture', 'endpoints_bulk', 'endpoints_lecture_simple',
           'sous_ressources')


def _meme_arbre(testcase, fr, en, chemin='$'):
    """Même structure : mêmes clés, mêmes longueurs, mêmes feuilles non
    textuelles (une feuille textuelle peut différer — c'est la traduction)."""
    if isinstance(fr, dict):
        testcase.assertIsInstance(en, dict, chemin)
        testcase.assertEqual(set(fr), set(en), chemin)
        for cle in fr:
            _meme_arbre(testcase, fr[cle], en[cle], f'{chemin}.{cle}')
    elif isinstance(fr, list):
        testcase.assertIsInstance(en, list, chemin)
        testcase.assertEqual(len(fr), len(en), chemin)
        for i, (a, b) in enumerate(zip(fr, en)):
            _meme_arbre(testcase, a, b, f'{chemin}[{i}]')
    elif isinstance(fr, str):
        testcase.assertIsInstance(en, str, chemin)
    else:
        testcase.assertEqual(fr, en, chemin)


def _entrees(ref):
    toutes = list(ref['endpoints'])
    for groupe in GROUPES:
        toutes.extend(ref[groupe]['liste'])
    return toutes


class Nti18n44ReferenceTests(SimpleTestCase):
    def test_langue_par_defaut_et_inconnue_restent_francaises(self):
        fr = public_api_reference()
        self.assertEqual(fr, reference_langue('fr'))
        self.assertEqual(fr, reference_langue('xx'))
        self.assertEqual(fr, reference_langue(None))
        self.assertTrue(fr['titre'].startswith('API publique'))

    def test_la_reference_anglaise_garde_toute_la_structure(self):
        _meme_arbre(self, reference_langue('fr'), reference_langue('en'))

    def test_les_textes_sont_reellement_traduits(self):
        en = reference_langue('en')
        self.assertEqual(en['titre'], 'Taqinor public API — Reference')
        self.assertTrue(en['introduction'].startswith('REST API'))

    def test_chemins_scopes_et_codes_ne_sont_jamais_traduits(self):
        fr, en = reference_langue('fr'), reference_langue('en')
        for a, b in zip(_entrees(fr), _entrees(en)):
            self.assertEqual(a['chemin'], b['chemin'])
            self.assertEqual(a.get('scope'), b.get('scope'))
            self.assertEqual(a.get('filtres'), b.get('filtres'))
            self.assertEqual(a.get('tri'), b.get('tri'))
        self.assertEqual([s['code'] for s in fr['scopes']],
                         [s['code'] for s in en['scopes']])
        self.assertEqual([e['code'] for e in fr['webhooks']['evenements']],
                         [e['code'] for e in en['webhooks']['evenements']])

    def test_chaque_description_dendpoint_a_sa_version_anglaise(self):
        fr, en = reference_langue('fr'), reference_langue('en')
        for a, b in zip(_entrees(fr), _entrees(en)):
            self.assertIn(a['chemin'], docs_i18n.ENDPOINTS_EN, a['chemin'])
            self.assertNotEqual(a['description'], b['description'], a['chemin'])

    def test_chaque_scope_et_chaque_evenement_a_son_libelle_anglais(self):
        for code, _libelle in SCOPE_CHOICES:
            self.assertIn(code, docs_i18n.SCOPES_EN, code)
        for code, _libelle in EVENT_CHOICES:
            self.assertIn(code, docs_i18n.EVENEMENTS_EN, code)

    def test_chaque_champ_decrit_a_sa_version_anglaise(self):
        fr = reference_langue('fr')
        for entree in fr['sous_ressources']['liste']:
            for champ in entree['champs']:
                self.assertIn((entree['chemin'], champ['nom']),
                              docs_i18n.CHAMPS_EN)
        for charge in fr['webhooks']['charges_utiles']:
            self.assertIn(charge['code'], docs_i18n.CHARGES_UTILES_EN)
            for champ in charge['champs']:
                self.assertIn((charge['code'], champ['nom']),
                              docs_i18n.CHAMPS_EN)

    def test_aucune_traduction_orpheline(self):
        """Une clé de traduction qui ne vise plus rien (endpoint renommé)
        serait une doc EN fantôme : on l'attrape ici."""
        fr = reference_langue('fr')
        chemins = {e['chemin'] for e in _entrees(fr)}
        self.assertEqual(set(docs_i18n.ENDPOINTS_EN) - chemins, set())
        for cle in docs_i18n.TEXTES_EN:
            noeud = fr
            for morceau in cle.split('.'):
                self.assertIn(morceau, noeud, cle)
                noeud = noeud[morceau]
            self.assertIsInstance(noeud, str, cle)


class Nti18n44OpenApiTests(SimpleTestCase):
    def test_le_schema_anglais_garde_tous_les_chemins_et_champs(self):
        _meme_arbre(self, build_openapi_document('fr'), build_openapi_document('en'))

    def test_le_defaut_est_inchange(self):
        self.assertEqual(build_openapi_schema(), build_openapi_document('fr'))
        self.assertEqual(build_openapi_document('xx'), build_openapi_document('fr'))

    def test_plus_aucune_chaine_statique_francaise_en_anglais(self):
        rendu = json.dumps(build_openapi_document('en'), ensure_ascii=False)
        for texte_fr in docs_i18n.OPENAPI_EXACT_EN:
            self.assertNotIn(json.dumps(texte_fr, ensure_ascii=False), rendu)
        self.assertNotIn('(détail)', rendu)
        self.assertNotIn('Champs triables', rendu)

    def test_endpoint_http_lang_en(self):
        client = APIClient()
        en = client.get('/api/public/v1/openapi.json?lang=en')
        self.assertEqual(en.status_code, 200)
        self.assertEqual(en.data['info']['title'], 'Taqinor public API')
        self.assertTrue(en.data['info']['description'].startswith('REST API'))
        fr = client.get('/api/public/v1/openapi.json')
        self.assertEqual(fr.data['info']['title'], 'API publique Taqinor')
        self.assertEqual(set(fr.data['paths']), set(en.data['paths']))
