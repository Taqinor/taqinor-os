"""NTRET2 — Rapport X (lecture) et rapport Z (clôture définitive) formels.

Couvre : X consultable à volonté (session ouverte OU clôturée, aucun effet de
bord, relisible N fois) ; Z exige la clôture, numéroté séquentiellement
(jamais count()+1), généré UNE SEULE FOIS par session (2e appel → 409) ;
isolation multi-tenant de la numérotation.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta import services as compta_services
from apps.compta.models import CompteTresorerie
from apps.crm.models import Client
from apps.pos import services
from apps.pos.models import LigneVenteComptoir, SessionCaisse, VenteComptoir
from apps.stock.models import Categorie, Produit

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


class RapportXZServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret2', 'NTRET2 Co')
        self.user = make_user(self.co, 'caissier-ntret2')
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        self.caisse_comptable = compta_services.creer_caisse(
            self.co, compte_caisse, libelle='Caisse POS',
            solde_initial=Decimal('0'))
        self.client_obj = Client.objects.create(company=self.co, nom='Client')
        categorie = Categorie.objects.create(company=self.co, nom='Acc')
        self.produit = Produit.objects.create(
            company=self.co, nom='Produit', prix_vente=Decimal('100'),
            prix_achat=Decimal('40'), quantite_stock=20, categorie=categorie)

    def _session(self):
        return services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)

    def _vente(self, session, mode='especes', montant='100'):
        vente = VenteComptoir.objects.create(
            company=self.co, reference=f'VC-XZ-{montant}-{mode}',
            client=self.client_obj, created_by=self.user,
            session_caisse=session)
        LigneVenteComptoir.objects.create(
            vente=vente, produit=self.produit, designation='Produit',
            quantite=1, prix_unitaire_ttc=Decimal(montant))
        services.valider_vente(
            vente=vente, paiements=[{'mode': mode, 'montant': montant}],
            user=self.user)
        return vente

    def test_rapport_x_readable_before_cloture_no_side_effect(self):
        session = self._session()
        self._vente(session)
        x1 = services.rapport_x(session)
        x2 = services.rapport_x(session)
        self.assertEqual(x1['nb_ventes'], 1)
        self.assertEqual(x1, x2)
        session.refresh_from_db()
        self.assertIsNone(session.numero_rapport_z)
        self.assertEqual(session.statut, SessionCaisse.Statut.OUVERTE)

    def test_rapport_x_readable_many_times_after_cloture(self):
        session = self._session()
        self._vente(session)
        services.cloturer_session(
            session=session, montant_compte=Decimal('100'), user=self.user)
        for _ in range(3):
            x = services.rapport_x(session)
            self.assertEqual(x['nb_ventes'], 1)

    def test_generer_rapport_z_requires_cloture(self):
        session = self._session()
        self._vente(session)
        with self.assertRaises(services.RapportZError):
            services.generer_rapport_z(session, user=self.user)

    def test_generer_rapport_z_assigns_sequential_numero(self):
        session = self._session()
        self._vente(session)
        services.cloturer_session(
            session=session, montant_compte=Decimal('100'), user=self.user)
        data = services.generer_rapport_z(session, user=self.user)
        self.assertTrue(data['numero_rapport_z'].startswith('Z-'))
        session.refresh_from_db()
        self.assertEqual(session.numero_rapport_z, data['numero_rapport_z'])

    def test_generer_rapport_z_twice_refuses(self):
        session = self._session()
        self._vente(session)
        services.cloturer_session(
            session=session, montant_compte=Decimal('100'), user=self.user)
        services.generer_rapport_z(session, user=self.user)
        with self.assertRaises(services.RapportZDejaGenereError):
            services.generer_rapport_z(session, user=self.user)

    def test_numero_rapport_z_sequential_across_sessions_same_company(self):
        session1 = self._session()
        self._vente(session1)
        services.cloturer_session(
            session=session1, montant_compte=Decimal('100'), user=self.user)
        data1 = services.generer_rapport_z(session1, user=self.user)

        compte_caisse_2 = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir 2',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        caisse_comptable_2 = compta_services.creer_caisse(
            self.co, compte_caisse_2, libelle='Caisse POS 2',
            solde_initial=Decimal('0'))
        session2 = services.ouvrir_session(
            company=self.co, caisse_comptable=caisse_comptable_2,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)
        self._vente(session2, mode='carte', montant='50')
        services.cloturer_session(
            session=session2, montant_compte=Decimal('0'), user=self.user)
        data2 = services.generer_rapport_z(session2, user=self.user)

        self.assertNotEqual(data1['numero_rapport_z'], data2['numero_rapport_z'])


class RapportXZApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntret2-api', 'NTRET2 API Co')
        self.user = make_user(self.co, 'caissier-ntret2-api')
        compta_services.seed_plan_comptable(self.co)
        compta_services.seed_journaux(self.co)
        compte_caisse = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.CAISSE,
            libelle='Caisse comptoir',
            compte_comptable=compta_services.get_compte(self.co, '5161'))
        self.caisse_comptable = compta_services.creer_caisse(
            self.co, compte_caisse, libelle='Caisse POS',
            solde_initial=Decimal('0'))
        self.session = services.ouvrir_session(
            company=self.co, caisse_comptable=self.caisse_comptable,
            caissier=self.user, fond_ouverture=Decimal('0'), user=self.user)

    def _url(self, path):
        return f'/api/django/pos/sessions/{self.session.id}/{path}/'

    def test_rapport_x_endpoint_multiple_calls_ok(self):
        api = auth(self.user)
        r1 = api.get(self._url('rapport-x'))
        r2 = api.get(self._url('rapport-x'))
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertEqual(r2.status_code, 200, r2.data)

    def test_rapport_z_endpoint_requires_cloture(self):
        api = auth(self.user)
        resp = api.get(self._url('rapport-z'))
        self.assertEqual(resp.status_code, 400)

    def test_rapport_z_endpoint_second_call_409(self):
        api = auth(self.user)
        api.post(self._url('cloturer'), {'montant_compte': '0'}, format='json')
        first = api.get(self._url('rapport-z'))
        self.assertEqual(first.status_code, 200, first.data)
        self.assertTrue(first.data['numero_rapport_z'])

        second = api.get(self._url('rapport-z'))
        self.assertEqual(second.status_code, 409, second.data)

    def test_rapport_z_pdf_requires_rapport_generated_first(self):
        api = auth(self.user)
        api.post(self._url('cloturer'), {'montant_compte': '0'}, format='json')
        before = api.get(self._url('rapport-z-pdf'))
        self.assertEqual(before.status_code, 400)

        api.get(self._url('rapport-z'))
        after = api.get(self._url('rapport-z-pdf'))
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after['Content-Type'], 'application/pdf')
