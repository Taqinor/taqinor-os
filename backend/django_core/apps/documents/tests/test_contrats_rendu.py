"""Dossier contractuel — rendu des cinq contenus du contrat d'API et
références de loi des textes par défaut (sans base de données).

- ``html_de`` rend chaque contenu d'exemple (contract_samples/acte_contractuel
  .json), sans accolade restée ni prix d'achat ;
- palier « pdf » : pagination de référence (contrat ≤ 6 pages, procès-verbaux
  ≤ 2, clôture ≤ 4 — docs/contrats/conception.md § 7) et PDF signé portant le
  nom du signataire ;
- toute référence de loi que PRODUISENT les fabriques de ``textes.py``
  (« article », « loi n° »), toutes options, figure dans
  docs/contrats/juridique.md § 2 (critère K9).

Run :
    powershell -File scripts/test-backend.ps1 \
        -Modules "apps.documents.tests.test_contrats_rendu"
"""
import copy
import itertools
import json
import re
import unittest
from pathlib import Path

import fitz
from django.test import tag

from apps.documents.contrats.rendu import html_de, pdf_de

ECHANTILLON = (Path(__file__).resolve().parents[1] / 'contract_samples'
               / 'acte_contractuel.json')


def juridique():
    """docs/contrats/juridique.md, cherché en remontant depuis ce fichier
    (.../backend/django_core/apps/documents/tests/ → racine du dépôt)."""
    for dossier in Path(__file__).resolve().parents:
        chemin = dossier / 'docs' / 'contrats' / 'juridique.md'
        if chemin.exists():
            return chemin
    raise AssertionError('docs/contrats/juridique.md introuvable')


PAGES_MAX = {'contrat_installation': 6, 'pv_livraison': 2, 'pv_reception': 2,
             'cloture_garanties': 4}
SIG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
       'FcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')


def exemples():
    donnees = json.loads(ECHANTILLON.read_text(encoding='utf-8'))
    return [(cle, v['contenu']) for cle, v in donnees.items()
            if (cle == 'exemple' or cle.startswith('exemple_'))
            and isinstance(v, dict) and isinstance(v.get('contenu'), dict)]


def texte_pdf(octets):
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        return doc.page_count, '\n'.join(p.get_text() for p in doc)
    finally:
        doc.close()


class RenduHtmlTests(unittest.TestCase):

    def test_cinq_exemples(self):
        liste = exemples()
        self.assertEqual(len(liste), 5)
        for cle, contenu in liste:
            with self.subTest(exemple=cle):
                html = html_de(contenu)
                self.assertIn(contenu['reference'], html)
                self.assertNotIn('{', re.sub(r'<style>.*?</style>', '', html,
                                             flags=re.S))
                self.assertNotIn('prix_achat', html)

    def test_type_inconnu(self):
        with self.assertRaises(ValueError):
            html_de({'type': 'inconnu'})


@tag('pdf')
class RenduPdfTests(unittest.TestCase):
    """Rendu WeasyPrint réel (palier « pdf », hors gate rapide)."""

    def test_pagination_de_reference(self):
        for cle, contenu in exemples():
            with self.subTest(exemple=cle):
                pages, texte = texte_pdf(pdf_de(contenu))
                self.assertLessEqual(pages, PAGES_MAX[contenu['type']], cle)
                self.assertIn(contenu['reference'], texte)

    def test_pdf_signe_porte_le_nom(self):
        contenu = copy.deepcopy(exemples()[0][1])
        contenu['signatures']['client'] = {
            'image': SIG, 'nom': 'Youssef EL EXEMPLE',
            'signe_le': '2026-11-24', 'preuve': ' · empreinte 0123456789abcdef'}
        _pages, texte = texte_pdf(pdf_de(contenu))
        self.assertIn('Youssef EL EXEMPLE', texte)
        self.assertIn('24 novembre 2026', texte)


class ReferencesDeLoiTests(unittest.TestCase):
    """K9 — chaque référence de loi des textes français est dans
    juridique.md § 2 (lue au niveau P)."""

    def _section_2(self):
        texte = juridique().read_text(encoding="utf-8")
        debut = texte.index('## 2.')
        fin = texte.index('## 3.', debut)
        return texte[debut:fin]

    @staticmethod
    def _textes_produits():
        """Tout le texte que les fabriques de ``textes.py`` PRODUISENT, toutes
        options allumées et éteintes (le code est exécuté, jamais lu)."""
        from apps.documents.contrats import textes
        morceaux = []
        for booleens in itertools.product((True, False), repeat=3):
            options = dict(zip(('consommateur', 'reserve_propriete',
                                'raccorde_reseau'), booleens),
                           penalite_retard_pct=5)
            for type_acte, variante in (
                    ('contrat_installation', ''),
                    ('pv_livraison', 'reste_a_regler'),
                    ('pv_livraison', 'tranche_reglee'),
                    ('pv_reception', ''), ('cloture_garanties', '')):
                for art in textes.articles_par_defaut(type_acte, variante, {},
                                                      options):
                    morceaux += [art['titre']] + art['paragraphes']
        morceaux += textes.quitus_par_defaut({})
        morceaux += textes.entretien_par_defaut()
        return '\n'.join(morceaux)

    def test_references_de_textes_dans_juridique(self):
        source = self._textes_produits()
        section = self._section_2()
        lois = set(re.findall(r'loi\s+n°\s*(\d{2}-\d{2})', source))
        self.assertTrue(lois)
        for loi in lois:
            with self.subTest(loi=loi):
                self.assertIn(loi, section)
        articles = re.findall(
            r'articles?\s+(\d+(?:-\d+)?)(?:\s+(?:à|et)\s+(\d+(?:-\d+)?))?',
            source)
        self.assertTrue(articles)
        for premier, second in articles:
            for numero in filter(None, (premier, second)):
                with self.subTest(article=numero):
                    self.assertRegex(section, rf'(?<![\d.]){re.escape(numero)}'
                                              rf'(?!\d)')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
