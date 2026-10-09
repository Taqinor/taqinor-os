"""ACHT9 (C-ACHT-007/008) — le besoin matériel d'un chantier lit la
NOMENCLATURE GELÉE (option retenue × N villas) via
`installations.selectors.quantites_nomenclature_chantier`, retranche du manque
la quantité déjà EN COMMANDE (BCF brouillon/envoyé non reçu du chantier) et
`draft_bcf_for_shortfall` est idempotent.

Rejoue CACH-1 (BCF pour une option non retenue ; ×3 → 10/10/1 au lieu de
30/30/3) et CACH-2 (deux BCF, manque 1 avec BCF envoyé).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.stock.test_acht_besoin_chantier"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.installations.models import Installation
from apps.stock.models import BonCommandeFournisseur, Fournisseur, Produit
from apps.stock.services import (
    compute_besoin_materiel, draft_bcf_for_shortfall,
)
from apps.ventes.models import Client, Devis, LigneDevis

User = get_user_model()


class BesoinChantierTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT9', slug='acht9-co')
        self.user = User.objects.create_user(
            username='resp-acht9', password='x', company=self.company,
            role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ACHT9')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau', sku='PAN-ACHT9',
            prix_vente=Decimal('100'), prix_achat=Decimal('60'),
            quantite_stock=0, fournisseur=self.fournisseur)
        self.batterie = Produit.objects.create(
            company=self.company, nom='Batterie', sku='BAT-ACHT9',
            prix_vente=Decimal('900'), prix_achat=Decimal('600'),
            quantite_stock=0, fournisseur=self.fournisseur)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='ACHT9',
            email='acht9@example.invalid')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT9', client=client,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        # Le devis porte aussi une batterie (option NON retenue) ; la
        # nomenclature gelée du chantier, elle, n'a que le panneau.
        for produit, qte in ((self.panneau, 10), (self.batterie, 1)):
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=Decimal('100'))
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ACHT9', devis=self.devis,
            bom=[{'produit_id': self.panneau.id, 'designation': 'Panneau',
                  'quantite': 10.0}])

    def _par_produit(self):
        return {b['produit_id']: b
                for b in compute_besoin_materiel(self.chantier)}

    def test_option_non_retenue_ignoree(self):
        besoins = self._par_produit()
        self.assertIn(self.panneau.id, besoins)
        self.assertNotIn(self.batterie.id, besoins)
        self.assertEqual(besoins[self.panneau.id]['requis'], 10)

    def test_multivilla_x3(self):
        # Nomenclature gelée d'un devis ×3 villas : quantités déjà × 3.
        Installation.objects.filter(pk=self.chantier.pk).update(
            bom=[{'produit_id': self.panneau.id, 'designation': 'Panneau',
                  'quantite': 30.0}])
        self.chantier.refresh_from_db()
        self.assertEqual(self._par_produit()[self.panneau.id]['requis'], 30)

    def test_double_commande_refusee(self):
        bon, nb = draft_bcf_for_shortfall(
            self.chantier, self.fournisseur, self.user, self.company)
        self.assertEqual(nb, 1)
        self.assertEqual(bon.chantier_origine_id, self.chantier.id)
        with self.assertRaises(ValueError) as ctx:
            draft_bcf_for_shortfall(
                self.chantier, self.fournisseur, self.user, self.company)
        self.assertIn('Un BCF ouvert couvre déjà ces manques', str(ctx.exception))
        self.assertIn(bon.reference, str(ctx.exception))
        self.assertEqual(BonCommandeFournisseur.objects.filter(
            company=self.company, chantier_origine=self.chantier).count(), 1)

    def test_bcf_envoye_retranche(self):
        bon, _nb = draft_bcf_for_shortfall(
            self.chantier, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])
        besoin = self._par_produit()[self.panneau.id]
        self.assertEqual(besoin['manque_brut'], 10)
        self.assertEqual(besoin['en_commande'], 10)
        self.assertEqual(besoin['manque'], 0)
