"""AUD216 — les mutations de `Produit.quantite_stock` prennent un verrou de ligne.

Défaut d'origine : 9 sites lisaient `quantite_stock` par `refresh_from_db()`
(ou par un sélecteur, ou par un `get_or_create` non verrouillé) puis écrivaient
une valeur absolue dérivée de cette lecture — alors que le patron ERR24
(`Produit.objects.select_for_update().get(...)`) existait déjà JUSTE À CÔTÉ
dans le même fichier (`apply_retour_fournisseur`,
`views/bon_commande_fournisseur.py`). Deux transactions concurrentes sur le
même produit lisaient donc la même valeur et la seconde écrasait la première :
lost update — de la marchandise vendue ou reçue disparaissait du registre.

COMMENT CES TESTS PROUVENT LA CORRECTION SANS CONCURRENCE RÉELLE
----------------------------------------------------------------
Le patron du dépôt (cf. `test_aud219_picking_verrou`) : on fabrique une copie
Python PÉRIMÉE du produit — exactement ce que détient une seconde requête HTTP
qui a lu avant le commit de la première — et on la passe au service. Avant
AUD216 le service faisait confiance à cette copie (`refresh_from_db` sur un
objet déjà relu ne change rien quand la valeur a bougé APRÈS) ; désormais il
re-lit la ligne SOUS VERROU depuis la base, donc l'arithmétique repart de la
valeur RÉELLE.

Run :
    python manage.py test apps.stock.test_aud216_verrou_produit -v 2
"""
import inspect
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase

from apps.stock import services as stock_services
from apps.stock.models import (
    EmplacementStock, MouvementStock, Produit, StockEmplacement,
    TransfertStock,
)
from apps.stock.services_transfert_deux_temps import (
    creer_demande_transfert, expedier_transfert, receptionner_transfert,
)
from authentication.models import Company

User = get_user_model()


class Aud216Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD216 Co', slug='aud216-co')
        self.user = User.objects.create_user(
            username='aud216_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau AUD216', sku='AUD216-1',
            prix_achat=Decimal('900'), prix_vente=Decimal('1400'),
            quantite_stock=100)


class Aud216ServiceVerrouTests(Aud216Base):
    """Le thin service `verrouiller_produit` est le point d'entrée cross-app."""

    def test_le_service_existe_et_renvoie_le_produit(self):
        with transaction.atomic():
            produit = stock_services.verrouiller_produit(self.produit.pk)
        self.assertEqual(produit.pk, self.produit.pk)

    def test_le_service_relit_la_valeur_reelle_pas_la_copie_perimee(self):
        perimee = Produit.objects.get(pk=self.produit.pk)   # copie « requête 2 »
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=40)

        self.assertEqual(perimee.quantite_stock, 100)       # encore périmée
        with transaction.atomic():
            frais = stock_services.verrouiller_produit(perimee.pk)
        self.assertEqual(frais.quantite_stock, 40)

    def test_produit_inconnu_leve_doesnotexist(self):
        with self.assertRaises(Produit.DoesNotExist):
            with transaction.atomic():
                stock_services.verrouiller_produit(10 ** 9)


class Aud216RecordStockMovementTests(Aud216Base):
    """`record_stock_movement` verrouille lui-même (filet, pas alibi)."""

    def test_le_parametre_de_verrou_existe_et_est_actif_par_defaut(self):
        signature = inspect.signature(stock_services.record_stock_movement)
        self.assertIn('verrouiller_produit', signature.parameters)
        self.assertIs(
            signature.parameters['verrouiller_produit'].default, True)

    def test_ecrit_normalement_dans_une_transaction(self):
        with transaction.atomic():
            mouvement = stock_services.record_stock_movement(
                company=self.company, produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=10, quantite_avant=100, quantite_apres=90,
                reference='AUD216-T1', note='test', created_by=self.user)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 90)
        self.assertEqual(mouvement.quantite_apres, 90)

    def _mouvement(self, reference, **extra):
        """Compte les `select_for_update()` émis SUR LE MANAGER `Produit` seul.

        On patche l'INSTANCE du manager (jamais la classe `Manager`, partagée
        par tous les modèles) : le compteur ne peut donc pas capter le verrou
        d'un autre modèle et rendre l'assertion creuse.
        """
        appels = {'n': 0}
        manager = Produit.objects
        original = manager.select_for_update

        def _compter(*args, **kwargs):
            appels['n'] += 1
            return original(*args, **kwargs)

        manager.select_for_update = _compter
        try:
            with transaction.atomic():
                stock_services.record_stock_movement(
                    company=self.company, produit=self.produit,
                    type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                    quantite=5, quantite_avant=100, quantite_apres=95,
                    reference=reference, note='test', created_by=self.user,
                    **extra)
        finally:
            del manager.select_for_update
        return appels['n']

    def test_le_verrou_est_pris_par_le_service_lui_meme(self):
        self.assertGreaterEqual(self._mouvement('AUD216-T2'), 1)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 95)

    def test_le_verrou_reste_desactivable_explicitement(self):
        """Échappatoire nommée : un appelant qui détient déjà le verrou (ou
        écrit hors transaction) peut le dire — et rien d'autre ne change."""
        self.assertEqual(
            self._mouvement('AUD216-T3', verrouiller_produit=False), 0)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 95)


class Aud216TransfertDeuxTempsTests(Aud216Base):
    """`receptionner_transfert` : produit ET ligne d'emplacement verrouillés."""

    def setUp(self):
        super().setUp()
        self.principal = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt AUD216', is_principal=True)
        self.source = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette AUD216')
        self.destination = EmplacementStock.objects.create(
            company=self.company, nom='Agence AUD216')
        StockEmplacement.objects.create(
            company=self.company, produit=self.produit,
            emplacement=self.source, quantite=20)

    def _transfert(self, quantite=5):
        transfert = creer_demande_transfert(
            company=self.company, user=self.user, produit_id=self.produit.id,
            source_id=self.source.id, destination_id=self.destination.id,
            quantite=quantite)
        return expedier_transfert(transfert, self.user)

    def test_reception_avec_ecart_repart_du_stock_reel(self):
        transfert = self._transfert(quantite=5)
        # Une transaction concurrente consomme du stock ENTRE l'expédition et
        # la réception : la copie portée par `transfert.produit` est périmée.
        Produit.objects.filter(pk=self.produit.pk).update(quantite_stock=60)

        receptionner_transfert(transfert, self.user, quantite_recue=3)

        self.produit.refresh_from_db()
        # Écart de -2 appliqué sur 60 (valeur RÉELLE), jamais sur 100 (périmée).
        self.assertEqual(self.produit.quantite_stock, 58)
        ajustement = MouvementStock.objects.filter(
            produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.AJUSTEMENT).first()
        self.assertIsNotNone(ajustement)
        self.assertEqual(ajustement.quantite_avant, 60)
        self.assertEqual(ajustement.quantite_apres, 58)

    def test_reception_sans_ecart_ne_touche_pas_le_total(self):
        transfert = self._transfert(quantite=5)
        receptionner_transfert(transfert, self.user, quantite_recue=5)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 100)
        self.assertEqual(
            StockEmplacement.objects.get(
                produit=self.produit, emplacement=self.destination).quantite, 5)
        transfert.refresh_from_db()
        self.assertEqual(transfert.statut, TransfertStock.Statut.RECU)
