"""ODX18 — App Facturation, étape 2 (vues/urls/recouvrement).

Les ViewSets/vues de facturation (Facture, Paiement, Avoir, FollowupLevel +
recouvrement) sont désormais servis SOUS DEUX préfixes : les nouvelles routes
``/api/django/facturation/…`` ET les routes historiques ``/api/django/ventes/…``
conservées à l'identique (mêmes classes, scoping société côté serveur, aucun
client cassé). Les PDFs facture restent le legacy (règle #4 — seul le devis
passe par /proposal).

Run :
    python manage.py test apps.facturation.tests.test_odx18_facturation_split -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
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


def make_client(company, email='odx18@example.com'):
    from apps.crm.models import Client
    return Client.objects.create(
        company=company, nom='ODX18', prenom='Client', email=email,
        telephone='+212600000018', adresse='Casablanca')


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data \
        else data
    return [x['id'] for x in rows]


class TestODX18ModelsShim(TestCase):
    def test_facturation_models_are_the_ventes_shim(self):
        # ODX17 a déplacé l'ÉTAT vers apps.facturation ; ventes garde un shim de
        # ré-export : la MÊME classe est visible des deux côtés.
        from apps.facturation.models import Facture, Paiement, Avoir
        from apps.ventes.models import (
            Facture as VF, Paiement as VP, Avoir as VA)
        self.assertIs(Facture, VF)
        self.assertIs(Paiement, VP)
        self.assertIs(Avoir, VA)
        # Tables physiques préservées (ventes_*), app_label = facturation.
        self.assertEqual(Facture._meta.db_table, 'ventes_facture')
        self.assertEqual(Facture._meta.app_label, 'facturation')


class TestODX18Routes(TestCase):
    def setUp(self):
        self.company = make_company('odx18-co', 'ODX18 Co')
        self.user = make_user(self.company, 'odx18_resp')
        self.client_obj = make_client(self.company)
        self.api = auth(self.user)

    def _facture(self, reference):
        from apps.facturation.models import Facture
        return Facture.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'))

    def test_new_facturation_route_lists_scoped(self):
        f = self._facture('FA-2026-0001')
        r = self.api.get('/api/django/facturation/factures/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(f.id, ids_of(r))

    def test_legacy_ventes_route_serves_same_data(self):
        f = self._facture('FA-2026-0002')
        r = self.api.get('/api/django/ventes/factures/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn(f.id, ids_of(r))

    def test_recouvrement_dual_prefix_balance_agee(self):
        # La balance âgée est servie sous les deux préfixes à l'identique.
        r_new = self.api.get('/api/django/facturation/balance-agee/')
        r_old = self.api.get('/api/django/ventes/balance-agee/')
        self.assertEqual(r_new.status_code, 200, r_new.data)
        self.assertEqual(r_old.status_code, 200, r_old.data)

    def test_niveaux_relance_dual_prefix(self):
        r_new = self.api.get('/api/django/facturation/niveaux-relance/')
        r_old = self.api.get('/api/django/ventes/niveaux-relance/')
        self.assertEqual(r_new.status_code, 200, r_new.data)
        self.assertEqual(r_old.status_code, 200, r_old.data)

    def test_deux_prefixes_reponses_octet_pour_octet(self):
        """ODX18 (étape 2, vues déplacées) — chaque route servie sous les deux
        préfixes renvoie EXACTEMENT les mêmes octets (même statut, même
        corps) : le déplacement des vues n'a rien changé."""
        f = self._facture('FA-2026-0003')
        suffixes = [
            'factures/', f'factures/{f.id}/', 'factures-lignes/', 'paiements/',
            'avoirs/', 'notes-debit/', 'niveaux-relance/', 'relances/',
            'balance-agee/', f'clients/{self.client_obj.id}/releve/',
        ]
        for suffixe in suffixes:
            with self.subTest(route=suffixe):
                r_old = self.api.get('/api/django/ventes/' + suffixe)
                r_new = self.api.get('/api/django/facturation/' + suffixe)
                self.assertEqual(r_old.status_code, 200, r_old.content)
                self.assertEqual(r_new.status_code, r_old.status_code)
                self.assertEqual(r_new.content, r_old.content)

    def test_vues_deplacees_memes_objets_sous_les_deux_prefixes(self):
        """ODX18 — les classes vivent dans apps.facturation ; les anciens
        chemins d'import ventes renvoient les MÊMES objets (aucune copie)."""
        from django.urls import resolve
        from apps.facturation import recouvrement
        from apps.facturation.views import FactureViewSet, PaiementViewSet
        from apps.ventes import recouvrement as ancien_recouvrement
        from apps.ventes.views import (
            FactureViewSet as AncienFacture, PaiementViewSet as AncienPaiement)
        self.assertIs(AncienFacture, FactureViewSet)
        self.assertIs(AncienPaiement, PaiementViewSet)
        self.assertEqual(FactureViewSet.__module__, 'apps.facturation.views.facture')
        self.assertIs(ancien_recouvrement.relances_list, recouvrement.relances_list)
        for suffixe in ('factures/1/ubl/', 'factures/1/dgi-export/', 'relances/'):
            with self.subTest(route=suffixe):
                v_old = resolve('/api/django/ventes/' + suffixe).func
                v_new = resolve('/api/django/facturation/' + suffixe).func
                self.assertIs(getattr(v_old, 'cls', v_old), getattr(v_new, 'cls', v_new))

    def test_remises_encaissement_route_historique_servie(self):
        """ODX18 (suite) — la remise d'encaissement (XFSM19) a déménagé dans
        apps.facturation.views ; sa route historique ventes/ la sert toujours,
        par la classe déménagée."""
        from django.urls import resolve
        from apps.facturation.views import RemiseEncaissementViewSet
        r = self.api.get('/api/django/ventes/remises-encaissement/')
        self.assertEqual(r.status_code, 200, r.content)
        vue = resolve('/api/django/ventes/remises-encaissement/').func
        self.assertIs(vue.cls, RemiseEncaissementViewSet)

    def test_tenant_isolation_on_new_route(self):
        other = make_company('odx18-other', 'Autre Co')
        other_client = make_client(other, email='other18@example.com')
        from apps.facturation.models import Facture
        Facture.objects.create(
            company=other, reference='FA-X', client=other_client,
            statut=Facture.Statut.EMISE)
        r = self.api.get('/api/django/facturation/factures/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(ids_of(r), [])


class TestODX18DemenagementSuite(SimpleTestCase):
    """ODX18 (suite) — sérialiseurs, avoirs/notes de débit, remises
    d'encaissement et façade de services : les anciens chemins ventes renvoient
    les MÊMES objets que apps.facturation (déplacement pur, aucune copie)."""

    def test_serialiseurs_deplaces_et_reexportes(self):
        from apps.facturation import serializers as nouveaux
        from apps.ventes import serializers_facturation as anciens
        for nom in ('FactureSerializer', 'FactureWriteSerializer',
                    'PaiementSerializer', 'AvoirSerializer',
                    'NoteDebitSerializer', 'RemiseEncaissementSerializer',
                    'MandatPaiementSerializer', 'FactureListeSerializer'):
            with self.subTest(nom=nom):
                cls = getattr(nouveaux, nom)
                self.assertIs(getattr(anciens, nom), cls)
                self.assertEqual(cls.__module__, 'apps.facturation.serializers')
        # Le bon de commande relève de ventes : il n'a pas bougé.
        self.assertEqual(anciens.BonCommandeSerializer.__module__,
                         'apps.ventes.serializers_facturation')
        self.assertFalse(hasattr(nouveaux, 'BonCommandeSerializer'))

    def test_vues_avoir_et_remise_deplacees(self):
        from apps.facturation import views as nouvelles
        from apps.ventes import views as anciennes
        attendus = {
            'AvoirViewSet': 'apps.facturation.views.avoir',
            'NoteDebitViewSet': 'apps.facturation.views.avoir',
            'RemiseEncaissementViewSet':
                'apps.facturation.views.remise_encaissement',
        }
        for nom, module in attendus.items():
            with self.subTest(nom=nom):
                cls = getattr(nouvelles, nom)
                self.assertIs(getattr(anciennes, nom), cls)
                self.assertEqual(cls.__module__, module)

    def test_avoirs_notes_debit_meme_classe_sous_les_deux_prefixes(self):
        from django.urls import resolve
        for suffixe in ('avoirs/', 'avoirs/1/', 'notes-debit/', 'notes-debit/1/'):
            with self.subTest(route=suffixe):
                v_old = resolve('/api/django/ventes/' + suffixe).func
                v_new = resolve('/api/django/facturation/' + suffixe).func
                self.assertIs(v_old.cls, v_new.cls)
                self.assertEqual(v_old.actions, v_new.actions)

    def test_facade_services_memes_objets_que_ventes(self):
        from apps.facturation import services as facade
        from apps.ventes import services as ventes_services
        self.assertTrue(facade.__all__)
        for nom in facade.__all__:
            with self.subTest(nom=nom):
                self.assertIs(getattr(facade, nom),
                              getattr(ventes_services, nom))
        # « Facturer la vente » (VNT26) n'est jamais ré-exporté par la façade.
        self.assertFalse(hasattr(facade, 'facturer_vente'))
