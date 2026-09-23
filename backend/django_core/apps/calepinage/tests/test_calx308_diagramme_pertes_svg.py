"""CALX308 — le diagramme de pertes rendu en SVG côté serveur.

Ce qui est prouvé ici, sur la cascade du CONTRAT
(``contract_samples/calepinage_pertes_cascade.json``, CALX141) :

* la somme des hauteurs de barres, relue à l'échelle publiée
  (``data-px-par-point``), correspond aux parts SERVIES à 0,1 point près — et
  chaque barre porte sa part servie telle quelle (AUCUNE part recalculée) ;
* un poste NON SOURCÉ porte le motif de hachure, qu'il ait une part ou qu'il
  soit omis ; une étape omise n'a pas de barre proportionnelle ;
* le SVG se parse en XML, a des dimensions FIXES en pixels, et ne contient ni
  accès réseau (``http://`` hors de l'identifiant d'espace de noms SVG exigé
  par la norme, ``href``, ``@import``) ni police distante ;
* la version embarquée dans le rapport ne porte AUCUNE URI, et la section
  « pertes » du rapport l'embarque ;
* en base (CI) : ``GET …/diagramme-pertes.svg/`` rend le SVG borné société,
  400 + champ nommé sans résultat ou sans cascade.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx308_diagramme_pertes_svg.py -q
"""
import copy
import json
import pathlib
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.services.diagramme_pertes import (
    ID_HACHURE, DiagrammeRefuse, svg_de_cascade, svg_embarquable,
)
from apps.calepinage.services.rapport import nombre_tel_que_servi
from apps.calepinage.services.rapport.pertes import html_de_section

from .test_api_liste import BaseApiCalepinage, url_detail
from .test_cal171_planche import LAYOUT

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CASCADE = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_pertes_cascade.json')
    .read_text(encoding='utf-8'))
RESULTAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']
SVG_NS = '{http://www.w3.org/2000/svg}'
XMLNS = 'xmlns="http://www.w3.org/2000/svg"'


def cascade():
    return copy.deepcopy(CASCADE['exemple']['cascade'])


def racine(svg):
    return ET.fromstring(svg.encode('utf-8'))


def rects(arbre, classe):
    return [r for r in arbre.iter(SVG_NS + 'rect')
            if classe in (r.get('class') or '').split()]


class HauteursTest(unittest.TestCase):
    def test_la_somme_des_hauteurs_correspond_aux_parts_servies(self):
        donnees = cascade()
        arbre = racine(svg_de_cascade(donnees))
        echelle = float(arbre.get('data-px-par-point'))
        self.assertGreater(echelle, 0)
        barres = rects(arbre, 'barre-poste')
        servies = [e['perte_pct'] for e in donnees['etapes']
                   if e['perte_pct'] is not None]
        self.assertEqual(len(barres), len(servies))
        somme_px = sum(float(b.get('height')) for b in barres)
        self.assertAlmostEqual(somme_px / echelle,
                               sum(abs(p) for p in servies), delta=0.1)

    def test_chaque_barre_porte_sa_part_servie_telle_quelle(self):
        donnees = cascade()
        par_etape = {e['etape']: e['perte_pct'] for e in donnees['etapes']}
        for barre in rects(racine(svg_de_cascade(donnees)), 'barre-poste'):
            with self.subTest(etape=barre.get('data-etape')):
                self.assertEqual(float(barre.get('data-pct')),
                                 par_etape[barre.get('data-etape')])
                self.assertAlmostEqual(
                    float(barre.get('height')),
                    abs(par_etape[barre.get('data-etape')])
                    * float(racine(svg_de_cascade(donnees))
                            .get('data-px-par-point')), delta=0.01)

    def test_les_parts_sont_ecrites_a_cote_des_barres_sans_arrondi(self):
        donnees = cascade()
        donnees['etapes'][2]['perte_pct'] = 8.04
        svg = svg_de_cascade(donnees)
        self.assertIn('8,04 %', svg)
        self.assertIn('%s %% (gain)' % nombre_tel_que_servi(-3.0), svg)

    def test_une_etape_omise_n_a_pas_de_barre_proportionnelle(self):
        arbre = racine(svg_de_cascade(cascade()))
        omises = {r.get('data-etape') for r in rects(arbre, 'barre-omise')}
        self.assertEqual(omises, {'spectral', 'indisponibilite'})
        for barre in rects(arbre, 'barre-omise'):
            self.assertIsNone(barre.get('data-pct'))


class HachureTest(unittest.TestCase):
    def test_le_motif_de_hachure_est_defini(self):
        arbre = racine(svg_de_cascade(cascade()))
        motifs = [p.get('id') for p in arbre.iter(SVG_NS + 'pattern')]
        self.assertEqual(motifs, [ID_HACHURE])

    def test_un_poste_omis_non_source_est_hachure(self):
        arbre = racine(svg_de_cascade(cascade()))
        for barre in rects(arbre, 'barre-omise'):
            self.assertEqual(barre.get('fill'), 'url(#%s)' % ID_HACHURE)

    def test_un_poste_non_source_avec_une_part_est_hachure(self):
        donnees = cascade()
        donnees['etapes'][2]['source'] = None        # thermique, 8 %
        arbre = racine(svg_de_cascade(donnees))
        thermique = [b for b in rects(arbre, 'barre-poste')
                     if b.get('data-etape') == 'thermique'][0]
        self.assertEqual(thermique.get('fill'), 'url(#%s)' % ID_HACHURE)
        self.assertEqual(thermique.get('data-source'), 'non')
        sourcee = [b for b in rects(arbre, 'barre-poste')
                   if b.get('data-etape') == 'irradiation_plan'][0]
        self.assertNotIn('url(', sourcee.get('fill'))

    def test_le_poste_non_source_est_nomme(self):
        self.assertIn('Indisponibilité réseau et maintenance (source non '
                      'renseignée)', svg_de_cascade(cascade()))


class AutonomieTest(unittest.TestCase):
    def setUp(self):
        self.svg = svg_de_cascade(cascade())

    def test_le_svg_se_parse_en_xml_aux_dimensions_fixes_en_pixels(self):
        arbre = racine(self.svg)
        self.assertEqual(arbre.tag, SVG_NS + 'svg')
        self.assertRegex(arbre.get('width'), r'^\d+(\.\d+)?px$')
        self.assertRegex(arbre.get('height'), r'^\d+(\.\d+)?px$')

    def test_aucun_acces_reseau(self):
        # La SEULE URI tolérée est l'identifiant d'espace de noms SVG (exigé
        # par la norme pour qu'un fichier .svg soit lu comme du SVG, jamais
        # chargé) ; tout le reste est interdit.
        self.assertEqual(self.svg.count(XMLNS), 1)
        sans_espace_de_noms = self.svg.replace(XMLNS, '')
        for interdit in ('http://', 'https://', '@import', 'href', '<image',
                         'url(http'):
            self.assertNotIn(interdit, sans_espace_de_noms)

    def test_la_version_embarquee_ne_porte_aucune_uri(self):
        embarque = svg_embarquable(self.svg)
        self.assertTrue(embarque.startswith('<svg'))
        self.assertNotIn('http://', embarque)
        self.assertNotIn('<?xml', embarque)

    def test_les_bornes_sont_lues_telles_que_servies(self):
        self.assertIn('Irradiance incidente', self.svg)
        self.assertIn('16800,0 kWh', self.svg)
        self.assertIn('Énergie livrée', self.svg)
        self.assertIn('15792,3 kWh', self.svg)

    def test_sans_cascade_refus_nommant_cascade(self):
        for vide in (None, {}, CASCADE['exemple_vide']['cascade']):
            with self.subTest(cascade=vide):
                with self.assertRaises(DiagrammeRefuse) as capture:
                    svg_de_cascade(vide)
                self.assertEqual(capture.exception.champ, 'cascade')

    def test_la_largeur_suit_la_demande(self):
        arbre = racine(svg_de_cascade(cascade(), largeur_mm=100))
        self.assertEqual(arbre.get('width'), '377.95px')

    def test_les_libelles_suivent_la_langue(self):
        self.assertIn('Delivered energy',
                      svg_de_cascade(cascade(), langue='en'))


class DansLaSectionPertesTest(unittest.TestCase):
    def test_la_section_pertes_embarque_le_diagramme(self):
        html = html_de_section({'resultat': {'cascade': cascade()},
                                'langue': 'fr',
                                'section': {'motif_si_absent': 'x'}})
        self.assertIn('<div class="diagramme-pertes"><svg', html)
        self.assertIn('barre-poste', html)
        self.assertNotIn('http://', html)


MIME_SVG_ATTENDU = 'image/svg+xml'


class EndpointDiagrammeEnBaseTest(BaseApiCalepinage):
    """``GET …/diagramme-pertes.svg/`` — câblage, société, refus (CI)."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT, layout_hash='a' * 64,
            resultat=copy.deepcopy(RESULTAT))
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Voisine',
            roof_layout=LAYOUT, resultat=copy.deepcopy(RESULTAT))
        self.sans_resultat = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Vide',
            roof_layout=LAYOUT)

    def _get(self, calepinage, servi=None):
        servi = copy.deepcopy(RESULTAT) if servi is None else servi
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=servi):
            return self.api.get(
                f'{url_detail(calepinage.pk)}diagramme-pertes.svg/')

    def test_le_svg_se_telecharge(self):
        reponse = self._get(self.calepinage)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse['Content-Type'], MIME_SVG_ATTENDU)
        self.assertTrue(reponse['Content-Disposition'].endswith(
            'diagramme-pertes.svg"'))
        self.assertIn('barre-poste', reponse.content.decode('utf-8'))

    def test_sans_resultat_400_nommant_resultat(self):
        reponse = self._get(self.sans_resultat)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('resultat', reponse.data)

    def test_sans_cascade_400_nommant_cascade(self):
        servi = copy.deepcopy(RESULTAT)
        servi['cascade'] = None
        reponse = self._get(self.calepinage, servi=servi)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('cascade', reponse.data)

    def test_une_autre_societe_est_introuvable(self):
        self.assertEqual(self._get(self.etranger).status_code, 404)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
