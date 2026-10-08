"""ASTK108/ASTK109 — facturation fournisseur « sur commande » (ZPUR1) vs
« sur réception » (FG56) : une ligne sur commande n'est jamais facturée deux
fois ; les deux chemins partagent un constructeur unique (date, acomptes,
événement).

Run:
    python manage.py test apps.stock.test_astk_facturation_sur_commande
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur, Produit,
    ReceptionFournisseur,
)
from apps.stock.services import facturer_bcf_sur_commande, facturer_reception
from testkit.time import frozen

User = get_user_model()


class _Base(TestCase):
    slug = 'astk108'

    def setUp(self):
        self.company = Company.objects.create(
            nom=f'{self.slug}-co', slug=f'{self.slug}-co')
        role = Role.objects.create(
            company=self.company, nom=f'r-{self.slug}',
            permissions=['stock_voir', 'stock_modifier',
                         # ASTK17-20 (D-ASTK-3) : l'acheteur porte les codes achats.
                         'achats_commander', 'achats_receptionner',
                         'achats_payer', 'catalogue_prix_modifier'])
        self.user = User.objects.create_user(
            username=f'{self.slug}-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom=f'Fournisseur {self.slug}')
        self.p_commande = Produit.objects.create(
            company=self.company, nom='Panneau import',
            sku=f'PV-CMD-{self.slug}', prix_vente=Decimal('200'),
            prix_achat=Decimal('100'), tva=Decimal('20'),
            politique_facturation_achat=(
                Produit.PolitiqueFacturationAchat.SUR_COMMANDE))
        self.p_reception = Produit.objects.create(
            company=self.company, nom='Câble', sku=f'CAB-REC-{self.slug}',
            prix_vente=Decimal('20'), prix_achat=Decimal('10'),
            tva=Decimal('20'))
        self.bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-{self.slug}-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.l_commande = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.p_commande, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        self.n = 0

    def _reception(self, lignes):
        self.n += 1
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-{self.slug}-{self.n}',
            bon_commande=self.bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        for ligne_bcf, quantite in lignes:
            LigneReceptionFournisseur.objects.create(
                reception=rec, ligne_commande=ligne_bcf,
                produit=ligne_bcf.produit, quantite=quantite)
        return rec

    def _total_ht_bcf(self):
        return FactureFournisseur.objects.filter(
            company=self.company, bon_commande=self.bcf).aggregate(
            t=Sum('montant_ht'))['t']


class SurCommandeTests(_Base):
    slug = 'astk108'

    def test_ligne_sur_commande_pas_refacturee(self):
        facturer_bcf_sur_commande(self.company, self.user, self.bcf)
        rec = self._reception([(self.l_commande, 10)])
        with self.assertRaisesMessage(ValueError, 'Rien à facturer'):
            facturer_reception(self.company, self.user, rec)
        # Relu : une seule facture, Σ HT = 1 000.
        self.assertEqual(
            FactureFournisseur.objects.filter(
                company=self.company, bon_commande=self.bcf).count(), 1)
        self.assertEqual(self._total_ht_bcf(), Decimal('1000.00'))

    def test_reception_mixte_ne_facture_que_sur_reception(self):
        l_reception = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.p_reception, quantite=50,
            prix_achat_unitaire=Decimal('10'))
        facturer_bcf_sur_commande(self.company, self.user, self.bcf)
        rec = self._reception([(self.l_commande, 10), (l_reception, 50)])
        facture = facturer_reception(self.company, self.user, rec)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.montant_ht, Decimal('500.00'))
        self.assertEqual(
            list(facture.lignes.values_list('designation', flat=True)),
            ['Câble'])
        self.assertEqual(self._total_ht_bcf(), Decimal('1500.00'))


class BuilderUniqueTests(_Base):
    """ASTK109 — un seul constructeur : la facture « sur commande » porte sa
    date, impute les acomptes du BCF et émet l'événement une fois."""
    slug = 'astk109'

    def setUp(self):
        super().setUp()
        from core.events import facture_fournisseur_creee
        self.recus = []

        def _capte(sender, instance, company, user=None, **kwargs):
            self.recus.append(instance.pk)
        facture_fournisseur_creee.connect(
            _capte, dispatch_uid='astk109-capte', weak=False)
        self.addCleanup(
            facture_fournisseur_creee.disconnect,
            dispatch_uid='astk109-capte')

    def test_sur_commande_porte_date_facture(self):
        with frozen('2026-10-06 10:00:00'):
            facture = facturer_bcf_sur_commande(
                self.company, self.user, self.bcf)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertIsNotNone(facture.date_facture)
        self.assertEqual(facture.date_facture, datetime.date(2026, 10, 6))
        self.assertEqual(self.recus, [facture.pk])

    def test_sur_commande_impute_acompte(self):
        from apps.stock.models import AcompteFournisseur
        acompte = AcompteFournisseur.objects.create(
            company=self.company, bon_commande=self.bcf,
            montant=Decimal('300'))
        facture = facturer_bcf_sur_commande(
            self.company, self.user, self.bcf)
        facture = FactureFournisseur.objects.get(pk=facture.pk)
        self.assertEqual(facture.total_acomptes_imputes, Decimal('300.00'))
        self.assertEqual(
            facture.solde_du, facture.montant_ttc - Decimal('300'))
        acompte.refresh_from_db()
        self.assertEqual(acompte.montant_consomme, Decimal('300.00'))
        self.assertEqual(acompte.imputations.get().facture_id, facture.pk)

    def test_meme_forme_que_sur_reception(self):
        l_reception = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bcf, produit=self.p_reception, quantite=10,
            prix_achat_unitaire=Decimal('100'))
        f_cmd = facturer_bcf_sur_commande(self.company, self.user, self.bcf)
        rec = self._reception([(l_reception, 10)])
        f_rec = facturer_reception(self.company, self.user, rec)
        for f in (f_cmd, f_rec):
            f = FactureFournisseur.objects.get(pk=f.pk)
            self.assertEqual(f.montant_ht, Decimal('1000.00'))
            self.assertEqual(f.montant_tva, Decimal('200.00'))
            self.assertEqual(f.montant_ttc, Decimal('1200.00'))
            self.assertIsNotNone(f.date_facture)
            self.assertEqual(f.lignes.count(), 1)
        self.assertEqual(self.recus, [f_cmd.pk, f_rec.pk])
