"""AUD223 — tout mouvement de stock passe par `record_stock_movement`.

Le docstring de `_emit_mouvement_stock_enregistre` affirmait que le service
était « le SEUL endroit du dépôt qui crée un MouvementStock » — c'est lui qui
émet ``core.events.mouvement_stock_enregistre`` (miroir comptable d'inventaire
permanent, `compta/receivers.py`) et qui déclenche l'alerte seuil-bas. L'audit
R2 a compté 22 sites de production qui en créaient un EN DIRECT : leurs
mouvements étaient invisibles pour la comptabilité.

Ce module vérifie le COMPORTEMENT (l'événement part) sur les chemins
convertis ; la garde structurelle qui interdit un 23e site vit dans
`scripts/check_mouvement_stock_service.py` (testée par
`scripts/tests/test_check_mouvement_stock_service.py`).

Run :
    python manage.py test apps.stock.test_aud223_mouvement_service_unique -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.events import mouvement_stock_enregistre

from apps.stock.models import (
    BonCommandeFournisseur, EmplacementStock, Fournisseur, InventaireSession,
    LigneBonCommandeFournisseur, LigneInventaire, LigneReceptionFournisseur,
    LigneRetourFournisseur, MouvementStock, Produit, ReceptionFournisseur,
    RetourFournisseur, TransfertStock,
)
from apps.stock import services
from apps.stock.services_consignation import creer_depot_consignation
from apps.stock.services_transfert_deux_temps import (
    expedier_transfert, receptionner_transfert,
)
from apps.stock.services_van_sales import charger_vehicule, decharger_vehicule

User = get_user_model()


def make_company(slug='aud223-co', nom='AUD223 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class CaptureEvenements:
    """Compte les ``mouvement_stock_enregistre`` émis dans le bloc."""

    def __init__(self):
        self.mouvements = []

    def __enter__(self):
        mouvement_stock_enregistre.connect(self._recevoir)
        return self

    def __exit__(self, *exc):
        mouvement_stock_enregistre.disconnect(self._recevoir)
        return False

    def _recevoir(self, sender, instance, company, **kwargs):
        self.mouvements.append(instance)

    def __len__(self):
        return len(self.mouvements)


class Aud223Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='aud223_admin', password='x', role_legacy='admin',
            company=self.company)
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur AUD223')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau AUD223', sku='AUD223-1',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=100)

    def _stock(self):
        self.produit.refresh_from_db()
        return self.produit.quantite_stock


class TestChemInsServices(Aud223Base):
    def test_apply_inventory_count_emet(self):
        with CaptureEvenements() as capture:
            services.apply_inventory_count(
                company=self.company, user=self.user, motif='Annuel',
                lignes=[{'produit': self.produit.id, 'quantite_comptee': 95}])
        self.assertEqual(len(capture), 1)
        self.assertEqual(self._stock(), 95)

    def test_valider_inventaire_session_emet(self):
        session = InventaireSession.objects.create(
            company=self.company, reference='INV-AUD223')
        LigneInventaire.objects.create(
            session=session, produit=self.produit,
            quantite_theorique=100, quantite_comptee=97)
        with CaptureEvenements() as capture:
            services.valider_inventaire_session(session, self.user)
        self.assertEqual(len(capture), 1)
        self.assertEqual(self._stock(), 97)

    def test_apply_retour_fournisseur_emet(self):
        retour = RetourFournisseur.objects.create(
            company=self.company, reference='RET-AUD223',
            fournisseur=self.fournisseur)
        LigneRetourFournisseur.objects.create(
            retour=retour, produit=self.produit, quantite=5, motif='Casse')
        with CaptureEvenements() as capture:
            services.apply_retour_fournisseur(retour, self.user)
        self.assertEqual(len(capture), 1)
        self.assertEqual(self._stock(), 95)

    def test_declarer_rebut_emet_et_garde_son_motif(self):
        with CaptureEvenements() as capture:
            mouvement = services.declarer_rebut(
                company=self.company, produit=self.produit, quantite=3,
                motif=MouvementStock.MotifRebut.CASSE,
                reference='OA-1', note='Casse atelier', user=self.user)
        self.assertEqual(len(capture), 1)
        # Le passe-plat `motif_rebut` du service ne perd pas la colonne.
        self.assertEqual(mouvement.motif_rebut,
                         MouvementStock.MotifRebut.CASSE)
        self.assertEqual(self._stock(), 97)

    def test_rebuter_produit_emet_et_garde_son_motif(self):
        with CaptureEvenements() as capture:
            res = services.rebuter_produit(
                company=self.company, produit=self.produit, quantite=2,
                motif=MouvementStock.MotifRebut.VOL, user=self.user)
        self.assertEqual(len(capture), 1)
        self.assertEqual(res['mouvement'].motif_rebut,
                         MouvementStock.MotifRebut.VOL)
        self.assertEqual(self._stock(), 98)

    def test_dotation_et_restitution_epi_emettent(self):
        with CaptureEvenements() as capture:
            services.decrementer_stock_dotation_epi(
                company=self.company, produit_id=self.produit.id, quantite=4,
                reference='EPI-1', user=self.user)
            self.assertEqual(self._stock(), 96)
            services.reintegrer_stock_restitution_epi(
                company=self.company, produit_id=self.produit.id, quantite=4,
                reference='EPI-1', user=self.user)
        self.assertEqual(len(capture), 2)
        self.assertEqual(self._stock(), 100)

    def test_consignation_emet(self):
        from apps.crm.models import Client  # test seul : jamais en production
        client = Client.objects.create(company=self.company, nom='Client 223')
        with CaptureEvenements() as capture:
            creer_depot_consignation(
                company=self.company, user=self.user, client_id=client.id,
                produit_id=self.produit.id, quantite=6,
                date_depot='2026-09-02')
        self.assertEqual(len(capture), 1)
        self.assertEqual(self._stock(), 94)

    def test_van_sales_charge_et_decharge_emettent(self):
        # `StockVehicule.actif_flotte` est un VRAI FK : l'id inventé « 1 » ne
        # cassait rien pendant le test mais violait la contrainte au
        # `SET CONSTRAINTS ALL IMMEDIATE` du teardown. On monte l'actif de
        # flotte pour de bon (test seul : jamais d'import flotte en production,
        # même convention que le `Client` de test_consignation_emet).
        from apps.flotte.models import ActifFlotte, Vehicule
        vehicule = Vehicule.objects.create(
            company=self.company, immatriculation='AUD223-B-1')
        actif = ActifFlotte.objects.create(
            company=self.company, vehicule=vehicule)
        lignes = [{'produit': self.produit.id, 'quantite': 10}]
        with CaptureEvenements() as capture:
            charger_vehicule(company=self.company, user=self.user,
                             actif_flotte_id=actif.id, lignes=lignes)
            self.assertEqual(self._stock(), 90)
            decharger_vehicule(company=self.company, user=self.user,
                               actif_flotte_id=actif.id, lignes=lignes)
        self.assertEqual(len(capture), 2)
        self.assertEqual(self._stock(), 100)


class TestChemInsReception(Aud223Base):
    def _bcf_et_reception(self, quantite=10):
        bc = BonCommandeFournisseur.objects.create(
            company=self.company, reference='BCF-AUD223',
            fournisseur=self.fournisseur)
        ligne_cmd = LigneBonCommandeFournisseur.objects.create(
            bon_commande=bc, produit=self.produit, quantite=quantite,
            prix_achat_unitaire=Decimal('900'))
        reception = ReceptionFournisseur.objects.create(
            company=self.company, reference='REC-AUD223', bon_commande=bc)
        LigneReceptionFournisseur.objects.create(
            reception=reception, ligne_commande=ligne_cmd,
            produit=self.produit, quantite=quantite)
        return reception

    def test_confirmation_puis_annulation_emettent(self):
        reception = self._bcf_et_reception(10)
        with CaptureEvenements() as capture:
            services.confirm_reception_fournisseur(reception, self.user)
            self.assertEqual(self._stock(), 110)
            services.annuler_reception_confirmee(reception, self.user)
        self.assertEqual(len(capture), 2)
        self.assertEqual(self._stock(), 100)


class TestTransfertDeuxTemps(Aud223Base):
    def test_ecart_de_reception_emet(self):
        principal = services.ensure_emplacements(self.company)
        destination = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt secondaire AUD223', ordre=50)
        transfert = TransfertStock.objects.create(
            company=self.company, reference='TR-AUD223', produit=self.produit,
            source=principal, destination=destination, quantite=10,
            statut=TransfertStock.Statut.DEMANDE)
        expedier_transfert(transfert, self.user)
        with CaptureEvenements() as capture:
            # 8 reçus pour 10 expédiés : l'écart est tracé en ajustement.
            receptionner_transfert(transfert, self.user, quantite_recue=8)
        self.assertEqual(len(capture), 1)
