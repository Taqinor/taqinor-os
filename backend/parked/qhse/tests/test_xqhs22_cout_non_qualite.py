"""XQHS22 — Coût de la non-qualité (CoQ) — interne uniquement.

Couvre :
  * les coûts se saisissent (NCR/CAPA/incident) ;
  * le rollup ventile par catégorie (interne/externe) et par mois ;
  * la permission ``cout_non_qualite_voir`` masque les montants (serializer +
    endpoint rollup) aux non-autorisés ;
  * aucun coût ne fuit dans un rendu client (retiré complètement, pas juste
    caché côté front) ;
  * le scoping société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.qhse.models import ActionCorrectivePreventive, Incident, NonConformite
from apps.qhse.selectors import cout_non_qualite
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='admin'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def make_user_with_role(company, username, permissions):
    # Ajoute toujours `qhse_voir` (accès de base aux endpoints QHSE — les
    # montants restent masqués/démasqués séparément par
    # `cout_non_qualite_voir`, testé ici) + une permission d'écriture
    # (`stock_modifier`) pour que le rôle passe ``is_responsable`` (ERR4 :
    # un rôle SANS permission d'écriture/gestion échoue
    # `IsResponsableOrAdmin`, indépendamment de `cout_non_qualite_voir`).
    role = Role.objects.create(
        company=company, nom=f'role-{username}',
        permissions=list(permissions) + ['qhse_voir', 'stock_modifier'])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CoutSaisieTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs22-saisie', 'Xqhs22 Saisie')

    def test_ncr_porte_cout_estime_et_reel(self):
        ncr = NonConformite.objects.create(
            company=self.company, titre='Retouche', cout_estime=500,
            cout_reel=650)
        self.assertEqual(ncr.cout_estime, 500)
        self.assertEqual(ncr.cout_reel, 650)

    def test_capa_porte_cout(self):
        ncr = NonConformite.objects.create(company=self.company, titre='NCR')
        capa = ActionCorrectivePreventive.objects.create(
            company=self.company, non_conformite=ncr, description='Action',
            cout=200)
        self.assertEqual(capa.cout, 200)

    def test_incident_porte_cout(self):
        incident = Incident.objects.create(
            company=self.company, titre='Incident', cout=1000)
        self.assertEqual(incident.cout, 1000)


class CoutNonQualiteRollupTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs22-rollup', 'Xqhs22 Rollup')

    def test_ncr_sans_ticket_sav_compte_interne(self):
        NonConformite.objects.create(
            company=self.company, titre='Retouche chantier',
            cout_reel=300, date_creation='2026-03-15')
        rollup = cout_non_qualite(self.company, 2026)
        self.assertEqual(rollup['interne'], 300)
        self.assertEqual(rollup['externe'], 0)

    def test_incident_compte_externe(self):
        from django.utils import timezone

        Incident.objects.create(
            company=self.company, titre='Incident client', cout=800)
        rollup = cout_non_qualite(self.company, timezone.now().year)
        self.assertEqual(rollup['externe'], 800)

    def test_capa_compte_interne(self):
        ncr = NonConformite.objects.create(company=self.company, titre='NCR')
        ActionCorrectivePreventive.objects.create(
            company=self.company, non_conformite=ncr, description='x',
            cout=150)
        from django.utils import timezone
        rollup = cout_non_qualite(self.company, timezone.now().year)
        self.assertEqual(rollup['interne'], 150)

    def test_total_est_somme(self):
        from django.utils import timezone
        Incident.objects.create(company=self.company, titre='I', cout=100)
        NonConformite.objects.create(
            company=self.company, titre='N', cout_reel=200)
        rollup = cout_non_qualite(self.company, timezone.now().year)
        self.assertEqual(rollup['total'], 300)

    def test_par_mois_ventile(self):
        NonConformite.objects.create(
            company=self.company, titre='N1', cout_reel=100,
            date_creation='2026-01-10')
        NonConformite.objects.create(
            company=self.company, titre='N2', cout_reel=50,
            date_creation='2026-02-10')
        rollup = cout_non_qualite(self.company, 2026)
        mois = {m['mois']: m for m in rollup['par_mois']}
        self.assertIn('2026-01', mois)
        self.assertIn('2026-02', mois)

    def test_scope_societe(self):
        other_co = make_company('xqhs22-rollup-other', 'Xqhs22 Rollup Other')
        Incident.objects.create(company=other_co, titre='Autre', cout=999)
        from django.utils import timezone
        rollup = cout_non_qualite(self.company, timezone.now().year)
        self.assertEqual(rollup['total'], 0)


class CoutNonQualitePermissionApiTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs22-perm', 'Xqhs22 Perm')

    def test_avec_permission_voit_montants(self):
        user = make_user_with_role(
            self.company, 'xqhs22-avec-perm',
            ['cout_non_qualite_voir'])
        resp = auth(user).get('/api/django/qhse/cout-non-qualite/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['total'])

    def test_sans_permission_montants_masques(self):
        user = make_user_with_role(self.company, 'xqhs22-sans-perm', [])
        resp = auth(user).get('/api/django/qhse/cout-non-qualite/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['total'])
        self.assertIsNone(resp.data['interne'])
        self.assertIsNone(resp.data['externe'])

    def test_superuser_legacy_voit_montants(self):
        user = make_user(self.company, 'xqhs22-legacy')
        resp = auth(user).get('/api/django/qhse/cout-non-qualite/')
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.data['total'])


class CoutFieldSerializerMaskingTests(TestCase):
    def setUp(self):
        self.company = make_company('xqhs22-mask', 'Xqhs22 Mask')

    def test_ncr_cout_absent_du_json_sans_permission(self):
        user = make_user_with_role(self.company, 'xqhs22-mask-user', [])
        ncr = NonConformite.objects.create(
            company=self.company, titre='NCR masquée', cout_reel=999)
        resp = auth(user).get(
            f'/api/django/qhse/non-conformites/{ncr.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('cout_reel', resp.data)
        self.assertNotIn('cout_estime', resp.data)

    def test_ncr_cout_present_avec_permission(self):
        user = make_user_with_role(
            self.company, 'xqhs22-mask-user2', ['cout_non_qualite_voir'])
        ncr = NonConformite.objects.create(
            company=self.company, titre='NCR visible', cout_reel=999)
        resp = auth(user).get(
            f'/api/django/qhse/non-conformites/{ncr.pk}/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('cout_reel', resp.data)
        self.assertEqual(resp.data['cout_reel'], '999.00')

    def test_incident_cout_absent_sans_permission(self):
        user = make_user_with_role(self.company, 'xqhs22-mask-inc', [])
        incident = Incident.objects.create(
            company=self.company, titre='Incident masqué', cout=500)
        resp = auth(user).get(f'/api/django/qhse/incidents/{incident.pk}/')
        self.assertNotIn('cout', resp.data)
