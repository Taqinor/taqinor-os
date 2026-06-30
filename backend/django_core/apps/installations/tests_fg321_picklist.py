"""
FG321 — Bons de prélèvement (pick list) par chantier.

Couvre :
  * génération via l'API : référence (`PICK-`) + société + `created_by` posés
    serveur ; une ligne par réservation active, ordonnée par casier ;
  * un chantier d'une autre société rejeté ;
  * cocher une ligne (`preleve`) ;
  * cycle démarrer/terminer ;
  * scope société + barrière de rôle.

Run :
    python manage.py test apps.installations.tests_fg321_picklist -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    Installation, StockReservation, BinLocation, BinAffectation,
    PickList, PickListLigne,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'fg321-co-{n}', defaults={'nom': nom or f'FG321 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable', username=None):
    return User.objects.create_user(
        username=username or f'fg321-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Panneau 550W'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=1500, prix_achat=0)


def make_installation(company, ref='PK1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'pk-{company.id}-{ref}@example.invalid')
    return Installation.objects.create(
        company=company, reference=ref, client=client,
        statut=Installation.Statut.RECEPTIONNE,
        type_installation='residentiel',
        puissance_installee_kwc=Decimal('6.5'))


class TestPickListGeneration(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.emp = make_emplacement(self.company)
        self.inst = make_installation(self.company)
        self.p1 = make_produit(self.company, 'Panneau')
        self.p2 = make_produit(self.company, 'Câble')
        StockReservation.objects.create(
            company=self.company, installation=self.inst,
            produit=self.p1, quantite=12)
        StockReservation.objects.create(
            company=self.company, installation=self.inst,
            produit=self.p2, quantite=3)
        # p1 a un casier à l'ordre 5, p2 aucun (passe en dernier)
        bin5 = BinLocation.objects.create(
            company=self.company, emplacement=self.emp, code='A-1-1', ordre=5)
        BinAffectation.objects.create(
            company=self.company, bin=bin5, produit=self.p1, quantite=20)

    def test_generate_creates_ordered_lines(self):
        resp = self.api.post(f'{BASE}/pick-lists/', {
            'installation': self.inst.id, 'company': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        pick = PickList.objects.get(id=resp.data['id'])
        self.assertEqual(pick.company_id, self.company.id)
        self.assertEqual(pick.created_by_id, self.user.id)
        self.assertTrue(pick.reference.startswith('PICK-'))
        lignes = list(pick.lignes.all())
        self.assertEqual(len(lignes), 2)
        # p1 (ordre 5) avant p2 (ordre 999999)
        self.assertEqual(lignes[0].produit_id, self.p1.id)
        self.assertEqual(lignes[0].quantite_demandee, 12)
        self.assertEqual(lignes[1].produit_id, self.p2.id)

    def test_installation_other_company_rejected(self):
        other = make_company()
        inst_other = make_installation(other, ref='OTH')
        resp = self.api.post(f'{BASE}/pick-lists/', {
            'installation': inst_other.id,
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_coche_ligne(self):
        pick = PickList.objects.create(
            company=self.company, installation=self.inst, reference='PICK-X')
        ligne = PickListLigne.objects.create(
            pick_list=pick, produit=self.p1, quantite_demandee=12)
        resp = self.api.patch(
            f'{BASE}/pick-list-lignes/{ligne.id}/',
            {'preleve': True, 'quantite_prelevee': 12}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne.refresh_from_db()
        self.assertTrue(ligne.preleve)
        self.assertEqual(ligne.quantite_prelevee, 12)

    def test_cycle_demarrer_terminer(self):
        pick = PickList.objects.create(
            company=self.company, installation=self.inst, reference='PICK-Y')
        r1 = self.api.post(f'{BASE}/pick-lists/{pick.id}/demarrer/', {},
                           format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        pick.refresh_from_db()
        self.assertEqual(pick.statut, PickList.Statut.EN_COURS)
        r2 = self.api.post(f'{BASE}/pick-lists/{pick.id}/terminer/', {},
                           format='json')
        self.assertEqual(r2.status_code, 200, r2.content)
        pick.refresh_from_db()
        self.assertEqual(pick.statut, PickList.Statut.TERMINE)


class TestScopingAndRoles(TestCase):
    def setUp(self):
        self.company = make_company()
        self.other = make_company()
        self.inst = make_installation(self.company)

    def test_commercial_cannot_generate(self):
        commercial = make_user(self.company, role='commercial')
        api = auth(commercial)
        resp = api.post(f'{BASE}/pick-lists/', {
            'installation': self.inst.id,
        }, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_other_company_cannot_see(self):
        PickList.objects.create(
            company=self.company, installation=self.inst, reference='PICK-Z')
        api = auth(make_user(self.other))
        resp = api.get(f'{BASE}/pick-lists/')
        results = resp.data.get('results', resp.data)
        self.assertEqual(len(results), 0)
