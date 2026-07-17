"""Tests NTAGR16 — Traçabilité amont-aval (parcelle → lot → client final).

Couvre : un lot vendu (stock_lot_id renseigné) affiche la chaîne complète
amont (parcelle/traitements) + aval (via stock.selectors.trace_serie), un
lot non vendu s'arrête proprement à l'amont (aval=None, jamais une erreur)."""
from unittest.mock import patch

from django.test import TestCase

from apps.agriculture.models import (
    CampagneCulturale, Exploitation, IntrantAgricole, Parcelle,
)
from apps.agriculture.selectors import tracer_lot
from apps.agriculture.services import creer_lot_recolte

from .helpers import auth, make_company, make_user


class TracabiliteLotTests(TestCase):
    def setUp(self):
        self.co = make_company('agr-trace-a', 'Ferme Traçabilité')
        self.admin = make_user(self.co, 'agr-trace-admin', 'admin')
        exploitation = Exploitation.objects.create(
            company=self.co, nom='Domaine',
        )
        self.parcelle = Parcelle.objects.create(
            company=self.co, exploitation=exploitation, nom='Parcelle 1',
            geometrie_gps=[{'lat': 31.5, 'lng': -7.9}])
        self.campagne = CampagneCulturale.objects.create(
            company=self.co, parcelle=self.parcelle, culture='Orange',
            date_recolte_prevue='2026-06-30')
        self.intrant = IntrantAgricole.objects.create(
            company=self.co, produit_id=1, categorie='phyto',
            matiere_active='Cuivre', numero_amm='AMM-1',
            delai_avant_recolte_jours=7)
        self.campagne.etapes.create(
            company=self.co, type_etape='traitement', date='2026-06-01',
            intrant=self.intrant)

    def test_lot_sans_stock_lot_id_s_arrete_a_l_amont(self):
        lot = creer_lot_recolte(
            company=self.co, campagne=self.campagne, date_recolte='2026-06-30',
            quantite_qtl='10')
        chaine = tracer_lot(lot)
        self.assertEqual(chaine['amont']['parcelle_id'], self.parcelle.id)
        self.assertEqual(len(chaine['amont']['traitements']), 1)
        self.assertEqual(
            chaine['amont']['traitements'][0]['matiere_active'], 'Cuivre')
        self.assertIsNone(chaine['aval'])

    def test_lot_vendu_affiche_la_chaine_aval(self):
        lot = creer_lot_recolte(
            company=self.co, campagne=self.campagne, date_recolte='2026-06-30',
            quantite_qtl='10', stock_lot_id='LOTENT-2026-0007')
        fake_chaine_stock = {
            'numero_lot': 'LOTENT-2026-0007',
            'reception': {'produit_nom': 'Orange calibre 60'},
            'emplacement': {'statut': 'epuise'},
        }
        with patch(
            'apps.stock.selectors.trace_serie',
            return_value=fake_chaine_stock,
        ) as mocked:
            chaine = tracer_lot(lot)
        mocked.assert_called_once_with(self.co, numero_lot='LOTENT-2026-0007')
        self.assertEqual(chaine['aval'], fake_chaine_stock)
        self.assertEqual(chaine['amont']['parcelle_id'], self.parcelle.id)

    def test_endpoint_tracabilite(self):
        lot = creer_lot_recolte(
            company=self.co, campagne=self.campagne, date_recolte='2026-06-30',
            quantite_qtl='10')
        api = auth(self.admin)
        resp = api.get(f'/api/django/agriculture/lots-recolte/{lot.id}/tracabilite/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['lot_id'], lot.id)
        self.assertIsNone(resp.data['aval'])

    def test_campagne_sans_traitement_amont_vide(self):
        campagne_vierge = CampagneCulturale.objects.create(
            company=self.co, parcelle=self.parcelle, culture='Citron')
        lot = creer_lot_recolte(
            company=self.co, campagne=campagne_vierge, date_recolte='2026-07-01',
            quantite_qtl='3')
        chaine = tracer_lot(lot)
        self.assertEqual(chaine['amont']['traitements'], [])
