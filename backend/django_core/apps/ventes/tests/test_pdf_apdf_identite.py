"""APDF2 (C-APDF-001) — le moteur legacy (étude, Devis final, une-page) suit
la règle de virement du résidentiel : société identifiée sans RIB ni banque →
aucune barre « Virement bancaire » ; RIB du profil → sa ligne ; aucun profil
→ la ligne historique (byte-identique). Une seule fonction
(``quote_engine.identite.ligne_rib``), appelée par les deux moteurs.

Rendu réel du moteur legacy (``build_quote_data`` puis
``generate_premium_pdf`` ; seul l'appel WeasyPrint final est remplacé par la
capture du HTML) ; aucune doublure du moteur.

Test-du-test : remettre ``ENT_RIB_LINE = _ENT_DEFAULT_RIB_LINE`` quand rib
et banque sont vides ⇒ ``test_legacy_etude_final_sans_rib_aucune_ligne``
échoue.

APDF3 — bande légale (``BandeLegaleTests``) : tout profil, quel que soit son
nom, imprime SES mentions (``identite.mentions_legales``) sur les quatre
formats du devis, avec l'ICE et le RC que la facture lit
(``utils.pdf._company_context``). Rendu RÉEL (``rendre_pdf`` : PDF servi par
/proposal, MinIO remplacé en mémoire). Test-du-test : remettre le test
``"TAQINOR" not in ent_nom.upper()`` dans ``theme.bande_legale`` ⇒
``test_nom_taqinor_profil_renseigne_lit_le_profil`` échoue.

APDF4 — logo (``LogoTests``) : le logo téléversé de la société
(``CompanyProfile.logo_key``, lu comme la facture) en page 1 de chaque format ;
société identifiée sans logo → bandeau neutre ; aucun profil → TAQINOR.
Seul le stockage est local (``utils.pdf._download``). Test-du-test : faire
renvoyer à ``theme.logo_imprime_b64`` l'asset sans lire
``entreprise['logo_uri']`` ⇒ ``test_logo_societe_tous_formats`` échoue.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase, tag

from apps.parametres.models import CompanyProfile
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine import identite
from apps.ventes.quote_engine.residential import trust
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)

#: Devis résidentiel servi par le gabarit PREMIUM (factures réelles, M1).
LIGNES_RESIDENTIEL = [
    ('Panneau Canadien Solar 710W', '14', '1272.73'),
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
    ('Batterie Dyness 10 kWh', '1', '25000'),
    ('Installation', '1', '4000'),
]
ETUDE_RESIDENTIEL = {
    **DEUX_OPTIONS,
    'factures_mensuelles_reelles': [
        1200, 1200, 1300, 1400, 1600, 1800,
        1900, 1900, 1700, 1500, 1300, 1200],
}
#: Les quatre formats du devis (``clean_pdf_options``).
FORMATS = {
    'defaut': {},
    'devis_final': {'devis_final': True},
    'include_etude': {'include_etude': True},
    'onepage': {'pdf_mode': 'onepage'},
}


def devis_residentiel(company, reference):
    devis = make_devis(company, make_user(company), make_client(company),
                       LIGNES_RESIDENTIEL, reference=reference,
                       etude_params=dict(ETUDE_RESIDENTIEL))
    devis.mode_installation = 'residentiel'
    devis.save(update_fields=['mode_installation'])
    return devis


def profil(company, **champs):
    """Pose les champs du profil société (``CompanyProfile.get`` le crée)."""
    p = CompanyProfile.get(company=company)
    CompanyProfile.objects.filter(pk=p.pk).update(**champs)


def rendre_pdf(devis, options=None):
    """Octets du PDF RÉEL servi par /proposal : ``generate_premium_devis_pdf``
    (registre des renderers, repli legacy), stockage MinIO remplacé en
    mémoire, images MinIO du toit neutralisées. Aucune doublure du moteur."""
    from apps.ventes.coherence.contexte import rendu_sans_reseau
    from apps.ventes.quote_engine import builder
    from apps.ventes.quote_engine.residential import renderer
    renderer._PDF_CACHE.clear()
    capture = {}
    with rendu_sans_reseau(), \
            mock.patch.object(builder, '_ensure_pdf_bucket', lambda: None), \
            mock.patch('apps.ventes.utils.pdf._upload_pdf',
                       lambda octets, cle: capture.update(pdf=octets)):
        builder.generate_premium_devis_pdf(
            devis.pk, builder.clean_pdf_options(options or {}),
            persist=False)
    return capture['pdf']


def png_rouge(largeur=120, hauteur=60) -> bytes:
    """Logo d'essai : PNG rouge uni."""
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (largeur, hauteur), (220, 20, 20)).save(buf, 'PNG')
    return buf.getvalue()


def images_page(octets, numero=0):
    """Images (PIL, RGB) embarquées dans la page ``numero`` du PDF."""
    import io
    import fitz
    from PIL import Image
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        out = []
        for info in doc[numero].get_images(full=True):
            brut = doc.extract_image(info[0])
            out.append(Image.open(io.BytesIO(brut['image'])).convert('RGB'))
        return out
    finally:
        doc.close()


def taille_logo_taqinor():
    """Dimensions de l'asset ``assets/logo.png`` (son empreinte)."""
    from pathlib import Path
    from PIL import Image
    from apps.ventes.quote_engine import residential
    chemin = (Path(residential.__file__).resolve().parent.parent
              / 'assets' / 'logo.png')
    with Image.open(chemin) as img:
        return img.size


def est_rouge(img) -> bool:
    r, g, b = img.getpixel((img.width // 2, img.height // 2))
    return r > 180 and g < 80 and b < 80


def texte_pdf(octets) -> str:
    """Texte extrait (PyMuPDF) de toutes les pages."""
    import fitz
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


class RibTenantTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='apdf2-co', nom='APDF2')
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            nom='SOLAIRE EXEMPLE SARL', ice='001111111000011', rib='',
            banque='')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '14', '1100'),
                ('Onduleur réseau 10kW', '1', '11700'),
                ('Onduleur hybride 5kW', '1', '24000'),
                ('Batterie 5 kWh', '1', '14000'),
            ], reference='DEV-APDF2-1', etude_params=dict(DEUX_OPTIONS))

    def _html(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        data = build_quote_data(self.devis, clean_pdf_options(
            {'devis_final': True, 'include_etude': True,
             'include_calepinage': False}))
        capture = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: capture.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_apdf2_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return capture.get('html', '')

    def test_legacy_etude_final_sans_rib_aucune_ligne(self):
        html = self._html()
        self.assertTrue(html)
        for interdit in ('Saham', '022 780', 'TAQINOR SOLUTION',
                         'Virement bancaire'):
            self.assertNotIn(interdit, html)

    def test_legacy_rib_profil_imprime(self):
        profil = CompanyProfile.get(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            rib='011 780 0000123456789012 34')
        html = self._html()
        self.assertIn('Virement bancaire', html)
        self.assertIn('RIB 011 780 0000123456789012 34', html)
        self.assertIn('SOLAIRE EXEMPLE SARL', html)
        self.assertNotIn('Saham', html)


class RegleUniqueTests(SimpleTestCase):
    def test_sans_profil_ligne_historique(self):
        G._apply_entreprise(None)
        self.assertEqual(G.ENT_RIB_LINE, G._ENT_DEFAULT_RIB_LINE)
        self.assertIn('Saham Bank', G.ENT_RIB_LINE)
        self.assertIn('TAQINOR SOLUTION', trust._ligne_rib({}))

    def test_meme_fonction_pour_les_deux_moteurs(self):
        for ent in ({'nom': 'X', 'ice': '1'}, {'nom': 'X', 'rib': '011'},
                    {'banque': 'BMCE'}, {}):
            with self.subTest(ent=ent):
                self.assertEqual(trust._ligne_rib({'entreprise': ent}),
                                 identite.ligne_rib(ent))
                G._apply_entreprise(ent)
                attendu = identite.ligne_rib(ent, gras=G._gras_rib_legacy)
                if any(ent.values()):
                    self.assertEqual(G.ENT_RIB_LINE, attendu)
        G._apply_entreprise(None)


@tag('pdf')
class BandeLegaleTests(TestCase):
    """APDF3 (C-APDF-001, D-APDF-1) — la bande légale lit le profil."""

    def setUp(self):
        self.company = make_company(slug='apdf3-co', nom='APDF3')
        profil(self.company, nom='TAQINOR Démo (complet)',
               ice='002589631000045', rc='198453',
               identifiant_fiscal='48291057', patente='35201478',
               forme_juridique='SARL', capital_social='250 000,00 MAD',
               email='demo@exemple.ma', telephone='', rib='', banque='')
        self.devis = devis_residentiel(self.company, 'DEV-APDF3-1')

    def test_nom_taqinor_profil_renseigne_lit_le_profil(self):
        texte = texte_pdf(rendre_pdf(self.devis))
        for attendu in ('002589631000045', '198453', 'au capital de'):
            self.assertIn(attendu, texte)
        for interdit in ('003799642000067', '691213', 'Reda Kasri',
                         '61 85 04 10', 'Gérant'):
            self.assertNotIn(interdit, texte)

    def test_meme_ice_tous_formats_et_facture(self):
        from apps.ventes.utils.pdf import _company_context
        facture = _company_context(self.company)
        self.assertEqual(facture['entreprise_ice'], '002589631000045')
        self.assertEqual(facture['entreprise_rc'], '198453')
        for nom, options in FORMATS.items():
            with self.subTest(format=nom):
                texte = texte_pdf(rendre_pdf(self.devis, options))
                self.assertIn(facture['entreprise_ice'], texte)
                self.assertIn(facture['entreprise_rc'], texte)
                self.assertNotIn('003799642000067', texte)
                self.assertNotIn('691213', texte)

    def test_sans_profil_repli_historique(self):
        from apps.ventes.quote_engine.residential import theme
        bande = theme.bande_legale({'entreprise': {}}, {})
        self.assertTrue(bande.startswith(identite.LEGALE_TAQINOR_PREMIUM))
        self.assertIn('+212 6 61 85 04 10', bande)
        G._apply_entreprise(None)
        self.assertEqual(G.ENT_LEGAL_LINE, identite.LEGALE_TAQINOR_LEGACY)


class MentionsLegalesTests(SimpleTestCase):
    """APDF3 — LA fonction des deux moteurs (sans base ni rendu)."""

    def tearDown(self):
        G._apply_entreprise(None)

    def test_profil_seul_forme_capital_sans_gerant(self):
        ent = {'nom': 'TAQINOR Démo', 'forme_juridique': 'SARLAU',
               'capital_social': '100 000,00 MAD', 'rc': '198453',
               'ice': '002589631000045', 'identifiant_fiscal': '48291057',
               'patente': '35201478'}
        self.assertEqual(identite.mentions_legales(ent), [
            '<b>TAQINOR Démo</b> SARLAU au capital de 100 000,00 MAD',
            'RC 198453', 'ICE 002589631000045'])
        self.assertEqual(identite.mentions_legales(
            ent, gras=None, fiscales=True)[2:], [
            'ICE 002589631000045', 'IF 48291057', 'Patente 35201478'])
        self.assertIsNone(identite.mentions_legales({}))

    def test_bande_et_ligne_legacy_meme_ice_meme_rc(self):
        from apps.ventes.quote_engine.residential import theme
        ent = {'nom': 'TAQINOR X', 'rc': '198453', 'ice': '0025'}
        bande = theme.bande_legale({'entreprise': ent}, {})
        G._apply_entreprise(ent)
        for valeur in ('RC 198453', 'ICE 0025'):
            self.assertIn(valeur, bande)
            self.assertIn(valeur, G.ENT_LEGAL_LINE)
        for ligne in (bande, G.ENT_LEGAL_LINE):
            self.assertNotIn('691213', ligne)
            self.assertNotIn('Reda Kasri', ligne)


@tag('pdf')
class LogoTests(TestCase):
    """APDF4 (C-APDF-001) — logo de la société sur tous les formats."""

    CLE = 'logos/apdf4.png'

    def setUp(self):
        self.company = make_company(slug='apdf4-co', nom='APDF4')
        profil(self.company, nom='TAQINOR Démo (complet)',
               ice='002589631000045', logo_key=self.CLE)
        self.devis = devis_residentiel(self.company, 'DEV-APDF4-1')
        brut = png_rouge()
        patcher = mock.patch(
            'apps.ventes.utils.pdf._download',
            lambda bucket, cle: brut if cle == self.CLE else None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_logo_societe_tous_formats(self):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, clean_pdf_options)
        from apps.ventes.utils.pdf import _company_context
        data = build_quote_data(self.devis, dict(
            clean_pdf_options({}), _embed_roof_render=True))
        self.assertEqual(data['entreprise']['logo_uri'],
                         _company_context(self.company)['logo_uri'])
        taille = taille_logo_taqinor()
        for nom in ('defaut', 'include_etude', 'onepage'):
            with self.subTest(format=nom):
                images = images_page(rendre_pdf(self.devis, FORMATS[nom]))
                self.assertTrue(any(est_rouge(i) for i in images), nom)
                self.assertFalse(any(i.size == taille for i in images), nom)

    def test_societe_sans_logo_pas_de_logo_taqinor(self):
        autre = make_company(slug='apdf4-autre', nom='APDF4 autre')
        profil(autre, nom='SOLAIRE EXEMPLE SARL', ice='001111111000011')
        devis = devis_residentiel(autre, 'DEV-APDF4-2')
        taille = taille_logo_taqinor()
        for nom in ('defaut', 'include_etude', 'onepage'):
            with self.subTest(format=nom):
                images = images_page(rendre_pdf(devis, FORMATS[nom]))
                self.assertFalse(any(i.size == taille for i in images), nom)


class LogoRegleTests(SimpleTestCase):
    """APDF4 — LA règle du logo, sans base ni rendu PDF."""

    def tearDown(self):
        G._apply_entreprise(None)

    def test_aucun_profil_logo_taqinor(self):
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(theme.logo_imprime_b64({}), theme.logo_dark_b64())
        self.assertEqual(theme.logo_imprime_b64({}, sombre=False),
                         theme.logo_color_b64())
        G._apply_entreprise(None)
        self.assertIsNone(G.ENT_LOGO_B64)

    def test_profil_sans_logo_bandeau_neutre(self):
        from apps.ventes.quote_engine.residential import theme
        data = {'entreprise': {'nom': 'SOLAIRE EXEMPLE SARL'}}
        self.assertEqual(theme.logo_imprime_b64(data),
                         theme._PIXEL_TRANSPARENT_B64)
        G._apply_entreprise(data['entreprise'])
        self.assertNotIn(G._logo_dark_b64(), G.logo_html())

    def test_logo_televerse_imprime_par_les_deux_moteurs(self):
        import base64
        import io
        from PIL import Image
        from apps.ventes.quote_engine.residential import theme
        uri = 'data:image/png;base64,' + base64.b64encode(
            png_rouge()).decode()
        ent = {'nom': 'X', 'logo_uri': uri}
        b64 = theme.logo_imprime_b64({'entreprise': ent})
        img = Image.open(io.BytesIO(base64.b64decode(b64))).convert('RGB')
        self.assertTrue(est_rouge(img))
        G._apply_entreprise(ent)
        self.assertIn(b64, G.logo_html())
        self.assertIn(b64, G.logo_p1_dark())
