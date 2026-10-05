"""SPL132 — golden des 20 sérialiseurs de facturation (ventes/serializers.py).

Capture AVANT SPL148 : aucun sérialiseur ne bouge ici. Aucune requête, aucune
base : `cls().get_fields()` + AST du source ; aucun symbole mocké. Fige, par
classe :

* `{champ: [classe du champ, read_only, required, source, many]}` ;
* le sha256 de `ast.dump` de la classe (corps non touché par un déplacement).

Régénération (rare, volontaire) : `GOLDEN_CAPTURE=1` réécrit le fixture.
`PLACE` : module attendu après SPL148 (`apps.ventes.serializers_facturation`).
Tant que SPL148 n'a pas eu lieu, `PLACE` est vide et `test_place` est SAUTÉ
(le garder rouge casserait la CI du merge qui porte seulement la capture) ;
SPL148 renseigne `PLACE` et la garde devient active.
"""
import ast
import hashlib
import json
import os
from pathlib import Path

from django.test import SimpleTestCase
from rest_framework.serializers import ListSerializer

from apps.ventes import serializers as ventes_serializers

SERIALISEURS = [
    'BonCommandeSerializer', 'LigneFactureSerializer', 'PaiementSerializer',
    'AffectationPaiementSerializer', 'RetenueSubieSerializer',
    'FactureSerializer', 'FactureWriteSerializer', 'LigneAvoirSerializer',
    'AvoirSerializer', 'LigneNoteDebitSerializer', 'NoteDebitSerializer',
    'PromessePaiementSerializer', 'RelancerFactureSerializer',
    'FollowupLevelSerializer', 'ParametrageRelanceClientSerializer',
    'RelanceLogSerializer', 'FactureActivitySerializer',
    'LigneRemiseEncaissementSerializer', 'RemiseEncaissementSerializer',
    'MandatPaiementSerializer',
]

# Module attendu par classe APRÈS SPL148 ; {} = aucun déplacement effectué.
PLACE = {}
MODULE_CIBLE = 'apps.ventes.serializers_facturation'

FIXTURE = (Path(__file__).parent / 'fixtures'
           / 'golden_serializers_facturation.json')
SERIALIZERS_PY = Path(__file__).resolve().parents[1] / 'serializers.py'


def _empreintes_ast():
    arbre = ast.parse(SERIALIZERS_PY.read_text(encoding='utf-8'))
    return {
        n.name: hashlib.sha256(ast.dump(n).encode('utf-8')).hexdigest()
        for n in arbre.body
        if isinstance(n, ast.ClassDef) and n.name in SERIALISEURS
    }


def _champ(champ):
    many = isinstance(champ, ListSerializer)
    base = champ.child if many else champ
    return [
        type(base).__name__,
        bool(champ.read_only),
        bool(champ.required),
        champ.source,
        many,
    ]


def _capturer():
    empreintes = _empreintes_ast()
    classes = {}
    for nom in SERIALISEURS:
        cls = getattr(ventes_serializers, nom)
        champs = cls().get_fields()
        classes[nom] = {
            'fields': {k: _champ(v) for k, v in champs.items()},
            'ast_sha256': empreintes.get(nom),
        }
    return {'serializers': classes}


class GoldenSerializersFacturationTests(SimpleTestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.capture = _capturer()

    def test_non_vacuite(self):
        self.assertEqual(len(self.capture['serializers']), 20)
        for nom, d in self.capture['serializers'].items():
            self.assertTrue(d['fields'], nom)
            self.assertTrue(d['ast_sha256'],
                            f'{nom} : classe introuvable dans serializers.py')

    def test_golden(self):
        if os.environ.get('GOLDEN_CAPTURE') == '1':
            FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE.write_text(
                json.dumps(self.capture, indent=1, ensure_ascii=False,
                           sort_keys=True) + '\n',
                encoding='utf-8',
            )
        attendu = json.loads(FIXTURE.read_text(encoding='utf-8'))
        courant = json.loads(json.dumps(self.capture, sort_keys=True))
        self.assertEqual(courant, attendu)

    def test_place(self):
        if not PLACE:
            self.skipTest('SPL148 pas encore fait : PLACE vide')
        reel = {nom: getattr(ventes_serializers, nom).__module__
                for nom in SERIALISEURS}
        self.assertEqual(reel, {nom: PLACE.get(nom, MODULE_CIBLE)
                                for nom in SERIALISEURS})
