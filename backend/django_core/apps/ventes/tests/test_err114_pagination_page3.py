"""ERR114 — la proposition résidentielle « full » tient EXACTEMENT sur ses
pages logiques, quelles que soient les polices de l'image.

CE QUI S'EST PASSÉ. La page 3 (``residential/trust.py``) tenait sur une feuille
avec les polices de l'image CI et débordait d'environ 25 mm avec celles de
l'image PROD : WeasyPrint poussait la fin de la page — le bloc « Prêt à passer
au solaire ? » (CTA de signature + QR) et la bande légale — sur une 4ᵉ feuille
quasi vide. Le contrat est de 3 pages exactement
(``test_quote_engine.test_premium_pdf_is_exactly_three_pages`` et le golden
YTEST10), mais le test canonique passait en CI : la CI ne voyait donc jamais le
document que le CLIENT recevait.

CE QUI EST GARDÉ ICI. Le renderer compare le nombre de pages LOGIQUES (un
``<div class="page">`` par gabarit) au nombre de feuilles réellement imprimées
et, sur débordement, re-rend UNE fois la page 3 au rythme vertical resserré.
Ces tests prouvent les trois propriétés qui comptent :
  1. le rendu par défaut est INCHANGÉ (aucune surcharge compacte émise) ;
  2. la version compacte ne RETIRE aucun bloc du contrat ;
  3. sur un débordement réel, le document revient au compte de pages logiques
     et le bloc de signature reste imprimé.

Aucune base de données : la fixture vendorée sert les données, comme les autres
tests « document rendu » du moteur.
"""
from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.residential import (
    render as rrender,
    renderer,
    sample_data,
    trust,
)

try:  # PyMuPDF — déjà vendoré (apps/ged, apps/paie) ; jamais requis à l'import
    import fitz
except Exception:  # pragma: no cover - environnement sans PyMuPDF
    fitz = None

# Chaque bloc du contrat de la page 3 : rien de tout cela ne doit disparaître
# quand le rythme vertical est resserré.
BLOCS_PAGE3 = (
    "Nos garanties",
    "La preuve, en ligne",
    "Conditions",
    "Prochaines étapes",
    "Bon pour accord",
    "Cachet et signature",
    "Prêt à passer au solaire ?",
    "Signez en ligne",
    "Estimations non contractuelles",
)


class TestPage3Compacte(SimpleTestCase):
    """La surcharge compacte : inerte par défaut, complète quand elle sert.

    Aucun PDF ici — seulement le HTML de la page 3, pour que cette garde-là
    tourne au palier PAR-MERGE (le contexte, lui, n'est bâti qu'UNE fois : il
    porte les graphiques matplotlib de la proposition).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        d = renderer._augment(sample_data.build("long"))
        cls.normal = trust.build(rrender.build_ctx(d))
        cls.compact = trust.build(rrender.build_ctx(d, compact_p3=True))
        cls.document = rrender.build_html(d)

    def test_rythme_compact_absent_par_defaut(self):
        self.assertNotIn("ERR114", self.normal)
        self.assertNotIn(".p3-sig-zone { height:10mm", self.normal)

    def test_rythme_compact_emis_sur_demande(self):
        self.assertIn("ERR114", self.compact)
        self.assertIn(".p3-sig-zone { height:10mm", self.compact)

    def test_la_version_compacte_ne_retire_aucun_bloc(self):
        for bloc in BLOCS_PAGE3:
            self.assertIn(bloc, self.normal,
                          f"bloc absent du rendu normal : {bloc}")
            self.assertIn(
                bloc, self.compact,
                f"la page 3 compacte a PERDU un bloc du contrat : {bloc}")

    def test_le_document_par_defaut_ne_porte_pas_la_surcharge(self):
        self.assertNotIn("ERR114", self.document)


@tag("pdf")
class TestGardePagination(SimpleTestCase):
    """Le renderer ramène le document à son compte de pages logiques.

    Rendu WeasyPrint réel → étiqueté ``pdf`` comme ses voisins de
    ``test_quote_engine_residential`` : ces gardes-là tournent au palier
    release-verify, aux côtés du golden YTEST10 qu'elles protègent.
    """

    def setUp(self):
        # Le cache LRU du renderer est indexé par empreinte de données : les
        # deux rendus ci-dessous portent les MÊMES données, il faut donc le
        # vider entre eux pour mesurer un vrai rendu à chaque fois.
        renderer._PDF_CACHE.clear()
        self.addCleanup(renderer._PDF_CACHE.clear)

    def _pages(self, pdf_bytes):
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            return len(doc), "\n".join(p.get_text() for p in doc)
        finally:
            doc.close()

    def test_sans_debordement_le_rendu_reste_a_trois_pages(self):
        if fitz is None:  # pragma: no cover
            self.skipTest("PyMuPDF absent")
        pdf = renderer.render_pdf_bytes(sample_data.build("deux"))
        pages, _ = self._pages(pdf)
        self.assertEqual(pages, 3)

    def _bas_de_contenu_mm(self, pdf_bytes, index):
        """Bas du contenu d'une page, en mm (même mesure que le renderer)."""
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            page = doc[index]
            mm = page.rect.height / 297.0
            # La bande de pied (13 mm, absolue) ne compte pas comme contenu.
            plafond = page.rect.height - 13.0 * mm - 0.5 * mm
            bas = 0.0
            for b in page.get_text("blocks"):
                if b[3] < plafond:
                    bas = max(bas, b[3])
            for dr in page.get_drawings():
                if dr["rect"].y1 < plafond:
                    bas = max(bas, dr["rect"].y1)
            return bas / mm
        finally:
            doc.close()

    def test_un_debordement_de_page_3_est_rattrape(self):
        """Page 3 poussée au-delà de la feuille : le document revient à 3.

        Le gonflement est CALIBRÉ sur le rendu réel (donc valable quelles que
        soient les polices de l'image, ce qui est précisément le piège
        d'ERR114) : on mesure le bas de contenu, puis on injecte de quoi
        dépasser la feuille de quelques mm. Il est posé sur les DEUX rendus —
        bien le gain vertical réel de la version compacte, et lui seul, qui
        ramène le document à 3 pages.
        """
        if fitz is None:  # pragma: no cover
            self.skipTest("PyMuPDF absent")
        from weasyprint import HTML

        donnees = sample_data.build("deux")
        d = renderer._augment(donnees)
        base = str(rrender.Path(rrender.__file__).resolve().parent)
        html = rrender.build_html(d)
        pdf_ref = HTML(string=html, base_url=f"file://{base}/").write_pdf()
        bas = self._bas_de_contenu_mm(pdf_ref, 2)
        manque = 297.0 - bas + 3.0
        self.assertGreater(manque, 0, "la page 3 déborde déjà sans gonflement")

        original = trust.build
        vus = []

        # La cale est faite de LIGNES DE TEXTE, à hauteur de ligne imposée :
        # une boîte à hauteur fixe est simplement rognée par le
        # `.page{overflow:hidden}`, alors que des lignes de texte se reportent
        # sur la feuille suivante — exactement ce qui est arrivé au bloc de
        # signature d'ERR114.
        ligne_mm = 4.0
        lignes = int(manque / ligne_mm) + 1
        cale = (f'<div style="font-size:7pt;line-height:{ligne_mm}mm">'
                + "<br>".join(["calibrage ERR114"] * lignes) + "</div>")

        def _gonfle(ctx):
            vus.append(bool(ctx.get("compact_p3")))
            return original(ctx) + cale

        trust.build = _gonfle
        try:
            # Sans la garde, ce gonflement PART bien sur une 4ᵉ feuille.
            sans_garde = HTML(
                string=rrender.build_html(d),
                base_url=f"file://{base}/").render()
            self.assertEqual(
                len(sans_garde.pages), 4,
                "le gonflement de calibrage n'a pas fait déborder la page 3 : "
                "le test ne prouverait rien")
            renderer._PDF_CACHE.clear()
            pdf = renderer.render_pdf_bytes(donnees)
        finally:
            trust.build = original

        pages, texte = self._pages(pdf)
        self.assertIn(True, vus,
                      "la garde n'a pas déclenché la re-passe resserrée")
        self.assertEqual(
            pages, 3,
            "le débordement de la page 3 n'a pas été rattrapé : le client "
            "recevrait un PDF de 4 pages dont la dernière est quasi vide")
        # Et le bloc de signature — ce qui débordait — est bien resté imprimé.
        self.assertIn("Prêt à passer au solaire", texte)
        self.assertIn("Bon pour accord", texte)
