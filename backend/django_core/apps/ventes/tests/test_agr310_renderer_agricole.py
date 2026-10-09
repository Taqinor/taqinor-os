"""AGR310 — renderer agricole de 3 pages (P1 eau et argent, P2 comment ça
marche, P3 équipement, prix, garanties) — rendu SEUL.

Deux étages :
  * HTML (aucune base, aucun WeasyPrint) : ``pages.build_html`` sur
    ``renderer._augment(data)`` — formalités, ancres ``figures``, absence de
    « None », d'ONEE, de CO₂, de batterie et des durées de
    ``theme.WARRANTIES`` ;
  * PDF réel (``@tag('pdf')``, WeasyPrint + PyMuPDF) : EXACTEMENT 3 pages, et
    aucun bloc de texte ne déborde sur la bande de pied (mesure du talon,
    patron ``residential.renderer._measure_page_slack``).
"""
import copy
import json
from pathlib import Path

from django.test import SimpleTestCase, tag

from apps.ventes.quote_engine.agricole import pages, renderer

try:  # PyMuPDF — dépendance du backend ; jamais requise à l'import
    import fitz
except Exception:  # pragma: no cover
    fitz = None

_CONTRATS = Path(__file__).resolve().parents[1] / 'contract_samples'

COURBE_OSP_30_8 = {'debits_m3h': [0, 12, 24, 30, 36, 39],
                   'hmt_m': [91, 85, 70, 60, 43, 34]}


def _bloc_agr3_public():
    bloc = json.loads((_CONTRATS / 'economie_pompage.json').read_text(
        encoding='utf-8'))['exemple']
    bloc.pop('vue_interne', None)
    return bloc


def _ligne(designation, qte, pu, **extra):
    it = {'designation': designation, 'marque': '', 'quantite': qte,
          'prix_unit_ht': pu, 'prix_unit_ttc': round(pu * 1.2, 2),
          'taux_tva': 20.0, 'role_pompage': None, 'courbe_pompe': None,
          'garantie_mois': None, 'garantie_production_mois': None,
          'ordre': 0}
    it.update(extra)
    return it


def _totaux(items):
    ht = round(sum(it['prix_unit_ht'] * it['quantite'] for it in items), 2)
    tva = round(ht * 0.2, 2)
    return {'ht_brut': ht, 'remise': 0.0, 'arrondi': 0.0, 'ht_net': ht,
            'tva': tva, 'ttc': round(ht + tva, 2)}


def data_complete(nb_lignes_extra=0, nb_options=1):
    """Charge utile ``build_quote_data`` d'un devis de pompage complet —
    valeurs de l'``exemple`` du contrat AGR2 (illustratives)."""
    items = [
        _ligne('Pompe immergée OSP 30/8 10 CV', 1, 15000.0,
               role_pompage='pompe', garantie_mois=36,
               courbe_pompe=copy.deepcopy(COURBE_OSP_30_8)),
        _ligne('VARIATEUR VEICHI SI23 7.5KW 380V', 1, 6000.0,
               role_pompage='variateur_pompage', garantie_mois=18),
        _ligne('Panneau mono 550W', 14, 1100.0),
        _ligne('Structures acier', 14, 375.0),
    ]
    for i in range(nb_lignes_extra):
        items.append(_ligne(f'Accessoire de pompage n°{i + 1}', 1, 250.0))
    options = [
        {'id': 90300 + i, 'designation': f'Option du kit n°{i + 1}',
         'quantite': 1.0, 'prix_unit_ht': 791.67, 'prix_unit_ttc': 950.0,
         'total_ht': 791.67, 'total_ttc': 950.0}
        for i in range(nb_options)]
    etude = {
        'mode_pompe': 'neuve',
        'besoin': {'mode': 'volume_declare', 'volume_m3_jour': 135,
                   'cultures': [], 'region': 'souss-massa'},
        'source': {'niveau_statique_m': 32, 'niveau_dynamique_m': 40,
                   'debit_exploitation_m3h': 36, 'profondeur_forage_m': 90,
                   'volume_reservoir_m3': None},
        'distance_champ_m': 25,
        'besoin_mensuel': {'m3_jour_mois': [135] * 12, 'nature': 'declare',
                           'source_et0': None},
        'production': {
            'm3_jour_mois': [140.3, 161.7, 186.0, 207.4, 219.6, 225.7,
                             228.8, 222.7, 201.3, 173.8, 146.4, 134.2],
            'source_irradiation': 'pvgis', 'mode': 'courbe'},
        'conception': {'mois_critique': 12},
        'champ': {'kwc': 7.7, 'nb_panneaux': 14},
        'ha_irrigables': {'valeur': None},
        # AMOT43 — la forme RÉELLE du producteur (``domain.pompage``).
        'provenance_pompage': {'entrees': {
            'volume_m3_jour': {'origine': 'lead', 'detail': 'client',
                               'date': '2026-09-12'},
            'niveau_dynamique_m': {'origine': 'lead',
                                   'detail': 'mesure_visite',
                                   'date': '2026-09-15'},
        }, '_empreinte': 'fixture'},
        'saisies_economie_pompage': {
            'energie_actuelle': {
                'valeur': 'butane',
                'provenance': {'origine': 'saisie', 'detail': None,
                               'date': '2026-09-12'}}},
        'pompe_cv': 10.2, 'pompe_kw': 7.5, 'hmt_m': 58.7,
        'debit_hmt_m3h': 30.5, 'm3_jour': 134.2, 'heures_pompage': 4.4,
        'champ_kwc': 7.7,
    }
    return {
        'ref': 'DEV-AGR310-01', 'date': '05/10/2026',
        'client_name': 'Ali Fellah', 'mode_installation': 'agricole',
        'pdf_mode': 'full', 'etude': etude, 'all_items': items,
        'sans_items': list(items), 'totaux_all': _totaux(items),
        'options_proposees': options,
        'payment_terms': {'acompte': 30, 'materiel': 60, 'solde': 10},
        'valid_until': '04/11/2026', 'entreprise': {'nom': 'Soleil Agri'},
        'site_url': 'soleil-agri.example', 'links': {},
        'langue_sortie': 'fr', '_economie_pompage': _bloc_agr3_public(),
    }


def data_minimale():
    """Pompe SANS courbe, aucune économie déclarée, culture inconnue."""
    d = data_complete()
    for it in d['all_items']:
        it['courbe_pompe'] = None
    d.pop('_economie_pompage')
    etude = d['etude']
    etude.pop('saisies_economie_pompage')
    etude['besoin'] = {'mode': 'fao', 'cultures': [], 'region': None,
                       'nature': 'agronomique_plein'}
    etude['besoin_mensuel'] = {'nature': 'agronomique_plein'}
    etude.pop('production')
    d['options_proposees'] = []
    return d


def html_de(data):
    return pages.build_html(renderer._augment(data))


class Agr310HtmlTests(SimpleTestCase):

    def test_formalites_et_ancres_presentes(self):
        html = html_de(data_complete())
        self.assertIn('data-formalite="declaration_8221"', html)
        self.assertIn('data-formalite="prelevement_3615"', html)
        self.assertIn('loi 82-21', html.lower())
        self.assertIn('36-15', html)
        for cle in ('pompe_hmt_m', 'pompe_debit_m3h', 'pompe_volume_m3_jour',
                    'sous_total_ht', 'total_ht', 'tva', 'total_ttc'):
            with self.subTest(cle=cle):
                self.assertIn(f'"{cle}', html)

    def test_aucune_mecanique_residentielle(self):
        html = html_de(data_complete())
        for interdit in ('ONEE', 'CO₂', 'CO2', 'atterie', '87,4',
                         'garantie fabricant', "main-d'œuvre"):
            with self.subTest(interdit=interdit):
                self.assertNotIn(interdit, html)

    def test_garanties_des_fiches_et_argent_present(self):
        html = html_de(data_complete())
        self.assertIn('Garantie constructeur de la pompe : 3 ans', html)
        self.assertIn('Garantie constructeur du variateur : 18 mois', html)
        self.assertIn('Votre argent', html)
        self.assertIn("L'aide FDA éventuelle n'est pas comptée", html)
        self.assertIn('à volume pompé égal', html)

    def test_fixture_minimale_sans_none_avec_motifs(self):
        html = html_de(data_minimale())
        self.assertNotIn('None', html)
        self.assertNotIn('Votre argent', html)
        self.assertIn('Courbe constructeur non disponible', html)
        self.assertIn('culture ou région inconnue', html)

    def test_trois_pages_dans_le_html(self):
        html = html_de(data_complete())
        self.assertEqual(html.count('<div class="page">'), 3)
        self.assertIn('Page 1 / 3', html)
        self.assertIn('Page 3 / 3', html)

    def test_unsupported_sans_ligne_ni_totaux(self):
        d = data_complete()
        d['all_items'] = []
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(d)
        d = data_complete()
        d['totaux_all'] = {}
        with self.assertRaises(renderer.Unsupported):
            renderer._augment(d)

    def test_is_agricole(self):
        class _D:
            mode_installation = 'Agricole '
        self.assertTrue(renderer.is_agricole(_D(), {'pdf_mode': 'full'}))
        self.assertFalse(renderer.is_agricole(_D(), {'pdf_mode': 'onepage'}))
        _D.mode_installation = 'residentiel'
        self.assertFalse(renderer.is_agricole(_D(), {'pdf_mode': 'full'}))


def pages_et_debordements(pdf_bytes):
    """``(nb_pages, [(page, y1_mm, footer_top_mm)])`` — un bloc de texte qui
    commence au-dessus de la bande de pied (13 mm) et finit dedans déborde."""
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    debords = []
    for i, page in enumerate(doc):
        mm = page.rect.height / 297.0
        footer_top = page.rect.height - 13.0 * mm
        for b in page.get_text('blocks'):
            if b[1] < footer_top - 0.5 * mm and b[3] > footer_top + 0.5 * mm:
                debords.append((i + 1, round(b[3] / mm, 1),
                                round(footer_top / mm, 1)))
    n = len(doc)
    doc.close()
    return n, debords


@tag('pdf')
class Agr310PdfReelTests(SimpleTestCase):

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def _verifier(self, data):
        n, debords = pages_et_debordements(renderer.render_pdf_bytes(data))
        self.assertEqual(n, 3)
        self.assertEqual(debords, [], 'contenu sous la bande de pied')

    def test_fixture_complete_trois_pages(self):
        self._verifier(data_complete())

    def test_fixture_minimale_trois_pages(self):
        self._verifier(data_minimale())

    def test_douze_lignes_six_options_trois_pages(self):
        self._verifier(data_complete(nb_lignes_extra=8, nb_options=6))
