"""XPUR10 — Tolérances par société & file d'exceptions sur le rapprochement
3 voies + blocage réel du paiement.

Couvre :
  * une facture à +0,5 % passe bon-à-payer (dans la tolérance) ;
  * une facture à +8 % a son paiement refusé jusqu'à résolution motivée ;
  * les défauts société pré-remplissent (tolerance_prix_pct) ;
  * résolution débloque le paiement + trace l'acteur ;
  * pas de BCF/rapprochement = comportement historique (jamais bloqué) ;
  * lecture via compta.selectors (jamais d'import de modèles compta).

Run:
    python manage.py test apps.stock.test_xpur10_tolerances_exceptions -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, FactureFournisseur,
    Fournisseur, LigneBonCommandeFournisseur, Produit,
    ReceptionFournisseur, LigneReceptionFournisseur,
)
from apps.stock.services import (
    check_facture_exception_gate, evaluate_facture_exception,
    factures_en_exception, resoudre_exception_facture,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy='responsable')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur10Base(TestCase):
    def setUp(self):
        self.company = _company('xpur10-co')
        self.user = _user(
            self.company, 'xpur10-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur 3 voies')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 3v', sku='OND-XPUR10',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1000'))

    def _bcf_recu(self, quantite=10, prix=Decimal('1000')):
        bcf = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-XPUR10-0001',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        ligne = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bcf, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=prix, quantite_recue=quantite)
        rec = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-XPUR10-0001',
            bon_commande=bcf, statut=ReceptionFournisseur.Statut.CONFIRME)
        LigneReceptionFournisseur.objects.create(
            reception=rec, ligne_commande=ligne, produit=self.produit,
            quantite=quantite)
        return bcf

    def _rapprochement(self, bcf, montant_recu, montant_facture):
        """Crée un Rapprochement compta directement (évite de dépendre du
        cheminement complet compta.services pour ce test unitaire ciblé)."""
        from apps.compta.models import Rapprochement
        return Rapprochement.objects.create(
            company=self.company, bon_commande=bcf,
            montant_commande=montant_recu, montant_recu=montant_recu,
            montant_facture=montant_facture,
            ecart=montant_facture - montant_recu)


class TestNoBcfNoRapprochement(Xpur10Base):
    def test_facture_sans_bcf_never_exception(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0001',
            fournisseur=self.fournisseur, montant_ttc=Decimal('1200'))
        en_exception, ecart = evaluate_facture_exception(
            self.company, facture)
        self.assertFalse(en_exception)
        self.assertIsNone(ecart)
        # No-op — payment gate never raises.
        check_facture_exception_gate(self.company, facture)

    def test_bcf_sans_rapprochement_evalue_never_exception(self):
        bcf = self._bcf_recu()
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0002',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12000'))
        en_exception, ecart = evaluate_facture_exception(
            self.company, facture)
        self.assertFalse(en_exception)
        self.assertIsNone(ecart)


class TestWithinTolerance(Xpur10Base):
    def test_0_5_pct_ecart_passes_within_default_tolerance(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10050'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0003',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12060'))
        en_exception, ecart_pct = evaluate_facture_exception(
            self.company, facture)
        self.assertFalse(en_exception)
        self.assertAlmostEqual(float(ecart_pct), 0.5, places=1)
        # Payment allowed.
        check_facture_exception_gate(self.company, facture)


class TestOutsideTolerance(Xpur10Base):
    def test_8_pct_ecart_blocks_payment_until_resolved(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10800'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0004',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12960'))
        with self.assertRaises(ValueError):
            check_facture_exception_gate(self.company, facture)
        facture.refresh_from_db()
        self.assertEqual(
            facture.statut_controle, FactureFournisseur.StatutControle.EXCEPTION)
        self.assertIsNotNone(facture.motif_ecart)

    def test_payment_endpoint_refused_in_exception(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10800'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0005',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12960'))
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '12960',
        }, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_facture_paiements_action_also_blocked(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10800'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0006',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12960'))
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/paiements/',
            {'montant': '12960'}, format='json')
        self.assertEqual(resp.status_code, 400, resp.data)


class TestResolution(Xpur10Base):
    def test_resolution_unblocks_payment_and_traces_actor(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10800'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0007',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12960'))
        with self.assertRaises(ValueError):
            check_facture_exception_gate(self.company, facture)
        facture.refresh_from_db()

        resoudre_exception_facture(
            facture, user=self.user, commentaire='Écart de fret accepté')
        facture.refresh_from_db()
        self.assertEqual(
            facture.statut_controle, FactureFournisseur.StatutControle.RESOLUE)
        self.assertEqual(facture.resolu_par_id, self.user.id)
        self.assertIsNotNone(facture.resolu_le)

        # Payment now allowed (resolved status is never re-evaluated back to
        # exception by the gate).
        check_facture_exception_gate(self.company, facture)
        resp = self.api.post('/api/django/stock/paiements-fournisseur/', {
            'facture': facture.id, 'montant': '12960',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_resolving_non_exception_facture_refused(self):
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0008',
            fournisseur=self.fournisseur, montant_ttc=Decimal('1200'))
        with self.assertRaises(ValueError):
            resoudre_exception_facture(facture, user=self.user)

    def test_resoudre_exception_endpoint(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10800'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0009',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12960'))
        evaluate_facture_exception(self.company, facture)
        resp = self.api.post(
            f'/api/django/stock/factures-fournisseur/{facture.id}/'
            'resoudre-exception/',
            {'commentaire': 'OK'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['statut_controle'], 'resolue')


class TestExceptionQueue(Xpur10Base):
    def test_en_exception_lists_only_exceptions(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10800'))
        facture_exception = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0010',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12960'))
        evaluate_facture_exception(self.company, facture_exception)
        facture_normale = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0011',
            fournisseur=self.fournisseur, montant_ttc=Decimal('1200'))
        qs = factures_en_exception(self.company)
        ids = [f.id for f in qs]
        self.assertIn(facture_exception.id, ids)
        self.assertNotIn(facture_normale.id, ids)

    def test_en_exception_endpoint(self):
        AchatsParametres.objects.create(
            company=self.company, tolerance_prix_pct=Decimal('1'))
        bcf = self._bcf_recu()
        self._rapprochement(
            bcf, montant_recu=Decimal('10000'), montant_facture=Decimal('10800'))
        facture = FactureFournisseur.objects.create(
            company=self.company, reference='FF-XPUR10-0012',
            fournisseur=self.fournisseur, bon_commande=bcf,
            montant_ttc=Decimal('12960'))
        evaluate_facture_exception(self.company, facture)
        resp = self.api.get(
            '/api/django/stock/factures-fournisseur/en-exception/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertGreaterEqual(len(resp.data), 1)
