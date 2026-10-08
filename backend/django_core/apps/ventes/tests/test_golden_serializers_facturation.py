"""SPL132 — golden des 20 sérialiseurs de facturation (ventes/serializers.py).

Capture AVANT SPL148 : aucun sérialiseur ne bouge ici. Aucune requête, aucune
base : `cls().get_fields()` + AST du source ; aucun symbole mocké. Fige, par
classe :

* `{champ: [classe du champ, read_only, required, source, many]}`.

SPL148 (fin de piste) : les 20 classes vivent dans
`apps.ventes.serializers_facturation` (sans ré-export) ; empreintes AST
vérifiées identiques (20/20) au moment du déplacement puis retirées du
fixture. `PLACE` est désormais actif : module attendu + aucun jumeau sur
`apps.ventes.serializers`.

Régénération (rare, volontaire) : `GOLDEN_CAPTURE=1` réécrit le fixture.
`PLACE` : module attendu après SPL148 (`apps.ventes.serializers_facturation`).
Tant que SPL148 n'a pas eu lieu, `PLACE` est vide et `test_place` est SAUTÉ
(le garder rouge casserait la CI du merge qui porte seulement la capture) ;
SPL148 renseigne `PLACE` et la garde devient active.
"""
import json
import os
from pathlib import Path

from django.test import SimpleTestCase
from rest_framework.serializers import ListSerializer

from apps.ventes import serializers as ventes_serializers
from apps.ventes import serializers_facturation

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
    # AFAC30 — sérialiseur d'ENTRÉE de `paiement-avec-retenue`.
    'PaiementAvecRetenueEntreeSerializer',
]

MODULE_CIBLE = 'apps.ventes.serializers_facturation'
# Module attendu par classe APRÈS SPL148.
PLACE = {nom: MODULE_CIBLE for nom in SERIALISEURS}

FIXTURE = (Path(__file__).parent / 'fixtures'
           / 'golden_serializers_facturation.json')


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
    classes = {}
    for nom in SERIALISEURS:
        cls = getattr(serializers_facturation, nom)
        champs = cls().get_fields()
        classes[nom] = {
            'fields': {k: _champ(v) for k, v in champs.items()},
        }
    return {'serializers': classes}


class GoldenSerializersFacturationTests(SimpleTestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.capture = _capturer()

    def test_non_vacuite(self):
        self.assertEqual(len(self.capture['serializers']), 21)
        for nom, d in self.capture['serializers'].items():
            self.assertTrue(d['fields'], nom)

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
        reel = {nom: getattr(serializers_facturation, nom).__module__
                for nom in SERIALISEURS}
        self.assertEqual(reel, {nom: PLACE.get(nom, MODULE_CIBLE)
                                for nom in SERIALISEURS})

    def test_aucun_jumeau_dans_serializers(self):
        # Sans ré-export : aucun des 20 noms ne reste sur serializers.py
        # (ni définition, ni import de façade).
        restes = [nom for nom in SERIALISEURS
                  if hasattr(ventes_serializers, nom)]
        self.assertEqual(restes, [])
