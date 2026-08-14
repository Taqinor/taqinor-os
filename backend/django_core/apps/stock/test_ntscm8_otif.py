"""NTSCM8 — scorecard fournisseur enrichi : OTIF réel promis-vs-livré.

Critère d'acceptation testé : une commande livrée 3 JOURS APRÈS
``date_livraison_prevue`` compte comme NON-OTIF **même si la quantité est
complète** — test dédié, distinct du test FG59 existant
(``test_xpur7_otd_livraison.py``).

Toutes les dates sont FIXES et injectées : la suite ne lit jamais l'horloge.

Run :
    python manage.py test apps.stock.test_ntscm8_otif -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.selectors import otif_fournisseur

User = get_user_model()

AUJOURDHUI = datetime.date(2026, 6, 30)
COMMANDE_LE = datetime.date(2026, 6, 1)
PROMIS_LE = datetime.date(2026, 6, 10)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntscm8Base(TestCase):
    def setUp(self):
        self.company = make_company('ntscm8-co', 'NTSCM8 Co')
        self.autre = make_company('ntscm8-autre', 'NTSCM8 Autre')
        self.admin = User.objects.create_user(
            username='ntscm8_admin', password='x', role_legacy='admin',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur NTSCM8')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 8 kW', sku='OND8-NTSCM8',
            prix_achat=Decimal('9000'), prix_vente=Decimal('12000'),
            quantite_stock=0)
        self._seq = 0

    def _livraison(self, *, recue_le, quantite=10, quantite_recue=10,
                   promis_le=PROMIS_LE):
        """Une commande promise puis (éventuellement) réceptionnée."""
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-NTSCM8-{self._seq:04d}',
            fournisseur=self.fournisseur, date_commande=COMMANDE_LE,
            date_livraison_prevue=promis_le)
        LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            quantite_recue=quantite_recue,
            prix_achat_unitaire=Decimal('9000'))
        if recue_le is not None:
            reception = ReceptionFournisseur.objects.create(
                company=self.company,
                reference=f'REC-NTSCM8-{self._seq:04d}', bon_commande=bc,
                statut=ReceptionFournisseur.Statut.CONFIRME,
                date_reception=recue_le)
            LigneReceptionFournisseur.objects.create(
                reception=reception,
                ligne_commande=bc.lignes.first(), produit=self.produit,
                quantite=quantite_recue)
        return bc


class Ntscm8OtifTests(Ntscm8Base):
    def test_complet_mais_3_jours_en_retard_nest_pas_otif(self):
        self._livraison(recue_le=PROMIS_LE + datetime.timedelta(days=3))

        res = otif_fournisseur(self.company, self.fournisseur,
                               aujourdhui=AUJOURDHUI)

        self.assertEqual(res['total_livraisons'], 1)
        self.assertEqual(res['nb_otif'], 0)
        self.assertEqual(res['nb_retard'], 1)
        self.assertEqual(res['nb_incomplet'], 0)
        self.assertEqual(res['taux_otif_pct'], '0')

    def test_a_lheure_et_complet_est_otif(self):
        self._livraison(recue_le=PROMIS_LE)
        res = otif_fournisseur(self.company, self.fournisseur,
                               aujourdhui=AUJOURDHUI)
        self.assertEqual(res['nb_otif'], 1)
        self.assertEqual(res['taux_otif_pct'], '100')

    def test_a_lheure_mais_incomplet_nest_pas_otif(self):
        self._livraison(recue_le=PROMIS_LE - datetime.timedelta(days=1),
                        quantite=10, quantite_recue=7)
        res = otif_fournisseur(self.company, self.fournisseur,
                               aujourdhui=AUJOURDHUI)
        self.assertEqual(res['nb_otif'], 0)
        self.assertEqual(res['nb_incomplet'], 1)
        self.assertEqual(res['nb_retard'], 0)

    def test_le_taux_est_bien_la_part_des_livraisons_a_lheure_et_completes(
            self):
        self._livraison(recue_le=PROMIS_LE)                      # OTIF
        self._livraison(recue_le=PROMIS_LE)                      # OTIF
        self._livraison(recue_le=PROMIS_LE + datetime.timedelta(days=3))
        self._livraison(recue_le=PROMIS_LE, quantite_recue=1)    # incomplet

        res = otif_fournisseur(self.company, self.fournisseur,
                               aujourdhui=AUJOURDHUI)
        self.assertEqual(res['total_livraisons'], 4)
        self.assertEqual(res['nb_otif'], 2)
        self.assertEqual(res['taux_otif_pct'], '50')

    def test_une_commande_sans_date_promise_nentre_pas_dans_le_calcul(self):
        self._livraison(recue_le=PROMIS_LE, promis_le=None)
        res = otif_fournisseur(self.company, self.fournisseur,
                               aujourdhui=AUJOURDHUI)
        self.assertEqual(res['total_livraisons'], 0)
        self.assertIsNone(res['taux_otif_pct'])

    def test_une_commande_jamais_receptionnee_nentre_pas_dans_le_calcul(self):
        self._livraison(recue_le=None)
        res = otif_fournisseur(self.company, self.fournisseur,
                               aujourdhui=AUJOURDHUI)
        self.assertEqual(res['total_livraisons'], 0)

    def test_la_fenetre_glissante_exclut_les_commandes_trop_anciennes(self):
        self._livraison(recue_le=PROMIS_LE)
        res = otif_fournisseur(self.company, self.fournisseur,
                               fenetre_mois=1,
                               aujourdhui=datetime.date(2026, 12, 31))
        self.assertEqual(res['total_livraisons'], 0)

    def test_aucune_commande_dune_autre_societe(self):
        self._livraison(recue_le=PROMIS_LE)
        autre_fournisseur = Fournisseur.objects.create(
            company=self.autre, nom='Voisin NTSCM8')
        res = otif_fournisseur(self.autre, autre_fournisseur,
                               aujourdhui=AUJOURDHUI)
        self.assertEqual(res['total_livraisons'], 0)


class Ntscm8ScorecardTests(Ntscm8Base):
    def test_le_scorecard_expose_le_taux_otif(self):
        self._livraison(recue_le=PROMIS_LE + datetime.timedelta(days=3))
        res = auth(self.admin).get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/'
            'performance/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('taux_otif_pct', res.data)
        self.assertEqual(res.data['otif_nb_retard'], 1)

    def test_endpoint_otif_dedie(self):
        self._livraison(recue_le=PROMIS_LE)
        res = auth(self.admin).get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/otif/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['taux_otif_pct'], '100')

    def test_endpoint_otif_refuse_lanonyme(self):
        res = APIClient().get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}/otif/')
        self.assertEqual(res.status_code, 401)
