"""CIQ345 — PDF industriel de 4 pages en arabe et en anglais.

HTML réel (``render.build_html``) d'un devis industriel COMPLET (étude C&I MT,
argent avec VAN et revente, financement, sensibilités, bloc bancable,
jalons, services, entreprise, signature) : en ``ar`` et en ``en``, aucun
libellé français du catalogue ``i18n_labels`` (les clés ``ci_*`` et les clés
génériques employées sont parcourues) ; ``dir="rtl"`` en arabe ; le
français est inchangé ; les chiffres ne changent pas d'une langue à l'autre.
Les DONNÉES (désignations, noms, CGV de la société, bande légale, offre de
financement saisie, sources servies par le moteur) ne sont pas traduites :
elles sont retirées du HTML avant la recherche. PDF réel : 4 pages.
"""
import re

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine import i18n_labels as L
from apps.ventes.quote_engine.ci import blocs as ci_blocs
from apps.ventes.quote_engine.figures import extract_figures
from apps.ventes.quote_engine.industriel import render, renderer, sample_data
from apps.ventes.quote_engine.residential import theme

_GABARIT = re.compile(r"\{[a-z_]+\}")

CLES_GENERIQUES = ("designation", "qte", "pu_ht", "total_ht",
                   "sous_total_ht", "remise", "arrondi", "tva", "total_ttc",
                   "bon_pour_accord", "bpa_date", "reference")
CLES = sorted(c for c in L.LIBELLES if c.startswith("ci_")) \
    + list(CLES_GENERIQUES)


def _data(langue=None):
    d = sample_data.build()
    d["totaux_all"] = {"ht_brut": 1458333.33, "remise": 0,
                       "ht_net": 1458333.33, "tva": 291666.67,
                       "ttc": 1750000}
    bloc = sample_data.economie_ci("exemple_industriel_mt")
    bloc["sensibilites"] = [
        {"cle": "indexation_tarif", "variation_pct": 2.0, "retour_ans": 4,
         "tri_pct": 29.1},
        {"cle": "production", "variation_pct": -10.0, "retour_ans": 5,
         "tri_pct": 24.2}]
    d["economie_ci"] = bloc
    d["etude"] = dict(d["etude"], bankable={"pr": {"p90_kwh": 312500}})
    d["jalons_paiement"] = [
        {"jalon": "commande", "libelle": "Commande", "pct": 30,
         "montant_ttc": 525000.0},
        {"jalon": "livraison_materiel", "libelle": "x", "pct": 40,
         "montant_ttc": 700000.0},
        {"jalon": "mise_en_service", "libelle": "x", "pct": 20,
         "montant_ttc": 350000.0},
        {"jalon": "reception_definitive", "libelle": "x", "pct": 10,
         "montant_ttc": 175000.0}]
    d["om_ci_lignes"] = [{"designation": "Contrat O&M annuel", "ht": 12000,
                          "ttc": 14400, "optionnelle": True}]
    d["entreprise_client"] = {"raison_sociale": "Atlas Froid SARL",
                              "ice": "001", "siege": "Fès"}
    d["valid_until"] = "05/11/2026"
    if langue:
        d["langue_sortie"] = langue
    return d


def _html(d):
    return render.build_html(renderer._augment(d))


def _donnees(d):
    """Les textes SAISIS ou SERVIS par le moteur (jamais traduits)."""
    valeurs = [it["designation"] for it in d["all_items"]]
    valeurs += ci_blocs.puces_conditions(d)
    valeurs += [theme.bande_legale(d, theme.company_identity(d)),
                d["client_name"], "Contrat O&M annuel", "Atlas Froid SARL"]
    eco = d["economie_ci"]
    valeurs += [eco["financement"]["libelle_client"],
                eco["financement"]["source"]]
    for flux in (eco.get("flux_ht"), eco.get("flux_ttc")):
        for h in (flux or {}).get("hypotheses") or []:
            if h.get("source"):
                valeurs.append(h["source"])
    for h in eco.get("hypotheses") or []:
        valeurs += [str(h.get("valeur") or ""), str(h.get("source") or "")]
    for r in eco.get("remplacements") or []:
        valeurs.append(r.get("motif") or "")
    return [v for v in valeurs if v]


def _html_sans_donnees(d):
    html = _html(d)
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    html = re.sub(r"data:[^\"')]+", "", html)
    for valeur in sorted(_donnees(d), key=len, reverse=True):
        html = html.replace(valeur, "")
    return html


def _morceaux_francais(cle, autre):
    fr = L.LIBELLES[cle]["fr"]
    if fr == L.LIBELLES[cle][autre]:
        return []
    return [m.strip() for m in _GABARIT.split(fr)
            if len(m.strip()) >= 4 and m.strip() not in
            L.LIBELLES[cle][autre]]


@tag("weasyprint")  # rendu PDF réel
class Ciq345LanguesIndustriel(SimpleTestCase):

    def _aucun_libelle_francais(self, langue):
        texte = re.sub(r"<[^>]+>", " ", _html_sans_donnees(_data(langue)))
        for cle in CLES:
            for morceau in _morceaux_francais(cle, langue):
                with self.subTest(langue=langue, cle=cle, morceau=morceau):
                    self.assertNotIn(morceau, texte)

    def test_arabe_rtl_sans_libelle_francais(self):
        self._aucun_libelle_francais("ar")
        html = _html(_data("ar"))
        self.assertIn('<html lang="ar" dir="rtl">', html)
        self.assertIn(L.libelle("ci_ind_synthese", "ar"), html)
        self.assertIn(L.libelle("ci_ind_rentabilite_sur", "ar").format(
            n="25"), html)

    def test_anglais_sans_libelle_francais(self):
        self._aucun_libelle_francais("en")
        html = _html(_data("en"))
        self.assertIn('<html lang="en" dir="ltr">', html)
        self.assertIn("IRR over 25 years", html)
        self.assertIn("Payment schedule", html)

    def test_francais_inchange(self):
        html = _html(_data())
        self.assertIn("<!doctype html><html><head>", html)
        for fr in ("Synthèse", "Rentabilité sur 25 ans",
                   "Échéancier de paiement", "Valeur pour l'entreprise"):
            self.assertIn(fr, html)
        self.assertEqual(_html(_data("de")), html)

    def test_les_chiffres_ne_changent_pas(self):
        def _valeurs(langue):
            return {i: sorted(str(m.valeur) for m in ms)
                    for i, ms in extract_figures(_html(_data(langue))).items()}
        fr = _valeurs(None)
        self.assertIn("tri_pct", fr)
        for langue in ("en", "ar"):
            with self.subTest(langue=langue):
                self.assertEqual(_valeurs(langue), fr)

    def test_quatre_pages_dans_les_trois_langues(self):
        """Le document LIVRÉ (``equip.document_adaptatif``, la décision de
        ``render_pdf_bytes`` : blocs cédables retirés dans l'ordre
        ``ORDRE_CEDABLES`` plutôt qu'une 5ᵉ page) fait 4 pages et AUCUNE ne
        descend sous le pied, dans les trois langues."""
        from weasyprint import HTML

        from apps.ventes.quote_engine.commercial.equip import (
            deborde, document_adaptatif,
        )
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                doc = document_adaptatif(
                    renderer._augment(_data(langue)), render.build_html,
                    lambda html: HTML(string=html).render())
                self.assertIsNotNone(doc)
                self.assertEqual(len(doc.pages), 4)
                self.assertFalse(any(deborde(page) for page in doc.pages))


#: AMOT84 — textes DYNAMIQUES français que le moteur sert ou imprime.
MOTIFS_VISITE_FR = (
    "site MT : visite avant le devis final", "tension de raccordement inconnue",
    "puissance souscrite inconnue", "surface disponible inconnue",
    "profil horaire non déclaré : estimation sous réserve de visite")
MOTIF_SENSIBILITE_FR = "charge horaire déclarée absente"


class Amot84TextesDynamiquesIndustriel(SimpleTestCase):
    """AMOT84 — en ``en`` / ``ar`` : ni MENTION_MT, ni motif de réserve de
    visite, ni motif de sensibilité, ni « ans » / « HT » du une-page en
    français ; le français est inchangé."""

    def _avec_motifs(self, langue):
        d = _data(langue)
        etude_ci = dict(d["etude"].get("etude_ci") or {})
        etude_ci["sous_reserve_visite"] = {"valeur": True, "motif": (
            "site MT : visite avant le devis final (D-CIQ-5); tension de "
            "raccordement inconnue; puissance souscrite inconnue; surface "
            "disponible inconnue; profil horaire non déclaré : estimation "
            "sous réserve de visite")}
        d["etude"] = dict(d["etude"], etude_ci=etude_ci)
        d["economie_ci"]["sensibilites"].append(
            {"cle": "production", "variation_pct": 5.0, "retour_ans": None,
             "motif": ("charge horaire déclarée absente : production non "
                       "recalculable heure par heure — scénario non chiffré")})
        return _html(d)

    def test_motifs_traduits_en_et_ar(self):
        for langue in ("en", "ar"):
            html = self._avec_motifs(langue)
            for fr in MOTIFS_VISITE_FR + (MOTIF_SENSIBILITE_FR,):
                with self.subTest(langue=langue, fr=fr):
                    self.assertNotIn(fr, html)
        # Décision fondateur 26/10/2026 — la liste « À confirmer : … » (les
        # motifs de réserve de visite) n'est plus imprimée, en aucune langue.
        self.assertNotIn("site survey before the final quote",
                         self._avec_motifs("en"))

    def test_francais_inchange_sans_code_interne(self):
        html = self._avec_motifs(None)
        self.assertIn(MOTIF_SENSIBILITE_FR, html)
        # Décision fondateur 26/10/2026 — motifs de réserve non imprimés.
        for fr in MOTIFS_VISITE_FR:
            self.assertNotIn(fr, html)
        self.assertNotIn("À confirmer", html)
        self.assertNotIn("D-CIQ-5", html)

    def test_mention_mt_dans_la_langue_du_document(self):
        from apps.ventes.quote_engine.ci.mentions import mention_tarif_mt
        from apps.ventes.quote_engine.constants_82_21 import MENTION_MT
        grille = {"origine": "grille_officielle"}
        self.assertEqual(mention_tarif_mt(grille), MENTION_MT)
        self.assertEqual(mention_tarif_mt(grille, langue="fr"), MENTION_MT)
        for langue in ("en", "ar"):
            with self.subTest(langue=langue):
                texte = mention_tarif_mt(grille, langue=langue)
                self.assertNotIn("Barème", texte)
                self.assertNotIn("relevé le", texte)
                self.assertIn("03/10/2026", texte)

    def test_une_page_ans_et_ht_traduits(self):
        from apps.ventes.tests.test_ciq210_onepage_ci import _onepage
        _d, fr = _onepage("industriel")
        # CPDF7 — le retour au dixième sur le flux servi (« 2,5 ans »).
        self.assertIn(">2,5 ans<", fr)
        self.assertNotIn(">3 ans<", fr)
        self.assertIn("/ an (HT)<", fr)
        # CPDF — arabe : « سنة » pour un retour décimal (RPDF7).
        for langue, ans, ht in (("en", " years", "(excl. VAT)"),
                                ("ar", " سنة", "(دون احتساب الضريبة)")):
            with self.subTest(langue=langue):
                _d, html = _onepage("industriel", langue_sortie=langue)
                self.assertIn(ans, html)
                self.assertIn(ht, html)
                self.assertNotIn(">2,5 ans<", html)
                self.assertNotIn("MAD/an<", html)


class CpdfAccordsGarantiesUnePage(SimpleTestCase):
    """CPDF — « ans » accordé en arabe (« سنة » hors 3..10 ans entiers),
    garantie par option dite « sans / avec batterie », une-page C&I signé."""

    def test_ans_accordes_en_arabe(self):
        from apps.ventes.quote_engine.ci import couverture
        ar = {"langue_sortie": "ar"}
        self.assertIn("سنة", couverture.unite_ans(ar, "2,5"))
        self.assertNotIn("سنوات", couverture.unite_ans(ar, "12"))
        self.assertIn("سنوات", couverture.unite_ans(ar, "4"))
        self.assertEqual(couverture.unite_ans({}, "2,5"), "&nbsp;ans")

    def test_garantie_par_option_nommee(self):
        self.assertEqual(
            ci_blocs.textes_garantie({}, "ans", "Onduleur (option 1)", "10"),
            ("ans", "Onduleur (sans batterie)"))
        en = ci_blocs.textes_garantie({"langue_sortie": "en"}, "ans",
                                      "Onduleur (option 2)", "5")
        self.assertEqual(en, ("years", "Inverter (with battery)"))
        ar = ci_blocs.textes_garantie({"langue_sortie": "ar"}, "ans",
                                      "Onduleur", "12")
        self.assertIn("سنة", ar[0])
        self.assertNotIn("سنوات", ar[0])

    def test_une_page_porte_le_bon_pour_accord(self):
        from apps.ventes.tests.test_ciq210_onepage_ci import _onepage
        _d, fr = _onepage("industriel")
        self.assertIn("Bon pour accord", fr)
        self.assertIn("signature du client", fr)


class Amot101FormatAnglaisIndustriel(SimpleTestCase):
    """AMOT101 (D-ACI-21=a) — l'industriel en ``en`` : montants au centime
    « 1,750,000.00 », TRI « 39.8 % », cumul du tableau des 25 ans au format
    anglais ; FR et AR inchangés ; une-page EN au format anglais aussi."""

    def test_anglais_format_anglais(self):
        from apps.ventes.quote_engine.montants import fmt_centimes
        d = renderer._augment(_data())
        ttc = d["_invest_ttc"]
        tri = d["ind_synthese"]["argent"]["indicateurs"]["tri_pct"]
        from apps.ventes.tests.test_ciq333_commercial_langues import visible
        en, fr, ar = (visible(_html(_data(langue)))
                      for langue in ("en", None, "ar"))
        self.assertIn(f"{ttc:,.2f}", en)
        self.assertIn(f"{tri:.1f}", en)
        self.assertNotIn(fmt_centimes(ttc), en)
        for html in (fr, ar):
            self.assertIn(fmt_centimes(ttc), html)
            self.assertIn(f"{tri:.1f}".replace(".", ","), html)

    def test_retour_au_dixieme_point_en_anglais(self):
        """CPDF7 — flux MT servi : cumul nul vers 3,7 ans (retour servi :
        4) ⇒ « 3.7 years » en anglais, « 3,7 » en français et en arabe."""
        en = _html(_data("en")).split('class="page"')[1]
        self.assertIn(">3.7<", en)
        for langue in (None, "ar"):
            self.assertIn(">3,7<", _html(_data(langue)).split(
                'class="page"')[1])

    def test_une_page_anglaise(self):
        from apps.ventes.tests.test_ciq210_onepage_ci import _onepage
        data, en = _onepage("industriel", langue_sortie="en")
        _data_fr, fr = _onepage("industriel")
        kwc = f"{float(data['puissance_kwc']):.2f}".rstrip("0").rstrip(".")
        self.assertIn(f"{kwc} kWp", en)
        self.assertIn(kwc.replace(".", ",") + " kWc", fr)
