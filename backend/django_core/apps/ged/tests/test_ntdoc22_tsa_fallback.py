"""NTDOC22 — Horodatage RFC 3161 : liste de TSA de secours + repli.

Couvre :
  * la liste effective des TSA (priorité à `GED_TSA_URL`, puis `GED_TSA_URLS`,
    dédoublonnée, ordre préservé) ;
  * aucune TSA configurée = comportement XGED5 inchangé (sceau sans
    horodatage) ;
  * une seule URL configurée qui répond = comportement XGED5 inchangé ;
  * la PREMIÈRE TSA en échec bascule automatiquement sur la SECONDE ;
  * toutes en échec = document quand même scellé, SANS horodatage (jamais
    bloquant) ;
  * sans pyHanko, `sceller_pdf` reste un no-op qui rend le PDF inchangé.
"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.ged import services


PDF = b'%PDF-1.4 document signe'
SCELLE = b'%PDF-1.4 document scelle'


class ListeTsaTests(SimpleTestCase):
    @override_settings(GED_TSA_URL='', GED_TSA_URLS='')
    def test_aucune_tsa_configuree(self):
        self.assertEqual(services.tsa_urls_configurees(), [])
        self.assertEqual(services.tsa_url_configuree(), '')

    @override_settings(GED_TSA_URL='https://tsa-a.example', GED_TSA_URLS='')
    def test_une_seule_url_historique(self):
        self.assertEqual(services.tsa_urls_configurees(),
                         ['https://tsa-a.example'])
        self.assertEqual(services.tsa_url_configuree(),
                         'https://tsa-a.example')

    @override_settings(
        GED_TSA_URL='https://tsa-a.example',
        GED_TSA_URLS=' https://tsa-b.example , https://tsa-c.example ')
    def test_secours_apres_la_principale_espaces_ignores(self):
        self.assertEqual(services.tsa_urls_configurees(), [
            'https://tsa-a.example',
            'https://tsa-b.example',
            'https://tsa-c.example',
        ])

    @override_settings(GED_TSA_URL='https://tsa-a.example',
                       GED_TSA_URLS='https://tsa-a.example')
    def test_doublon_dedoublonne(self):
        self.assertEqual(services.tsa_urls_configurees(),
                         ['https://tsa-a.example'])

    @override_settings(GED_TSA_URL='', GED_TSA_URLS='https://tsa-b.example')
    def test_liste_seule_utilisable(self):
        self.assertEqual(services.tsa_urls_configurees(),
                         ['https://tsa-b.example'])
        self.assertEqual(services.tsa_url_configuree(),
                         'https://tsa-b.example')

    @override_settings(GED_TSA_URL='',
                       GED_TSA_URLS=['https://tsa-b.example', ''])
    def test_liste_python_acceptee(self):
        self.assertEqual(services.tsa_urls_configurees(),
                         ['https://tsa-b.example'])


class _FauxTimeStamper:
    """Horodateur factice : mémorise l'URL, ne contacte jamais le réseau."""

    def __init__(self, url):
        self.url = url


class ScellementFallbackTests(SimpleTestCase):
    def setUp(self):
        self.appels = []

        def _faux_sceller(pdf_bytes, signataire, timestamper):
            url = getattr(timestamper, 'url', None)
            self.appels.append(url)
            if url in self.tsa_en_echec:
                raise RuntimeError(f'TSA injoignable : {url}')
            return SCELLE

        self.tsa_en_echec = set()
        self._patches = [
            mock.patch.object(services, '_pades_signer_disponible',
                              return_value=True),
            mock.patch.object(services, '_certificat_societe_pour_scellement',
                              return_value=object()),
            mock.patch.object(services, '_sceller_avec_timestamper',
                              side_effect=_faux_sceller),
            mock.patch.object(services, '_timestamper_http',
                              side_effect=_FauxTimeStamper),
        ]
        for patch in self._patches:
            patch.start()
            self.addCleanup(patch.stop)

    @override_settings(GED_TSA_URL='', GED_TSA_URLS='')
    def test_sans_tsa_sceau_sans_horodatage(self):
        octets, scelle = services.sceller_pdf(PDF)
        self.assertTrue(scelle)
        self.assertEqual(octets, SCELLE)
        # Une seule tentative, SANS horodateur — comportement XGED5 inchangé.
        self.assertEqual(self.appels, [None])

    @override_settings(GED_TSA_URL='https://tsa-a.example', GED_TSA_URLS='')
    def test_une_tsa_qui_repond_comportement_inchange(self):
        octets, scelle = services.sceller_pdf(PDF)
        self.assertTrue(scelle)
        self.assertEqual(octets, SCELLE)
        self.assertEqual(self.appels, ['https://tsa-a.example'])

    @override_settings(GED_TSA_URL='https://tsa-a.example',
                       GED_TSA_URLS='https://tsa-b.example')
    def test_premiere_en_echec_bascule_sur_la_seconde(self):
        self.tsa_en_echec = {'https://tsa-a.example'}
        octets, scelle = services.sceller_pdf(PDF)
        self.assertTrue(scelle)
        self.assertEqual(octets, SCELLE)
        self.assertEqual(
            self.appels,
            ['https://tsa-a.example', 'https://tsa-b.example'])

    @override_settings(GED_TSA_URL='https://tsa-a.example',
                       GED_TSA_URLS='https://tsa-b.example')
    def test_toutes_en_echec_sceau_sans_horodatage(self):
        self.tsa_en_echec = {'https://tsa-a.example', 'https://tsa-b.example'}
        octets, scelle = services.sceller_pdf(PDF)
        self.assertTrue(scelle)
        self.assertEqual(octets, SCELLE)
        # Les deux TSA tentées, puis un dernier essai SANS horodateur.
        self.assertEqual(
            self.appels,
            ['https://tsa-a.example', 'https://tsa-b.example', None])


class NoOpSansPyhankoTests(SimpleTestCase):
    def test_sans_la_lib_le_pdf_est_rendu_inchange(self):
        with mock.patch.object(services, '_pades_signer_disponible',
                               return_value=False):
            octets, scelle = services.sceller_pdf(PDF)
        self.assertFalse(scelle)
        self.assertEqual(octets, PDF)

    def test_sans_certificat_le_pdf_est_rendu_inchange(self):
        with mock.patch.object(services, '_pades_signer_disponible',
                               return_value=True), \
                mock.patch.object(
                    services, '_certificat_societe_pour_scellement',
                    return_value=None):
            octets, scelle = services.sceller_pdf(PDF)
        self.assertFalse(scelle)
        self.assertEqual(octets, PDF)
