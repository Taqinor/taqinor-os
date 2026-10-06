"""CIQ333 — PDF commercial en arabe et en anglais : libellés structurels par
``i18n_labels``, mise en page de droite à gauche pour l'arabe.

HTML réel (``render.build_html``) d'un devis commercial COMPLET (étude C&I,
argent, financement, services, entreprise, options, signature) : en ``ar``
et en ``en``, aucun libellé français du catalogue (les clés ``ci_*`` et les
clés génériques que les pages emploient sont parcourues) ; ``dir="rtl"`` en
arabe ; le français est inchangé. Les DONNÉES saisies (désignations, noms,
CGV de la société, bande légale, offre de financement) ne sont jamais
traduites : elles sont retirées du HTML avant la recherche. PDF réel :
3 pages dans les trois langues.
"""
import copy
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes.economie_ci import economie_ci_publique
from apps.ventes.quote_engine import i18n_labels as L
from apps.ventes.quote_engine.ci import blocs as ci_blocs
from apps.ventes.quote_engine.commercial import render, renderer, sample_data
from apps.ventes.quote_engine.residential import theme

_CONTRATS = Path(__file__).resolve().parents[1] / "contract_samples"
_GABARIT = re.compile(r"\{[a-z_]+\}")


def _contrat(nom):
    return json.loads((_CONTRATS / nom).read_text(encoding="utf-8"))


ETUDE_CI = _contrat("etude_ci_preview.json")
ECONOMIE_CI = _contrat("economie_ci.json")

#: Clés génériques du catalogue que les pages commerciales emploient.
CLES_GENERIQUES = ("designation", "qte", "pu_ht", "total_ht",
                   "sous_total_ht", "remise", "arrondi", "tva", "total_ttc",
                   "bon_pour_accord", "bpa_date", "reference")
CLES = sorted(c for c in L.LIBELLES
              if c.startswith("ci_") and not c.startswith("ci_ind_")) \
    + list(CLES_GENERIQUES)


def _data(langue=None):
    d = copy.deepcopy(sample_data.build("hotel"))
    etude_ci = copy.deepcopy(ETUDE_CI["exemple"])
    etude_ci["sous_reserve_visite"] = {"valeur": True, "motif": None}
    d["etude"] = dict(d["etude"], etude_ci=etude_ci, injection_dh_an=5000)
    eco = copy.deepcopy(ECONOMIE_CI["exemple"])
    eco["financement"] = copy.deepcopy(
        ECONOMIE_CI["exemple_industriel_mt"]["financement"])
    d["economie_ci"] = economie_ci_publique(eco)
    d["jalons_paiement"] = [
        {"jalon": "commande", "libelle": "Commande", "pct": 40,
         "montant_ttc": 256000.0},
        {"jalon": "livraison_materiel", "libelle": "Livraison du matériel",
         "pct": 50, "montant_ttc": 320000.0},
        {"jalon": "mise_en_service", "libelle": "Mise en service", "pct": 10,
         "montant_ttc": 64000.0}]
    d["om_ci_lignes"] = [{"designation": "Contrat O&M annuel", "ht": 12000,
                          "ttc": 14400, "optionnelle": True}]
    d["delai_intervention_suivi_heures"] = 48
    d["entreprise_client"] = {"raison_sociale": "Atlas SARL", "ice": "001",
                              "siege": "Casa", "interlocuteur": "M. Idrissi",
                              "fonction": "DAF"}
    d["_entrees_ci_lead"] = {"manquants": [
        "tension_raccordement", "type_toiture", "compteur_puissance_kva"]}
    d["options_proposees"] = [{"designation": "Monitoring", "quantite": 1,
                               "taux_tva": 20, "total_ht": 1000,
                               "total_ttc": 1200}]
    d["note_client"] = "Message libre"
    d["accepte_par_nom"] = "Karim"
    d["date_acceptation"] = "01/10/2026"
    d["valid_until"] = "05/11/2026"
    if langue:
        d["langue_sortie"] = langue
    return d


def _html(d):
    return render.build_html(renderer._augment(d))


def _html_sans_donnees(d):
    """Le HTML rendu, sans ce qui n'est pas un libellé : feuilles de style,
    images ``data:``, et les DONNÉES saisies (désignations, noms, CGV de la
    société, bande légale, offre de financement saisie)."""
    html = _html(d)
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.S)
    html = re.sub(r"data:[^\"')]+", "", html)
    donnees = [it["designation"] for it in d["all_items"]]
    donnees += [o["designation"] for o in d["options_proposees"]]
    donnees += ci_blocs.puces_conditions(d)
    donnees += [theme.bande_legale(d, theme.company_identity(d)),
                d["note_client"], d["client_name"], "Contrat O&M annuel"]
    offre = d["economie_ci"]["financement"]
    donnees += [offre["libelle_client"], offre["source"]]
    for valeur in sorted(donnees, key=len, reverse=True):
        html = html.replace(valeur, "")
    return html


def _texte_visible(html):
    return re.sub(r"<[^>]+>", " ", html)


def _morceaux_francais(cle, autre):
    fr = L.LIBELLES[cle]["fr"]
    if fr == L.LIBELLES[cle][autre]:
        return []
    return [m.strip() for m in _GABARIT.split(fr)
            if len(m.strip()) >= 4 and m.strip() not in
            L.LIBELLES[cle][autre]]


class Ciq333LanguesCommercial(SimpleTestCase):

    def _aucun_libelle_francais(self, langue):
        texte = _texte_visible(_html_sans_donnees(_data(langue)))
        for cle in CLES:
            for morceau in _morceaux_francais(cle, langue):
                with self.subTest(langue=langue, cle=cle, morceau=morceau):
                    self.assertNotIn(morceau, texte)

    def test_arabe_rtl_sans_libelle_francais(self):
        self._aucun_libelle_francais("ar")
        html = _html(_data("ar"))
        self.assertIn('<html lang="ar" dir="rtl">', html)
        self.assertIn(L.libelle("ci_echeancier", "ar"), html)
        self.assertIn(L.libelle("ci_kicker_commercial", "ar"), html)
        # L'espacement de lettres casse la liaison des lettres arabes.
        self.assertIn("letter-spacing:0 !important", html)

    def test_anglais_sans_libelle_francais(self):
        self._aucun_libelle_francais("en")
        html = _html(_data("en"))
        self.assertIn('<html lang="en" dir="ltr">', html)
        self.assertIn("Payment schedule", html)
        self.assertIn("Estimated payback", html)

    def test_francais_inchange(self):
        html = _html(_data())
        self.assertIn("<!doctype html><html><head>", html)
        self.assertNotIn(" dir=", html.split("<body>")[0])
        for fr in ("Proposition — Autoconsommation solaire commerciale",
                   "Échéancier de paiement", "Comment nous procédons",
                   "Retour estimé", "Bon pour accord — pour la société"):
            self.assertIn(fr, html)
        # Une langue inconnue rend le document français, au caractère près.
        self.assertEqual(_html(_data("de")), html)
        self.assertEqual(_html(_data("fr")), html)

    def test_trois_pages_dans_les_trois_langues(self):
        from weasyprint import HTML
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                pdf = renderer.render_pdf_bytes(_data(langue))
                self.assertEqual(pdf[:4], b"%PDF")
                doc = HTML(string=_html(_data(langue))).render()
                self.assertEqual(len(doc.pages), 3)

    def test_les_donnees_saisies_ne_sont_pas_traduites(self):
        html = _html(_data("ar"))
        self.assertIn("Panneau Jinko 710W", html)
        self.assertIn("Atlas SARL", html)
