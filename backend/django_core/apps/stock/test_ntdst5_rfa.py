"""NTDST5 — remises arrière (RFA) fournisseurs.

Critère d'acceptation testé : générer DEUX FOIS l'avoir pour la même période
est REFUSÉ (un accord ne matérialise qu'un seul avoir).

Toutes les dates sont FIXES.

Run :
    python manage.py test apps.stock.test_ntdst5_rfa -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    AccordRFAFournisseur, AvoirFournisseur, BonCommandeFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, Produit,
)
from apps.stock.services_rfa import (
    ca_achat_periode, calculer_rfa_fournisseur, generer_avoir_rfa,
)

User = get_user_model()

DEBUT = datetime.date(2026, 1, 1)
FIN = datetime.date(2026, 12, 31)
COMMANDE_LE = datetime.date(2026, 3, 15)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntdst5Base(TestCase):
    URL = '/api/django/stock/accords-rfa-fournisseur/'

    def setUp(self):
        self.company = make_company('ntdst5-co', 'NTDST5 Co')
        self.autre = make_company('ntdst5-autre', 'NTDST5 Autre')
        self.admin = User.objects.create_user(
            username='ntdst5_admin', password='x', role_legacy='admin',
            company=self.company)
        self.normal = User.objects.create_user(
            username='ntdst5_normal', password='x', role_legacy='normal',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTDST5')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau NTDST5', sku='PAN-NTDST5',
            prix_achat=Decimal('900'), prix_vente=Decimal('1200'),
            quantite_stock=0)
        self._seq = 0

    def _commande(self, quantite, quantite_recue, date=COMMANDE_LE):
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-NTDST5-{self._seq:04d}',
            fournisseur=self.fournisseur, date_commande=date)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            quantite_recue=quantite_recue,
            prix_achat_unitaire=Decimal('1000'))
        return bc

    def _accord(self, **kwargs):
        defauts = dict(
            company=self.company, fournisseur=self.fournisseur,
            periode_debut=DEBUT, periode_fin=FIN,
            seuil_ca_achat=Decimal('50000'), taux_pct=Decimal('3'))
        defauts.update(kwargs)
        return AccordRFAFournisseur.objects.create(**defauts)


class Ntdst5CalculTests(Ntdst5Base):
    def test_seul_le_receptionne_compte_dans_le_ca(self):
        self._commande(quantite=100, quantite_recue=60)
        self.assertEqual(
            ca_achat_periode(self.company, self.fournisseur, DEBUT, FIN),
            Decimal('60000.00'))

    def test_une_commande_hors_periode_ne_compte_pas(self):
        self._commande(quantite=100, quantite_recue=100,
                       date=datetime.date(2025, 6, 1))
        self.assertEqual(
            ca_achat_periode(self.company, self.fournisseur, DEBUT, FIN),
            Decimal('0.00'))

    def test_sous_le_seuil_le_montant_du_est_nul(self):
        self._commande(quantite=100, quantite_recue=10)  # 10 000 < 50 000
        calcul = calculer_rfa_fournisseur(self._accord())
        self.assertFalse(calcul['seuil_atteint'])
        self.assertEqual(calcul['montant_du'], '0')
        self.assertEqual(calcul['progression_pct'], '20.00')

    def test_au_dessus_du_seuil_le_taux_sapplique_au_ca(self):
        self._commande(quantite=100, quantite_recue=100)  # 100 000
        calcul = calculer_rfa_fournisseur(self._accord())
        self.assertTrue(calcul['seuil_atteint'])
        self.assertEqual(calcul['montant_du'], '3000.00')

    def test_un_montant_fixe_ignore_le_taux(self):
        self._commande(quantite=100, quantite_recue=100)
        accord = self._accord(taux_pct=None, montant_fixe=Decimal('7500'))
        self.assertEqual(
            calculer_rfa_fournisseur(accord)['montant_du'], '7500.00')

    def test_aucun_ca_dune_autre_societe(self):
        self._commande(quantite=100, quantite_recue=100)
        autre_fournisseur = Fournisseur.objects.create(
            company=self.autre, nom='Voisin NTDST5')
        self.assertEqual(
            ca_achat_periode(self.autre, autre_fournisseur, DEBUT, FIN),
            Decimal('0.00'))


class Ntdst5AvoirTests(Ntdst5Base):
    def test_generer_deux_fois_pour_la_meme_periode_est_refuse(self):
        self._commande(quantite=100, quantite_recue=100)
        accord = self._accord()

        avoir = generer_avoir_rfa(accord, self.admin)
        self.assertEqual(avoir.montant_ttc, Decimal('3000.00'))
        self.assertEqual(AvoirFournisseur.objects.filter(
            company=self.company).count(), 1)

        accord.refresh_from_db()
        with self.assertRaises(ValueError):
            generer_avoir_rfa(accord, self.admin)
        # Toujours UN SEUL avoir.
        self.assertEqual(AvoirFournisseur.objects.filter(
            company=self.company).count(), 1)

    def test_generer_sous_le_seuil_est_refuse(self):
        self._commande(quantite=100, quantite_recue=10)
        with self.assertRaises(ValueError):
            generer_avoir_rfa(self._accord(), self.admin)

    def test_deux_accords_jumeaux_sont_interdits_en_base(self):
        self._accord()
        with self.assertRaises(IntegrityError):
            self._accord()


class Ntdst5ApiTests(Ntdst5Base):
    def test_action_generer_avoir_puis_refus_du_second_appel(self):
        self._commande(quantite=100, quantite_recue=100)
        accord = self._accord()
        api = auth(self.admin)

        premier = api.post(f'{self.URL}{accord.id}/generer-avoir/')
        self.assertEqual(premier.status_code, 201)
        second = api.post(f'{self.URL}{accord.id}/generer-avoir/')
        self.assertEqual(second.status_code, 400)

    def test_taux_et_montant_fixe_sont_exclusifs(self):
        res = auth(self.admin).post(self.URL, {
            'fournisseur': self.fournisseur.id,
            'periode_debut': DEBUT.isoformat(),
            'periode_fin': FIN.isoformat(),
            'seuil_ca_achat': '1000', 'taux_pct': '3',
            'montant_fixe': '500',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_ni_taux_ni_montant_fixe_est_refuse(self):
        res = auth(self.admin).post(self.URL, {
            'fournisseur': self.fournisseur.id,
            'periode_debut': DEBUT.isoformat(),
            'periode_fin': FIN.isoformat(), 'seuil_ca_achat': '1000',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_un_patch_ne_peut_pas_effacer_lavoir_genere(self):
        self._commande(quantite=100, quantite_recue=100)
        accord = self._accord()
        generer_avoir_rfa(accord, self.admin)
        res = auth(self.admin).patch(f'{self.URL}{accord.id}/', {
            'avoir_genere': None}, format='json')
        self.assertEqual(res.status_code, 200)
        accord.refresh_from_db()
        self.assertTrue(accord.avoir_deja_genere)

    def test_lecture_refusee_a_un_role_normal_car_montants_dachat(self):
        self.assertEqual(auth(self.normal).get(self.URL).status_code, 403)
