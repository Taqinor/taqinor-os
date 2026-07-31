"""NTMIG9 — chargement via le connecteur Odoo JSON-2 (gated).

Deux chemins :

* connecteur ABSENT (état réel du dépôt : FG378 n'est pas livré) → no-op
  propre, 400 explicite qui renvoie vers l'import fichier ;
* connecteur PRÉSENT (simulé) → les enregistrements passent par le MÊME
  pipeline que l'import fichier, et le connecteur n'est sollicité qu'en
  LECTURE. Règle #1 : jamais une écriture vers Odoo, encore moins en SQL.
"""
from unittest.mock import patch

from django.test import TestCase

from apps.crm.models import Client
from apps.migration import services
from apps.migration.models import LotMigration, ProjetMigration

from ._base import auth, make_admin, make_company

CSV = (
    b'nom,email,external_id\n'
    b'Gamma SARL,gamma@ex.ma,ODOO-10\n'
)


class FauxClientOdoo:
    """Connecteur JSON-2 simulé : n'expose QUE de la lecture.

    Toute tentative d'écriture est enregistrée pour être assertée à zéro —
    c'est la preuve mécanique de la règle #1.
    """

    def __init__(self):
        self.lectures = []
        self.ecritures = []

    def exporter_entite(self, entite, params):
        self.lectures.append((entite, params))
        return CSV, f'{entite}.csv'

    # Les méthodes d'écriture existent uniquement pour prouver qu'elles ne
    # sont jamais appelées par le service de migration.
    def create(self, *a, **k):  # pragma: no cover - jamais appelé
        self.ecritures.append(('create', a, k))

    def write(self, *a, **k):  # pragma: no cover - jamais appelé
        self.ecritures.append(('write', a, k))

    def unlink(self, *a, **k):  # pragma: no cover - jamais appelé
        self.ecritures.append(('unlink', a, k))

    def execute_sql(self, *a, **k):  # pragma: no cover - jamais appelé
        raise AssertionError('SQL vers Odoo INTERDIT (règle #1).')


class OdooApiGatedTests(TestCase):
    URL = '/api/django/migration/lots-migration/{}/charger-odoo/'

    def setUp(self):
        self.company = make_company('mig-g9-co', 'Migr G9')
        self.admin = make_admin(self.company, 'mig-g9-admin')
        self.projet = ProjetMigration.objects.create(
            company=self.company, nom='Client C', source='odoo')
        self.lot = LotMigration.objects.create(
            company=self.company, projet=self.projet, entite='clients')

    def test_service_no_op_sans_connecteur(self):
        with self.assertRaises(services.ConnecteurNonConfigure):
            services.charger_depuis_odoo_api(self.lot)

    def test_connecteur_absent_du_depot(self):
        """État réel : FG378 n'est pas livré, la fabrique n'existe pas."""
        self.assertIsNone(services._odoo_connector_client(self.company))

    def test_endpoint_400_propose_limport_fichier(self):
        resp = auth(self.admin).post(self.URL.format(self.lot.pk))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('fichier', resp.data['detail'].lower())
        # Rien n'a été créé : un no-op est vraiment un no-op.
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 0)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.EN_ATTENTE)

    def test_connecteur_incomplet_retombe_sur_le_fichier(self):
        class SansExport:
            pass

        with patch.object(services, '_odoo_connector_client',
                          return_value=SansExport()):
            resp = auth(self.admin).post(self.URL.format(self.lot.pk))
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('fichier', resp.data['detail'].lower())

    def test_chemin_connecte_lit_sans_jamais_ecrire_cote_odoo(self):
        faux = FauxClientOdoo()
        with patch.object(services, '_odoo_connector_client',
                          return_value=faux):
            resp = auth(self.admin).post(
                self.URL.format(self.lot.pk), {'limite': 50}, format='json')

        self.assertEqual(resp.status_code, 200, resp.data)
        # Lecture seule : un export demandé, zéro écriture côté Odoo.
        self.assertEqual(len(faux.lectures), 1)
        self.assertEqual(faux.lectures[0][0], 'clients')
        self.assertEqual(faux.ecritures, [])
        # Et les données ont bien traversé le pipeline fichier habituel.
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.statut, LotMigration.Statut.CHARGE)
        self.assertIsNotNone(self.lot.import_job_id)

    def test_chemin_connecte_reste_idempotent(self):
        faux = FauxClientOdoo()
        with patch.object(services, '_odoo_connector_client',
                          return_value=faux):
            services.charger_depuis_odoo_api(self.lot)
            r2 = services.charger_depuis_odoo_api(self.lot)
        self.assertEqual(r2['created'], 0)
        self.assertEqual(r2['updated'], 1)
        self.assertEqual(
            Client.objects.filter(company=self.company).count(), 1)

    def test_lot_reconcilie_refuse_le_chargement_api(self):
        self.lot.statut = LotMigration.Statut.RECONCILIE
        self.lot.save(update_fields=['statut'])
        faux = FauxClientOdoo()
        with patch.object(services, '_odoo_connector_client',
                          return_value=faux):
            with self.assertRaises(services.LotFige):
                services.charger_depuis_odoo_api(self.lot)
        # Le connecteur n'a même pas été sollicité.
        self.assertEqual(faux.lectures, [])

    def test_non_admin_refuse(self):
        from ._base import make_user
        simple = make_user(self.company, 'mig-g9-simple')
        resp = auth(simple).post(self.URL.format(self.lot.pk))
        self.assertEqual(resp.status_code, 403)
