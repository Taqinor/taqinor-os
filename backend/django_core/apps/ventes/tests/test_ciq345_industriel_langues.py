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
        from weasyprint import HTML

        from apps.ventes.quote_engine.commercial.equip import deborde
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                doc = HTML(string=_html(_data(langue))).render()
                self.assertEqual(len(doc.pages), 4)
                self.assertFalse(deborde(doc.pages[2]))
