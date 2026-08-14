"""NTWMS21 — demande de transfert avec workflow d'approbation.

Critère d'acceptation testé : un transfert AU-DESSUS du seuil configuré est
bloqué tant qu'un responsable n'a pas approuvé la demande — et SOUS le seuil
(ou seuil à 0, le défaut), le transfert direct historique reste inchangé.

Run :
    python manage.py test apps.stock.test_ntwms21_demande_transfert -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    AchatsParametres, DemandeTransfert, EmplacementStock, Produit,
    StockEmplacement, TransfertStock,
)
from apps.stock.services import (
    creer_demande_transfert, decider_demande_transfert,
    executer_demande_transfert, transfer_stock, transfert_exige_approbation,
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
        self.magasinier = User.objects.create_user(
            username='ntwms21_magasinier', password='x', role_legacy='normal',
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


class TestSeuilApprobation(Ntwms21Base):
    def test_seuil_par_defaut_zero_ne_bloque_rien(self):
        """Aucune régression : sans seuil, le transfert direct passe."""
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

    def test_au_dessus_du_seuil_le_transfert_direct_est_refuse(self):
        self._seuil('20000')  # 5 × 9 000 = 45 000 > 20 000
        with self.assertRaises(ValueError):
            transfer_stock(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=self.principal.id,
                destination_id=self.camionnette.id, quantite=5)
        self.assertEqual(TransfertStock.objects.count(), 0)


class TestWorkflowApprobation(Ntwms21Base):
    def _demande(self, quantite=5):
        return creer_demande_transfert(
            company=self.company, user=self.magasinier, produit=self.produit,
            quantite=quantite, emplacement_source=self.principal,
            emplacement_destination=self.camionnette,
            motif='Chantier Bouskoura')

    def test_demande_puis_approbation_puis_execution(self):
        self._seuil('20000')
        demande = self._demande()
        self.assertEqual(demande.statut, DemandeTransfert.Statut.DEMANDE)
        self.assertEqual(demande.valeur_estimee, Decimal('45000.00'))

        decider_demande_transfert(demande=demande, user=self.admin,
                                  approuver=True)
        self.assertEqual(demande.statut, DemandeTransfert.Statut.APPROUVE)

        executer_demande_transfert(demande=demande, user=self.admin)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeTransfert.Statut.EXECUTE)
        self.assertIsNotNone(demande.transfert_id)
        # Le stock a réellement bougé (jamais un mécanisme parallèle).
        self.assertEqual(
            StockEmplacement.objects.get(
                produit=self.produit, emplacement=self.camionnette).quantite,
            5)

    def test_demande_non_approuvee_ne_s_execute_pas(self):
        demande = self._demande()
        with self.assertRaises(ValueError):
            executer_demande_transfert(demande=demande, user=self.admin)
        self.assertEqual(TransfertStock.objects.count(), 0)

    def test_demande_rejetee_ne_s_execute_pas(self):
        demande = self._demande()
        decider_demande_transfert(demande=demande, user=self.admin,
                                  approuver=False)
        self.assertEqual(demande.statut, DemandeTransfert.Statut.REJETE)
        with self.assertRaises(ValueError):
            executer_demande_transfert(demande=demande, user=self.admin)

    def test_source_et_destination_identiques_refusees(self):
        with self.assertRaises(ValueError):
            creer_demande_transfert(
                company=self.company, user=self.magasinier,
                produit=self.produit, quantite=2,
                emplacement_source=self.principal,
                emplacement_destination=self.principal)

    def test_demande_deja_decidee_n_est_pas_redecidee(self):
        demande = self._demande()
        decider_demande_transfert(demande=demande, user=self.admin,
                                  approuver=True)
        with self.assertRaises(ValueError):
            decider_demande_transfert(demande=demande, user=self.admin,
                                      approuver=False)


class TestEndpointsDemandeTransfert(Ntwms21Base):
    URL = '/api/django/stock/demandes-transfert/'

    def _creer_via_api(self, client=None):
        return (client or self.api).post(self.URL, {
            'produit': self.produit.id, 'quantite': 5,
            'emplacement_source': self.principal.id,
            'emplacement_destination': self.camionnette.id,
            'motif': 'Chantier',
        }, format='json')

    def test_magasinier_peut_demander(self):
        reponse = self._creer_via_api(auth(self.magasinier))
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(reponse.data['statut'], 'demande')
        self.assertEqual(reponse.data['valeur_estimee'], '45000.00')

    def test_magasinier_ne_peut_pas_approuver(self):
        demande_id = self._creer_via_api().data['id']
        reponse = auth(self.magasinier).post(
            f'{self.URL}{demande_id}/approuver/', {}, format='json')
        self.assertEqual(reponse.status_code, 403)

    def test_responsable_approuve_puis_execute(self):
        self._seuil('20000')
        demande_id = self._creer_via_api().data['id']
        approbation = self.api.post(f'{self.URL}{demande_id}/approuver/', {},
                                    format='json')
        self.assertEqual(approbation.status_code, 200)
        execution = self.api.post(f'{self.URL}{demande_id}/executer/', {},
                                  format='json')
        self.assertEqual(execution.status_code, 200)
        self.assertEqual(execution.data['statut'], 'execute')

    def test_produit_hors_societe_refuse(self):
        produit_autre = Produit.objects.create(
            company=self.autre, nom='Autre', sku='AUT-NTWMS21',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'))
        reponse = self.api.post(self.URL, {
            'produit': produit_autre.id, 'quantite': 1,
            'emplacement_source': self.principal.id,
            'emplacement_destination': self.camionnette.id,
        }, format='json')
        self.assertEqual(reponse.status_code, 400)
