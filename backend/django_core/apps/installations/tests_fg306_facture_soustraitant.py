"""
FG306 — Factures & règlements des sous-traitants chantier (AP dédiée).

Couvre :
  * création d'une facture sous-traitant via l'API avec société + ``created_by``
    posés CÔTÉ SERVEUR (jamais lus du corps) ;
  * l'injection de ``company``/``statut`` dans le corps est ignorée ;
  * les FK ``sous_traitant`` / ``ordre`` / ``chantier`` doivent appartenir à la
    MÊME société (sinon rejet) ;
  * le reflet automatique du statut au fil des paiements (à payer → partielle →
    payée) ;
  * un paiement ne peut pas dépasser le reste à payer, ni régler une facture
    annulée ;
  * la suppression d'un paiement rafraîchit le statut de la facture ;
  * le scope société (la société B ne voit pas les factures de A) ;
  * la barrière de rôle (lecture & écriture responsable/admin — montants
    INTERNES, jamais lecture libre).

Run :
    python manage.py test apps.installations.tests_fg306_facture_soustraitant -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import (
    FactureSousTraitant, PaiementSousTraitant, SousTraitant,
    Installation,
)

User = get_user_model()
_seq = itertools.count(1)

BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg306-co-{n}', defaults={'nom': nom or f'FG306 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg306-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_client(company):
    from apps.crm.models import Client
    n = next(_seq)
    return Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'fg306-{company.id}-{n}@example.invalid')


def make_chantier(company):
    n = next(_seq)
    return Installation.objects.create(
        company=company, reference=f'CH-{company.id}-{n}',
        client=make_client(company))


def make_sous_traitant(company, raison='Terrasol SARL', metier='terrassement'):
    return SousTraitant.objects.create(
        company=company, raison_sociale=raison, metier=metier)


class TestFactureCreation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)
        self.chantier = make_chantier(self.company)

    def test_create_server_side_company(self):
        r = self.api.post(f'{BASE}/factures-sous-traitant/', {
            'sous_traitant': self.st.id,
            'chantier': self.chantier.id,
            'numero': 'F-2026-001',
            'montant_ht': '40000', 'montant_tva': '8000',
            'montant_ttc': '48000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        fac = FactureSousTraitant.objects.get(id=r.data['id'])
        self.assertEqual(fac.company_id, self.company.id)
        self.assertEqual(fac.created_by_id, self.user.id)
        self.assertEqual(fac.statut, FactureSousTraitant.Statut.BROUILLON)

    def test_injected_company_statut_ignored(self):
        autre = make_company()
        r = self.api.post(f'{BASE}/factures-sous-traitant/', {
            'company': autre.id,
            'statut': 'payee',
            'sous_traitant': self.st.id,
            'montant_ttc': '1000',
        })
        self.assertEqual(r.status_code, 201, r.data)
        fac = FactureSousTraitant.objects.get(id=r.data['id'])
        self.assertEqual(fac.company_id, self.company.id)
        self.assertEqual(fac.statut, FactureSousTraitant.Statut.BROUILLON)

    def test_foreign_sous_traitant_rejected(self):
        autre = make_company()
        st_autre = make_sous_traitant(autre)
        r = self.api.post(f'{BASE}/factures-sous-traitant/', {
            'sous_traitant': st_autre.id, 'montant_ttc': '1000',
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestPaiementReflectsStatut(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)
        self.fac = FactureSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st,
            montant_ttc=1000,
            statut=FactureSousTraitant.Statut.A_PAYER)

    def test_partial_then_full_payment(self):
        r1 = self.api.post(f'{BASE}/paiements-sous-traitant/', {
            'facture': self.fac.id, 'montant': '400',
        })
        self.assertEqual(r1.status_code, 201, r1.data)
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut, FactureSousTraitant.Statut.PARTIELLE)

        r2 = self.api.post(f'{BASE}/paiements-sous-traitant/', {
            'facture': self.fac.id, 'montant': '600',
        })
        self.assertEqual(r2.status_code, 201, r2.data)
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut, FactureSousTraitant.Statut.PAYEE)

    def test_payment_over_remaining_rejected(self):
        r = self.api.post(f'{BASE}/paiements-sous-traitant/', {
            'facture': self.fac.id, 'montant': '1500',
        })
        self.assertEqual(r.status_code, 400, r.data)

    def test_delete_payment_reverts_statut(self):
        r = self.api.post(f'{BASE}/paiements-sous-traitant/', {
            'facture': self.fac.id, 'montant': '1000',
        })
        pid = r.data['id']
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut, FactureSousTraitant.Statut.PAYEE)
        d = self.api.delete(f'{BASE}/paiements-sous-traitant/{pid}/')
        self.assertEqual(d.status_code, 204)
        self.fac.refresh_from_db()
        self.assertEqual(self.fac.statut, FactureSousTraitant.Statut.A_PAYER)

    def test_cannot_pay_cancelled(self):
        self.fac.statut = FactureSousTraitant.Statut.ANNULEE
        self.fac.save(update_fields=['statut'])
        r = self.api.post(f'{BASE}/paiements-sous-traitant/', {
            'facture': self.fac.id, 'montant': '100',
        })
        self.assertEqual(r.status_code, 400, r.data)


class TestLifecycleAndScope(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.st = make_sous_traitant(self.company)

    def test_annuler_blocked_when_paid(self):
        fac = FactureSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, montant_ttc=500,
            statut=FactureSousTraitant.Statut.A_PAYER)
        PaiementSousTraitant.objects.create(
            company=self.company, facture=fac, montant=200)
        r = self.api.post(
            f'{BASE}/factures-sous-traitant/{fac.id}/annuler/')
        self.assertEqual(r.status_code, 400, r.data)

    def test_scope_isolation(self):
        other = make_company()
        st_o = make_sous_traitant(other)
        FactureSousTraitant.objects.create(
            company=other, sous_traitant=st_o, montant_ttc=1)
        FactureSousTraitant.objects.create(
            company=self.company, sous_traitant=self.st, montant_ttc=1)
        r = self.api.get(f'{BASE}/factures-sous-traitant/')
        self.assertEqual(r.status_code, 200, r.data)
        results = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(len(results), 1)

    def test_read_requires_role(self):
        viewer = make_user(self.company, role='normal')
        api = auth(viewer)
        r = api.get(f'{BASE}/factures-sous-traitant/')
        self.assertEqual(r.status_code, 403, r.data)
