"""NTSCM2 — Moteur de prévision saisonnière (core/demand_forecast.py) +
``apps.scm.services.generer_previsions``.

Critère d'acceptation : un test avec 24 mois d'historique synthétique à
saisonnalité marquée produit une projection dont l'erreur absolue moyenne
(MAE) est inférieure à celle d'une moyenne mobile simple.

``MouvementStock`` est créé directement via ``apps.stock.models`` UNIQUEMENT
pour construire la fixture de test — la production (``apps/scm/services.py``)
ne lit ``stock.MouvementStock`` que via ``django.apps.apps.get_model``
dynamique en LECTURE SEULE (jamais un import statique, jamais une écriture
dans ``apps.stock`` — voir le commentaire de
``_historique_sorties_mensuelles``)."""
from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.scm.models import PrevisionDemande
from apps.scm.services import generer_previsions
from apps.stock.models import MouvementStock, Produit
from core.demand_forecast import forecast_demand

from .helpers import make_company

# Motif saisonnier marqué (creux hiver, pic été) — répété à l'identique sur
# 2 années pleines pour que l'indice saisonnier calculé soit EXACT.
MONTHLY_FACTOR = [0.5, 0.5, 0.7, 0.9, 1.0, 1.4, 1.8, 1.7, 1.1, 0.8, 0.6, 0.5]
BASE_LEVEL = 100


def _synthetic_history(start_year, n_months):
    """Historique déterministe ``[(periode, quantite), ...]`` reproduisant
    ``MONTHLY_FACTOR`` en boucle à partir de janvier ``start_year``."""
    out = []
    for i in range(n_months):
        total = start_year * 12 + i
        y, m0 = divmod(total, 12)
        m = m0 + 1
        qty = BASE_LEVEL * MONTHLY_FACTOR[m0]
        out.append((f'{y:04d}-{m:02d}', qty))
    return out


class ForecastDemandMaeTests(TestCase):
    def test_seasonal_forecast_beats_simple_moving_average_on_seasonal_data(self):
        # 24 mois d'historique (2024-01 .. 2025-12), motif qui SE RÉPÈTE.
        history = _synthetic_history(2024, 24)
        # Continuation "vraie" (2026-01 .. 2026-06) suit exactement le même motif.
        vrai = {
            periode: BASE_LEVEL * MONTHLY_FACTOR[int(periode[5:7]) - 1]
            for periode, _ in _synthetic_history(2026, 6)
        }

        resultat = forecast_demand(history, horizon_mois=6)
        self.assertFalse(resultat.used_fallback)
        mae_saisonnier = sum(
            abs(qty - vrai[periode]) for periode, qty in resultat.previsions
        ) / len(resultat.previsions)

        # Moyenne mobile simple (baseline de comparaison) : moyenne à plat des
        # 3 derniers mois observés (Oct/Nov/Déc, en creux), répétée pour tout
        # l'horizon — ignore totalement la saisonnalité.
        derniers_3 = [q for _, q in history[-3:]]
        moyenne_simple = sum(derniers_3) / len(derniers_3)
        mae_moyenne_simple = sum(
            abs(moyenne_simple - v) for v in vrai.values()
        ) / len(vrai)

        self.assertLess(mae_saisonnier, mae_moyenne_simple)

    def test_fallback_under_twelve_months_of_history(self):
        history = _synthetic_history(2026, 6)  # seulement 6 mois
        resultat = forecast_demand(history, horizon_mois=3)
        self.assertTrue(resultat.used_fallback)
        self.assertEqual(resultat.indices_saisonniers, {})
        # Repli = moyenne simple, à plat sur tout l'horizon.
        valeurs_previsions = {q for _, q in resultat.previsions}
        self.assertEqual(len(valeurs_previsions), 1)

    def test_empty_history_yields_no_forecast(self):
        resultat = forecast_demand([], horizon_mois=3)
        self.assertTrue(resultat.used_fallback)
        self.assertEqual(resultat.previsions, [])


class GenererPrevisionsServiceTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-forecast', 'Supply Forecast')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur 6kW', prix_vente=8000,
            quantite_stock=500)

    def _seed_mouvements(self, history):
        qty_restante = 10000
        for periode, qty in history:
            y, m = int(periode[:4]), int(periode[5:7])
            qty = int(qty)
            mvt = MouvementStock.objects.create(
                company=self.company, produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=qty, quantite_avant=qty_restante,
                quantite_apres=qty_restante - qty)
            qty_restante -= qty
            # `date` est auto_now_add : on la repositionne explicitement au
            # mois voulu pour construire un historique déterministe.
            mvt.date = timezone.make_aware(
                timezone.datetime(y, m, 15))
            mvt.save(update_fields=['date'])

    def test_generer_previsions_uses_seasonal_method_with_enough_history(self):
        today = timezone.localdate()
        # 24 mois d'historique consécutifs se terminant le mois dernier
        # (index mensuel absolu, jamais discrétisé en "année de départ").
        idx_dernier_mois_complet = today.year * 12 + (today.month - 1) - 1
        history = []
        for offset in range(23, -1, -1):
            idx = idx_dernier_mois_complet - offset
            y, m0 = divmod(idx, 12)
            periode = f'{y:04d}-{m0 + 1:02d}'
            history.append((periode, BASE_LEVEL * MONTHLY_FACTOR[m0]))
        self._seed_mouvements(history)

        previsions = generer_previsions(
            self.produit, 6, self.company, fenetre_mois=30)
        self.assertEqual(len(previsions), 6)
        self.assertTrue(
            all(p.methode == PrevisionDemande.Methode.SAISONNIER for p in previsions))
        self.assertTrue(
            all(p.company_id == self.company.id for p in previsions))

    def test_generer_previsions_is_idempotent_update_or_create(self):
        self._seed_mouvements(_synthetic_history(date.today().year - 2, 24))
        first = generer_previsions(self.produit, 3, self.company)
        second = generer_previsions(self.produit, 3, self.company)
        self.assertEqual({p.id for p in first}, {p.id for p in second})
        self.assertEqual(
            PrevisionDemande.objects.filter(
                company=self.company, produit=self.produit).count(),
            3)
