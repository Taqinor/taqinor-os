"""
N14 — Réservation de stock sur chantier puis consommation à « Installé ».

Couvre :
  * la création d'un chantier depuis un devis à BOM réserve les bonnes
    quantités par SKU, et le disponible reflète la réservation ;
  * l'alerte de stock bas / le disponible tiennent compte de la réservation ;
  * le passage à « Installé » crée EXACTEMENT une SORTIE par SKU et décrémente
    le stock ; un second passage par « Installé » ne crée AUCUN mouvement
    supplémentaire (idempotence) et le stock reste inchangé ;
  * l'annulation et la clôture libèrent la réservation restante (le disponible
    revient) ;
  * réservations + mouvements portent la société du chantier (multi-tenant).

Run :
    docker compose exec django_core python manage.py test \
        apps.installations.tests_reservation -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import Produit, MouvementStock
from apps.stock.services import (
    reserved_quantity, available_quantity, is_low_stock_available,
)
from apps.installations.models import StockReservation
from apps.installations.services import (
    create_installation_from_devis, seed_reservations,
    consume_reservations, release_reservations,
)

User = get_user_model()

_seq = itertools.count(1)


def make_company(slug='resa-co', nom='Resa Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom, stock, seuil=0):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-{company.id}-{n}',
        prix_vente=Decimal('100'), quantite_stock=stock, seuil_alerte=seuil)


def make_accepted_devis_with_lines(company, lines):
    """lines = [(produit, quantite), ...]. Crée un devis accepté + ses lignes."""
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'resa-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-RESA-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel')
    for produit, qte in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    return devis


class TestReservationSeeding(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='resa_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.panneau = make_produit(self.company, 'Panneau 550W', stock=20)
        self.onduleur = make_produit(self.company, 'Onduleur 5kW', stock=10)

    def test_creation_reserves_quantities_per_sku(self):
        devis = make_accepted_devis_with_lines(
            self.company, [(self.panneau, 12), (self.onduleur, 1)])
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)
        # Une réservation active par SKU, à la quantité du BOM.
        resas = {r.produit_id: r for r in inst.reservations.all()}
        self.assertEqual(resas[self.panneau.id].quantite, 12)
        self.assertEqual(resas[self.onduleur.id].quantite, 1)
        self.assertTrue(all(r.active and not r.consomme
                            for r in resas.values()))
        # Le stock total n'a PAS bougé (réservation ≠ décrément).
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        # Disponible reflète la réservation.
        self.assertEqual(reserved_quantity(self.panneau), 12)
        self.assertEqual(available_quantity(self.panneau), 8)
        self.assertEqual(available_quantity(self.onduleur), 9)

    def test_empty_bom_is_robust(self):
        # Devis sans ligne produit → BOM vide → aucune réservation, aucun crash.
        devis = make_accepted_devis_with_lines(self.company, [])
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)
        self.assertEqual(inst.reservations.count(), 0)

    def test_seeding_is_idempotent(self):
        devis = make_accepted_devis_with_lines(
            self.company, [(self.panneau, 5)])
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        # Réamorcer ne duplique pas et réaligne la quantité.
        seed_reservations(inst)
        seed_reservations(inst)
        self.assertEqual(
            inst.reservations.filter(produit=self.panneau).count(), 1)
        self.assertEqual(
            inst.reservations.get(produit=self.panneau).quantite, 5)

    def test_low_stock_accounts_for_reservation(self):
        # Stock 10, seuil 6 → pas en alerte brute. Réserver 5 → disponible 5
        # ≤ seuil → en alerte sur le disponible.
        produit = make_produit(self.company, 'Câble', stock=10, seuil=6)
        devis = make_accepted_devis_with_lines(
            self.company, [(produit, 5)])
        create_installation_from_devis(devis, self.user, self.company)
        produit.refresh_from_db()
        self.assertFalse(
            produit.seuil_alerte > 0
            and produit.quantite_stock <= produit.seuil_alerte)
        self.assertTrue(is_low_stock_available(produit))
        self.assertEqual(available_quantity(produit), 5)


class TestConsumptionIdempotent(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='resa_resp2', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(self.company, 'Panneau X', stock=30)
        self.onduleur = make_produit(self.company, 'Onduleur Y', stock=8)
        devis = make_accepted_devis_with_lines(
            self.company, [(self.panneau, 10), (self.onduleur, 2)])
        self.inst, _ = create_installation_from_devis(
            devis, self.user, self.company)

    def _sortie_count(self, produit):
        return MouvementStock.objects.filter(
            produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            reference=self.inst.reference).count()

    def test_installe_consumes_once_then_idempotent_via_service(self):
        n = consume_reservations(self.inst, self.user)
        self.assertEqual(n, 2)  # deux SKU consommés
        self.panneau.refresh_from_db()
        self.onduleur.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)  # 30 - 10
        self.assertEqual(self.onduleur.quantite_stock, 6)  # 8 - 2
        self.assertEqual(self._sortie_count(self.panneau), 1)
        self.assertEqual(self._sortie_count(self.onduleur), 1)
        # Réservations marquées consommées.
        self.assertTrue(all(
            r.consomme for r in self.inst.reservations.all()))
        # Disponible = stock (plus de réservation engagée).
        self.assertEqual(available_quantity(self.panneau), 20)

        # Rejouer la consommation : AUCUN mouvement supplémentaire, stock figé.
        again = consume_reservations(self.inst, self.user)
        self.assertEqual(again, 0)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertEqual(self._sortie_count(self.panneau), 1)
        self.assertEqual(self._sortie_count(self.onduleur), 1)

    def test_installe_via_api_then_reenter_installe_no_double(self):
        url = f'/api/django/installations/chantiers/{self.inst.id}/'
        # Passe à « Installé » via l'API (déclenche le hook de statut).
        r = self.api.patch(url, {'statut': 'installe'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertEqual(self._sortie_count(self.panneau), 1)

        # Repasser par un autre statut puis de nouveau « Installé ».
        self.api.patch(url, {'statut': 'en_cours'}, format='json')
        r2 = self.api.patch(url, {'statut': 'installe'}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.panneau.refresh_from_db()
        # Toujours UNE seule SORTIE, stock inchangé (idempotence).
        self.assertEqual(self.panneau.quantite_stock, 20)
        self.assertEqual(self._sortie_count(self.panneau), 1)
        self.assertEqual(self._sortie_count(self.onduleur), 1)

    def test_company_scoping_on_reservation_and_movement(self):
        consume_reservations(self.inst, self.user)
        for r in self.inst.reservations.all():
            self.assertEqual(r.company_id, self.company.id)
        for mv in MouvementStock.objects.filter(reference=self.inst.reference):
            self.assertEqual(mv.company_id, self.company.id)


class TestReleaseOnCancelClose(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='resa_resp3', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.produit = make_produit(self.company, 'Structure', stock=15)
        devis = make_accepted_devis_with_lines(
            self.company, [(self.produit, 6)])
        self.inst, _ = create_installation_from_devis(
            devis, self.user, self.company)

    def test_cancel_releases_remaining_reservation(self):
        self.assertEqual(available_quantity(self.produit), 9)  # 15 - 6
        url = f'/api/django/installations/chantiers/{self.inst.id}/annuler/'
        r = self.api.post(url, {'motif': 'Client se désiste'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        # Réservation libérée → le disponible revient au stock complet.
        self.assertEqual(reserved_quantity(self.produit), 0)
        self.assertEqual(available_quantity(self.produit), 15)
        self.assertFalse(
            self.inst.reservations.filter(active=True).exists())
        # Le stock total n'a jamais été décrémenté (pas de consommation).
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 15)

    def test_close_releases_unconsumed_reservation(self):
        # Clôture SANS être passé par « Installé » → libère le reste.
        n = release_reservations(self.inst)
        self.assertEqual(n, 1)
        self.assertEqual(available_quantity(self.produit), 15)
        # Une réservation déjà consommée n'est pas relâchée.
        StockReservation.objects.filter(installation=self.inst).update(
            active=True, consomme=True)
        self.assertEqual(release_reservations(self.inst), 0)

    def test_close_via_api_after_install_keeps_consumption(self):
        url = f'/api/django/installations/chantiers/{self.inst.id}/'
        self.api.patch(url, {'statut': 'installe'}, format='json')
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 9)  # consommé 6
        # Clôturer ne ré-ajoute pas le stock consommé.
        self.api.patch(url, {'statut': 'cloture'}, format='json')
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 9)
        self.assertEqual(reserved_quantity(self.produit), 0)
