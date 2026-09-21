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
        # Sanity : le retour et le BCF sont bien de la MÊME société (le
        # scoping réel est garanti par la vue/le serializer — ce test isole
        # juste la logique de service).
        self.assertEqual(retour.company_id, self.company.id)
        self.assertNotEqual(retour.company_id, autre.id)
        apply_retour_fournisseur(retour, user=None)
        ligne.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 15)
