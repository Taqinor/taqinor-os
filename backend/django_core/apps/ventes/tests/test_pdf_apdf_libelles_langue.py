"""APDF8-APDF10 (C-APDF-004) — les libellés FIXES des gabarits suivent la langue
du document ; le français reste octet pour octet celui d'hier.

APDF8 — devis résidentiel premium (couverture, détail, page de confiance) :
chaque libellé passe par ``i18n_labels`` (clés ``res_*``) via
``residential.cover.libelle_fixe``. Rendu réel : PDF servi par /proposal
(``test_pdf_apdf_identite.rendre_pdf``, MinIO en mémoire) lu par PyMuPDF, et
HTML du gabarit sur les données d'échantillon (sans base).
Test-du-test : remettre « Votre installation solaire » en dur dans
``residential/cover.py`` ⇒ ``test_en_et_ar_aucun_libelle_fr`` (variante sans
économies) échoue.
"""
import copy

from django.test import SimpleTestCase, TestCase, tag

#: APDF8 — libellés de gabarit français du devis résidentiel (sondes PDEV-2 /
#: PLANG-3). Comparaison sans casse : deux titres sont mis en capitales par CSS.
LIBELLES_RESIDENTIEL = (
    "Valable jusqu", "Votre installation solaire",
    "Consultez votre proposition interactive", "Bonjour", "kWc installés",
    "Le détail de votre projet", "VOTRE ÉQUIPEMENT", "Pourquoi",
    "NOS GARANTIES", "Prochaines étapes", "Validité de l",
    "Bon pour accord", "La preuve, en ligne",
)


def texte_html(html):
    """Texte visible d'un HTML de gabarit (styles et balises retirés)."""
    import html as H
    import re
    s = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", H.unescape(s))


def trouves(texte, libelles):
    bas = texte.lower()
    return [lib for lib in libelles if lib.lower() in bas]


def html_residentiel(langue, **surcharges):
    """HTML du gabarit résidentiel premium (données d'échantillon)."""
    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.quote_engine.residential import render, renderer
    from apps.ventes.quote_engine.residential import sample_data
    d = copy.deepcopy(dict(sample_data.build("deux")))
    d.update(copy.deepcopy(surcharges))
    if langue != "fr":
        d["langue_sortie"] = langue
        d["libelles_document"] = i18n_labels.libelles(langue)
    return render.build_html(renderer._augment(d))


#: Branches du gabarit dont les libellés diffèrent (économies masquées,
#: option unique, recommandation hybride, devis final).
VARIANTES = {
    "base": {},
    "sans_economies": {"masquer_economies": True},
    "option_unique": {"deux_options": False, "avec_ok": True},
    "hybride": {"pourquoi_avec": (
        "Pourquoi nous la recommandons : l'onduleur hybride est prêt pour "
        "la batterie — vous l'ajoutez quand vous voulez, sans changer "
        "d'onduleur."), "libelle_avec": "Hybride, batterie plus tard"},
    "devis_final": {"devis_final": True},
}


class ResidentielLibellesHtmlTests(SimpleTestCase):
    """APDF8 — HTML du gabarit (sans base ni WeasyPrint)."""

    def test_en_et_ar_aucun_libelle_fr(self):
        for langue in ("en", "ar"):
            for nom, surcharges in VARIANTES.items():
                with self.subTest(langue=langue, variante=nom):
                    texte = texte_html(html_residentiel(langue, **surcharges))
                    self.assertEqual(
                        trouves(texte, LIBELLES_RESIDENTIEL), [])

    def test_fr_porte_ses_libelles(self):
        texte = texte_html(html_residentiel("fr"))
        absents = [lib for lib in LIBELLES_RESIDENTIEL
                   if lib not in ("Votre installation solaire",
                                  "VOTRE ÉQUIPEMENT")
                   and lib.lower() not in texte.lower()]
        self.assertEqual(absents, [])
        texte = texte_html(html_residentiel("fr", masquer_economies=True))
        self.assertIn("Votre installation solaire", texte)
        texte = texte_html(html_residentiel(
            "fr", deux_options=False, avec_ok=True))
        self.assertIn("Votre équipement", texte)

    def test_chaque_cle_res_porte_trois_langues_et_ses_gabarits(self):
        import re
        from apps.ventes.quote_engine import i18n_labels as L
        for cle, trad in L.LIBELLES.items():
            if not cle.startswith("res_"):
                continue
            with self.subTest(cle=cle):
                for langue in ("fr", "en", "ar"):
                    self.assertTrue(trad[langue].strip())
                    self.assertEqual(
                        sorted(re.findall(r"\{\w+\}", trad[langue])),
                        sorted(re.findall(r"\{\w+\}", trad["fr"])))


@tag("pdf")
class ResidentielLibellesTests(TestCase):
    """APDF8 — PDF RÉEL du devis résidentiel en en / ar / fr."""

    def setUp(self):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel)
        from apps.ventes.tests._quote_engine_common import make_company
        self.company = make_company(slug="apdf8-co", nom="APDF8")
        self.devis = devis_residentiel(self.company, "DEV-APDF8-1")

    def _texte(self, langue):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            rendre_pdf, texte_pdf)
        return texte_pdf(rendre_pdf(self.devis, {"langue_sortie": langue}))

    def test_en_aucun_libelle_fr(self):
        texte = self._texte("en")
        self.assertEqual(trouves(texte, LIBELLES_RESIDENTIEL), [])
        # Les données saisies restent telles quelles.
        self.assertIn("Panneau Canadien Solar 710W", texte)

    def test_ar_aucun_libelle_fr(self):
        texte = self._texte("ar")
        self.assertEqual(trouves(texte, LIBELLES_RESIDENTIEL), [])

    def test_fr_texte_inchange(self):
        texte = self._texte("fr")
        for libelle in ("Le détail de votre projet", "Prochaines étapes",
                        "Bon pour accord", "Bonjour"):
            self.assertIn(libelle, texte)
        self.assertEqual(texte, self._texte("fr"))
