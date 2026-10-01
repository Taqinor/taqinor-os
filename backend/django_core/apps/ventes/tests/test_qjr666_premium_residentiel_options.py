"""QJR666 (décision fondateur 01/10) — les choix EXPLICITES du dialogue PDF ne
sont plus perdus en silence par le gabarit premium RÉSIDENTIEL.

Décision : « ajouter au gabarit premium » (pas de bascule vers l'ancien
moteur). Le document résidentiel 'full' honore désormais :

* ``devis_final`` — cases Acompte / Matériel / Solde AU CENTIME (lues dans
  ``montants_tranches`` = ``builder.repartition_paiement``) + ligne de
  virement, à la place du bloc « La preuve, en ligne » : 3 pages ;
* ``include_calepinage = True`` EXPLICITE — la planche cotée en page
  « Calepinage » (une page de plus) ; l'AUTO n'ajoute rien, une planche
  périmée (QJR522) n'est pas composée ;
* ``show_monthly = False`` — la carte « Votre facture mois par mois » n'est
  pas imprimée ;
* ``langue_sortie`` / ``libelles_document`` — les libellés STRUCTURELS
  (tableau, chaîne des totaux, échéancier, « Réf. ») ; un document français
  reste octet pour octet celui d'avant.

Le moteur ne fait que RENDRE (règle #4).

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_qjr666_premium_residentiel_options"
"""
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.quote_engine import i18n_labels
from apps.ventes.quote_engine.residential import (
    render as rrender,
    renderer,
    sample_data,
)
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

try:  # PyMuPDF — jamais requis à l'import
    import fitz
except Exception:  # pragma: no cover
    fitz = None

#: Montants du builder (``repartition_paiement``) pour les deux branches.
MONTANTS = {
    "sans": {"total": 61728.4, "acompte": 18518.52, "materiel": 37037.04,
             "solde": 6172.84, "pct_a": 30, "pct_m": 60, "pct_s": 10,
             "deux_cases": False, "solde2": 43209.88, "pct_s2": 70},
    "avec": {"total": 98765.43, "acompte": 29629.63, "materiel": 59259.26,
             "solde": 9876.54, "pct_a": 30, "pct_m": 60, "pct_s": 10,
             "deux_cases": False, "solde2": 69135.8, "pct_s2": 70},
}
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200">'
       '<rect x="10" y="10" width="80" height="40"/></svg>')
TITRE_CALEPINAGE = '>Calepinage</div>'
CARTE_MENSUELLE = 'Votre facture mois par mois'


def _data(**extra):
    d = sample_data.build("deux")
    d.update(extra)
    return d


def _html(**extra):
    return rrender.build_html(renderer._augment(_data(**extra)))


class LeFrancaisParDefautEstInchange(SimpleTestCase):
    def test_langue_fr_explicite_octet_identique(self):
        self.assertEqual(
            _html(),
            _html(langue_sortie="fr",
                  libelles_document=i18n_labels.libelles("fr")))

    def test_options_par_defaut_inertes(self):
        html = _html(show_monthly=True, devis_final=False,
                     montants_tranches=MONTANTS)
        self.assertEqual(html, _html(montants_tranches=MONTANTS))
        self.assertIn("La preuve, en ligne", html)
        self.assertNotIn("Modalités de paiement", html)
        self.assertNotIn(TITRE_CALEPINAGE, html)
        self.assertTrue(html.startswith("<!doctype html><html><head>"))


class DevisFinal(SimpleTestCase):
    def test_cases_au_centime_branche_recommandee(self):
        html = _html(devis_final=True, montants_tranches=MONTANTS)
        self.assertIn("Modalités de paiement", html)
        branche = MONTANTS["avec"]  # recommandé = « Avec batterie »
        for montant in (branche["acompte"], branche["materiel"],
                        branche["solde"]):
            self.assertIn(
                f"{renderer_fmt(montant)} MAD", html)
        self.assertIn("Acompte · À la signature", html)
        self.assertIn("Matériel · Avant installation", html)
        self.assertIn("Solde · Après installation", html)
        self.assertNotIn("La preuve, en ligne", html)

    def test_scenario_sans_batterie_imprime_la_branche_sans(self):
        html = _html(devis_final=True, montants_tranches=MONTANTS,
                     scenario="Sans batterie")
        self.assertIn(f"{renderer_fmt(MONTANTS['sans']['acompte'])} MAD",
                      html)

    def test_deux_tranches_deux_cases(self):
        deux = {b: dict(v, materiel=0.0) for b, v in MONTANTS.items()}
        html = _html(devis_final=True, montants_tranches=deux)
        self.assertNotIn("Matériel · Avant installation", html)
        self.assertIn("Solde · À la livraison", html)
        self.assertIn(f"{renderer_fmt(deux['avec']['solde2'])} MAD", html)

    def test_sans_montants_du_builder_aucune_case_inventee(self):
        html = _html(devis_final=True)
        self.assertNotIn("Modalités de paiement", html)
        self.assertIn("La preuve, en ligne", html)

    def test_rib_du_tenant_et_jamais_celui_d_un_autre(self):
        tenant = {"nom": "Soleil SARL", "rib": "011 222 333",
                  "banque": "Banque X"}
        html = _html(devis_final=True, montants_tranches=MONTANTS,
                     entreprise=tenant)
        self.assertIn("RIB 011 222 333", html)
        self.assertNotIn("Saham Bank", html)
        sans_rib = _html(devis_final=True, montants_tranches=MONTANTS,
                         entreprise={"nom": "Soleil SARL"})
        self.assertNotIn("Saham Bank", sans_rib)
        self.assertNotIn("Virement bancaire", sans_rib)


def renderer_fmt(v):
    from apps.ventes.quote_engine.montants import fmt_centimes
    return fmt_centimes(v)


class GrapheMensuel(SimpleTestCase):
    def test_decoche_retire_la_carte(self):
        self.assertIn(CARTE_MENSUELLE, _html())
        self.assertNotIn(CARTE_MENSUELLE, _html(show_monthly=False))


class PlancheCalepinage(SimpleTestCase):
    def test_demande_explicite_une_page_de_plus(self):
        base = _html()
        html = _html(include_calepinage=True, include_calepinage_demande=True,
                     calepinage_svg=SVG, calepinage_empreinte="calepinage ab12")
        self.assertIn(TITRE_CALEPINAGE, html)
        self.assertIn(SVG, html)
        self.assertEqual(html.count('<div class="page">'),
                         base.count('<div class="page">') + 1)
        # Avant la page d'engagement.
        self.assertLess(html.index(TITRE_CALEPINAGE),
                        html.index("Bon pour accord"))

    def test_auto_n_ajoute_rien(self):
        html = _html(include_calepinage=True, calepinage_svg=SVG)
        self.assertNotIn(TITRE_CALEPINAGE, html)

    def test_demande_sans_planche_aucune_page_blanche(self):
        html = _html(include_calepinage_demande=True)
        self.assertNotIn(TITRE_CALEPINAGE, html)

    def test_la_page_ne_porte_aucun_montant(self):
        html = _html(include_calepinage=True, include_calepinage_demande=True,
                     calepinage_svg=SVG)
        debut = html.index(TITRE_CALEPINAGE)
        fin = html.index('<div class="page">', debut)
        for interdit in ("MAD", "Total TTC", "prix_achat", "marge"):
            self.assertNotIn(interdit, html[debut:fin])


class Langue(SimpleTestCase):
    def test_anglais(self):
        html = _html(langue_sortie="en",
                     libelles_document=i18n_labels.libelles("en"))
        self.assertTrue(html.startswith('<!doctype html><html lang="en">'))
        for libelle in ("Description", "Unit price excl. VAT",
                        "Subtotal excl. VAT", "Total incl. VAT", "Ref."):
            self.assertIn(libelle, html)
        self.assertNotIn("<span>Sous-total HT</span>", html)

    def test_arabe_isole_et_police(self):
        html = _html(langue_sortie="ar",
                     libelles_document=i18n_labels.libelles("ar"),
                     devis_final=True, montants_tranches=MONTANTS)
        self.assertIn('<html lang="ar">', html)
        self.assertIn('<span class="i18n-rtl" dir="rtl">', html)
        self.assertIn(i18n_labels.libelle("total_ttc", "ar"), html)
        self.assertIn(i18n_labels.libelle("conditions_paiement", "ar"), html)
        self.assertIn(".i18n-rtl{", html)

    def test_langue_inconnue_rend_le_francais(self):
        self.assertEqual(_html(langue_sortie="xx"), _html())


@tag("pdf")
class PaginationReelle(SimpleTestCase):
    """Rendu WeasyPrint réel : les comptes de pages du contrat."""

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest("PyMuPDF absent")
        renderer._PDF_CACHE.clear()
        self.addCleanup(renderer._PDF_CACHE.clear)

    def _pages(self, **extra):
        pdf = renderer.render_pdf_bytes(_data(**extra))
        doc = fitz.open(stream=pdf, filetype="pdf")
        try:
            return len(doc), "\n".join(p.get_text() for p in doc)
        finally:
            doc.close()

    def test_devis_final_reste_a_trois_pages(self):
        n, texte = self._pages(devis_final=True, montants_tranches=MONTANTS)
        self.assertEqual(n, 3)
        self.assertIn("Bon pour accord", texte)

    def test_sans_graphe_mensuel_trois_pages(self):
        n, _ = self._pages(show_monthly=False)
        self.assertEqual(n, 3)

    def test_planche_demandee_quatre_pages(self):
        n, texte = self._pages(include_calepinage=True,
                               include_calepinage_demande=True,
                               calepinage_svg=SVG)
        self.assertEqual(n, 4)
        self.assertIn("Calepinage", texte)

    def test_anglais_trois_pages(self):
        n, _ = self._pages(langue_sortie="en",
                           libelles_document=i18n_labels.libelles("en"))
        self.assertEqual(n, 3)


@tag("pdf")
class CheminDeProduction(TestCase):
    """Par ``generate_premium_devis_pdf`` (upload mocké) : un devis
    résidentiel servi par le gabarit premium honore la demande explicite de
    planche — et l'AUTO n'y ajoute rien."""

    def setUp(self):
        from apps.ventes.tests.test_quote_engine_formats import LAYOUT_CAL182
        from apps.calepinage.models import Calepinage
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # Même devis que TestQuoteSignLinkAndPageNumbers : factures RÉELLES
        # (M1), sinon _augment refuse et le legacy servirait le document.
        self.devis = make_devis(
            self.company, self.user, self.client_obj, [
                ('Panneau Canadien Solar 710W', '14', '1272.73'),
                ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
                ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
                ('Batterie Dyness 10 kWh', '1', '25000'),
                ('Installation', '1', '4000'),
            ], reference='DEV-QJR666-1', etude_params={
                **DEUX_OPTIONS,
                'factures_mensuelles_reelles': [
                    1200, 1200, 1300, 1400, 1600, 1800,
                    1900, 1900, 1700, 1500, 1300, 1200],
            })
        self.devis.mode_installation = 'residentiel'
        self.devis.save(update_fields=['mode_installation'])
        Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=self.devis,
            titre='Villa Anfa', roof_layout=LAYOUT_CAL182,
            layout_hash='ab12cd34' * 8, version_moteur='2.1.0')
        renderer._PDF_CACHE.clear()
        self.addCleanup(renderer._PDF_CACHE.clear)

    def _rendu(self, options):
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as upload, \
                patch('apps.ventes.quote_engine.residential.renderer.'
                      'render_pdf_bytes',
                      wraps=renderer.render_pdf_bytes) as resid:
            generate_premium_devis_pdf(self.devis.id, options)
        self.assertTrue(resid.called, 'le gabarit résidentiel doit servir')
        return upload.call_args[0][0], resid.call_args[0][0]

    def test_demande_explicite_planche_imprimee(self):
        pdf, data = self._rendu({'include_calepinage': True})
        self.assertTrue(data.get('include_calepinage_demande'))
        html = rrender.build_html(renderer._augment(data))
        self.assertIn(TITRE_CALEPINAGE, html)
        if fitz is not None:
            doc = fitz.open(stream=pdf, filetype="pdf")
            try:
                self.assertIn('Calepinage',
                              "\n".join(p.get_text() for p in doc))
            finally:
                doc.close()

    def test_auto_aucune_page_de_plus(self):
        _pdf, data = self._rendu({})
        self.assertNotIn('include_calepinage_demande', data)
        html = rrender.build_html(renderer._augment(data))
        self.assertNotIn(TITRE_CALEPINAGE, html)
