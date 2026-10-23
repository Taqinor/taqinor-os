"""AGR319 — annexe « Note de calcul du kit de pompage » (pièce du dossier
FDA, Guide FDA 2024 p.21), rendue par le renderer agricole SEULEMENT sur
l'option explicite ``include_note_calcul``.

HTML réel (``pages.build_html``) : option off → 3 pages inchangées ; option
on → 4 pages, annexe sans « None », aucun montant d'aide ni ``prix_achat``.
La whitelist ``clean_pdf_options`` ne laisse passer qu'un booléen, défaut off.
PDF réel (``@tag('pdf')``) : 4 pages, aucun débordement.
"""
import re

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import pages, renderer
from apps.ventes.quote_engine.builder import clean_pdf_options
from apps.ventes.tests.test_agr310_renderer_agricole import (
    data_complete, fitz, pages_et_debordements,
)

HYPOTHESES = [
    {'cle': 'energie_hydraulique_wh_par_m3_m', 'valeur': 2.725,
     'statut': 'physique', 'source': 'ρ·g/3600'},
    {'cle': 'rendement_pompe_pct', 'valeur': 55, 'statut': 'estimation',
     'source': None},
]


def _data(option=True, references=None, **kw):
    d = data_complete(**kw)
    d['etude'].update({
        'hmt_composantes': {'niveau_dynamique_m': 40, 'denivele_m': 4,
                            'pertes_lineaires_m': 3.7,
                            'pertes_singulieres_m': 0.8,
                            'pression_service_m': 10.2},
        'conception': {'mois_critique': 12, 'debit_conception_m3h': 30.7},
        'hypotheses_pompage': list(HYPOTHESES),
    })
    d['etude']['provenance_pompage']['entrees']['hmt_saisie_m'] = {
        'origine': 'calculee', 'detail': None, 'date': '2026-09-15'}
    for it in d['all_items']:
        it['description'] = f"Fiche de {it['designation']}"
        it['prix_achat'] = 1234.0  # jamais imprimé
    if option:
        d['include_note_calcul'] = True
        d['references_pompage'] = list(references or [])
    return d


def _html(d):
    return pages.build_html(renderer._augment(d))


def _annexe(html):
    return html.split('<div class="page">')[4]


class Agr319NoteCalculTests(SimpleTestCase):

    def test_option_off_trois_pages_inchangees(self):
        sans = _html(_data(option=False))
        self.assertEqual(sans.count('<div class="page">'), 3)
        self.assertNotIn('Note de calcul', sans)
        self.assertIn('Page 3 / 3', sans)

    def test_option_on_quatre_pages_et_contenu(self):
        html = _html(_data())
        self.assertEqual(html.count('<div class="page">'), 4)
        self.assertIn('Page 4 / 4', html)
        annexe = _annexe(html)
        for attendu in ('Note de calcul du kit de pompage',
                        'Champ photovoltaïque : 7,7 kWc, 14 panneaux',
                        'Pompe immergée OSP 30/8 10 CV',
                        'garantie 3 ans',
                        'Hauteur manométrique totale retenue : 58,7 m',
                        'Pertes linéaires', 'Pression de service',
                        'Débit de conception : 30,7 m³/h (mois critique : '
                        'décembre)',
                        # AGQ12 — libellé client, jamais la clé brute.
                        'Énergie hydraulique par m³ et par mètre de hauteur',
                        'EST.',
                        'Fiche de VARIATEUR VEICHI SI23 7.5KW 380V'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, annexe)
        # AGQ32 — sans référence, aucune phrase ni section.
        self.assertNotIn('Aucune référence', annexe)
        self.assertNotIn('Références de la société', annexe)
        self.assertNotIn('None', annexe)

    def test_annexe_sans_cle_brute_ni_chemin_de_depot(self):
        """AGQ12 (C-AGQ-011) — l'annexe imprime, pour chaque hypothèse de la
        table du noyau, son libellé, sa valeur (plage « min – max ») et sa
        source PUBLIQUE : aucune clé brute, aucun chemin du dépôt, aucune
        décision interne, aucun id de tâche. Mutant : imprimer ``source`` au
        lieu de ``source_client`` ⇒ « docs/ » revient ⇒ rouge."""
        from core.pompage import hypotheses as H
        d = _data()
        d['etude']['hypotheses_pompage'] = H.utilisees([
            'energie_hydraulique_wh_par_m3_m', 'ratio_champ_pompe_bande_alerte',
            'tolerance_conception_pct', 'pertes_pvgis_comprises_pct',
            'rendement_groupe'])
        annexe = _annexe(_html(d))
        bloc = annexe.split('Hypothèses de calcul et leurs sources')[1].split(
            '<div class="ag-sec">')[0]
        for attendu in ('<th>Hypothèse</th>', 'Rapport puissance du champ solaire',
                        '1,2 – 1,5', '-5 – 20',
                        'Règle de dimensionnement de la société',
                        'EST. — Estimation prudente'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, bloc)
        for interdit in ('docs/', 'backend/', 'décision', 'JAMAIS',
                         'ratio_champ_pompe_bande_alerte', 'energie_hydraulique'):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, bloc)
        self.assertIsNone(re.search(r'[A-Z]{3,}\d+', bloc), bloc)
        # Devis d'hier : entrée sans ``libelle`` → lue dans la table par sa clé.
        d['etude']['hypotheses_pompage'] = [
            {'cle': 'cv_vers_kw', 'valeur': 0.7355, 'statut': 'physique',
             'source': 'interne'}]
        bloc = _annexe(_html(d)).split('Hypothèses de calcul')[1]
        self.assertIn('Conversion cheval-vapeur', bloc)
        self.assertNotIn('interne', bloc)

    def test_annexe_porte_hmt_composantes_chaines_et_cartouche(self):
        """AGQ31 (C-AGQ-029) — l'annexe FDA porte le site, les cultures et
        surfaces déclarées, la nature du besoin, la source d'ensoleillement,
        le calage, les chaînes contre l'entrée du variateur, le point de
        fonctionnement, le tableau besoin / livré / couverture, les garanties
        et le cartouche. Valeurs LUES (etude_params, synthèse). Mutant :
        omettre les chaînes ⇒ rouge."""
        d = _data()
        d['etude']['champ']['chaines'] = {
            'serie': 7, 'paralleles': 2, 'voc_froid_v': 360,
            'vmp_chaud_v': 250, 'verifiable': True, 'motif': None}
        d['etude']['variateur'] = {'nom': 'VEICHI SI23 7.5KW'}
        d['etude']['besoin']['cultures'] = [
            {'culture': 'agrumes', 'surface_ha': 4, 'irrigation': 'goutte'}]
        d['etude']['source']['profondeur_calage_m'] = 70
        d['etude']['couverture_pct_mois'] = [104] * 12
        d['etude']['entrees_resolues'] = {
            'localisation': {'valeur': {'ville': 'Taroudant'}}}
        annexe = _annexe(_html(d))
        for attendu in ('Site : Taroudant', 'agrumes · 4 ha · goutte',
                        'Besoin déclaré par vous', 'PVGIS',
                        'Profondeur de calage : 70 m',
                        '7 en série × 2 en parallèle', 'Voc à froid 360 V',
                        'Vmp à chaud 250 V', 'VEICHI SI23 7.5KW',
                        'Point de fonctionnement : 30,5 m³/h à 58,7 m',
                        'Débit de conception', 'Besoin (m³/j)',
                        'Couverture', '104 %', 'Garanties :',
                        'Étude réalisée par Soleil Agri le 05/10/2026'):
            with self.subTest(attendu=attendu):
                self.assertIn(attendu, annexe)
        self.assertEqual(annexe.count('<div class="page">'), 0)
        # Chaînes non vérifiables : le motif servi est dit ; HMT saisie dite.
        d['etude']['champ']['chaines'] = {
            'verifiable': False, 'motif': 'fiche panneau incomplète'}
        d['etude']['hmt'] = {'source': 'saisie', 'composantes': None}
        d['etude']['hmt_composantes'] = {}
        annexe = _annexe(_html(d))
        self.assertIn('Chaînes non vérifiées : fiche panneau incomplète', annexe)
        self.assertIn('HMT saisie telle quelle', annexe)
        self.assertNotIn('None', annexe)

        html = _html(_data(references=[
            {'titre': 'Pompage 7,5 kW', 'ville': 'Taroudant',
             'mise_en_service': '2026-05'}]))
        annexe = _annexe(html)
        self.assertIn('Pompage 7,5 kW — Taroudant (2026-05)', annexe)
        self.assertNotIn('Aucune référence de pompage', annexe)

    def test_aucun_montant_d_aide_ni_prix_achat(self):
        annexe = _annexe(_html(_data()))
        self.assertNotIn('1234', annexe)
        self.assertNotIn('1 234', annexe)
        self.assertNotIn('prix_achat', annexe)
        self.assertNotIn('FDA :', annexe)
        # Aucun montant en dirhams dans l'annexe (ni aide, ni prix).
        self.assertIsNone(re.search(r'\d[\d\s ]*(MAD|DH)\b', annexe))

    def test_whitelist_booleen_defaut_off(self):
        self.assertFalse(clean_pdf_options({})['include_note_calcul'])
        self.assertTrue(
            clean_pdf_options({'include_note_calcul': 1})['include_note_calcul'])
        self.assertFalse(clean_pdf_options(
            {'include_note_calcul': ''})['include_note_calcul'])


@tag('pdf')
class Agr319PdfReelTests(SimpleTestCase):

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def test_off_trois_pages_on_quatre_pages(self):
        for option, attendu in ((False, 3), (True, 4)):
            with self.subTest(option=option):
                n, debords = pages_et_debordements(
                    renderer.render_pdf_bytes(_data(option=option)))
                self.assertEqual(n, attendu)
                self.assertEqual(debords, [])
