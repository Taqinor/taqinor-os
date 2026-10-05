# -*- coding: utf-8 -*-
"""ACAL174 — les modules favoris de la société EN TÊTE, drapeau ``favori``.

``favoris_materiel`` (CAL200) était saisi dans la Bibliothèque mais lu par
aucun sélecteur de matériel. Désormais ``GET modules-disponibles/`` et les
candidats de ``GET entree-electrique/`` le servent en tête. Base RÉELLE.
"""
from __future__ import annotations

from decimal import Decimal

from apps.calepinage.models import Calepinage, ParametresCalepinage
from apps.stock.models import FicheTechnique, Produit

from .test_api_liste import BaseApiCalepinage, url_detail


def _url(pk, suffixe):
    return f'{url_detail(pk)}{suffixe}/'


class Favoris(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.a = self._module('A Module')
        self.b = self._module('B Module')
        self.c = self._module('C Module')
        self.reglages = ParametresCalepinage.objects.create(
            company=self.company,
            favoris_materiel={'modules': [self.b.pk]})
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa')

    def _module(self, nom):
        produit = Produit.objects.create(
            company=self.company, nom=nom, sku='ACAL174-%s' % nom,
            prix_achat=Decimal('999'), prix_vente=Decimal('1500'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=produit, type_fiche='module',
            vmp_v=41.4, voc_v=49.3, isc_a=18.59, imp_a=17.59, pmax_wc=710.0,
            longueur_mm=2384, largeur_mm=1303)
        return produit

    def test_favori_en_tete_modules_disponibles(self):
        reponse = self.api.get(_url(self.calepinage.pk,
                                    'modules-disponibles'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = reponse.data['modules']
        self.assertEqual([ligne['module']['produitId'] for ligne in lignes],
                         [self.b.pk, self.a.pk, self.c.pk])
        self.assertEqual([ligne['favori'] for ligne in lignes],
                         [True, False, False])

    def test_favori_dans_candidats(self):
        reponse = self.api.get(_url(self.calepinage.pk, 'entree-electrique'))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        modules = reponse.data['candidats']['modules']
        self.assertEqual([ligne['id'] for ligne in modules],
                         [self.b.pk, self.a.pk, self.c.pk])
        self.assertEqual([ligne['favori'] for ligne in modules],
                         [True, False, False])

    def test_favori_archive_omis(self):
        Produit.objects.filter(pk=self.b.pk).update(is_archived=True)
        reponse = self.api.get(_url(self.calepinage.pk,
                                    'modules-disponibles'))
        lignes = reponse.data['modules']
        self.assertEqual([ligne['module']['produitId'] for ligne in lignes],
                         [self.a.pk, self.c.pk])
        self.assertFalse(any(ligne['favori'] for ligne in lignes))
