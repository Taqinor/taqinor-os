"""NTSCM18 — Simulation de rupture (what-if) sur un horizon.

Critère d'acceptation : un scénario « délai fournisseur +15 jours » avance la
date de rupture simulée d'exactement 15 jours par rapport au scénario de
base pour une conso constante.

ADAPTATION documentée dans ``services.simuler_rupture`` : ``core.
stock_reorder.predict_reorder`` calcule la date de rupture PHYSIQUE
(``stock actuel / conso``), indépendante du délai fournisseur (un stock se
vide à la même vitesse quel que soit le délai de la PROCHAINE livraison) — à
conso/stock constants elle ne peut donc jamais bouger avec le seul délai. La
métrique qui EN DÉPEND à parts égales est ``date_limite_commande``
(``rupture_date − lead_time_days``, dernier jour où passer commande) : c'est
elle qui avance de exactement +15 jours de délai = -15 jours sur cette date."""
from django.test import TestCase
from django.utils import timezone

from apps.scm.services import simuler_rupture
from apps.stock.models import MouvementStock, Produit

from .helpers import auth, make_company, make_user


class SimulerRuptureTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-simuler-rupture', 'Supply Simuler Rupture')
        self.admin = make_user(self.company, 'scm-simuler-rupture-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur hybride', prix_vente=12000,
            quantite_stock=170)

        today = timezone.localdate()
        idx_dernier = today.year * 12 + (today.month - 1) - 1
        qty_restante = 100000
        for offset in range(5, -1, -1):
            idx = idx_dernier - offset
            y, m0 = divmod(idx, 12)
            mvt = MouvementStock.objects.create(
                company=self.company, produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=300, quantite_avant=qty_restante,
                quantite_apres=qty_restante - 300)
            qty_restante -= 300
            mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
            mvt.save(update_fields=['date'])

    def test_delai_fournisseur_plus_15_jours_avance_la_date_limite_de_15_jours(self):
        resultat = simuler_rupture(
            self.produit, {'delai_fournisseur_jours_supplementaires': 15},
            self.company)

        self.assertIsNotNone(resultat['base']['rupture_date'])
        # Conso/stock inchangés dans ce scénario -> la date de rupture
        # PHYSIQUE ne bouge jamais.
        self.assertEqual(resultat['delta_jours_rupture'], 0)
        # ... mais la date limite de commande (rupture - lead_time) avance
        # d'exactement 15 jours.
        self.assertEqual(resultat['delta_jours_date_limite_commande'], -15)

    def test_scenario_est_en_memoire_aucune_ecriture(self):
        avant = self.produit.quantite_stock
        simuler_rupture(self.produit, {'demande_pct': 50}, self.company)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, avant)

    def test_demande_plus_pourcentage_rapproche_la_rupture(self):
        resultat = simuler_rupture(
            self.produit, {'demande_pct': 100}, self.company)
        # Conso doublée -> rupture deux fois plus proche (jours restants
        # réduits, jamais négatifs ni None).
        self.assertIsNotNone(resultat['base']['days_until_rupture'])
        self.assertIsNotNone(resultat['simule']['days_until_rupture'])
        self.assertLess(
            resultat['simule']['days_until_rupture'],
            resultat['base']['days_until_rupture'])

    def test_endpoint_simuler(self):
        resp = auth(self.admin).post(
            f'/api/django/scm/produits/{self.produit.id}/simuler/',
            {'delai_fournisseur_jours_supplementaires': 15}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['delta_jours_date_limite_commande'], -15)

    def test_endpoint_produit_introuvable(self):
        resp = auth(self.admin).post(
            '/api/django/scm/produits/999999/simuler/', {}, format='json')
        self.assertEqual(resp.status_code, 404)
