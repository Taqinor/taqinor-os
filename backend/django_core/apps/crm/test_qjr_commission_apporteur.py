"""QJR22 — Commission apporteur : % × total NET de l'OPTION ACCEPTÉE.

Avant ce correctif, ``_calculer_commission_deal_on_devis_accepted``
(``crm/receivers.py``) calculait la commission sur ``devis.total_ht`` — le
total BRUT (remise globale ignorée) de TOUTES les lignes du devis. Sur un
devis à deux options, cela revenait à commissionner la SOMME DES DEUX
options, un montant qui ne correspond à aucune vente réelle (origine :
R4-B2.1).

Décision fondateur D3 (29/08/2026) : la commission est un pourcentage du
total NET (remise globale honorée) de l'OPTION ACCEPTÉE SEULE, calculé par
la chaîne canonique par option (``apps.ventes.utils.options.option_totaux``
— la même source que l'échéancier/le bon de commande). Ce module prouve :
(1) un devis remisé à deux options accepté sur l'option AVEC commissionne
le total NET de CETTE option, pas le brut des deux ; (2) idem pour l'option
SANS ; (3) un devis mono-option (comportement historique NTCRM22) reste
inchangé au centime.

NOTE — ce fichier vit à plat dans ``apps/crm/`` (comme tous les autres
tests de cette app, ex. ``tests_ntcrm22_commission_deal.py``), jamais dans
un sous-paquet ``apps/crm/tests/`` : ``apps/crm/tests.py`` existe déjà
comme MODULE historique (TestLeadModel…) — un sous-paquet ``tests/`` du
même nom l'aurait silencieusement masqué (les paquets priment sur les
modules du même nom dans l'import Python), désactivant tous ses tests sans
la moindre erreur visible.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.test_qjr_commission_apporteur -v 2
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Apporteur, DealEnregistre, Lead
from apps.crm.services import resolve_client_for_lead
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted


class CommissionOptionAccepteeTests(TestCase):
    """Devis remisé à deux options : la commission suit l'option ACCEPTÉE,
    au NET, jamais le brut ni la somme des deux."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QJR22', slug='taqinor-qjr22')
        self.apporteur = Apporteur.objects.create(
            company=self.company, nom='Apporteur QJR22',
            taux_commission_pct=Decimal('5.00'))
        self.lead = Lead.objects.create(company=self.company, nom='Lead QJR22')
        self.deal = DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur, lead=self.lead,
            statut=DealEnregistre.Statut.APPROUVE)
        self.client_obj = resolve_client_for_lead(self.lead)

    def _devis_deux_options(self, reference):
        devis = Devis.objects.create(
            company=self.company, client=self.client_obj, lead=self.lead,
            reference=reference, statut=Devis.Statut.ACCEPTE,
            remise_globale=Decimal('10.00'))
        # Ligne commune aux deux options (variante='' = défaut).
        LigneDevis.objects.create(
            devis=devis, designation='Panneaux mono 550W', quantite=1,
            prix_unitaire=Decimal('10000.00'))
        # Option « sans batterie » seule (F14 — variante déclarée, exclusive).
        LigneDevis.objects.create(
            devis=devis, designation='Onduleur réseau 8kW', quantite=1,
            prix_unitaire=Decimal('8000.00'), variante='sans')
        # Option « avec batterie » seule.
        LigneDevis.objects.create(
            devis=devis, designation='Onduleur hybride 5kW', quantite=1,
            prix_unitaire=Decimal('12000.00'), variante='avec')
        LigneDevis.objects.create(
            devis=devis, designation='Batterie 5 kWh', quantite=1,
            prix_unitaire=Decimal('6000.00'), variante='avec')
        return devis

    def test_commission_sur_total_net_option_avec_acceptee(self):
        devis = self._devis_deux_options('DEV-QJR22-AVEC')
        devis.option_acceptee = Devis.OptionAcceptee.AVEC_BATTERIE
        devis.save(update_fields=['option_acceptee'])

        devis_accepted.send(
            sender='test', devis=devis, user=None, ancien_statut='envoye')
        self.deal.refresh_from_db()

        # HT brut option AVEC = 10000 (commun) + 12000 + 6000 = 28000 ;
        # net après 10 % de remise globale = 25200.00 ; commission 5 % = 1260.00.
        self.assertEqual(self.deal.montant_commission_du, Decimal('1260.00'))
        self.assertEqual(self.deal.statut, DealEnregistre.Statut.A_PAYER)
        # AVANT le correctif, le calcul portait sur devis.total_ht (brut,
        # TOUTES les lignes des deux options confondues = 36000.00, aucune
        # remise) : 5 % × 36000 = 1800.00 — un montant qu'aucune vente ne
        # justifie. Nommé explicitement pour la traçabilité de la régression.
        self.assertNotEqual(
            self.deal.montant_commission_du, Decimal('1800.00'))

    def test_commission_sur_total_net_option_sans_acceptee(self):
        devis = self._devis_deux_options('DEV-QJR22-SANS')
        devis.option_acceptee = Devis.OptionAcceptee.SANS_BATTERIE
        devis.save(update_fields=['option_acceptee'])

        devis_accepted.send(
            sender='test', devis=devis, user=None, ancien_statut='envoye')
        self.deal.refresh_from_db()

        # HT brut option SANS = 10000 (commun) + 8000 = 18000 ;
        # net après 10 % de remise = 16200.00 ; commission 5 % = 810.00.
        self.assertEqual(self.deal.montant_commission_du, Decimal('810.00'))


class CommissionMonoOptionUnchangedTests(TestCase):
    """Devis mono-option (comportement historique NTCRM22) : au centime
    près — même fixture/assertion que ``tests_ntcrm22_commission_deal.py``."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QJR22mono', slug='taqinor-qjr22mono')
        self.apporteur = Apporteur.objects.create(
            company=self.company, nom='Apporteur commission',
            taux_commission_pct=Decimal('5.00'))
        self.lead = Lead.objects.create(company=self.company, nom='Lead deal')
        self.deal = DealEnregistre.objects.create(
            company=self.company, apporteur=self.apporteur, lead=self.lead,
            statut=DealEnregistre.Statut.APPROUVE)
        self.client_obj = resolve_client_for_lead(self.lead)
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_obj, lead=self.lead,
            reference='DVC1QJR22MONO', statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=self.devis, designation='Panneau', quantite=1,
            prix_unitaire=Decimal('10000.00'))

    def test_commission_calculee_et_statut_a_payer(self):
        devis_accepted.send(
            sender='test', devis=self.devis, user=None, ancien_statut='envoye')
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.statut, DealEnregistre.Statut.A_PAYER)
        self.assertEqual(self.deal.montant_commission_du, Decimal('500.00'))
