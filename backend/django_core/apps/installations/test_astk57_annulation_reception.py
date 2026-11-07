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

    def test_serie_d_une_autre_reception_jamais_retournee(self):
        """AAPV22 — S1 mise en stock par REC-ASTK57 puis « reçue » par une
        seconde réception : annuler la seconde laisse S1 en stock (REC-1)."""
        from apps.installations.selectors import series_en_stock
        from apps.installations.services import (
            retourner_series_entrepot_reception,
        )
        rec2 = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK57-2',
            bon_commande=self.bc)
        LigneReceptionFournisseur.objects.create(
            reception=rec2, ligne_commande=self.ligne_cmd,
            produit=self.panneau, quantite=1, numeros_serie=['S1'])
        retourner_series_entrepot_reception(
            reception=rec2, company=self.company)
        serie = SerieEntrepot.objects.get(
            company=self.company, produit=self.panneau, numero_serie='S1')
        self.assertEqual(serie.statut, SerieEntrepot.Statut.EN_STOCK)
        self.assertEqual(serie.reference_reception, 'REC-ASTK57')
        self.assertEqual(
            series_en_stock(self.company, self.panneau.id, ['S1', 'SN-9']),
            {'S1': 'REC-ASTK57'})

    def test_retour_valide_reduit_provision_et_reservation(self):
        """AAPV9 — retour de 4 sur 10 reçus à 50 : provision 300 ouverte,
        réservation 6 ; renvoyer le signal ne change rien ; une facture de
        300 HT liée au BCF lettre la provision."""
        from apps.installations.services import lettrer_gr_ir_facture
        from apps.stock.models import FactureFournisseur, RetourFournisseur
        from apps.stock.services import apply_retour_fournisseur
        from core.events import retour_fournisseur_valide
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-AAPV9', fournisseur=self.bc.fournisseur,
            bon_commande=self.bc, statut=RetourFournisseur.Statut.BROUILLON)
        retour.lignes.create(produit=self.panneau, quantite=4)
        with self.captureOnCommitCallbacks(execute=True):
            apply_retour_fournisseur(retour, self.user)

        def etat():
            prov = ReceptionNonFacturee.objects.get(bon_commande=self.bc)
            resa = StockReservation.objects.get(
                installation=self.inst, produit=self.panneau)
            return prov.montant_provision, prov.lettre, resa.quantite
        self.assertEqual(etat(), (Decimal('300.00'), False, 6))
        retour_fournisseur_valide.send(
            sender=RetourFournisseur, retour=retour, company=self.company,
            user=self.user, lignes=[])
        self.assertEqual(etat(), (Decimal('300.00'), False, 6))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AAPV9', fournisseur=self.bc.fournisseur,
            bon_commande=self.bc, montant_ht=Decimal('300'),
            montant_tva=Decimal('60'), montant_ttc=Decimal('360'))
        lettrer_gr_ir_facture(facture=facture, company=self.company, user=self.user)
        self.assertEqual(etat()[1], True)

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
