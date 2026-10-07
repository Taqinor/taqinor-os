"""ASTK48 — double validation d'une session d'inventaire / d'une
revalorisation : l'effet n'est appliqué qu'une fois.

Constat C-ASTK-010 (sonde MVT-9) : ``valider_inventaire_session`` et
``valider_revalorisation`` testaient le statut sur l'instance PASSÉE, sans la
relire sous verrou. Deux instances chargées avant la première validation
(double clic, deux onglets) passaient toutes deux la garde : 2 AJUSTEMENT,
stock 80 au lieu de 90. Les instances périmées sont la simulation
déterministe de la course, comme la sonde.

Run :
    python manage.py test apps.stock.test_astk_verrou_validation -v 2
"""
import itertools
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import (
    InventaireSession, LigneInventaire, MouvementStock, Produit,
    RevalorisationStock,
)
from apps.stock.services import (
    creer_revalorisation, valider_inventaire_session, valider_revalorisation,
)
from authentication.models import Company

_seq = itertools.count(1)


class VerrouValidationTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk48-co-{n}', nom=f'ASTK48 Co {n}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5 kWh', sku=f'ASTK48-{n}',
            prix_achat=Decimal('100'), prix_vente=Decimal('150'),
            quantite_stock=100)

    def test_double_validation_session_un_seul_ajustement(self):
        session = InventaireSession.objects.create(
            company=self.company, reference=f'INV-ASTK48-{next(_seq)}')
        LigneInventaire.objects.create(
            session=session, produit=self.produit,
            quantite_theorique=100, quantite_comptee=90)
        a = InventaireSession.objects.get(pk=session.pk)
        b = InventaireSession.objects.get(pk=session.pk)  # instance périmée

        valider_inventaire_session(a, None)
        with self.assertRaisesMessage(ValueError, 'déjà validée'):
            valider_inventaire_session(b, None)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 90)
        self.assertEqual(MouvementStock.objects.filter(
            produit=self.produit, reference=session.reference,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
        ).count(), 1)
        session.refresh_from_db()
        self.assertEqual(session.statut, InventaireSession.Statut.VALIDE)

    def test_double_validation_revalorisation(self):
        reval = creer_revalorisation(
            company=self.company, produit=self.produit,
            nouveau_cout='120', motif='Correction coût', user=None)
        a = RevalorisationStock.objects.get(pk=reval.pk)
        b = RevalorisationStock.objects.get(pk=reval.pk)  # instance périmée

        valider_revalorisation(a)
        premiere_date = RevalorisationStock.objects.get(
            pk=reval.pk).date_validation
        with self.assertRaisesMessage(ValueError, 'déjà validée'):
            valider_revalorisation(b)

        relu = RevalorisationStock.objects.get(pk=reval.pk)
        self.assertEqual(relu.statut, RevalorisationStock.Statut.VALIDEE)
        # La 2e validation n'a rien réécrit.
        self.assertEqual(relu.date_validation, premiere_date)
        self.assertEqual(RevalorisationStock.objects.filter(
            produit=self.produit,
            statut=RevalorisationStock.Statut.VALIDEE).count(), 1)
