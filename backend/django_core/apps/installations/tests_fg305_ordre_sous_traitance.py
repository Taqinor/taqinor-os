"""
FG305 — Ordres de travaux émis aux sous-traitants chantier.

``OrdreSousTraitance`` est la commande de PRESTATION passée à un sous-traitant de
l'annuaire (``SousTraitant``, FG304) : pour un chantier (``Installation``, même
app), une prestation décrite, un montant engagé et une échéance, avec un cycle de
vie propre (brouillon → émis → en cours → réceptionné → clos).

Couvre :
  * création via l'API avec référence (`OST-…`) + société + ``created_by`` posés
    CÔTÉ SERVEUR (jamais lus du corps) — la référence n'est jamais count()+1 ;
  * l'injection de ``company``/``reference`` dans le corps est ignorée ;
  * la FK ``sous_traitant`` doit appartenir à la MÊME société (sinon rejet) ;
  * la FK ``chantier`` doit appartenir à la MÊME société (sinon rejet) ;
  * les transitions de cycle de vie (`emettre`/`receptionner`/`cloturer`) et
    leurs gardes d'état ;
  * le filtre par ``sous_traitant``, ``statut`` et ``chantier`` ;
  * le scope société (la société B ne voit pas les ordres de A) ;
  * la barrière de rôle (écriture/lifecycle responsable/admin, lecture libre).

Run :
    python manage.py test apps.installations.tests_fg305_ordre_sous_traitance -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    OrdreSousTraitance, SousTraitant, Installation,
)

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg305-co-{n}', defaults={'nom': nom or f'FG305 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg305-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    from apps.crm.models import Client
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'fg305-{company.id}-{n}@example.invalid')


def make_chantier(company):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-{company.id}-{n}',
        client=make_client(company))


def make_sous_traitant(company, raison='Terrasol SARL', metier='terrassement'):
    return SousTraitant.objects.create(
        company=company, raison_sociale=raison, metier=metier)


# ── Création via l'API ────────────────────────────────────────────────────────

class TestOrdreCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)
        self.chantier = make_chantier(self.company)

    def test_create_ordre_server_side_ref_company(self):
        """FG305 — créer un ordre : référence OST-, société + créateur posés
        côté serveur (jamais count()+1)."""
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id,
            'chantier': self.chantier.id,
            'prestation': 'Terrassement des fondations + tranchées câbles',
            'montant': '45000.00',
            'date_echeance': '2026-07-15',
        })
        self.assertEqual(r.status_code, 201, r.data)
        ordre = OrdreSousTraitance.objects.get(id=r.data['id'])
        self.assertEqual(ordre.company_id, self.company.id)
        self.assertEqual(ordre.created_by_id, self.user.id)
        self.assertEqual(ordre.sous_traitant_id, self.st.id)
        self.assertEqual(ordre.chantier_id, self.chantier.id)
        # Référence anti-collision posée serveur, préfixe OST-.
        self.assertTrue(ordre.reference.startswith('OST-'), ordre.reference)
        # Statut initial = brouillon.
        self.assertEqual(ordre.statut, OrdreSousTraitance.Statut.BROUILLON)

    def test_reference_increments_not_count(self):
        """FG305 — deux ordres → références distinctes et croissantes (le
        highest-used+1, jamais count()+1)."""
        ref1 = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id, 'prestation': 'A', 'montant': '1',
        }).data['reference']
        ref2 = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id, 'prestation': 'B', 'montant': '2',
        }).data['reference']
        self.assertNotEqual(ref1, ref2)

    def test_company_and_reference_forced_server_side(self):
        """FG305 — société et référence du corps sont ignorées (forcées
        serveur)."""
        autre = make_company()
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'company': autre.id,            # tentative d'injection
            'reference': 'OST-HACK-9999',   # tentative d'injection
            'sous_traitant': self.st.id,
            'prestation': 'Pose structures',
            'montant': '12000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        ordre = OrdreSousTraitance.objects.get(id=r.data['id'])
        self.assertEqual(ordre.company_id, self.company.id)
        self.assertNotEqual(ordre.reference, 'OST-HACK-9999')

    def test_chantier_optional(self):
        """FG305 — le chantier est optionnel (ordre cadre sans affectation)."""
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id,
            'prestation': 'Astreinte génie civil',
            'montant': '8000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        ordre = OrdreSousTraitance.objects.get(id=r.data['id'])
        self.assertIsNone(ordre.chantier_id)

    def test_blank_prestation_rejected(self):
        """FG305 — la prestation est obligatoire."""
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id,
            'prestation': '   ',
            'montant': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_negative_montant_rejected(self):
        """FG305 — un montant négatif est refusé."""
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id,
            'prestation': 'Pose',
            'montant': '-5',
        })
        self.assertEqual(r.status_code, 400, r.data)


# ── Tenant safety sur les FK ──────────────────────────────────────────────────

class TestOrdreForeignKeyTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_sous_traitant_other_company_rejected(self):
        """FG305 — un sous-traitant d'une AUTRE société est rejeté (fuite
        inter-tenant impossible)."""
        autre = make_company()
        st_autre = make_sous_traitant(autre, raison='Étranger SARL')
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': st_autre.id,
            'prestation': 'Pose',
            'montant': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('sous_traitant', r.data)

    def test_chantier_other_company_rejected(self):
        """FG305 — un chantier d'une AUTRE société est rejeté."""
        autre = make_company()
        chantier_autre = make_chantier(autre)
        r = self.api.post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id,
            'chantier': chantier_autre.id,
            'prestation': 'Pose',
            'montant': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('chantier', r.data)


# ── Cycle de vie ──────────────────────────────────────────────────────────────

class TestOrdreLifecycle(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def _make_ordre(self, statut=OrdreSousTraitance.Statut.BROUILLON):
        return OrdreSousTraitance.objects.create(
            company=self.company, reference=f'OST-T-{next(_seq)}',
            sous_traitant=self.st, prestation='Pose', montant=1000,
            statut=statut, created_by=self.user)

    def test_emettre(self):
        """FG305 — émettre : brouillon → émis + pose la date d'émission."""
        ordre = self._make_ordre()
        r = self.api.post(
            f'{BASE}/ordres-sous-traitance/{ordre.id}/emettre/')
        self.assertEqual(r.status_code, 200, r.data)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreSousTraitance.Statut.EMIS)
        self.assertIsNotNone(ordre.date_emission)

    def test_receptionner_with_montant_realise(self):
        """FG305 — réceptionner un ordre émis + enregistrer le réalisé."""
        ordre = self._make_ordre(statut=OrdreSousTraitance.Statut.EMIS)
        r = self.api.post(
            f'{BASE}/ordres-sous-traitance/{ordre.id}/receptionner/',
            {'montant_realise': '950.50'})
        self.assertEqual(r.status_code, 200, r.data)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreSousTraitance.Statut.RECEPTIONNE)
        self.assertEqual(str(ordre.montant_realise), '950.50')

    def test_receptionner_requires_emis(self):
        """FG305 — on ne réceptionne pas un brouillon."""
        ordre = self._make_ordre()
        r = self.api.post(
            f'{BASE}/ordres-sous-traitance/{ordre.id}/receptionner/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_cloturer_requires_receptionne(self):
        """FG305 — on ne clôt qu'un ordre réceptionné."""
        ordre = self._make_ordre(statut=OrdreSousTraitance.Statut.EMIS)
        r = self.api.post(
            f'{BASE}/ordres-sous-traitance/{ordre.id}/cloturer/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_full_lifecycle(self):
        """FG305 — brouillon → émis → réceptionné → clos."""
        ordre = self._make_ordre()
        oid = ordre.id
        self.assertEqual(self.api.post(
            f'{BASE}/ordres-sous-traitance/{oid}/emettre/').status_code, 200)
        self.assertEqual(self.api.post(
            f'{BASE}/ordres-sous-traitance/{oid}/receptionner/'
        ).status_code, 200)
        r = self.api.post(
            f'{BASE}/ordres-sous-traitance/{oid}/cloturer/')
        self.assertEqual(r.status_code, 200, r.data)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, OrdreSousTraitance.Statut.CLOS)


# ── Filtres ───────────────────────────────────────────────────────────────────

class TestOrdreFilters(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st_a = make_sous_traitant(self.company, raison='Terrasol')
        self.st_b = make_sous_traitant(
            self.company, raison='Élec Atlas', metier='electricite')
        self.chantier = make_chantier(self.company)
        self.o1 = OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-F-1',
            sous_traitant=self.st_a, chantier=self.chantier,
            prestation='Terrassement', montant=100,
            statut=OrdreSousTraitance.Statut.BROUILLON)
        self.o2 = OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-F-2',
            sous_traitant=self.st_b, prestation='Câblage', montant=200,
            statut=OrdreSousTraitance.Statut.EMIS)

    def test_filter_by_sous_traitant(self):
        """FG305 — filtre par sous-traitant."""
        r = self.api.get(
            f'{BASE}/ordres-sous-traitance/?sous_traitant={self.st_b.id}')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(ids, [self.o2.id])

    def test_filter_by_statut(self):
        """FG305 — filtre par statut."""
        r = self.api.get(f'{BASE}/ordres-sous-traitance/?statut=emis')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(ids, [self.o2.id])

    def test_filter_by_chantier(self):
        """FG305 — filtre par chantier."""
        r = self.api.get(
            f'{BASE}/ordres-sous-traitance/?chantier={self.chantier.id}')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(ids, [self.o1.id])


# ── Scope société ─────────────────────────────────────────────────────────────

class TestOrdreTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_list_company_isolation(self):
        """FG305 — la société B ne voit pas les ordres de A."""
        OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-X-1',
            sous_traitant=self.st, prestation='Pose', montant=1)
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(f'{BASE}/ordres-sous-traitance/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_retrieve_cross_company_404(self):
        """FG305 — récupérer un ordre d'une autre société → 404."""
        ordre = OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-X-2',
            sous_traitant=self.st, prestation='Pose', montant=1)
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(
            f'{BASE}/ordres-sous-traitance/{ordre.id}/')
        self.assertEqual(r.status_code, 404)


# ── Barrière de rôle ──────────────────────────────────────────────────────────

class TestOrdreRoleGate(TestCase):
    def setUp(self):
        self.company = make_company()
        # Rôle hérité « normal » : ni responsable ni admin → lecture seule.
        self.lecteur = make_user(self.company, role='normal')
        self.st = make_sous_traitant(self.company)

    def test_read_allowed_any_role(self):
        """FG305 — un rôle simple peut LIRE la liste."""
        r = auth(self.lecteur).get(f'{BASE}/ordres-sous-traitance/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_write_forbidden_for_non_manager(self):
        """FG305 — un rôle simple ne peut PAS créer (écriture
        responsable/admin)."""
        r = auth(self.lecteur).post(f'{BASE}/ordres-sous-traitance/', {
            'sous_traitant': self.st.id,
            'prestation': 'Pose',
            'montant': '1000',
        })
        self.assertEqual(r.status_code, 403, r.data)

    def test_lifecycle_forbidden_for_non_manager(self):
        """FG305 — un rôle simple ne peut PAS émettre (action d'écriture)."""
        ordre = OrdreSousTraitance.objects.create(
            company=self.company, reference='OST-R-1',
            sous_traitant=self.st, prestation='Pose', montant=1)
        r = auth(self.lecteur).post(
            f'{BASE}/ordres-sous-traitance/{ordre.id}/emettre/')
        self.assertEqual(r.status_code, 403, r.data)
