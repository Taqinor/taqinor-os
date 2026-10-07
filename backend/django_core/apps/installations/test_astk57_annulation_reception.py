"""ASTK57 — installations abonnée à ``reception_fournisseur_annulee``.

Rejoue RESA-7 : une réception confirmée d'un BCF « besoin chantier »
(``chantier_origine``) avec la série S1 et une provision GR/IR ouverte de
500,00 est annulée (contre-passation réelle ``annuler_reception_confirmee``)
puis le signal est émis. Avant ASTK57 : provision ouverte = 1 (500.00), série
« en_stock », réservation YPROC10 intacte. Après : provision extournée, série
« retourné », réservation ≤ reçu net ; un second envoi ne change rien.

Le signal est émis ici par le test, avec le payload catalogué (reception,
company, user, lignes) : son émetteur de production est ASTK56 (stock). Aucun
mock — ``core.events`` réel, services stock et installations réels.

Run :
    python manage.py test apps.installations.test_astk57_annulation_reception
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client, Lead
from apps.installations.models import SerieEntrepot, StockReservation
from apps.installations.models_gr_ir import ReceptionNonFacturee
from apps.installations.services import create_installation_from_devis
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
)
from apps.ventes.models import Devis, LigneDevis
from core.events import reception_fournisseur_annulee

User = get_user_model()


class AnnulationReceptionAbonnesTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-astk57', defaults={'nom': 'Co ASTK57'})
        self.user = User.objects.create_user(
            username='resp-astk57', password='x', company=self.company,
            role_legacy='responsable')
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble ASTK57', sku='SKU-ASTK57-C',
            prix_vente=Decimal('10'), quantite_stock=100)
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ASTK57', sku='SKU-ASTK57-P',
            prix_vente=Decimal('100'), quantite_stock=0)
        client = Client.objects.create(
            company=self.company, nom='Site', prenom='Client',
            email='astk57@example.invalid')
        lead = Lead.objects.create(
            company=self.company, nom='Site', prenom='Client',
            stage='SIGNED', type_installation='residentiel')
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ASTK57-1', client=client,
            lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
            mode_installation='residentiel')
        # Le panneau n'est PAS dans la nomenclature : sa réservation naît
        # uniquement de la réception YPROC10.
        LigneDevis.objects.create(
            devis=devis, produit=self.cable, designation='Câble',
            quantite=Decimal('5'), prix_unitaire=Decimal('10'))
        self.inst, _ = create_installation_from_devis(
            devis, self.user, self.company)
        fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fourn ASTK57')
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, fournisseur=fournisseur,
            reference='BCF-ASTK57', chantier_origine=self.inst,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne_cmd = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.panneau, quantite=10,
            prix_achat_unitaire=Decimal('50'))
        self.rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK57',
            bon_commande=self.bc)
        LigneReceptionFournisseur.objects.create(
            reception=self.rec, ligne_commande=self.ligne_cmd,
            produit=self.panneau, quantite=10, numeros_serie=['S1'])
        confirm_reception_fournisseur(self.rec, self.user)
        self.rec.refresh_from_db()

    def _annuler(self):
        annuler_reception_confirmee(self.rec, self.user)
        self.rec.refresh_from_db()
        self._emettre()

    def _emettre(self):
        lignes = [
            {'ligne': lg, 'produit': lg.produit, 'quantite_annulee': 10}
            for lg in self.rec.lignes.all()]
        reception_fournisseur_annulee.send(
            sender=ReceptionFournisseur, reception=self.rec,
            company=self.company, user=self.user, lignes=lignes)

    def _etat(self):
        resa = StockReservation.objects.filter(
            installation=self.inst, produit=self.panneau).first()
        return (
            list(ReceptionNonFacturee.objects.filter(
                reception=self.rec, lettre=False).values_list(
                'montant_provision', flat=True)),
            SerieEntrepot.objects.get(
                company=self.company, produit=self.panneau,
                numero_serie='S1').statut,
            (resa.quantite, resa.active) if resa else None,
        )

    def test_preconditions_reception_confirmee(self):
        provisions, statut, resa = self._etat()
        self.assertEqual(provisions, [Decimal('500.00')])
        self.assertEqual(statut, SerieEntrepot.Statut.EN_STOCK)
        self.assertEqual(resa, (10, True))

    def test_provision_extournee(self):
        self._annuler()
        self.assertFalse(ReceptionNonFacturee.objects.filter(
            reception=self.rec, lettre=False).exists())

    def test_provision_lettree_jamais_touchee(self):
        ReceptionNonFacturee.objects.filter(reception=self.rec).update(
            lettre=True)
        self._annuler()
        self.assertEqual(ReceptionNonFacturee.objects.filter(
            reception=self.rec, lettre=True).count(), 1)

    def test_serie_retournee(self):
        self._annuler()
        statut = SerieEntrepot.objects.get(
            company=self.company, produit=self.panneau,
            numero_serie='S1').statut
        self.assertNotEqual(statut, SerieEntrepot.Statut.EN_STOCK)
        self.assertEqual(statut, SerieEntrepot.Statut.RETOURNE)

    def test_reservation_replafonnee_au_recu_net(self):
        self._annuler()
        self.ligne_cmd.refresh_from_db()
        resa = StockReservation.objects.get(
            installation=self.inst, produit=self.panneau)
        self.assertLessEqual(resa.quantite, self.ligne_cmd.quantite_recue)
        self.assertEqual(resa.quantite, 0)
        self.assertFalse(resa.active)

    def test_reservation_nomenclature_jamais_reduite(self):
        # Le câble (besoin propre du chantier, N14) n'est pas concerné.
        self._annuler()
        resa = StockReservation.objects.get(
            installation=self.inst, produit=self.cable)
        self.assertEqual((resa.quantite, resa.active), (5, True))

    def test_second_envoi_idempotent(self):
        self._annuler()
        avant = self._etat()
        self._emettre()
        self.assertEqual(self._etat(), avant)

    def test_autre_societe_intacte(self):
        autre, _ = Company.objects.get_or_create(
            slug='co-astk57-b', defaults={'nom': 'Co ASTK57 B'})
        annuler_reception_confirmee(self.rec, self.user)
        self.rec.refresh_from_db()
        reception_fournisseur_annulee.send(
            sender=ReceptionFournisseur, reception=self.rec, company=autre,
            user=self.user, lignes=[])
        provisions, statut, _resa = self._etat()
        self.assertEqual(provisions, [Decimal('500.00')])
        self.assertEqual(statut, SerieEntrepot.Statut.EN_STOCK)
