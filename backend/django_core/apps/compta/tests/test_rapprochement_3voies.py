"""Tests FG131 — rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur).

Contrôle de pré-paiement : on confronte les trois montants HT d'un même achat —
COMMANDÉ (bon de commande fournisseur), REÇU (réceptions confirmées) et FACTURÉ
(facture fournisseur). Les trois documents vivent dans ``apps.stock`` et sont
lus UNIQUEMENT via ``apps.stock.selectors`` ; la compta ne duplique aucun
document d'achat (elle ne fait que les référencer + comparer).

Couvre :
* lecture cross-app des trois montants via les sélecteurs de stock ;
* création d'un rapprochement (idempotente) + évaluation immédiate de l'écart ;
* concordance vs écart bloquant (facturé > reçu hors tolérance) ;
* tolérance (arrondis/frais) ;
* validation (bon-à-payer) refusée tant qu'un écart bloque ;
* ``company`` posée côté serveur (jamais lue du corps) + isolation multi-société ;
* endpoints API + gate de rôle.

Run :
    python manage.py test apps.compta.tests.test_rapprochement_3voies -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import Rapprochement
from apps.stock import selectors as stock_selectors
from apps.stock import services as stock_services
from apps.stock.models import (
    BonCommandeFournisseur, FactureFournisseur, Fournisseur,
    LigneBonCommandeFournisseur, Produit, ReceptionFournisseur,
    LigneReceptionFournisseur,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _Fixture(TestCase):
    """Un BCF avec une ligne (10 × 90 = 900 HT commandé) par société."""

    def setUp(self):
        self.co = make_company('fg131', 'FG131 Co')
        self.user = make_user(self.co, 'fg131_resp')
        self.fournisseur = Fournisseur.objects.create(
            company=self.co, nom='Grossiste FG131')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau 550W', sku='FG131-A',
            prix_achat=Decimal('90'), prix_vente=Decimal('150'),
            quantite_stock=0)
        self.bon = BonCommandeFournisseur.objects.create(
            company=self.co, reference='BCF-FG131-1',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        self.ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=self.bon, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('90'))

    def _recevoir(self, qte):
        """Crée + confirme une réception de ``qte`` unités (entrée en stock)."""
        rec = ReceptionFournisseur.objects.create(
            company=self.co, reference=f'REC-FG131-{qte}',
            bon_commande=self.bon)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=self.ligne, produit=self.produit,
            quantite=qte)
        stock_services.confirm_reception_fournisseur(rec, self.user)
        return rec

    def _facturer(self, montant_ht):
        return FactureFournisseur.objects.create(
            company=self.co, reference=f'FF-FG131-{montant_ht}',
            fournisseur=self.fournisseur, bon_commande=self.bon,
            montant_ht=Decimal(montant_ht),
            montant_tva=Decimal('0'), montant_ttc=Decimal(montant_ht))


# ── Sélecteurs cross-app (stock) ───────────────────────────────────────────

class StockSelectorTests(_Fixture):
    def test_three_way_amounts_commande(self):
        data = stock_selectors.three_way_amounts(self.co, self.bon.id)
        self.assertTrue(data['exists'])
        self.assertEqual(data['montant_commande'], Decimal('900'))
        self.assertEqual(data['montant_recu'], Decimal('0'))
        self.assertEqual(data['montant_facture'], Decimal('0'))
        self.assertEqual(data['fournisseur_id'], self.fournisseur.id)

    def test_montant_recu_compte_seulement_les_receptions_confirmees(self):
        self._recevoir(4)  # 4 × 90 = 360 reçu
        data = stock_selectors.three_way_amounts(self.co, self.bon.id)
        self.assertEqual(data['montant_recu'], Decimal('360'))

    def test_montant_facture_somme_les_factures_du_bcf(self):
        self._facturer('500')
        self._facturer('100')
        data = stock_selectors.three_way_amounts(self.co, self.bon.id)
        self.assertEqual(data['montant_facture'], Decimal('600'))

    def test_bcf_autre_societe_invisible(self):
        autre = make_company('fg131-b', 'FG131 B')
        data = stock_selectors.three_way_amounts(autre, self.bon.id)
        self.assertFalse(data['exists'])


# ── Service — création / évaluation ─────────────────────────────────────────

class RapprochementServiceTests(_Fixture):
    def test_creer_pose_company_et_evalue(self):
        self._recevoir(10)   # 900 reçu
        self._facturer('900')  # 900 facturé
        rapp = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        self.assertEqual(rapp.company_id, self.co.id)
        self.assertEqual(rapp.montant_commande, Decimal('900'))
        self.assertEqual(rapp.montant_recu, Decimal('900'))
        self.assertEqual(rapp.montant_facture, Decimal('900'))
        self.assertEqual(rapp.ecart, Decimal('0'))
        self.assertEqual(rapp.statut, Rapprochement.Statut.CONCORDANT)
        self.assertTrue(rapp.bon_a_payer)

    def test_ecart_bloquant_quand_facture_depasse_recu(self):
        self._recevoir(4)    # 360 reçu
        self._facturer('900')  # 900 facturé → écart +540
        rapp = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        self.assertEqual(rapp.ecart, Decimal('540'))
        self.assertEqual(rapp.statut, Rapprochement.Statut.ECART)
        self.assertFalse(rapp.bon_a_payer)

    def test_tolerance_absorbe_un_petit_ecart(self):
        self._recevoir(10)   # 900 reçu
        self._facturer('905')  # 905 facturé → écart +5
        rapp = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id,
            tolerance=Decimal('10'), user=self.user)
        self.assertEqual(rapp.ecart, Decimal('5'))
        self.assertEqual(rapp.statut, Rapprochement.Statut.CONCORDANT)

    def test_creer_est_idempotent_et_reevalue(self):
        rapp1 = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        # Première éval : rien reçu/facturé → concordant (0 vs 0).
        self.assertEqual(rapp1.statut, Rapprochement.Statut.CONCORDANT)
        # On reçoit + facture puis on recrée : même objet, ré-évalué.
        self._recevoir(2)     # 180 reçu
        self._facturer('900')  # 900 facturé → écart +720
        rapp2 = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        self.assertEqual(rapp1.id, rapp2.id)
        self.assertEqual(Rapprochement.objects.filter(
            company=self.co, bon_commande=self.bon).count(), 1)
        self.assertEqual(rapp2.statut, Rapprochement.Statut.ECART)
        self.assertEqual(rapp2.ecart, Decimal('720'))

    def test_creer_refuse_bcf_inconnu(self):
        autre = make_company('fg131-c', 'FG131 C')
        with self.assertRaises(ValidationError):
            services.creer_rapprochement(
                autre, bon_commande_id=self.bon.id, user=self.user)

    def test_tolerance_negative_refusee(self):
        with self.assertRaises(ValidationError):
            services.creer_rapprochement(
                self.co, bon_commande_id=self.bon.id,
                tolerance=Decimal('-1'), user=self.user)

    def test_ecart_commande_recu_informatif(self):
        self._recevoir(4)  # 360 reçu vs 900 commandé → -540 (livraison partielle)
        rapp = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        self.assertEqual(rapp.ecart_commande_recu, Decimal('-540'))


# ── Service — validation (bon-à-payer) ──────────────────────────────────────

class RapprochementValidationTests(_Fixture):
    def test_valider_concordant_pose_bon_a_payer(self):
        self._recevoir(10)
        self._facturer('900')
        rapp = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        rapp = services.valider_rapprochement(rapp, user=self.user)
        self.assertEqual(rapp.statut, Rapprochement.Statut.VALIDE)
        self.assertEqual(rapp.valide_par_id, self.user.id)
        self.assertIsNotNone(rapp.date_validation)
        self.assertTrue(rapp.bon_a_payer)

    def test_valider_refuse_si_ecart_bloquant(self):
        self._recevoir(4)
        self._facturer('900')  # écart +540
        rapp = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        with self.assertRaises(ValidationError):
            services.valider_rapprochement(rapp, user=self.user)
        rapp.refresh_from_db()
        self.assertEqual(rapp.statut, Rapprochement.Statut.ECART)

    def test_validation_non_ecrasee_par_reevaluation(self):
        self._recevoir(10)
        self._facturer('900')
        rapp = services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        services.valider_rapprochement(rapp, user=self.user)
        # Une ré-évaluation ne doit pas dégrader un VALIDE en concordant/écart.
        rapp = services.evaluer_rapprochement(rapp)
        self.assertEqual(rapp.statut, Rapprochement.Statut.VALIDE)


# ── Sélecteur d'alerte ──────────────────────────────────────────────────────

class RapprochementSelectorTests(_Fixture):
    def test_rapprochements_en_ecart(self):
        self._recevoir(4)
        self._facturer('900')  # écart bloquant
        services.creer_rapprochement(
            self.co, bon_commande_id=self.bon.id, user=self.user)
        en_ecart = selectors.rapprochements_en_ecart(self.co)
        self.assertEqual(len(en_ecart), 1)
        self.assertEqual(en_ecart[0].bon_commande_id, self.bon.id)


# ── API + gate de rôle ──────────────────────────────────────────────────────

class RapprochementAPITests(_Fixture):
    URL = '/api/django/compta/rapprochements-3voies/'

    def test_create_pose_company_serveur(self):
        self._recevoir(10)
        self._facturer('900')
        api = auth(self.user)
        r = api.post(self.URL, {'bon_commande': self.bon.id,
                                'company': 99999}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        rapp = Rapprochement.objects.get(id=r.data['id'])
        self.assertEqual(rapp.company_id, self.co.id)  # corps ignoré
        self.assertEqual(r.data['statut'], 'concordant')
        self.assertEqual(Decimal(r.data['montant_recu']), Decimal('900'))

    def test_action_evaluer(self):
        api = auth(self.user)
        r = api.post(self.URL, {'bon_commande': self.bon.id}, format='json')
        rid = r.data['id']
        self._recevoir(2)
        self._facturer('900')  # écart +720
        r2 = api.post(f'{self.URL}{rid}/evaluer/')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['statut'], 'ecart')
        self.assertEqual(Decimal(r2.data['ecart']), Decimal('720'))

    def test_action_valider_refusee_si_ecart(self):
        self._recevoir(4)
        self._facturer('900')
        api = auth(self.user)
        r = api.post(self.URL, {'bon_commande': self.bon.id}, format='json')
        rid = r.data['id']
        r2 = api.post(f'{self.URL}{rid}/valider/')
        self.assertEqual(r2.status_code, 400, r2.data)

    def test_action_valider_ok_si_concordant(self):
        self._recevoir(10)
        self._facturer('900')
        api = auth(self.user)
        r = api.post(self.URL, {'bon_commande': self.bon.id}, format='json')
        rid = r.data['id']
        r2 = api.post(f'{self.URL}{rid}/valider/')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertEqual(r2.data['statut'], 'valide')

    def test_gate_de_role_refuse_un_commercial(self):
        commercial = make_user(self.co, 'fg131_com', role='commercial')
        api = auth(commercial)
        r = api.get(self.URL)
        self.assertEqual(r.status_code, 403)

    def test_isolation_multi_societe(self):
        autre = make_company('fg131-d', 'FG131 D')
        autre_user = make_user(autre, 'fg131_d_resp')
        api = auth(autre_user)
        # Un BCF d'une autre société ne peut être rapproché.
        r = api.post(self.URL, {'bon_commande': self.bon.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
