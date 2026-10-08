"""ACHT8 (C-ACHT-007) — LA lecture unique des quantités de la nomenclature
gelée d'un chantier, exposée par le sélecteur
`selectors.quantites_nomenclature_chantier` (option retenue × N villas,
repli sur le gel du devis si la nomenclature est vide) ; `_bom_quantities`
lui délègue, et le stock pourra la lire sans importer les services.

Rouge d'abord : la fonction n'existait pas.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_selecteur_nomenclature"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations import selectors
from apps.installations.models import Installation
from apps.installations.services import _bom_quantities
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()


class SelecteurNomenclatureTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht8', defaults={'nom': 'Co ACHT8'})
        self.user = User.objects.create_user(
            username='resp-acht8', password='x', company=self.company,
            role_legacy='responsable')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ACHT8', sku='PAN-ACHT8',
            prix_vente=Decimal('100'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur ACHT8', sku='OND-ACHT8',
            prix_vente=Decimal('1000'), quantite_stock=10)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='acht8@example.invalid')
        self.lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        self._n = 0

    def _chantier(self, lignes, etude_params=None):
        self._n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ACHT8-{self._n}',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel',
            etude_params=etude_params or {})
        for produit, qte in lignes:
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')
        return Installation.objects.get(devis=devis)

    def test_option_retenue(self):
        """Lit la nomenclature GELÉE, jamais les lignes courantes du devis."""
        inst = self._chantier([(self.panneau, 10), (self.onduleur, 1)])
        # Une ligne ajoutée au devis APRÈS le gel n'entre pas.
        intrus = Produit.objects.create(
            company=self.company, nom='Batterie intruse', sku='BAT-ACHT8',
            prix_vente=Decimal('10'), quantite_stock=5)
        LigneDevis.objects.create(
            devis=inst.devis, produit=intrus, designation='Batterie',
            quantite=Decimal('1'), prix_unitaire=Decimal('10'))
        self.assertEqual(
            selectors.quantites_nomenclature_chantier(inst),
            {self.panneau.id: 10, self.onduleur.id: 1})

    def test_multivilla_x3(self):
        inst = self._chantier([(self.panneau, 10), (self.onduleur, 1)],
                              etude_params={'nombre_proprietes': 3})
        self.assertEqual(
            selectors.quantites_nomenclature_chantier(inst),
            {self.panneau.id: 30, self.onduleur.id: 3})

    def test_parite_bom_quantities(self):
        inst = self._chantier([(self.panneau, Decimal('12.5')),
                               (self.onduleur, 1)])
        self.assertEqual(selectors.quantites_nomenclature_chantier(inst),
                         _bom_quantities(inst))
        self.assertEqual(
            selectors.quantites_nomenclature_chantier(inst)[self.panneau.id],
            13)

    def test_repli_devis(self):
        inst = self._chantier([(self.panneau, 4)])
        Installation.objects.filter(pk=inst.pk).update(bom=[])
        inst.refresh_from_db()
        self.assertEqual(
            selectors.quantites_nomenclature_chantier(inst),
            {self.panneau.id: 4})

    def test_plafond_err54(self):
        inst = self._chantier([(self.panneau, Decimal('12.2'))])
        self.assertEqual(
            selectors.quantites_nomenclature_chantier(inst, plafond=True),
            {self.panneau.id: 13})
        self.assertEqual(
            selectors.quantites_nomenclature_chantier(inst),
            {self.panneau.id: 12})
