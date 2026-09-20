"""CAL240 — reprendre dans un calepinage le contour d'une toiture d'AO.

Ce qui est prouvé ici :

* un contour AO importé se RELIT à la tolérance du test (aller-retour repère
  local métrique → degrés → repère local métrique, la seule conversion du
  domaine, CAL31) ;
* SEUL le contour voyage : les pans, obstacles et zones du document sont
  rendus à l'identique, et la toiture AO n'est pas touchée ;
* une toiture AO SANS origine géographique est refusée 400 en NOMMANT le
  champ à renseigner ;
* une affaire déposée rend 409 avec le motif EXACT du serveur AO ;
* une toiture d'une AUTRE société est introuvable (404), jamais « interdite » ;
* le geste est journalisé (CAL26) et une reprise à l'identique ne crée pas de
  seconde version.

Run :
    python manage.py test apps.calepinage.tests.test_import_contour_ao -v2
"""
from apps.ao.models import AppelOffre, BatimentAO, ToitureAO
from apps.calepinage.models import Calepinage

from .test_api_liste import BaseApiCalepinage, url_detail

#: Un rectangle 14 m × 10 m en repère LOCAL MÉTRIQUE (x est, y nord).
CONTOUR = [[0.0, 0.0], [14.0, 0.0], [14.0, 10.0], [0.0, 10.0]]
ANCRE_LAT = 33.5731
ANCRE_LNG = -7.5898

#: Une conception déjà tracée : ce sont SES pans et SES obstacles qui doivent
#: survivre intacts à l'import du contour.
LAYOUT = {
    'version': 2,
    'panelWatt': 720,
    'zones': [{'id': 'z1', 'vertices': [[-7.59, 33.57], [-7.5899, 33.57],
                                        [-7.5899, 33.5701]],
               'obstacles': [{'id': 'obs-1', 'centerLng': -7.59,
                              'centerLat': 33.57, 'lengthM': 1.0,
                              'widthM': 1.0}]}],
    'exclusionZones': [{'id': 'zx-1', 'nature': 'INTERDITE',
                        'vertices': [[-7.59, 33.57], [-7.5899, 33.57],
                                     [-7.5899, 33.5701]]}],
}


def url_import(pk):
    return f'{url_detail(pk)}importer-contour-ao/'


class BaseImportContourAo(BaseApiCalepinage):
    """Une affaire, un bâtiment, une toiture ANCRÉE, et un calepinage."""

    def setUp(self):
        super().setUp()
        self.affaire = AppelOffre.objects.create(
            company=self.company, reference='AO-CAL240-1',
            reference_acheteur='AOO 04/2026', objet='Centrale PV en toiture',
            acheteur='Direction régionale')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.affaire, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment,
            code_document='05H', designation='Toiture principale',
            contour_local_m=CONTOUR,
            origine_lat=ANCRE_LAT, origine_lng=ANCRE_LNG)
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk,
            titre='Atelier Bouskoura', roof_layout=dict(LAYOUT))


class ImportContourAoTest(BaseImportContourAo):

    def test_le_contour_importe_se_relit_a_la_tolerance(self):
        reponse = self.api.post(url_import(self.calepinage.pk),
                                {'toiture': self.toiture.pk}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)

        from apps.ao.services import outline_latlng_vers_contour_ao

        retour = outline_latlng_vers_contour_ao(reponse.data['outline'],
                                                self.toiture)
        for (x, y), (xa, ya) in zip(retour, CONTOUR):
            self.assertAlmostEqual(x, xa, places=2)
            self.assertAlmostEqual(y, ya, places=2)

    def test_l_outline_est_bien_en_lat_lng(self):
        """L'ordre d'axes est le piège que CAL31 ferme : [lat, lng]."""
        reponse = self.api.post(url_import(self.calepinage.pk),
                                {'toiture': self.toiture.pk}, format='json')
        for lat, lng in reponse.data['outline']:
            self.assertAlmostEqual(lat, ANCRE_LAT, places=2)
            self.assertAlmostEqual(lng, ANCRE_LNG, places=2)

    def test_seul_le_contour_voyage(self):
        self.api.post(url_import(self.calepinage.pk),
                      {'toiture': self.toiture.pk}, format='json')
        self.calepinage.refresh_from_db()
        layout = self.calepinage.roof_layout
        self.assertEqual(layout['zones'], LAYOUT['zones'])
        self.assertEqual(layout['exclusionZones'], LAYOUT['exclusionZones'])
        self.assertEqual(layout['panelWatt'], LAYOUT['panelWatt'])
        self.assertEqual(len(layout['outline']), 4)

    def test_la_toiture_ao_n_est_pas_touchee(self):
        self.api.post(url_import(self.calepinage.pk),
                      {'toiture': self.toiture.pk}, format='json')
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m, CONTOUR)

    def test_l_affaire_suffit_a_designer_la_source(self):
        reponse = self.api.post(url_import(self.calepinage.pk),
                                {'appel_offre': self.affaire.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['toiture'], self.toiture.pk)

    def test_une_version_est_deposee_puis_plus_rien_a_l_identique(self):
        premier = self.api.post(url_import(self.calepinage.pk),
                                {'toiture': self.toiture.pk}, format='json')
        self.assertIsNotNone(premier.data['version'])
        second = self.api.post(url_import(self.calepinage.pk),
                               {'toiture': self.toiture.pk}, format='json')
        self.assertTrue(second.data['inchange'])
        self.assertIsNone(second.data['version'])

    def test_le_geste_est_journalise(self):
        from apps.records.models import Activity

        self.api.post(url_import(self.calepinage.pk),
                      {'toiture': self.toiture.pk}, format='json')
        corps = ' '.join(texte for texte
                         in Activity.objects.values_list('body', flat=True)
                         if texte)
        self.assertIn('05H', corps)


class LesRefusDeLImportContourAo(BaseImportContourAo):

    def test_une_toiture_sans_ancre_est_refusee_en_nommant_le_champ(self):
        self.toiture.origine_lat = None
        self.toiture.origine_lng = None
        self.toiture.save(update_fields=['origine_lat', 'origine_lng'])
        reponse = self.api.post(url_import(self.calepinage.pk),
                                {'toiture': self.toiture.pk}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('origine_lat', reponse.data)
        self.assertIn('ancre géographique', reponse.data['detail'])

    def test_une_toiture_sans_contour_est_refusee(self):
        self.toiture.contour_local_m = []
        self.toiture.save(update_fields=['contour_local_m'])
        reponse = self.api.post(url_import(self.calepinage.pk),
                                {'toiture': self.toiture.pk}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('contour_local_m', reponse.data)

    def test_une_affaire_deposee_rend_409_avec_le_motif_du_serveur(self):
        from apps.ao import selectors as selectors_ao

        self.affaire.statut = AppelOffre.Statut.DEPOSE
        self.affaire.save(update_fields=['statut'])
        reponse = self.api.post(url_import(self.calepinage.pk),
                                {'toiture': self.toiture.pk}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['detail'],
                         selectors_ao.raison_conception_figee(self.affaire))

    def test_une_toiture_d_une_autre_societe_est_introuvable(self):
        autre_affaire = AppelOffre.objects.create(
            company=self.autre, reference='AO-CAL240-2',
            reference_acheteur='AOO 05/2026', objet='Voisine',
            acheteur='Voisin')
        autre_batiment = BatimentAO.objects.create(
            company=self.autre, appel_offre=autre_affaire, code='B')
        autre_toiture = ToitureAO.objects.create(
            company=self.autre, batiment=autre_batiment,
            contour_local_m=CONTOUR, origine_lat=ANCRE_LAT,
            origine_lng=ANCRE_LNG)
        reponse = self.api.post(url_import(self.calepinage.pk),
                                {'toiture': autre_toiture.pk}, format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)

    def test_sans_source_le_refus_nomme_le_champ(self):
        reponse = self.api.post(url_import(self.calepinage.pk), {},
                                format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('toiture', reponse.data)

    def test_un_calepinage_d_une_autre_societe_est_introuvable(self):
        reponse = self.api_autre.post(url_import(self.calepinage.pk),
                                      {'toiture': self.toiture.pk},
                                      format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)

    def test_sans_droit_de_gerer_l_import_est_refuse(self):
        reponse = self.api_sans.post(url_import(self.calepinage.pk),
                                     {'toiture': self.toiture.pk},
                                     format='json')
        self.assertEqual(reponse.status_code, 403, reponse.data)
