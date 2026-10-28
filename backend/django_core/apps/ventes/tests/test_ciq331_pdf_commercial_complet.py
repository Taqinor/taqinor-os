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
        # CPDF7 — au dixième sur le flux servi (3 ans servis, 2,5 au flux).
        self.assertEqual(chiffres["payback_ans"], 2.5)
        self.assertIn("2,5", p1)
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

    def test_vingt_trois_categories(self):
        # Décision fondateur 26-27/10/2026 : les 23 activités du lead, chacune
        # rend son PDF commercial en 3 pages.
        from weasyprint import HTML
        self.assertEqual(len(CATEGORIES), 23)
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


# ── R2 (fondateur 28/10/2026) — UNE ligne « Tableau de protection AC/DC » ──
#: Les organes C&I du tableau (rôle produit ``role_ci`` de
#: ``ROLES_TABLEAU_CI``), Σ HT = 7 800 ; le câble AC (``cable_ac``) n'en fait
#: PAS partie et reste une ligne à part.
ORGANES = [
    ("coffret_dc", "Coffret DC C&I", 2, 1500.0),
    ("protection_ac", "Disjoncteur AC 63 A (C&I)", 2, 400.0),
    ("protection_dc", "Protection DC (fusibles / sectionneur) par MPPT", 2, 150.0),
    ("protection_dc", "Parafoudre DC par onduleur", 1, 200.0),
    ("protection_ac", "Parafoudre AC", 1, 300.0),
    ("mise_a_la_terre", "Mise à la terre du champ PV", 1, 900.0),
    ("compteur_injection", "Comptage / limitation d'injection", 1, 1800.0),
    ("coffret_ac", "Coffret AC C&I", 1, 500.0),
]
CABLE_AC = {"designation": "Câble AC 16 mm²", "marque": "", "quantite": 30,
            "prix_unit_ht": 50.0, "prix_unit_ttc": 60.0, "taux_tva": 20,
            "role_ci": "cable_ac"}


def items_organes(taux=20):
    return [{"designation": nom, "marque": "", "quantite": q,
             "prix_unit_ht": pu, "prix_unit_ttc": round(pu * 1.2, 2),
             "taux_tva": taux, "role_ci": role}
            for role, nom, q, pu in ORGANES]


def avec_organes(data, cle="all_items"):
    """``data`` + les 8 organes du tableau et le câble AC (mêmes totaux
    qu'un devis qui les porterait : les figures du document sont comparées
    entre le rendu groupé et le rendu ligne à ligne)."""
    data[cle] = list(data[cle]) + items_organes() + [dict(CABLE_AC)]
    return data


class TableauProtectionAcDc(SimpleTestCase):

    def test_regroupement_pur(self):
        from apps.ventes.quote_engine.ci.tableau import regrouper_tableau
        items = [{"designation": "Panneau", "quantite": 2, "prix_unit_ht": 1.0,
                  "taux_tva": 10, "ordre": 0}] + items_organes() + [dict(CABLE_AC)]
        for i, it in enumerate(items):
            it.setdefault("ordre", i)
        sortie = regrouper_tableau(items)
        self.assertEqual([it["designation"] for it in sortie],
                         ["Panneau", "Tableau de protection AC/DC", "Câble AC 16 mm²"])
        tableau = sortie[1]
        self.assertEqual(tableau["role_ci"], "tableau_ci")
        self.assertEqual(tableau["quantite"], 1.0)
        self.assertEqual(tableau["prix_unit_ht"], 7800.0)
        self.assertEqual(tableau["prix_unit_ttc"], 9360.0)
        self.assertEqual(tableau["ordre"], 1)
        self.assertEqual(
            [(sl["designation"], sl["quantite"]) for sl in tableau["sous_lignes"]],
            [(nom, float(q)) for _r, nom, q, _pu in ORGANES])
        self.assertTrue(all("prix" not in cle for sl in tableau["sous_lignes"]
                            for cle in sl))
        # Sans organe : le même objet ; les lignes d'origine ne sont pas mutées.
        seul = items[:1]
        self.assertIs(regrouper_tableau(seul), seul)
        self.assertEqual(items[1]["designation"], "Coffret DC C&I")

    def test_une_ligne_par_taux_de_tva(self):
        from apps.ventes.quote_engine.ci.tableau import regrouper_tableau
        items = items_organes()
        items[0] = dict(items[0], taux_tva=10)
        groupes = regrouper_tableau(items)
        self.assertEqual([g["taux_tva"] for g in groupes], [10, 20])
        self.assertEqual([g["prix_unit_ht"] for g in groupes], [3000.0, 4800.0])
        self.assertEqual([len(g["sous_lignes"]) for g in groupes], [1, 7])

    def test_libelle_trilingue_jargon_et_hors_ci(self):
        from apps.ventes.quote_engine.ci.installation import lignes_client
        items = items_organes()
        for langue, libelle in (("fr", "Tableau de protection AC/DC"),
                                ("en", "AC/DC protection switchboard"),
                                ("ar", "لوحة الحماية AC/DC")):
            sortie = lignes_client(items, {"mode_installation": "commercial",
                                           "langue_sortie": langue})
            self.assertEqual([it["designation"] for it in sortie], [libelle])
            # CPDF — « C&I » retiré AUSSI des sous-lignes.
            self.assertEqual(sortie[0]["sous_lignes"][0]["designation"],
                             "Coffret DC")
            self.assertEqual(sortie[0]["sous_lignes"][1]["designation"],
                             "Disjoncteur AC 63 A")
        for mode in ("residentiel", "agricole", ""):
            self.assertIs(lignes_client(items, {"mode_installation": mode}),
                          items)
        self.assertEqual(items[0]["designation"], "Coffret DC C&I")

    def test_tableau_et_installation_regroupes_ensemble(self):
        from apps.ventes.quote_engine.ci.installation import lignes_client
        sortie = lignes_client(items_organes() + items_prestations(),
                               {"mode_installation": "industriel"})
        self.assertEqual([it["designation"] for it in sortie],
                         ["Tableau de protection AC/DC",
                          "Installation clé en main"])
        self.assertEqual([it["prix_unit_ht"] for it in sortie],
                         [7800.0, 90000.0])
        self.assertNotIn("sous_lignes", sortie[1])

    def test_charge_utile_publique_regroupee_par_panier(self):
        from apps.ventes.quote_engine.ci.installation import regrouper_paniers
        data = {"mode_installation": "commercial",
                "sans_items": items_organes(),
                "avec_items": items_organes()[:3],
                "option_batterie": {"lignes": items_organes()[:2]}}
        regrouper_paniers(data)
        self.assertEqual(len(data["sans_items"]), 1)
        self.assertEqual(data["sans_items"][0]["prix_unit_ht"], 7800.0)
        self.assertEqual(len(data["sans_items"][0]["sous_lignes"]), 8)
        self.assertEqual(data["avec_items"][0]["prix_unit_ht"], 4100.0)
        self.assertEqual(data["option_batterie"]["lignes"][0]["prix_unit_ht"],
                         3800.0)
        # Les totaux ne sont jamais recalculés ici : aucune clé ``totaux_*``
        # n'est posée.
        self.assertFalse([k for k in data if k.startswith("totaux")])

    def test_le_pdf_commercial_imprime_une_ligne_et_le_detail(self):
        from html import unescape
        html = _html(avec_organes(_data()))
        u = unescape(html)
        self.assertEqual(u.count("Tableau de protection AC/DC"), 1)
        self.assertEqual(html.count('class="ci-sl"'), len(ORGANES))
        for _role, nom, _q, _pu in ORGANES:
            # Jamais une rangée à part entière, toujours en sous-ligne.
            self.assertNotIn(f'<td class="c2-d">{nom}', u)
        self.assertIn("2&#160;×&#160;Coffret DC<", html)
        self.assertNotIn("C&amp;I", html)
        self.assertIn('<td class="c2-d">Câble AC 16 mm²', u)
        self.assertIn("7 800,00", u.replace("\u202f", " ").replace("\xa0", " "))

    def test_totaux_identiques_ligne_a_ligne_ou_groupes(self):
        from apps.ventes.quote_engine.ci import tableau
        sans = avec_organes(_data())
        avec = avec_organes(_data())
        for it in sans["all_items"]:
            it.pop("role_ci", None)  # ligne à ligne : aucun regroupement
        self.assertEqual(
            {k: [m.valeur for m in v] for k, v in extract_figures(_html(sans)).items()},
            {k: [m.valeur for m in v] for k, v in extract_figures(_html(avec)).items()})
        self.assertEqual(tableau.sous_lignes_html({"sous_lignes": []}, 6, "#000"), "")

    def test_une_page_legacy_detail_echappe(self):
        """Le une-page (moteur legacy) imprime la ligne regroupée et ses
        sous-lignes, échappées UNE fois (ERR37 : l'échappement précède le
        regroupement)."""
        from ._moteur_fixtures import html_onepage
        organes = items_organes()
        organes[5] = dict(organes[5], designation="Mise à la terre <PV>")
        html = html_onepage(mode_installation="commercial",
                            all_items=list(_data()["all_items"]) + organes)
        self.assertEqual(html.count("Tableau de protection AC/DC"), 1)
        self.assertEqual(html.count('class="ci-sl"'), len(ORGANES))
        self.assertIn("&lt;PV&gt;", html)
        self.assertNotIn("<PV>", html)
        self.assertNotIn("C&amp;I", html)


def avec_remise_globale(items, pct):
    """Les items annotés comme le builder les sert sous une remise globale
    (QJRREM, ``_annoter_remise``) : totaux remisés au prorata, au centime."""
    coef = 1 - pct / 100.0
    sortie = []
    for it in items:
        qte = float(it["quantite"])
        total_ht = round(qte * float(it["prix_unit_ht"]) * coef, 2)
        taux = float(it.get("taux_tva") or 0)
        sortie.append(dict(
            it, pu_ht_remise=round(total_ht / qte, 2), total_ht_remise=total_ht,
            pu_ttc_remise=round(total_ht / qte * (1 + taux / 100), 2),
            total_ttc_remise=round(total_ht * (1 + taux / 100), 2)))
    return sortie


class TableauProtectionRemiseGlobale(SimpleTestCase):
    """R2 (revue) — la remise globale répartie par le builder survit au
    regroupement : « Tableau de protection AC/DC » ET « Installation clé en
    main » impriment leur total REMISÉ, jamais le catalogue."""

    def test_regroupement_porte_la_remise(self):
        from apps.ventes.quote_engine.ci.installation import lignes_client
        # 10 % sur 7 800 (organes) et 90 000 (prestations), à la main.
        items = avec_remise_globale(items_organes() + items_prestations(), 10)
        tableau, installation = lignes_client(
            items, {"mode_installation": "commercial"})
        self.assertEqual(tableau["prix_unit_ht"], 7800.0)
        self.assertEqual(tableau["pu_ht_remise"], 7020.0)
        self.assertEqual(tableau["total_ht_remise"], 7020.0)
        self.assertEqual(tableau["total_ttc_remise"], 8424.0)
        self.assertEqual(installation["prix_unit_ht"], 90000.0)
        self.assertEqual(installation["pu_ht_remise"], 81000.0)
        self.assertEqual(installation["total_ttc_remise"], 97200.0)
        # Sans annotation du builder : aucune clé remise (repli catalogue).
        nu = lignes_client(items_organes(), {"mode_installation": "commercial"})
        self.assertNotIn("pu_ht_remise", nu[0])

    def test_pdf_commercial_imprime_le_remise_et_barre_le_catalogue(self):
        from html import unescape
        data = _data()
        data["all_items"] = avec_remise_globale(
            list(data["all_items"]) + items_organes() + items_prestations(), 10)
        data["totaux_all"] = dict(data["totaux_all"], remise=1.0)
        import re
        u = unescape(_html(data)).replace("\u202f", " ").replace("\xa0", " ")
        u = re.sub(r'<div class="ci-sl".*?</div>', "", u)  # la rangée sans son détail
        ligne = u[u.find("Tableau de protection AC/DC"):][:600]
        self.assertIn("7 800,00", ligne)   # catalogue, barré
        self.assertIn("7 020,00", ligne)   # remisé, imprimé
        ligne = u[u.find("Installation clé en main"):][:600]
        self.assertIn("81 000,00", ligne)

    def test_une_page_legacy_imprime_le_remise(self):
        from ._moteur_fixtures import html_onepage
        items = avec_remise_globale(list(_data()["all_items"]) + items_organes(), 10)
        html = html_onepage(mode_installation="commercial", all_items=items,
                            discount_pct=10.0)
        import re
        u = html.replace("\u202f", " ").replace("\xa0", " ").replace("&#160;", " ")
        u = re.sub(r'<div class="ci-sl".*?</div>', "", u)
        ligne = u[u.find("Tableau de protection AC/DC"):][:900]
        self.assertIn("7 020", ligne)


@tag("weasyprint")  # rendu PDF réel
class TableauProtectionTroisPages(SimpleTestCase):

    def test_une_page_ci_avec_les_huit_sous_lignes_ne_deborde_pas(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine import generate_devis_premium as legacy
        from ._moteur_fixtures import html_onepage
        html = html_onepage(mode_installation="commercial",
                            all_items=list(_data()["all_items"])
                            + items_organes() + items_prestations())
        self.assertEqual(html.count('class="ci-sl"'), len(ORGANES))
        self.assertEqual(len(HTML(string=html).render().pages), 1)
        mesure = legacy._mesure_onepage(html)
        self.assertIsNotNone(mesure)
        self.assertEqual(mesure[0], 0.0)

    def test_trois_pages_avec_tableau_et_installation(self):
        data = avec_organes(avec_prestations(_data()))
        self.assertEqual(len(_pages(data)), 3)
        data = avec_organes(avec_prestations(_data(lignes=30)))
        self.assertEqual(len(_pages(data)), 3)
