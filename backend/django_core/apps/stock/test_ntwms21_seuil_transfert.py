"""NTWMS21 — seuil d'approbation des transferts de valeur.

Critère d'acceptation testé : un transfert AU-DESSUS du seuil configuré est
bloqué tant qu'un responsable n'a pas approuvé la demande — et SOUS le seuil
(ou seuil à 0, le défaut de toutes les sociétés), le transfert direct
historique reste strictement inchangé.

DÉCOUVERTE DE LANE : le workflow demande → approbation → exécution EXISTE
DÉJÀ (`installations.DemandeTransfert`, FG325, qui exécute le mouvement en
appelant `stock.services.transfer_stock`). NTWMS21 n'en construit donc pas un
second : il ajoute le SEUIL qui manquait, et cette suite vérifie qu'une
demande approuvée traverse bien la garde.

Run :
    python manage.py test apps.stock.test_ntwms21_seuil_transfert -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    AchatsParametres, EmplacementStock, Produit, StockEmplacement,
    TransfertStock,
)
from apps.stock.services import (
    demande_transfert_approuvee_existe, transfer_stock,
    transfert_exige_approbation, valeur_transfert,
)

User = get_user_model()


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms21Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms21-co', 'NTWMS21 Co')
        self.autre = make_company('ntwms21-autre', 'NTWMS21 Autre')
        self.admin = User.objects.create_user(
            username='ntwms21_admin', password='x', role_legacy='admin',
            company=self.company)
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTWMS21', is_principal=True)
        self.camionnette = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette NTWMS21')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 8kW', sku='OND8-NTWMS21',
            prix_achat=Decimal('9000'), prix_vente=Decimal('12000'),
            quantite_stock=10)
        self.api = auth(self.admin)

    def _seuil(self, valeur):
        parametres = AchatsParametres.for_company(self.company)
        parametres.seuil_approbation_transfert = Decimal(valeur)
        parametres.save(update_fields=['seuil_approbation_transfert'])

    def _demande(self, quantite=5, statut='approuve'):
        """Demande FG325 (le workflow EXISTANT), atteinte par l'accesseur
        inverse de notre propre string-FK — jamais un import de ses models."""
        modele = EmplacementStock._meta.get_field(
            'installations_demandes_transfert_sortantes').related_model
        return modele.objects.create(
            company=self.company, reference=f'DTR-NTWMS21-{quantite}',
            produit=self.produit, source=self.principal,
            destination=self.camionnette, quantite=quantite, statut=statut)


class TestSeuilApprobation(Ntwms21Base):
    def test_valeur_du_transfert(self):
        self.assertEqual(valeur_transfert(self.produit, 5),
                         Decimal('45000.00'))

    def test_seuil_par_defaut_zero_ne_bloque_rien(self):
        """Aucune régression : sans seuil configuré, le direct passe."""
        self.assertFalse(
            transfert_exige_approbation(self.company, self.produit, 5))
        transfert = transfer_stock(
            company=self.company, user=self.admin,
            produit_id=self.produit.id, source_id=self.principal.id,
            destination_id=self.camionnette.id, quantite=5)
        self.assertIsInstance(transfert, TransfertStock)

    def test_sous_le_seuil_le_transfert_direct_reste_inchange(self):
        self._seuil('50000')  # 5 × 9 000 = 45 000 < 50 000
        transfert = transfer_stock(
            company=self.company, user=self.admin,
            produit_id=self.produit.id, source_id=self.principal.id,
            destination_id=self.camionnette.id, quantite=5)
        self.assertIsInstance(transfert, TransfertStock)
        self.assertEqual(
            StockEmplacement.objects.get(
                produit=self.produit, emplacement=self.camionnette).quantite,
            5)

    def test_au_dessus_du_seuil_le_transfert_direct_est_refuse(self):
        self._seuil('20000')  # 45 000 > 20 000
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=self.principal.id,
                destination_id=self.camionnette.id, quantite=5)
        self.assertEqual(TransfertStock.objects.count(), 0)

    def test_message_oriente_vers_la_demande(self):
        self._seuil('20000')
        with self.assertRaises(ValueError) as contexte:
            transfer_stock(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=self.principal.id,
                destination_id=self.camionnette.id, quantite=5)
        self.assertIn('demande de transfert', str(contexte.exception))


class TestDemandeApprouveeTraverseLaGarde(Ntwms21Base):
    def test_demande_approuvee_laisse_passer_le_transfert(self):
        """La régression la plus dangereuse : sans cette exemption, une
        demande FG325 approuvée devenait inexécutable."""
        self._seuil('20000')
        self._demande(quantite=5, statut='approuve')

        self.assertTrue(demande_transfert_approuvee_existe(
            self.company, produit_id=self.produit.id,
            source_id=self.principal.id,
            destination_id=self.camionnette.id, quantite=5))
        transfert = transfer_stock(
            company=self.company, user=self.admin,
            produit_id=self.produit.id, source_id=self.principal.id,
            destination_id=self.camionnette.id, quantite=5)
        self.assertIsInstance(transfert, TransfertStock)

    def test_demande_seulement_demandee_ne_suffit_pas(self):
        self._seuil('20000')
        self._demande(quantite=5, statut='demande')
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=self.principal.id,
                destination_id=self.camionnette.id, quantite=5)

    def test_demande_pour_une_autre_quantite_ne_couvre_pas(self):
        self._seuil('20000')
        self._demande(quantite=3, statut='approuve')
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=self.principal.id,
                destination_id=self.camionnette.id, quantite=5)

    def test_seuil_isole_par_societe(self):
        self._seuil('20000')
        self.assertFalse(
            transfert_exige_approbation(self.autre, self.produit, 5))


class TestEndpointSeuil(Ntwms21Base):
    def test_transfert_api_refuse_au_dessus_du_seuil(self):
        self._seuil('20000')
        reponse = self.api.post('/api/django/stock/transferts/', {
            'produit': self.produit.id, 'source': self.principal.id,
            'destination': self.camionnette.id, 'quantite': 5,
        }, format='json')
        self.assertIn(reponse.status_code, (400, 409))
        self.assertEqual(TransfertStock.objects.count(), 0)

    def test_transfert_api_passe_sous_le_seuil(self):
        self._seuil('100000')
        reponse = self.api.post('/api/django/stock/transferts/', {
            'produit': self.produit.id, 'source': self.principal.id,
            'destination': self.camionnette.id, 'quantite': 5,
        }, format='json')
        self.assertIn(reponse.status_code, (200, 201))
