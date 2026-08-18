"""Drift-lock — ``pricing.py`` (ventes) vs ``tariff.py`` (parametres), même
grille ONEE BT résidentielle SÉLECTIVE, DEUX implémentations indépendantes :

  · ``apps/ventes/quote_engine/pricing.py`` — ``ONEE_TRANCHES`` /
    ``_monthly_bill_from_kwh`` (économies du devis/PDF, rule #4).
  · ``apps/parametres/tariff.py`` — ``monthly_bill_residentiel`` (consommé par
    ``apps/ventes/etude.py`` pour l'étude bancable et par l'écran Tarification
    & ROI), avec son barème par défaut ``apps/parametres/models_tariff.py``
    ``DEFAULT_RESIDENTIAL_TIERS``.

PAS de fusion voulue (hors périmètre — CLAUDE.md) : ce test est l'ALARME. Si
l'une des deux implémentations est éditée SEULE, ce test passe au rouge au
lieu de laisser devis et études diverger en silence. Voir le commentaire de
renvoi à chaque site d'implémentation.

``parametres`` est une app FONDATION (exemptée de la frontière cross-app —
CLAUDE.md) : ce test côté ``ventes`` peut donc l'importer directement.

PUR — aucune DB. ``TariffSettings()`` est instancié NON sauvegardé (jamais de
``.save()``, jamais de ``.objects.get_or_create()``) : on ne lit que ses
DÉFAUTS de champ (``effective_tiers()``, ``selective_threshold_kwh=150``,
``tolerance_kwh=10``) — instancier un modèle Django ne touche jamais la base,
seuls ``.save()``/``.objects.*`` le font. Tourne en ``SimpleTestCase``.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_tariff_drift_lock -v 2
"""
from django.test import SimpleTestCase

from apps.parametres import tariff as tariff_service
from apps.parametres.models_tariff import TariffSettings
from apps.ventes.quote_engine.pricing import ONEE_TRANCHES, _monthly_bill_from_kwh

# Sonde traversant CHAQUE marche de la grille vérifiée RADEEJ (18/08/2026) :
# progressif 0-100 / 101-150, puis sélectif (tout le mois au tarif de sa
# tranche, tolérance 10 kWh déjà repliée dans les bornes 210/310/510) :
# 151-210 / 211-310 / 311-510 / >510.
PROBE_KWH = [100, 150, 151, 210, 211, 310, 311, 499, 500, 501, 510, 511, 700, 1250]


class TestTariffDriftLock(SimpleTestCase):
    """Les deux implémentations doivent facturer le MÊME montant MAD partout."""

    def test_both_implementations_agree_on_every_probe(self):
        settings = TariffSettings()  # non sauvegardé — défauts de champ, pas de DB.
        for kwh in PROBE_KWH:
            pricing_bill = round(
                _monthly_bill_from_kwh(float(kwh), ONEE_TRANCHES), 2)
            tariff_bill = float(
                tariff_service.monthly_bill_residentiel(settings, kwh))
            self.assertAlmostEqual(
                pricing_bill, tariff_bill, places=2,
                msg=(
                    f"{kwh} kWh/mois : pricing.py={pricing_bill} MAD vs "
                    f"tariff.py={tariff_bill} MAD — les deux implémentations "
                    "ont divergé, voir la note en tête de ce fichier."
                ))

    def test_default_seeded_tiers_match_the_verified_grid(self):
        # DEFAULT_RESIDENTIAL_TIERS (models_tariff.py) stocke des bornes déjà
        # EFFECTIVES (210/310/510, tolérance repliée) ; ONEE_TRANCHES
        # (pricing.py) stocke des bornes NOMINALES (200/300/500) +
        # boundary_tolerance=10, repliée au calcul. Mêmes six prix, mêmes six
        # bornes effectives : on vérifie ici les CONSTANTES stockées, pas
        # seulement la sortie du calcul (ceinture et bretelles).
        settings = TariffSettings()
        effective = settings.effective_tiers()
        bornes_effectives_attendues = [
            (100, 0.9010), (150, 1.0732), (210, 1.0732),
            (310, 1.1676), (510, 1.3817), (None, 1.5958),
        ]
        for (ceiling, price), tier in zip(bornes_effectives_attendues, effective):
            self.assertEqual(tier['max_kwh'], ceiling)
            self.assertAlmostEqual(float(tier['prix_kwh_ttc']), price, places=4)
