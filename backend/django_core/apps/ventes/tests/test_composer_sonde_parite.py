# -*- coding: utf-8 -*-
"""QJR605 — les cartes Éco / Recommandé / Max, l'échelle de paliers batterie
et le balayage de tailles composent via UN constructeur de pipeline.

Constat : ``offres_tailles._Contexte.composer``, l'échelle de
``dimensionnement_devis`` et ``dimensionnement.balayer_tailles`` appelaient
``composition_residentielle`` en direct — sans la gamme du devis, sans la
phase, sans les paires MPPT, sans le hors-réseau : sur un triphasé à gamme
épinglée, ou sur un site isolé, les tailles montrées étaient chiffrées avec un
autre kit que celui du devis.

Run :
    python manage.py test apps.ventes.tests.test_composer_sonde_parite -v 2
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes import offres_tailles as ot
from apps.ventes.domain import pipeline
from apps.ventes.models import Devis, ParametresGammes

CATALOGUE = (
    ('Panneau Canadien Solar 710W', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', '14000'),
    ('Onduleur réseau Huawei 5kW Triphasé', '15000'),
    ('Onduleur réseau Deye 5kW Triphasé', '15500'),
    ('Onduleur hybride Deye 5kW Monophasé', '17000'),
    ('Onduleur hybride Deye 5kW Triphasé', '18000'),
    ('Deye Off-Grid 6kW', '16000'),
    ('Batterie Dyness 5 kWh', '16000'),
    ('Structures acier', '500'),
    ('Socles', '80'),
    ('Transport', '1000'),
)


def _empreinte(lignes):
    return [(li.designation, int(li.quantite),
             Decimal(str(li.prix_unitaire)).quantize(Decimal('0.01')))
            for li in lignes]


class _Base(TestCase):
    RACCORDEMENT = 'triphase'

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.create(
            slug='qjr605-%s' % self.RACCORDEMENT, nom='qjr605')
        ParametresGammes.objects.update_or_create(
            company=self.company,
            defaults={
                'deux_gammes': True,
                'nom_essentielle': ParametresGammes.SLOT_ESSENTIELLE,
                'nom_premium': ParametresGammes.SLOT_PREMIUM,
                'marques': {ParametresGammes.SLOT_PREMIUM: {
                    'onduleur_reseau': 'Deye'}},
            })
        self.produits = {}
        for nom, prix in CATALOGUE:
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=100)
        client = Client.objects.create(company=self.company, nom='QJR605')
        self.lead = Lead.objects.create(
            company=self.company, nom='QJR605', ville='Casablanca',
            raccordement=self.RACCORDEMENT)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR605-%s' % self.RACCORDEMENT,
            statut='brouillon', client=client, lead=self.lead,
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params={'gamme': {'nom': ParametresGammes.SLOT_PREMIUM}})
        panneau = self.produits['Panneau Canadien Solar 710W']
        self.devis.lignes.create(
            produit=panneau, designation=panneau.nom, quantite=Decimal('8'),
            prix_unitaire=panneau.prix_vente, remise=Decimal('0'), ordre=0)

    def _contexte(self):
        from apps.ventes.services import catalogue_de_la_societe
        return ot._Contexte(self.devis, {}, 710.0,
                            catalogue_de_la_societe(self.company), {}, [])


class TriphaseGammeEpinglee(_Base):
    RACCORDEMENT = 'triphase'

    def test_carte_compose_comme_le_pipeline(self):
        lignes = self._contexte().composer(8, avec_batterie=False)
        self.assertIsNotNone(lignes)
        attendu = pipeline.composer(pipeline.IntentionComposition(
            company=self.company, kwc=8 * 0.71, nb_panneaux=8,
            panel_watt=710, scenario=pipeline.COMPOSITION_SANS,
            phase='triphase', gamme_nom_devis=ParametresGammes.SLOT_PREMIUM,
            taux_tva=Decimal('20'), ville='Casablanca'))
        self.assertEqual(_empreinte(lignes), _empreinte(attendu))
        designations = [li.designation for li in lignes]
        self.assertIn('Onduleur réseau Deye 5kW Triphasé', designations)

    def test_contexte_sonde_lit_le_devis(self):
        contexte = pipeline.contexte_sonde_du_devis(self.devis)
        self.assertEqual(contexte.phase, 'triphase')
        self.assertEqual(contexte.gamme_nom_devis,
                         ParametresGammes.SLOT_PREMIUM)
        self.assertFalse(contexte.hors_reseau)
        self.assertEqual(contexte.taux_tva, Decimal('20'))


class SiteIsole(_Base):
    RACCORDEMENT = 'aucun'

    def test_aucun_onduleur_reseau_ni_hybride(self):
        contexte = pipeline.contexte_sonde_du_devis(self.devis)
        self.assertTrue(contexte.hors_reseau)
        for avec in (False, True):
            lignes = pipeline.composer_sonde(contexte, 8, avec_batterie=avec)
            noms = ' '.join(li.designation for li in lignes).lower()
            self.assertNotIn('réseau', noms)
            self.assertNotIn('hybride', noms)
            self.assertIn('off-grid', noms)
        lignes = self._contexte().composer(8, avec_batterie=True)
        noms = ' '.join(li.designation for li in lignes).lower()
        self.assertNotIn('hybride', noms)
        self.assertIn('off-grid', noms)


class AucunAppelDirect(TestCase):
    """Les trois modules ne composent plus en direct : ils passent par
    ``pipeline.composer_sonde``."""

    MODULES = ('offres_tailles.py', 'domain/dimensionnement_devis.py',
               'dimensionnement.py')

    def test_garde_ast(self):
        racine = Path(__file__).resolve().parent.parent
        for relatif in self.MODULES:
            arbre = ast.parse((racine / relatif).read_text(encoding='utf-8'))
            appels = [
                n for n in ast.walk(arbre)
                if isinstance(n, ast.Call)
                and getattr(n.func, 'id', getattr(n.func, 'attr', None))
                == 'composition_residentielle']
            self.assertEqual(appels, [], relatif)
            self.assertIn('composer_sonde',
                          (racine / relatif).read_text(encoding='utf-8'),
                          relatif)
