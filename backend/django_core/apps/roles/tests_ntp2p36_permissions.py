"""NTP2P36 — catalogue de permissions pour l'approbation d'achats et notes
de frais.

Périmètre de ce lot (lane ``apps/roles`` isolée) : SEUL le catalogue
(``ALL_PERMISSIONS``/``PERMISSION_MODULE``, héritage Directeur/Administrateur)
est posé ici. Le câblage des vérifications 403 sur les actions réelles
(``approuver-etape`` en apps/installations, ``valider-dossier`` en
apps/stock, ``emettre`` — NTP2P15, non construit) est HORS périmètre et
n'est PAS testé ici : ces quatre codes ne sont pour l'instant consommés par
aucun viewset routé (même situation transitoire que les six codes WIR169
avant leur câblage — cf. ``apps/roles/tests_wir169_catalogue_declare.py``).
"""
from django.test import SimpleTestCase

from .models import (
    ADMIN_PERMISSIONS,
    ALL_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
    PERMISSION_MODULE,
)

NTP2P36_CODES = (
    'approuver_demande_achat',
    'approuver_note_frais_direction',
    'valider_dossier_fournisseur',
    'emettre_carte_achat',
)


class Ntp2p36CatalogueTests(SimpleTestCase):
    def test_les_quatre_codes_sont_catalogues(self):
        for code in NTP2P36_CODES:
            self.assertIn(code, ALL_PERMISSIONS, code)

    def test_directeur_et_admin_les_portent_par_heritage(self):
        for code in NTP2P36_CODES:
            self.assertIn(code, DIRECTEUR_PERMISSIONS, code)
            self.assertIn(code, ADMIN_PERMISSIONS, code)

    def test_module_proprietaire_declare(self):
        self.assertEqual(
            PERMISSION_MODULE['approuver_demande_achat'], 'installations')
        self.assertEqual(
            PERMISSION_MODULE['valider_dossier_fournisseur'], 'stock')
        self.assertEqual(
            PERMISSION_MODULE['emettre_carte_achat'], 'stock')
        self.assertEqual(
            PERMISSION_MODULE['approuver_note_frais_direction'], 'frais')

    def test_aucun_doublon_introduit(self):
        self.assertEqual(len(ALL_PERMISSIONS), len(set(ALL_PERMISSIONS)))
