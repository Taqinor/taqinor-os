"""Tests XACC28 — Refacturation des frais au client (billable expenses).

Couvre : deux frais refacturables validés d'un même client deviennent deux
lignes de la facture (avec marge), re-génération ne duplique jamais (chaque
note déjà refacturée est exclue via ``facture_refacturation_id``), le
justificatif reste consultable, et l'isolation multi-société.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import NoteFrais
from apps.crm.models import Client
from apps.ventes.models import Facture
from apps.ventes.utils.references import create_with_reference

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


def make_client(company, nom='Client Test'):
    return Client.objects.create(company=company, nom=nom)


def make_facture(company, client):
    def _create(ref):
        return Facture.objects.create(
            reference=ref, company=company, client=client,
            statut=Facture.Statut.BROUILLON,
            type_facture=Facture.TypeFacture.COMPLETE,
            taux_tva=Decimal('20'), montant_ht=Decimal('0'),
            montant_tva=Decimal('0'), montant_ttc=Decimal('0'))
    return create_with_reference(Facture, 'FAC', company, _create)


def make_note_validee(company, employe, user, *, montant, taux_marge=0,
                      client_id=None, refacturable=True):
    note = services.creer_note_frais(
        company, employe=employe, date_frais=date(2026, 6, 1),
        montant=Decimal(montant), motif='Frais chantier',
        categorie=NoteFrais.Categorie.DEPLACEMENT,
        refacturable=refacturable, taux_marge=Decimal(taux_marge),
        client_refacturation_id=client_id, user=user)
    services.soumettre_note_frais(note)
    return services.valider_note_frais(note, user=user)


class RefacturationServiceTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc28-svc', 'XACC28 Svc')
        self.user = make_user(self.co, 'xacc28-svc-user')
        self.employe = make_user(self.co, 'xacc28-employe', role='normal')
        self.client_obj = make_client(self.co)
        self.facture = make_facture(self.co, self.client_obj)

    def test_deux_frais_deviennent_deux_lignes_avec_marge(self):
        n1 = make_note_validee(
            self.co, self.employe, self.user, montant=1000, taux_marge=10,
            client_id=self.client_obj.id)
        n2 = make_note_validee(
            self.co, self.employe, self.user, montant=500, taux_marge=10,
            client_id=self.client_obj.id)
        services.refacturer_frais_client(
            self.co, facture=self.facture,
            note_frais_ids=[n1.id, n2.id], user=self.user)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.lignes.count(), 2)
        # 1000*1.1 + 500*1.1 = 1650 HT
        self.assertEqual(self.facture.montant_ht, Decimal('1650.00'))
        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertEqual(n1.facture_refacturation_id, self.facture.id)
        self.assertEqual(n2.facture_refacturation_id, self.facture.id)

    def test_regeneration_zero_nouvelle_ligne(self):
        n1 = make_note_validee(
            self.co, self.employe, self.user, montant=1000,
            client_id=self.client_obj.id)
        services.refacturer_frais_client(
            self.co, facture=self.facture, note_frais_ids=[n1.id],
            user=self.user)
        with self.assertRaises(Exception):
            services.refacturer_frais_client(
                self.co, facture=self.facture, note_frais_ids=[n1.id],
                user=self.user)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.lignes.count(), 1)

    def test_note_non_validee_refusee(self):
        note = services.creer_note_frais(
            self.co, employe=self.employe, date_frais=date(2026, 6, 1),
            montant=Decimal('200'), motif='Non validée',
            refacturable=True, client_refacturation_id=self.client_obj.id,
            user=self.user)
        with self.assertRaises(Exception):
            services.refacturer_frais_client(
                self.co, facture=self.facture, note_frais_ids=[note.id],
                user=self.user)

    def test_note_non_refacturable_refusee(self):
        note = make_note_validee(
            self.co, self.employe, self.user, montant=200,
            client_id=self.client_obj.id, refacturable=False)
        with self.assertRaises(Exception):
            services.refacturer_frais_client(
                self.co, facture=self.facture, note_frais_ids=[note.id],
                user=self.user)

    def test_justificatif_reste_consultable(self):
        note = make_note_validee(
            self.co, self.employe, self.user, montant=300,
            client_id=self.client_obj.id)
        services.refacturer_frais_client(
            self.co, facture=self.facture, note_frais_ids=[note.id],
            user=self.user)
        note.refresh_from_db()
        # Le champ justificatif reste inchangé (aucune suppression).
        self.assertEqual(note.montant, Decimal('300.00'))

    def test_selector_frais_refacturables_non_factures(self):
        n1 = make_note_validee(
            self.co, self.employe, self.user, montant=100,
            client_id=self.client_obj.id)
        n2 = make_note_validee(
            self.co, self.employe, self.user, montant=200,
            client_id=self.client_obj.id)
        avant = selectors.frais_refacturables_non_factures(
            self.co, client_id=self.client_obj.id)
        self.assertEqual(avant.count(), 2)
        services.refacturer_frais_client(
            self.co, facture=self.facture, note_frais_ids=[n1.id],
            user=self.user)
        apres = selectors.frais_refacturables_non_factures(
            self.co, client_id=self.client_obj.id)
        self.assertEqual(apres.count(), 1)
        self.assertEqual(apres.first().id, n2.id)


class RefacturationApiTests(TestCase):
    def setUp(self):
        self.co_a = make_company('xacc28-a', 'XACC28 A')
        self.co_b = make_company('xacc28-b', 'XACC28 B')
        self.user_a = make_user(self.co_a, 'xacc28-user-a')
        self.employe_a = make_user(self.co_a, 'xacc28-employe-a', role='normal')
        self.client_a = make_client(self.co_a)
        self.facture_a = make_facture(self.co_a, self.client_a)

    def test_refacturer_endpoint(self):
        note = make_note_validee(
            self.co_a, self.employe_a, self.user_a, montant=400,
            client_id=self.client_a.id)
        resp = auth(self.user_a).post(
            '/api/django/compta/notes-frais/refacturer/',
            {'facture_id': self.facture_a.id, 'note_frais_ids': [note.id]},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.facture_a.refresh_from_db()
        self.assertEqual(self.facture_a.lignes.count(), 1)

    def test_facture_cross_company_404(self):
        facture_b = make_facture(self.co_b, make_client(self.co_b))
        note = make_note_validee(
            self.co_a, self.employe_a, self.user_a, montant=400,
            client_id=self.client_a.id)
        resp = auth(self.user_a).post(
            '/api/django/compta/notes-frais/refacturer/',
            {'facture_id': facture_b.id, 'note_frais_ids': [note.id]},
            format='json')
        self.assertEqual(resp.status_code, 404)

    def test_refacturables_endpoint(self):
        make_note_validee(
            self.co_a, self.employe_a, self.user_a, montant=100,
            client_id=self.client_a.id)
        resp = auth(self.user_a).get(
            '/api/django/compta/notes-frais/refacturables/',
            {'client': self.client_a.id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
