"""NTSCM15 — Impact financier du plan S&OP (rapprochement CA/marge).

Critère d'acceptation : l'écran affiche les 3 vues synchronisées sur le même
cycle et l'alerte d'écart >15% est visible en rouge. Le backend ne peut pas
vérifier le rendu visuel (frontend ``frontend/src/pages/scm/CycleSopPage.jsx``) ;
ce test couvre la partie serveur : la valorisation utilise ``prix_vente``
(JAMAIS ``prix_achat``) et l'alerte se déclenche exactement au-delà du seuil
de 15% d'écart avec le forecast CA.

``apps.ventes.selectors.carnet_commande_par_mois`` (l'historique CA lu en
lecture seule) est STUBÉ (``unittest.mock.patch``) pour rendre le forecast
déterministe SANS construire de fixtures ``ventes.Devis``/``crm.Client``
complètes (hors périmètre de cette lane — ``ventes``/``crm`` appartiennent à
d'autres apps) ; ``Produit`` est créé via ``apps.stock.models`` UNIQUEMENT
pour la fixture (frontière cross-app, CLAUDE.md)."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.scm.models import CyclePlanificationSOP, LigneDemandeSOP
from apps.scm.selectors import SEUIL_ALERTE_ECART_CA_PCT, impact_financier_cycle
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


def _flat_history(valeur):
    mois = {}
    for m in range(9, 13):
        mois[f'2025-{m:02d}'] = Decimal(str(valeur))
    for m in range(1, 9):
        mois[f'2026-{m:02d}'] = Decimal(str(valeur))
    return mois


class ImpactFinancierCycleTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-fin', 'Supply Finance')
        self.admin = make_user(self.company, 'scm-fin-admin', 'admin')
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2026-09')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit solaire 6kWc',
            prix_vente=Decimal('10000'), prix_achat=Decimal('6000'))
        LigneDemandeSOP.objects.create(
            company=self.company, cycle=self.cycle, produit=self.produit,
            quantite_prevision_systeme=Decimal('10'))
        # ca_previsionnel attendu = 10 x 10 000 (prix_vente) = 100 000.

    def test_valorisation_uses_prix_vente_never_prix_achat(self):
        resultat = impact_financier_cycle(self.cycle)
        self.assertEqual(resultat['ca_previsionnel_ht'], Decimal('100000.00'))
        self.assertEqual(resultat['lignes'][0]['prix_vente'], Decimal('10000'))
        # Valorisé au prix d'achat, ce serait 60 000 — jamais le résultat ici.
        self.assertNotEqual(resultat['ca_previsionnel_ht'], Decimal('60000.00'))

    def test_no_history_degrades_gracefully_without_alert(self):
        # Aucun carnet de commandes -> pas de forecast -> pas d'alerte (jamais
        # de blocage).
        with patch(
                'apps.ventes.selectors.carnet_commande_par_mois',
                return_value={}):
            resultat = impact_financier_cycle(self.cycle)
        self.assertIsNone(resultat['ca_forecast_ht'])
        self.assertIsNone(resultat['ecart_pct'])
        self.assertFalse(resultat['alerte_ecart'])

    def test_large_deviation_from_forecast_triggers_alert(self):
        # Historique plat ~1 000/mois : quel que soit le moteur (moyenne,
        # tendance ou Holt-Winters), un forecast reste du même ordre de
        # grandeur que son historique — jamais proche de 100 000.
        with patch(
                'apps.ventes.selectors.carnet_commande_par_mois',
                return_value=_flat_history(1000)):
            resultat = impact_financier_cycle(self.cycle)
        self.assertIsNotNone(resultat['ca_forecast_ht'])
        self.assertTrue(resultat['alerte_ecart'])
        self.assertGreater(abs(resultat['ecart_pct']), SEUIL_ALERTE_ECART_CA_PCT)

    def test_matching_forecast_does_not_trigger_alert(self):
        # Historique plat à 100 000/mois : le forecast doit converger vers
        # ~100 000, proche du CA prévisionnel -> pas d'alerte.
        with patch(
                'apps.ventes.selectors.carnet_commande_par_mois',
                return_value=_flat_history(100000)):
            resultat = impact_financier_cycle(self.cycle)
        self.assertFalse(resultat['alerte_ecart'])

    def test_impact_financier_endpoint_admin_only(self):
        responsable = make_user(self.company, 'scm-fin-resp', 'responsable')
        with patch(
                'apps.ventes.selectors.carnet_commande_par_mois',
                return_value={}):
            resp = auth(responsable).get(
                f'/api/django/scm/cycles-sop/{self.cycle.id}/impact-financier/')
            self.assertEqual(resp.status_code, 403, resp.data)

            resp = auth(self.admin).get(
                f'/api/django/scm/cycles-sop/{self.cycle.id}/impact-financier/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['ca_previsionnel_ht'], '100000.00')
