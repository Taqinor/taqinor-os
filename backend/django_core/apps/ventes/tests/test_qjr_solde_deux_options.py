"""QJR24 — le solde d'un devis à deux options NON accepté suit le total affiché.

``utils/options.option_totaux`` résolvait l'option par défaut sur la seule
``option_acceptee`` : tant que le devis n'était pas accepté, aucun filtre ne
s'appliquait et le solde comme l'échéancier étaient bâtis sur la SOMME des
deux options — un montant qui n'existe dans aucun document et que le client ne
paiera jamais.

DÉCISION FONDATEUR D9 (29/08/2026) — avant acceptation, le solde suit le TOTAL
AFFICHÉ (la même option que ``total_affiche`` : la recommandée / AVEC) ; après
acceptation, l'option acceptée. Plus jamais la somme des deux.

Le devis de référence (mêmes chiffres que ``test_options``) :

    réseau 11 700 · hybride 24 000 · panneaux 14 × 1 100 · batterie 14 000 ·
    installation 4 000, TVA 20 %

    → option SANS  = 31 100 HT → 37 320 TTC
    → option AVEC  = 57 400 HT → 68 880 TTC
    → somme des deux (le bug) = 69 100 HT → 82 920 TTC

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr_solde_deux_options"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import display_totals
from apps.ventes.utils.echeancier import next_tranche, solde_devis
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, option_effective, option_lines,
    option_totaux,
)

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')

TTC_SANS = Decimal('37320.00')
TTC_AVEC = Decimal('68880.00')
#: Le montant que le solde affichait AVANT QJR24 : la somme des deux paniers.
TTC_SOMME_DES_DEUX = Decimal('82920.00')


class _Base(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qjr24-co', defaults={'nom': 'QJR24 Co'})
        self.user = User.objects.create_user(
            username='qjr24_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR24',
            email='qjr24@example.invalid', telephone='+212600000024')
        self.compteur = 0

    def _lignes(self, devis, lignes, prefixe):
        for desig, qty, pu in lignes:
            produit = Produit.objects.create(
                company=self.company, nom=desig,
                sku=f'{prefixe}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))

    def _devis_deux_options(self, statut=Devis.Statut.ENVOYE, option=''):
        """PV86 — un document à DEUX options DÉCLARE son alternative dans
        ``etude_params['scenario']`` (ce que le générateur persiste)."""
        self.compteur += 1
        prefixe = f'Q24{self.compteur:02d}'
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{prefixe}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            option_acceptee=option,
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        self._lignes(devis, [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ], prefixe)
        return devis

    def _devis_option_unique(self):
        self.compteur += 1
        prefixe = f'Q24U{self.compteur:02d}'
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{prefixe}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self._lignes(devis, [
            ('Onduleur réseau', '1', '11700'),
            ('Panneau mono 550W', '14', '1100'),
        ], prefixe)
        return devis


class SoldeAvantAcceptation(_Base):
    """D9 — avant acceptation, l'argent suit le TOTAL AFFICHÉ."""

    def test_le_solde_est_le_total_de_loption_mise_en_avant(self):
        devis = self._devis_deux_options()
        solde = solde_devis(devis)
        self.assertEqual(solde['total_ttc'], TTC_AVEC)
        self.assertEqual(solde['restant'], TTC_AVEC)

    def test_le_solde_nest_plus_la_somme_des_deux_options(self):
        """La régression que QJR24 corrige, épinglée nommément."""
        devis = self._devis_deux_options()
        self.assertNotEqual(solde_devis(devis)['total_ttc'],
                            TTC_SOMME_DES_DEUX)

    def test_le_solde_egale_le_total_affiche(self):
        """« Le solde suit le TOTAL AFFICHÉ » — la formulation exacte de D9 :
        le nombre du solde et celui de la liste sortent de la même option."""
        devis = self._devis_deux_options()
        affiche = display_totals(devis)
        self.assertEqual(affiche['nb_options'], 2)
        ecart = abs(Decimal(str(affiche['total']))
                    - solde_devis(devis)['total_ttc'])
        self.assertLessEqual(ecart, Decimal('0.01'), (
            f"solde {solde_devis(devis)['total_ttc']} != total affiché "
            f"{affiche['total']}"))

    def test_lecheancier_suit_la_meme_option(self):
        """Échéancier COHÉRENT : l'acompte est 30 % du total affiché."""
        devis = self._devis_deux_options()
        tranche = next_tranche(devis)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['ttc'], Decimal('20664.00'))  # 30 % de 68 880

    def test_les_lignes_suivent_la_meme_option_que_largent(self):
        """Les lignes et l'argent décrivent la MÊME vente."""
        devis = self._devis_deux_options()
        designations = {li.designation for li in option_lines(devis)}
        self.assertIn('Onduleur hybride', designations)
        self.assertIn('Batterie 5 kWh', designations)
        self.assertNotIn('Onduleur réseau', designations)

    def test_option_effective_avant_acceptation(self):
        devis = self._devis_deux_options()
        self.assertEqual(option_effective(devis), AVEC_BATTERIE)


class SoldeApresAcceptation(_Base):
    """A3 conservé — après acceptation, l'option acceptée fait foi."""

    def test_acceptation_de_sans_le_solde_suit_sans(self):
        devis = self._devis_deux_options(
            statut=Devis.Statut.ACCEPTE, option=SANS_BATTERIE)
        self.assertEqual(option_effective(devis), SANS_BATTERIE)
        solde = solde_devis(devis)
        self.assertEqual(solde['total_ttc'], TTC_SANS)
        self.assertNotEqual(solde['total_ttc'], TTC_AVEC)
        self.assertNotEqual(solde['total_ttc'], TTC_SOMME_DES_DEUX)

    def test_acceptation_de_sans_lecheancier_suit_sans(self):
        devis = self._devis_deux_options(
            statut=Devis.Statut.ACCEPTE, option=SANS_BATTERIE)
        tranche = next_tranche(devis)
        self.assertEqual(tranche['key'], 'acompte')
        self.assertEqual(tranche['ttc'], Decimal('11196.00'))  # 30 % de 37 320

    def test_acceptation_de_avec_le_solde_suit_avec(self):
        devis = self._devis_deux_options(
            statut=Devis.Statut.ACCEPTE, option=AVEC_BATTERIE)
        self.assertEqual(solde_devis(devis)['total_ttc'], TTC_AVEC)
        self.assertEqual(next_tranche(devis)['ttc'], Decimal('20664.00'))


class DevisSansAlternativeInchange(_Base):
    """Non-régression : un devis à option unique ne change pas d'un centime."""

    def test_option_effective_vide_sur_option_unique(self):
        devis = self._devis_option_unique()
        self.assertEqual(option_effective(devis), '')

    def test_totaux_complets_sur_option_unique(self):
        devis = self._devis_option_unique()
        totaux = option_totaux(devis)
        self.assertEqual(totaux['ht'], Decimal(str(devis.total_ht)))
        self.assertEqual(totaux['ttc'], Decimal(str(devis.total_ttc)))
        self.assertEqual(len(option_lines(devis)), 2)

    def test_solde_complet_sur_option_unique(self):
        devis = self._devis_option_unique()
        self.assertEqual(solde_devis(devis)['total_ttc'],
                         Decimal(str(devis.total_ttc)).quantize(
                             Decimal('0.01')))
