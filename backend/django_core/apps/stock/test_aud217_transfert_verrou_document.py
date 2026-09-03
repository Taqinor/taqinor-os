"""AUD217 — expédier/réceptionner verrouillent le TRANSFERT lui-même.

Défaut d'origine (NTRET7) : `expedier_transfert` et `receptionner_transfert`
contrôlaient `transfert.statut` sur l'objet Python REÇU EN ARGUMENT, AVANT
d'ouvrir leur transaction et sans jamais verrouiller la ligne. Deux requêtes
concurrentes sur le même transfert détiennent chacune leur propre copie, lue
avant que l'autre n'ait committé : les deux lisent `DEMANDE` (ou `EXPEDIE`),
les deux passent le contrôle, et le traitement s'applique DEUX FOIS — la
source est décrémentée deux fois pour un seul camion, ou la destination
créditée deux fois pour une seule arrivée.

Distinct d'AUD216/R2-01 : là l'objet non verrouillé est la LIGNE DE STOCK, ici
c'est le DOCUMENT (son statut).

Correctif : re-fetch `TransfertStock.objects.select_for_update().get(pk=...)`
en tout début du bloc atomique, AVANT le contrôle de statut — patron déjà
utilisé par `promotions.services.debiter_carte_cadeau`.

Les tests reproduisent la course SANS concurrence réelle, avec le patron du
dépôt (`test_aud219_picking_verrou`) : deux copies Python distinctes de la
même ligne, la seconde étant STALE au moment de son traitement.

Run :
    python manage.py test apps.stock.test_aud217_transfert_verrou_document -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, StockEmplacement, TransfertStock,
)
from apps.stock.services_transfert_deux_temps import (
    creer_demande_transfert, expedier_transfert, receptionner_transfert,
)
from authentication.models import Company

User = get_user_model()


class Aud217Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD217 Co', slug='aud217-co')
        self.user = User.objects.create_user(
            username='aud217_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUD217', sku='AUD217-1',
            prix_achat=Decimal('4000'), prix_vente=Decimal('6000'),
            quantite_stock=100)
        EmplacementStock.objects.create(
            company=self.company, nom='Dépôt AUD217', is_principal=True)
        self.source = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette AUD217')
        self.destination = EmplacementStock.objects.create(
            company=self.company, nom='Agence AUD217')
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.source, quantite=30)

        self.transfert = creer_demande_transfert(
            company=self.company, user=self.user, produit_id=self.produit.id,
            source_id=self.source.id, destination_id=self.destination.id,
            quantite=10)

    def _copie(self):
        """Ce que détient une seconde requête HTTP : sa propre copie mémoire."""
        return TransfertStock.objects.get(pk=self.transfert.pk)

    def _quantite(self, emplacement):
        ligne = StockEmplacement.objects.filter(
            produit=self.produit, emplacement=emplacement).first()
        return 0 if ligne is None else ligne.quantite


class Aud217ExpeditionConcurrenteTests(Aud217Base):
    def test_la_seconde_expedition_est_refusee(self):
        requete_a = self._copie()
        requete_b = self._copie()   # lue AVANT l'expédition de A : stale

        expedier_transfert(requete_a, self.user)
        with self.assertRaises(ValueError) as ctx:
            expedier_transfert(requete_b, self.user)

        self.assertIn('DEMANDÉ', str(ctx.exception))

    def test_la_source_nest_decrementee_quune_fois(self):
        expedier_transfert(self._copie(), self.user)
        with self.assertRaises(ValueError):
            expedier_transfert(self._copie(), self.user)

        # 30 − 10 = 20. Avant AUD217 : 10 (double décrément pour un camion).
        self.assertEqual(self._quantite(self.source), 20)

    def test_le_statut_reste_expedie_une_seule_fois(self):
        expedier_transfert(self._copie(), self.user)
        with self.assertRaises(ValueError):
            expedier_transfert(self._copie(), self.user)

        self.transfert.refresh_from_db()
        self.assertEqual(self.transfert.statut, TransfertStock.Statut.EXPEDIE)


class Aud217ReceptionConcurrenteTests(Aud217Base):
    def setUp(self):
        super().setUp()
        expedier_transfert(self.transfert, self.user)

    def test_la_seconde_reception_est_refusee(self):
        requete_a = self._copie()
        requete_b = self._copie()   # stale

        receptionner_transfert(requete_a, self.user, quantite_recue=10)
        with self.assertRaises(ValueError) as ctx:
            receptionner_transfert(requete_b, self.user, quantite_recue=10)

        self.assertIn('EXPÉDIÉ', str(ctx.exception))

    def test_la_destination_nest_creditee_quune_fois(self):
        receptionner_transfert(self._copie(), self.user, quantite_recue=10)
        with self.assertRaises(ValueError):
            receptionner_transfert(self._copie(), self.user, quantite_recue=10)

        # Avant AUD217 : 20 (double crédit pour une seule arrivée).
        self.assertEqual(self._quantite(self.destination), 10)

    def test_l_ajustement_d_ecart_nest_ecrit_quune_fois(self):
        receptionner_transfert(self._copie(), self.user, quantite_recue=8)
        with self.assertRaises(ValueError):
            receptionner_transfert(self._copie(), self.user, quantite_recue=8)

        ajustements = MouvementStock.objects.filter(
            produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT,
            reference=self.transfert.reference)
        self.assertEqual(ajustements.count(), 1)
        self.produit.refresh_from_db()
        # Écart de −2 appliqué UNE fois : 100 − 2 = 98 (jamais 96).
        self.assertEqual(self.produit.quantite_stock, 98)


class Aud217CheminNominalTests(Aud217Base):
    """Le cycle normal reste inchangé (aucune régression NTRET7)."""

    def test_le_cycle_complet_passe(self):
        transfert = expedier_transfert(self.transfert, self.user)
        self.assertEqual(transfert.statut, TransfertStock.Statut.EXPEDIE)
        self.assertEqual(self._quantite(self.source), 20)

        transfert = receptionner_transfert(
            transfert, self.user, quantite_recue=10)
        self.assertEqual(transfert.statut, TransfertStock.Statut.RECU)
        self.assertEqual(transfert.quantite_recue, 10)
        self.assertEqual(self._quantite(self.destination), 10)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 100)

    def test_reception_avant_expedition_toujours_refusee(self):
        autre = creer_demande_transfert(
            company=self.company, user=self.user, produit_id=self.produit.id,
            source_id=self.source.id, destination_id=self.destination.id,
            quantite=1)
        with self.assertRaises(ValueError):
            receptionner_transfert(autre, self.user, quantite_recue=1)

    def test_quantite_recue_invalide_toujours_refusee(self):
        expedier_transfert(self.transfert, self.user)
        for invalide in ('abc', -1):
            with self.assertRaises(ValueError):
                receptionner_transfert(
                    self._copie(), self.user, quantite_recue=invalide)
