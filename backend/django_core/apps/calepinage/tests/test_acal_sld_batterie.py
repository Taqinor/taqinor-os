# -*- coding: utf-8 -*-
"""ACAL168 — la batterie DÉCLARÉE se dessine dans le schéma unifilaire.

Schéma RÉEL, sans doublure : les Produit et leurs FicheTechnique sont créés en
base, l'entrée électrique est posée par ``enregistrer_entree``, et le dessin
sort de ``core.electrique`` via l'adaptateur unique. La batterie vient de la
MÊME fonction que la simulation (``chaines.batterie_du_calepinage``) : un seul
produit, un seul nombre de packs, une seule provenance.

Run :
    python manage.py test apps.calepinage.tests.test_acal_sld_batterie -v2
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.services.electrique import enregistrer_entree
from apps.stock.models import FicheTechnique, Produit

from .test_acal_sld_conception_reelle import (
    BaseConceptionReelle, ParametresCalepinage, url_schema,
)

FICHE_BATTERIE = dict(bat_kwh_nominal=10.0, bat_kwh_usable=9.0,
                      bat_dod_pct=90.0, bat_rendement_ar_pct=94.0,
                      bat_cycles_publies=6000, bat_max_charge_kw=5.0,
                      bat_max_decharge_kw=5.0)


class SchemaBatterie(BaseConceptionReelle):
    def setUp(self):
        super().setUp()
        ParametresCalepinage.objects.create(
            company=self.company, norme_electrique={'norme': 'nf_c_15_100'})
        self.batterie = Produit.objects.create(
            company=self.company, nom='Pack 10 kWh', marque='Marque',
            sku='ACAL168-B', prix_achat=Decimal('999'),
            prix_vente=Decimal('1500'), quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=self.batterie,
            type_fiche='batterie', **FICHE_BATTERIE)

    def _schema(self):
        reponse = self.api.get(url_schema(self.calepinage.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_bloc_batterie_dessine(self):
        enregistrer_entree(self.calepinage, {
            'batterie': {'produit': self.batterie.pk, 'packs': 2,
                         'strategie': 'autoconso'}})

        donnees = self._schema()

        clefs = [bloc['clef'] for bloc in donnees['blocs']]
        self.assertIn('batterie', clefs)
        bloc = next(b for b in donnees['blocs'] if b['clef'] == 'batterie')
        self.assertIn('Pack 10 kWh', bloc['titre'])
        self.assertIn('kWh', bloc['sous_titre'])
        # Le cartouche porte la ligne « Stockage ».
        self.assertIn('Stockage', donnees['svg'])

    def test_sans_batterie_inchange(self):
        avant = self._schema()

        # Aucune déclaration : le schéma reste celui d'aujourd'hui.
        self.assertNotIn('batterie',
                         [bloc['clef'] for bloc in avant['blocs']])
        # Une lecture de plus rend le MÊME dessin (déterministe).
        self.assertEqual(avant['svg'], self._schema()['svg'])
