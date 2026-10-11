# -*- coding: utf-8 -*-
"""QJR609 — garde PDF « cet optimum décrit votre devis » : capacité UTILE
contre UTILE, comme la page web ; la capacité IMPRIMÉE reste nominale.

Constat : ``_optimum_decrit_ce_devis`` comparait le ``batterie_kwh`` de
l'optimum (kWh UTILES) à ``BATTERIE_KWH_TOTAL`` (NOMINAL lu sur la
désignation) ; la garde web (``config_vendue_du_devis``) passe par
``capacite_batterie_des_lignes`` (UTILE). Les deux verdicts pouvaient
diverger dès qu'une fiche porte une capacité utile inférieure au nominal.

Run :
    python manage.py test apps.ventes.tests.test_pdf_garde_optimum_capacite_utile -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine import generate_devis_premium as moteur

User = get_user_model()

NOMS_GLOBALES = ("BATTERIE_KWH_TOTAL", "BATTERIE_KWH_UTILE_VENDUE", "NB_PAN",
                 "ONEPAGE_BRANCHE")


class GardeUtileContreUtile(TestCase):
    def setUp(self):
        from authentication.models import Company
        self._ABSENT = object()
        self._sauvegarde = {n: getattr(moteur, n, self._ABSENT)
                            for n in NOMS_GLOBALES}
        self.company = Company.objects.create(slug='qjr609', nom='qjr609')
        self.user = User.objects.create_user(
            username='qjr609', password='x', company=self.company,
            role_legacy='admin')
        client = Client.objects.create(company=self.company, nom='QJR609')
        panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='Q609-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('1'),
            quantite_stock=100)
        hybride = Produit.objects.create(
            company=self.company, nom='Onduleur hybride Deye 8kW Monophasé',
            sku='Q609-ONDH', prix_vente=Decimal('20000'),
            prix_achat=Decimal('1'), quantite_stock=100)
        batterie = Produit.objects.create(
            company=self.company, nom='Batterie Deye 16 kWh', sku='Q609-BAT',
            prix_vente=Decimal('40000'), prix_achat=Decimal('1'),
            quantite_stock=100)
        FicheTechnique.objects.create(
            company=self.company, produit=batterie, type_fiche='batterie',
            bat_kwh_nominal=Decimal('16.00'), bat_kwh_usable=Decimal('14.40'),
            bat_dod_pct=Decimal('90.0'), bat_v_nominal=Decimal('51.2'))
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR609', client=client,
            statut='brouillon', taux_tva=Decimal('20.00'),
            created_by=self.user, mode_installation='residentiel',
            etude_params={'scenario': 'Avec batterie'})
        for ordre, (produit, qte) in enumerate(
                ((panneau, 12), (hybride, 1), (batterie, 1))):
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=produit.nom,
                quantite=Decimal(qte), prix_unitaire=produit.prix_vente,
                ordre=ordre)

    def tearDown(self):
        for nom, valeur in self._sauvegarde.items():
            if valeur is self._ABSENT:
                if hasattr(moteur, nom):
                    delattr(moteur, nom)
            else:
                setattr(moteur, nom, valeur)

    def test_garde_pdf_et_garde_web_rendent_le_meme_verdict(self):
        from apps.ventes.dimensionnement import (
            ConfigInstallation, config_vendue_du_devis, decrit)
        from apps.ventes.quote_engine.builder import build_quote_data

        data = build_quote_data(self.devis)
        # Le kWh IMPRIMÉ reste NOMINAL.
        self.assertEqual(float(data['batterie_kwh_total']), 16.0)
        self.assertAlmostEqual(float(data['batterie_kwh_utile_vendue']),
                               14.4, places=2)

        moteur.apply_quote_data(data)
        self.assertEqual(moteur.BATTERIE_KWH_TOTAL, 16.0)
        optimum = {'panneaux': 12, 'kwc': 6.6, 'batterie_kwh': 14.4}

        verdict_web = decrit(
            ConfigInstallation(panneaux=optimum['panneaux'],
                               batterie_kwh=optimum['batterie_kwh']),
            config_vendue_du_devis(self.devis))
        self.assertTrue(verdict_web)
        self.assertTrue(moteur._optimum_decrit_ce_devis(optimum))
        # Un optimum chiffré en NOMINAL ne décrit plus ce devis côté PDF.
        self.assertFalse(moteur._optimum_decrit_ce_devis(
            dict(optimum, batterie_kwh=16.0)))


class ParseKwhUnique(TestCase):
    def test_builder_et_public_views_lisent_le_catalogue(self):
        import ast
        from pathlib import Path
        from apps.ventes.domain import catalogue
        # SPL162 — le lecteur vit dans ``lignes_classement`` (move only) :
        # identité vérifiée là, absence de ``def`` sur les DEUX fichiers.
        from apps.ventes.quote_engine import lignes_classement
        self.assertIs(lignes_classement._parse_kwh, catalogue._parse_kwh)
        racine = Path(__file__).resolve().parent.parent
        for nom in ('builder.py', 'lignes_classement.py'):
            source = (racine / 'quote_engine' / nom).read_text(
                encoding='utf-8')
            defs = [n.name for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.FunctionDef)]
            self.assertNotIn('_parse_kwh', defs, nom)
        # SPL241 — ``public_views.py`` est découpé en ``public/*.py`` : la
        # garde lit le GROUPE (jamais vide), pas un fichier qui se vide.
        from apps.ventes.tests.split_golden import fichiers_du_groupe
        public = ''.join(
            chemin.read_text(encoding='utf-8')
            for chemin in fichiers_du_groupe('public_views.py', 'public/*.py'))
        self.assertNotIn('builder import (\n        _is_battery, _is_panel, '
                         '_parse_kwh', public)
        self.assertIn('domain.catalogue import _parse_kwh', public)
