"""CALX28 — aller-retour HTTP export-layout / import-layout du panneau
Documents.

CE QUI EST PROUVÉ ICI, et ce que ça complète
---------------------------------------------
`test_cal216_import_export.py` (CAL216) prouve DÉJÀ le round-trip au niveau
SERVICE (`services.io_layout.exporter_layout`/`importer_layout` appelés
directement). Ce fichier-ci prouve la MÊME propriété par la PORTE HTTP que
CALX28 branche réellement dans le panneau Documents
(`calepinageApi.calepinages.exporterConception`/`importerConception` ->
`GET .../export-layout/` puis `POST .../import-layout/`) : un aller-retour
export -> import laisse `layout_hash` INCHANGÉ, et un document hors schéma
est refusé en NOMMANT le CHEMIN JSON du premier défaut — exactement ce que
`PanneauDocuments.jsx` affiche sous ses deux boutons.

Needs the ORM (TestCase) — NON EXÉCUTÉ dans cette session (aucune base
disponible sur cet hôte, voir LANE_RULES_CALX.md §3). À lancer avec :
    python manage.py test apps.calepinage.tests.test_calx28_io_layout_aller_retour -v2
"""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage
from apps.crm.models import Client
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

_SCHEMA = (Path(__file__).resolve().parents[1] / 'contract_samples'
           / 'roof_layout_v2.schema.json')
with open(_SCHEMA, encoding='utf-8') as _fichier:
    _DOCUMENT_VALIDE = json.load(_fichier)['exemple']


class AllerRetourHttpTest(TestCase):
    """``export-layout/`` -> ``import-layout/``, par la porte HTTP que
    CALX28 câble réellement (jamais la fonction service appelée à la main)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='IO Layout HTTP Co', slug='io-layout-http-calx28')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='calx28', password='x', company=self.company,
            role=self.role)
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client CALX28')
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.url = ('/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/')

    def test_export_puis_import_laisse_layout_hash_inchange(self):
        # Un document valide est d'abord posé — le bouton « Exporter » du
        # panneau n'a de sens que sur une conception déjà enregistrée.
        premier = self.api.post(self.url + 'import-layout/', _DOCUMENT_VALIDE,
                                format='json')
        self.assertEqual(premier.status_code, 200, premier.data)
        self.calepinage.refresh_from_db()
        premier_hash = self.calepinage.layout_hash
        self.assertTrue(premier_hash)

        # Le bouton « Exporter la conception (JSON) » lit le document TEL QUEL.
        export = self.api.get(self.url + 'export-layout/')
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.data['layout_hash'], premier_hash)
        self.assertEqual(export.data['roof_layout'], _DOCUMENT_VALIDE)

        # Le bouton « Importer une conception » repose EXACTEMENT ce que
        # l'export a rendu (le round-trip du panneau) : l'empreinte ne bouge
        # pas, et le serveur le DIT (`inchange: true`).
        reimport = self.api.post(
            self.url + 'import-layout/', export.data['roof_layout'],
            format='json')
        self.assertEqual(reimport.status_code, 200, reimport.data)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.layout_hash, premier_hash)
        self.assertTrue(reimport.data['inchange'])

    def test_export_sans_conception_rend_roof_layout_none(self):
        # Un calepinage neuf : le bouton « Exporter » ne doit jamais recevoir
        # un objet vide qui se ferait passer pour une conception.
        export = self.api.get(self.url + 'export-layout/')
        self.assertEqual(export.status_code, 200)
        self.assertIsNone(export.data['roof_layout'])

    def test_document_hors_schema_refuse_en_nommant_le_chemin_json(self):
        # `version` doit être un entier (schéma v2) — c'est EXACTEMENT ce que
        # le panneau affiche « ligne par ligne » sous le bouton « Importer ».
        invalide = dict(_DOCUMENT_VALIDE, version='deux')
        reponse = self.api.post(self.url + 'import-layout/', invalide,
                                format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('version', reponse.data)

        # Rien n'est écrasé par un refus : l'empreinte reste celle d'avant.
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.layout_hash or None)
