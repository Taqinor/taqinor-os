"""ADEV55 — le contrat de maintenance né d'un devis accepté ne porte que les
lignes de l'OPTION ACCEPTÉE ; une ligne optionnelle non activée n'y entre
jamais.

Run :
    python manage.py test apps.sav.tests_adev55_contrat_option_retenue -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ContratMaintenance
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class ContratOptionRetenueTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='adev55-co', defaults={'nom': 'ADEV55 Co'})
        self.user = User.objects.create_user(
            username='adev55_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV55',
            email='adev55@example.invalid')
        self.recurrent = Produit.objects.create(
            company=self.company, nom='Onduleur hybride', sku='OND-HYB-55',
            prix_achat=0, prix_vente=28000, est_recurrent=True)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-55', prix_achat=0,
            prix_vente=1000)
        # Un VRAI devis à deux options (onduleur réseau d'un côté, hybride +
        # batterie de l'autre) : sans cela le noyau ne filtre rien.
        self.reseau = Produit.objects.create(
            company=self.company, nom='Onduleur réseau injection',
            sku='OND-RES-55', prix_achat=0, prix_vente=9000)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie lithium 10 kWh',
            sku='BAT-55', prix_achat=0, prix_vente=30000)

    def _devis(self, num, *, option, optionnelle=False):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{7000 + num}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            option_acceptee=option, taux_tva=Decimal('20'),
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=10, prix_unitaire=Decimal('1000'),
            taux_tva=Decimal('20'), variante='')
        LigneDevis.objects.create(
            devis=devis, produit=self.reseau,
            designation='Onduleur réseau injection', quantite=1,
            prix_unitaire=Decimal('9000'), taux_tva=Decimal('20'),
            variante='sans')
        LigneDevis.objects.create(
            devis=devis, produit=self.batterie,
            designation='Batterie lithium 10 kWh', quantite=1,
            prix_unitaire=Decimal('30000'), taux_tva=Decimal('20'),
            variante='avec')
        LigneDevis.objects.create(
            devis=devis, produit=self.recurrent, designation='Onduleur hybride',
            quantite=1, prix_unitaire=Decimal('28000'),
            taux_tva=Decimal('20'), variante='avec', optionnelle=optionnelle)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        return devis

    def _contrats(self, devis):
        return ContratMaintenance.objects.filter(
            company=self.company, notes__contains=f'[devis:{devis.pk}]')

    def test_sans_batterie_aucun_contrat_onduleur(self):
        devis = self._devis(1, option='sans_batterie')
        self.assertEqual(self._contrats(devis).count(), 0)

    def test_avec_batterie_contrat_cree(self):
        devis = self._devis(2, option='avec_batterie')
        contrats = list(self._contrats(devis))
        self.assertEqual(len(contrats), 1)
        self.assertEqual(contrats[0].prix, Decimal('33600.00'))

    def test_optionnelle_non_activee_exclue(self):
        devis = self._devis(3, option='avec_batterie', optionnelle=True)
        self.assertEqual(self._contrats(devis).count(), 0)
