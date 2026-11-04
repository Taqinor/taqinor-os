"""ASTK98 (C-ASTK-028) — la livraison directe chantier (XPUR23) solde la
réservation du chantier : le matériel reçu et sorti pour le chantier n'est
plus sorti une seconde fois à « Installé ».

Le test part d'un stock libre de 5 (la sonde RESA-1c était masquée par le
plancher ERR80 avec un stock 0). Chantier réservant 10, BCF de livraison
directe de 10 : ENTRÉE 10 + SORTIE 10 à la réception, réservation soldée,
puis `consume_reservations` (« Installé ») ne sort plus rien → stock 5.

Source réelle : `confirm_reception_fournisseur` via l'action `recevoir`,
service chantiers `solder_reservations_vente` (ASTK120),
`consume_reservations` — aucun mock.

Run :
    python manage.py test apps.stock.test_astk_livraison_directe_reservation -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation, StockReservation
from apps.installations.services import consume_reservations
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, MouvementStock, Produit,
)
from authentication.models import Company

User = get_user_model()


class LivraisonDirecteReservationTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ASTK98', slug='astk98-co')
        self.user = User.objects.create_user(
            username='astk98-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        client = Client.objects.create(
            company=self.company, nom='Client ASTK98', prenom='Test')
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ASTK98-1', client=client)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau ASTK98', sku='PAN-ASTK98',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1000'),
            quantite_stock=5)
        self.resa = StockReservation.objects.create(
            company=self.company, installation=self.chantier,
            produit=self.produit, quantite=10)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK98')
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK98-1',
            fournisseur=fournisseur, chantier_livraison=self.chantier,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne = self.bc.lignes.create(
            produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))

    def _recevoir(self):
        return self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{self.bc.id}/'
            'recevoir/',
            {'receptions': [{'ligne': self.ligne.id, 'quantite': 10}]},
            format='json')

    def test_une_seule_sortie(self):
        rep = self._recevoir()
        self.assertEqual(rep.status_code, 200, rep.data)
        # Persistance : réservation relue soldée dès la réception.
        self.resa.refresh_from_db()
        self.assertTrue(self.resa.consomme)
        self.assertEqual(self.resa.quantite, 0)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)

        # « Installé » : plus aucune sortie pour ce produit.
        consume_reservations(self.chantier, self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 5)
        sorties = MouvementStock.objects.filter(
            produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(sorties.count(), 1)
        self.assertEqual(sorties.get().quantite, 10)

    def test_reliquat_seul_sorti_a_installe(self):
        # Réception partielle de 4 : la réservation garde 6, « Installé »
        # ne sort que le reliquat.
        rep = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{self.bc.id}/'
            'recevoir/',
            {'receptions': [{'ligne': self.ligne.id, 'quantite': 4}]},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.data)
        self.resa.refresh_from_db()
        self.assertFalse(self.resa.consomme)
        self.assertEqual(self.resa.quantite, 6)

    # ── ASTK259 (C-ASTK-VER4-041) — chantier d'une VENTE ────────────────
    def _vente(self):
        """Devis accepté de 10 panneaux (stock 30) → chantier (réservation
        10) + BCF de livraison directe de 20 vers ce chantier."""
        from apps.crm import stages
        from apps.crm.models import Lead
        from apps.installations.services import create_installation_from_devis
        from apps.ventes.models import Devis, LigneDevis
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK259', sku='PAN-ASTK259',
            prix_vente=Decimal('100'), prix_achat=Decimal('60'),
            quantite_stock=30, tva=Decimal('20.00'))
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='ASTK259',
            email='astk259@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='ASTK259',
            stage=stages.SIGNED, type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASTK259', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau',
            quantite=Decimal('10'), prix_unitaire=Decimal('100'),
            taux_tva=Decimal('20.00'))
        chantier, _ = create_installation_from_devis(
            devis, self.user, self.company)
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-ASTK259',
            fournisseur=Fournisseur.objects.create(
                company=self.company, nom='Fournisseur ASTK259'),
            chantier_livraison=chantier,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = bcf.lignes.create(
            produit=self.panneau, quantite=20,
            prix_achat_unitaire=Decimal('60'))
        return devis, chantier, bcf, ligne

    def _direct(self, bcf, ligne, quantite):
        rep = self.api.post(
            f'/api/django/stock/bons-commande-fournisseur/{bcf.id}/recevoir/',
            {'receptions': [{'ligne': ligne.id, 'quantite': quantite}]},
            format='json')
        self.assertEqual(rep.status_code, 200, rep.data)

    def _somme(self, type_mouvement, **filtres):
        return sum(MouvementStock.objects.filter(
            produit=self.panneau, type_mouvement=type_mouvement,
            **filtres).values_list('quantite', flat=True))

    def test_vente_sortie_puis_livraison_directe(self):
        """ROUGE sur c38868a62 : facture émise puis direct 10 ⇒ 20 sorties,
        stock 20. Attendu : ENTRÉE 10, aucune SORTIE de plus, stock 30."""
        from apps.ventes.domain.facturation_ops import facturer_devis_complet
        devis, chantier, bcf, ligne = self._vente()
        facturer_devis_complet(
            devis=devis, user=self.user, company=self.company, paiements=[])
        self._direct(bcf, ligne, 10)
        sortie = MouvementStock.TypeMouvement.SORTIE
        self.assertEqual(self._somme(MouvementStock.TypeMouvement.ENTREE), 10)
        self.assertEqual(self._somme(sortie), 10)
        self.assertEqual(self._somme(sortie, reference=chantier.reference), 0)
        # Persistance : relu en base.
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 30)
        self.assertTrue(StockReservation.objects.get(
            installation=chantier, produit=self.panneau).consomme)

    def test_sortie_partielle_de_la_vente_puis_direct_15(self):
        """Cas « acompte émis » : l'émission sort le panier par
        `reserver_stock_devis_facture` (même appel qu'`emettre_facture`) ;
        direct 15 ⇒ SORTIE 5 sous la référence du chantier, stock 30."""
        from apps.ventes.domain.facturation_ops import (
            reserver_stock_devis_facture,
        )
        devis, chantier, bcf, ligne = self._vente()
        reserver_stock_devis_facture(
            devis=devis, user=self.user, company=self.company)
        self._direct(bcf, ligne, 15)
        sortie = MouvementStock.TypeMouvement.SORTIE
        self.assertEqual(self._somme(sortie), 15)
        self.assertEqual(self._somme(sortie, reference=chantier.reference), 5)
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 30)

    def test_sans_facture_direct_4_puis_6(self):
        devis, chantier, bcf, ligne = self._vente()
        self._direct(bcf, ligne, 4)
        self._direct(bcf, ligne, 6)
        sortie = MouvementStock.TypeMouvement.SORTIE
        self.assertEqual(
            sorted(MouvementStock.objects.filter(
                produit=self.panneau, type_mouvement=sortie,
                reference=chantier.reference).values_list(
                    'quantite', flat=True)), [4, 6])
        self.panneau.refresh_from_db()
        self.assertEqual(self.panneau.quantite_stock, 30)
        resa = StockReservation.objects.get(
            installation=chantier, produit=self.panneau)
        self.assertTrue(resa.consomme)
