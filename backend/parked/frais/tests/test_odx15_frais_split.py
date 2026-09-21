"""ODX15 — les notes de frais (FG135/136 + ZACC6/XACC27/XACC28) sont relogées
de ``apps.compta`` vers ``apps.frais`` en STATE-ONLY.

Ce que le test prouve :

* les 5 modèles vivent dans ``apps.frais`` mais gardent leurs tables PHYSIQUES
  ``compta_*`` (le move ne touche aucune donnée) ;
* le shim ``apps.compta.models`` ré-exporte les MÊMES classes (identité) ;
* ``apps.frais.models`` n'importe jamais ``apps.compta`` (FK-string seulement) ;
* les nouvelles routes ``/api/django/frais/…`` ET les anciennes
  ``/api/django/compta/…`` répondent, sur les mêmes données, company-scopées ;
* le CYCLE COMPLET (brouillon → soumise → validée → remboursée) et les
  ÉCRITURES restent identiques, postées par ``apps.compta.services`` : la
  frontière ODX15 (saisie/référentiel chez frais, posting chez compta) tient ;
* le verrou de période FG115 est toujours respecté ;
* les réfs ``NDF-`` sont inchangées.

Run :
    python manage.py test apps.frais.tests.test_odx15_frais_split -v2
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [x['id'] for x in rows]


class TestOdx15Relocation(TestCase):
    def test_models_live_in_frais_with_preserved_db_tables(self):
        from apps.frais.models import (
            BaremeIndemnite, IndemniteChantier, NoteFrais, PlafondNoteFrais,
            RapportNoteFrais,
        )
        attendu = {
            NoteFrais: 'compta_notefrais',
            RapportNoteFrais: 'compta_rapportnotefrais',
            PlafondNoteFrais: 'compta_plafondnotefrais',
            BaremeIndemnite: 'compta_baremeindemnite',
            IndemniteChantier: 'compta_indemnitechantier',
        }
        for model, table in attendu.items():
            self.assertEqual(model._meta.db_table, table)
            self.assertEqual(model._meta.app_label, 'frais')

    def test_shim_compta_reexporte_les_memes_classes(self):
        from apps.compta.models import BaremeIndemnite as ShimBareme
        from apps.compta.models import IndemniteChantier as ShimIndem
        from apps.compta.models import NoteFrais as ShimNote
        from apps.compta.models import PlafondNoteFrais as ShimPlafond
        from apps.compta.models import RapportNoteFrais as ShimRapport
        from apps.frais.models import (
            BaremeIndemnite, IndemniteChantier, NoteFrais, PlafondNoteFrais,
            RapportNoteFrais,
        )
        self.assertIs(ShimNote, NoteFrais)
        self.assertIs(ShimRapport, RapportNoteFrais)
        self.assertIs(ShimPlafond, PlafondNoteFrais)
        self.assertIs(ShimBareme, BaremeIndemnite)
        self.assertIs(ShimIndem, IndemniteChantier)

    def test_frais_models_never_import_compta(self):
        """Le sens du shim va compta → frais, jamais l'inverse : les FK vers la
        compta sont des références STRING ('compta.CompteComptable')."""
        import inspect

        from apps.frais import models as frais_models
        source = inspect.getsource(frais_models)
        self.assertNotIn('from apps.compta', source)
        self.assertNotIn('import apps.compta', source)
        self.assertIn("'compta.CompteComptable'", source)

    def test_migrations_du_move_sont_state_only(self):
        """Aucune opération BASE des deux côtés : ``database_operations`` vide.

        C'est LA garantie du move — sinon des tables seraient créées/droppées
        et les données bougeraient. Vérifié sur les fichiers eux-mêmes, pas sur
        une intention écrite en commentaire.
        """
        from importlib import import_module

        from django.db.migrations.operations.special import (
            SeparateDatabaseAndState,
        )

        chemins = (
            'apps.compta.migrations.0122_odx15_frais_split',
            'apps.frais.migrations.0001_odx15_frais_split',
            # 0002 (ContentType) est volontairement HORS de cette liste : c'est
            # une RunPython idempotente qui ne touche QUE django_content_type.
        )
        for chemin in chemins:
            module = import_module(chemin)
            operations = module.Migration.operations
            self.assertTrue(operations, chemin)
            for operation in operations:
                self.assertIsInstance(operation, SeparateDatabaseAndState,
                                      chemin)
                self.assertEqual(operation.database_operations, [], chemin)
                self.assertTrue(operation.state_operations, chemin)

    def test_migration_frais_depend_du_retrait_dans_compta(self):
        """L'ordre garantit qu'aucun instant n'a deux modèles par table."""
        from importlib import import_module

        module = import_module('apps.frais.migrations.0001_odx15_frais_split')
        self.assertIn(('compta', '0122_odx15_frais_split'),
                      module.Migration.dependencies)

    def test_manifest_du_module(self):
        from django.apps import apps as django_apps

        manifest = django_apps.get_app_config('frais').module_manifest
        self.assertEqual(manifest['key'], 'frais')
        self.assertEqual(manifest['depends'], ['rh', 'compta'])


class TestOdx15Routes(TestCase):
    def setUp(self):
        from apps.compta import services as compta_services

        self.co = make_company('odx15-co', 'ODX15 Co')
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        self.user = make_user(self.co, 'odx15_resp')
        self.employe = make_user(self.co, 'odx15_employe', role='normal')
        self.api = auth(self.user)

    def test_nouvelle_route_frais_cree_avec_company_serveur(self):
        autre = make_company('odx15-autre', 'Autre ODX15')
        resp = self.api.post('/api/django/frais/notes-frais/', {
            'employe': self.employe.id, 'date_frais': '2026-02-10',
            'montant': '320', 'motif': 'Taxi chantier',
            'company': autre.id,  # ignoré : posé côté serveur
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        from apps.frais.models import NoteFrais
        note = NoteFrais.objects.get(pk=resp.data['id'])
        self.assertEqual(note.company_id, self.co.id)
        # Réf NDF- inchangée (references-factory, jamais count()+1).
        self.assertTrue(note.reference.startswith('NDF-'), note.reference)

    def test_ancienne_route_compta_sert_les_memes_donnees(self):
        from apps.frais.models import NoteFrais
        note = NoteFrais.objects.create(
            company=self.co, employe=self.employe, date_frais=date(2026, 2, 11),
            montant=Decimal('120'), motif='Péage')
        legacy = self.api.get('/api/django/compta/notes-frais/')
        neuf = self.api.get('/api/django/frais/notes-frais/')
        self.assertEqual(legacy.status_code, 200, legacy.content)
        self.assertEqual(neuf.status_code, 200, neuf.content)
        self.assertIn(note.id, ids_of(legacy))
        self.assertIn(note.id, ids_of(neuf))

    def test_les_cinq_ressources_repondent_sur_les_deux_prefixes(self):
        for segment in ('notes-frais', 'rapports-notes-frais',
                        'plafonds-notes-frais', 'baremes-indemnite',
                        'indemnites-chantier'):
            for prefixe in ('frais', 'compta'):
                resp = self.api.get(f'/api/django/{prefixe}/{segment}/')
                self.assertEqual(resp.status_code, 200,
                                 f'{prefixe}/{segment} → {resp.status_code}')

    def test_isolation_multi_societe_sur_la_nouvelle_route(self):
        autre = make_company('odx15-b', 'Autre B')
        etranger = make_user(autre, 'odx15_etranger', role='normal')
        from apps.frais.models import NoteFrais
        NoteFrais.objects.create(
            company=autre, employe=etranger, date_frais=date(2026, 2, 12),
            montant=Decimal('99'), motif='Note autre société')
        resp = self.api.get('/api/django/frais/notes-frais/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(ids_of(resp), [])


class TestOdx15CycleEtEcritures(TestCase):
    """Le POSTING reste chez compta : mêmes écritures, mêmes comptes."""

    def setUp(self):
        from apps.compta import services as compta_services
        from apps.compta.models import CompteTresorerie

        self.co = make_company('odx15-cycle', 'ODX15 Cycle')
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        self.services = compta_services
        self.employe = make_user(self.co, 'odx15_cycle_emp', role='normal')
        self.resp = make_user(self.co, 'odx15_cycle_resp')
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE ODX15',
            compte_comptable=compta_services.get_compte(self.co, '5141'))

    def _note(self):
        return self.services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 2, 13),
            montant=Decimal('450'), motif='Carburant', user=self.resp)

    def test_cycle_complet_poste_les_memes_ecritures(self):
        from apps.frais.models import NoteFrais

        note = self._note()
        self.assertEqual(note.statut, NoteFrais.Statut.BROUILLON)
        self.services.soumettre_note_frais(note)
        self.services.valider_note_frais(note, user=self.resp)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.VALIDEE)
        self.assertIsNotNone(note.ecriture_charge_id)
        lignes = list(note.ecriture_charge.lignes.all())
        comptes = {lig.compte.numero for lig in lignes}
        # Débit charge 6143 / crédit personnel créditeur 4432 — inchangé.
        self.assertIn('6143', comptes)
        self.assertIn('4432', comptes)
        self.assertEqual(sum(lig.debit for lig in lignes),
                         sum(lig.credit for lig in lignes))

        self.services.rembourser_note_frais(
            note, compte_tresorerie=self.banque, user=self.resp)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteFrais.Statut.REMBOURSEE)
        self.assertIsNotNone(note.ecriture_remboursement_id)
        comptes_rbt = {lig.compte.numero
                       for lig in note.ecriture_remboursement.lignes.all()}
        self.assertIn('4432', comptes_rbt)
        self.assertIn('5141', comptes_rbt)

    def test_verrou_de_periode_fg115_toujours_respecte(self):
        from apps.compta.models import PeriodeComptable

        PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)
        note = self._note()
        self.services.soumettre_note_frais(note)
        with self.assertRaises(ValidationError):
            self.services.valider_note_frais(note, user=self.resp)

    def test_facade_frais_services_est_celle_de_compta(self):
        """``apps.frais.services`` ne duplique AUCUNE logique comptable."""
        from apps.compta import services as compta_services
        from apps.frais import selectors as frais_selectors
        from apps.frais import services as frais_services

        self.assertIs(frais_services.valider_note_frais,
                      compta_services.valider_note_frais)
        self.assertIs(frais_services.rembourser_note_frais,
                      compta_services.rembourser_note_frais)
        self.assertIs(frais_services.valider_indemnite_chantier,
                      compta_services.valider_indemnite_chantier)
        self.assertIs(
            frais_selectors.indemnites_chantier_remboursables_par_paie,
            __import__('apps.compta.selectors', fromlist=['x'])
            .indemnites_chantier_remboursables_par_paie)
