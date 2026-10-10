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


# ── APDF9 — une-page legacy + titre des clauses particulières ──────────────

#: APDF9 — libellés de gabarit français du UNE PAGE (sonde PLANG-3).
LIBELLES_UNE_PAGE = (
    "Consultez votre", "DEVIS N°", "PUISSANCE CRÊTE", "PRODUCTION ANNUELLE",
    "ÉCONOMIE ANNUELLE", "PRIX PAR KWC", "Validité : jusqu", "Siège : ",
    "Clauses particulières",
)


def texte_normalise(texte):
    """Espaces insécables ramenés à l'espace (le gabarit en pose avant « : »)."""
    return texte.replace("\xa0", " ").replace(" ", " ")


def html_une_page(langue, **surcharges):
    """HTML EXACT du une-page legacy (données d'échantillon, sans base)."""
    from apps.ventes.quote_engine import generate_devis_premium as G
    from apps.ventes.quote_engine import i18n_labels
    from apps.ventes.tests import _moteur_fixtures as mf
    surcharges = dict(surcharges, pdf_mode="onepage")
    if langue != "fr":
        surcharges["langue_sortie"] = langue
        surcharges["libelles_document"] = i18n_labels.libelles(langue)
    return G.render_html_for(mf.donnees_legacy("deux", **surcharges))


class UnePageLibellesHtmlTests(SimpleTestCase):
    """APDF9 — HTML du une-page (profil, adresse, clause gelée)."""

    SURCHARGES = {
        "entreprise": {"nom": "SOLAIRE EXEMPLE SARL", "adresse": "1 rue A",
                       "ice": "001111111000011"},
        "clauses_cgv": [{"nom": "Clause A", "corps_texte": "Texte A."}],
    }

    def test_en_et_ar_aucun_libelle_fr(self):
        for langue in ("en", "ar"):
            with self.subTest(langue=langue):
                texte = texte_normalise(texte_html(
                    html_une_page(langue, **self.SURCHARGES)))
                self.assertEqual(trouves(texte, LIBELLES_UNE_PAGE), [])
                # Les données saisies restent telles quelles.
                self.assertIn("Clause A", texte)
                self.assertIn("1 rue A", texte)

    def test_fr_inchange(self):
        texte = texte_normalise(texte_html(
            html_une_page("fr", **self.SURCHARGES)))
        for libelle in ("Consultez votre", "DEVIS N°", "Siège : ",
                        "Clauses particulières"):
            self.assertIn(libelle.lower(), texte.lower())

    def test_titre_clauses_par_langue(self):
        from apps.ventes.quote_engine import clauses_cgv
        clause = [{"nom": "A", "corps_texte": "B"}]
        self.assertIn(clauses_cgv.TITRE, clauses_cgv.bloc_clauses_html(clause))
        self.assertEqual(clauses_cgv.TITRE, "Clauses particulières")
        self.assertIn("Special terms",
                      clauses_cgv.bloc_clauses_html(clause, langue="en"))


@tag("pdf")
class UnePageLibellesTests(TestCase):
    """APDF9 — une-page RÉEL (résidentiel et agricole) en en / ar / fr."""

    def setUp(self):
        from apps.ventes.tests.test_pdf_apdf_garde_identite import MARCHES
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel, profil)
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        self.company = make_company(slug="apdf9-co", nom="APDF9")
        profil(self.company, nom="SOLAIRE EXEMPLE SARL", adresse="1 rue A",
               ice="001111111000011")
        lignes, etude, mode = MARCHES["agricole"]
        agricole = make_devis(self.company, make_user(self.company),
                              make_client(self.company), lignes,
                              reference="DEV-APDF9-AGRI",
                              etude_params=dict(etude))
        agricole.mode_installation = mode
        agricole.save(update_fields=["mode_installation"])
        self.devis = [devis_residentiel(self.company, "DEV-APDF9-RES"),
                      agricole]

    def _rendu(self, devis, langue):
        import fitz
        from apps.ventes.tests.test_pdf_apdf_identite import rendre_pdf
        pdf = rendre_pdf(devis, {"pdf_mode": "onepage",
                                 "langue_sortie": langue})
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            return (texte_normalise("\n".join(p.get_text() for p in doc)),
                    len(doc))
        finally:
            doc.close()

    def test_onepage_en(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                texte, _pages = self._rendu(devis, "en")
                self.assertEqual(trouves(texte, LIBELLES_UNE_PAGE), [])

    def test_onepage_ar(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                texte, _pages = self._rendu(devis, "ar")
                self.assertEqual(trouves(texte, LIBELLES_UNE_PAGE), [])

    def test_onepage_fr_inchange_une_page(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                texte, pages = self._rendu(devis, "fr")
                self.assertEqual(pages, 1)
                self.assertIn("DEVIS", texte)
                for langue in ("en", "ar"):
                    self.assertEqual(self._rendu(devis, langue)[1], 1)


# ── APDF10 — puces CGV par défaut + note de TVA dans la langue du document ─

#: APDF10 — morceaux français des puces CGV par défaut et de la note de TVA.
PUCES_FR = ("Acompte à la commande", "à la réception du matériel",
            "après la mise en marche", "TVA : 10% panneaux",
            "Tarifs de référence")
TERMES = {"acompte": 40, "materiel": 50, "solde": 10}


def _pourcentages(puces):
    import re
    return sorted(re.findall(r"(\d+)&#37;", " ".join(puces)))


class PucesCgvLangueHtmlTests(SimpleTestCase):
    """APDF10 — ``cgv_bullets_remplies`` (PDF C&I + page publique), pur."""

    def _puces(self, langue, **data):
        from apps.ventes.quote_engine.builder import tva_note_des_lignes
        from apps.ventes.quote_engine.generate_devis_premium import (
            cgv_bullets_remplies)

        class _Ligne:
            def __init__(self, taux, designation):
                self.taux_tva, self.designation = taux, designation
                self.produit = None

        note = tva_note_des_lignes(
            [_Ligne(10, "Panneau Jinko 710W"), _Ligne(20, "Onduleur 10kW")],
            20, langue=langue)
        return cgv_bullets_remplies(dict(
            {"langue_sortie": langue, "payment_terms": TERMES,
             "tva_note": note, "valid_until": "01/02/2027"}, **data))

    def test_en_et_ar_puces_traduites_memes_pourcentages(self):
        fr = self._puces("fr")
        for langue in ("en", "ar"):
            with self.subTest(langue=langue):
                puces = self._puces(langue)
                self.assertEqual(trouves(" ".join(puces), PUCES_FR), [])
                self.assertEqual(_pourcentages(puces), _pourcentages(fr))
                self.assertEqual(len(puces), len(fr))

    def test_fr_inchange(self):
        from apps.ventes.quote_engine.generate_devis_premium import (
            DEFAULT_DOC_TEXTS, remplir_cgv_bullets)
        attendu = remplir_cgv_bullets(
            DEFAULT_DOC_TEXTS["cgv_bullets"], acompte=40, materiel=50,
            solde=10, tva_note=("TVA : 10% panneaux photovoltaïques · 20% "
                                "autres équipements et prestations"),
            valid_until="01/02/2027")
        self.assertEqual(self._puces("fr"), attendu)

    def test_surcharge_societe_conservee(self):
        perso = ["Clause société {acompte}&#37; non traduite"]
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                self.assertEqual(
                    self._puces(langue, doc_texts={"cgv_bullets": perso}),
                    ["Clause société 40&#37; non traduite"])


@tag("pdf")
class PucesCgvLangueTests(TestCase):
    """APDF10 — conditions du PDF C&I RÉEL en en / ar (sans CGV société)."""

    def setUp(self):
        from apps.ventes.tests.test_pdf_apdf_garde_identite import MARCHES
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis, make_user)
        self.company = make_company(slug="apdf10-co", nom="APDF10")
        user, client = make_user(self.company), make_client(self.company)
        self.devis = []
        for mode in ("commercial", "industriel"):
            lignes, _etude, _mode = MARCHES[mode]
            devis = make_devis(self.company, user, client, lignes,
                               reference=f"DEV-APDF10-{mode[:3].upper()}")
            devis.mode_installation = mode
            devis.save(update_fields=["mode_installation"])
            self.devis.append(devis)

    def _texte(self, devis, langue):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            rendre_pdf, texte_pdf)
        return texte_normalise(texte_pdf(rendre_pdf(
            devis, {"langue_sortie": langue})))

    def test_ci_en_puces_traduites(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                self.assertEqual(
                    trouves(self._texte(devis, "en"), PUCES_FR), [])

    def test_ci_ar_puces_traduites(self):
        for devis in self.devis:
            with self.subTest(devis=devis.reference):
                self.assertEqual(
                    trouves(self._texte(devis, "ar"), PUCES_FR), [])

    def test_surcharge_societe_conservee(self):
        from apps.parametres.models_documents import DocumentTemplates
        modele = DocumentTemplates.get(company=self.company)
        modele.cgv_bullets = ["CLAUSE-SOCIETE-APDF10 conservée"]
        modele.save()
        for langue in ("fr", "en", "ar"):
            with self.subTest(langue=langue):
                self.assertIn("CLAUSE-SOCIETE-APDF10 conservée",
                              self._texte(self.devis[0], langue))
