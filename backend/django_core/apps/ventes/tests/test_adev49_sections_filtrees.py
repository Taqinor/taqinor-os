"""ADEV49 (C-ADEV-016) — la charge publique est filtrée par LA table
``CLES_PAR_SECTION`` : une case « Synthèse d'économies » décochée ne laisse
partir aucune économie (``eco_*``, ``roi_*``, ``savings_method``,
``hypotheses``, ``facture_*``…) à AUCUN niveau du JSON servi (``quote``
compris) ; une case PDF décochée sert ``pdf_disponible: false``.
Sonde VA p9 : ``eco_s_ann 15381 … roi_s 4.0 … facture_sans_solaire 16493``
servis sous ``sections={'economies': False, 'pdf': False}``.

Test-du-test : retirer ``eco_s_ann`` de la table ⇒ ``test_toute_cle_d_economie_est_classee``
la nomme (et ``test_economies_decochee_rien_a_aucun_niveau`` la trouve).

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev49_sections_filtrees -v 2
"""
import re

from django.test import TestCase

from apps.ventes.models import ShareLink
from apps.ventes.public_views import CLES_PAR_SECTION

from .test_adev50_cumul_25_ans_servi import devis_deux_options, lire

#: Forme d'une clé d'économies : toute clé servie qui la porte DOIT être
#: classée dans ``CLES_PAR_SECTION['economies']``.
MOTIF_ECONOMIES = re.compile(
    r'^(eco_|roi_|factures?_|savings_|hypotheses$|cashflow_|net_gain_)')


def occurrences(noeud, chemin='', ancetres=()):
    """(chemin, clé, valeur, ancêtres) de toutes les clés, à toute profondeur."""
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            ici = f'{chemin}.{cle}' if chemin else str(cle)
            yield ici, cle, valeur, ancetres
            yield from occurrences(valeur, ici, ancetres + (cle,))
    elif isinstance(noeud, list):
        for i, valeur in enumerate(noeud):
            yield from occurrences(valeur, f'{chemin}[{i}]', ancetres)


class SectionsFiltreesTests(TestCase):

    def setUp(self):
        self.devis = devis_deux_options('adev49')

    def _payload(self, sections=None):
        link = ShareLink.objects.create(
            company=self.devis.company, devis=self.devis,
            sections=sections or {})
        resp = lire(link.token)
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def test_economies_decochee_rien_a_aucun_niveau(self):
        servi = self._payload()
        # Prémisse : avec la case cochée, des économies partent bien.
        self.assertTrue(any(
            cle in CLES_PAR_SECTION['economies'] and valeur is not None
            for _c, cle, valeur, _a in occurrences(servi.get('quote') or {})))

        for section, cles in CLES_PAR_SECTION.items():
            with self.subTest(section=section):
                retire = self._payload({section: False})
                fuites = [
                    chemin for chemin, cle, valeur, _a in occurrences(retire)
                    if cle in cles and (
                        '.' in chemin or '[' in chemin or valeur is not None)]
                self.assertEqual(fuites, [], f'{section} décochée : servi')

    def test_rejoue_va_p9(self):
        retire = self._payload(
            {'economies': False, 'pdf': False, 'roof3d': False})
        quote = retire.get('quote') or {}
        for cle in ('eco_s_ann', 'roi_s', 'facture_sans_solaire',
                    'savings_method', 'hypotheses'):
            self.assertNotIn(cle, quote, cle)
        for cle in ('savings_method', 'hypotheses', 'facture_sans_solaire'):
            self.assertIsNone(retire.get(cle), cle)
        self.assertIs(retire['pdf_disponible'], False)

    def test_toute_cle_d_economie_est_classee(self):
        servi = self._payload()
        table = CLES_PAR_SECTION['economies']
        # Une clé sous un bloc DÉJÀ classé (``offres_tailles``…) part avec lui.
        non_classees = sorted({
            cle for _c, cle, _v, ancetres in occurrences(servi)
            if isinstance(cle, str) and MOTIF_ECONOMIES.match(cle)
            and cle not in table and not set(ancetres) & set(table)})
        self.assertEqual(
            non_classees, [],
            'clé(s) d\'économies servie(s) sans classement dans '
            'CLES_PAR_SECTION')

    def test_cases_cochees_rendu_inchange(self):
        servi = self._payload()
        self.assertIs(servi['pdf_disponible'], True)
        self.assertIsNotNone((servi.get('quote') or {}).get('eco_s_ann'))
        self.assertEqual(self._payload({'pdf': False})['option_totals'],
                         servi['option_totals'])
