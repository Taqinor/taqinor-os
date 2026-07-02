"""
FG304 / DC34 — Annuaire des sous-traitants chantier (référentiel UNIFIÉ).

Depuis DC34 un sous-traitant N'EST PLUS un modèle parallèle : c'est un
``stock.Fournisseur`` de type « service » porteur d'un ``SousTraitantProfile``
(métier / actif / note). L'endpoint ``sous-traitants/`` reste identique (contrat
d'API FG304 préservé) mais orchestre le couple Fournisseur/profil via les
services stock.

Couvre :
  * création via l'API avec société + ``created_by`` posés CÔTÉ SERVEUR ;
  * l'injection de ``company`` dans le corps est ignorée (forcée serveur) ;
  * le stockage de l'ICE et du RIB (sur le Fournisseur) ;
  * le filtre par ``metier`` et par ``actif`` (lus sur le profil) ;
  * la recherche plein-texte (``?search=``) sur raison sociale et ICE ;
  * le scope société (la société B ne voit pas l'annuaire de A) ;
  * la barrière de rôle (écriture responsable/admin uniquement, lecture libre).

Run :
    python manage.py test apps.installations.tests_fg304_sous_traitant -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Fournisseur, SousTraitantProfile
from apps.stock.services import create_sous_traitant

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg304-co-{n}', defaults={'nom': nom or f'FG304 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg304-{next(_seq)}', password='x',
        role_legacy=role, company=company)


# ── Création via l'API ────────────────────────────────────────────────────────

class TestSousTraitantCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_create_sous_traitant(self):
        """FG304/DC34 — créer un sous-traitant : Fournisseur(type=service) +
        profil, société + créateur posés serveur."""
        r = self.api.post(f'{BASE}/sous-traitants/', {
            'raison_sociale': 'Terrasol SARL',
            'metier': 'terrassement',
            'contact_nom': 'Karim Benani',
            'telephone': '+212600000000',
            'email': 'contact@terrasol.ma',
            'ice': '001234567000089',
            'rib': '011780000012345678901234',
            'adresse': '12 rue des Chantiers, Casablanca',
        })
        self.assertEqual(r.status_code, 201, r.data)
        f = Fournisseur.objects.get(id=r.data['id'])
        # Société posée côté serveur, jamais du corps ; type service.
        self.assertEqual(f.company_id, self.company.id)
        self.assertEqual(f.type, 'service')
        self.assertEqual(f.nom, 'Terrasol SARL')
        profil = SousTraitantProfile.objects.get(fournisseur=f)
        self.assertEqual(profil.company_id, self.company.id)
        self.assertEqual(profil.metier, 'terrassement')
        self.assertEqual(profil.created_by_id, self.user.id)
        self.assertTrue(profil.actif)

    def test_ice_rib_stored(self):
        """FG304 — l'ICE et le RIB sont stockés tels quels (chaînes, zéros de
        tête préservés) sur le Fournisseur."""
        ice = '002233445000067'
        rib = '230810000099887766554433'
        r = self.api.post(f'{BASE}/sous-traitants/', {
            'raison_sociale': 'GC Maroc',
            'metier': 'genie_civil',
            'ice': ice, 'rib': rib,
        })
        self.assertEqual(r.status_code, 201, r.data)
        f = Fournisseur.objects.get(id=r.data['id'])
        self.assertEqual(f.ice, ice)
        self.assertEqual(f.rib, rib)

    def test_company_forced_server_side(self):
        """FG304 — la société du corps de requête est ignorée (forcée serveur)."""
        autre = make_company()
        r = self.api.post(f'{BASE}/sous-traitants/', {
            'company': autre.id,  # tentative d'injection
            'raison_sociale': 'Levage Express',
            'metier': 'levage',
        })
        self.assertEqual(r.status_code, 201, r.data)
        f = Fournisseur.objects.get(id=r.data['id'])
        self.assertEqual(f.company_id, self.company.id)

    def test_blank_raison_sociale_rejected(self):
        """FG304 — la raison sociale est obligatoire."""
        r = self.api.post(f'{BASE}/sous-traitants/', {
            'raison_sociale': '   ',
            'metier': 'transport',
        })
        self.assertEqual(r.status_code, 400, r.data)


# ── Filtres & recherche ───────────────────────────────────────────────────────

class TestSousTraitantFiltersSearch(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.terrass = create_sous_traitant(
            company=self.company, nom='Terrasol SARL',
            metier='terrassement', ice='001234567000089', actif=True)
        self.elec = create_sous_traitant(
            company=self.company, nom='Élec Atlas',
            metier='electricite', ice='009988776000054', actif=True)
        self.vieux = create_sous_traitant(
            company=self.company, nom='Vieux Transport',
            metier='transport', ice='005555555000011', actif=False)

    def test_filter_by_metier(self):
        """FG304 — filtre par métier."""
        r = self.api.get(f'{BASE}/sous-traitants/?metier=electricite')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(ids, [self.elec.id])

    def test_filter_by_actif_true(self):
        """FG304 — filtre actif=true ne renvoie que les sous-traitants actifs."""
        r = self.api.get(f'{BASE}/sous-traitants/?actif=true')
        self.assertEqual(r.status_code, 200, r.data)
        ids = {row['id'] for row in r.data['results']}
        self.assertEqual(ids, {self.terrass.id, self.elec.id})

    def test_filter_by_actif_false(self):
        """FG304 — filtre actif=false ne renvoie que les archivés."""
        r = self.api.get(f'{BASE}/sous-traitants/?actif=false')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(ids, [self.vieux.id])

    def test_search_by_raison_sociale(self):
        """FG304 — recherche plein-texte sur la raison sociale (nom)."""
        r = self.api.get(f'{BASE}/sous-traitants/?search=Atlas')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(ids, [self.elec.id])

    def test_search_by_ice(self):
        """FG304 — recherche plein-texte sur l'ICE."""
        r = self.api.get(f'{BASE}/sous-traitants/?search=001234567')
        self.assertEqual(r.status_code, 200, r.data)
        ids = [row['id'] for row in r.data['results']]
        self.assertEqual(ids, [self.terrass.id])


# ── Scope société ─────────────────────────────────────────────────────────────

class TestSousTraitantTenant(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)

    def test_list_company_isolation(self):
        """FG304 — la société B ne voit pas l'annuaire de A."""
        create_sous_traitant(
            company=self.company, nom='Terrasol SARL', metier='terrassement')
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(f'{BASE}/sous-traitants/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['count'], 0)

    def test_retrieve_cross_company_404(self):
        """FG304 — récupérer un sous-traitant d'une autre société → 404."""
        st = create_sous_traitant(
            company=self.company, nom='Terrasol SARL', metier='terrassement')
        company_b = make_company()
        user_b = make_user(company_b)
        r = auth(user_b).get(f'{BASE}/sous-traitants/{st.id}/')
        self.assertEqual(r.status_code, 404)


# ── Barrière de rôle ──────────────────────────────────────────────────────────

class TestSousTraitantRoleGate(TestCase):
    def setUp(self):
        self.company = make_company()
        # Rôle hérité « normal » : ni responsable ni admin → lecture seule.
        self.lecteur = make_user(self.company, role='normal')

    def test_read_allowed_any_role(self):
        """FG304 — un rôle simple peut LIRE la liste."""
        r = auth(self.lecteur).get(f'{BASE}/sous-traitants/')
        self.assertEqual(r.status_code, 200, r.data)

    def test_write_forbidden_for_non_manager(self):
        """FG304 — un rôle simple ne peut PAS créer (écriture
        responsable/admin)."""
        r = auth(self.lecteur).post(f'{BASE}/sous-traitants/', {
            'raison_sociale': 'Terrasol SARL',
            'metier': 'terrassement',
        })
        self.assertEqual(r.status_code, 403, r.data)
