"""ASTK58 — annuler une réception confirmée NON CONFORME lève la quarantaine
qu'elle avait posée (NTWMS34).

Constat C-ASTK-011 (volet WMS-13, plausible non sondé) : le routage qualité
post-confirmation crée un ``BlocageQualite`` EN_QUARANTAINE rattaché à la
réception ; ``annuler_reception_confirmee`` contre-passait le stock sans
toucher au blocage, laissant une quarantaine fantôme sur une marchandise
sortie.

Run :
    python manage.py test apps.stock.test_astk_annulation_quarantaine -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BlocageQualite, BonCommandeFournisseur, Categorie, ControleReception,
    Fournisseur, PlanEchantillonnage, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
    quantite_disponible_hors_quarantaine,
)
from apps.stock.services_qualite_reception import (
    enregistrer_controle_reception,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class AnnulationQuarantaineTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'astk58-co-{n}', nom=f'ASTK58 Co {n}')
        self.admin = User.objects.create_user(
            username=f'astk58-{n}', password='x', role_legacy='admin',
            company=self.company)
        categorie = Categorie.objects.create(
            company=self.company, nom=f'Batteries ASTK58 {n}')
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=categorie,
            taux_echantillon_pct=20)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK58')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie ASTK58', sku=f'ASTK58-{n}',
            categorie=categorie, prix_achat=Decimal('3000'),
            prix_vente=Decimal('4000'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK58-{n}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_cmd = bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('3000'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK58-{n}',
            bon_commande=bc)
        self.reception.lignes.create(
            ligne_commande=ligne_cmd, produit=self.produit, quantite=10)
        enregistrer_controle_reception(
            reception=self.reception, user=self.admin,
            resultat=ControleReception.Resultat.NON_CONFORME,
            unites_controlees=2, observation='Cellules gonflées')
        confirm_reception_fournisseur(self.reception, self.admin)
        # Pré-condition : la quarantaine est posée.
        self.assertTrue(BlocageQualite.objects.filter(
            reception=self.reception,
            statut=BlocageQualite.Statut.EN_QUARANTAINE).exists())

    def test_annulation_leve_la_quarantaine(self):
        annuler_reception_confirmee(self.reception, self.admin)

        self.assertFalse(BlocageQualite.objects.filter(
            reception=self.reception,
            statut=BlocageQualite.Statut.EN_QUARANTAINE).exists())
        blocage = BlocageQualite.objects.get(reception=self.reception)
        self.assertEqual(blocage.statut, BlocageQualite.Statut.LEVEE)
        self.assertIn('réception annulée', blocage.motif.lower())

    def test_stock_et_disponible_jamais_negatif(self):
        annuler_reception_confirmee(self.reception, self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertEqual(
            quantite_disponible_hors_quarantaine(self.company, self.produit),
            0)


class AnnulationPeseeCrossDockTests(TestCase):
    """ERR-ASTK58-ANNULATION-RECEPTION-JUMEAUX-PESEE-CROSSDOCK — annuler une
    réception contre-passe AUSSI l'ajustement de pesée ``PESEE-<réf>`` et
    libère ses ``AffectationCrossDock`` (et le contenu du colis non scellé
    qu'elles alimentaient) : stock final et affectations nuls."""

    def setUp(self):
        from apps.stock.models import (
            EmplacementStock, LigneBonCommandeFournisseur,
            LigneReceptionFournisseur,
        )
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'errastk58-co-{n}', nom=f'ERR ASTK58 Co {n}')
        self.admin = User.objects.create_user(
            username=f'errastk58-{n}', password='x', role_legacy='admin',
            company=self.company)
        EmplacementStock.objects.create(
            company=self.company, nom='Dépôt ERR-ASTK58', is_principal=True)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ERR-ASTK58')
        self.produit = Produit.objects.create(
            company=self.company, nom='Câble ERR-ASTK58',
            sku=f'ERRASTK58-{n}', prix_achat=Decimal('12'),
            prix_vente=Decimal('18'), quantite_stock=0)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ERRASTK58-{n}',
            fournisseur=fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne_cmd = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('12'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ERRASTK58-{n}',
            bon_commande=bc)
        self.ligne = LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=ligne_cmd,
            produit=self.produit, quantite=10)

    def test_pesee_et_cross_dock_contre_passes(self):
        from apps.stock.models import (
            AffectationCrossDock, MouvementStock, UniteLogistiqueLigne,
        )
        from apps.stock.services import (
            affecter_reception_cross_dock, creer_vague_depuis_besoins,
        )
        from apps.stock.services_catch_weight import (
            enregistrer_pesee_ligne_reception, rapprocher_pesee_reception,
            reference_rapprochement,
        )
        enregistrer_pesee_ligne_reception(
            ligne_reception=self.ligne, user=self.admin,
            unite_variable=True, quantite_reelle='11.000', unite_mesure='m')
        confirm_reception_fournisseur(self.reception, self.admin)
        rapprocher_pesee_reception(reception=self.reception, user=self.admin)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 11)
        creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 4}])
        affecter_reception_cross_dock(
            reception=self.reception, user=self.admin)
        self.assertEqual(AffectationCrossDock.objects.filter(
            reception=self.reception).count(), 1)
        self.assertEqual(sum(UniteLogistiqueLigne.objects.filter(
            company=self.company, produit=self.produit,
        ).values_list('quantite', flat=True)), 4)

        annuler_reception_confirmee(
            ReceptionFournisseur.objects.get(pk=self.reception.pk),
            self.admin)

        self.produit.refresh_from_db()
        # Avant le correctif : 1 (la sortie de 10 laissait l'ajustement +1).
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertTrue(MouvementStock.objects.filter(
            company=self.company,
            reference=f'ANNUL-{reference_rapprochement(self.reception)}',
        ).exists())
        self.assertFalse(AffectationCrossDock.objects.filter(
            reception=self.reception).exists())
        self.assertFalse(UniteLogistiqueLigne.objects.filter(
            company=self.company, produit=self.produit).exists())
