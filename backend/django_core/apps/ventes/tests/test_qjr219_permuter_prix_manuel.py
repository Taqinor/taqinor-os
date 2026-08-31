# -*- coding: utf-8 -*-
"""QJR219 — ``_permuter_onduleur`` respecte un prix TAPÉ par le vendeur.

TEST ROUGE D'ABORD : ``domain/resynchronisation._permuter_onduleur`` écrasait
``prix_unitaire`` avec le prix catalogue SANS consulter ``prix_manuel`` et SANS
effacer le drapeau — le prix tapé disparaissait pendant que la ligne continuait
d'affirmer qu'il avait été tapé par le vendeur (état MENTEUR).

COMPORTEMENT RETENU, ÉCRIT : L'ABSTENTION, avec l'avertissement FR NOMMÉ
(``MSG_PERMUTATION_PRIX_MANUEL``) — même règle que
``lignes.retarifer_forfaits_par_panneau`` (D12) et que le bloc « DEUX
onduleurs » voisin, qui CONSERVE déjà un onduleur intrus hors prix catalogue.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr219_permuter_prix_manuel -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.domain.resynchronisation import MSG_PERMUTATION_PRIX_MANUEL
from apps.ventes.models import Devis
from apps.ventes.services import sync_devis_from_layout
from apps.ventes.tests.test_pv18_sync_layout import (
    BAREMES_FORFAIT, CATALOGUE_KIT, layout, make_company,
)

User = get_user_model()

PANNEAU = 'Panneau Jinko 550W'
RESEAU = 'Onduleur réseau Huawei 5kW'
HYBRIDE = 'Onduleur hybride Deye 5kW'
BATTERIE = 'Batterie Dyness 5 kWh'

#: Le prix NÉGOCIÉ que le vendeur a tapé sur l'onduleur réseau (catalogue :
#: 14 000). Il ne doit jamais disparaître en silence.
PRIX_NEGOCIE = Decimal('12500.00')


class TestQJR219(TestCase):

    def setUp(self):
        from apps.stock.models import Produit

        self.company = make_company('qjr219-co')
        self.user = User.objects.create_user(
            username='qjr219user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR219')
        self.produits = {}
        for nom, sku, prix in CATALOGUE_KIT:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku='QJR219-%s' % sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))
        self.compteur = 0

    def _devis(self, *, prix_manuel):
        """Réseau + batterie, sans hybride : la branche de PERMUTATION."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR219-%s' % self.compteur,
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user)
        devis.lignes.create(
            produit=self.produits[PANNEAU], designation=PANNEAU,
            quantite=Decimal('12'),
            prix_unitaire=self.produits[PANNEAU].prix_vente,
            remise=Decimal('0'), ordre=1)
        devis.lignes.create(
            produit=self.produits[RESEAU], designation=RESEAU,
            quantite=Decimal('1'),
            prix_unitaire=(PRIX_NEGOCIE if prix_manuel
                           else self.produits[RESEAU].prix_vente),
            remise=Decimal('0'), ordre=2, prix_manuel=prix_manuel)
        devis.lignes.create(
            produit=self.produits[BATTERIE], designation=BATTERIE,
            quantite=Decimal('1'),
            prix_unitaire=self.produits[BATTERIE].prix_vente,
            remise=Decimal('0'), ordre=3)
        return devis

    def _sync(self, devis):
        return sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='avec_batterie'),
            user=self.user)

    def _onduleur(self, devis):
        lignes = [li for li in devis.lignes.all()
                  if 'onduleur' in (li.designation or '').lower()]
        self.assertEqual(len(lignes), 1, [li.designation for li in lignes])
        return lignes[0]

    # ── LE ROUGE ────────────────────────────────────────────────────────────
    def test_prix_manuel_la_permutation_s_abstient_et_le_dit(self):
        devis = self._devis(prix_manuel=True)
        resultat = self._sync(devis)

        ligne = self._onduleur(devis)
        self.assertEqual(ligne.designation, RESEAU)
        self.assertEqual(ligne.prix_unitaire, PRIX_NEGOCIE)
        self.assertTrue(ligne.prix_manuel)
        messages = ' | '.join(resultat.get('avertissements') or ())
        self.assertIn(RESEAU, messages)
        self.assertIn('Prix saisi à la main', messages)

    def test_jamais_l_etat_menteur(self):
        """Le défaut nommé : prix catalogue écrit ET ``prix_manuel`` à True."""
        devis = self._devis(prix_manuel=True)
        self._sync(devis)
        ligne = self._onduleur(devis)
        catalogue = self.produits[RESEAU].prix_vente
        self.assertFalse(
            ligne.prix_manuel and ligne.prix_unitaire == catalogue,
            'la ligne affirme un prix vendeur qui a été écrasé')

    def test_le_message_nomme_les_deux_produits(self):
        devis = self._devis(prix_manuel=True)
        resultat = self._sync(devis)
        attendu = MSG_PERMUTATION_PRIX_MANUEL % (RESEAU, HYBRIDE)
        self.assertIn(attendu, resultat.get('avertissements') or ())

    # ── NON-RÉGRESSION ──────────────────────────────────────────────────────
    def test_sans_prix_manuel_la_permutation_a_toujours_lieu(self):
        devis = self._devis(prix_manuel=False)
        self._sync(devis)
        ligne = self._onduleur(devis)
        self.assertEqual(ligne.designation, HYBRIDE)
        self.assertEqual(ligne.prix_unitaire,
                         self.produits[HYBRIDE].prix_vente)
        self.assertFalse(ligne.prix_manuel)
