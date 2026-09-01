"""QJR158 — lot de robustesse de ``quote_engine/pricing.py`` (cinq constats).

(a) ``_lire_etude_horaire`` ne gardait QUE la production et la consommation :
    un bloc horaire aux économies absentes/nulles passait, et
    ``calculate_savings_roi`` posait ``savings_model='horaire'``,
    ``savings_estimated=False`` et **0 MAD d'économie** — le document annonçant
    « la méthode la plus fine de ce document » avec une économie nulle, au lieu
    de retomber sur le modèle « factures » qui, lui, aurait chiffré. Faiblesse
    jumelle : la garde de fraîcheur était SAUTÉE quand la puissance valait 0.
(b) le cashflow 25 ans ne retranche aucun coût d'exploitation et ne provisionne
    ni dégradation ni remplacement de BATTERIE — alors que son rendement
    aller-retour EST modélisé et que l'onduleur, lui, est provisionné. Aucun de
    ces deux montants n'existe dans le dépôt : ils sont ÉNONCÉS (règle
    fondateur — jamais un chiffre inventé).
(c) ``cashflow_assumptions`` publiait les CONSTANTES du module alors que
    ``compute_cashflow_payback`` accepte ``years``/``degradation``/
    ``escalation``/``inverter_replace_year`` en arguments.
(d) ``_DEFAULT_PRODUCTIBLE`` valait 1240 quand le repli canonique du dépôt est
    ``productible.DEFAULT_PRODUCTIBLE`` (1651) : −25 % sur « Production estimée
    ≈ N kWh par kWc et par an », atteint uniquement par deux ``except``
    **muets** du builder.
(e) la dichotomie plafonnait à 1e6 et rendait ≈ 1 024 000 kWh/mois avec
    ``estimation: False`` sur une facture hors plage ; deux docstrings
    affirmaient ``approximatif`` « TOUJOURS False » alors que la branche de
    repli renvoie True.

Fonctions PURES : aucune base de données, aucun WeasyPrint — exécutable sur
l'hôte.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr158_pricing_replis -v 2
"""
import ast
import inspect
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine import builder, pricing, productible


def bloc_horaire(**surcharges):
    """Bloc ``etude_params['etude_horaire']`` minimal mais VALIDE."""
    mois = [{"economie_sans_mad": 100.0, "economie_avec_mad": 130.0,
             "facture_avant_mad": 400.0} for _ in range(12)]
    bloc = {
        "kwc": 5.68,
        "annuel": {
            "production_kwh": 8000.0,
            "consommation_kwh": 9000.0,
            "economie_sans_mad": 1200.0,
            "economie_avec_mad": 1560.0,
            "taux_autoconso_sans": 0.60,
            "taux_autoconso_avec": 0.85,
        },
        "mois": mois,
    }
    bloc.update(surcharges)
    return bloc


# ════════════════════════════════════════════════════════════════════════════
# (a) LE BLOC HORAIRE DOIT SAVOIR DIRE L'ÉCONOMIE
# ════════════════════════════════════════════════════════════════════════════

class TestA_GardeEconomies(SimpleTestCase):

    def test_le_bloc_nominal_reste_accepte(self):
        """Non-régression : rien ne change sur le chemin sain."""
        lu = pricing._lire_etude_horaire(bloc_horaire(), 5.68)
        self.assertIsNotNone(lu)
        self.assertEqual(lu["eco_sans"], 1200)
        self.assertEqual(lu["eco_avec"], 1560)

    def test_economies_absentes_le_bloc_est_refuse(self):
        for cle in ("economie_sans_mad", "economie_avec_mad"):
            with self.subTest(cle=cle):
                bloc = bloc_horaire()
                bloc["annuel"].pop(cle)
                self.assertIsNone(pricing._lire_etude_horaire(bloc, 5.68))

    def test_economies_nulles_ou_negatives_le_bloc_est_refuse(self):
        for cle in ("economie_sans_mad", "economie_avec_mad"):
            for valeur in (0, 0.0, -1.0):
                with self.subTest(cle=cle, valeur=valeur):
                    bloc = bloc_horaire()
                    bloc["annuel"][cle] = valeur
                    self.assertIsNone(pricing._lire_etude_horaire(bloc, 5.68))

    def test_le_document_retombe_sur_un_modele_qui_chiffre(self):
        """LE CONSTAT — un bloc mutilé imposait 'horaire' + 0 MAD ; désormais
        le calcul retombe sur un modèle qui produit une économie."""
        bloc = bloc_horaire()
        bloc["annuel"]["economie_sans_mad"] = 0
        roi = pricing.calculate_savings_roi(
            5.68, 100000, 130000, utility="onee",
            conso_annuelle_kwh=9000, etude_horaire=bloc)
        self.assertNotEqual(roi["savings_model"], "horaire")
        self.assertGreater(roi["eco_s_ann"], 0)

    def test_puissance_zero_la_garde_de_fraicheur_refuse(self):
        """``if puissance_kwc:`` sautait TOUTE la vérification à 0 : un bloc
        calculé pour une autre installation entrait sans contrôle."""
        self.assertIsNone(pricing._lire_etude_horaire(bloc_horaire(), 0))
        self.assertIsNone(pricing._lire_etude_horaire(bloc_horaire(), 0.0))

    def test_puissance_non_demandee_le_comportement_historique_tient(self):
        """``None`` = l'appelant ne DEMANDE pas la vérification de fraîcheur."""
        self.assertIsNotNone(pricing._lire_etude_horaire(bloc_horaire()))

    def test_puissance_divergente_toujours_refusee(self):
        """Non-régression de la garde CJ2a elle-même."""
        self.assertIsNone(pricing._lire_etude_horaire(bloc_horaire(), 9.0))


# ════════════════════════════════════════════════════════════════════════════
# (b) CE QUE LE CASHFLOW NE MODÉLISE PAS EST DIT
# ════════════════════════════════════════════════════════════════════════════

class TestB_OmissionsDites(SimpleTestCase):

    def test_les_couts_d_exploitation_sont_declares_non_deduits(self):
        notes = " ".join(pricing.cashflow_assumptions()["notes"])
        self.assertIn("exploitation", notes)
        self.assertIn("non déduits", notes)

    def test_la_batterie_non_provisionnee_est_declaree(self):
        notes = " ".join(
            pricing.cashflow_assumptions(stockage=True)["notes"])
        self.assertIn("remplacement de la batterie", notes)
        self.assertIn("Aucune perte de capacité", notes)

    def test_sans_stockage_aucune_note_batterie(self):
        """Non-régression : on ne parle pas d'un composant absent du devis."""
        notes = " ".join(
            pricing.cashflow_assumptions(stockage=False)["notes"])
        self.assertNotIn("batterie", notes)

    def test_l_omission_batterie_ne_cree_aucune_puce(self):
        """La page 3 est à hauteur fixe : l'aveu vit DANS la note du stockage,
        il n'ajoute pas un item à la liste."""
        sans = pricing.cashflow_assumptions(stockage=False)["notes"]
        avec = pricing.cashflow_assumptions(stockage=True)["notes"]
        self.assertEqual(len(avec), len(sans) + 1)   # la seule note 'Stockage'

    def test_aucun_montant_d_exploitation_n_est_invente(self):
        """Règle fondateur : on DIT l'omission, on ne chiffre pas ce qu'on
        n'a pas — aucune note ne porte un montant d'O&M."""
        for note in pricing.cashflow_assumptions(stockage=True)["notes"]:
            if "exploitation" in note or "capacité" in note:
                self.assertNotIn("MAD", note)


# ════════════════════════════════════════════════════════════════════════════
# (c) LE BLOC PUBLIÉ DÉCRIT LE CALCUL RÉELLEMENT FAIT
# ════════════════════════════════════════════════════════════════════════════

class TestC_HypothesesReelles(SimpleTestCase):

    def test_les_quatre_parametres_sont_publies_tels_que_passes(self):
        h = pricing.cashflow_assumptions(
            inverter_replace_cost=16000,
            years=15, degradation=0.01, escalation=0.02,
            inverter_replace_year=10)
        self.assertEqual(h["years"], 15)
        self.assertEqual(h["degradation_pct"], 1.0)
        self.assertEqual(h["escalation_pct"], 2.0)
        self.assertEqual(h["inverter_replace_year"], 10)
        notes = " ".join(h["notes"])
        self.assertIn("année 10", notes)
        self.assertIn("1 %/an", notes.replace(" ", " "))
        # Escalade NON nulle : la note ne peut plus annoncer un tarif constant.
        self.assertNotIn("tarif constant", notes)
        self.assertIn("hausse du tarif électrique supposée", notes)

    def test_les_defauts_reproduisent_le_comportement_historique(self):
        h = pricing.cashflow_assumptions()
        self.assertEqual(h["years"], pricing.CASHFLOW_YEARS)
        self.assertEqual(h["degradation_pct"],
                         round(pricing.PANEL_DEGRADATION * 100, 2))
        self.assertEqual(h["escalation_pct"],
                         round(pricing.TARIFF_ESCALATION * 100, 1))
        self.assertEqual(h["inverter_replace_year"],
                         pricing.INVERTER_REPLACE_YEAR)
        self.assertIn("tarif constant", " ".join(h["notes"]))

    def test_le_bloc_du_devis_decrit_bien_sa_propre_projection(self):
        """``calculate_savings_roi`` définit les paramètres UNE fois : la durée
        annoncée est celle de la courbe qu'il publie."""
        roi = pricing.calculate_savings_roi(
            5.0, 100000, 130000, tarif_kwh_override=1.5)
        h = roi["cashflow_assumptions"]
        self.assertEqual(h["years"], len(roi["cashflow_sans"]))
        self.assertEqual(h["years"], len(roi["cashflow_avec"]))


# ════════════════════════════════════════════════════════════════════════════
# (d) UN SEUL REPLI DE PRODUCTIBLE, ET LES DEUX ``except`` PARLENT
# ════════════════════════════════════════════════════════════════════════════

class TestD_ProductibleCanonique(SimpleTestCase):

    def test_le_repli_est_celui_du_depot(self):
        self.assertEqual(pricing._DEFAULT_PRODUCTIBLE,
                         productible.DEFAULT_PRODUCTIBLE)

    def test_la_production_de_repli_ne_perd_plus_25_pourcent(self):
        roi = pricing.calculate_savings_roi(10.0, 100000, 120000)
        attendu = round(10.0 * productible.DEFAULT_PRODUCTIBLE
                        * pricing.PRODUCTION_DERATE)
        self.assertEqual(roi["prod_kwh"], attendu)
        # Le chiffre d'avant (1240) est bien celui qu'on ne publie plus.
        self.assertNotEqual(
            roi["prod_kwh"],
            round(10.0 * 1240 * pricing.PRODUCTION_DERATE))

    def test_les_deux_except_du_builder_journalisent(self):
        """PREUVE PAR LECTURE DE SOURCE — les deux ``except Exception`` qui
        mènent au repli de productible étaient MUETS : une production publiée
        25 % trop basse était indistinguable d'un calcul normal. Ils appellent
        désormais ``logger.warning``.

        On les identifie par ce que leur ``try`` importe, jamais par un numéro
        de ligne (qui dériverait au premier ajout au-dessus)."""
        source = Path(inspect.getsourcefile(builder)).read_text(
            encoding="utf-8")
        arbre = ast.parse(source)
        attendus = {"tariff_for", "productible_for_city"}
        trouves = set()
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Try):
                continue
            importes = {
                alias.name
                for n in ast.walk(noeud)
                if isinstance(n, ast.ImportFrom)
                for alias in n.names
            }
            cible = importes & attendus
            if not cible:
                continue
            journalise = any(
                isinstance(n, ast.Attribute) and n.attr == "warning"
                and isinstance(n.value, ast.Name) and n.value.id == "logger"
                for h in noeud.handlers for n in ast.walk(h))
            self.assertTrue(
                journalise,
                f"le repli de {cible} est encore muet dans builder.py")
            trouves |= cible
        self.assertEqual(trouves, attendus,
                         "les deux replis de productible n'ont pas été trouvés")


# ════════════════════════════════════════════════════════════════════════════
# (e) UNE FACTURE HORS PLAGE N'EST PAS UN RÉSULTAT
# ════════════════════════════════════════════════════════════════════════════

class TestE_FactureHorsPlage(SimpleTestCase):

    #: Facture qu'aucune consommation ≤ ``_BISSECTION_KWH_MAX`` ne produit.
    HORS_PLAGE = 5e9

    def test_la_bissection_rend_none_hors_plage(self):
        self.assertIsNone(pricing._kwh_from_bill_bisect(
            self.HORS_PLAGE, pricing.ONEE_TRANCHES))

    def test_kwh_from_bill_etiquette_estimation_hors_plage(self):
        out = pricing.kwh_from_bill(self.HORS_PLAGE, utility="onee")
        self.assertTrue(out["estimation"])
        self.assertEqual(out["kwh_mensuel"], 0.0)
        self.assertEqual(out["label"], pricing.ESTIMATION_LABEL)

    def test_plus_jamais_la_borne_de_boucle_presentee_comme_exacte(self):
        """LE CONSTAT — ≈ 1 024 000 kWh/mois sortait avec estimation=False."""
        out = pricing.kwh_from_bill(self.HORS_PLAGE, utility="onee")
        self.assertLess(out["kwh_mensuel"], pricing._BISSECTION_KWH_MAX)
        self.assertFalse(out["kwh_mensuel"] > 100000)

    def test_les_inversions_nominales_sont_inchangees(self):
        """Non-régression : l'inverse épinglé du barème sélectif ne bouge pas."""
        for bill, attendu in ((235.0, 210.0), (150.5, 150.0),
                              (1135.9992, 700.0)):
            with self.subTest(bill=bill):
                self.assertAlmostEqual(
                    pricing.kwh_from_bill(bill, utility="onee")["kwh_mensuel"],
                    attendu, places=1)

    def test_une_grosse_facture_reelle_reste_inversable(self):
        """La borne ne doit pas refuser un vrai client industriel."""
        out = pricing.kwh_from_bill(50000.0, utility="onee")
        self.assertFalse(out["estimation"])
        self.assertGreater(out["kwh_mensuel"], 0)

    def test_les_docstrings_ne_promettent_plus_toujours_false(self):
        """(e) — « approximatif : TOUJOURS False » était démenti par la branche
        de repli sans table, qui renvoie True."""
        for fonction in (pricing.kwh_from_bill, pricing.annual_bill_from_kwh):
            with self.subTest(fonction=fonction.__name__):
                doc = fonction.__doc__ or ""
                self.assertNotIn("TOUJOURS False", doc)
                self.assertNotIn("toujours False", doc)
        sans_table = pricing.kwh_from_bill(500.0, utility="inconnu")
        self.assertTrue(sans_table["estimation"])
        self.assertEqual(sans_table["approximatif"],
                         sans_table["estimation"])
