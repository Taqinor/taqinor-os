"""Revue critique 25/08/2026, findings #5a et #5b — les deux mensonges de
l'échelle des paliers de batterie (``apps.ventes.dimensionnement``).

5a. BASES DE PRIX MÉLANGÉES. Le palier retenu affichait le TTC du DEVIS
    (remise appliquée) et les autres la composition CATALOGUE brute : sur un
    devis remisé, l'écart entre deux pilules était faux. Le prix de CHAQUE
    palier passe désormais par :func:`facteur_remise_du_devis`, la même chaîne
    de remise que ``quote_engine.builder`` (remise de ligne puis remise
    globale).

5b. ``retenu`` DÉPAREILLÉ. Le palier « Retenu pour ce devis » était marqué sur
    la capacité de l'OPTIMUM DU MOTEUR, pas sur celle des LIGNES vendues : la
    pilule affichait le prix d'une autre capacité. Il est désormais marqué
    d'après :func:`capacite_batterie_des_lignes` — et, sans correspondance
    exacte, AUCUN palier n'est marqué.

Ces tests portent sur les deux lectures PURES (aucun PVGIS, aucun catalogue à
composer) : c'est là que vivait la cause.
"""
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.dimensionnement import (
    capacite_batterie_des_lignes,
    facteur_remise_du_devis,
)
from apps.ventes.models import Devis, LigneDevis


class _BaseDevis(TestCase):
    """Un devis résidentiel minimal — panneaux, onduleur, batteries."""

    slug = 'lpalier'

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Paliers', slug=f'taqinor-{self.slug}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client Paliers')

    def _devis(self, reference='DEV-PAL-01', **extra):
        return Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_obj, statut='brouillon',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            **extra)

    def _ligne(self, devis, designation, quantite, prix, *,
               remise='0', variante=''):
        produit = Produit.objects.create(
            company=self.company, nom=f'{designation} #{devis.pk}',
            prix_vente=Decimal(prix), quantite_stock=10)
        return LigneDevis.objects.create(
            devis=devis, produit=produit, designation=designation,
            quantite=Decimal(quantite), prix_unitaire=Decimal(prix),
            remise=Decimal(remise), variante=variante)


class FacteurRemiseTests(_BaseDevis):
    """5a — la MÊME remise que le devis, sur CHAQUE palier."""

    def test_sans_remise_le_facteur_vaut_un(self):
        devis = self._devis()
        self._ligne(devis, 'Panneau 710W', '10', '1000')
        self.assertAlmostEqual(facteur_remise_du_devis(devis), 1.0, places=6)

    def test_remise_globale_reprise_a_l_identique(self):
        devis = self._devis(remise_globale=Decimal('10'))
        self._ligne(devis, 'Panneau 710W', '10', '1000')
        self._ligne(devis, 'Batterie 10 kWh', '1', '25000')
        self.assertAlmostEqual(facteur_remise_du_devis(devis), 0.90, places=6)

    def test_remise_de_ligne_et_remise_globale_se_composent(self):
        """Chaîne de ``quote_engine.builder`` : la remise de LIGNE d'abord, la
        remise GLOBALE ensuite sur le sous-total HT."""
        devis = self._devis(remise_globale=Decimal('10'))
        self._ligne(devis, 'Panneau 710W', '10', '1000', remise='20')
        # HT brut = 10 000 ; après remise de ligne = 8 000 ; après globale
        # = 7 200 ⇒ facteur = 0,72.
        self.assertAlmostEqual(facteur_remise_du_devis(devis), 0.72, places=6)

    def test_lignes_de_l_option_sans_batterie_exclues_de_la_portee(self):
        """L-2OPT — l'échelle chiffre l'option AVEC batterie : la remise d'une
        ligne réservée à l'option SANS ne doit pas déteindre dessus."""
        devis = self._devis()
        self._ligne(devis, 'Panneau 710W', '10', '1000', variante='')
        self._ligne(devis, 'Onduleur réseau 10kW', '1', '10000',
                    remise='50', variante='sans')
        self.assertAlmostEqual(facteur_remise_du_devis(devis), 1.0, places=6)

    def test_devis_sans_ligne_aucun_rabais_invente(self):
        self.assertAlmostEqual(
            facteur_remise_du_devis(self._devis()), 1.0, places=6)

    def test_remise_aberrante_rend_le_prix_catalogue(self):
        """Une remise de 100 % (ou plus) ne décrit aucun prix réel : on rend le
        catalogue plutôt qu'un zéro fabriqué."""
        devis = self._devis(remise_globale=Decimal('100'))
        self._ligne(devis, 'Panneau 710W', '10', '1000')
        self.assertAlmostEqual(facteur_remise_du_devis(devis), 1.0, places=6)

    def test_sections_et_notes_ignorees(self):
        """XSAL14 — une ligne de section/note ne porte pas de prix : elle ne
        pèse dans aucun total, donc dans aucun facteur."""
        devis = self._devis(remise_globale=Decimal('10'))
        self._ligne(devis, 'Panneau 710W', '10', '1000')
        LigneDevis.objects.create(
            devis=devis, designation='— Kit solaire —',
            type_ligne=LigneDevis.TypeLigne.SECTION)
        self.assertAlmostEqual(facteur_remise_du_devis(devis), 0.90, places=6)


class CapaciteDesLignesTests(_BaseDevis):
    """5b — ``retenu`` se lit sur les LIGNES vendues, jamais sur le moteur."""

    def test_capacite_lue_sur_les_lignes_batterie(self):
        devis = self._devis()
        self._ligne(devis, 'Panneau 710W', '14', '1166')
        self._ligne(devis, 'Batterie Dyness 10 kWh', '2', '25000')
        self.assertAlmostEqual(
            capacite_batterie_des_lignes(devis), 20.0, places=2)

    def test_calibres_melanges_additionnes(self):
        devis = self._devis()
        self._ligne(devis, 'Batterie Dyness 10 kWh', '1', '25000')
        self._ligne(devis, 'Batterie Dyness 5 kWh', '1', '14000')
        self.assertAlmostEqual(
            capacite_batterie_des_lignes(devis), 15.0, places=2)

    def test_aucune_ligne_batterie_aucun_palier_retenu(self):
        """« Jamais un marquage faux » : sans batterie vendue, la lecture rend
        ``None`` et aucune pilule ne peut se déclarer retenue."""
        devis = self._devis()
        self._ligne(devis, 'Panneau 710W', '14', '1166')
        self._ligne(devis, 'Onduleur réseau 10kW', '1', '15000')
        self.assertIsNone(capacite_batterie_des_lignes(devis))

    def test_quantite_nulle_ignoree(self):
        devis = self._devis()
        self._ligne(devis, 'Batterie Dyness 10 kWh', '0', '25000')
        self.assertIsNone(capacite_batterie_des_lignes(devis))

    def test_la_capacite_des_lignes_peut_differer_de_l_optimum_moteur(self):
        """LE SCÉNARIO DU FINDING : le bloc ``dimensionnement`` du devis
        annonce 15 kWh (optimum moteur) alors que les LIGNES en vendent 20 —
        c'est 20 qui doit être retenu, sinon la pilule affiche le prix d'une
        autre capacité."""
        devis = self._devis(etude_params={
            'dimensionnement': {'recommandation_avec': {'batterie_kwh': 15.0}}})
        self._ligne(devis, 'Batterie Dyness 10 kWh', '2', '25000')
        self.assertAlmostEqual(
            capacite_batterie_des_lignes(devis), 20.0, places=2)
