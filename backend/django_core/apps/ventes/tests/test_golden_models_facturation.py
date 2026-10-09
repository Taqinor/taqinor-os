"""SPL133 — golden des 17 modèles d'argent restés dans `ventes/models.py`.

Capture AVANT tout déplacement (SPL149) : aucun modèle ne bouge ici. Le golden
ne touche JAMAIS la base (introspection `_meta` + AST du source) ; il ne mocke
aucun symbole. Il fige, par modèle :

* `deconstruct()` de chaque champ concret local (chemin, args, kwargs) ;
* `db_table`, `app_label`, `ordering`, noms des index et des contraintes,
  `unique_together`.

Régénération (rare, volontaire) : `GOLDEN_CAPTURE=1` réécrit le fixture.
SPL149 (fin de piste) : les 17 modèles vivent dans
`apps.ventes.models_facturation` (ré-exportés en fin de `models.py`) ;
empreintes AST vérifiées identiques (17/17) au déplacement puis retirées du
fixture. `PLACE` est actif : module attendu + aucun jumeau (aucune
définition restée dans `models.py`).
"""
import ast
import json
import os
from pathlib import Path

from django.apps import apps as django_apps
from django.test import SimpleTestCase

MODELES = [
    'FactureActivity', 'ProformaDocument', 'FactureSource', 'BonCommande',
    'AffectationPaiement', 'NoteDebit', 'LigneNoteDebit', 'RetenueSubie',
    'PromessePaiement', 'ParametrageRelanceClient', 'PaymentLink',
    'RemiseEncaissement', 'LigneRemiseEncaissement', 'MandatPaiement',
    'TentativeDebitMandat', 'LivraisonBC', 'LigneLivraisonBC',
    # AFAC34 — enregistrement d'abandon de créance (golden régénéré).
    'AbandonCreance',
    # AFAC50 — liaison facture d'origine / facture de pénalités.
    'FacturePenalite',
]

MODULE_CIBLE = 'apps.ventes.models_facturation'
# Module attendu par modèle APRÈS SPL149.
PLACE = {nom: MODULE_CIBLE for nom in MODELES}

FIXTURE = Path(__file__).parent / 'fixtures' / 'golden_models_facturation.json'
MODELS_PY = Path(__file__).resolve().parents[1] / 'models.py'


def _norm(valeur):
    """Valeur de `deconstruct()` -> JSON stable."""
    if isinstance(valeur, (str, int, float, bool)) or valeur is None:
        return valeur
    if isinstance(valeur, (list, tuple)):
        return [_norm(v) for v in valeur]
    if isinstance(valeur, (set, frozenset)):
        return sorted(repr(v) for v in valeur)
    if isinstance(valeur, dict):
        return {str(k): _norm(v)
                for k, v in sorted(valeur.items(), key=lambda kv: str(kv[0]))}
    if isinstance(valeur, type):
        return f'{valeur.__module__}.{valeur.__qualname__}'
    if callable(valeur) and hasattr(valeur, '__qualname__'):
        return f'{valeur.__module__}.{valeur.__qualname__}'
    return repr(valeur)


def _capturer():
    modeles = {}
    for nom in MODELES:
        m = django_apps.get_model('ventes', nom)
        meta = m._meta
        modeles[nom] = {
            'app_label': meta.app_label,
            'db_table': meta.db_table,
            'ordering': _norm(list(meta.ordering)),
            'unique_together': _norm([list(t) for t in meta.unique_together]),
            'indexes': sorted(i.name for i in meta.indexes),
            'constraints': sorted(c.name for c in meta.constraints),
            'fields': [
                [f.name, _norm(f.deconstruct()[1:])]
                for f in meta.local_concrete_fields
            ],
        }
    return {'modeles': modeles}


class GoldenModelsFacturationTests(SimpleTestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.capture = _capturer()

    def test_non_vacuite(self):
        self.assertEqual(len(self.capture['modeles']), 19)
        for nom, d in self.capture['modeles'].items():
            self.assertTrue(d['fields'], nom)
            self.assertEqual(d['app_label'], 'ventes', nom)

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

    def test_constantes_importables(self):
        # Importées depuis `apps.ventes.models` par domain/encaissements.py et
        # tests_cad122_signature_domicile.py : doivent le rester.
        from apps.ventes.models import (
            DELAI_RETRACTATION_DOMICILE_JOURS, AcompteAvantDelaiLegal,
        )
        self.assertEqual(DELAI_RETRACTATION_DOMICILE_JOURS, 7)
        self.assertTrue(issubclass(AcompteAvantDelaiLegal, Exception))

    def test_aucun_jumeau_dans_models_py(self):
        # Ré-export autorisé (import), définition interdite : aucune classe
        # des 17 ne doit plus être DÉFINIE dans models.py.
        arbre = ast.parse(MODELS_PY.read_text(encoding='utf-8'))
        restes = [n.name for n in arbre.body
                  if isinstance(n, ast.ClassDef) and n.name in MODELES]
        self.assertEqual(restes, [])

    def test_place(self):
        reel = {nom: django_apps.get_model('ventes', nom).__module__
                for nom in MODELES}
        self.assertEqual(reel, {nom: PLACE.get(nom, MODULE_CIBLE)
                                for nom in MODELES})
