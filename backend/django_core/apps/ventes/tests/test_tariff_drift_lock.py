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
from apps.parametres.models_tariff import (
    DEFAULT_RESIDENTIAL_TIERS,
    TariffSettings,
)
from apps.ventes.quote_engine import bareme
from apps.ventes.quote_engine.pricing import (
    ONEE_TRANCHES,
    _monthly_bill_from_kwh,
    two_bills_savings,
)

# Sonde traversant CHAQUE marche de la grille vérifiée RADEEJ (18/08/2026) :
# progressif 0-100 / 101-150, puis sélectif (tout le mois au tarif de sa
# tranche, tolérance 10 kWh déjà repliée dans les bornes 210/310/510) :
# 151-210 / 211-310 / 311-510 / >510.
#
# Sondes FRACTIONNAIRES (F2, revue Fable pré-merge) — ``apps/ventes/etude.py``
# ``_annual_savings_year1`` calcule ``self_consumed_kwh/12``, presque jamais un
# entier : ``apps/parametres/tariff.py`` tronquait ce kWh en ``int()`` avant de
# choisir la tranche sélective, alors que la multiplication finale gardait le
# kWh réel — un client à 210,5 kWh/mois retombait (via l'``int()``) dans la
# tranche 151–210 au lieu de 211–310 : SEULE la SÉLECTION de tranche doit lire
# le kWh exact, jamais sa troncature.
#
# Dérivation à la main de 210,5 kWh (bornes opératoires 210/310/510, barème
# DEFAULT_RESIDENTIAL_TIERS **TTC 2026**, TVA 20 %) : 210,5 > 210 ⇒ tranche
# 211–310 (1,187388 MAD/kWh) ⇒ 210,5 × 1,187388 = 249,945174 → arrondi
# 249,95 MAD (PAS 210,5 × 1,091388 = 229,737174 → 229,74 MAD, la valeur bogue
# par troncature — écart −8,1 %).
# Même mécanique à 310,7 (> 310 ⇒ tranche 311–510, 1,381704 ⇒ 310,7 × 1,381704
# = 429,2954328 → 429,30 MAD, contre 368,92 MAD tronqué, −14,1 %) et à 510,3 (> 510 ⇒ palier ouvert,
# 1,622856 ⇒ 828,14 MAD, contre 717,03 MAD tronqué, −13,4 %). Les autres sondes
# fractionnaires (150,5 / 211,3 / 499,5 / 700,25) ne franchissent aucune borne
# entière : elles n'auraient PAS détecté le bug seules — gardées pour couvrir
# l'intérieur de chaque tranche, pas seulement ses abords.
PROBE_KWH = [
    100, 150, 151, 210, 211, 310, 311, 499, 500, 501, 510, 511, 700, 1250,
    150.5, 210.5, 211.3, 310.7, 499.5, 510.3, 700.25,
]


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
            (100, 0.916272), (150, 1.091388), (210, 1.091388),
            # T5 = 1,381704 depuis la décision fondateur D5 (29/08/2026) :
            # 1,15142 HT × 1,20, prouvé par la facture SRM du 08/05/2026.
            (310, 1.187388), (510, 1.381704), (None, 1.622856),
        ]
        for (ceiling, price), tier in zip(bornes_effectives_attendues, effective):
            self.assertEqual(tier['max_kwh'], ceiling)
            self.assertAlmostEqual(float(tier['prix_kwh_ttc']), price, places=4)


class TestClientT5UneSeuleValeur(SimpleTestCase):
    """QJR26 / décision fondateur D5 (29/08/2026) — UN SEUL TARIF T5.

    Le tarif de la tranche 311–510 kWh/mois vivait en plusieurs exemplaires :
    ``bareme.TRANCHES_2026`` portait SEUL la valeur PROUVÉE contre une facture
    réelle du fondateur (facture SRM n° 643769639 du 08/05/2026 : 359 kWh ×
    1,15142 HT = 413,36 HT / 496,03 TTC ⇒ 1,15142 × 1,20 = 1,381704 TTC),
    pendant que ``pricing.ONEE_TRANCHES`` et ``DEFAULT_RESIDENTIAL_TIERS``
    gardaient l'extrapolation « HT constant » (1,405116). Un même client T5
    voyait donc sa facture actuelle et ses économies gonflées d'environ 1,7 %
    sur le chemin « factures », et le même document pouvait valoriser son kWh de
    deux façons selon le modèle d'économies qui gagnait.

    Ce test verrouille la propagation : les TROIS sites portent la MÊME valeur,
    celle de ``bareme.py``, et un client T5 concret est facturé à l'identique
    par les deux moteurs.
    """

    #: Le client T5 de référence : 4 800 kWh/an = 400 kWh/mois, donc en plein
    #: milieu de la bande 311–510 (loin des bornes, la tolérance ne joue pas).
    CONSO_ANNUELLE = 4800
    KWH_MOIS = 400

    def _prix_t5_bareme(self):
        """LA valeur de référence, lue dans ``bareme.TRANCHES_2026``."""
        return dict((plafond, prix) for plafond, prix in bareme.TRANCHES_2026)[500]

    def test_les_trois_sites_portent_la_valeur_prouvee_par_la_facture(self):
        # Ancrage explicite sur la facture, pour qu'un futur éditeur voie d'où
        # sort le nombre au lieu de le recopier : 1,15142 HT × 1,20 = 1,381704.
        self.assertAlmostEqual(1.15142 * 1.20, 1.381704, places=9)
        reference = self._prix_t5_bareme()
        self.assertAlmostEqual(reference, 1.381704, places=9)

        # 1) moteur de devis / PDF (rule #4)
        self.assertAlmostEqual(
            dict((c, p) for c, p in ONEE_TRANCHES)[500], reference, places=9,
            msg='pricing.ONEE_TRANCHES a divergé de bareme.TRANCHES_2026')
        # 2) défauts société (étude bancable + écran Tarification & ROI)
        t5_defaut = [t for t in DEFAULT_RESIDENTIAL_TIERS
                     if t['max_kwh'] == 510][0]['prix_kwh_ttc']
        self.assertAlmostEqual(float(t5_defaut), reference, places=9,
                               msg='DEFAULT_RESIDENTIAL_TIERS a divergé')
        # 3) la divergence publiée est RÉSORBÉE, pas seulement silencieuse.
        t5 = [d for d in bareme.DIVERGENCES_PRICING
              if d['tranche'].startswith('311-510')][0]
        self.assertEqual(t5['statut'], 'propagé')
        self.assertAlmostEqual(t5['valeur_pricing'], t5['valeur_moteur'],
                               places=9)

    def test_la_facture_actuelle_du_client_t5_est_celle_de_la_facture_reelle(self):
        # Dérivation à la main : 400 kWh/mois × 1,381704 = 552,6816 MAD/mois.
        # (Avec l'ancien 1,405116 c'était 562,0464 — soit +9,36 MAD/mois,
        #  +1,69 %, sur un client qui n'a jamais consommé un kWh de plus.)
        attendu_mois = self.KWH_MOIS * 1.381704
        self.assertAlmostEqual(attendu_mois, 552.6816, places=9)

        # Chemin moteur de devis…
        self.assertAlmostEqual(
            _monthly_bill_from_kwh(self.KWH_MOIS, ONEE_TRANCHES),
            attendu_mois, places=9)
        # …chemin barème étalonné sur facture (composante énergie) : identiques.
        self.assertAlmostEqual(
            bareme.facture_mad(self.KWH_MOIS)['energie_mad'],
            attendu_mois, places=9)
        # …chemin défauts société (Decimal, arrondi au centime).
        settings = TariffSettings()
        self.assertAlmostEqual(
            float(tariff_service.monthly_bill_residentiel(
                settings, self.KWH_MOIS)),
            round(attendu_mois, 2), places=2)

    def test_les_economies_du_client_t5_suivent_la_meme_valeur(self):
        # Le client pose du solaire : 4 000 kWh/an produits, 60 % autoconsommés
        # (2 400 kWh) ⇒ résiduel 2 400 kWh/an = 200 kWh/mois, qui retombe dans
        # la bande 151–210 (1,091388) — la marche sélective, pas un prorata.
        #
        # RECALAGE QJR157 (30/08/2026) — LA FACTURE N'EST PLUS QUE L'ÉNERGIE.
        # ``two_bills_savings`` tarife désormais les deux factures par
        # ``bareme.facture_mad``, lignes fixes (location + entretien) et TPPAN
        # comprises. La composante ÉNERGIE ci-dessous est INCHANGÉE — c'est
        # elle que ce verrou surveille, et elle porte toujours la valeur T5
        # prouvée par la facture — mais les totaux annuels montent :
        #   facture sans : 400 × 1,381704 = 552,6816 × 12 = 6 632,18 d'énergie
        #                  + 479,23 de lignes fixes + 780,00 de TPPAN
        #                  = 7 891,41 → 7 891
        #   facture avec : 200 × 1,091388 = 218,2776  × 12 = 2 619,33 d'énergie
        #                  + 479,23 de lignes fixes + 300,00 de TPPAN
        #                  = 3 398,56 → 3 399
        #   économie     : 7 891 − 3 399 = 4 492 MAD/an
        # Les lignes fixes s'annulent dans l'écart ; la TPPAN suit le kWh et ne
        # s'annule donc pas — d'où 4 013 → 4 492. Le second bloc de ce test
        # isole justement l'ÉNERGIE pour que le verrou T5 reste indépendant des
        # charges.
        out = two_bills_savings(4000, self.CONSO_ANNUELLE, 0.60, utility='onee')
        self.assertEqual(out['facture_sans'], 7891)
        self.assertEqual(out['facture_avec'], 3399)
        self.assertEqual(out['economie'], 4492)

        # Le moteur « factures » (bareme.py) valorise le MÊME écart d'énergie :
        # charges fixes et TPPAN mises à part (elles ne dépendent pas du tarif
        # T5), les deux implémentations doivent bouger du même montant.
        ecart_bareme = (bareme.facture_mad(self.KWH_MOIS)['energie_mad']
                        - bareme.facture_mad(200)['energie_mad'])
        ecart_pricing = (_monthly_bill_from_kwh(self.KWH_MOIS, ONEE_TRANCHES)
                         - _monthly_bill_from_kwh(200, ONEE_TRANCHES))
        self.assertAlmostEqual(ecart_bareme, ecart_pricing, places=9)
        self.assertAlmostEqual(ecart_bareme, 552.6816 - 218.2776, places=9)

    def test_lancienne_valeur_extrapolee_ne_facture_plus_rien(self):
        """Garde anti-retour : l'extrapolation réfutée ne tarife plus rien.

        La valeur interdite n'est PAS recopiée en dur : on la RE-DÉRIVE par le
        calcul même que la facture réfute (HT 2025 supposé constant × TVA 20 %),
        pour que le test dise POURQUOI elle est interdite — et pour que le
        dépôt ne contienne plus qu'une seule écriture littérale du tarif T5.
        """
        extrapolation_refutee = round(1.17093 * 1.20, 6)  # → l'ancien T5 2026
        self.assertGreater(extrapolation_refutee, self._prix_t5_bareme())

        for table in (ONEE_TRANCHES, bareme.TRANCHES_2026,
                      bareme.TRANCHES_2025):
            for _plafond, prix in table:
                self.assertNotAlmostEqual(
                    prix, extrapolation_refutee, places=6,
                    msg='une table facture encore au tarif T5 extrapolé')
        for tier in DEFAULT_RESIDENTIAL_TIERS:
            self.assertNotAlmostEqual(
                float(tier['prix_kwh_ttc']), extrapolation_refutee, places=6,
                msg='DEFAULT_RESIDENTIAL_TIERS facture encore à l\'extrapolation')
