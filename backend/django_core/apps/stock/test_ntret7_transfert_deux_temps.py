"""NTRET7 — transferts inter-magasins en DEUX TEMPS (expédition / réception).

Critère d'acceptation testé : un transfert traverse les TROIS étapes, l'écart
de réception est JOURNALISÉ et la destination n'incrémente QUE le REÇU RÉEL —
et le bon de transfert PDF est généré.

NOTE DE DÉDOUBLONNAGE. ``installations.DemandeTransfert`` (FG325) est le
workflow d'APPROBATION (demandé → approuvé/refusé → exécuté) et NTWMS21 son
seuil : il ne modélise PAS le délai camion. NTRET7 est le cycle PHYSIQUE
(départ / arrivée / écart), porté par ``stock.TransfertStock`` lui-même comme
la tâche le demande. Les deux sont complémentaires, pas concurrents.

Run :
    python manage.py test apps.stock.test_ntret7_transfert_deux_temps -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, tag
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, StockEmplacement,
    TransfertStock,
)
from apps.stock.services import transfer_stock
from apps.stock.services_transfert_deux_temps import (
    creer_demande_transfert, expedier_transfert, receptionner_transfert,
    render_bon_transfert_html,
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


class Ntret7Base(TestCase):
    def setUp(self):
        self.company = make_company('ntret7-co', 'NTRET7 Co')
        self.autre = make_company('ntret7-autre', 'NTRET7 Autre')
        self.admin = User.objects.create_user(
            username='ntret7_admin', password='x', role_legacy='admin',
            company=self.company)
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt NTRET7', is_principal=True)
        self.magasin_a = EmplacementStock.objects.create(
            company=self.company, nom='Magasin A NTRET7')
        self.magasin_b = EmplacementStock.objects.create(
            company=self.company, nom='Magasin B NTRET7')
        self.produit = Produit.objects.create(
            company=self.company, nom='Disjoncteur 32 A', sku='DJ32-NTRET7',
            prix_achat=Decimal('120'), prix_vente=Decimal('180'),
            quantite_stock=100)
        self.se_a = StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.magasin_a, quantite=40)

    def _demande(self, quantite=10):
        return creer_demande_transfert(
            company=self.company, user=self.admin,
            produit_id=self.produit.id, source_id=self.magasin_a.id,
            destination_id=self.magasin_b.id, quantite=quantite)


class Ntret7CycleTests(Ntret7Base):
    def test_les_trois_etapes_sans_ecart(self):
        transfert = self._demande(quantite=10)
        self.assertEqual(transfert.statut, TransfertStock.Statut.DEMANDE)
        self.assertTrue(transfert.reference.startswith('TRF-'))
        # Étape 1 : rien n'a bougé.
        self.se_a.refresh_from_db()
        self.assertEqual(self.se_a.quantite, 40)

        expedier_transfert(transfert, self.admin)
        transfert.refresh_from_db()
        self.se_a.refresh_from_db()
        self.assertEqual(transfert.statut, TransfertStock.Statut.EXPEDIE)
        self.assertEqual(self.se_a.quantite, 30)
        self.assertFalse(StockEmplacement.objects.filter(
            produit=self.produit, emplacement=self.magasin_b).exists())

        receptionner_transfert(transfert, self.admin, quantite_recue=10)
        transfert.refresh_from_db()
        self.assertEqual(transfert.statut, TransfertStock.Statut.RECU)
        self.assertEqual(transfert.ecart_reception, 0)
        self.assertEqual(StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.magasin_b).quantite, 10)

    def test_un_ecart_nincremente_que_le_recu_reel_et_est_journalise(self):
        transfert = self._demande(quantite=10)
        expedier_transfert(transfert, self.admin)
        receptionner_transfert(transfert, self.admin, quantite_recue=8)

        transfert.refresh_from_db()
        self.assertEqual(transfert.quantite_recue, 8)
        self.assertEqual(transfert.ecart_reception, -2)
        # La destination reçoit 8, jamais 10.
        self.assertEqual(StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.magasin_b).quantite, 8)
        # L'écart est TRACÉ (ajustement motivé) et noté sur le document.
        ajustement = MouvementStock.objects.get(
            company=self.company,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT)
        self.assertEqual(ajustement.quantite, 2)
        self.assertIn('Écart de réception', ajustement.note)
        self.assertIn('Écart de réception', transfert.note)
        # Le total société baisse de 2 (les 2 unités ont réellement disparu).
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 98)

    def test_un_surplus_est_journalise_de_la_meme_facon(self):
        transfert = self._demande(quantite=5)
        expedier_transfert(transfert, self.admin)
        receptionner_transfert(transfert, self.admin, quantite_recue=6)

        transfert.refresh_from_db()
        self.assertEqual(transfert.ecart_reception, 1)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 101)

    def test_lordre_des_etapes_est_impose(self):
        transfert = self._demande(quantite=5)
        with self.assertRaises(ValueError):
            receptionner_transfert(transfert, self.admin, quantite_recue=5)

        expedier_transfert(transfert, self.admin)
        transfert.refresh_from_db()
        with self.assertRaises(ValueError):
            expedier_transfert(transfert, self.admin)

        receptionner_transfert(transfert, self.admin, quantite_recue=5)
        transfert.refresh_from_db()
        with self.assertRaises(ValueError):
            receptionner_transfert(transfert, self.admin, quantite_recue=5)

    def test_expedier_plus_que_le_stock_source_est_refuse(self):
        transfert = self._demande(quantite=999)
        with self.assertRaises(ValueError):
            expedier_transfert(transfert, self.admin)

    def test_quantite_recue_negative_est_refusee(self):
        transfert = self._demande(quantite=5)
        expedier_transfert(transfert, self.admin)
        with self.assertRaises(ValueError):
            receptionner_transfert(transfert, self.admin, quantite_recue=-1)

    def test_le_transfert_direct_historique_reste_inchange(self):
        direct = transfer_stock(
            company=self.company, user=self.admin,
            produit_id=self.produit.id, source_id=self.magasin_a.id,
            destination_id=self.magasin_b.id, quantite=5)
        # Il naît TERMINÉ, sans référence de bon : comportement N15 intact.
        self.assertEqual(direct.statut, TransfertStock.Statut.RECU)
        self.assertEqual(direct.reference, '')
        self.assertIsNone(direct.quantite_recue)
        self.se_a.refresh_from_db()
        self.assertEqual(self.se_a.quantite, 35)
        self.assertEqual(StockEmplacement.objects.get(
            produit=self.produit, emplacement=self.magasin_b).quantite, 5)

    def test_source_egale_destination_est_refusee(self):
        with self.assertRaises(ValueError):
            creer_demande_transfert(
                company=self.company, user=self.admin,
                produit_id=self.produit.id, source_id=self.magasin_a.id,
                destination_id=self.magasin_a.id, quantite=1)

    def test_un_produit_dune_autre_societe_est_introuvable(self):
        autre_produit = Produit.objects.create(
            company=self.autre, nom='Voisin', sku='VOISIN-RET7',
            prix_achat=Decimal('1'), prix_vente=Decimal('2'),
            quantite_stock=10)
        with self.assertRaises(ValueError):
            creer_demande_transfert(
                company=self.company, user=self.admin,
                produit_id=autre_produit.id, source_id=self.magasin_a.id,
                destination_id=self.magasin_b.id, quantite=1)


class Ntret7BonTests(Ntret7Base):
    def test_le_bon_porte_sku_quantite_attendue_et_code_barres(self):
        transfert = self._demande(quantite=12)
        html = render_bon_transfert_html(transfert)

        self.assertIn('DJ32-NTRET7', html)
        self.assertIn('>12<', html)
        self.assertIn(transfert.reference, html)
        self.assertIn('<svg', html)  # code-barres du bon
        self.assertNotIn('TAQINOR', html.upper())


class Ntret7ApiTests(Ntret7Base):
    URL = '/api/django/stock/transferts/'

    def test_le_cycle_complet_par_api(self):
        api = auth(self.admin)
        demande = api.post(f'{self.URL}demander/', {
            'produit': self.produit.id, 'source': self.magasin_a.id,
            'destination': self.magasin_b.id, 'quantite': 7,
        }, format='json')
        self.assertEqual(demande.status_code, 201)
        transfert_id = demande.data['id']

        expedie = api.post(f'{self.URL}{transfert_id}/expedier/')
        self.assertEqual(expedie.status_code, 200)
        self.assertEqual(expedie.data['statut'], 'expedie')

        recu = api.post(f'{self.URL}{transfert_id}/receptionner/',
                        {'quantite_recue': 6}, format='json')
        self.assertEqual(recu.status_code, 200)
        self.assertEqual(recu.data['statut'], 'recu')
        self.assertEqual(recu.data['ecart_reception'], -1)

    def test_receptionner_avant_expedition_renvoie_400(self):
        transfert = self._demande(quantite=3)
        res = auth(self.admin).post(
            f'{self.URL}{transfert.id}/receptionner/',
            {'quantite_recue': 3}, format='json')
        self.assertEqual(res.status_code, 400)

    def test_le_filtre_statut_est_applique(self):
        self._demande(quantite=2)
        res = auth(self.admin).get(self.URL, {'statut': 'demande'})
        self.assertEqual(len(res.data.get('results', res.data)), 1)

    def test_endpoint_refuse_lanonyme(self):
        transfert = self._demande(quantite=1)
        self.assertEqual(APIClient().post(
            f'{self.URL}{transfert.id}/expedier/').status_code, 401)


@tag('pdf')
class Ntret7PdfTests(Ntret7Base):
    """Rendu WeasyPrint RÉEL — hors palier rapide (étiquette `pdf`)."""

    def test_le_bon_pdf_est_servi(self):
        transfert = self._demande(quantite=4)
        res = auth(self.admin).get(
            f'/api/django/stock/transferts/{transfert.id}/bon-pdf/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'application/pdf')
        self.assertTrue(res.content.startswith(b'%PDF'))
