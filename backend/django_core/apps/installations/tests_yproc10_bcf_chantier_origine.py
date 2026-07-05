"""YPROC10 — BCF « besoin chantier » : lien structurel au chantier d'origine
+ réservation automatique à la réception.

Couvre :
  * `draft_bcf_for_shortfall` pose `chantier_origine` sur le BCF généré ;
  * confirmer la réception d'un BCF portant `chantier_origine` crée/complète
    la `StockReservation` du chantier pour les quantités reçues, plafonnée au
    manque recalculé (jamais de sur-réservation) ;
  * re-confirmer (ou une seconde réception partielle) n'ajoute jamais plus
    que le manque restant (idempotence) ;
  * un BCF SANS chantier_origine se comporte exactement comme avant (aucune
    réservation créée par ce chemin) ;
  * la réservation est visible dans le disponible N14.

Run:
    python manage.py test \
        apps.installations.tests_yproc10_bcf_chantier_origine -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis, LigneDevis
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    draft_bcf_for_shortfall, confirm_reception_fournisseur, available_quantity,
)
from apps.installations.models import StockReservation
from apps.installations.services import (
    create_installation_from_devis, reserver_stock_recu_pour_chantier,
)

User = get_user_model()

_seq = itertools.count(1)


def make_company(slug='yproc10-co', nom='YPROC10 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_produit(company, nom, stock, seuil=0):
    n = next(_seq)
    return Produit.objects.create(
        company=company, nom=nom, sku=f'SKU-YPROC10-{company.id}-{n}',
        prix_vente=Decimal('100'), prix_achat=Decimal('60'),
        quantite_stock=stock, seuil_alerte=seuil)


def make_accepted_devis_with_lines(company, lines):
    n = next(_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'yproc10-{company.id}-{n}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Site', prenom='Client', stage='SIGNED',
        type_installation='residentiel')
    devis = Devis.objects.create(
        company=company, reference=f'DEV-YPROC10-{company.id}-{n}',
        client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'), mode_installation='residentiel')
    for produit, qte in lines:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=produit.nom,
            quantite=Decimal(str(qte)), prix_unitaire=Decimal('100'))
    return devis


class Yproc10Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='yproc10_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YPROC10')
        # Panneau requis 20, dispo seulement 5 -> manque 15.
        self.panneau = make_produit(self.company, 'Panneau YPROC10', stock=5)

    def _chantier_avec_manque(self, requis=20):
        devis = make_accepted_devis_with_lines(
            self.company, [(self.panneau, requis)])
        inst, _created = create_installation_from_devis(
            devis, self.user, self.company)
        return inst

    def _confirmer_reception(self, bc, qte):
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-YPROC10-{bc.id}',
            bon_commande=bc, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        ligne_cmd = bc.lignes.get(produit=self.panneau)
        rec.lignes.create(
            ligne_commande=ligne_cmd, produit=self.panneau, quantite=qte)
        confirm_reception_fournisseur(rec, self.user)
        return rec


class TestLienStructurel(Yproc10Base):
    def test_draft_bcf_pose_chantier_origine(self):
        inst = self._chantier_avec_manque()
        bon, _count = draft_bcf_for_shortfall(
            inst, self.fournisseur, self.user, self.company)
        self.assertEqual(bon.chantier_origine_id, inst.id)


class TestReservationAutomatiqueALaReception(Yproc10Base):
    def test_reception_reserve_jusquau_manque(self):
        inst = self._chantier_avec_manque(requis=20)
        bon, _count = draft_bcf_for_shortfall(
            inst, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])

        self._confirmer_reception(bon, 10)

        resa = StockReservation.objects.get(
            installation=inst, produit=self.panneau)
        self.assertEqual(resa.quantite, 10)
        self.assertTrue(resa.active)
        self.assertFalse(resa.consomme)

    def test_reservation_plafonnee_au_manque_jamais_de_surreservation(self):
        inst = self._chantier_avec_manque(requis=20)  # manque = 15
        bon, _count = draft_bcf_for_shortfall(
            inst, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])

        # Réception de 20 (plus que le manque de 15) : plafonnée à 15.
        self._confirmer_reception(bon, 20)

        resa = StockReservation.objects.get(
            installation=inst, produit=self.panneau)
        self.assertLessEqual(resa.quantite, 15)

    def test_reconfirmation_idempotente_ne_double_pas(self):
        inst = self._chantier_avec_manque(requis=20)
        bon, _count = draft_bcf_for_shortfall(
            inst, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])

        rec = self._confirmer_reception(bon, 10)
        # Appeler à nouveau le service directement (simule un ré-abonné/
        # rejeu du signal) : ne double jamais la réservation.
        reserver_stock_recu_pour_chantier(reception=rec)

        resa = StockReservation.objects.get(
            installation=inst, produit=self.panneau)
        self.assertEqual(resa.quantite, 10)

    def test_reservation_visible_dans_le_disponible(self):
        inst = self._chantier_avec_manque(requis=20)
        bon, _count = draft_bcf_for_shortfall(
            inst, self.fournisseur, self.user, self.company)
        bon.statut = BonCommandeFournisseur.Statut.ENVOYE
        bon.save(update_fields=['statut'])

        # N14 réserve DÉJÀ tout le besoin du chantier (20) dès sa création
        # (`seed_reservations`, indépendant de YPROC10) : le disponible reflète
        # donc le manque réel du chantier avant toute réception (5 stock − 20
        # réservé = -15).
        avant = available_quantity(self.panneau)
        self.assertEqual(avant, -15)
        self._confirmer_reception(bon, 10)
        self.panneau.refresh_from_db()
        apres = available_quantity(self.panneau)
        # YPROC10 replafonne la réservation du chantier à la quantité REÇUE
        # cumulée (10, jamais plus que le manque figé au brouillon = 15) —
        # elle n'est donc plus jamais gonflée au besoin total (20). Stock
        # total +10 (15) − réservé 10 = 5 : le disponible est bien VISIBLE
        # (il bouge avec la réception) et jamais sur-réservé.
        self.assertEqual(apres, 5)
        self.assertGreater(apres, avant)


class TestSansChantierOrigineInchange(Yproc10Base):
    def test_bcf_sans_chantier_origine_aucune_reservation(self):
        bon = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC10-SANS',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bon.lignes.create(
            produit=self.panneau, quantite=10,
            prix_achat_unitaire=Decimal('60'))
        self._confirmer_reception(bon, 10)
        self.assertEqual(
            StockReservation.objects.filter(produit=self.panneau).count(), 0)
