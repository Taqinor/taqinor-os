"""NTPRT26 — carte « Ma performance » du portail FOURNISSEUR (lecture seule).

Ce que la tâche exige, et ce que ce module vérifie :

1. **CRITÈRE D'ACCEPTATION — les chiffres matchent le calcul interne existant
   sur le même fournisseur.** La ponctualité de la carte est comparée, valeur
   par valeur, à `services.otd_stats` (XPUR7) et à l'action interne
   `fournisseurs/{id}/performance/` ; la conformité à réception est comparée au
   MÊME sélecteur que celui que le scorecard interne consomme.
2. **La carte ne porte AUCUN montant** — ni dépenses, ni prix d'achat, ni score
   de risque interne.
3. **Isolation.** Un `fournisseur_id` absent ou d'une autre société renvoie une
   carte VIDE, jamais les chiffres de la société entière.
4. **Zéro n'est pas « aucune mesure ».** Sans réception contrôlée, le taux de
   conformité est `None` — jamais 0 %, qui se lirait comme un fournisseur
   catastrophique.

Run :
    python manage.py test apps.stock.test_ntprt26_performance_fournisseur -v2
"""
import datetime
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.achats.models import (
    BonCommandeFournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, ReceptionFournisseur,
)
from apps.roles.models import Role
from apps.stock.models import ControleReception, Fournisseur, Produit
from apps.stock.selectors import (
    performance_portail_fournisseur, taux_conformite_reception_fournisseur,
)
from apps.stock.services import otd_stats, supplier_performance
from authentication.models import Company, CustomUser

#: Prix d'achat DISTINCTIF (5 chiffres) : un petit nombre se retrouverait par
#: hasard dans un id, un pourcentage ou un nombre de jours.
PRIX_ACHAT_SECRET = '52968.00'

_seq = itertools.count(1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_interne(company, username):
    role = Role.objects.create(
        company=company, nom=f'r-{username}',
        permissions=['stock_voir', 'stock_modifier'])
    return CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role, role_legacy='responsable')


def make_fournisseur(company, nom):
    return Fournisseur.objects.create(
        company=company, nom=f'{nom}-{next(_seq)}')


def make_produit(company, nom, sku):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku, prix_vente='9900.00',
        prix_achat=PRIX_ACHAT_SECRET)


def make_livraison(company, fournisseur, produit, *, date_confirmee,
                   date_reception, resultat_controle=None):
    """Un BCF confirmé + sa réception CONFIRMÉE (+ son contrôle qualité).

    C'est exactement la matière que l'OTD interne (XPUR7) mesure : une date
    promise et une date réellement reçue.
    """
    bc = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur,
        reference=f'BCF-NTPRT26-{next(_seq)}',
        statut=BonCommandeFournisseur.Statut.ENVOYE,
        date_commande=datetime.date(2026, 6, 1),
        date_confirmee_fournisseur=date_confirmee)
    ligne = LigneBonCommandeFournisseur.objects.create(
        bon_commande=bc, produit=produit, quantite=5,
        prix_achat_unitaire=PRIX_ACHAT_SECRET, quantite_recue=5)
    reception = ReceptionFournisseur.objects.create(
        company=company, reference=f'REC-NTPRT26-{next(_seq)}',
        bon_commande=bc, statut=ReceptionFournisseur.Statut.CONFIRME,
        date_reception=date_reception)
    LigneReceptionFournisseur.objects.create(
        reception=reception, ligne_commande=ligne, produit=produit,
        quantite=5)
    if resultat_controle is not None:
        ControleReception.objects.create(
            company=company, reception=reception, resultat=resultat_controle,
            unites_controlees=5, unites_attendues=5)
    return bc, reception


class ConcordanceAvecLeCalculInterneTests(TestCase):
    """Le critère d'acceptation, joué contre les fonctions internes."""

    def setUp(self):
        self.company = make_company('ntprt26-co', 'NTPRT26 Société')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        self.produit = make_produit(
            self.company, 'Onduleur NTPRT26', 'OND-NTPRT26')
        # Une livraison en retard de 5 jours, conforme ; une à l'heure, non
        # conforme — la carte doit donc porter un retard moyen non nul et un
        # taux de conformité strictement entre 0 et 100.
        make_livraison(
            self.company, self.fournisseur, self.produit,
            date_confirmee=datetime.date(2026, 6, 10),
            date_reception=datetime.date(2026, 6, 15),
            resultat_controle=ControleReception.Resultat.CONFORME)
        make_livraison(
            self.company, self.fournisseur, self.produit,
            date_confirmee=datetime.date(2026, 6, 20),
            date_reception=datetime.date(2026, 6, 20),
            resultat_controle=ControleReception.Resultat.NON_CONFORME)

    def test_la_ponctualite_est_celle_de_otd_stats(self):
        carte = performance_portail_fournisseur(
            self.company, self.fournisseur.id)
        interne = otd_stats(self.company, self.fournisseur)

        self.assertEqual(carte['otd_ecart_moyen_jours'],
                         interne['otd_ecart_moyen_jours'])
        self.assertEqual(carte['otd_a_lheure_pct'],
                         interne['otd_a_lheure_pct'])
        # La matière est réelle : un retard moyen mesuré, pas un None.
        self.assertIsNotNone(carte['otd_ecart_moyen_jours'])

    def test_la_conformite_est_celle_du_selecteur_partage(self):
        carte = performance_portail_fournisseur(
            self.company, self.fournisseur.id)
        partage = taux_conformite_reception_fournisseur(
            self.company, self.fournisseur.id)

        self.assertEqual(carte['receptions_controlees'],
                         partage['receptions_controlees'])
        self.assertEqual(carte['receptions_conformes'],
                         partage['receptions_conformes'])
        self.assertEqual(carte['taux_conformite_reception_pct'],
                         partage['taux_conformite_pct'])
        self.assertEqual(carte['taux_conformite_reception_pct'], 50.0)

    def test_le_scorecard_interne_lit_la_meme_ponctualite(self):
        carte = performance_portail_fournisseur(
            self.company, self.fournisseur.id)
        interne = supplier_performance(self.company, self.fournisseur)

        for cle in ('otd_ecart_moyen_jours', 'otd_a_lheure_pct'):
            self.assertEqual(carte[cle], interne[cle], cle)

    def test_l_endpoint_interne_sert_la_meme_ponctualite(self):
        api = APIClient()
        api.force_authenticate(
            user=make_interne(self.company, 'ntprt26-interne'))
        res = api.get(
            f'/api/django/stock/fournisseurs/{self.fournisseur.id}'
            f'/performance/')

        self.assertEqual(res.status_code, 200, res.data)
        carte = performance_portail_fournisseur(
            self.company, self.fournisseur.id)
        self.assertEqual(res.data['otd_a_lheure_pct'],
                         carte['otd_a_lheure_pct'])
        self.assertEqual(res.data['otd_ecart_moyen_jours'],
                         carte['otd_ecart_moyen_jours'])

    def test_le_nom_du_fournisseur_est_le_sien(self):
        carte = performance_portail_fournisseur(
            self.company, self.fournisseur.id)
        self.assertEqual(carte['fournisseur_nom'], self.fournisseur.nom)


class AucunMontantDansLaCarteTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt26-montant-co', 'NTPRT26 Montant')
        self.fournisseur = make_fournisseur(self.company, 'Alpha')
        self.produit = make_produit(
            self.company, 'Onduleur M26', 'OND-M26')
        make_livraison(
            self.company, self.fournisseur, self.produit,
            date_confirmee=datetime.date(2026, 6, 10),
            date_reception=datetime.date(2026, 6, 12),
            resultat_controle=ControleReception.Resultat.CONFORME)

    def test_ni_prix_d_achat_ni_depenses_ni_score_de_risque(self):
        carte = performance_portail_fournisseur(
            self.company, self.fournisseur.id)
        charge = str(carte)

        self.assertNotIn(PRIX_ACHAT_SECRET, charge)
        self.assertNotIn(PRIX_ACHAT_SECRET.split('.')[0], charge)
        for interdit in ('prix_achat', 'total_achats', 'marge', 'score_risque',
                         'incidents', 'scar'):
            self.assertNotIn(interdit, carte)
            self.assertNotIn(interdit, charge)

    def test_le_scorecard_interne_porte_bien_ce_que_la_carte_retire(self):
        """La carte n'est pas une simple recopie : ce qu'elle retire existe
        réellement côté interne (sinon ce test passerait pour rien)."""
        interne = supplier_performance(self.company, self.fournisseur)
        self.assertIn('total_achats_ht', interne)
        self.assertIn('incidents_qualite_critiques_ouverts', interne)


class IsolationEtAbsenceDeMesureTests(TestCase):
    def setUp(self):
        self.company = make_company('ntprt26-iso-co', 'NTPRT26 Isolation')
        self.autre_company = make_company('ntprt26-iso-co2', 'NTPRT26 Iso 2')
        self.f_a = make_fournisseur(self.company, 'Alpha')
        self.f_etranger = make_fournisseur(self.autre_company, 'Gamma')
        self.produit = make_produit(self.company, 'Onduleur I26', 'OND-I26')

    def test_un_fournisseur_sans_livraison_n_a_pas_de_taux_plutot_que_zero(self):
        carte = performance_portail_fournisseur(self.company, self.f_a.id)

        self.assertEqual(carte['fournisseur_nom'], self.f_a.nom)
        self.assertIsNone(carte['otd_ecart_moyen_jours'])
        self.assertIsNone(carte['otd_a_lheure_pct'])
        self.assertIsNone(carte['taux_conformite_reception_pct'])
        self.assertEqual(carte['receptions_controlees'], 0)
        self.assertEqual(carte['receptions_conformes'], 0)

    def test_une_reception_non_controlee_n_entre_pas_au_denominateur(self):
        make_livraison(
            self.company, self.f_a, self.produit,
            date_confirmee=datetime.date(2026, 6, 10),
            date_reception=datetime.date(2026, 6, 10))

        carte = performance_portail_fournisseur(self.company, self.f_a.id)
        self.assertEqual(carte['receptions_controlees'], 0)
        self.assertIsNone(carte['taux_conformite_reception_pct'])
        # La ponctualité, elle, se mesure sans contrôle qualité.
        self.assertEqual(carte['otd_a_lheure_pct'], 100.0)

    def test_un_fournisseur_d_une_autre_societe_rend_une_carte_vide(self):
        carte = performance_portail_fournisseur(
            self.company, self.f_etranger.id)
        self.assertEqual(carte['fournisseur_nom'], '')
        self.assertIsNone(carte['otd_a_lheure_pct'])

    def test_sans_rattachement_la_carte_est_vide(self):
        for carte in (performance_portail_fournisseur(self.company, None),
                      performance_portail_fournisseur(None, self.f_a.id)):
            self.assertEqual(carte['fournisseur_nom'], '')
            self.assertEqual(carte['receptions_controlees'], 0)
            self.assertIsNone(carte['taux_conformite_reception_pct'])

    def test_la_conformite_est_bornee_au_couple_societe_fournisseur(self):
        make_livraison(
            self.company, self.f_a, self.produit,
            date_confirmee=datetime.date(2026, 6, 10),
            date_reception=datetime.date(2026, 6, 10),
            resultat_controle=ControleReception.Resultat.CONFORME)

        # Le même fournisseur lu avec l'AUTRE société : aucune mesure.
        etranger = taux_conformite_reception_fournisseur(
            self.autre_company, self.f_a.id)
        self.assertEqual(etranger['receptions_controlees'], 0)
        self.assertIsNone(etranger['taux_conformite_pct'])

    def test_aucune_ecriture_n_est_possible_depuis_la_carte(self):
        """Lecture seule : consulter sa performance ne change aucun chiffre."""
        make_livraison(
            self.company, self.f_a, self.produit,
            date_confirmee=datetime.date(2026, 6, 10),
            date_reception=datetime.date(2026, 6, 14),
            resultat_controle=ControleReception.Resultat.NON_CONFORME)
        avant = performance_portail_fournisseur(self.company, self.f_a.id)

        for _ in range(3):
            performance_portail_fournisseur(self.company, self.f_a.id)

        self.assertEqual(
            performance_portail_fournisseur(self.company, self.f_a.id), avant)
        self.assertEqual(
            ControleReception.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            Produit.objects.get(pk=self.produit.pk).prix_achat,
            Decimal(PRIX_ACHAT_SECRET))
