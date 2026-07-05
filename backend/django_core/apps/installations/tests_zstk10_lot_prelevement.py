"""ZSTK10 — Regroupement de prélèvements en lot (batch transfer, Odoo parity).

Les pick-lists (FG321) sont générées par chantier ; Odoo permet de grouper
plusieurs pickings en un « Batch Transfer ». Couvre :

  * grouper 3 pick-lists crée un lot dont les lignes sont triées par casier ;
  * cocher une ligne du lot propage à la pick-list source ;
  * clôturer le lot n'est possible que si toutes les pick-lists sont
    soldées ;
  * référence sans trou (`create_with_reference`) ;
  * pick-lists de dépôts différents refusées ;
  * isolation tenant.

Run :
    python manage.py test apps.installations.tests_zstk10_lot_prelevement -v2
"""
import itertools

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    Installation, PickList, PickListLigne, BinLocation, LotPrelevement,
)
from apps.installations.services import (
    creer_lot_prelevement, lignes_lot_prelevement, cocher_ligne_lot,
    cloturer_lot_prelevement,
)

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'zstk10-co-{n}', defaults={'nom': f'ZSTK10 Co {n}'})
    return company


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'zstk10-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_installation(company):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='ZSTK10',
        email=f'zstk10-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-ZSTK10-{n}', client=client,
        statut=Installation.Statut.PLANIFIE)


def make_emplacement(company, nom='Dépôt'):
    from apps.stock.models import EmplacementStock
    return EmplacementStock.objects.create(company=company, nom=nom)


def make_produit(company, nom='Onduleur'):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, prix_vente=100, prix_achat=0)


def make_picklist_avec_bin(company, installation, emplacement, ordre):
    n = next(_seq)
    pl = PickList.objects.create(
        company=company, installation=installation, reference=f'PICK-{n}')
    bin_loc = BinLocation.objects.create(
        company=company, emplacement=emplacement, code=f'BIN-{n}', ordre=ordre)
    produit = make_produit(company, nom=f'Produit-{n}')
    PickListLigne.objects.create(
        pick_list=pl, produit=produit, designation=produit.nom,
        bin=bin_loc, quantite_demandee=5, ordre=ordre)
    return pl


class TestCreerLotPrelevement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)
        self.emp = make_emplacement(self.company)
        # 3 pick-lists, casiers d'ordre décroissant pour vérifier le tri.
        self.pl3 = make_picklist_avec_bin(
            self.company, self.inst, self.emp, ordre=30)
        self.pl1 = make_picklist_avec_bin(
            self.company, self.inst, self.emp, ordre=10)
        self.pl2 = make_picklist_avec_bin(
            self.company, self.inst, self.emp, ordre=20)

    def test_grouper_3_picklists_trie_par_casier(self):
        lot = creer_lot_prelevement(
            self.company, [self.pl3.id, self.pl1.id, self.pl2.id], self.user)
        self.assertEqual(lot.pick_lists.count(), 3)
        lignes = lignes_lot_prelevement(lot)
        self.assertEqual(len(lignes), 3)
        ordres = [li['ordre'] for li in lignes]
        self.assertEqual(ordres, sorted(ordres))
        self.assertEqual(lignes[0]['pick_list_id'], self.pl1.id)

    def test_reference_sans_trou(self):
        lot1 = creer_lot_prelevement(self.company, [self.pl1.id], self.user)
        lot2 = creer_lot_prelevement(self.company, [self.pl2.id], self.user)
        self.assertNotEqual(lot1.reference, lot2.reference)

    def test_cocher_ligne_propage_a_picklist_source(self):
        lot = creer_lot_prelevement(
            self.company, [self.pl1.id, self.pl2.id], self.user)
        lignes = lignes_lot_prelevement(lot)
        ligne_id = lignes[0]['ligne_id']
        cocher_ligne_lot(lot, ligne_id, quantite_prelevee=5)
        ligne_source = PickListLigne.objects.get(id=ligne_id)
        self.assertTrue(ligne_source.preleve)
        self.assertEqual(ligne_source.quantite_prelevee, 5)

    def test_cloturer_refuse_si_picklist_non_soldee(self):
        lot = creer_lot_prelevement(
            self.company, [self.pl1.id, self.pl2.id], self.user)
        with self.assertRaises(ValueError):
            cloturer_lot_prelevement(lot)
        lot.refresh_from_db()
        self.assertEqual(lot.statut, LotPrelevement.Statut.PLANIFIE)

    def test_cloturer_ok_quand_toutes_soldees(self):
        lot = creer_lot_prelevement(
            self.company, [self.pl1.id, self.pl2.id], self.user)
        self.pl1.statut = PickList.Statut.TERMINE
        self.pl1.save(update_fields=['statut'])
        self.pl2.statut = PickList.Statut.TERMINE
        self.pl2.save(update_fields=['statut'])
        cloturer_lot_prelevement(lot)
        lot.refresh_from_db()
        self.assertEqual(lot.statut, LotPrelevement.Statut.TERMINE)

    def test_depots_differents_refuses(self):
        other_emp = make_emplacement(self.company, nom='Autre dépôt')
        pl_autre_depot = make_picklist_avec_bin(
            self.company, self.inst, other_emp, ordre=5)
        with self.assertRaises(ValueError):
            creer_lot_prelevement(
                self.company, [self.pl1.id, pl_autre_depot.id], self.user)

    def test_endpoint_creer_lignes_cocher_cloturer(self):
        r = self.api.post(f'{BASE}/lots-prelevement/', {
            'pick_list_ids': [self.pl1.id, self.pl2.id],
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        lot_id = r.data['id']

        r2 = self.api.get(f'{BASE}/lots-prelevement/{lot_id}/lignes/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(len(r2.data), 2)

        ligne_id = r2.data[0]['ligne_id']
        r3 = self.api.post(
            f'{BASE}/lots-prelevement/{lot_id}/cocher-ligne/',
            {'ligne_id': ligne_id, 'quantite_prelevee': 5}, format='json')
        self.assertEqual(r3.status_code, 200, r3.data)

        # Pas encore soldé -> clôture refusée.
        r4 = self.api.post(f'{BASE}/lots-prelevement/{lot_id}/cloturer/')
        self.assertEqual(r4.status_code, 400)

        self.pl1.statut = PickList.Statut.TERMINE
        self.pl1.save(update_fields=['statut'])
        self.pl2.statut = PickList.Statut.TERMINE
        self.pl2.save(update_fields=['statut'])
        r5 = self.api.post(f'{BASE}/lots-prelevement/{lot_id}/cloturer/')
        self.assertEqual(r5.status_code, 200, r5.data)
        self.assertEqual(r5.data['statut'], 'termine')

    def test_isolation_tenant(self):
        other_company = make_company()
        other_user = make_user(other_company)
        other_api = auth(other_user)
        r = other_api.post(f'{BASE}/lots-prelevement/', {
            'pick_list_ids': [self.pl1.id],
        }, format='json')
        # La pick-list appartient à une autre société -> aucune sélectionnée.
        self.assertEqual(r.status_code, 400)
