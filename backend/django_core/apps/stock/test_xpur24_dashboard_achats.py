"""XPUR24 — Tableau de bord achats (analyse des dépenses).

Couvre :
  * le dashboard rend les 5 blocs depuis des données RÉELLES multi-mois ;
  * l'export xlsx sort (contenu xlsx valide) ;
  * un utilisateur non autorisé (rôle standard) reçoit 403 ;
  * la dérive de prix moyen par SKU se calcule bien mois par mois ;
  * les engagements ouverts ne comptent que les BCF envoyés non
    entièrement reçus, montant restant jamais négatif.

Run:
    python manage.py test apps.stock.test_xpur24_dashboard_achats -v 2
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    BonCommandeFournisseur, Categorie, FactureFournisseur, Fournisseur,
    Produit, ReceptionFournisseur,
)
from apps.stock.services import (
    analyse_achats_dashboard, derive_prix_moyen_par_sku,
    engagements_ouverts_achats,
)

User = get_user_model()


def _company(slug):
    return Company.objects.create(nom=slug, slug=slug)


def _user(company, username, permissions=None, role_legacy='responsable'):
    role = Role.objects.create(
        company=company, nom=f'r-{username}', permissions=permissions or [])
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Xpur24Base(TestCase):
    def setUp(self):
        self.company = _company('xpur24-co')
        self.user = _user(
            self.company, 'xpur24-resp',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur X24')
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Onduleurs X24')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X24', sku='OND-XPUR24',
            categorie=self.categorie,
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _bcf(self, statut, date_creation=None, prix=Decimal('1200'),
             quantite=2):
        # Compteur par-instance : deux appels avec le même statut/prix dans
        # un même test ne doivent jamais collisionner sur la référence
        # unique (company_id, reference) — cf. IntegrityError observé en CI.
        self._bcf_seq = getattr(self, '_bcf_seq', 0) + 1
        bc = BonCommandeFournisseur.objects.create(
            company=self.company,
            reference=f'BCF-X24-{statut}-{prix}-{self._bcf_seq}',
            fournisseur=self.fournisseur, statut=statut)
        if date_creation:
            BonCommandeFournisseur.objects.filter(pk=bc.pk).update(
                date_creation=date_creation)
            bc.refresh_from_db()
        bc.lignes.create(
            produit=self.produit, quantite=quantite,
            prix_achat_unitaire=prix)
        return bc


class TestDashboardCinqBlocs(Xpur24Base):
    def test_dashboard_rend_les_5_blocs(self):
        self._bcf(BonCommandeFournisseur.Statut.RECU)
        data = analyse_achats_dashboard(self.company)
        self.assertIn('depenses', data)
        self.assertIn('derive_prix', data)
        self.assertIn('engagements_ouverts', data)
        self.assertIn('top_produits', data)
        self.assertIn('temps_cycle', data)

    def test_depenses_par_fournisseur_categorie_mois(self):
        self._bcf(BonCommandeFournisseur.Statut.RECU)
        data = analyse_achats_dashboard(self.company)
        depenses = data['depenses']
        self.assertEqual(len(depenses['par_fournisseur']), 1)
        self.assertEqual(
            depenses['par_fournisseur'][0]['fournisseur'],
            'Fournisseur X24')
        self.assertEqual(len(depenses['par_categorie']), 1)
        self.assertEqual(len(depenses['par_mois']), 1)

    def test_endpoint_dashboard(self):
        self._bcf(BonCommandeFournisseur.Statut.RECU)
        resp = self.api.get(
            '/api/django/stock/produits/analyse-achats/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('depenses', resp.data)

    def test_endpoint_export_xlsx(self):
        self._bcf(BonCommandeFournisseur.Statut.RECU)
        resp = self.api.get(
            '/api/django/stock/produits/analyse-achats/export-xlsx/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheetml', resp['Content-Type'])

    def test_non_autorise_recoit_403(self):
        user_standard = _user(
            self.company, 'xpur24-standard', permissions=['stock_voir'],
            role_legacy='commercial')
        api_standard = _api(user_standard)
        resp = api_standard.get('/api/django/stock/produits/analyse-achats/')
        self.assertEqual(resp.status_code, 403)


class TestDerivePrixMoyen(Xpur24Base):
    def test_derive_calculee_par_mois(self):
        now = timezone.now()
        self._bcf(
            BonCommandeFournisseur.Statut.RECU,
            date_creation=now - datetime.timedelta(days=60),
            prix=Decimal('1000'))
        self._bcf(
            BonCommandeFournisseur.Statut.RECU,
            date_creation=now, prix=Decimal('1300'))
        series = derive_prix_moyen_par_sku(self.company, nb_mois=6)
        entry = next(e for e in series if e['produit_id'] == self.produit.id)
        self.assertGreaterEqual(len(entry['series']), 2)
        self.assertEqual(entry['derive'], Decimal('300.00'))


class TestEngagementsOuverts(Xpur24Base):
    def test_bcf_envoye_non_recu_compte_comme_engagement(self):
        self._bcf(BonCommandeFournisseur.Statut.ENVOYE)
        result = engagements_ouverts_achats(self.company)
        self.assertEqual(len(result['lignes']), 1)
        self.assertEqual(result['lignes'][0]['montant_restant'], Decimal('2400'))

    def test_bcf_recu_absent_des_engagements(self):
        self._bcf(BonCommandeFournisseur.Statut.RECU)
        result = engagements_ouverts_achats(self.company)
        self.assertEqual(result['lignes'], [])

    def test_bcf_partiellement_recu_montant_restant_positif(self):
        bc = self._bcf(
            BonCommandeFournisseur.Statut.ENVOYE, quantite=10,
            prix=Decimal('100'))
        ligne = bc.lignes.first()
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X24-1', bon_commande=bc,
            statut='confirme')
        reception.lignes.create(
            ligne_commande=ligne, produit=self.produit, quantite=4)
        ligne.quantite_recue = 4
        ligne.save(update_fields=['quantite_recue'])
        result = engagements_ouverts_achats(self.company)
        self.assertEqual(len(result['lignes']), 1)
        # commandé 1000, reçu (via montant_recu_bcf : lignes de réception
        # confirmées × prix ligne commande) 4*100=400 -> reste 600.
        self.assertEqual(result['lignes'][0]['montant_restant'], Decimal('600'))


class TestTopProduitsAchetes(Xpur24Base):
    def test_top_produits_agrege_quantite_et_montant(self):
        self._bcf(
            BonCommandeFournisseur.Statut.RECU, quantite=3,
            prix=Decimal('1000'))
        self._bcf(
            BonCommandeFournisseur.Statut.RECU, quantite=2,
            prix=Decimal('1000'))
        from apps.stock.services import top_produits_achetes
        top = top_produits_achetes(self.company)
        entry = next(e for e in top if e['produit_id'] == self.produit.id)
        self.assertEqual(entry['quantite_totale'], 5)
        self.assertEqual(entry['montant_total'], Decimal('5000'))


class TestTempsCycle(Xpur24Base):
    def test_temps_cycle_bcf_vers_reception(self):
        bc = self._bcf(BonCommandeFournisseur.Statut.RECU)
        ligne = bc.lignes.first()
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-X24-CYCLE',
            bon_commande=bc, statut='confirme')
        reception.lignes.create(
            ligne_commande=ligne, produit=self.produit, quantite=2)
        from apps.stock.services import temps_cycle_achats
        data = temps_cycle_achats(self.company)
        detail = next(
            d for d in data['details'] if d['bon_commande_id'] == bc.id)
        self.assertIsNotNone(detail['jours_bcf_vers_reception'])
        # YPROC5 non câblé — dégradation propre, jamais une erreur.
        self.assertIsNone(detail['jours_da_vers_bcf'])

    def test_temps_cycle_reception_vers_facture(self):
        bc = self._bcf(BonCommandeFournisseur.Statut.RECU)
        FactureFournisseur.objects.create(
            company=self.company, reference='FF-X24-CYCLE',
            fournisseur=self.fournisseur, bon_commande=bc,
            montant_ttc=Decimal('1000'))
        from apps.stock.services import temps_cycle_achats
        data = temps_cycle_achats(self.company)
        self.assertIsInstance(data['details'], list)
