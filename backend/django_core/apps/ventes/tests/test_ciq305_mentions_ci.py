"""CIQ305 — Mentions et hypothèses C&I : UNE table (``quote_engine/ci/
mentions.py``), sourcée et trilingue, servie à ``synthese_ci['hypotheses']``
et aux gabarits PDF commercial / industriel.

Tests PURS (``SimpleTestCase``) + rendu HTML réel des deux gabarits.
"""
import copy
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.quote_engine.ci.mentions import (
    TEXTES_POINTE_AVEC_NON_CHIFFREE,
    TEXTES_POINTE_SANS,
    mentions_ci,
    valeur_option_avec,
)
from apps.ventes.quote_engine.ci.synthese import synthese_ci
from apps.ventes.quote_engine.commercial import render as com_render
from apps.ventes.quote_engine.commercial import renderer as com_renderer
from apps.ventes.quote_engine.commercial import sample_data as com_sample
from apps.ventes.quote_engine.constants_82_21 import (
    MENTION_82_21,
    MENTION_ART13,
    MENTION_BT,
)
from apps.ventes.quote_engine.industriel import render as ind_render
from apps.ventes.quote_engine.industriel import renderer as ind_renderer
from apps.ventes.quote_engine.industriel import sample_data as ind_sample
from apps.ventes.tests.test_ciq303_synthese_ci_coeur import _data, _etude_ci

QUOTE_ENGINE = Path(__file__).resolve().parents[1] / "quote_engine"
COPIES_INTERDITES = ("net des frais réseau", "plafond en révision",
                     "heures les plus chères", "puissance souscrite lissée")


def _par_cle(entrees):
    return {e["cle"]: e for e in entrees}


def _etude(tension):
    etude = _etude_ci()
    etude["entrees_resolues"]["tension"]["valeur"] = tension
    return etude


class TestTableMentions(SimpleTestCase):

    def test_forme_trilingue_sourcee(self):
        for e in synthese_ci(_data(_etude("bt")))["hypotheses"]:
            self.assertEqual(set(e), {"cle", "textes", "source", "date"})
            self.assertEqual(set(e["textes"]), {"fr", "en", "ar"})
            self.assertTrue(all(e["textes"].values()))
            self.assertTrue(e["source"])

    def test_bt_ligne_bt_aucune_revente(self):
        h = _par_cle(mentions_ci(_data(_etude("bt"))))
        self.assertEqual(h["revente_bt"]["textes"]["fr"], MENTION_BT)
        self.assertNotIn("revente", h)
        self.assertEqual(h["contribution_art13"]["textes"]["fr"],
                         MENTION_ART13)
        self.assertNotIn("puissance_souscrite", h)

    def test_mt_avec_revente_mention_8221_lue(self):
        data = _data(_etude("mt"), mode_installation="industriel",
                     economie_ci={"statut": "calcule",
                                  "revente": {"statut": "calculee"}})
        h = _par_cle(mentions_ci(data))
        self.assertEqual(h["revente"]["textes"]["fr"], MENTION_82_21)
        self.assertNotIn("revente_bt", h)
        # Convention 2 : site MT ⇒ la puissance souscrite ne change pas.
        self.assertIn("puissance souscrite",
                      h["puissance_souscrite"]["textes"]["fr"])

    def test_mt_sans_revente_aucune_ligne_de_revente(self):
        h = _par_cle(mentions_ci(_data(_etude("mt"))))
        self.assertNotIn("revente", h)
        self.assertNotIn("revente_bt", h)

    def test_puissance_souscrite_declaree_en_bt(self):
        etude = _etude("bt")
        etude["entrees_resolues"]["puissance_souscrite_kva"] = {
            "valeur": 60, "provenance": None}
        self.assertIn("puissance_souscrite",
                      _par_cle(mentions_ci(_data(etude))))

    def test_note_pointe_selon_la_composition(self):
        sans = _par_cle(mentions_ci(_data(_etude("bt"))))["pointe"]
        self.assertEqual(sans["textes"], TEXTES_POINTE_SANS)
        avec = _par_cle(mentions_ci(_data(
            _etude("bt"), option_servie="avec")))["pointe"]
        self.assertEqual(avec["textes"], TEXTES_POINTE_AVEC_NON_CHIFFREE)
        self.assertNotIn("non promise", avec["textes"]["fr"])
        # Batterie différée (onduleur hybride sans batterie) : phrase « sans ».
        differee = _par_cle(mentions_ci(_data(
            _etude("bt"), option_servie="avec",
            avec_batterie_differee=True)))["pointe"]
        self.assertEqual(differee["textes"], TEXTES_POINTE_SANS)
        # Fondateur 27/10/2026 — un fait, jamais « non promise » ; l'offre
        # réseau d'un devis à deux options renvoie à l'option « avec ».
        self.assertEqual(TEXTES_POINTE_SANS["fr"],
                         "Le soir et la nuit, votre consommation reste fournie par le réseau.")
        # CPDF9 — sans part du soir servie par l'étude (aucun
        # ``option_avec``), la phrase perd sa seconde moitié.
        deux = _par_cle(mentions_ci(_data(
            _etude("bt"), option_servie="sans",
            option_batterie={"totaux": {}, "valeur_chiffree": None})))["pointe"]
        self.assertEqual(deux["textes"], TEXTES_POINTE_SANS)
        for textes in (sans["textes"], deux["textes"]):
            self.assertNotIn("non promise", textes["fr"])

    @staticmethod
    def _deux_options(restitue_kwh_an, besoin_nocturne_kwh=100):
        etude = _etude("bt")
        etude["option_avec"] = {
            "economie_annuelle_mad": 95767.0,
            "batterie": {"capacite_utile_kwh": 92.2,
                         "besoin_nocturne_kwh": besoin_nocturne_kwh},
            "bilan": {"batterie": {"capacite_utile_kwh": 92.2,
                                   "restitue_kwh_an": restitue_kwh_an}}}
        return _data(etude, option_servie="sans", option_batterie={
            "totaux": {"ht_net": 394250}, "valeur_chiffree": None})

    def test_cpdf9_phrase_soir_selon_la_part_couverte(self):
        # 100 kWh/jour hors production × 365 = 36 500 kWh/an.
        couvre = _par_cle(mentions_ci(self._deux_options(33000)))["pointe"]
        self.assertEqual(couvre["textes"]["fr"], (
            "Le soir et la nuit, votre consommation reste fournie par le "
            "réseau ; l'option avec batterie la couvre."))
        partie = _par_cle(mentions_ci(self._deux_options(13505)))["pointe"]
        self.assertEqual(partie["textes"]["fr"], (
            "Le soir et la nuit, votre consommation reste fournie par le "
            "réseau ; l'option avec batterie en couvre 37\u00a0%."))
        self.assertIn("covers 37% of it", partie["textes"]["en"])
        self.assertIn("37", partie["textes"]["ar"])
        self.assertNotIn("la couvre", partie["textes"]["fr"])
        # Besoin du soir non servi : la phrase sans sa seconde moitié.
        absent = _par_cle(mentions_ci(self._deux_options(
            31000, besoin_nocturne_kwh=None)))["pointe"]
        self.assertEqual(absent["textes"], TEXTES_POINTE_SANS)
        # Besoin du soir non servi (devis rafraîchi) : aucun repli sur les
        # taux de couverture globaux (critique Fable 28/10) — la phrase seule.
        data = self._deux_options(31000, besoin_nocturne_kwh=None)
        data["etude"]["etude_ci"].setdefault("bilan", {})[
            "taux_couverture"] = 0.52
        data["etude"]["etude_ci"]["option_avec"].setdefault("bilan", {})[
            "taux_couverture"] = 0.93
        repli = _par_cle(mentions_ci(data))["pointe"]
        self.assertEqual(repli["textes"], TEXTES_POINTE_SANS)

    def test_cpdf2_retour_option_avec_servi_jamais_recalcule(self):
        data = self._deux_options(31000)
        data["etude"]["etude_ci"]["option_avec"]["retour_simple_ans"] = 22.1
        valeur = valeur_option_avec(data)
        # Quotient HT ÷ économie = 4,1 ans : jamais imprimé.
        self.assertEqual(valeur["retour_simple_ans"], 22.1)
        del data["etude"]["etude_ci"]["option_avec"]["retour_simple_ans"]
        self.assertIsNone(valeur_option_avec(data)["retour_simple_ans"])

    def test_d_ci_batterie_non_rentable_badge_ligne_fr_en_ar(self):
        """D-CI-BATTERIE-NON-RENTABLE (fondateur 30/10/2026) — l'option
        marquée non rentable par l'étude (niveau 5) garde ses chiffres réels
        et reçoit le badge et la raison dans les trois langues, au PDF
        (bloc de l'option, carte de couverture) comme à /proposition."""
        from apps.ventes.quote_engine.ci.blocs import bloc_option_avec
        from apps.ventes.quote_engine.ci.options_cote import _badge_non_rentable
        data = self._deux_options(31000)
        avec = data["etude"]["etude_ci"]["option_avec"]
        avec["retour_simple_ans"] = 6.4
        self.assertNotIn("batterie_rentable", valeur_option_avec(data))
        avec.update(batterie_rentable=False, motif_non_rentable={
            "retour_marginal_ans": 13.6, "horizon_annees": 10,
            "code": "retour_au_dela_horizon"})
        valeur = valeur_option_avec(data)
        self.assertIs(valeur["batterie_rentable"], False)
        self.assertEqual((valeur["retour_marginal_ans"], valeur["horizon_annees"]),
                         (13.6, 10))
        self.assertEqual((valeur["economie_annuelle_mad"], valeur["retour_simple_ans"]),
                         (95767.0, 6.4))
        self.assertEqual(valeur["textes_badge"], {
            "fr": "non rentable sur les seuls critères financiers",
            "en": "not cost-effective on financial criteria alone",
            "ar": "غير مربح وفق المعايير المالية وحدها"})
        self.assertEqual(valeur["textes_non_rentable"]["fr"], (
            "Retour estimé 13,6 ans (remplacement batterie inclus), au-delà de "
            "l'horizon de 10 ans retenu : l'option solaire seule est recommandée."))
        self.assertEqual(valeur["textes_non_rentable"]["en"], (
            "Estimated payback 13.6 years (battery replacement included), beyond "
            "the 10-year horizon used: the solar-only option is recommended."))
        self.assertIn("13,6", valeur["textes_non_rentable"]["ar"])
        self.assertIn("10", valeur["textes_non_rentable"]["ar"])
        # PDF — bloc de l'option : titre + badge, chiffres réels, raison.
        data["option_batterie"] = {"totaux": {"ht_net": 394250, "tva": 78850,
                                              "ttc": 473100}, "lignes": []}
        for lg, badge, mot in (("fr", "non rentable", "remplacement batterie inclus"),
                               ("en", "not cost-effective", "battery replacement included"),
                               ("ar", "غير مربح", "استبدال البطارية")):
            data["langue_sortie"] = lg
            html = bloc_option_avec(data, lambda cle, fr: fr, lambda x: f"{x:,.0f}",
                                    ("#000", "#111", "#222", "#333"))
            self.assertIn(badge, html)
            self.assertIn(mot, html)
            self.assertIn("473,100", html)
            synthese = {"option_batterie": {"valeur_chiffree": valeur_option_avec(data)}}
            self.assertIn(badge, _badge_non_rentable({"com_synthese": synthese,
                                                      "langue_sortie": lg}, "com"))
        # Rentable : rien ne change.
        avec.pop("batterie_rentable")
        data["langue_sortie"] = "fr"
        html = bloc_option_avec(data, lambda cle, fr: fr, lambda x: f"{x:,.0f}",
                                ("#000", "#111", "#222", "#333"))
        self.assertNotIn("non rentable", html)
        self.assertEqual(_badge_non_rentable({"com_synthese": {"option_batterie": {
            "valeur_chiffree": valeur_option_avec(data)}}}, "com"), "")

    def test_niveau_13_batterie_non_remplacee_la_ligne_ne_le_dit_plus_inclus(self):
        """Fondateur 19/11/2026 (D-BATCYC-1) — quand le retour du supplément ne
        compte PAS le remplacement de la batterie (cycles publiés au-delà de
        l'horizon), l'étude sert ``remplacement_inclus: False`` et la ligne
        perd sa parenthèse, dans les trois langues."""
        data = self._deux_options(31000)
        data["etude"]["etude_ci"]["option_avec"].update(
            batterie_rentable=False, motif_non_rentable={
                "retour_marginal_ans": 12.4, "horizon_annees": 10,
                "code": "retour_au_dela_horizon", "remplacement_inclus": False})
        textes = valeur_option_avec(data)["textes_non_rentable"]
        self.assertEqual(textes["fr"], (
            "Retour estimé 12,4 ans, au-delà de l'horizon de 10 ans retenu : "
            "l'option solaire seule est recommandée."))
        self.assertEqual(textes["en"], (
            "Estimated payback 12.4 years, beyond the 10-year horizon used: "
            "the solar-only option is recommended."))
        for lg, mot in (("fr", "inclus"), ("en", "included"), ("ar", "استبدال")):
            self.assertNotIn(mot, textes[lg], lg)

    def test_d_hyb_5_onduleur_garde_pour_l_extension_fr_en_ar(self):
        """D-HYB-5 (fondateur 17/11/2026) — 1 batterie chiffrée sur 3
        calculées, hybride 20 kW gardé, un 15 kW suffirait : UNE phrase sous
        l'option « avec batterie » (bloc PDF, tableau deux options, synthèse
        web), dans les trois langues, faits servis seulement ; rien quand
        l'étude sert ``onduleur_extension`` null ou ne la sert pas."""
        from apps.ventes.quote_engine.ci.blocs import bloc_option_avec
        from apps.ventes.quote_engine.ci.mentions import extension_option_avec
        from apps.ventes.quote_engine.commercial.equip import tableau_deux_options
        data = self._deux_options(31000)
        avec = data["etude"]["etude_ci"]["option_avec"]
        avec["batterie"]["quantite"] = 1
        data["option_batterie"] = {"totaux": {"ht_net": 394250, "tva": 78850,
                                              "ttc": 473100}, "lignes": []}
        avant = {lg: bloc_option_avec(dict(data, langue_sortie=lg), lambda cle, fr: fr,
                                      lambda x: f"{x:,.0f}", ("#000", "#111", "#222", "#333"))
                 for lg in ("fr", "en", "ar")}
        self.assertIsNone(extension_option_avec(data))
        avec["onduleur_extension"] = None
        self.assertIsNone(extension_option_avec(data))
        self.assertIsNone(synthese_ci(data)["option_batterie"]["extension"])
        self.assertEqual(bloc_option_avec(dict(data, langue_sortie="fr"), lambda cle, fr: fr,
                                          lambda x: f"{x:,.0f}", ("#000", "#111", "#222", "#333")),
                         avant["fr"])
        avec["onduleur_extension"] = {
            "retenu": {"produit": 12, "nom": "Deye 20", "kw_ac": 20.0, "quantite": 1},
            "suffisant": {"produit": 11, "nom": "Deye 15", "kw_ac": 15.0, "quantite": 1},
            "batteries_max": 3}
        ext = extension_option_avec(data)
        self.assertEqual(ext["textes"]["fr"], (
            "Onduleur hybride 20 kW retenu pour l'extension : l'installation peut recevoir "
            "jusqu'à 3 batteries (2 à ajouter plus tard). Un onduleur de 15 kW suffirait "
            "pour l'installation de départ."))
        self.assertEqual(ext["textes"]["en"], (
            "20 kW hybrid inverter selected for expansion: the installation can take up to "
            "3 batteries (2 to add later). A 15 kW inverter would be enough for the initial "
            "installation."))
        for chiffre in ("20", "15", "3", "2"):
            self.assertIn(chiffre, ext["textes"]["ar"])
        self.assertEqual({k: ext[k] for k in ("retenu_kw", "suffisant_kw", "batteries_max",
                                              "batteries_a_ajouter")},
                         {"retenu_kw": 20.0, "suffisant_kw": 15.0, "batteries_max": 3,
                          "batteries_a_ajouter": 2})
        self.assertEqual(synthese_ci(data)["option_batterie"]["extension"], ext)
        for lg in ("fr", "en", "ar"):
            html = bloc_option_avec(dict(data, langue_sortie=lg), lambda cle, fr: fr,
                                    lambda x: f"{x:,.0f}", ("#000", "#111", "#222", "#333"))
            self.assertIn(ext["textes"][lg], html)
            self.assertNotEqual(html, avant[lg])
            duo = tableau_deux_options(dict(data, langue_sortie=lg), lambda cle, fr: fr,
                                       lambda x: f"{x:,.0f}", ("#000",) * 5,
                                       [{"designation": "Panneau", "quantite": 10}])
            self.assertIn(ext["textes"][lg], "".join(duo))   # fragments de la page 2
        # Plusieurs appareils : le pluriel ; banque déjà complète : rien.
        avec["onduleur_extension"]["retenu"]["quantite"] = 2
        avec["onduleur_extension"]["suffisant"]["quantite"] = 2
        self.assertTrue(extension_option_avec(data)["textes"]["fr"].startswith(
            "2 onduleurs hybrides de 20 kW retenus pour l'extension"))
        self.assertIn("2 onduleurs de 15 kW suffiraient", extension_option_avec(data)["textes"]["fr"])
        avec["batterie"]["quantite"] = 3
        self.assertIsNone(extension_option_avec(data))

    def test_tarif_utilise_et_sa_source(self):
        tarif = {"origine": "grille_officielle", "contrat": "bt_patente",
                 "mention": "Grille ONEE, repli",
                 "tarifs_par_poste": [{"releve_le": "2026-10-03"}]}
        h = _par_cle(mentions_ci(_data(
            _etude("bt"), economie_ci={"tarif": tarif})))
        # AMOT88 — le texte client dit « tarif officiel ONEE publié »,
        # jamais « repli » (le mot reste dans la source, interne).
        self.assertEqual(h["tarif"]["textes"]["fr"],
                         "Prix du kWh : tarif officiel ONEE publié, en "
                         "attendant la lecture de votre facture.")
        self.assertNotIn("repli", " ".join(h["tarif"]["textes"].values()))
        self.assertEqual(h["tarif"]["source"], "Grille ONEE, repli")
        self.assertEqual(h["tarif"]["date"], "2026-10-03")
        self.assertNotIn("tarif", _par_cle(mentions_ci(_data(_etude("bt")))))

    def test_releve_partiel_mention_estimation(self):
        # ADEV110 (C-ADEV-VER-006) — un relevé partiel (ADEV77) est dit au
        # client, trilingue et sourcé, AVANT la mention de visite.
        etude = _etude("bt")
        etude["sous_reserve_visite"] = {"valeur": True, "motif": None}
        etude["hypotheses"] = [{"cle": "consommation", "valeur": 48000.0,
                                "statut": "estimation",
                                "source": "relevé partiel (3 mois)"}]
        entrees = synthese_ci(_data(etude))["hypotheses"]
        cles = [e["cle"] for e in entrees]
        h = _par_cle(entrees)["consommation_estimee"]
        self.assertIn("estimation sur 3 mois relevés", h["textes"]["fr"])
        self.assertEqual(set(h["textes"]), {"fr", "en", "ar"})
        self.assertTrue(all("3" in t for t in h["textes"].values()))
        self.assertEqual(h["source"], "relevé partiel (3 mois)")
        self.assertLess(cles.index("consommation_estimee"), cles.index("visite"))
        # 12 mois relevés (aucune hypothèse d'estimation) : liste inchangée.
        sans = _etude("bt")
        sans["sous_reserve_visite"] = {"valeur": True, "motif": None}
        self.assertEqual([e for e in entrees if e["cle"] != "consommation_estimee"],
                         synthese_ci(_data(sans))["hypotheses"])

    def test_consommation_estimee_par_la_puissance_maximale_dite_au_client(self):
        # Fondateur 24/11/2026 — la consommation estimée depuis la puissance
        # maximale appelée est dite au client (même entrée, trilingue), sans
        # la formule interne ni la mention d'une décision du fondateur.
        from apps.ventes.domain.estimation_puissance_ci import estimer_consommation
        from apps.ventes.tests.test_ciq118_etude_ci_preview import RYTHME_HASNAOUI, _resolution
        hypotheses = []
        kwh, _feuille = estimer_consommation(
            _resolution(_puissance_max_kva=380, **RYTHME_HASNAOUI), 2025, [], hypotheses)
        self.assertEqual(len(kwh or []), 12)
        etude = _etude("mt")
        etude["sous_reserve_visite"] = {"valeur": True, "motif": None}
        etude["hypotheses"] = hypotheses
        h = _par_cle(synthese_ci(_data(etude))["hypotheses"])["consommation_estimee"]
        self.assertEqual(h["textes"]["fr"],
                         "Consommation : estimation à partir de la puissance maximale déclarée (380 kVA).")
        self.assertEqual(set(h["textes"]), {"fr", "en", "ar"})
        self.assertTrue(all("380" in t for t in h["textes"].values()))
        self.assertNotIn("fondateur", h["source"])

    def test_visite_si_sous_reserve(self):
        etude = _etude("bt")
        etude["sous_reserve_visite"] = {"valeur": True, "motif": None}
        h = _par_cle(synthese_ci(_data(etude))["hypotheses"])
        self.assertIn("visite technique", h["visite"]["textes"]["fr"])
        self.assertNotIn("visite", _par_cle(
            synthese_ci(_data(_etude("bt")))["hypotheses"]))


class TestGabaritsLisentLaTable(SimpleTestCase):

    def _avec_injection(self, sample):
        # CIQ129 — l'injection est celle du moteur C&I (``economie_ci.
        # revente`` calculée, contrat partagé), plus une clé d'étude écran.
        base = copy.deepcopy(sample.build())
        base["economie_ci"] = ind_sample.economie_ci()
        return base

    def test_rendu_reel_des_deux_gabarits(self):
        html_com = com_render.build_html(
            com_renderer._augment(self._avec_injection(com_sample)))
        html_ind = ind_render.build_html(
            ind_renderer._augment(self._avec_injection(ind_sample)))
        for html in (html_com, html_ind):
            self.assertIn(MENTION_82_21, html)
            for copie in COPIES_INTERDITES:
                self.assertNotIn(copie, html)

    def test_releve_partiel_imprime_dans_les_deux_gabarits(self):
        # ADEV110 (rejeu FAIL du 04/11, P6.pdf_releve_partiel) — la mention
        # servie à ``synthese_ci['hypotheses']`` est IMPRIMÉE dans la note
        # client de la couverture commerciale ET industrielle ; 12 mois : rien.
        partiel = {"hypotheses": [{"cle": "consommation", "valeur": 48000.0,
                                   "statut": "estimation",
                                   "source": "relevé partiel (3 mois)"}]}
        for sample, renderer, render, note in (
                (com_sample, com_renderer, com_render, 'class="c1c-note"'),
                (ind_sample, ind_renderer, ind_render, 'class="i1-note"')):
            base = self._avec_injection(sample)
            base["etude"]["etude_ci"] = copy.deepcopy(partiel)
            html = render.build_html(renderer._augment(base))
            bloc = html[html.index(note):]
            bloc = bloc[:bloc.index("</div>")]
            self.assertIn("estimation sur 3 mois relevés", bloc)
            sans = render.build_html(renderer._augment(
                self._avec_injection(sample)))
            self.assertNotIn("mois relevés", sans)

    def test_aucune_copie_8221_dans_le_moteur(self):
        for chemin in QUOTE_ENGINE.rglob("*.py"):
            if chemin.name == "mentions.py":
                continue
            source = chemin.read_text(encoding="utf-8")
            for copie in COPIES_INTERDITES[:2]:
                self.assertNotIn(copie, source, msg=str(chemin))
