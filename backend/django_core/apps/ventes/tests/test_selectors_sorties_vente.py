"""ASTK257 (C-ASTK-VER4-040) — ``sorties_de_la_vente`` : Σ des SORTIES sous
la référence du devis, de ses BC et de son chantier, chaque mouvement une
fois. Nouveau fichier car : ``selectors.py`` n'a aucun module de test canonique.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_selectors_sorties_vente"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.services import create_installation_from_devis
from apps.stock.models import MouvementStock, Produit
from apps.stock.services import mouvement_type_sortie
from apps.ventes.models import BonCommande, Devis, LigneDevis
from apps.ventes.selectors import sorties_de_la_vente

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class SortiesDeLaVenteTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Co ASTK257', slug=f'co-astk257-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'resp-astk257-{_nxt()}', password='x',
            company=self.company, role_legacy='responsable')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK257',
            sku=f'SKU-ASTK257-{_nxt()}', prix_vente=Decimal('100'),
            quantite_stock=30, tva=Decimal('20.00'))
        self.client_obj = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email=f'astk257-{_nxt()}@example.invalid')

    def _devis(self, chantier=True):
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-ASTK257-{_nxt()}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        inst = None
        if chantier:
            inst, _ = create_installation_from_devis(
                devis, self.user, self.company)
        return devis, inst

    def _sortie(self, reference, qte):
        MouvementStock.objects.create(
            company=self.company, produit=self.panneau,
            type_mouvement=mouvement_type_sortie(), quantite=qte,
            quantite_avant=0, quantite_apres=0, reference=reference)

    def test_somme_devis_bc_chantier_une_fois(self):
        devis, inst = self._devis()
        self._sortie(devis.reference, 10)  # facture émise
        self._sortie(inst.reference, 3)  # F11
        self.assertEqual(
            sorties_de_la_vente(devis.id, self.company),
            {self.panneau.id: Decimal('13')})

    def test_sans_chantier_devis_et_bc(self):
        devis, _ = self._devis(chantier=False)
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-ASTK257-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        self._sortie(devis.reference, 4)
        self._sortie(bc.reference, 2)
        self._sortie('AUTRE-REF', 7)  # hors vente
        self.assertEqual(
            sorties_de_la_vente(devis.id, self.company),
            {self.panneau.id: Decimal('6')})

    def test_devis_inconnu_ou_autre_societe(self):
        devis, _ = self._devis(chantier=False)
        self._sortie(devis.reference, 4)
        autre = Company.objects.create(
            nom='Autre ASTK257', slug=f'autre-astk257-{_nxt()}')
        self.assertEqual(sorties_de_la_vente(devis.id, autre), {})
        self.assertEqual(sorties_de_la_vente(999999999, self.company), {})
