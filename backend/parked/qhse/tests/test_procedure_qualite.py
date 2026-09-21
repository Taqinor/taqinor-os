"""Tests QHSE18 — Procédure qualité versionnée (docs qualité GED).

Couvre :
* service ``nouvelle_version_procedure`` : v1 pour une référence inédite,
  v2/v3 incrémentées côté serveur (jamais count()+1), historique préservé,
  company/auteur posés côté serveur, ``document_id`` référence lâche au GED ;
* service ``activer_procedure`` : la version visée passe EN_VIGUEUR et les
  autres versions en vigueur de la même référence deviennent OBSOLETE ;
* sélecteurs ``procedure_qualite_courante`` (en vigueur, à défaut version la
  plus haute), ``procedure_qualite_versions``, ``procedures_qualite_courantes`` ;
* contrainte d'unicité (company, reference, version) ;
* endpoints API : create (route service → version serveur), ``activer``,
  ``courante``, ``versions``, filtres ``?reference=`` / ``?courantes=1`` ;
* isolation entre sociétés.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ProcedureQualite
from apps.qhse.selectors import (
    procedure_qualite_courante, procedure_qualite_versions,
    procedures_qualite_courantes,
)
from apps.qhse.services import (
    activer_procedure, nouvelle_version_procedure,
)

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


# ── Service : versioning ────────────────────────────────────────────────────

class NouvelleVersionProcedureTests(TestCase):
    def setUp(self):
        self.company = make_company('co-pq', 'CoPQ')
        self.user = make_user(self.company, 'pq-user')

    def test_premiere_version_est_v1(self):
        proc = nouvelle_version_procedure(
            self.company, 'PRO-QUAL-001', 'Gestion des NC', auteur=self.user)
        self.assertEqual(proc.version, 1)
        self.assertEqual(proc.statut, ProcedureQualite.Statut.BROUILLON)
        self.assertEqual(proc.company_id, self.company.id)
        self.assertEqual(proc.auteur_id, self.user.id)

    def test_versions_incrementent_sans_ecraser(self):
        v1 = nouvelle_version_procedure(
            self.company, 'PRO-QUAL-001', 'Gestion des NC')
        v2 = nouvelle_version_procedure(
            self.company, 'PRO-QUAL-001', 'Gestion des NC (rev)')
        v3 = nouvelle_version_procedure(
            self.company, 'PRO-QUAL-001', 'Gestion des NC (rev2)')
        self.assertEqual([v1.version, v2.version, v3.version], [1, 2, 3])
        # Historique préservé : 3 lignes pour la référence.
        self.assertEqual(
            ProcedureQualite.objects.filter(
                company=self.company, reference='PRO-QUAL-001').count(),
            3)

    def test_references_distinctes_ont_leur_propre_compteur(self):
        a = nouvelle_version_procedure(self.company, 'PRO-A', 'A')
        b = nouvelle_version_procedure(self.company, 'PRO-B', 'B')
        a2 = nouvelle_version_procedure(self.company, 'PRO-A', 'A bis')
        self.assertEqual(a.version, 1)
        self.assertEqual(b.version, 1)
        self.assertEqual(a2.version, 2)

    def test_document_id_reference_lache(self):
        proc = nouvelle_version_procedure(
            self.company, 'PRO-QUAL-002', 'Doc lié', document_id=42)
        self.assertEqual(proc.document_id, 42)

    def test_contrainte_unicite_company_reference_version(self):
        nouvelle_version_procedure(self.company, 'PRO-DUP', 'X')
        with self.assertRaises(IntegrityError):
            ProcedureQualite.objects.create(
                company=self.company, reference='PRO-DUP',
                titre='collision', version=1)


# ── Service : activation ────────────────────────────────────────────────────

class ActiverProcedureTests(TestCase):
    def setUp(self):
        self.company = make_company('co-pq2', 'CoPQ2')

    def test_activation_met_en_vigueur_et_obsoletise_les_autres(self):
        v1 = nouvelle_version_procedure(self.company, 'PRO-X', 'X')
        v2 = nouvelle_version_procedure(self.company, 'PRO-X', 'X rev')
        activer_procedure(v1)
        v1.refresh_from_db()
        self.assertEqual(v1.statut, ProcedureQualite.Statut.EN_VIGUEUR)
        self.assertIsNotNone(v1.date_application)

        # Activer v2 obsolétise v1.
        activer_procedure(v2)
        v1.refresh_from_db()
        v2.refresh_from_db()
        self.assertEqual(v2.statut, ProcedureQualite.Statut.EN_VIGUEUR)
        self.assertEqual(v1.statut, ProcedureQualite.Statut.OBSOLETE)

    def test_activation_n_affecte_pas_une_autre_reference(self):
        x = nouvelle_version_procedure(self.company, 'PRO-X', 'X')
        y = nouvelle_version_procedure(self.company, 'PRO-Y', 'Y')
        activer_procedure(x)
        activer_procedure(y)
        x.refresh_from_db()
        y.refresh_from_db()
        # Y en vigueur n'obsolétise pas X (référence différente).
        self.assertEqual(x.statut, ProcedureQualite.Statut.EN_VIGUEUR)
        self.assertEqual(y.statut, ProcedureQualite.Statut.EN_VIGUEUR)


# ── Sélecteurs ──────────────────────────────────────────────────────────────

class ProcedureSelecteursTests(TestCase):
    def setUp(self):
        self.company = make_company('co-pq3', 'CoPQ3')

    def test_courante_renvoie_en_vigueur(self):
        v1 = nouvelle_version_procedure(self.company, 'PRO-S', 'S')
        v2 = nouvelle_version_procedure(self.company, 'PRO-S', 'S rev')
        activer_procedure(v1)  # v1 en vigueur, v2 brouillon
        courante = procedure_qualite_courante(self.company, 'PRO-S')
        self.assertEqual(courante.id, v1.id)
        self.assertEqual(courante.version, 1)
        # marque v2 pour que le linter n'avertisse pas; v2 reste brouillon
        self.assertEqual(v2.statut, ProcedureQualite.Statut.BROUILLON)

    def test_courante_defaut_version_la_plus_haute(self):
        nouvelle_version_procedure(self.company, 'PRO-S2', 'S2')
        v2 = nouvelle_version_procedure(self.company, 'PRO-S2', 'S2 rev')
        # Aucune en vigueur → version la plus haute.
        courante = procedure_qualite_courante(self.company, 'PRO-S2')
        self.assertEqual(courante.id, v2.id)

    def test_courante_none_si_reference_inconnue(self):
        self.assertIsNone(
            procedure_qualite_courante(self.company, 'INEXISTANT'))

    def test_versions_renvoie_tout_recent_dabord(self):
        nouvelle_version_procedure(self.company, 'PRO-V', 'V')
        nouvelle_version_procedure(self.company, 'PRO-V', 'V rev')
        versions = list(procedure_qualite_versions(self.company, 'PRO-V'))
        self.assertEqual([v.version for v in versions], [2, 1])

    def test_courantes_une_par_reference(self):
        a1 = nouvelle_version_procedure(self.company, 'PRO-A', 'A')
        nouvelle_version_procedure(self.company, 'PRO-A', 'A rev')
        b1 = nouvelle_version_procedure(self.company, 'PRO-B', 'B')
        activer_procedure(a1)  # PRO-A courante = v1 (en vigueur)
        courantes = procedures_qualite_courantes(self.company)
        refs = {p.reference for p in courantes}
        self.assertEqual(refs, {'PRO-A', 'PRO-B'})
        par_ref = {p.reference: p for p in courantes}
        self.assertEqual(par_ref['PRO-A'].id, a1.id)
        # PRO-B : aucune en vigueur → version la plus haute (b1, seule version).
        self.assertEqual(par_ref['PRO-B'].id, b1.id)


# ── Isolation société ───────────────────────────────────────────────────────

class ProcedureIsolationTests(TestCase):
    def setUp(self):
        self.co1 = make_company('co-pq-a', 'A')
        self.co2 = make_company('co-pq-b', 'B')

    def test_meme_reference_independante_par_societe(self):
        a = nouvelle_version_procedure(self.co1, 'PRO-COMMUN', 'A')
        b = nouvelle_version_procedure(self.co2, 'PRO-COMMUN', 'B')
        # Chaque société a sa propre v1 (la contrainte d'unicité inclut company).
        self.assertEqual(a.version, 1)
        self.assertEqual(b.version, 1)
        self.assertIsNone(
            procedure_qualite_courante(self.co1, 'INCONNUE'))
        self.assertEqual(
            procedure_qualite_courante(self.co1, 'PRO-COMMUN').id, a.id)
        self.assertEqual(
            procedure_qualite_courante(self.co2, 'PRO-COMMUN').id, b.id)


# ── API ─────────────────────────────────────────────────────────────────────

class ProcedureQualiteApiTests(TestCase):
    def setUp(self):
        self.company = make_company('co-pq-api', 'CoAPI')
        self.user = make_user(self.company, 'pq-api-user')
        self.client_api = auth_client(self.user)
        self.other_company = make_company('co-pq-api-2', 'CoAPI2')
        self.other_user = make_user(self.other_company, 'pq-api-other')
        self.other_client = auth_client(self.other_user)

    def test_create_route_par_service_pose_version_serveur(self):
        # On tente d'imposer version=99 → ignoré (read-only), v1 calculée.
        resp = self.client_api.post(
            '/api/django/qhse/procedures-qualite/',
            {'reference': 'PRO-API-1', 'titre': 'T', 'version': 99,
             'statut': 'en_vigueur', 'contenu': 'corps'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['version'], 1)
        self.assertEqual(resp.data['statut'], 'brouillon')
        proc = ProcedureQualite.objects.get(id=resp.data['id'])
        self.assertEqual(proc.company_id, self.company.id)
        self.assertEqual(proc.auteur_id, self.user.id)

    def test_create_deuxieme_fois_donne_v2(self):
        self.client_api.post(
            '/api/django/qhse/procedures-qualite/',
            {'reference': 'PRO-API-2', 'titre': 'T'}, format='json')
        resp = self.client_api.post(
            '/api/django/qhse/procedures-qualite/',
            {'reference': 'PRO-API-2', 'titre': 'T rev'}, format='json')
        self.assertEqual(resp.data['version'], 2)

    def test_activer_endpoint(self):
        v1 = nouvelle_version_procedure(self.company, 'PRO-ACT', 'T')
        v2 = nouvelle_version_procedure(self.company, 'PRO-ACT', 'T rev')
        activer_procedure(v1)
        resp = self.client_api.post(
            f'/api/django/qhse/procedures-qualite/{v2.id}/activer/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut'], 'en_vigueur')
        v1.refresh_from_db()
        self.assertEqual(v1.statut, ProcedureQualite.Statut.OBSOLETE)

    def test_courante_endpoint(self):
        v1 = nouvelle_version_procedure(self.company, 'PRO-CUR', 'T')
        activer_procedure(v1)
        nouvelle_version_procedure(self.company, 'PRO-CUR', 'T rev')
        resp = self.client_api.get(
            '/api/django/qhse/procedures-qualite/courante/',
            {'reference': 'PRO-CUR'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['id'], v1.id)

    def test_courante_404_si_inconnue(self):
        resp = self.client_api.get(
            '/api/django/qhse/procedures-qualite/courante/',
            {'reference': 'NOPE'})
        self.assertEqual(resp.status_code, 404)

    def test_courante_400_sans_reference(self):
        resp = self.client_api.get(
            '/api/django/qhse/procedures-qualite/courante/')
        self.assertEqual(resp.status_code, 400)

    def test_versions_endpoint(self):
        v1 = nouvelle_version_procedure(self.company, 'PRO-VER', 'T')
        nouvelle_version_procedure(self.company, 'PRO-VER', 'T rev')
        resp = self.client_api.get(
            f'/api/django/qhse/procedures-qualite/{v1.id}/versions/')
        self.assertEqual(resp.status_code, 200)
        versions = [r['version'] for r in resp.data]
        self.assertEqual(versions, [2, 1])

    def test_filtre_reference(self):
        nouvelle_version_procedure(self.company, 'PRO-F1', 'A')
        nouvelle_version_procedure(self.company, 'PRO-F2', 'B')
        resp = self.client_api.get(
            '/api/django/qhse/procedures-qualite/', {'reference': 'PRO-F1'})
        refs = {r['reference'] for r in rows(resp)}
        self.assertEqual(refs, {'PRO-F1'})

    def test_filtre_courantes(self):
        v1 = nouvelle_version_procedure(self.company, 'PRO-C1', 'A')
        nouvelle_version_procedure(self.company, 'PRO-C1', 'A rev')
        activer_procedure(v1)
        resp = self.client_api.get(
            '/api/django/qhse/procedures-qualite/', {'courantes': '1'})
        results = rows(resp)
        # Une seule entrée pour PRO-C1 (la version en vigueur v1).
        ids = [r['id'] for r in results if r['reference'] == 'PRO-C1']
        self.assertEqual(ids, [v1.id])

    def test_isolation_societe_liste(self):
        nouvelle_version_procedure(self.company, 'PRO-ISO', 'A')
        nouvelle_version_procedure(self.other_company, 'PRO-ISO-OTHER', 'B')
        resp = self.other_client.get(
            '/api/django/qhse/procedures-qualite/')
        refs = {r['reference'] for r in rows(resp)}
        self.assertNotIn('PRO-ISO', refs)

    def test_isolation_societe_detail_404(self):
        proc = nouvelle_version_procedure(self.company, 'PRO-ISO-D', 'A')
        resp = self.other_client.get(
            f'/api/django/qhse/procedures-qualite/{proc.id}/')
        self.assertEqual(resp.status_code, 404)
