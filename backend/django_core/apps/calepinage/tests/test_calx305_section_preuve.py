"""CALX305 — la section « Régime de preuve et empreinte » du rapport.

Ce qui est prouvé ici :

* le régime imprimé (``methode``, ``methode_exacte``, ``optimal``,
  ``total_retenu``, ``total_optimal``, ``borne_superieure``, ``libelle``,
  ``pas_cm``, ``nb_optima``) est ÉGAL, clé par clé, à ``resultat['preuve']``
  — REPORTÉ par ``note_calcul.verdict_de_preuve``, jamais recalculé (même
  garantie que CAL177) ;
* une marge NON MESURÉE (``None``) s'imprime « non mesuré », jamais « 0 » ;
* l'encart dit ce que « optimum prouvé » signifie et ce qu'il ne signifie
  PAS ;
* contrôles passés, cotes à confirmer, motifs de non-engageabilité et
  avertissements du moteur, quand ils existent, sont imprimés ;
* dans le rapport assemblé, la section passe par ce rédacteur, sa feuille
  est posée dans le ``<head>``, et — en rendu PDF réel — l'empreinte paraît
  UNE FOIS PAR PAGE (pied courant du gabarit), pas seulement dans le corps
  de la section.

Run :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx305_section_preuve.py -q
"""
import copy
import json
import pathlib
import re
import unittest
from types import SimpleNamespace

from django.test import tag

from apps.calepinage.services.note_calcul import (
    CLES_MARGES, CLES_VERDICT, _valeur_verdict,
)
from apps.calepinage.services.rapport import (
    construire_rapport, html_de_rapport,
)
from apps.calepinage.services.rapport.preuve import (
    ENCART_OPTIMUM_PROUVE, html_de_section,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def _charger(nom):
    return json.loads((RACINE_APP / 'contract_samples' / f'{nom}.json')
                      .read_text(encoding='utf-8'))


#: Le résultat BRUT du moteur : le régime y vit sous ``preuve`` (comme dans
#: CAL177 — ``test_cal177_verdict.py``), et l'entrée exigée de la section
#: (``hash_entree``) y est publiée.
RESULTAT_MOTEUR = _charger('pose')['exemple']
RESULTAT_SANS_REGIME = _charger('calepinage_resultat')['exemple']
MOTIF = (
    "Aucune empreinte d'entrée publiée : le calepinage n'a pas encore "
    "été calculé.")


def contexte(resultat, langue='fr'):
    return {'resultat': resultat, 'langue': langue,
            'section': {'code': 'preuve', 'motif_si_absent': MOTIF}}


class EgaliteAvecLeResultatTest(unittest.TestCase):
    """Le régime imprimé est celui que le moteur publie sous ``preuve``."""

    def setUp(self):
        self.resultat = copy.deepcopy(RESULTAT_MOTEUR)
        self.html = html_de_section(contexte(self.resultat))

    def test_chaque_cle_du_regime_est_egale_a_celle_du_resultat(self):
        # Même formatage que le rendu (`_valeur_verdict` : un booléen
        # s'imprime « oui »/« non », jamais `True`/`False`) — la garantie
        # vérifiée est l'ÉGALITÉ de la VALEUR, pas de sa représentation
        # Python.
        preuve = self.resultat['preuve']
        for cle in CLES_VERDICT:
            with self.subTest(cle=cle):
                self.assertIn(
                    str(_valeur_verdict(preuve[cle])), self.html,
                    'valeur de « %s » absente du rendu' % cle)

    def test_chaque_marge_mesuree_est_egale_a_celle_du_resultat(self):
        marges = self.resultat['marges']
        for cle in CLES_MARGES:
            with self.subTest(cle=cle):
                self.assertIn(
                    str(_valeur_verdict(marges[cle])), self.html,
                    'valeur de la marge « %s » absente du rendu' % cle)

    def test_les_controles_passes_sont_imprimes(self):
        for controle in self.resultat['preuve']['controles']:
            self.assertIn(controle, self.html)

    def test_optimum_prouve_est_imprime_pour_ce_resultat(self):
        self.assertIn('Optimum prouv', self.html)


class MargeNonMesureeTest(unittest.TestCase):
    def test_une_marge_none_imprime_non_mesure_jamais_zero(self):
        resultat = copy.deepcopy(RESULTAT_MOTEUR)
        resultat['marges'] = {'troncon_min_cm': None, 'bande_min_cm': None,
                              'rangee_critique': None,
                              'obstacle_critique': None}
        html = html_de_section(contexte(resultat))
        self.assertEqual(html.count('non mesuré'), 4)
        self.assertNotIn('<td>0</td>', html)

    def test_un_resultat_sans_regime_publie_reste_non_mesure(self):
        # `calepinage_resultat.json` ne publie ni `preuve`, ni `marges`,
        # ni les champs plats : aucune valeur n'est fabriquée pour autant.
        html = html_de_section(contexte(copy.deepcopy(RESULTAT_SANS_REGIME)))
        self.assertEqual(html.count('non mesuré'), len(CLES_VERDICT)
                         + len(CLES_MARGES))


class EncartTest(unittest.TestCase):
    def test_l_encart_dit_ce_que_le_mot_signifie_et_ne_signifie_pas(self):
        html = html_de_section(contexte(copy.deepcopy(RESULTAT_MOTEUR)))
        self.assertIn('encart-preuve', html)
        self.assertIn('signifie', ENCART_OPTIMUM_PROUVE)
        self.assertIn('NE signifie PAS', ENCART_OPTIMUM_PROUVE)


class CotesEtMotifsTest(unittest.TestCase):
    def test_une_cote_a_confirmer_est_listee(self):
        resultat = copy.deepcopy(RESULTAT_SANS_REGIME)
        resultat['cotes_a_confirmer'] = ['Hauteur OSM du pan P1']
        html = html_de_section(contexte(resultat))
        self.assertIn('Cotes à confirmer', html)
        self.assertIn('Hauteur OSM du pan P1', html)

    def test_un_motif_de_non_engageabilite_est_liste(self):
        resultat = copy.deepcopy(RESULTAT_SANS_REGIME)
        resultat['motifs_non_engageable'] = ['Obstacle OBS-1 non coté']
        html = html_de_section(contexte(resultat))
        self.assertIn('Motifs de non-engageabilité', html)
        self.assertIn('Obstacle OBS-1 non coté', html)

    def test_sans_cote_ni_motif_rien_n_est_imprime(self):
        html = html_de_section(contexte(copy.deepcopy(RESULTAT_SANS_REGIME)))
        self.assertNotIn('Cotes à confirmer', html)
        self.assertNotIn('non-engageabilité', html)


class AvertissementsTest(unittest.TestCase):
    def test_les_avertissements_du_moteur_sont_imprimes(self):
        resultat = copy.deepcopy(RESULTAT_SANS_REGIME)
        resultat['avertissements'] = ['Simulation périmée : conception '
                                      'modifiée après le dernier calcul.']
        html = html_de_section(contexte(resultat))
        self.assertIn('Avertissements du moteur', html)
        self.assertIn('Simulation périmée', html)


class DansLeRapportTest(unittest.TestCase):
    def test_la_section_passe_par_ce_redacteur_et_sa_feuille_est_en_tete(self):
        rapport = construire_rapport(
            SimpleNamespace(company=None, client_id=None, lead_id=None,
                            titre='Villa', resultat=None, pk=None),
            resultat=copy.deepcopy(RESULTAT_SANS_REGIME),
            site={}, identite={}, styles={})
        html = html_de_rapport(rapport)
        section = re.search(r'<section class="section-rapport" '
                            r'data-section="preuve">.*?</section>',
                            html, re.S).group(0)
        self.assertIn('regime-preuve', section)
        self.assertIn('.regime-preuve th', html.split('</head>')[0])
        self.assertNotIn('<style>', html.split('</head>')[1])


@tag('pdf')
class RenduReelTest(unittest.TestCase):
    """WeasyPrint + PyMuPDF réels — l'empreinte paraît UNE FOIS PAR PAGE."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    def test_l_empreinte_paraît_une_fois_par_page_du_rapport(self):
        import fitz

        from apps.calepinage.services.pack_technique import compter_pages
        from apps.calepinage.services.rapport import rendre_rapport

        resultat = copy.deepcopy(RESULTAT_SANS_REGIME)
        nu = SimpleNamespace(
            company=None, client_id=None, lead_id=None,
            titre='Villa Anfa', resultat=None, pk=None)
        site = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
                'source': 'roof_point'}
        identite = {'titre_document': "Rapport d'étude",
                    'projet': 'Villa Anfa', 'client': 'Mme Bennani'}
        styles = {'nom_affiche': 'Soleil Atlas'}
        octets = rendre_rapport(nu, resultat=resultat, site=site,
                                identite=identite, styles=styles)
        pages = compter_pages(octets)
        self.assertGreater(pages, 1, 'le rapport tient sur une seule page')
        document = fitz.open(stream=octets, filetype='pdf')
        try:
            texte = '\n'.join(page.get_text() for page in document)
        finally:
            document.close()
        # La marque courte de l'empreinte (`hash_court`) : le hash de
        # l'échantillon commence par « abababab ».
        self.assertEqual(texte.count('abababab'), pages,
                         "l'empreinte n'apparaît pas exactement une fois "
                         "par page (%d occurrences, %d pages)"
                         % (texte.count('abababab'), pages))


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
