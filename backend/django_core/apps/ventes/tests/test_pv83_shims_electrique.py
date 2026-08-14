"""PV83 (ARC6) — les shims ``apps.ventes`` → ``core.electrique``.

Ce module ARME deux garanties opposées, et c'est voulu :

1. **``string_design`` est bien un SHIM** : sa physique (bornes de fenêtre,
   découpe en chaînes égales) vient du noyau ``core.electrique.chaines``, et sa
   charge utile historique reste identique clé pour clé.
2. **``generate_boq`` et ``single_line_diagram`` ne le sont PAS**, faute de
   pouvoir l'être sans changer le comportement. Les tests ci-dessous ÉPINGLENT
   la divergence : si quelqu'un « simplifie » un jour en branchant l'historique
   sur le noyau, ils deviennent rouges au lieu de laisser passer un changement
   silencieux de bordereau ou de schéma.

Calcul pur — aucune base, ``SimpleTestCase``.

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pv83_shims_electrique -v 2
"""
import math

from django.test import SimpleTestCase

from apps.ventes import single_line_diagram as sld
from apps.ventes import solar_design as sd
from core.electrique import concevoir
from core.electrique.chaines import concevoir_chaines, fenetre_admissible
from core.electrique.nomenclature import nomenclature_dict
from core.electrique.schema import rendre_schema

MODULE = {"vmp": 34, "voc": 41, "puissance_w": 550}
ONDULEUR = {"v_min": 90, "v_max": 1000, "v_mppt_min": 120,
            "v_mppt_max": 850, "n_mppt": 2, "ac_kw": 10}


def _entree(n, module=None, inverter=None,
            cold=sd.DEFAULT_COLD_TEMP_C, hot=sd.DEFAULT_HOT_TEMP_C):
    mod = {**sd.DEFAULT_MODULE, **(module or {})}
    inv = {**sd.DEFAULT_INVERTER_WINDOW, **(inverter or {})}
    n_mppt = max(1, int(inv.get("n_mppt") or 1))
    return sd._entree_electrique_du_dict(mod, inv, n, n_mppt, cold, hot)


class StringDesignEstUnShimTest(SimpleTestCase):
    """La physique publiée par ``string_design`` EST celle du noyau."""

    def test_tensions_unitaires_viennent_du_noyau(self):
        res = sd.string_design(24, module=MODULE, inverter=ONDULEUR)
        fenetre = fenetre_admissible(
            _entree(24, MODULE, ONDULEUR).module,
            _entree(24, MODULE, ONDULEUR).onduleur,
            sd.DEFAULT_COLD_TEMP_C, sd.DEFAULT_HOT_TEMP_C)
        longueur = res["panels_per_string"]
        self.assertEqual(res["voltages"]["voc_cold"],
                         round(fenetre.voc_froid_unitaire_v * longueur, 1))
        self.assertEqual(res["voltages"]["vmp_cold"],
                         round(fenetre.vmp_froid_unitaire_v * longueur, 1))
        self.assertEqual(res["voltages"]["vmp_hot"],
                         round(fenetre.vmp_chaud_unitaire_v * longueur, 1))

    def test_decoupe_identique_a_celle_du_noyau(self):
        for n in (6, 12, 16, 18, 20, 24, 30, 36):
            with self.subTest(n=n):
                res = sd.string_design(n, module=MODULE, inverter=ONDULEUR)
                noyau = concevoir_chaines(_entree(n, MODULE, ONDULEUR))
                repartition = noyau.repartitions[0]
                self.assertEqual(res["panels_per_string"],
                                 repartition.longueur_chaine)
                self.assertEqual(res["strings"], repartition.nb_chaines)

    def test_tension_de_demarrage_reste_distincte_du_bas_de_plage(self):
        # ``v_min`` (démarrage) ≠ ``v_mppt_min`` : le shim doit passer les deux
        # bornes au noyau, sinon la longueur minimale change.
        entree = _entree(20, MODULE, ONDULEUR)
        self.assertEqual(entree.onduleur.tension_demarrage_v,
                         float(ONDULEUR["v_min"]))
        self.assertEqual(entree.onduleur.mppt_v_min,
                         float(ONDULEUR["v_mppt_min"]))

    def test_helpers_re_exportent_le_noyau(self):
        from core.electrique.chaines import _choisir_longueur
        from core.electrique.types import _tension_a_temperature
        for args in ((24, 2, 6, 20), (23, 2, 6, 20), (30, 3, 5, 15)):
            with self.subTest(args=args):
                self.assertEqual(sd._choose_string_layout(*args),
                                 _choisir_longueur(*args))
        self.assertEqual(sd._voltage_at_temp(41.0, -0.27, -5.0),
                         _tension_a_temperature(41.0, -0.27, -5.0))
        # dérive linéaire : à froid la tension MONTE, à chaud elle baisse
        self.assertGreater(sd._voltage_at_temp(41.0, -0.27, -5.0), 41.0)
        self.assertLess(sd._voltage_at_temp(41.0, -0.27, 70.0), 41.0)

    def test_charge_utile_historique_intacte(self):
        res = sd.string_design(24, module=MODULE, inverter=ONDULEUR)
        self.assertEqual(
            set(res),
            {"n_panels", "n_mppt", "strings", "panels_per_string",
             "string_layout", "dc_kw", "ac_kw", "dc_ac_ratio", "voltages",
             "checks", "ok", "warnings"})
        self.assertEqual(
            set(res["checks"]),
            {"voc_cold_under_vmax", "vmp_cold_under_mppt_max",
             "vmp_hot_over_mppt_min", "vmp_hot_over_vmin"})

    def test_dc_kw_compte_tous_les_panneaux(self):
        # Divergence ASSUMÉE : le noyau ne compte que la puissance mise en
        # chaîne, l'historique compte tous les panneaux (réserve comprise).
        res = sd.string_design(23, module=MODULE, inverter=ONDULEUR)
        self.assertAlmostEqual(res["dc_kw"], round(23 * 550 / 1000.0, 3), 3)

    def test_repli_non_homogene_compte_au_plafond(self):
        # Fenêtre étroite : aucune découpe égale → repli historique au plafond.
        res = sd.string_design(
            23, module=MODULE,
            inverter={**ONDULEUR, "v_mppt_max": 400, "n_mppt": 1})
        if res["strings"] * res["panels_per_string"] != 23:
            self.assertEqual(
                res["strings"],
                int(math.ceil(23 / res["panels_per_string"])))
            self.assertTrue(any("non homogène" in w for w in res["warnings"]))

    def test_jamais_de_prix_dans_la_sortie(self):
        res = sd.string_design(24, module=MODULE, inverter=ONDULEUR)
        blob = repr(res).lower()
        for interdit in ("prix", "marge", "prix_achat"):
            self.assertNotIn(interdit, blob)


class BordereauxDivergentsTest(SimpleTestCase):
    """``generate_boq`` ≠ ``nomenclature_dict`` — divergence DOCUMENTÉE."""

    def test_meme_forme_de_sortie(self):
        legacy = sd.generate_boq(n_panels=20, kwc=11.0, phases=1)
        noyau = nomenclature_dict(_entree(20, MODULE, ONDULEUR))
        self.assertEqual(set(legacy), set(noyau))
        self.assertEqual(set(legacy["summary"]), set(noyau["summary"]))

    def test_designations_historiques_epinglees(self):
        res = sd.generate_boq(n_panels=20, kwc=11.0, phases=1)
        designations = [it["designation"] for it in res["items"]]
        self.assertTrue(any(d.startswith("Sectionneur-fusible")
                            for d in designations))
        self.assertIn("Parafoudre DC Type 2", designations)
        self.assertTrue(any(d.startswith("Rail") for d in designations))
        specs = {it["designation"]: it["spec"] for it in res["items"]}
        self.assertEqual(specs["Crochet / patte de fixation toiture"],
                         "selon couverture (tuile/bac acier)")
        self.assertEqual(specs["Câble de terre cuivre nu 25 mm²"],
                         "liaison équipotentielle structure + masses")

    def test_calibre_ac_reste_entier_plafonne(self):
        res = sd.generate_boq(n_panels=400, kwc=220.0, phases=1)
        self.assertIsInstance(res["summary"]["ac_breaker_amp"], int)
        self.assertLessEqual(res["summary"]["ac_breaker_amp"], 160)

    def test_le_noyau_omet_les_organes_non_exiges(self):
        # La preuve que brancher l'un sur l'autre CHANGERAIT le bordereau :
        # sur liaison DC courte, le noyau ne pose aucun parafoudre DC.
        resultat = concevoir(_entree(20, MODULE, ONDULEUR))
        reperes = {p.repere for p in resultat.protections}
        self.assertNotIn("PDC1", reperes)
        legacy = sd.generate_boq(n_panels=20, kwc=11.0)
        self.assertIn("Parafoudre DC Type 2",
                      [it["designation"] for it in legacy["items"]])


class SchemasDivergentsTest(SimpleTestCase):
    """``build_single_line_svg`` (v1) ≠ ``rendre_schema`` (v2) — assumé."""

    def test_v1_reste_la_planche_de_cinq_blocs(self):
        svg = sld.build_single_line_svg(
            {"n_panneaux": 24, "puissance_panneau_wc": 550,
             "puissance_onduleur_kw": 10, "phases": 3})
        self.assertIn('viewBox="0 0 980 260"', svg)
        for bloc in ("Panneaux PV", "String(s) DC", "Comptage",
                     "ONEE (réseau)"):
            self.assertIn(bloc, svg)

    def test_v2_dessine_la_chaine_canonique(self):
        entree = _entree(20, MODULE, ONDULEUR)
        svg = rendre_schema(entree, concevoir(entree))
        self.assertNotIn('viewBox="0 0 980 260"', svg)
        self.assertIn("Onduleur", svg)

    def test_aucun_des_deux_ne_publie_de_prix(self):
        entree = _entree(20, MODULE, ONDULEUR)
        for svg in (sld.build_single_line_svg({"n_panneaux": 20}),
                    rendre_schema(entree, concevoir(entree))):
            blob = svg.lower()
            self.assertNotIn("prix", blob)
            self.assertNotIn("marge", blob)
