"""CIQ331 — PDF commercial : 3 pages complétées du retour sur investissement,
de la production annuelle, de l'échéancier et de la validité (D-CIQ-9).

Rendu RÉEL (gabarit + WeasyPrint) sur la fixture commerciale, enrichie de la
sortie du moteur C&I (contrat ``etude_ci_preview.json``), du bloc PUBLIC
``economie_ci`` (contrat ``economie_ci.json``) et des N jalons de paiement
servis par le builder (CIQ212, ``jalons_paiement``).
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase, tag

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine.ci.categories import CATEGORIES
from apps.ventes.quote_engine.ci.synthese import (
    MOTIF_ARGENT_MT, chiffres_cles, synthese_ci)
from apps.ventes.quote_engine.commercial import render, renderer, sample_data
from apps.ventes.quote_engine.figures import extract_figures

from ._moteur_fixtures import etude_ci_au_kwc_servi

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"


def _contrat(nom):
    return json.loads((_CONTRATS / nom).read_text(encoding="utf-8"))


ETUDE_CI = _contrat("etude_ci_preview.json")
ECONOMIE_CI = _contrat("economie_ci.json")

JALONS = [
    {"jalon": "commande", "libelle": "Commande", "pct": 40,
     "montant_ttc": 256000.0},
    {"jalon": "livraison_materiel", "libelle": "Livraison du matériel",
     "pct": 50, "montant_ttc": 320000.0},
    {"jalon": "mise_en_service", "libelle": "Mise en service", "pct": 10,
     "montant_ttc": 64000.0},
]


def _data(categorie="hotel", *, argent=True, lignes=None, tension=None,
          etude_ci=True):
    data = copy.deepcopy(sample_data.build(categorie))
    etude = dict(data["etude"])
    if etude_ci:
        etude["etude_ci"] = copy.deepcopy(ETUDE_CI["exemple"])
    if tension:
        etude["tension_raccordement"] = tension
    data["etude"] = etude
    if argent:
        data["economie_ci"] = economie_ci_publique(
            copy.deepcopy(ECONOMIE_CI["exemple"]))
    data["jalons_paiement"] = copy.deepcopy(JALONS)
    data["valid_until"] = "05/11/2026"
    if lignes:
        modele = data["all_items"][0]
        data["all_items"] = [dict(modele, designation=f"Article {i}")
                             for i in range(lignes)]
    return etude_ci_au_kwc_servi(data)


def _html(data):
    return render.build_html(renderer._augment(data))


def _pages(data):
    import fitz
    pdf = renderer.render_pdf_bytes(data)
    return [p.get_text() for p in fitz.open(stream=pdf, filetype="pdf")]


def _cles(html):
    return {i.split("@")[0] for i in extract_figures(html)}


@tag("weasyprint")  # rendu PDF réel
class Ciq331DocumentChiffre(SimpleTestCase):

    def test_payback_production_et_jalons(self):
        data = _data()
        pages = _pages(data)
        self.assertEqual(len(pages), 3)
        chiffres = chiffres_cles(synthese_ci(data))
        p1 = pages[0]
        self.assertIn("Production annuelle", p1)
        self.assertIn("95 425", p1.replace(" ", " ").replace(
            "\xa0", " "))
        self.assertIn("Retour estimé", p1)
        self.assertIn("Valable jusqu", p1)
        self.assertEqual(chiffres["payback_ans"], 3)
        p3 = pages[2].replace(" ", " ").replace("\xa0", " ")
        self.assertIn("Échéancier de paiement", p3)
        for montant in ("256 000,00", "320 000,00", "64 000,00"):
            self.assertIn(montant, p3)
        for libelle in ("À la commande", "À la livraison",
                        "À la mise en service"):
            self.assertIn(libelle, p3)

    def test_ancres_payback_et_production(self):
        html = _html(_data())
        cles = _cles(html)
        self.assertIn("payback_ans", cles)
        self.assertIn("production_annuelle_kwh", cles)

    def test_financement_servi_puis_conditions(self):
        data = _data()
        eco = copy.deepcopy(ECONOMIE_CI["exemple"])
        eco["financement"] = copy.deepcopy(
            ECONOMIE_CI["exemple_industriel_mt"]["financement"])
        data["economie_ci"] = economie_ci_publique(eco)
        html = _html(data)
        p3 = html.split('class="page"')[3]
        self.assertIn("Offre de financement", p3)
        self.assertLess(p3.index("Échéancier de paiement"),
                        p3.index("Offre de financement"))
        self.assertLess(p3.index("Offre de financement"),
                        p3.index("Bon pour accord"))


@tag("weasyprint")  # rendu PDF réel
class Ciq331SansArgent(SimpleTestCase):

    def test_motif_et_aucun_zero(self):
        html = _html(_data(argent=False))
        p1 = html.split('class="page"')[1]
        self.assertIn("vos 12 dernières factures", p1)
        self.assertNotIn("0&nbsp;MAD", p1)
        self.assertNotIn(">0<", p1)
        cles = _cles(html)
        self.assertNotIn("economie_annuelle", cles)
        self.assertNotIn("payback_ans", cles)

    def test_mt_sans_factures(self):
        html = _html(_data(argent=False, tension="mt", etude_ci=False))
        self.assertNotIn("répartition horaire", html)
        self.assertIn(MOTIF_ARGENT_MT, html)
        self.assertEqual(len(_pages(_data(argent=False, tension="mt",
                                          etude_ci=False))), 3)


@tag("weasyprint")  # rendu PDF réel
class Ciq331TroisPages(SimpleTestCase):

    def test_dix_categories(self):
        from weasyprint import HTML
        self.assertEqual(len(CATEGORIES), 10)
        for categorie in CATEGORIES:
            with self.subTest(categorie=categorie):
                doc = HTML(string=_html(_data(categorie))).render()
                self.assertEqual(len(doc.pages), 3)

    def test_quarante_lignes(self):
        self.assertEqual(len(_pages(_data(lignes=40))), 3)


class Ciq331EcheancierN(SimpleTestCase):

    def test_quatre_jalons_servis_tels_quels(self):
        data = _data()
        data["jalons_paiement"] = [
            {"jalon": "commande", "libelle": "Commande", "pct": 30,
             "montant_ttc": 192000.0},
            {"jalon": "livraison_materiel", "libelle": "x", "pct": 40,
             "montant_ttc": 256000.0},
            {"jalon": "mise_en_service", "libelle": "x", "pct": 20,
             "montant_ttc": 128000.0},
            {"jalon": "reception_definitive", "libelle": "x", "pct": 10,
             "montant_ttc": 64000.0},
        ]
        ech = synthese_ci(data)["echeancier"]
        self.assertEqual([j["jalon"] for j in ech],
                         ["commande", "livraison", "mise_en_service",
                          "reception_definitive"])
        self.assertEqual([j["pct"] for j in ech], [30, 40, 20, 10])
        self.assertEqual(sum(j["montant_ttc"] for j in ech), 640000)
        self.assertEqual(set(ech[0]), {"libelle", "pct", "montant_ttc",
                                       "jalon"})

    def test_sans_jalons_repli_sur_les_trois_creneaux(self):
        data = _data()
        data.pop("jalons_paiement")
        ech = synthese_ci(data)["echeancier"]
        self.assertEqual([j["jalon"] for j in ech],
                         ["commande", "livraison", "mise_en_service"])


class Amot81OrigineDuTarif(SimpleTestCase):
    """AMOT81 — la couverture commerciale dit l'origine du prix du kWh quand
    c'est la grille de repli (jamais sur une facture déclarée) ; la tension
    d'un brouillon auto (clé ``tension``) est lue comme la saisie d'écran."""

    def _page1(self, data):
        return _html(data).split('class="page"')[1]

    def test_ligne_grille_sur_repli_absente_sur_facture(self):
        p1 = self._page1(_data())
        # AMOT88 — en mots du client : ni « repli », ni « capture ».
        self.assertIn("Tarif ONEE BT publié", p1)
        # Décision fondateur 26/10/2026 — sans la réserve interne.
        self.assertNotIn("à confirmer sur votre facture", p1)
        for mot in ("repli", "capture", "reconfirm"):
            self.assertNotIn(mot, p1)
        data = _data()
        data["economie_ci"]["tarif"]["origine"] = "declare_facture"
        self.assertNotIn("Tarif ONEE", _html(data))

    def test_date_de_la_grille_dite(self):
        data = _data()
        for poste in data["economie_ci"]["tarif"]["tarifs_par_poste"]:
            poste["releve_le"] = "2025-02-16"
        self.assertIn("Tarif ONEE BT publié (grille du 16/02/2025).",
                      self._page1(data))

    def test_tension_lue_sous_ses_deux_cles(self):
        for tension in ("mt", "bt"):
            data = _data(argent=False, etude_ci=False)
            data["etude"]["tension"] = tension
            html = _html(data)
            with self.subTest(tension=tension):
                if tension == "mt":
                    self.assertIn(MOTIF_ARGENT_MT, html)
                else:
                    self.assertNotIn(MOTIF_ARGENT_MT, html)
                    self.assertIn("vos 12 dernières factures", html)


class Amot83Raccordement8221(SimpleTestCase):
    """AMOT83 (D-ACI-11=a) — régime 82-21 calculé ⇒ la phrase fixe « dossier
    monté et suivi par » la société (jamais le texte de loi) ; sans régime ⇒
    absente ; la pose se fait « en coordination avec votre activité »."""

    PHRASE = ("Raccordement et autorisations du site&#160;: dossier monté et "
              "suivi par TAQINOR")

    def test_accord_de_raccordement_ligne_imprimee(self):
        self.assertEqual(_data()["etude"]["etude_ci"]["regime_8221_suggere"][
            "regime"], "accord_raccordement")
        html = _html(_data())
        self.assertIn(self.PHRASE, html)
        self.assertNotIn("décret 2.25.100", html)

    def test_sans_regime_ligne_absente(self):
        data = _data()
        data["etude"]["etude_ci"]["regime_8221_suggere"] = {"regime": None}
        self.assertNotIn("dossier monté et suivi", _html(data))

    def test_en_coordination_avec_votre_activite(self):
        html = _html(_data())
        self.assertIn("en coordination avec votre activité", html)
        self.assertNotIn("sans interrompre", html)


# ── Fondateur 26/10/2026 — UNE ligne « Installation clé en main » ──────────
#: Les 8 prestations C&I (rôle produit ``role_ci``), Σ HT = 90 000 : le
#: même montant que la ligne « Installation » de l'échantillon.
PRESTATIONS = [
    ("etudes_ingenierie", "Études et ingénierie C&I", 1, 10000.0),
    ("pose_structure", "Pose de la structure C&I", 1, 15000.0),
    ("pose_modules", "Pose des modules C&I", 1, 20000.0),
    ("raccordement_ac", "Raccordement AC C&I", 1, 12000.0),
    ("mise_en_service", "Mise en service C&I", 1, 8000.0),
    ("dossier_raccordement", "Dossier de raccordement C&I", 1, 5000.0),
    ("levage_acces", "Levage et accès C&I", 2, 5000.0),
    ("transport_ci", "Transport C&I", 1, 10000.0),
]


def items_prestations(taux=20):
    return [{"designation": nom, "marque": "", "quantite": q,
             "prix_unit_ht": pu, "prix_unit_ttc": round(pu * 1.2, 2),
             "taux_tva": taux, "role_ci": role}
            for role, nom, q, pu in PRESTATIONS]


def avec_prestations(data, cle="all_items"):
    """``data`` dont la ligne « Installation » est remplacée par les 8
    prestations détaillées (mêmes totaux)."""
    data[cle] = [it for it in data[cle] if it["designation"] != "Installation"
                 ] + items_prestations()
    return data


class InstallationCleEnMain(SimpleTestCase):

    def test_le_pdf_commercial_regroupe_les_huit_prestations(self):
        from html import unescape
        html = unescape(_html(avec_prestations(_data())))
        for _role, nom, _q, _pu in PRESTATIONS:
            self.assertNotIn(nom, html)
        self.assertEqual(html.count("Installation clé en main"), 1)
        self.assertIn("90 000,00", html.replace("\u202f", " ")
                      .replace("\xa0", " "))

    def test_totaux_identiques_au_centime(self):
        avant = extract_figures(_html(_data()))
        apres = extract_figures(_html(avec_prestations(_data())))
        self.assertTrue(avant)
        self.assertEqual(
            {k: [m.valeur for m in v] for k, v in avant.items()},
            {k: [m.valeur for m in v] for k, v in apres.items()})

    def test_une_ligne_par_taux_de_tva_et_ttc_juste(self):
        from apps.ventes.quote_engine.ci.installation import (
            regrouper_installation)
        items = items_prestations()
        items[0] = dict(items[0], taux_tva=10)
        sortie = regrouper_installation(
            [{"designation": "Panneau", "quantite": 2, "prix_unit_ht": 1.0,
              "taux_tva": 10}] + items)
        self.assertEqual(sortie[0]["designation"], "Panneau")
        groupes = sortie[1:]
        self.assertEqual([g["taux_tva"] for g in groupes], [10, 20])
        self.assertEqual([g["prix_unit_ht"] for g in groupes],
                         [10000.0, 80000.0])
        self.assertEqual([g["prix_unit_ttc"] for g in groupes],
                         [11000.0, 96000.0])
        self.assertEqual({g["quantite"] for g in groupes}, {1.0})

    def test_libelle_trilingue_et_hors_ci_inchange(self):
        from apps.ventes.quote_engine.ci.installation import lignes_client
        items = items_prestations()
        for langue, libelle in (("fr", "Installation clé en main"),
                                ("en", "Turnkey installation"),
                                ("ar", "تركيب متكامل جاهز للتشغيل")):
            sortie = lignes_client(items, {"mode_installation": "industriel",
                                           "langue_sortie": langue})
            self.assertEqual([it["designation"] for it in sortie], [libelle])
        for mode in ("residentiel", "agricole", ""):
            self.assertIs(lignes_client(items, {"mode_installation": mode}),
                          items)

    def test_deux_options_regroupees_chacune(self):
        from apps.ventes.quote_engine.ci.installation import (
            regrouper_paniers)
        data = {"mode_installation": "commercial",
                "sans_items": items_prestations(),
                "avec_items": items_prestations()[:2]}
        regrouper_paniers(data)
        self.assertEqual([it["prix_unit_ht"] for it in data["sans_items"]],
                         [90000.0])
        self.assertEqual([it["prix_unit_ht"] for it in data["avec_items"]],
                         [25000.0])


# ── CPDF3 / CPDF5 / CPDF8 — couverture d'un devis C&I (27/10/2026) ─────────

def deux_options(data):
    """``data`` en devis « les deux » : l'offre réseau servie en titre et
    l'option batterie servie à côté (totaux, valeur chiffrée du moteur)."""
    data["option_servie"] = "sans"
    data["puissance_kwc_avec"] = 95.5
    data["option_batterie"] = {
        "totaux": {"ht_net": 800000.0, "ttc": 960000.0},
        "valeur_chiffree": {"economie_annuelle_mad": 120000.0,
                            "retour_simple_ans": 6.66,
                            "taux_couverture_pct": 61.4,
                            "textes": {"fr": "x", "en": "x", "ar": "x"}},
        "motif": None}
    return data


def _p1(data):
    import re
    from html import unescape
    html = _html(data).split('class="page"')[1]
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))
                  .replace("\xa0", " ").replace("\u202f", " "))


class Cpdf3DeuxOptionsCoteACote(SimpleTestCase):

    def test_deux_cartes_meme_gabarit(self):
        p1 = _p1(deux_options(_data()))
        sans, avec = p1.split("Sans batterie")[1].split("Avec batterie")
        for carte in (sans, avec):
            for libelle in ("Puissance", "Investissement TTC",
                            "Économie annuelle", "Retour sur investissement",
                            "Part de votre consommation couverte"):
                self.assertIn(libelle, carte)
        self.assertIn("90 kWc", sans)
        self.assertIn("640 000,00 MAD", sans)
        self.assertIn("95,5 kWc", avec)
        self.assertIn("960 000,00 MAD", avec)
        self.assertIn("120 000 MAD HT", avec)
        self.assertIn("6,7 ans", avec)
        self.assertIn("61 %", avec)

    def test_cartes_remplacent_bloc_investissement_et_tuiles(self):
        p1 = _p1(deux_options(_data()))
        self.assertNotIn("Investissement (clé en main)", p1)
        self.assertNotIn("Économies estimées", p1)
        self.assertNotIn("Puissance crête", p1)
        self.assertEqual(p1.count("640 000,00"), 1)
        cles = _cles(_html(deux_options(_data())))
        for cle in ("payback_ans", "economie_annuelle", "puissance_kwc",
                    "couverture_pct", "total_affiche"):
            self.assertIn(cle, cles)

    def test_valeur_absente_ligne_omise(self):
        data = deux_options(_data())
        data["option_batterie"]["valeur_chiffree"] = None
        data["option_batterie"]["motif"] = "valeur non chiffrée"
        avec = _p1(data).split("Avec batterie")[1]
        self.assertIn("960 000,00 MAD", avec)
        self.assertNotIn("Retour sur investissement",
                         avec.split("Prochaines")[0])

    def test_mono_option_inchangee(self):
        p1 = _p1(_data())
        self.assertNotIn("Sans batterie", p1)
        self.assertIn("Investissement (clé en main)", p1)
        self.assertIn("Puissance crête", p1)


@tag("weasyprint")  # rendu PDF réel
class Cpdf3TroisPages(SimpleTestCase):

    def test_deux_options_trois_pages(self):
        self.assertEqual(len(_pages(deux_options(_data()))), 3)


class Cpdf5Cpdf8Couverture(SimpleTestCase):

    def test_ni_scenario_prudent_ni_tva_non_declaree(self):
        p1 = _p1(_data())
        self.assertNotIn("scénario prudent", p1)
        self.assertNotIn("TVA récupérable non déclarée", p1)
        self.assertNotIn(" · ·", p1)

    def test_nom_une_fois_en_casse_saisie(self):
        data = _data()
        nom = "Démo — Boulangerie (7/7, 6-22 h)"
        data["client_full"] = data["client_name"] = nom
        p1 = _p1(data)
        self.assertEqual(p1.count(nom), 1)
        self.assertNotIn("6-22 H", p1)

    def test_kwh_an_insecable(self):
        html = _html(_data())
        self.assertIn(".c1c-ku{font-size:9pt;", html)
        self.assertIn("white-space:nowrap;}", html.split(".c1c-ku{")[1][:80])

    def test_activite_inconnue_sans_libelle_interne(self):
        html = _html(_data("autre"))
        self.assertNotIn("Autre commerce", _p1(_data("autre")))
        self.assertIn('class="c1c-kicker">Autoconsommation solaire', html)

    def test_source_echappee_traduite(self):
        from apps.ventes.quote_engine.ci.couverture import texte_client
        doc = {"langue_sortie": "fr"}
        for brut in ("etude_ci.bilan (moteur C&I)",
                     "etude_ci.bilan (moteur C&amp;I)"):
            self.assertNotIn("moteur", texte_client(doc, brut))
