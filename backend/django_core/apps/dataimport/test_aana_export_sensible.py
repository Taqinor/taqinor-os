"""AANA14 — aucun champ sensible dans les exports (CSV, XLSX, JSON, ZIP).

Balaye le registre ENTIER : jetons publics, marge et prix d'achat ne sortent
jamais du système, quel que soit le type d'objet exporté.
"""
from django.test import SimpleTestCase

from .export_registry import REGISTRY, SENSITIVE_FIELDS

MOTS_INTERDITS = ('token', 'marge', 'prix_achat')


class ExportSensibleTests(SimpleTestCase):
    def test_aucun_champ_sensible_exporte(self):
        fautes = {
            cle: [c for c in spec.header()
                  if any(m in c for m in MOTS_INTERDITS)]
            for cle, spec in REGISTRY.items()
        }
        fautes = {cle: cols for cle, cols in fautes.items() if cols}
        self.assertEqual(fautes, {})

    def test_les_champs_declares_sensibles_existent_sur_le_modele(self):
        # Garde contre une faute de frappe dans SENSITIVE_FIELDS : un nom qui
        # n'existe pas sur le modèle n'exclurait rien en silence.
        for spec in REGISTRY.values():
            meta = spec.model._meta
            for nom in SENSITIVE_FIELDS.get(
                    (meta.app_label, meta.model_name), set()):
                meta.get_field(nom)
