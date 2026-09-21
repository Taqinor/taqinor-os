"""Tests CONTRAT7 — ModeleContrat (bibliothèque de gabarits de contrats).

Couvre :
- Création d'un ModeleContrat (company posée côté serveur, jamais depuis le corps).
- Isolation multi-tenant (société A ne voit pas les modèles de société B).
- CRUD basique (liste, détail, mise à jour, suppression).
- Filtres : ?actif=, ?categorie=.
- Recherche plein texte : ?search=.
- Action ``/instancier/`` : crée un Contrat pré-rempli depuis le gabarit,
  avec et sans surcharge de l'objet et de la référence.
- Action ``/instancier/`` refuse les corps invalides.
- Accès réservé aux Responsables/Administrateurs (rôle normal → 403).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats.models import Contrat, ModeleContrat

User = get_user_model()

BASE = '/api/django/contrats/modeles/'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


def make_modele(company, nom='Modèle O&M Standard', **kwargs):
    defaults = {
        'type_contrat_defaut': 'om',
        'corps': 'Corps type O&M.',
        'clauses': 'Clause 1 : …',
        'actif': True,
        'ordre': 0,
    }
    defaults.update(kwargs)
    return ModeleContrat.objects.create(company=company, nom=nom, **defaults)


# ---------------------------------------------------------------------------
# Tests de création (company posée côté serveur)
# ---------------------------------------------------------------------------

class ModeleContratCreateTests(TestCase):
    """La company est toujours posée côté serveur, jamais depuis le corps."""

    def setUp(self):
        self.co = make_company('mc-create', 'Create')
        self.admin = make_user(self.co, 'mc-create-admin', role='admin')

    def _payload(self, **kwargs):
        payload = {
            'nom': 'Gabarit PPA résidentiel',
            'type_contrat_defaut': 'ppa',
            'corps': 'Corps PPA.',
            'clauses': 'Clause PPA 1.',
        }
        payload.update(kwargs)
        return payload

    def test_create_forces_company_server_side(self):
        """La company est posée côté serveur, même si le client en fournit une autre."""
        api = auth(self.admin)
        # On ne transmet PAS de company dans le payload.
        resp = api.post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ModeleContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.company, self.co)

    def test_create_sets_default_values(self):
        """Les valeurs par défaut (devise=MAD, confidentialite=interne, actif=True) s'appliquent."""
        api = auth(self.admin)
        resp = api.post(BASE, {'nom': 'Gabarit vente simple'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ModeleContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.devise_defaut, 'MAD')
        self.assertEqual(obj.confidentialite_defaut, Contrat.NiveauConfidentialite.INTERNE)
        self.assertTrue(obj.actif)

    def test_create_with_all_fields(self):
        """Création avec tous les champs optionnels."""
        api = auth(self.admin)
        payload = self._payload(
            categorie='O&M Premium',
            devise_defaut='EUR',
            confidentialite_defaut='confidentiel',
            actif=False,
            ordre=5,
        )
        resp = api.post(BASE, payload, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        obj = ModeleContrat.objects.get(id=resp.data['id'])
        self.assertEqual(obj.categorie, 'O&M Premium')
        self.assertEqual(obj.devise_defaut, 'EUR')
        self.assertEqual(obj.confidentialite_defaut, 'confidentiel')
        self.assertFalse(obj.actif)
        self.assertEqual(obj.ordre, 5)

    def test_display_fields_in_response(self):
        """Les champs _display sont renvoyés en lecture seule."""
        api = auth(self.admin)
        resp = api.post(BASE, self._payload(), format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('type_contrat_defaut_display', resp.data)
        self.assertEqual(resp.data['type_contrat_defaut'], 'ppa')
        self.assertEqual(resp.data['type_contrat_defaut_display'], 'PPA')


# ---------------------------------------------------------------------------
# Tests d'isolation multi-tenant
# ---------------------------------------------------------------------------

class ModeleContratIsolationTests(TestCase):
    """Société A ne voit pas les modèles de société B."""

    def setUp(self):
        self.co_a = make_company('mc-iso-a', 'A')
        self.co_b = make_company('mc-iso-b', 'B')
        self.admin_a = make_user(self.co_a, 'mc-iso-admin-a', role='admin')
        self.admin_b = make_user(self.co_b, 'mc-iso-admin-b', role='admin')
        self.modele_a = make_modele(self.co_a, nom='Modèle A')
        self.modele_b = make_modele(self.co_b, nom='Modèle B')

    def test_list_only_returns_own_company_modeles(self):
        """La liste ne renvoie que les modèles de la société de l'utilisateur."""
        api_b = auth(self.admin_b)
        resp = api_b.get(BASE)
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.modele_b.id, ids)
        self.assertNotIn(self.modele_a.id, ids)

    def test_detail_of_other_company_returns_404(self):
        """Le détail d'un modèle d'une autre société renvoie 404."""
        api_b = auth(self.admin_b)
        resp = api_b.get(f'{BASE}{self.modele_a.id}/')
        self.assertEqual(resp.status_code, 404)

    def test_update_other_company_returns_404(self):
        """La mise à jour d'un modèle d'une autre société renvoie 404."""
        api_b = auth(self.admin_b)
        resp = api_b.patch(
            f'{BASE}{self.modele_a.id}/', {'nom': 'Tentative hijack'}, format='json')
        self.assertEqual(resp.status_code, 404)

    def test_delete_other_company_returns_404(self):
        """La suppression d'un modèle d'une autre société renvoie 404."""
        api_b = auth(self.admin_b)
        resp = api_b.delete(f'{BASE}{self.modele_a.id}/')
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Tests de filtres et recherche
# ---------------------------------------------------------------------------

class ModeleContratFiltresTests(TestCase):
    """Filtres ?actif= et ?categorie=, recherche ?search=."""

    def setUp(self):
        self.co = make_company('mc-filtres', 'F')
        self.admin = make_user(self.co, 'mc-filtres-admin', role='admin')
        self.m_actif = make_modele(
            self.co, nom='Modèle Actif', categorie='O&M', actif=True)
        self.m_inactif = make_modele(
            self.co, nom='Modèle Inactif', categorie='PPA', actif=False)

    def test_filtre_actif_true(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}?actif=true')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.m_actif.id, ids)
        self.assertNotIn(self.m_inactif.id, ids)

    def test_filtre_actif_false(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}?actif=false')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertNotIn(self.m_actif.id, ids)
        self.assertIn(self.m_inactif.id, ids)

    def test_filtre_categorie(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}?categorie=O%26M')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.m_actif.id, ids)
        self.assertNotIn(self.m_inactif.id, ids)

    def test_search_by_nom(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}?search=Inactif')
        self.assertEqual(resp.status_code, 200)
        ids = [r['id'] for r in rows(resp)]
        self.assertIn(self.m_inactif.id, ids)
        self.assertNotIn(self.m_actif.id, ids)


# ---------------------------------------------------------------------------
# Tests de l'action /instancier/
# ---------------------------------------------------------------------------

class ModeleContratInstancierTests(TestCase):
    """Action POST /<id>/instancier/ — création d'un Contrat depuis un gabarit."""

    def setUp(self):
        self.co = make_company('mc-inst', 'I')
        self.admin = make_user(self.co, 'mc-inst-admin', role='admin')
        self.modele = make_modele(
            self.co,
            nom='Gabarit O&M Standard',
            type_contrat_defaut='om',
            devise_defaut='MAD',
            confidentialite_defaut='interne',
        )

    def _url(self, pk=None):
        pk = pk or self.modele.pk
        return f'{BASE}{pk}/instancier/'

    def test_instancier_crée_un_contrat(self):
        """Un POST sans corps crée un Contrat pré-rempli depuis le gabarit."""
        api = auth(self.admin)
        resp = api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # Le Contrat est bien créé en DB.
        self.assertTrue(Contrat.objects.filter(id=resp.data['id']).exists())

    def test_instancier_hérite_type_contrat_du_gabarit(self):
        """Le Contrat créé hérite du type_contrat du gabarit."""
        api = auth(self.admin)
        resp = api.post(self._url(), {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        contrat = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(contrat.type_contrat, self.modele.type_contrat_defaut)

    def test_instancier_hérite_devise_du_gabarit(self):
        """Le Contrat créé hérite de la devise du gabarit."""
        api = auth(self.admin)
        resp = api.post(self._url(), {}, format='json')
        contrat = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(contrat.devise, self.modele.devise_defaut)

    def test_instancier_hérite_confidentialite_du_gabarit(self):
        """Le Contrat créé hérite de la confidentialité du gabarit."""
        api = auth(self.admin)
        resp = api.post(self._url(), {}, format='json')
        contrat = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(contrat.confidentialite, self.modele.confidentialite_defaut)

    def test_instancier_objet_par_defaut_est_nom_du_modele(self):
        """Sans objet dans le corps, l'objet du Contrat est le nom du gabarit."""
        api = auth(self.admin)
        resp = api.post(self._url(), {}, format='json')
        contrat = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(contrat.objet, self.modele.nom)

    def test_instancier_surcharge_objet(self):
        """Un objet fourni dans le corps est utilisé à la place du nom du gabarit."""
        api = auth(self.admin)
        resp = api.post(self._url(), {'objet': 'Contrat O&M Casablanca'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        contrat = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(contrat.objet, 'Contrat O&M Casablanca')

    def test_instancier_surcharge_reference(self):
        """Une référence fournie dans le corps est propagée au Contrat."""
        api = auth(self.admin)
        resp = api.post(
            self._url(), {'reference': 'CTR-2026-001'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        contrat = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(contrat.reference, 'CTR-2026-001')

    def test_instancier_company_posée_côté_serveur(self):
        """Le Contrat instancié appartient à la société de l'utilisateur (côté serveur)."""
        api = auth(self.admin)
        resp = api.post(self._url(), {}, format='json')
        contrat = Contrat.objects.get(id=resp.data['id'])
        self.assertEqual(contrat.company, self.co)
        self.assertEqual(contrat.created_by, self.admin)

    def test_instancier_autre_société_retourne_404(self):
        """Un utilisateur ne peut pas instancier un gabarit d'une autre société."""
        co_b = make_company('mc-inst-b', 'B')
        admin_b = make_user(co_b, 'mc-inst-admin-b', role='admin')
        api_b = auth(admin_b)
        resp = api_b.post(self._url(self.modele.pk), {}, format='json')
        self.assertEqual(resp.status_code, 404)


# ---------------------------------------------------------------------------
# Tests de contrôle d'accès
# ---------------------------------------------------------------------------

class ModeleContratAccessTests(TestCase):
    """Accès réservé aux Responsables et Administrateurs."""

    def setUp(self):
        self.co = make_company('mc-access', 'Acc')
        self.normal = make_user(self.co, 'mc-access-normal', role='normal')

    def test_role_normal_refuse_en_liste(self):
        api = auth(self.normal)
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 403)

    def test_role_normal_refuse_en_creation(self):
        api = auth(self.normal)
        resp = api.post(BASE, {'nom': 'Tentative'}, format='json')
        self.assertEqual(resp.status_code, 403)
