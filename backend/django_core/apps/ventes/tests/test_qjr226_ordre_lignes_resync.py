# -*- coding: utf-8 -*-
"""QJR226 — les lignes PANNEAU **et** BATTERIE créées par la resynchro
reçoivent un ``ordre``.

TEST ROUGE D'ABORD : ``domain/resynchronisation`` créait ces DEUX lignes (ce
n'est pas une ligne, ce sont deux — correction R3) sans ``ordre``. Elles
prenaient donc le défaut modèle ``0`` et, sous ``ordering = ['ordre', 'id']``,
passaient DEVANT toute ligne d'ordre ≥ 1 — typiquement en tête d'un devis écrit
à l'écran, dont les lignes sont numérotées 1..n. C'est le mode de défaillance
PVORD que la justification de l'écrivain unique nomme explicitement.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr226_ordre_lignes_resync -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.resynchronisation import _ordre_suivant
from apps.ventes.models import Devis
from apps.ventes.services import sync_devis_from_layout
from apps.ventes.tests.test_pv18_sync_layout import layout, make_company

User = get_user_model()

PANNEAU = 'Panneau Jinko 550W'
RESEAU = 'Onduleur réseau Huawei 5kW'
HYBRIDE = 'Onduleur hybride Deye 5kW'
BATTERIE = 'Batterie Dyness 5 kWh'
INSTALLATION = 'Installation'


class _Base(TestCase):

    def setUp(self):
        self.company = make_company('qjr226-co')
        self.user = User.objects.create_user(
            username='qjr226user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR226')
        self.produits = {}
        for nom, sku, prix in (
                (PANNEAU, 'PAN', '1100'),
                (RESEAU, 'ONDR', '14000'),
                (HYBRIDE, 'ONDH', '17000'),
                (BATTERIE, 'BAT', '16000'),
                (INSTALLATION, 'INST', '4800')):
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku='QJR226-%s' % sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=200)
        self.compteur = 0

    def _devis(self, lignes):
        """Un devis dont les lignes sont numérotées 1..n — comme l'écran les
        écrit (``ordre=index``)."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR226-%s' % self.compteur,
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user, taux_tva=Decimal('20'))
        for index, (nom, qte) in enumerate(lignes, start=1):
            devis.lignes.create(
                produit=self.produits[nom], designation=nom,
                quantite=Decimal(str(qte)),
                prix_unitaire=self.produits[nom].prix_vente,
                remise=Decimal('0'), ordre=index)
        return devis

    def _designations_ordonnees(self, devis):
        return [li.designation for li in devis.lignes.all()]


class LigneBatterieCreee(_Base):

    def test_la_batterie_creee_suit_les_lignes_existantes(self):
        """LE ROUGE (moitié batterie) : elle sortait EN TÊTE."""
        devis = self._devis([(PANNEAU, 12), (HYBRIDE, 1), (INSTALLATION, 1)])
        sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='avec_batterie'),
            user=self.user)

        ordonnees = self._designations_ordonnees(devis)
        self.assertIn(BATTERIE, ordonnees, ordonnees)
        self.assertNotEqual(ordonnees[0], BATTERIE, ordonnees)
        batterie = devis.lignes.get(designation=BATTERIE)
        self.assertGreaterEqual(int(batterie.ordre), 4)


class LignePanneauCreee(_Base):

    def test_le_panneau_cree_suit_les_lignes_existantes(self):
        """LE ROUGE (moitié panneau) : elle sortait EN TÊTE aussi."""
        devis = self._devis([(RESEAU, 1), (INSTALLATION, 1)])
        sync_devis_from_layout(devis, layout(panels=12, kwc=6.6),
                               user=self.user)

        ordonnees = self._designations_ordonnees(devis)
        panneaux = [d for d in ordonnees if d.startswith('Panneau')]
        self.assertTrue(panneaux, ordonnees)
        self.assertNotEqual(ordonnees[0], panneaux[0], ordonnees)
        ligne = devis.lignes.get(designation=panneaux[0])
        self.assertGreaterEqual(int(ligne.ordre), 3)


class OrdreSuivant(_Base):
    """La règle elle-même — une seule définition, partagée par les créateurs."""

    def test_max_plus_un(self):
        devis = self._devis([(PANNEAU, 12), (RESEAU, 1), (INSTALLATION, 1)])
        self.assertEqual(_ordre_suivant(devis), 4)

    def test_devis_vide_commence_a_un(self):
        devis = self._devis([])
        self.assertEqual(_ordre_suivant(devis), 1)

    def test_ignore_un_cache_de_prefetch_perime(self):
        """Deux créations d'affilée ne peuvent pas atterrir au MÊME ordre : le
        calcul passe par la base, jamais par la relation préchargée."""
        devis = self._devis([(PANNEAU, 12)])
        prefetche = Devis.objects.prefetch_related('lignes').get(pk=devis.pk)
        list(prefetche.lignes.all())  # amorce le cache
        prefetche.lignes.create(
            produit=self.produits[RESEAU], designation=RESEAU,
            quantite=Decimal('1'),
            prix_unitaire=self.produits[RESEAU].prix_vente,
            remise=Decimal('0'), ordre=2)
        self.assertEqual(_ordre_suivant(prefetche), 3)
