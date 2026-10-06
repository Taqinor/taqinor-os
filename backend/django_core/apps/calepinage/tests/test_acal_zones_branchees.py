"""ACAL312 (D-ACAL-20) — services/zones.py BRANCHÉ de bout en bout.

Constat C-ACAL-145 / C-ACAL-033 : ``natures_admises``, ``injecter_zones`` et
``chiffrage_zones`` n'avaient aucun appelant de production — une nature libre
(« BIDON ») s'enregistrait, l'atelier n'avait aucune source pour son sélecteur
de nature, la pose publiée ne chiffrait aucune zone et le rapport d'étude ne
disait rien des surfaces retirées.

Ce qui est prouvé ici, sur les VRAIS chemins (porte HTTP, traducteur, moteur
pur, écrivains de simulation, rédacteur de section, WeasyPrint/PyMuPDF) :

* POST ``layout/`` et ``import-layout/`` refusent une nature inconnue au
  chemin ``exclusionZones.2.nature`` avec la liste du NOYAU ; rien n'est
  écrit ; une zone déjà stockée renvoyée inchangée passe (pass-through) ;
* GET ``design-context`` sert ``natures_zones`` (même source, parité contrat) ;
* drapeau ``USE_MOTEUR_CALEPINAGE`` levé, une zone INTERDITE réduit le compte
  serveur de 12 à 8 modules (``traduction`` → ``zones.injecter_zones``) ;
* ``resultat_calepinage`` publie ``pose.zones`` (aire INTERDITE retirée,
  RESERVEE chiffrée à part, PREFEREE à 0 dans le retiré) ;
* la section « Site » du rapport imprime « Surface retirée : X m² (interdite)
  / réservée : Y m² » — jamais un montant — jusque dans le PDF.

Test-du-test : retirer ``injecter_zones`` de ``entree_depuis_layout`` ⇒
``test_zone_interdite_reduit_le_compte_moteur`` rougit (12 au lieu de 8) ;
accepter 'BIDON' ⇒ ``test_nature_inconnue_refusee_nommee`` rougit.

Run :
    python manage.py test apps.calepinage.tests.test_acal_zones_branchees
"""
from __future__ import annotations

import copy
import json
import math
import unittest
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings, tag

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.calepinage.services.traduction import entree_depuis_layout
from apps.calepinage.services.zones import natures_admises
from apps.ventes.services import compte_moteur_du_layout
from authentication.models import Company

from .acal_livrables_helpers import (
    LAYOUT_SIMULABLE, calepinage_simule_reel, exiger_bibliotheques_pdf,
    patch_materiel,
)
from .test_api_liste import BaseApiCalepinage, url_detail

_M_PAR_DEG = math.pi / 180.0 * 6378137.0
_CONTRATS = Path(__file__).resolve().parents[1] / 'contract_samples'
EXEMPLE_V2 = json.loads((_CONTRATS / 'roof_layout_v2.schema.json')
                        .read_text(encoding='utf-8'))['exemple']
CONTRAT_CONTEXTE = json.loads((_CONTRATS / 'calepinage_design_context.json')
                              .read_text(encoding='utf-8'))


def _rectangle(lon0, lat0, largeur_m, hauteur_m, dx_m=0.0):
    """Rectangle ``[lng, lat]`` de ``largeur_m`` (E-O) × ``hauteur_m`` (N-S),
    centré ``dx_m`` mètres à l'est de ``(lon0, lat0)`` — même sphère que
    ``core.calepinage.geo`` (R = 6 378 137 m)."""
    echelle = _M_PAR_DEG * math.cos(math.radians(lat0))
    lon0 = lon0 + dx_m / echelle
    dlon = largeur_m / echelle / 2.0
    dlat = hauteur_m / _M_PAR_DEG / 2.0
    return [[lon0 - dlon, lat0 - dlat], [lon0 + dlon, lat0 - dlat],
            [lon0 + dlon, lat0 + dlat], [lon0 - dlon, lat0 + dlat]]


def _toit_plat(**racine):
    """Toit plat 10 × 8 m plein sud, module 2,384 × 1,303 m (720 Wc) : avec
    un retrait de rive de 0,50 m, le moteur y pose 12 modules."""
    document = {
        'version': 2,
        'pin': {'lat': 33.5, 'lng': -7.6},
        'panelWatt': 720,
        'panelLengthM': 2.384,
        'panelWidthM': 1.303,
        'zones': [{
            'id': 'Z1', 'label': 'Toit principal', 'roofType': 'flat',
            'pitchDeg': 0, 'facingAzimuthDeg': 180, 'obstacles': [],
            'vertices': _rectangle(-7.6, 33.5, 10.0, 8.0),
        }],
    }
    document.update(racine)
    return document


#: Une bande INTERDITE de 3 × 10 m posée sur la moitié est du toit.
ZONE_INTERDITE = {'id': 'zx-1', 'nature': 'INTERDITE',
                  'vertices': _rectangle(-7.6, 33.5, 3.0, 10.0, dx_m=3.5)}


def _trois_zones(nature_3='BIDON'):
    """[INTERDITE, RESERVEE, <nature_3>] — rectangles simples (ACAL76)."""
    lon, lat = -7.6, 33.5
    return [
        {'id': 'zx-1', 'nature': 'INTERDITE',
         'vertices': _rectangle(lon, lat, 2.0, 2.0, dx_m=-3.0)},
        {'id': 'zx-2', 'nature': 'RESERVEE',
         'vertices': _rectangle(lon, lat, 2.0, 2.0, dx_m=0.0)},
        {'id': 'zx-3', 'nature': nature_3,
         'vertices': _rectangle(lon, lat, 2.0, 2.0, dx_m=3.0)},
    ]


class NatureRefuseeApiTest(BaseApiCalepinage):
    """POST layout/ et import-layout/ — porte HTTP réelle, base réelle."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL312')
        self.d0 = _toit_plat()
        enregistrer_layout(self.calepinage, copy.deepcopy(self.d0),
                           user=self.user)
        self.url = f'{url_detail(self.calepinage.pk)}layout/'

    def _lire(self):
        return self.api.get(self.url).data['roof_layout']

    def _poster(self, document):
        # ACAL316 — If-Match obligatoire : le jeton lu juste avant d'écrire.
        jeton = self.api.get(self.url).data['empreinte_document'] or ''
        return self.api.post(self.url, {'roof_layout': document},
                             format='json', HTTP_IF_MATCH=f'"{jeton}"')

    def test_nature_inconnue_refusee_nommee(self):
        document = dict(copy.deepcopy(self.d0), exclusionZones=_trois_zones())
        reponse = self._poster(document)
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('exclusionZones.2.nature', reponse.data)
        message = str(reponse.data['exclusionZones.2.nature'])
        self.assertIn('BIDON', message)
        for nature in natures_admises():
            self.assertIn(nature, message)
        # Refus ⇒ GET layout/ inchangé.
        self.assertEqual(self._lire(), self.d0)

    def test_import_nature_inconnue_refusee_nommee(self):
        document = dict(copy.deepcopy(EXEMPLE_V2),
                        exclusionZones=_trois_zones())
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}import-layout/', document,
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('exclusionZones.2.nature', reponse.data)
        message = str(reponse.data['exclusionZones.2.nature'])
        for nature in natures_admises():
            self.assertIn(nature, message)
        self.assertEqual(self._lire(), self.d0)

    def test_natures_admises_enregistrees_puis_renvoyees_octet_identiques(self):
        document = dict(copy.deepcopy(self.d0),
                        exclusionZones=_trois_zones('PREFEREE'))
        self.assertEqual(self._poster(document).status_code, 200)
        relu = self._lire()
        self.assertEqual(relu['exclusionZones'], document['exclusionZones'])
        # Enregistrer → rouvrir → enregistrer sans toucher : pass-through.
        reponse = self._poster(copy.deepcopy(relu))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(
            json.dumps(self._lire()['exclusionZones'], sort_keys=True),
            json.dumps(document['exclusionZones'], sort_keys=True))

    def test_zone_historique_inchangee_ne_bloque_pas_la_reedition(self):
        ancien = dict(copy.deepcopy(self.d0), exclusionZones=_trois_zones())
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=ancien)
        document = copy.deepcopy(ancien)
        document['panelWatt'] = 710
        reponse = self._poster(document)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._lire(), document)


class DesignContextNaturesTest(BaseApiCalepinage):

    def test_design_context_sert_les_natures(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL312-dc')
        reponse = self.api.get(f'{url_detail(calepinage.pk)}design-context/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['natures_zones'],
                         list(natures_admises()))
        # Parité avec le contrat que l'atelier lit (D02-T03).
        self.assertEqual(reponse.data['natures_zones'],
                         CONTRAT_CONTEXTE['exemple']['natures_zones'])


class ZoneInterditeCompteMoteurTest(TestCase):
    """Compte serveur réel (``compte_moteur_du_layout``), drapeau levé."""

    @classmethod
    def setUpTestData(cls):
        cls.societe = Company.objects.create(nom='ACAL312', slug='acal312')
        enregistrer_parametres(cls.societe, {'degagements': {
            'retrait_rive_m': 0.5, 'source': 'Consigne ACAL312'}})

    @override_settings(USE_MOTEUR_CALEPINAGE=True)
    def test_zone_interdite_reduit_le_compte_moteur(self):
        sans = compte_moteur_du_layout(_toit_plat(), company=self.societe)
        avec = compte_moteur_du_layout(
            _toit_plat(exclusionZones=[copy.deepcopy(ZONE_INTERDITE)]),
            company=self.societe)
        self.assertIsNotNone(sans)
        self.assertIsNotNone(avec)
        self.assertEqual(sans['modules'], 12)
        self.assertEqual(avec['modules'], 8)


class TraductionInjecteLesZonesTest(SimpleTestCase):

    def test_l_entree_moteur_porte_la_zone_du_document(self):
        traduction = entree_depuis_layout(
            _toit_plat(exclusionZones=[copy.deepcopy(ZONE_INTERDITE)]))
        zones = traduction.document['zones']
        self.assertEqual([(z['repere'], z['nature']) for z in zones],
                         [('zx-1', 'INTERDITE')])

    def test_sans_zone_l_entree_est_inchangee(self):
        self.assertEqual(entree_depuis_layout(_toit_plat()).document['zones'],
                         [])


def _layout_avec_zones():
    """La conception simulable des livrables, plus trois zones d'exclusion
    posées à 50 m à l'est de l'épingle (hors pan : seule l'aire compte)."""
    pin = LAYOUT_SIMULABLE['pin']
    lon, lat = pin['lng'], pin['lat']
    return dict(copy.deepcopy(LAYOUT_SIMULABLE), exclusionZones=[
        {'id': 'zx-1', 'nature': 'INTERDITE',
         'vertices': _rectangle(lon, lat, 3.0, 10.0, dx_m=50.0)},
        {'id': 'zx-2', 'nature': 'RESERVEE',
         'vertices': _rectangle(lon, lat, 2.0, 2.0, dx_m=60.0)},
        {'id': 'zx-3', 'nature': 'PREFEREE',
         'vertices': _rectangle(lon, lat, 1.0, 1.0, dx_m=70.0)},
    ])


class PoseZonesTest(unittest.TestCase):
    """Écrivains de simulation RÉELS, résultat SERVI (aucun ORM)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pivot = calepinage_simule_reel(_layout_avec_zones())

    def setUp(self):
        materiel = patch_materiel()
        materiel.start()
        self.addCleanup(materiel.stop)

    def _servi(self):
        from apps.calepinage.services.electrique import resultat_calepinage

        return resultat_calepinage(self.pivot)

    def test_pose_zones_chiffre_les_aires(self):
        zones = self._servi()['pose']['zones']
        par_nature = zones['par_nature']
        self.assertEqual(set(par_nature), set(natures_admises()))
        self.assertEqual(par_nature['INTERDITE']['nombre'], 1)
        self.assertAlmostEqual(par_nature['INTERDITE']['aire_retiree_m2'],
                               30.0, places=1)
        # RESERVEE chiffrée À PART, PREFEREE à zéro dans le retiré.
        self.assertAlmostEqual(par_nature['RESERVEE']['aire_retiree_m2'],
                               4.0, places=1)
        self.assertAlmostEqual(par_nature['PREFEREE']['aire_m2'], 1.0,
                               places=1)
        self.assertEqual(par_nature['PREFEREE']['aire_retiree_m2'], 0.0)
        self.assertAlmostEqual(zones['aire_retiree_m2'], 34.0, places=1)

    def test_pose_zones_recalcule_a_chaque_lecture(self):
        self.assertEqual(self._servi()['pose']['zones'],
                         self._servi()['pose']['zones'])

    def test_rapport_site_imprime_les_surfaces_retirees(self):
        from apps.calepinage.services.rapport.site import html_de_section

        servi = self._servi()
        html = html_de_section({'resultat': servi, 'site': {},
                                'langue': 'fr'})
        self.assertIn('Surface retirée : 30,0 m² (interdite) / réservée : '
                      '4,0 m²', html)

    @tag('pdf')
    def test_rapport_site_imprime_les_surfaces_retirees_dans_le_pdf(self):
        exiger_bibliotheques_pdf()
        import fitz

        from apps.calepinage.services.rapport import rendre_rapport

        octets = rendre_rapport(self.pivot, site={}, identite={}, styles={},
                                etat={})
        document = fitz.open(stream=octets, filetype='pdf')
        try:
            texte = ' '.join(' '.join(page.get_text().split())
                             for page in document)
        finally:
            document.close()
        self.assertIn('Surface retirée : 30,0 m² (interdite)', texte)
        self.assertIn('réservée : 4,0 m²', texte)
