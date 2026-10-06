"""ACAL207 (C-ACAL-025, D-ACAL-28) — « Appliquer la cote au pan ».

Ce qui est prouvé ici :

* le côté choisi d'un pan dessiné à 11,90 m est recalé sur la cote mesurée
  de 12,40 m (± 1 cm) par homothétie LE LONG de ce côté ;
* la composante perpendiculaire est inchangée (le côté voisin garde sa
  longueur) et l'azimut du pan n'est pas touché ;
* la précision déclarée du relevé est CONSERVÉE dans ``cotesReleve`` et une
  version « Cote du relevé appliquée — côté 0 » est déposée ;
* une cote A_CONFIRMER (déduite par fermeture) est refusée, 400 nommé ;
* un pan croisé est refusé, 400 nommé ;
* un relevé ou un calepinage d'une autre société est introuvable (404).

Run :
    python manage.py test apps.calepinage.tests.test_acal_releve_cote_pan -v2
"""
import math

from apps.calepinage.models import Calepinage, CalepinageVersion
from core.calepinage.geo import deprojeteur_local, projeteur_local

from .test_api_liste import BaseApiCalepinage, url_detail

PIN = {'lat': 33.5731, 'lng': -7.5898}
ORIGINE = (PIN['lng'], PIN['lat'])

#: Un pan rectangulaire en mètres autour de l'épingle : côté 0 (sud, ouest →
#: est) = 11,90 m, côté 1 (est, sud → nord) = 8,00 m.
RECTANGLE_M = [(-5.0, -4.0), (6.9, -4.0), (6.9, 4.0), (-5.0, 4.0)]


def _en_lng_lat(points_m):
    deprojeter = deprojeteur_local(ORIGINE)
    return [list(deprojeter(p)) for p in points_m]


def _en_metres(sommets):
    projeter = projeteur_local(ORIGINE)
    return [projeter(s) for s in sommets]


def _longueur(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


#: Chaînes saisies : « Égout sud » mesurée (12,40 m, tolérance DÉCLARÉE
#: 0,05 m) ; « Pignon » à qui manque une cote (d DÉDUITE = 5,00 m, à
#: confirmer).
CHAINES = [
    {'nom': 'Égout sud', 'total_mesure': 12.4, 'tolerance_m': 0.05,
     'cotes': [{'nom': 'a', 'valeur': 5.2}, {'nom': 'b', 'valeur': 7.2}]},
    {'nom': 'Pignon', 'total_mesure': 9.0,
     'cotes': [{'nom': 'c', 'valeur': 4.0}, {'nom': 'd', 'valeur': None}]},
]


class AppliquerCotePanTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.layout = {
            'version': 2, 'pin': dict(PIN),
            'zones': [{'id': 'z1', 'vertices': _en_lng_lat(RECTANGLE_M),
                       'facingAzimuthDeg': 180, 'pitchDeg': 20}],
        }
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Relevé 207',
            roof_layout=self.layout)
        reponse = self.api.post(
            f'{url_detail(self.calepinage.pk)}releve/',
            {'releve_le': '2026-10-05', 'chaines': CHAINES}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.releve_id = reponse.data['releve']['id']

    def _appliquer(self, corps, calepinage=None, releve_id=None, api=None):
        calepinage = calepinage or self.calepinage
        return (api or self.api).post(
            f'{url_detail(calepinage.pk)}releve/'
            f'{releve_id or self.releve_id}/appliquer-cote/',
            corps, format='json')

    def _sommets_relus(self):
        reponse = self.api.get(f'{url_detail(self.calepinage.pk)}layout/')
        self.assertEqual(reponse.status_code, 200)
        return reponse.data['roof_layout']

    def test_cote_recale_le_cote_choisi_par_homothetie(self):
        avant = _en_metres(self.layout['zones'][0]['vertices'])
        self.assertAlmostEqual(_longueur(avant[0], avant[1]), 11.90, places=6)
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 12.4})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIn('roof_layout', reponse.data)
        self.assertIsNotNone(reponse.data['version'])

        apres = _en_metres(self._sommets_relus()['zones'][0]['vertices'])
        self.assertAlmostEqual(_longueur(apres[0], apres[1]), 12.40,
                               delta=0.01)
        # Ancré au sommet 0 : il ne bouge pas.
        self.assertAlmostEqual(apres[0][0], avant[0][0], places=6)
        self.assertAlmostEqual(apres[0][1], avant[0][1], places=6)

    def test_perpendiculaire_inchangee_et_azimut_intact(self):
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 12.4})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        zone = self._sommets_relus()['zones'][0]
        apres = _en_metres(zone['vertices'])
        # Le côté 1 (perpendiculaire au côté 0) garde ses 8,00 m : une
        # homothétie UNIFORME l'aurait porté à 8 × 12,4 / 11,9.
        self.assertAlmostEqual(_longueur(apres[1], apres[2]), 8.0, delta=0.01)
        for (_x, y_apres), (_x0, y_avant) in zip(apres, RECTANGLE_M):
            self.assertAlmostEqual(y_apres, y_avant, delta=0.001)
        self.assertEqual(zone['facingAzimuthDeg'], 180)
        self.assertEqual(zone['pitchDeg'], 20)

    def test_precision_conservee_et_version_creee(self):
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 12.4})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        cotes = self._sommets_relus()['zones'][0]['cotesReleve']
        self.assertEqual(len(cotes), 1)
        self.assertEqual(cotes[0]['cote'], 0)
        self.assertEqual(cotes[0]['longueurM'], 12.4)
        self.assertEqual(cotes[0]['precisionM'], 0.05)
        self.assertEqual(cotes[0]['releveId'], self.releve_id)
        self.assertTrue(cotes[0]['appliqueLe'])
        versions = CalepinageVersion.objects.filter(
            calepinage=self.calepinage)
        self.assertEqual(versions.count(), avant + 1)
        self.assertEqual(versions.order_by('-pk').first().libelle,
                         'Cote du relevé appliquée — côté 0')
        # Enregistrer sans toucher : inchangé, aucune version de plus.
        document = self._sommets_relus()
        url = f'{url_detail(self.calepinage.pk)}layout/'
        # ACAL316 — If-Match obligatoire : le jeton lu juste avant d'écrire.
        jeton = self.api.get(url).data['empreinte_document']
        reponse = self.api.post(url, document, format='json',
                                HTTP_IF_MATCH=f'"{jeton}"')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['inchange'])
        self.assertEqual(versions.count(), avant + 1)

    def test_cote_a_confirmer_refusee(self):
        # « d » = 9,00 − 4,00 = 5,00 m, DÉDUITE par fermeture.
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 1, 'longueur_m': 5.0})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('cote_index', reponse.data)
        self.assertIn('A_CONFIRMER', reponse.data['cote_index'])
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.roof_layout, self.layout)

    def test_longueur_absente_du_releve_refusee(self):
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 13.7})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('longueur_m', reponse.data)

    def test_pan_croise_refuse(self):
        croise = dict(self.layout, zones=[{
            'id': 'z1', 'vertices': _en_lng_lat(
                [(-5.0, -4.0), (6.9, 4.0), (6.9, -4.0), (-5.0, 4.0)])}])
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_layout=croise)
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 12.4})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('zone_id', reponse.data)
        self.assertIn('croisé', reponse.data['zone_id'])

    def test_autre_societe_introuvable(self):
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 12.4},
            api=self.api_autre)
        self.assertEqual(reponse.status_code, 404)
        etranger = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Autre',
            roof_layout=dict(self.layout))
        # Le relevé d'un AUTRE calepinage n'est pas applicable ici.
        reponse = self._appliquer(
            {'zone_id': 'z1', 'cote_index': 0, 'longueur_m': 12.4},
            calepinage=etranger)
        self.assertEqual(reponse.status_code, 404)
