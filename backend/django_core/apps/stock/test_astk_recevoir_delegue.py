"""ASTK62 (C-ASTK-013) — l'action BCF `recevoir` délègue à la réception.

Constat BCF-7 : `POST …/bons-commande-fournisseur/<id>/recevoir/`
réimplémentait la réception en ligne (views/bon_commande_fournisseur.py) :
aucun document de réception (donc ni annulable ni facturable), aucune
provision GR/IR (0 au lieu de 1), aucun contrôle qualité, `int()` muet sur la
quantité. Désormais elle crée une ReceptionFournisseur puis appelle
`confirm_reception_fournisseur` : les deux portes sont identiques.

Run :
    python manage.py test apps.stock.test_astk_recevoir_delegue
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.installations.models_gr_ir import ReceptionNonFacturee
from apps.stock.models import (
    BonCommandeFournisseur, Categorie, Fournisseur, MouvementStock,
    PlanEchantillonnage, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    annuler_reception_confirmee, confirm_reception_fournisseur,
)

User = get_user_model()

URL = '/api/django/stock/bons-commande-fournisseur/'


class RecevoirDelegueTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='ASTK62 Co', slug='astk62-co')
        self.user = User.objects.create_user(
            username='astk62-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK62')
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs ASTK62')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK62', sku='OND-ASTK62',
            categorie=self.categorie, prix_vente=Decimal('2000'),
            prix_achat=Decimal('1200'), quantite_stock=0)
        self._seq = 0

    def _bcf(self, quantite=15):
        self._seq += 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK62-{self._seq}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('100'))
        return bc, ligne

    def _recevoir(self, bc, ligne, quantite):
        return self.api.post(f'{URL}{bc.pk}/recevoir/', {
            'receptions': [{'ligne': ligne.pk, 'quantite': quantite}]},
            format='json')

    def test_recevoir_cree_reception(self):
        bc, ligne = self._bcf(15)
        rep = self._recevoir(bc, ligne, 15)
        self.assertEqual(rep.status_code, 200, rep.data)
        # Réponse inchangée : le BCF sérialisé.
        self.assertEqual(rep.data['id'], bc.pk)
        reception = ReceptionFournisseur.objects.get(bon_commande=bc)
        self.assertEqual(reception.statut, ReceptionFournisseur.Statut.CONFIRME)
        self.assertEqual(reception.lignes.get().quantite_appliquee, 15)
        # Provision GR/IR posée par l'abonné de la confirmation.
        self.assertEqual(ReceptionNonFacturee.objects.filter(
            company=self.company, reception=reception).count(), 1)
        ligne.refresh_from_db()
        bc.refresh_from_db()
        self.produit.refresh_from_db()
        self.assertEqual(ligne.quantite_recue, 15)
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.RECU)
        self.assertEqual(self.produit.quantite_stock, 15)
        mvt = MouvementStock.objects.get(produit=self.produit)
        self.assertEqual(mvt.reference, reception.reference)

    def test_identique_a_reception_puis_confirmer(self):
        bc1, ligne1 = self._bcf(10)
        self.assertEqual(self._recevoir(bc1, ligne1, 6).status_code, 200)

        bc2, ligne2 = self._bcf(10)
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-ASTK62-MANUEL',
            bon_commande=bc2, statut=ReceptionFournisseur.Statut.BROUILLON,
            created_by=self.user)
        reception.lignes.create(
            ligne_commande=ligne2, produit=self.produit, quantite=6)
        confirm_reception_fournisseur(reception, self.user)

        ligne1.refresh_from_db()
        ligne2.refresh_from_db()
        bc1.refresh_from_db()
        bc2.refresh_from_db()
        self.assertEqual(ligne1.quantite_recue, ligne2.quantite_recue)
        self.assertEqual(bc1.statut, bc2.statut)
        rec1 = ReceptionFournisseur.objects.get(bon_commande=bc1)
        self.assertEqual(rec1.statut, reception.statut)
        for rec in (rec1, reception):
            self.assertEqual(ReceptionNonFacturee.objects.filter(
                company=self.company, reception=rec).count(), 1)
            self.assertEqual(MouvementStock.objects.filter(
                reference=rec.reference,
                type_mouvement=MouvementStock.TypeMouvement.ENTREE).count(), 1)

    def test_reception_par_le_bcf_annulable(self):
        bc, ligne = self._bcf(15)
        self.assertEqual(self._recevoir(bc, ligne, 15).status_code, 200)
        reception = ReceptionFournisseur.objects.get(bon_commande=bc)
        annuler_reception_confirmee(reception, self.user)
        self.produit.refresh_from_db()
        ligne.refresh_from_db()
        bc.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertEqual(ligne.quantite_recue, 0)
        self.assertEqual(bc.statut, BonCommandeFournisseur.Statut.ENVOYE)

    def test_controle_qualite_exige_refuse_comme_confirmer(self):
        PlanEchantillonnage.objects.create(
            company=self.company, categorie=self.categorie,
            taux_echantillon_pct=100)
        bc, ligne = self._bcf(15)
        rep = self._recevoir(bc, ligne, 15)
        self.assertEqual(rep.status_code, 400, rep.data)
        self.assertIn("plan d'échantillonnage", rep.data['detail'])
        # Rien n'est écrit : ni réception, ni stock, ni quantité reçue.
        self.assertFalse(
            ReceptionFournisseur.objects.filter(bon_commande=bc).exists())
        self.produit.refresh_from_db()
        ligne.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)
        self.assertEqual(ligne.quantite_recue, 0)

    def test_quantite_non_entiere_400(self):
        bc, ligne = self._bcf(15)
        # La quantité est un ENTIER JSON (schéma == serveur, api-fuzz) : 2.5 et '2.5' -> 400.
        for quantite in ('2.5', 2.5, '3', True, 0, -1):
            rep = self._recevoir(bc, ligne, quantite)
            self.assertEqual(rep.status_code, 400, (quantite, rep.data))
            self.assertIn('receptions', rep.data)
        self.assertFalse(
            ReceptionFournisseur.objects.filter(bon_commande=bc).exists())
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 0)

    def test_corps_hors_schema_400_et_inconnus_404(self):
        # api-fuzz : item vide / liste vide / corps non objet = 400 ; ligne ou
        # conditionnement inconnu = 404 (jamais 400 « Réception invalide »).
        bc, ligne = self._bcf(15)
        url = f'{URL}{bc.pk}/recevoir/'
        for corps in ({'receptions': [{}]}, {'receptions': []}, {}, [],
                      {'receptions': [{'ligne': {}, 'quantite': 1}]},
                      {'receptions': [{'ligne': ligne.pk, 'quantite': 1, 'conditionnement': {}}]}):
            self.assertEqual(self.api.post(url, corps, format='json').status_code, 400, corps)
        for item in ({'ligne': 987654, 'quantite': 1},
                     {'ligne': ligne.pk, 'quantite': 1, 'conditionnement': 987654},
                     {'ligne': ligne.pk, 'quantite': 1, 'conditionnement_code_barres': 'INCONNU'}):
            rep = self.api.post(url, {'receptions': [item]}, format='json')
            self.assertEqual(rep.status_code, 404, (item, rep.data))
        self.assertFalse(ReceptionFournisseur.objects.filter(bon_commande=bc).exists())
