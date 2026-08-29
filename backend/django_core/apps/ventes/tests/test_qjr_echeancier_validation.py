"""QJR21 — l'échéancier refuse un montant interprété comme un pourcentage.

``Devis.echeancier`` est un JSONField dont ``pct_or_montant`` était TOUJOURS lu
comme un pourcentage, alors que le nom du champ et son ``help_text``
autorisent un montant : une tranche saisie en dirhams produisait une facture de
plusieurs centaines de fois le total du devis.

Ce module prouve les trois cas exigés :

  1. POURCENTAGE VALIDE — une tranche ≤ 100 (déclarée ou non) reste un
     pourcentage, mot pour mot comme hier (rétro-compatibilité).
  2. MONTANT DÉCLARÉ — une tranche qui déclare ``montant`` vaut ce montant TTC
     et non un pourcentage ; son poids est DÉRIVÉ du total.
  3. AMBIGU REFUSÉ — au-delà de 100 sans unité déclarée, l'API répond 400 avec
     un message en français.

ATTENTION FIXTURES (R4-B3) : les montants de test restent SOUS 1000 MAD —
``Facture.pourcentage`` est un ``numeric(5, 2)`` et un test qui le ferait
déborder échouerait pour la mauvaise raison.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr_echeancier_validation"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.echeancier import (
    EcheancierInvalide, UNITE_MONTANT, UNITE_PCT, next_tranche,
    normaliser_tranche, schedule_for_devis, tranches_normalisees,
    unite_declaree, valider_echeancier,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


# ═══════════════════════════════════════════════════════════════════════════
# 1. LA RÈGLE, SANS BASE — le validateur pur
# ═══════════════════════════════════════════════════════════════════════════
class RegleUniteTranche(SimpleTestCase):
    """``normaliser_tranche`` : la seule source de la règle et des messages."""

    def test_sans_declaration_et_sous_100_reste_un_pourcentage(self):
        """Rétro-compatibilité : toutes les données d'hier sont inchangées."""
        tranche = normaliser_tranche(
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 40})
        self.assertEqual(tranche['unite'], UNITE_PCT)
        self.assertEqual(tranche['valeur'], 40.0)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['libelle'], 'Acompte')

    def test_pourcentage_declare_explicitement(self):
        tranche = normaliser_tranche(
            {'libelle': 'Acompte', 'type': 'acompte',
             'unite': 'pct', 'pct_or_montant': 30})
        self.assertEqual(tranche['unite'], UNITE_PCT)
        self.assertEqual(tranche['key'], 'acompte')

    def test_montant_declare_par_la_cle_unite(self):
        tranche = normaliser_tranche(
            {'libelle': 'Acompte', 'type': 'acompte',
             'unite': 'montant', 'pct_or_montant': 500})
        self.assertEqual(tranche['unite'], UNITE_MONTANT)
        self.assertEqual(tranche['valeur'], 500.0)
        # La NATURE de la tranche reste 'acompte' : ``unite`` ne l'écrase pas.
        self.assertEqual(tranche['key'], 'acompte')

    def test_montant_declare_par_la_cle_type(self):
        """``type`` : 'montant' déclare l'unité et n'est alors PAS une nature."""
        tranche = normaliser_tranche(
            {'libelle': 'Premier versement', 'type': 'montant',
             'pct_or_montant': 750}, index=0)
        self.assertEqual(tranche['unite'], UNITE_MONTANT)
        self.assertEqual(tranche['key'], 'tranche_0')

    def test_valeur_ambigue_au_dela_de_100_est_refusee(self):
        with self.assertRaises(EcheancierInvalide) as ctx:
            normaliser_tranche(
                {'libelle': 'Acompte', 'type': 'acompte',
                 'pct_or_montant': 500})
        message = str(ctx.exception)
        self.assertIn('ambigu', message)
        self.assertIn('montant', message)

    def test_pourcentage_declare_au_dela_de_100_est_refuse(self):
        with self.assertRaises(EcheancierInvalide) as ctx:
            normaliser_tranche({'unite': 'pct', 'pct_or_montant': 120})
        self.assertIn('100', str(ctx.exception))

    def test_montant_declare_au_dela_de_100_est_accepte(self):
        """C'est TOUTE la différence : déclaré, un montant n'est plus ambigu."""
        tranche = normaliser_tranche(
            {'unite': 'montant', 'pct_or_montant': 900})
        self.assertEqual(tranche['unite'], UNITE_MONTANT)
        self.assertEqual(tranche['valeur'], 900.0)

    def test_valeur_negative_refusee(self):
        with self.assertRaises(EcheancierInvalide):
            normaliser_tranche({'unite': 'pct', 'pct_or_montant': -5})

    def test_valeur_non_numerique_refusee(self):
        with self.assertRaises(EcheancierInvalide):
            normaliser_tranche({'pct_or_montant': 'quarante'})

    def test_tranche_non_objet_refusee(self):
        with self.assertRaises(EcheancierInvalide):
            normaliser_tranche('acompte', index=1)

    def test_unite_declaree_lit_unite_puis_type(self):
        self.assertEqual(unite_declaree({'unite': 'MONTANT'}), UNITE_MONTANT)
        self.assertEqual(unite_declaree({'type': 'Pct'}), UNITE_PCT)
        # Une NATURE de tranche ne déclare aucune unité.
        self.assertIsNone(unite_declaree({'type': 'acompte'}))
        self.assertIsNone(unite_declaree({}))

    def test_valider_echeancier_refuse_une_non_liste(self):
        with self.assertRaises(EcheancierInvalide):
            valider_echeancier('pas-une-liste')

    def test_valider_echeancier_vide_ne_leve_pas(self):
        self.assertEqual(valider_echeancier(None), [])
        self.assertEqual(valider_echeancier([]), [])


# ═══════════════════════════════════════════════════════════════════════════
# 2. L'ÉCHÉANCIER D'UN DEVIS — lecture tolérante, calcul juste
# ═══════════════════════════════════════════════════════════════════════════
def _company():
    company, _ = Company.objects.get_or_create(
        slug='qjr21-co', defaults={'nom': 'QJR21 Co'})
    return company


def _user(company):
    return User.objects.create_user(
        username='qjr21_resp', password='x', role_legacy='responsable',
        company=company)


def _client_obj(company):
    return Client.objects.create(
        company=company, nom='QJR21', prenom='Client',
        email='qjr21@example.invalid', telephone='+212600000021')


def _devis(company, client_obj, ref, echeancier=None,
           statut=Devis.Statut.ACCEPTE):
    """Devis à 17 000 TTC : 15 000 HT + 2 000 TVA (split 10/20)."""
    devis = Devis.objects.create(
        company=company, reference=ref, client=client_obj, statut=statut,
        taux_tva=Decimal('20.00'), mode_installation='residentiel',
        echeancier=echeancier)
    panneau = Produit.objects.create(
        company=company, nom=f'Panneau {ref}', sku=f'PV-{ref}',
        prix_vente=Decimal('1000'), quantite_stock=100, tva=Decimal('10.00'))
    onduleur = Produit.objects.create(
        company=company, nom=f'Onduleur {ref}', sku=f'OND-{ref}',
        prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
    LigneDevis.objects.create(
        devis=devis, produit=panneau, designation='Panneau PV 450W',
        quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
        remise=Decimal('0'), taux_tva=Decimal('10.00'))
    LigneDevis.objects.create(
        devis=devis, produit=onduleur, designation='Onduleur 5kW',
        quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
        remise=Decimal('0'), taux_tva=Decimal('20.00'))
    return devis


class EcheancierDUnDevis(TestCase):

    def setUp(self):
        self.company = _company()
        self.client_obj = _client_obj(self.company)

    def test_pourcentage_valide_facture_le_pourcentage(self):
        devis = _devis(
            self.company, self.client_obj, f'DEV-{MONTH}-Q21A',
            echeancier=[
                {'libelle': 'Acompte', 'type': 'acompte',
                 'pct_or_montant': 40},
                {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 60},
            ])
        self.assertEqual(schedule_for_devis(devis),
                         [('acompte', 40.0), ('solde', 60.0)])
        tranche = next_tranche(devis)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['pourcentage'], Decimal('40.0'))
        # 40 % de 17 000 TTC.
        self.assertEqual(tranche['ttc'], Decimal('6800.00'))

    def test_montant_declare_vaut_ce_montant_et_non_un_pourcentage(self):
        """Fixture SOUS 1000 MAD (R4-B3) : 500 MAD d'acompte sur 17 000 TTC."""
        devis = _devis(
            self.company, self.client_obj, f'DEV-{MONTH}-Q21B',
            echeancier=[
                {'libelle': 'Acompte fixe', 'type': 'acompte',
                 'unite': 'montant', 'pct_or_montant': 500},
                {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 100},
            ])
        tranches = tranches_normalisees(devis)
        self.assertEqual(tranches[0]['unite'], UNITE_MONTANT)

        tranche = next_tranche(devis)
        # AVANT QJR21 : 500 était lu « 500 % » → 85 000 MAD de TTC facturé.
        self.assertEqual(tranche['ttc'], Decimal('500.00'))
        self.assertEqual(tranche['ht'] + tranche['tva'], Decimal('500.00'))
        # Le pourcentage publié est DÉRIVÉ (500 / 17 000), jamais la valeur
        # brute — c'est aussi ce qui garde ``Facture.pourcentage`` dans son
        # numeric(5, 2).
        self.assertEqual(tranche['pourcentage'], Decimal('2.94'))
        self.assertLess(tranche['pourcentage'], Decimal('100'))

    def test_echeancier_ambigu_deja_stocke_retombe_sur_le_defaut(self):
        """Lecture TOLÉRANTE : une donnée héritée ambiguë ne facture pas
        500 % du devis — elle retombe sur l'échéancier par défaut."""
        devis = _devis(
            self.company, self.client_obj, f'DEV-{MONTH}-Q21C',
            echeancier=[
                {'libelle': 'Acompte', 'type': 'acompte',
                 'pct_or_montant': 500},
            ])
        self.assertEqual(len(tranches_normalisees(devis)), 3)
        tranche = next_tranche(devis)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['ttc'], Decimal('5100.00'))  # 30 % de 17 000

    def test_echeancier_malforme_retombe_sur_le_defaut(self):
        devis = _devis(self.company, self.client_obj, f'DEV-{MONTH}-Q21D',
                       echeancier='pas-une-liste')
        self.assertEqual(len(schedule_for_devis(devis)), 3)


# ═══════════════════════════════════════════════════════════════════════════
# 3. L'API REFUSE EN 400 — la garde à l'écriture
# ═══════════════════════════════════════════════════════════════════════════
class ApiEcheancier(TestCase):

    def setUp(self):
        self.company = _company()
        self.user = _user(self.company)
        self.client_obj = _client_obj(self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis = _devis(self.company, self.client_obj,
                            f'DEV-{MONTH}-Q21E',
                            statut=Devis.Statut.BROUILLON)

    def _patch(self, echeancier):
        return self.api.patch(
            f'/api/django/ventes/devis/{self.devis.id}/',
            {'echeancier': echeancier}, format='json')

    def test_pourcentage_valide_accepte(self):
        reponse = self._patch([
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 30},
            {'libelle': 'Matériel', 'type': 'intermediaire',
             'pct_or_montant': 60},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10},
        ])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(len(self.devis.echeancier), 3)

    def test_montant_declare_accepte(self):
        """Fixture SOUS 1000 MAD (R4-B3)."""
        reponse = self._patch([
            {'libelle': 'Acompte fixe', 'type': 'acompte',
             'unite': 'montant', 'pct_or_montant': 750},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 100},
        ])
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.echeancier[0]['unite'], 'montant')

    def test_valeur_ambigue_refusee_en_400_en_francais(self):
        reponse = self._patch([
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 750},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 100},
        ])
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('echeancier', reponse.data)
        message = str(reponse.data['echeancier'])
        self.assertIn('ambigu', message)
        self.assertIn('montant', message)
        # Rien n'a été écrit.
        self.devis.refresh_from_db()
        self.assertIsNone(self.devis.echeancier)

    def test_liste_attendue(self):
        reponse = self._patch({'acompte': 30})
        self.assertEqual(reponse.status_code, 400, reponse.data)

    def test_echeancier_vide_reste_accepte(self):
        reponse = self._patch(None)
        self.assertEqual(reponse.status_code, 200, reponse.data)
