"""AUD226 — le relevé catch-weight rejoint le stock par une action EXPLICITE.

Constat R2 : la quantité et la valeur réellement pesées (NTWMS37) étaient
display-only — hors de leur module, seul l'endpoint d'affichage les lisait ;
ni `Produit.quantite_stock` ni le coût moyen ne les voyaient jamais. Le relevé
était un chiffre mort sur un écran.

Option de repli RETENUE (autorisée par la tâche) : le relevé reste informatif
(valorisation + litige fournisseur) parce que `quantite_stock` compte des
UNITÉS entières là où le relevé est un décimal dans une unité de MESURE, et que
rabattre `quantite_recue` sur le relevé laisserait le BCF éternellement
« partiellement reçu ». L'écart se solde donc par une action de rapprochement
explicite et tracée — un ajustement N16 posé par `record_stock_movement` (donc
miroir comptable et alerte seuil-bas inclus), idempotent.

Run :
    python manage.py test apps.stock.test_aud226_rapprochement_pesee -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    BonCommandeFournisseur, Fournisseur, LigneBonCommandeFournisseur,
    LigneReceptionFournisseur, MouvementStock, Produit, ReceptionFournisseur,
)
from apps.stock.services import confirm_reception_fournisseur
from apps.stock.services_catch_weight import (
    ecart_pesee_reception, enregistrer_pesee_ligne_reception,
    rapprocher_pesee_reception, reference_rapprochement,
)

User = get_user_model()


def make_company(slug='aud226-co', nom='AUD226 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud226Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud226_admin', password='x', role_legacy='admin',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Câbles AUD226')
        self.cable = Produit.objects.create(
            company=self.company, nom='Câble solaire AUD226', sku='AUD226-1',
            prix_achat=Decimal('12'), prix_vente=Decimal('18'),
            quantite_stock=0)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur AUD226', sku='AUD226-2',
            prix_achat=Decimal('6000'), prix_vente=Decimal('8000'),
            quantite_stock=0)
        self.bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUD226-1',
            fournisseur=self.fournisseur)
        self.ligne_cmd_cable = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.cable, quantite=100,
            prix_achat_unitaire=Decimal('12'))
        self.ligne_cmd_onduleur = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bc, produit=self.onduleur, quantite=2,
            prix_achat_unitaire=Decimal('6000'))
        self.reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-AUD226-1', bon_commande=self.bc)
        self.ligne_cable = LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=self.ligne_cmd_cable,
            produit=self.cable, quantite=100)
        self.ligne_onduleur = LigneReceptionFournisseur.objects.create(
            reception=self.reception, ligne_commande=self.ligne_cmd_onduleur,
            produit=self.onduleur, quantite=2)

    def _peser(self, quantite_reelle, ligne=None):
        return enregistrer_pesee_ligne_reception(
            ligne_reception=ligne or self.ligne_cable, user=self.admin,
            unite_variable=True, quantite_reelle=quantite_reelle,
            unite_mesure='m')

    def _confirmer(self):
        confirm_reception_fournisseur(self.reception, self.admin)
        self.cable.refresh_from_db()
        self.onduleur.refresh_from_db()


class TestRapprochementPesee(Aud226Base):
    def test_ecart_expose_avec_son_arrondi_en_unites(self):
        self._peser('98.400')
        self._confirmer()

        ecarts = ecart_pesee_reception(self.reception)

        self.assertEqual(len(ecarts), 1)   # l'onduleur n'a aucun relevé
        self.assertEqual(ecarts[0]['ecart'], Decimal('-1.600'))
        self.assertEqual(ecarts[0]['ecart_entier'], -2)

    def test_le_rapprochement_corrige_le_stock_canonique(self):
        self._peser('98.400')
        self._confirmer()
        self.assertEqual(self.cable.quantite_stock, 100)   # nominal à l'entrée

        res = rapprocher_pesee_reception(
            reception=self.reception, user=self.admin)

        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 98)
        self.assertEqual(res['ajustes'], 1)

    def test_le_rapprochement_est_trace_en_ajustement(self):
        self._peser('98.400')
        self._confirmer()
        rapprocher_pesee_reception(reception=self.reception, user=self.admin)

        mvt = MouvementStock.objects.get(
            produit=self.cable,
            reference=reference_rapprochement(self.reception))
        self.assertEqual(mvt.type_mouvement,
                         MouvementStock.TypeMouvement.AJUSTEMENT)
        self.assertEqual(mvt.quantite, 2)
        self.assertEqual(mvt.quantite_avant, 100)
        self.assertEqual(mvt.quantite_apres, 98)
        self.assertIn('98.400', mvt.note)

    def test_rapprochement_idempotent(self):
        self._peser('98.400')
        self._confirmer()
        rapprocher_pesee_reception(reception=self.reception, user=self.admin)

        with self.assertRaises(ValueError):
            rapprocher_pesee_reception(
                reception=self.reception, user=self.admin)

        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 98)

    def test_ecart_negligeable_ne_pose_aucun_mouvement(self):
        # 99,8 m pour 100 nominal : l'écart s'arrondit à 0 unité.
        self._peser('99.800')
        self._confirmer()

        res = rapprocher_pesee_reception(
            reception=self.reception, user=self.admin)

        self.assertEqual(res, {'ajustes': 0, 'inchanges': 1, 'mouvements': []})
        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 100)

    def test_reception_non_confirmee_refusee(self):
        self._peser('98.400')
        with self.assertRaises(ValueError):
            rapprocher_pesee_reception(
                reception=self.reception, user=self.admin)

    def test_ligne_sans_releve_intouchee(self):
        self._peser('98.400')
        self._confirmer()
        rapprocher_pesee_reception(reception=self.reception, user=self.admin)

        self.onduleur.refresh_from_db()
        self.assertEqual(self.onduleur.quantite_stock, 2)
        self.assertFalse(MouvementStock.objects.filter(
            produit=self.onduleur,
            reference=reference_rapprochement(self.reception)).exists())

    def test_surplus_pese_augmente_le_stock(self):
        self._peser('102.600')
        self._confirmer()

        rapprocher_pesee_reception(reception=self.reception, user=self.admin)

        self.cable.refresh_from_db()
        self.assertEqual(self.cable.quantite_stock, 103)
