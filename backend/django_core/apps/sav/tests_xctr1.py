"""XCTR1 — Produit récurrent → conversion devis-accepté en contrat.

Couvre :
  * devis accepté avec une ligne dont le produit est `est_recurrent` → crée
    exactement UN `ContratMaintenance` (jamais deux en cas de double signal) ;
  * devis accepté SANS ligne récurrente → aucun contrat créé ;
  * prix du contrat = total TTC des lignes récurrentes uniquement ;
  * périodicité reprise du produit récurrent quand renseignée.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_xctr1 -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.sav.models import ContratMaintenance
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='sav-xctr1', nom='Sav Co XCTR1'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class XCTR1DevisAccepteContratTest(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='xctr1_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='XCTR1',
            email='xctr1-client@example.invalid')
        self.produit_recurrent = Produit.objects.create(
            company=self.company, nom='Monitoring annuel', sku='MON-XCTR1',
            prix_achat=0, prix_vente=1200,
            est_recurrent=True,
            periodicite_defaut=Produit.PeriodiciteDefaut.TRIMESTRIEL)
        self.produit_normal = Produit.objects.create(
            company=self.company, nom='Panneau PV', sku='PAN-XCTR1',
            prix_achat=800, prix_vente=1500)

    def _devis(self, num, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def test_devis_with_recurring_line_creates_one_contract(self):
        devis = self._devis(1, statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit_recurrent,
            designation='Monitoring annuel', quantite=1,
            prix_unitaire=Decimal('1200'), taux_tva=Decimal('20'))

        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')

        self.assertEqual(
            ContratMaintenance.objects.filter(client=self.client_obj).count(), 1)
        contrat = ContratMaintenance.objects.get(client=self.client_obj)
        self.assertEqual(contrat.periodicite, 'trimestriel')
        self.assertEqual(contrat.prix, Decimal('1440.00'))  # 1200 * 1.20
        self.assertIn(f'[devis:{devis.pk}]', contrat.notes)

        # Double émission du signal (retry / double clic) : pas de second contrat.
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        self.assertEqual(
            ContratMaintenance.objects.filter(client=self.client_obj).count(), 1)

    def test_devis_without_recurring_line_creates_no_contract(self):
        devis = self._devis(2, statut=Devis.Statut.ACCEPTE)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit_normal,
            designation='Panneau PV', quantite=10,
            prix_unitaire=Decimal('1500'), taux_tva=Decimal('20'))

        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')

        self.assertEqual(
            ContratMaintenance.objects.filter(client=self.client_obj).count(), 0)
