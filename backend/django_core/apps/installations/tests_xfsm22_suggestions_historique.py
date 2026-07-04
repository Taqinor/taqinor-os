"""
XFSM22 — Durée & pièces suggérées par l'historique (heuristique).

Couvre :
  * `suggestion_duree_intervention` = médiane des durées réelles F15 des
    interventions TERMINÉES/VALIDÉES de même type, repli société si pas assez
    d'historique technicien ;
  * silencieux (None) sous le seuil d'historique (`_MIN_HISTORIQUE`) ;
  * `suggestion_pieces_intervention` = top-N produits consommés (F11) sur les
    interventions similaires, triés par quantité décroissante ;
  * jamais de blocage/forçage de saisie — affichées à la création seulement ;
  * endpoint `suggestions-creation` (GET, query params).

Run :
    python manage.py test apps.installations.tests_xfsm22_suggestions_historique -v2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import (
    ConsommationLigne, Installation, Intervention, MaterielConsommation,
)
from apps.installations.selectors import (
    suggestion_duree_intervention, suggestion_pieces_intervention,
)
from apps.stock.models import Produit

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'


def make_company(slug=None, nom=None):
    from authentication.models import Company
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'xfsm22-co-{n}', defaults={'nom': nom or f'XFSM22 Co {n}'})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_user(company, role='responsable'):
    return User.objects.create_user(
        username=f'xfsm22-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def make_installation(company, type_installation='residentiel'):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Client', prenom='XFSM22',
        email=f'xfsm22-{company.id}-{n}@example.invalid')
    return Installation.objects.create(
        company=company, reference=f'CHT-XFSM22-{n}', client=client,
        type_installation=type_installation)


def make_terminee(company, inst, minutes, technicien=None):
    now = timezone.now()
    return Intervention.objects.create(
        company=company, installation=inst, type_intervention='pose',
        statut=Intervention.Statut.TERMINEE, technicien=technicien,
        depart_depot_le=now,
        arrivee_site_le=now,
        retour_depot_le=now + timezone.timedelta(minutes=minutes))


def make_produit(company, nom):
    return Produit.objects.create(company=company, nom=nom, prix_vente=100)


class TestSuggestionDuree(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)

    def test_silent_below_threshold(self):
        make_terminee(self.company, self.inst, 60)
        result = suggestion_duree_intervention(self.company, 'pose')
        self.assertIsNone(result['duree_suggeree_min'])

    def test_median_over_company_history(self):
        for minutes in (60, 90, 120):
            make_terminee(self.company, self.inst, minutes)
        result = suggestion_duree_intervention(self.company, 'pose')
        self.assertEqual(result['duree_suggeree_min'], 90)
        self.assertEqual(result['portee'], 'societe')

    def test_technicien_scope_used_when_enough_history(self):
        tech = make_user(self.company, role='normal')
        other = make_user(self.company, role='normal')
        for minutes in (30, 30, 30):
            make_terminee(self.company, self.inst, minutes, technicien=tech)
        for minutes in (200, 200, 200):
            make_terminee(self.company, self.inst, minutes, technicien=other)
        result = suggestion_duree_intervention(
            self.company, 'pose', technicien=tech)
        self.assertEqual(result['duree_suggeree_min'], 30)
        self.assertEqual(result['portee'], 'technicien')

    def test_other_type_intervention_never_mixed_in(self):
        for minutes in (60, 90, 120):
            make_terminee(self.company, self.inst, minutes)
        Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='depannage',
            statut=Intervention.Statut.TERMINEE)
        result = suggestion_duree_intervention(self.company, 'depannage')
        # Une seule interv depannage → sous le seuil, donc None.
        self.assertIsNone(result['duree_suggeree_min'])


class TestSuggestionPieces(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst = make_installation(self.company)
        self.panneau = make_produit(self.company, 'Panneau 550W')
        self.onduleur = make_produit(self.company, 'Onduleur 5kW')

    def _make_consommation(self, qte_panneau, qte_onduleur):
        interv = Intervention.objects.create(
            company=self.company, installation=self.inst,
            type_intervention='pose', statut=Intervention.Statut.TERMINEE)
        mc = MaterielConsommation.objects.create(
            company=self.company, intervention=interv)
        ConsommationLigne.objects.create(
            company=self.company, consommation=mc, produit=self.panneau,
            designation='Panneau', quantite_utilisee=Decimal(qte_panneau))
        ConsommationLigne.objects.create(
            company=self.company, consommation=mc, produit=self.onduleur,
            designation='Onduleur', quantite_utilisee=Decimal(qte_onduleur))

    def test_silent_below_threshold(self):
        self._make_consommation(10, 1)
        result = suggestion_pieces_intervention(self.company, 'pose')
        self.assertEqual(result, [])

    def test_top_products_sorted_desc(self):
        for _ in range(3):
            self._make_consommation(10, 1)
        result = suggestion_pieces_intervention(self.company, 'pose')
        self.assertEqual(result[0]['produit_id'], self.panneau.id)
        self.assertEqual(result[0]['quantite_totale'], Decimal('30'))
        self.assertEqual(result[1]['produit_id'], self.onduleur.id)

    def test_filtered_by_type_installation(self):
        for _ in range(3):
            self._make_consommation(10, 1)
        other_inst = make_installation(self.company, type_installation='agricole')
        interv2 = Intervention.objects.create(
            company=self.company, installation=other_inst,
            type_intervention='pose', statut=Intervention.Statut.TERMINEE)
        mc2 = MaterielConsommation.objects.create(
            company=self.company, intervention=interv2)
        ConsommationLigne.objects.create(
            company=self.company, consommation=mc2, produit=self.onduleur,
            designation='Onduleur', quantite_utilisee=Decimal('999'))
        result = suggestion_pieces_intervention(
            self.company, 'pose', type_installation='residentiel')
        onduleur_total = next(
            r['quantite_totale'] for r in result
            if r['produit_id'] == self.onduleur.id)
        self.assertEqual(onduleur_total, Decimal('3'))


class TestSuggestionsCreationApi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.api = auth(self.user)
        self.inst = make_installation(self.company)

    def test_requires_type_intervention(self):
        r = self.api.get(f'{BASE}/interventions/suggestions-creation/')
        self.assertEqual(r.status_code, 400)

    def test_returns_duree_and_pieces_keys(self):
        for minutes in (60, 90, 120):
            make_terminee(self.company, self.inst, minutes)
        r = self.api.get(
            f'{BASE}/interventions/suggestions-creation/'
            '?type_intervention=pose')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertIn('duree', r.data)
        self.assertIn('pieces', r.data)
        self.assertEqual(r.data['duree']['duree_suggeree_min'], 90)
