"""NTP2P17 — Dashboard spend management.

Couvre : consommation budgétaire par département (NTP2P4) visible en un
coup d'œil (% du mois en cours), top fournisseurs par volume, exceptions
3 voies (en cours vs résolues), notes de frais en attente, et l'endpoint
``stock/tableau-bord-achats/``.

Run:
    python manage.py test apps.stock.test_ntp2p17_tableau_bord_achats -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock import selectors as stock_selectors
from apps.stock.models import (
    BonCommandeFournisseur, BudgetDepartement,
    EngagementBudget, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, Produit,
)

User = get_user_model()
_seq = itertools.count(1)


def _company():
    from authentication.models import Company
    n = next(_seq)
    return Company.objects.create(nom=f'NTP2P17 Co {n}', slug=f'ntp2p17-{n}')


def _user(company, role='responsable'):
    return User.objects.create_user(
        username=f'ntp2p17-{next(_seq)}', password='x',
        role_legacy=role, company=company)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _departement(company):
    from apps.rh.models import Departement
    return Departement.objects.create(company=company, nom='Achats')


class TestBudgetsDepartement(TestCase):
    def test_budget_avec_engagement_actif_affiche_taux_consommation(self):
        company = _company()
        dept = _departement(company)
        annee = timezone.localdate().year
        budget = BudgetDepartement.objects.create(
            company=company, departement=dept,
            periodicite=BudgetDepartement.Periodicite.ANNUELLE,
            annee=annee, montant_alloue=Decimal('10000'))
        EngagementBudget.objects.create(
            company=company, budget=budget, montant=Decimal('4000'),
            statut=EngagementBudget.Statut.ACTIF)
        resultat = stock_selectors.tableau_bord_achats(company)
        lignes = resultat['budgets_departement']
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['departement_id'], dept.id)
        self.assertEqual(lignes[0]['taux_consommation_pct'], 40.0)

    def test_sans_budget_configure_liste_vide(self):
        company = _company()
        resultat = stock_selectors.tableau_bord_achats(company)
        self.assertEqual(resultat['budgets_departement'], [])


class TestTopFournisseurs(TestCase):
    def test_classe_par_volume_decroissant(self):
        company = _company()
        gros = Fournisseur.objects.create(company=company, nom='Gros volume')
        petit = Fournisseur.objects.create(company=company, nom='Petit volume')
        produit = Produit.objects.create(
            company=company, nom='Produit X', sku='NTP2P17-X',
            prix_vente=Decimal('200'), prix_achat=Decimal('100'))
        bcf_gros = BonCommandeFournisseur.objects.create(
            company=company, reference='BCF-NTP2P17-1', fournisseur=gros,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf_gros, produit=produit, quantite=100,
            prix_achat_unitaire=Decimal('100'))
        bcf_petit = BonCommandeFournisseur.objects.create(
            company=company, reference='BCF-NTP2P17-2', fournisseur=petit,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf_petit, produit=produit, quantite=1,
            prix_achat_unitaire=Decimal('100'))

        resultat = stock_selectors.tableau_bord_achats(company)
        top = resultat['top_fournisseurs']
        self.assertEqual(top[0]['fournisseur_id'], gros.id)
        self.assertEqual(top[0]['volume'], Decimal('10000'))


class TestExceptions3Voies(TestCase):
    def test_compte_en_cours_et_resolues_separement(self):
        company = _company()
        fournisseur = Fournisseur.objects.create(
            company=company, nom='Fournisseur exceptions')
        FactureFournisseur.objects.create(
            company=company, reference='FF-NTP2P17-1', fournisseur=fournisseur,
            montant_ttc=Decimal('1000'),
            statut_controle=FactureFournisseur.StatutControle.EXCEPTION)
        FactureFournisseur.objects.create(
            company=company, reference='FF-NTP2P17-2', fournisseur=fournisseur,
            montant_ttc=Decimal('1000'),
            statut_controle=FactureFournisseur.StatutControle.RESOLUE)
        FactureFournisseur.objects.create(
            company=company, reference='FF-NTP2P17-3', fournisseur=fournisseur,
            montant_ttc=Decimal('1000'))  # normale, ne compte pas

        resultat = stock_selectors.tableau_bord_achats(company)
        self.assertEqual(resultat['exceptions_3voies'], {
            'en_cours': 1, 'resolues': 1, 'total': 2,
        })


class TestNotesFraisEnAttente(TestCase):
    def test_compte_seulement_les_notes_soumises(self):
        from apps.frais.models import NoteFrais

        company = _company()
        employe = _user(company)
        NoteFrais.objects.create(
            company=company, employe=employe, date_frais=timezone.localdate(),
            montant=Decimal('300'), motif='Repas',
            statut=NoteFrais.Statut.SOUMISE)
        NoteFrais.objects.create(
            company=company, employe=employe, date_frais=timezone.localdate(),
            montant=Decimal('500'), motif='Transport',
            statut=NoteFrais.Statut.BROUILLON)

        resultat = stock_selectors.tableau_bord_achats(company)
        self.assertEqual(resultat['notes_frais_en_attente'], {
            'count': 1, 'montant_total': Decimal('300'),
        })


class TestEndpoint(TestCase):
    def test_endpoint_renvoie_les_cles_attendues(self):
        company = _company()
        user = _user(company, role='responsable')
        api = _api(user)
        resp = api.get('/api/django/stock/tableau-bord-achats/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for cle in ('budgets_departement', 'top_fournisseurs',
                    'delai_demande_bcf_jours', 'delai_bcf_reception_jours',
                    'exceptions_3voies', 'notes_frais_en_attente'):
            self.assertIn(cle, resp.data)

    def test_endpoint_refuse_role_non_responsable(self):
        company = _company()
        user = _user(company, role='utilisateur')
        api = _api(user)
        resp = api.get('/api/django/stock/tableau-bord-achats/')
        self.assertEqual(resp.status_code, 403, resp.data)
