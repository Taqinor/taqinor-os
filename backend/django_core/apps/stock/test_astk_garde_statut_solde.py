"""ASTK111 (C-ASTK-035, C7, S2) — garde de CLASSE « statut ⇔ solde ».

Après CHAQUE écriture AP (paiement, tentative de PATCH de paiement, annulation
de paiement, imputation d'acompte, imputation d'avoir, facturation de
réception), le statut de la facture fournisseur est la projection de
``solde_du`` (solde = TTC → à payer ; solde ≤ 0 → payée ; entre les deux →
partiellement payée) ET ``comptes-a-payer`` = exactement les factures à solde
> 0. La propriété est rejouée sur une GRILLE d'ordres et de montants (aucune
liste de numéros) ; un chemin d'écriture qui oublie le recalcul fait échouer la
garde avec le NOM du pas.

Services et endpoints réels, aucun mock.

Run :
    python manage.py test apps.stock.test_astk_garde_statut_solde -v 2
"""
import datetime
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.roles.models import Role
from apps.stock.models import (
    AcompteFournisseur, AvoirFournisseur, BonCommandeFournisseur,
    FactureFournisseur, Fournisseur, ImputationAcompteFournisseur,
    LigneBonCommandeFournisseur, LigneReceptionFournisseur,
    PaiementFournisseur, Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    facturer_reception, imputer_acomptes_bcf, imputer_avoir_fournisseur,
)
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/stock/factures-fournisseur/'
PAIEMENTS = '/api/django/stock/paiements-fournisseur/'
TTC = Decimal('12000.00')
MONTANTS = {'paiement': Decimal('3000'), 'avoir': Decimal('2500'),
            'acompte': Decimal('1500')}


def projection(facture):
    """Statut attendu, dérivé du SEUL ``solde_du`` (oracle de la garde)."""
    ttc = facture.montant_ttc or Decimal('0')
    solde = facture.solde_du
    if solde >= ttc:
        return FactureFournisseur.Statut.A_PAYER
    if solde <= Decimal('0'):
        return FactureFournisseur.Statut.PAYEE
    return FactureFournisseur.Statut.PARTIELLEMENT_PAYEE


class GardeStatutSolde(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='astk111-co', slug='astk111-co')
        role = Role.objects.create(
            company=self.company, nom='r-astk111',
            permissions=['stock_voir', 'stock_modifier', 'prix_achat_voir',
                         'achats_payer'])
        self.user = User.objects.create_user(
            username='astk111-user', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.admin = User.objects.create_superuser(
            username='astk111-admin', password='x',
            email='astk111@example.test')
        self.admin.company = self.company
        self.admin.save(update_fields=['company'])
        self.api_admin = APIClient()
        self.api_admin.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur ASTK111')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur ASTK111', sku='OND-ASTK111',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'),
            tva=Decimal('20'))
        self.n = 0

    # ── jeu de données ──────────────────────────────────────────────────────
    def _bcf_et_reception(self):
        self.n += 1
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-ASTK111-{self.n}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=10,
            prix_achat_unitaire=Decimal('1000'))
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference=f'REC-ASTK111-{self.n}',
            bon_commande=bcf, statut=ReceptionFournisseur.Statut.CONFIRME,
            date_reception=datetime.date(2026, 10, 1))
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=10)
        return bcf, rec

    # ── les écritures AP (un nom de pas chacune) ───────────────────────────
    def _pas_paiement(self, ctx, montant):
        facture = FactureFournisseur.objects.get(pk=ctx['facture'].pk)
        montant = min(montant, facture.solde_du)
        if montant <= 0:
            return
        reponse = self.api.post(
            f'{BASE}{facture.pk}/paiements/',
            {'montant': str(montant), 'date_paiement': '2026-10-02'},
            format='json')
        assert reponse.status_code == 201, reponse.content
        ctx['dernier_paiement'] = reponse.data.get('id')

    def _pas_patch_paiement(self, ctx, montant):
        paiement = PaiementFournisseur.objects.filter(
            facture=ctx['facture']).order_by('-id').first()
        if paiement is None:
            return
        # Refusé aujourd'hui (405, ASTK27) : l'invariant doit tenir ensuite,
        # que le serveur accepte ou refuse l'écriture.
        self.api.patch(f'{PAIEMENTS}{paiement.pk}/',
                       {'montant': str(montant)}, format='json')

    def _pas_annulation_paiement(self, ctx, montant):
        paiement = PaiementFournisseur.objects.filter(
            facture=ctx['facture']).order_by('-id').first()
        if paiement is None:
            return
        self.api_admin.delete(f'{PAIEMENTS}{paiement.pk}/')

    def _pas_acompte(self, ctx, montant):
        AcompteFournisseur.objects.create(
            company=self.company, bon_commande=ctx['bcf'], montant=montant)
        imputer_acomptes_bcf(ctx['bcf'])

    def _pas_avoir(self, ctx, montant):
        self.n += 1
        facture = FactureFournisseur.objects.get(pk=ctx['facture'].pk)
        montant = min(montant, facture.solde_du)
        if montant <= 0:
            return
        avoir = AvoirFournisseur.objects.create(
            company=self.company, reference=f'AVF-ASTK111-{self.n}',
            fournisseur=self.fournisseur, montant_ttc=montant,
            statut=AvoirFournisseur.Statut.VALIDE)
        imputer_avoir_fournisseur(avoir, facture, user=self.user)

    def _pas(self, nom):
        return {
            'paiement': self._pas_paiement,
            'patch_paiement': self._pas_patch_paiement,
            'annulation_paiement': self._pas_annulation_paiement,
            'acompte': self._pas_acompte,
            'avoir': self._pas_avoir,
        }[nom]

    # ── l'invariant ─────────────────────────────────────────────────────────
    def _invariant(self, contexte):
        """Liste des violations après un pas (vide = invariant tenu)."""
        violations = []
        factures = list(FactureFournisseur.objects.filter(
            company=self.company))
        for facture in factures:
            attendu = projection(facture)
            if facture.statut != attendu:
                violations.append(
                    f'{contexte} : {facture.reference} statut='
                    f'{facture.statut} mais solde_du={facture.solde_du} '
                    f'(TTC {facture.montant_ttc}) ⇒ attendu {attendu}')
        reponse = self.api.get(f'{BASE}comptes-a-payer/')
        if reponse.status_code != 200:
            violations.append(
                f'{contexte} : comptes-a-payer → {reponse.status_code}')
            return violations
        ids = {f['id'] for f in reponse.data['results']}
        attendus = {f.id for f in factures if f.solde_du > 0}
        if ids != attendus:
            violations.append(
                f'{contexte} : comptes-a-payer={sorted(ids)} ≠ factures à '
                f'solde > 0 = {sorted(attendus)}')
        return violations

    # ── la propriété ────────────────────────────────────────────────────────
    def test_invariant_apres_chaque_ecriture(self):
        violations = []
        ordres = list(itertools.permutations(('paiement', 'avoir', 'acompte')))
        for index, ordre in enumerate(ordres):
            bcf, rec = self._bcf_et_reception()
            facture = facturer_reception(self.company, self.user, rec)
            ctx = {'bcf': bcf, 'facture': facture}
            violations += self._invariant(f'cas{index}/facturation_reception')
            sequence = list(ordre) + ['patch_paiement',
                                      'annulation_paiement', 'paiement']
            for nom in sequence:
                montant = MONTANTS.get(nom, Decimal('100'))
                if nom == 'paiement' and nom == sequence[-1]:
                    montant = TTC  # solde le reste (plafonné au solde dû)
                self._pas(nom)(ctx, montant)
                violations += self._invariant(f'cas{index}/{nom}')
        self.assertEqual(
            violations, [],
            'Statut ≠ projection(solde_du) après une écriture AP :\n'
            + '\n'.join(violations))

    def test_facturation_avec_acompte_prealable(self):
        """Facturation de réception sur BCF déjà acompté (acompte < TTC,
        puis acompte = TTC) : statut = projection du solde dès la création."""
        violations = []
        for montant in (Decimal('3600'), TTC):
            bcf, rec = self._bcf_et_reception()
            AcompteFournisseur.objects.create(
                company=self.company, bon_commande=bcf, montant=montant)
            facture = facturer_reception(self.company, self.user, rec)
            ctx = {'bcf': bcf, 'facture': facture}
            violations += self._invariant(
                f'acompte_prealable_{montant}/facturation_reception')
            self._pas_paiement(ctx, TTC)
            violations += self._invariant(
                f'acompte_prealable_{montant}/paiement')
        self.assertEqual(violations, [], '\n'.join(violations))

    def test_la_garde_nomme_le_pas_qui_oublie_le_recalcul(self):
        """Test-du-test : une imputation d'acompte écrite SANS recalcul (on
        retire l'appel à recompute) est repérée avec le nom du pas."""
        bcf, rec = self._bcf_et_reception()
        facture = facturer_reception(self.company, self.user, rec)
        acompte = AcompteFournisseur.objects.create(
            company=self.company, bon_commande=bcf, montant=Decimal('3000'))
        ImputationAcompteFournisseur.objects.create(
            company=self.company, acompte=acompte, facture=facture,
            montant=Decimal('3000'))  # aucun recompute_facture_..._statut
        violations = self._invariant('acompte_sans_recalcul')
        self.assertTrue(
            any('acompte_sans_recalcul' in v and facture.reference in v
                for v in violations), violations)
