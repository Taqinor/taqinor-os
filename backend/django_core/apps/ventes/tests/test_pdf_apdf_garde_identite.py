"""APDF45 (C-APDF-001) — garde de la classe « identité d'une autre société ».

Un profil « SOLAIRE EXEMPLE SARL » (ICE 001111111000011, sans RIB, sans site,
sans logo) et un devis par marché (résidentiel, commercial, industriel,
agricole) : chaque format servi par /proposal (défaut, une-page,
include_etude, devis_final, devis_final + include_etude) est RENDU pour de vrai
(``generate_premium_devis_pdf`` : registre des renderers et repli legacy,
MinIO remplacé en mémoire — ``test_pdf_apdf_identite.rendre_pdf``) puis lu par
PyMuPDF : aucun texte TAQINOR (RC, ICE, RIB Saham, gérant, liens du site) et
aucune image aux dimensions de l'asset ``assets/logo.png``. Couvre les
appelants d'APDF2 à APDF5. Le test liste les rendus effectués.

Test-du-test : réintroduire un littéral « RIB 022 780 » dans un seul gabarit
⇒ le cas (marché, format) correspondant échoue.
"""
from django.test import TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)
from apps.ventes.tests.test_pdf_apdf_identite import (
    ETUDE_RESIDENTIEL, LIGNES_RESIDENTIEL, profil, rendre_pdf,
    taille_logo_taqinor,
)

#: Textes d'identité TAQINOR qui ne doivent JAMAIS sortir sous un autre nom.
INTERDITS = (
    '691213', '003799642000067', 'Saham', '022 780', '022 780',
    '0002720029379418', 'Reda Kasri', 'taqinor.ma/realisations',
    'taqinor.ma/produits', 'taqinor.ma/garanties',
)

#: Un devis par marché : (lignes, etude_params, mode_installation).
MARCHES = {
    'residentiel': (LIGNES_RESIDENTIEL, ETUDE_RESIDENTIEL, 'residentiel'),
    'commercial': ([('Panneau mono 450W', '40', '1500'),
                    ('Onduleur réseau 20 kW', '1', '30000')],
                   None, 'commercial'),
    'industriel': ([('Panneau mono 450W', '40', '1500'),
                    ('Onduleur réseau 20 kW', '1', '30000')],
                   None, 'industriel'),
    'agricole': ([('Pompe immergée 5,5 CV', '1', '18000'),
                  ('Panneau mono 550W', '12', '1100')],
                 {'pompe_cv': '5.5', 'pompe_kw': 4.05,
                  'type_pompe': 'immergee', 'alim': 'tri', 'hmt_m': '80',
                  'champ_kwc': 5.68}, 'agricole'),
}

FORMATS = {
    'defaut': {},
    'onepage': {'pdf_mode': 'onepage'},
    'include_etude': {'include_etude': True},
    'devis_final': {'devis_final': True},
    'devis_final_etude': {'devis_final': True, 'include_etude': True},
}


def lire_pdf(octets):
    """(texte de toutes les pages, tailles des images embarquées)."""
    import io
    import fitz
    from PIL import Image
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        texte = '\n'.join(page.get_text() for page in doc)
        tailles = []
        for page in doc:
            for info in page.get_images(full=True):
                brut = doc.extract_image(info[0])
                with Image.open(io.BytesIO(brut['image'])) as img:
                    tailles.append(img.size)
        return texte, tailles
    finally:
        doc.close()


@tag('pdf')
class GardeIdentiteTests(TestCase):

    def setUp(self):
        self.company = make_company(slug='apdf45-co', nom='APDF45')
        profil(self.company, nom='SOLAIRE EXEMPLE SARL',
               ice='001111111000011', rib='', banque='', site_web='',
               logo_key='')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, marche):
        lignes, etude, mode = MARCHES[marche]
        devis = make_devis(self.company, self.user, self.client_obj, lignes,
                           reference=f'DEV-APDF45-{marche[:4].upper()}',
                           etude_params=dict(etude) if etude else None)
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        return devis

    def test_aucune_identite_taqinor_marche_par_format(self):
        taille_taqinor = taille_logo_taqinor()
        rendus = []
        for marche in MARCHES:
            devis = self._devis(marche)
            for nom, options in FORMATS.items():
                with self.subTest(marche=marche, format=nom):
                    texte, tailles = lire_pdf(rendre_pdf(devis, options))
                    rendus.append((marche, nom))
                    self.assertTrue(texte.strip())
                    for interdit in INTERDITS:
                        self.assertNotIn(interdit, texte)
                    self.assertNotIn(taille_taqinor, tailles)
        # Le test LISTE les rendus effectués : 4 marchés × 5 formats.
        self.assertEqual(len(rendus), len(MARCHES) * len(FORMATS), rendus)
