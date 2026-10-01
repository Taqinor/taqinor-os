# -*- coding: utf-8 -*-
"""QJR610 — le moteur PDF lit l'option recommandée par
``domain.scenario.recommended_option_effective`` (la règle du registre écrite
une fois).

Constat : ``builder.py`` réécrivait la règle en ligne et divergeait pour une
valeur INCONNUE au registre : le domaine l'ignore et garde la valeur stockée,
le builder remplaçait une valeur stockée valide puis retombait sur le défaut
dérivé du scénario.

Run :
    python manage.py test apps.ventes.tests.test_builder_recommandation_registre -v 2
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()
BUILDER = (Path(__file__).resolve().parent.parent / 'quote_engine'
           / 'builder.py')


class GardeAst(SimpleTestCase):
    def test_plus_d_appel_effectif_recommended_option(self):
        arbre = ast.parse(BUILDER.read_text(encoding='utf-8'))
        fautifs = []
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            nom = getattr(noeud.func, 'id', getattr(noeud.func, 'attr', ''))
            if 'effectif' not in str(nom) or 'effective' in str(nom):
                continue
            if any(isinstance(a, ast.Constant)
                   and a.value == 'recommended_option' for a in noeud.args):
                fautifs.append(noeud.lineno)
        self.assertEqual(fautifs, [])


class RegistreInconnuGardeLeStocke(TestCase):
    def test_valeur_inconnue_au_registre_ignoree(self):
        from authentication.models import Company
        from apps.ventes.quote_engine.builder import build_quote_data
        company = Company.objects.create(slug='qjr610', nom='qjr610')
        user = User.objects.create_user(
            username='qjr610', password='x', company=company,
            role_legacy='admin')
        client = Client.objects.create(company=company, nom='QJR610')
        devis = Devis.objects.create(
            company=company, reference='DEV-QJR610', client=client,
            statut='brouillon', taux_tva=Decimal('20.00'), created_by=user,
            etude_params={'scenario': 'Les deux (Sans + Avec)',
                          'recommended_option': 'Sans batterie'},
            overrides={'recommended_option': {'valeur': 'Option fantôme',
                                              'origine': 'manuel'}})
        for ordre, (nom, qte, prix) in enumerate((
                ('Panneau Jinko 550W', 12, '1100'),
                ('Onduleur réseau Huawei 5kW', 1, '14000'),
                ('Onduleur hybride Deye 5kW', 1, '17000'),
                ('Batterie Dyness 5 kWh', 1, '16000'))):
            produit = Produit.objects.create(
                company=company, nom=nom, sku='Q610-%d' % ordre,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=10)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(prix),
                ordre=ordre)
        data = build_quote_data(devis)
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['recommended'], 'Sans batterie')
