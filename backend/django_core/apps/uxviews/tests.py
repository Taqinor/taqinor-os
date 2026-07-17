"""NTUX1/2 — Tests de l'app `apps.uxviews` (fondation SavedView).

Couvre : société+owner posés côté serveur (jamais du corps), isolation
multi-société, visibilité PERSONNELLE (owner uniquement) vs EQUIPE (toute la
société), garde-fou `definir-par-defaut-role` (Directeur/Admin uniquement, un
seul défaut actif par rôle+écran), garde-fous de suppression.
"""
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role

from .models import SavedView

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role_legacy)


def make_role(company, nom='Commercial'):
    return Role.objects.create(company=company, nom=nom, permissions=[])


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class SavedViewApiTests(TestCase):
    BASE = '/api/django/uxviews/saved-views/'

    def setUp(self):
        self.co_a = make_company('uxv-a', 'A')
        self.co_b = make_company('uxv-b', 'B')
        self.directeur = make_user(self.co_a, 'uxv-directeur', role_legacy='responsable')
        self.commercial1 = make_user(self.co_a, 'uxv-com1', role_legacy='normal')
        self.commercial2 = make_user(self.co_a, 'uxv-com2', role_legacy='normal')
        self.other_co_user = make_user(self.co_b, 'uxv-b-user', role_legacy='normal')
        self.role_commercial = make_role(self.co_a, 'Commercial')

    def _payload(self, **kw):
        base = {'ecran': 'crm.leads', 'nom': 'Mes leads chauds', 'configuration': {'filtres': {}}}
        base.update(kw)
        return base

    # ── Création : société + propriétaire côté serveur ─────────────────────
    def test_create_forces_company_and_owner_server_side(self):
        resp = auth(self.commercial1).post(self.BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = SavedView.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co_a)
        self.assertEqual(obj.owner, self.commercial1)
        self.assertFalse(obj.est_defaut_role)

    def test_create_ignores_owner_and_company_in_body(self):
        payload = self._payload(owner=self.commercial2.id, company=self.co_b.id)
        resp = auth(self.commercial1).post(self.BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = SavedView.objects.get(id=resp.data['id'])
        self.assertEqual(obj.owner, self.commercial1)
        self.assertEqual(obj.company, self.co_a)

    # ── Visibilité : personnelle vs équipe, isolation multi-société ────────
    def test_personal_view_hidden_from_other_users(self):
        SavedView.objects.create(
            company=self.co_a, owner=self.commercial1, ecran='crm.leads', nom='Perso',
            visibilite=SavedView.Visibilite.PERSONNELLE,
        )
        resp = auth(self.commercial2).get(self.BASE, {'ecran': 'crm.leads'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(rows(resp)), 0)

    def test_team_view_visible_to_company_but_not_other_company(self):
        SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='Équipe',
            visibilite=SavedView.Visibilite.EQUIPE,
        )
        resp_same_co = auth(self.commercial1).get(self.BASE, {'ecran': 'crm.leads'})
        self.assertEqual(len(rows(resp_same_co)), 1)
        resp_other_co = auth(self.other_co_user).get(self.BASE, {'ecran': 'crm.leads'})
        self.assertEqual(len(rows(resp_other_co)), 0)

    def test_ecran_filter(self):
        SavedView.objects.create(
            company=self.co_a, owner=self.commercial1, ecran='crm.leads', nom='A')
        SavedView.objects.create(
            company=self.co_a, owner=self.commercial1, ecran='ventes.devis', nom='B')
        resp = auth(self.commercial1).get(self.BASE, {'ecran': 'ventes.devis'})
        self.assertEqual(len(rows(resp)), 1)
        self.assertEqual(rows(resp)[0]['nom'], 'B')

    # ── NTUX2 — définir-par-défaut-rôle : Directeur/Admin uniquement ───────
    def test_definir_par_defaut_role_forbidden_for_commercial(self):
        view = SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='Équipe',
            visibilite=SavedView.Visibilite.EQUIPE, role=self.role_commercial,
        )
        resp = auth(self.commercial1).post(f'{self.BASE}{view.id}/definir-par-defaut-role/')
        self.assertEqual(resp.status_code, 403)

    def test_definir_par_defaut_role_single_default_per_role_ecran(self):
        v1 = SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='V1',
            role=self.role_commercial, est_defaut_role=True,
        )
        v2 = SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='V2',
            role=self.role_commercial,
        )
        resp = auth(self.directeur).post(
            f'{self.BASE}{v2.id}/definir-par-defaut-role/',
            {'role': self.role_commercial.id}, format='json',
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertFalse(v1.est_defaut_role)
        self.assertTrue(v2.est_defaut_role)
        self.assertEqual(v2.visibilite, SavedView.Visibilite.EQUIPE)

    def test_definir_par_defaut_role_requires_role(self):
        view = SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='V',
        )
        resp = auth(self.directeur).post(f'{self.BASE}{view.id}/definir-par-defaut-role/')
        self.assertEqual(resp.status_code, 400)

    # ── Suppression : garde-fous ────────────────────────────────────────────
    def test_delete_own_personal_view(self):
        view = SavedView.objects.create(
            company=self.co_a, owner=self.commercial1, ecran='crm.leads', nom='V')
        resp = auth(self.commercial1).delete(f'{self.BASE}{view.id}/')
        self.assertEqual(resp.status_code, 204)

    def test_cannot_delete_default_role_view_without_permission(self):
        view = SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='V',
            role=self.role_commercial, est_defaut_role=True,
            visibilite=SavedView.Visibilite.EQUIPE,
        )
        resp = auth(self.commercial1).delete(f'{self.BASE}{view.id}/')
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(SavedView.objects.filter(id=view.id).exists())

    def test_directeur_can_delete_default_role_view(self):
        view = SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='V',
            role=self.role_commercial, est_defaut_role=True,
            visibilite=SavedView.Visibilite.EQUIPE,
        )
        resp = auth(self.directeur).delete(f'{self.BASE}{view.id}/')
        self.assertEqual(resp.status_code, 204)

    # ── NTUX23 — rapport « configuration des vues actives » (gouvernance) ──
    def test_toutes_company_forbidden_for_commercial(self):
        resp = auth(self.commercial1).get(f'{self.BASE}toutes-company/')
        self.assertEqual(resp.status_code, 403)

    def test_toutes_company_lists_every_view_of_the_company_beyond_perso_equipe_filter(self):
        # Vue PERSONNELLE d'un AUTRE utilisateur — invisible via list() normal,
        # mais visible ici (rapport de gouvernance Directeur/Admin).
        SavedView.objects.create(
            company=self.co_a, owner=self.commercial1, ecran='crm.leads', nom='Perso com1',
            visibilite=SavedView.Visibilite.PERSONNELLE,
        )
        SavedView.objects.create(
            company=self.co_a, owner=self.commercial2, ecran='ventes.devis', nom='Perso com2',
            visibilite=SavedView.Visibilite.PERSONNELLE,
        )
        # Vue d'une AUTRE company — ne doit jamais apparaître.
        SavedView.objects.create(
            company=self.co_b, owner=self.other_co_user, ecran='crm.leads', nom='Autre société',
        )
        resp = auth(self.directeur).get(f'{self.BASE}toutes-company/')
        self.assertEqual(resp.status_code, 200)
        noms = {r['nom'] for r in rows(resp)}
        self.assertEqual(noms, {'Perso com1', 'Perso com2'})

    def test_export_xlsx_forbidden_for_commercial(self):
        resp = auth(self.commercial1).get(f'{self.BASE}export-xlsx/')
        self.assertEqual(resp.status_code, 403)

    def test_export_xlsx_returns_a_workbook_with_one_row_per_view_and_default_role(self):
        SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='Équipe',
            visibilite=SavedView.Visibilite.EQUIPE, role=self.role_commercial, est_defaut_role=True,
        )
        SavedView.objects.create(
            company=self.co_a, owner=self.commercial1, ecran='ventes.devis', nom='Perso',
        )
        resp = auth(self.directeur).get(f'{self.BASE}export-xlsx/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        from openpyxl import load_workbook
        import io
        wb = load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        # En-tête + 2 lignes de données.
        self.assertEqual(ws.max_row, 3)
        header = [c.value for c in ws[1]]
        self.assertEqual(header, ['Écran', 'Nom', 'Propriétaire', 'Visibilité', 'Rôle par défaut', 'Dernière modification'])
        noms = {ws.cell(row=r, column=2).value for r in (2, 3)}
        self.assertEqual(noms, {'Équipe', 'Perso'})
        # Le rôle par défaut n'apparaît que pour la vue qui le porte.
        roles_col = {ws.cell(row=r, column=2).value: ws.cell(row=r, column=5).value for r in (2, 3)}
        self.assertEqual(roles_col['Équipe'], 'Commercial')
        # openpyxl relit une cellule chaîne-vide comme None (l'export écrit bien '').
        self.assertIn(roles_col['Perso'], (None, ''))

    # ── NTUX34 — import CSV de vues sauvegardées entre environnements ──────
    def _csv(self, rows):
        lines = ['ecran,nom,configuration']
        for ecran, nom, configuration in rows:
            lines.append(f'{ecran},{nom},"{configuration}"')
        return SimpleUploadedFile(
            'vues.csv', ('\n'.join(lines)).encode('utf-8'), content_type='text/csv')

    def test_importer_forbidden_for_commercial(self):
        fichier = self._csv([('crm.leads', 'V1', json.dumps({}))])
        resp = auth(self.commercial1).post(f'{self.BASE}importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 403)

    def test_importer_creates_valid_rows_as_personal_views_owned_by_caller(self):
        config = json.dumps({'colonnes_visibles': ['nom'], 'filtres': {'op': 'AND', 'conditions': []}})
        fichier = self._csv([('crm.leads', 'Mes leads chauds', config.replace('"', '""'))])
        resp = auth(self.directeur).post(f'{self.BASE}importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['created']), 1)
        self.assertEqual(resp.data['erreurs'], [])
        view = SavedView.objects.get(id=resp.data['created'][0]['id'])
        self.assertEqual(view.owner, self.directeur)
        self.assertEqual(view.company, self.co_a)
        self.assertEqual(view.visibilite, SavedView.Visibilite.PERSONNELLE)
        self.assertEqual(view.configuration['colonnes_visibles'], ['nom'])

    def test_importer_reports_invalid_json_line_with_its_number_and_still_imports_valid_rows(self):
        good = json.dumps({'colonnes_visibles': ['nom']}).replace('"', '""')
        lines = [
            'ecran,nom,configuration',
            f'crm.leads,Vue valide,"{good}"',
            'crm.leads,Vue cassée,"{pas du json valide"',
        ]
        fichier = SimpleUploadedFile(
            'vues.csv', ('\n'.join(lines)).encode('utf-8'), content_type='text/csv')
        resp = auth(self.directeur).post(f'{self.BASE}importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['created']), 1)
        self.assertEqual(len(resp.data['erreurs']), 1)
        self.assertEqual(resp.data['erreurs'][0]['ligne'], 2)
        self.assertIn('JSON', resp.data['erreurs'][0]['message'])

    def test_importer_never_silently_overwrites_renames_with_import_suffix(self):
        SavedView.objects.create(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='Mes leads',
            configuration={'ancien': True},
        )
        config = json.dumps({'nouveau': True}).replace('"', '""')
        fichier = self._csv([('crm.leads', 'Mes leads', config)])
        resp = auth(self.directeur).post(f'{self.BASE}importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(SavedView.objects.filter(company=self.co_a, owner=self.directeur, ecran='crm.leads').count(), 2)
        imported = SavedView.objects.get(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='Mes leads (import)')
        self.assertEqual(imported.configuration, {'nouveau': True})
        original = SavedView.objects.get(
            company=self.co_a, owner=self.directeur, ecran='crm.leads', nom='Mes leads')
        self.assertEqual(original.configuration, {'ancien': True})

    def test_importer_rejects_malformed_configuration_structure(self):
        bad = json.dumps({'colonnes_visibles': 'pas-une-liste'}).replace('"', '""')
        fichier = self._csv([('crm.leads', 'Vue mal formée', bad)])
        resp = auth(self.directeur).post(f'{self.BASE}importer/', {'fichier': fichier}, format='multipart')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['created'], [])
        self.assertEqual(len(resp.data['erreurs']), 1)
