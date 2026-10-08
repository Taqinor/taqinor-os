"""ADEV29 (C-ADEV-039) — la permutation d'onduleur de la resynchronisation
calepinage suit la RÈGLE DU COMPOSEUR (plus petit modèle ≥ 0,8 × kWc, phase
du client) au lieu du « moins cher de la marque préférée ».

Rejoue VB r1 : devis « Sans batterie » (Huawei 10 kW TRIPHASÉ, 12 panneaux,
6,6 kWc), layout « avec batterie » → permutation vers « Deye 5 kW
Monophasé », sans avertissement.

Test-du-test : remettre ``_pick_product`` (« moins cher ») dans
``_permuter_onduleur`` ⇒ ``test_phase_conservee`` échoue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import sync_devis_from_layout
from apps.ventes.tests.test_pv18_sync_layout import layout, make_company

User = get_user_model()

PANNEAU = 'Panneau Jinko 550W'
RESEAU_TRI = 'Onduleur réseau Huawei 10kW Triphasé'


class ResyncOnduleurTests(TestCase):
    def setUp(self):
        self.company = make_company('adev29-co')
        self.user = User.objects.create_user(
            username='adev29', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client ADEV29')
        self.panneau = self._produit(PANNEAU, '1100')
        self.reseau = self._produit(RESEAU_TRI, '14000')
        self._produit('Batterie Dyness 5 kWh', '15000')

    def _produit(self, nom, prix):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=nom[:20] + str(len(nom)),
            prix_vente=Decimal(prix), prix_achat=Decimal('1'),
            quantite_stock=10)

    def _devis(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV29',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'),
            etude_params={'scenario': 'Sans batterie'})
        devis.lignes.create(
            produit=self.panneau, designation=PANNEAU, quantite=Decimal('12'),
            prix_unitaire=Decimal('1100'), remise=Decimal('0'), ordre=1)
        devis.lignes.create(
            produit=self.reseau, designation=RESEAU_TRI, quantite=Decimal('1'),
            prix_unitaire=Decimal('14000'), remise=Decimal('0'), ordre=2)
        return devis

    def _resync(self, devis):
        return sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='avec_batterie'),
            user=self.user)

    def _onduleurs(self, devis):
        return list(devis.lignes.filter(designation__icontains='onduleur')
                    .values_list('designation', flat=True))

    def test_phase_conservee(self):
        self._produit('Onduleur hybride Deye 5kW Monophasé', '9000')
        self._produit('Onduleur hybride Deye 6kW Triphasé', '21000')
        self._resync(self._devis())
        devis = Devis.objects.get(reference='DEV-ADEV29')
        self.assertEqual(self._onduleurs(devis),
                         ['Onduleur hybride Deye 6kW Triphasé'])

    def test_puissance_min_08_kwc(self):
        # 0,8 × 6,6 = 5,28 kW : le 5 kW triphasé est trop petit, le 8 kW est
        # le plus petit modèle suffisant (le 12 kW, plus gros, n'est pas pris).
        self._produit('Onduleur hybride Deye 5kW Triphasé', '15000')
        self._produit('Onduleur hybride Deye 8kW Triphasé', '24000')
        self._produit('Onduleur hybride Deye 12kW Triphasé', '20000')
        self._resync(self._devis())
        devis = Devis.objects.get(reference='DEV-ADEV29')
        self.assertEqual(self._onduleurs(devis),
                         ['Onduleur hybride Deye 8kW Triphasé'])
        ligne = devis.lignes.get(designation__icontains='hybride')
        self.assertEqual(ligne.prix_unitaire, Decimal('24000'))

    def test_aucun_candidat_avertit(self):
        self._produit('Onduleur hybride Deye 5kW Monophasé', '9000')
        resultat = self._resync(self._devis())
        devis = Devis.objects.get(reference='DEV-ADEV29')
        # L'onduleur d'origine reste ; le manque est DIT.
        self.assertEqual(self._onduleurs(devis), [RESEAU_TRI])
        texte = ' | '.join(resultat.get('avertissements') or ())
        self.assertIn('hybride', texte.lower())
