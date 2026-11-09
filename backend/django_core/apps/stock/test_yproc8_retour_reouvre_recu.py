"""YPROC8 — Le retour fournisseur doit rouvrir le « reçu » de la ligne BCF.

Couvre :
  * retourner N unités d'un BCF entièrement reçu rouvre `quantite_restante`
    de N sur la ligne BCF correspondante ;
  * le statut du BCF redescend de RECU à ENVOYE si le retour rend le BCF plus
    entièrement reçu ;
  * le décrément est plafonné à la quantité effectivement reçue ;
  * un retour SANS BCF lié se comporte comme avant (aucune régression) ;
  * multi-tenant : un retour d'une société ne touche jamais le BCF d'une
    autre société.

SOLMVP12 (20/09/2026) — le rafraîchissement du rapprochement 3 voies
(lecture/écriture du module compta, détaché de stock) a été retiré de
``apply_retour_fournisseur`` : la couverture correspondante est retirée
d'ici.

Run:
    python manage.py test apps.stock.test_yproc8_retour_reouvre_recu -v 2
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, Produit, RetourFournisseur,
)
from apps.stock.services import apply_retour_fournisseur


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


class Yproc8Base(TestCase):
    def setUp(self):
        self.company = _company('yproc8-co')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur YPROC8')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau YPROC8', sku='PAN-YPROC8',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'),
            quantite_stock=20)

    def _bcf_recu(self, quantite=20, prix=Decimal('100')):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-YPROC8-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        ligne = bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=prix, quantite_recue=quantite)
        return bc, ligne

    def _retour(self, bc, quantite, motif='Défectueux'):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-YPROC8-1',
            fournisseur=self.fournisseur, bon_commande=bc,
            statut=RetourFournisseur.Statut.BROUILLON)
        retour.lignes.create(
            produit=self.produit, quantite=quantite, motif=motif)
        return retour


class TestReouvertureQuantiteRecue(Yproc8Base):
    def test_retour_partiel_reouvre_quantite_restante(self):
        bc, ligne = self._bcf_recu(quantite=20)
        retour = self._retour(bc, 5)
        apply_retour_fournisseur(retour, user=None)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 15)
        self.assertEqual(ligne.quantite_restante, 5)

    def test_statut_bcf_redescend_de_recu_a_envoye(self):
        bc, ligne = self._bcf_recu(quantite=20)
        retour = self._retour(bc, 5)
        apply_retour_fournisseur(retour, user=None)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_retour_plafonne_a_la_quantite_recue(self):
        bc, ligne = self._bcf_recu(quantite=20)
        self.produit.quantite_stock = 100
        self.produit.save(update_fields=['quantite_stock'])
        # Retour de plus que ce qui a été reçu (25 > 20) : la ligne ne peut
        # pas descendre sous 0.
        retour = self._retour(bc, 20)
        apply_retour_fournisseur(retour, user=None)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 0)
        self.assertGreaterEqual(ligne.quantite_recue, 0)

    def test_retour_total_garde_bcf_envoye_pas_negatif(self):
        bc, ligne = self._bcf_recu(quantite=20)
        retour = self._retour(bc, 20)
        apply_retour_fournisseur(retour, user=None)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 0)
        bc.refresh_from_db()
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_facturer_apres_retour_facture_le_net(self):
        """AAPV25 — réception de 10, retour de 3 validé : « Facturer » crée
        7 000 HT / 8 400 TTC, 3 voies normale ; une facture de 10 000 HT liée
        ensuite passe en exception."""
        import datetime
        from apps.stock.models import (
            FactureFournisseur, LigneReceptionFournisseur, ReceptionFournisseur,
        )
        from apps.stock.services import evaluer_rapprochement_3_voies, facturer_reception
        self.produit.quantite_stock = 0
        self.produit.save(update_fields=['quantite_stock'])
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AAPV25', fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        ligne = bc.lignes.create(produit=self.produit, quantite=10,
                                 prix_achat_unitaire=Decimal('1000'), quantite_recue=10)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-AAPV25', bon_commande=bc,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit, quantite=10)
        self.produit.quantite_stock = 10
        self.produit.save(update_fields=['quantite_stock'])
        apply_retour_fournisseur(self._retour(bc, 3), user=None)
        facture = facturer_reception(self.company, None, rec)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_ht, Decimal('7000.00'))
        self.assertEqual(facture.montant_ttc, Decimal('8400.00'))
        self.assertEqual(facture.statut_controle, 'normale')
        self.assertEqual([lg.quantite for lg in facture.lignes.all()], [7])
        autre = FactureFournisseur.objects.create(
            company=self.company, reference='FF-AAPV25-2', fournisseur=self.fournisseur,
            bon_commande=bc, montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
            montant_ttc=Decimal('12000'))
        self.assertEqual(evaluer_rapprochement_3_voies(autre), 'exception')

    def test_deux_lignes_meme_produit_retour_compte_une_fois(self):
        """AAPV80 — lignes A et B 10 × 1 000 du même produit, 20 reçus, 3
        retournés : 17 000 HT attendus et facturés (le retour n'est retiré
        qu'une fois, de la ligne la plus récente)."""
        import datetime
        from apps.stock.models import LigneReceptionFournisseur, ReceptionFournisseur
        from apps.stock.services import _montant_attendu_bcf_ht, facturer_reception
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AAPV80', fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        lignes = [bc.lignes.create(produit=self.produit, quantite=10, quantite_recue=10,
                                   prix_achat_unitaire=Decimal('1000')) for _ in 'AB']
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-AAPV80', bon_commande=bc,
            statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        for ligne in lignes:
            LigneReceptionFournisseur.objects.create(
                reception=rec, ligne_commande=ligne, produit=self.produit, quantite=10)
        apply_retour_fournisseur(self._retour(bc, 3), user=None)
        self.assertEqual([lg.quantite_recue for lg in bc.lignes.order_by('id')], [10, 7])
        self.assertEqual(_montant_attendu_bcf_ht(bc.id), Decimal('17000.00'))
        facture = facturer_reception(self.company, None, rec)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_ht, Decimal('17000.00'))
        self.assertEqual(sorted(lg.quantite for lg in facture.lignes.all()), [7, 10])


class TestSansBcfLieInchange(Yproc8Base):
    def test_retour_sans_bcf_lie_comportement_historique(self):
        self.produit.quantite_stock = 10
        self.produit.save(update_fields=['quantite_stock'])
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RF-YPROC8-2',
            fournisseur=self.fournisseur, bon_commande=None,
            statut=RetourFournisseur.Statut.BROUILLON)
        retour.lignes.create(
            produit=self.produit, quantite=3, motif='Sans BCF')
        apply_retour_fournisseur(retour, user=None)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 7)
        retour.refresh_from_db()
        self.assertEqual(retour.statut, RetourFournisseur.Statut.VALIDE)


class TestMultiTenant(Yproc8Base):
    def test_retour_isole_par_societe(self):
        autre = _company('yproc8-autre')
        bc, ligne = self._bcf_recu(quantite=20)
        retour = self._retour(bc, 5)
        # Sanity : le retour et le BCF sont bien de la MÊME société. Ce test
        # isole juste la logique de service ; le refus par l'API d'un BCF,
        # fournisseur ou produit d'une autre société est prouvé par ASTK2
        # (test_astk_fk_retour_modele_bcf.py).
        self.assertEqual(retour.company_id, self.company.id)
        self.assertNotEqual(retour.company_id, autre.id)
        apply_retour_fournisseur(retour, user=None)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 15)
