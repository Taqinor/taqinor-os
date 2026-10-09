"""ACHT10 — `creer_bcf_depuis_lignes` : refus des quantités non entières / ≤ 0
et des prix négatifs (au lieu de la troncature silencieuse par `int()`), et
transmission du chantier d'origine (la réception réserve alors au chantier)."""
from decimal import Decimal
from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    confirm_reception_fournisseur, creer_bcf_depuis_lignes,
)
from authentication.models import Company

User = get_user_model()


class BcfDepuisLignesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACHT10', slug='acht10-co')
        self.user = User.objects.create_user(
            username='acht10', password='x', role_legacy='responsable',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ACHT10')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ACHT10', sku='ACHT10-1',
            prix_vente=Decimal('100'), prix_achat=Decimal('60'),
            quantite_stock=5)

    def _creer(self, lignes, **kw):
        return creer_bcf_depuis_lignes(
            company=self.company, user=self.user,
            fournisseur=self.fournisseur, lignes=lignes, **kw)

    def _aucun_bcf(self):
        self.assertEqual(
            BonCommandeFournisseur.objects.filter(
                company=self.company).count(), 0)

    def test_quantite_decimale_refusee(self):
        with self.assertRaises(ValueError) as ctx:
            self._creer([
                {'produit': self.produit.id, 'quantite': 2.5},
                {'designation': 'cable', 'quantite': 0.5}])
        self.assertIn('Ligne 1', str(ctx.exception))
        self.assertIn('2,5', str(ctx.exception))
        self.assertIn('non entière', str(ctx.exception))
        self._aucun_bcf()

    def test_quantite_decimale_tuple_historique_refusee(self):
        with self.assertRaises(ValueError):
            self._creer([(self.produit.id, 'x', Decimal('2.5'), 10)])
        self._aucun_bcf()

    def test_quantite_nulle_negative_refusee(self):
        for qte in (0, -3):
            with self.assertRaises(ValueError) as ctx:
                self._creer([{'designation': 'neg', 'quantite': qte}])
            self.assertIn('Ligne 1', str(ctx.exception))
        self._aucun_bcf()

    def test_prix_negatif_refuse(self):
        with self.assertRaises(ValueError) as ctx:
            self._creer([
                {'designation': 'ok', 'quantite': 1, 'prix': 5},
                {'designation': 'zero', 'quantite': 1, 'prix': -5}])
        self.assertIn('Ligne 2', str(ctx.exception))
        self._aucun_bcf()

    def test_lot_valide_inchange(self):
        bon = self._creer([(self.produit.id, 'p', Decimal('3'), Decimal('10'))])
        ligne = bon.lignes.get()
        self.assertEqual(ligne.quantite, 3)
        self.assertEqual(ligne.prix_achat_unitaire, Decimal('10'))
        self.assertIsNone(bon.chantier_origine_id)

    def test_chantier_autre_societe_refuse(self):
        autre = Company.objects.create(nom='Autre', slug='acht10-autre')

        class _Chantier:
            company_id = autre.pk
        with self.assertRaises(ValueError):
            self._creer([{'designation': 'x', 'quantite': 1}],
                        chantier_origine=_Chantier())
        self._aucun_bcf()

    def test_chantier_origine_pose_et_reserve(self):
        # Modèles des autres apps résolus par nom (frontière inter-apps :
        # aucun import statique de crm/ventes/installations depuis stock).
        Client, Lead = (django_apps.get_model('crm', n)
                        for n in ('Client', 'Lead'))
        Devis, LigneDevis = (django_apps.get_model('ventes', n)
                             for n in ('Devis', 'LigneDevis'))
        StockReservation = django_apps.get_model(
            'installations', 'StockReservation')
        create_installation_from_devis = import_module(
            'apps.installations.services').create_installation_from_devis
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='C',
            email='acht10@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='C', stage='SIGNED',
            type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACHT10-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='P',
            quantite=Decimal('20'), prix_unitaire=Decimal('100'))
        inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        StockReservation.objects.filter(installation=inst).delete()

        bon = self._creer(
            [(self.produit.id, 'P', 2, 10)], chantier_origine=inst)
        self.assertEqual(bon.chantier_origine_id, inst.id)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ACHT10-1', bon_commande=bon,
            statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        rec.lignes.create(
            ligne_commande=bon.lignes.get(), produit=self.produit, quantite=2)
        confirm_reception_fournisseur(rec, self.user)
        resa = StockReservation.objects.get(
            installation=inst, produit=self.produit)
        self.assertEqual(resa.quantite, 2)
