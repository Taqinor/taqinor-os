"""AUD224 — le pipeline WMS décrémente enfin le stock à l'expédition.

Défaut d'origine : picking → emballage → scellage → expédition ne touchait
JAMAIS `Produit.quantite_stock`. La marchandise partait physiquement du quai
sans jamais sortir du système : valorisation, réappro et jusqu'au théorique des
comptages tournants (`generer_comptages_tournants`) restaient faux.

La sortie est posée au point de CONFIRMATION d'expédition (génération de
l'étiquette/du numéro de suivi), via `record_stock_movement` — donc miroir
comptable et alerte seuil-bas inclus —, idempotente, et SANS double décompte
sur le flux chantier (déjà consommé à l'INSTALLÉ par les `StockReservation`).

Run :
    python manage.py test apps.stock.test_aud224_sortie_expedition -v 2
"""
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.stock.models import MouvementStock, Produit
from apps.stock.providers import NoOpProvider
from apps.stock.services import (
    ajouter_ligne_unite_logistique, creer_expedition_transporteur,
    creer_unite_logistique, creer_vague_depuis_besoins,
    generer_etiquette_expedition, reference_sortie_expedition,
    sceller_unite_logistique,
)

User = get_user_model()


def make_company(slug='aud224-co', nom='AUD224 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class Aud224Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud224_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur AUD224', sku='AUD224-1',
            prix_achat=Decimal('700'), prix_vente=Decimal('1000'),
            quantite_stock=10)

    def _colis(self, quantite=3, ligne_picking=None):
        colis = creer_unite_logistique(company=self.company)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=colis, produit=self.produit,
            quantite=quantite, ligne_picking=ligne_picking)
        sceller_unite_logistique(unite=colis, user=self.admin)
        colis.refresh_from_db()
        return colis

    def _expedier(self, colis):
        expedition = creer_expedition_transporteur(
            company=self.company, unite=colis)
        with mock.patch.object(NoOpProvider, 'creer_expedition') as creer:
            creer.return_value = (f'INT-{colis.sscc}', b'')
            generer_etiquette_expedition(
                expedition=expedition, user=self.admin)
        return expedition

    def _stock(self):
        self.produit.refresh_from_db()
        return self.produit.quantite_stock


class TestSortieExpedition(Aud224Base):
    def test_la_confirmation_d_expedition_decremente_le_stock(self):
        colis = self._colis(quantite=3)

        expedition = self._expedier(colis)

        # Avant AUD224 : 10 (le stock ne bougeait jamais sur ce pipeline).
        self.assertEqual(self._stock(), 7)
        mvt = MouvementStock.objects.get(
            company=self.company,
            reference=reference_sortie_expedition(expedition))
        self.assertEqual(mvt.type_mouvement, MouvementStock.TypeMouvement.SORTIE)
        self.assertEqual(mvt.quantite, 3)
        self.assertEqual(mvt.quantite_avant, 10)
        self.assertEqual(mvt.quantite_apres, 7)

    def test_sortie_idempotente(self):
        from apps.stock.services import decrementer_stock_expedition

        colis = self._colis(quantite=3)
        expedition = self._expedier(colis)

        res = decrementer_stock_expedition(
            expedition=expedition, user=self.admin)

        self.assertEqual(res['mouvements'], [])
        self.assertEqual(self._stock(), 7)
        self.assertEqual(
            MouvementStock.objects.filter(
                reference=reference_sortie_expedition(expedition)).count(), 1)

    def test_pas_de_double_decompte_sur_le_flux_chantier(self):
        """Une ligne issue d'une vague rattachée à un chantier est consommée
        à l'INSTALLÉ (StockReservation) : elle n'est pas re-décomptée ici."""
        from apps.installations.models import Installation

        chantier = Installation.objects.create(
            company=self.company, reference='INST-AUD224')
        vague = creer_vague_depuis_besoins(
            company=self.company, user=self.admin,
            besoins=[{'produit_id': self.produit.id, 'quantite': 3,
                      'installation_id': chantier.id}])
        ligne_picking = vague.lignes.first()
        colis = self._colis(quantite=3, ligne_picking=ligne_picking)

        expedition = self._expedier(colis)

        self.assertEqual(self._stock(), 10)
        self.assertFalse(MouvementStock.objects.filter(
            reference=reference_sortie_expedition(expedition)).exists())

    def test_stock_insuffisant_borne_a_zero(self):
        self.produit.quantite_stock = 2
        self.produit.save(update_fields=['quantite_stock'])
        colis = self._colis(quantite=5)

        self._expedier(colis)

        # Plancher ERR80 : on ne sort jamais plus que le stock en main.
        self.assertEqual(self._stock(), 0)

    def test_palette_decompte_le_contenu_de_ses_colis(self):
        palette = creer_unite_logistique(
            company=self.company, type_unite='palette')
        enfant = creer_unite_logistique(
            company=self.company, type_unite='colis', parent=palette)
        ajouter_ligne_unite_logistique(
            company=self.company, unite=enfant, produit=self.produit,
            quantite=4)
        sceller_unite_logistique(unite=enfant, user=self.admin)
        sceller_unite_logistique(unite=palette, user=self.admin)
        palette.refresh_from_db()

        self._expedier(palette)

        self.assertEqual(self._stock(), 6)
