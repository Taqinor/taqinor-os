"""AUD322 — réactiver un chantier annulé réamorce ses réservations de stock.

Défaut d'origine : `annuler` appelait `release_reservations(inst)`
(`active=False`) mais `reactiver` ne levait que le drapeau `annule` et
rappelait `reactiver_interventions_annulees` — JAMAIS `seed_reservations`, la
seule fonction qui repasse une réservation à `active=True`. Or
`consume_reservations` ne filtre que `active=True, consomme=False` : une
réservation restée inactive après réactivation était invisible pour toujours.
Un chantier annulé par erreur puis réactivé progressait donc jusqu'à
« Installé », matériel physiquement posé, sans qu'aucune SORTIE de stock ne se
poste — le stock restait silencieusement gonflé.

Run :
    python manage.py test apps.installations.tests_aud322_reactivation_reservations -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.installations.models import Installation, StockReservation
from apps.installations.services import seed_reservations

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations/chantiers'


def make_company():
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=f'aud322-co-{n}', defaults={'nom': f'AUD322 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReactivationReamorceLesReservationsTests(TestCase):
    def setUp(self):
        from apps.stock.models import EmplacementStock, Produit
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'aud322-resp-{next(_seq)}', password='x',
            company=self.company, role_legacy='responsable')
        self.api = auth(self.user)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau AUD322',
            prix_vente=Decimal('100'), quantite_stock=10)
        EmplacementStock.objects.create(company=self.company, nom='Dépôt')
        self.inst = Installation.objects.create(
            company=self.company, reference='AUD322-1',
            statut=Installation.Statut.PLANIFIE,
            bom=[{'produit_id': self.produit.id,
                  'designation': 'Panneau AUD322', 'quantite': 4}])
        seed_reservations(self.inst)

    def _annuler_puis_reactiver(self):
        r1 = self.api.post(f'{BASE}/{self.inst.id}/annuler/',
                           {'motif': 'Erreur de saisie'}, format='json')
        self.assertEqual(r1.status_code, 200, r1.data)
        self.assertFalse(
            StockReservation.objects.filter(
                installation=self.inst, active=True).exists())
        r2 = self.api.post(f'{BASE}/{self.inst.id}/reactiver/', {},
                           format='json')
        self.assertEqual(r2.status_code, 200, r2.data)

    def test_reactivation_repasse_les_reservations_en_actif(self):
        """ROUGE avant AUD322 : les réservations restaient active=False."""
        self._annuler_puis_reactiver()
        self.assertTrue(
            StockReservation.objects.filter(
                installation=self.inst, active=True, consomme=False).exists())

    def test_la_consommation_se_poste_apres_reactivation(self):
        """ROUGE avant AUD322 : aucune SORTIE, stock gonflé à 10."""
        self._annuler_puis_reactiver()
        r = self.api.patch(
            f'{BASE}/{self.inst.id}/',
            {'statut': Installation.Statut.INSTALLE}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 6)  # 10 − 4 consommés

    def test_une_note_de_chatter_trace_le_reamorcage(self):
        self._annuler_puis_reactiver()
        notes = [a.body or '' for a in self.inst.activites.all()]
        self.assertTrue(
            any('réamorcée' in n for n in notes), notes)

    def test_chantier_sans_reservation_nen_cree_aucune(self):
        """Mode `manuelle` (ZSTK11) : un chantier jamais réservé le reste."""
        vierge = Installation.objects.create(
            company=self.company, reference='AUD322-2',
            statut=Installation.Statut.PLANIFIE,
            bom=[{'produit_id': self.produit.id,
                  'designation': 'Panneau AUD322', 'quantite': 4}])
        self.api.post(f'{BASE}/{vierge.id}/annuler/', {}, format='json')
        self.api.post(f'{BASE}/{vierge.id}/reactiver/', {}, format='json')
        self.assertFalse(
            StockReservation.objects.filter(installation=vierge).exists())
