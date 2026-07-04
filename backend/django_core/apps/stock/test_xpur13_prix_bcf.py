"""XPUR13 — Garde-fous prix sur la ligne BCF (accords + historique).

Couvre :
  * une ligne au-dessus du prix convenu du contrat en vigueur lève un warning
    (jamais bloquant) qui affiche le prix convenu ;
  * un écart au-delà du seuil société vs le dernier prix/prix moyen lève un
    warning (0 = désactivé, comportement historique inchangé) ;
  * le popover « historique des prix » (endpoint) renvoie les achats
    récents, toutes sources ;
  * le rapport « achats hors contrat » liste les lignes au-dessus du prix
    convenu, filtrable par fournisseur/période.

Run:
    python manage.py test apps.stock.test_xpur13_prix_bcf -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.stock.models import (
    AchatsParametres, BonCommandeFournisseur, Fournisseur, Produit,
)
from apps.stock.services import (
    check_prix_ligne_bcf, historique_prix_produit, prix_moyen_recent_produit,
    rapport_achats_hors_contrat,
)
from apps.installations.models_contrat_prix import (
    ContratPrixFournisseur, ContratPrixLigne,
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


class Xpur13Base(TestCase):
    def setUp(self):
        self.company = _company('xpur13-co')
        self.user = _user(
            self.company, 'xpur13-user',
            permissions=['stock_modifier', 'stock_voir'])
        self.api = _api(self.user)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Prix')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X13', sku='OND-XPUR13',
            prix_vente=Decimal('2000'), prix_achat=Decimal('1200'))

    def _contrat_actif(self, prix_convenu):
        contrat = ContratPrixFournisseur.objects.create(
            company=self.company, reference='CPF-0001',
            intitule='Accord X13', fournisseur=self.fournisseur,
            statut=ContratPrixFournisseur.Statut.ACTIF)
        ContratPrixLigne.objects.create(
            contrat=contrat, produit=self.produit,
            prix_convenu=Decimal(str(prix_convenu)))
        return contrat


class TestCheckPrixLigneBcfContrat(Xpur13Base):
    def test_prix_au_dessus_du_contrat_leve_warning(self):
        self._contrat_actif(1000)
        result = check_prix_ligne_bcf(
            self.company, produit_id=self.produit.id,
            fournisseur_id=self.fournisseur.id, prix_saisi=1200)
        self.assertTrue(result['ok'])  # jamais bloquant
        self.assertEqual(len(result['warnings']), 1)
        self.assertEqual(result['warnings'][0]['type'], 'hors_contrat')
        self.assertEqual(
            result['warnings'][0]['prix_convenu'], Decimal('1000'))

    def test_prix_conforme_au_contrat_pas_de_warning(self):
        self._contrat_actif(1000)
        result = check_prix_ligne_bcf(
            self.company, produit_id=self.produit.id,
            fournisseur_id=self.fournisseur.id, prix_saisi=900)
        self.assertEqual(result['warnings'], [])

    def test_sans_contrat_pas_de_warning_contrat(self):
        result = check_prix_ligne_bcf(
            self.company, produit_id=self.produit.id,
            fournisseur_id=self.fournisseur.id, prix_saisi=5000)
        self.assertEqual(result['warnings'], [])


class TestCheckPrixLigneBcfDeviation(Xpur13Base):
    def _bcf_historique(self, prix):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-HIST-{prix}',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.RECU)
        bc.lignes.create(
            produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal(str(prix)))
        return bc

    def test_seuil_zero_desactive_le_warning_ecart(self):
        self._bcf_historique(1000)
        # seuil_deviation_prix_pct par défaut = 0 (comportement historique).
        result = check_prix_ligne_bcf(
            self.company, produit_id=self.produit.id,
            fournisseur_id=self.fournisseur.id, prix_saisi=5000)
        self.assertEqual(
            [w for w in result['warnings']
             if w['type'] == 'ecart_historique'], [])

    def test_ecart_au_dessus_du_seuil_leve_warning(self):
        AchatsParametres.objects.create(
            company=self.company, seuil_deviation_prix_pct=Decimal('10'))
        self._bcf_historique(1000)
        result = check_prix_ligne_bcf(
            self.company, produit_id=self.produit.id,
            fournisseur_id=self.fournisseur.id, prix_saisi=1500)
        ecarts = [w for w in result['warnings']
                  if w['type'] == 'ecart_historique']
        self.assertEqual(len(ecarts), 1)

    def test_ecart_sous_le_seuil_pas_de_warning(self):
        AchatsParametres.objects.create(
            company=self.company, seuil_deviation_prix_pct=Decimal('50'))
        self._bcf_historique(1000)
        result = check_prix_ligne_bcf(
            self.company, produit_id=self.produit.id,
            fournisseur_id=self.fournisseur.id, prix_saisi=1050)
        ecarts = [w for w in result['warnings']
                  if w['type'] == 'ecart_historique']
        self.assertEqual(ecarts, [])


class TestHistoriquePrix(Xpur13Base):
    def _bcf(self, prix, statut=BonCommandeFournisseur.Statut.RECU):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference=f'BCF-H-{prix}',
            fournisseur=self.fournisseur, statut=statut)
        bc.lignes.create(
            produit=self.produit, quantite=2,
            prix_achat_unitaire=Decimal(str(prix)))
        return bc

    def test_historique_liste_les_achats_recents(self):
        self._bcf(1000)
        self._bcf(1100)
        historique = historique_prix_produit(self.company, self.produit.id)
        self.assertEqual(len(historique), 2)

    def test_bcf_annule_exclu_de_l_historique(self):
        self._bcf(1000)
        self._bcf(9999, statut=BonCommandeFournisseur.Statut.ANNULE)
        historique = historique_prix_produit(self.company, self.produit.id)
        prix = [h['prix_achat_unitaire'] for h in historique]
        self.assertNotIn(Decimal('9999'), prix)

    def test_prix_moyen_recent(self):
        self._bcf(1000)
        self._bcf(1200)
        moyen = prix_moyen_recent_produit(self.company, self.produit.id)
        self.assertEqual(moyen, Decimal('1100.00'))

    def test_endpoint_historique_prix(self):
        self._bcf(1000)
        resp = self.api.get(
            '/api/django/stock/bons-commande-fournisseur/historique-prix/'
            f'?produit={self.produit.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_endpoint_historique_prix_requiert_produit(self):
        resp = self.api.get(
            '/api/django/stock/bons-commande-fournisseur/historique-prix/')
        self.assertEqual(resp.status_code, 400)


class TestRapportAchatsHorsContrat(Xpur13Base):
    def test_rapport_liste_les_depassements(self):
        self._contrat_actif(1000)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-DEPASSE',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=3,
            prix_achat_unitaire=Decimal('1300'))
        rapport = rapport_achats_hors_contrat(self.company)
        self.assertEqual(len(rapport), 1)
        self.assertEqual(rapport[0]['prix_convenu'], Decimal('1000'))
        self.assertEqual(rapport[0]['prix_saisi'], Decimal('1300'))

    def test_rapport_filtre_par_fournisseur(self):
        self._contrat_actif(1000)
        autre_fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Autre Fournisseur X13')
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUTRE-F',
            fournisseur=autre_fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1300'))
        rapport = rapport_achats_hors_contrat(
            self.company, fournisseur_id=self.fournisseur.id)
        self.assertEqual(rapport, [])

    def test_endpoint_rapport(self):
        self._contrat_actif(1000)
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-RPT',
            fournisseur=self.fournisseur,
            statut=BonCommandeFournisseur.Statut.ENVOYE)
        bc.lignes.create(
            produit=self.produit, quantite=1,
            prix_achat_unitaire=Decimal('1500'))
        resp = self.api.get(
            '/api/django/stock/bons-commande-fournisseur/'
            'achats-hors-contrat/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)


class TestBcfCreationSurfacePrixWarning(Xpur13Base):
    def test_creation_bcf_expose_prix_warnings(self):
        self._contrat_actif(1000)
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 2,
                'prix_achat_unitaire': '1300',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIn('prix_warnings', resp.data)
        self.assertEqual(len(resp.data['prix_warnings']), 1)

    def test_creation_bcf_conforme_pas_de_warning(self):
        self._contrat_actif(1000)
        resp = self.api.post('/api/django/stock/bons-commande-fournisseur/', {
            'fournisseur': self.fournisseur.id,
            'lignes': [{
                'produit': self.produit.id, 'quantite': 2,
                'prix_achat_unitaire': '900',
            }],
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertNotIn('prix_warnings', resp.data)
