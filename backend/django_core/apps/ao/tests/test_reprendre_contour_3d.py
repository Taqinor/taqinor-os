"""CAL241 — reprendre dans la toiture AO le contour dessiné en 3D.

Ce que ce module VERROUILLE :

  1. **L'aller-retour AO → 3D → AO est STABLE** à la tolérance déclarée : le
     contour repris retombe sur le contour relevé.
  2. **Une affaire déposée/close rend EXACTEMENT le 409 d'avant** — la même
     phrase que ``layout`` et que ``design-context``
     (``selectors.raison_conception_figee``, source unique).
  3. **Seul le contour voyage** : aucune variante 2D RETENUE, aucun obstacle,
     aucune chaîne de cotes, aucune zone n'est modifié.
  4. **Multi-tenant** : une toiture d'une autre société est un 404, et le
     calepinage est lu borné à la société de l'appelant.
  5. **Aucune coordonnée devinée** : sans contour 3D exploitable, c'est un 400
     français, jamais un ``0, 0`` inventé.

Run :
    python manage.py test apps.ao.tests.test_reprendre_contour_3d -v2
"""
from decimal import Decimal

from django.apps import apps as registre
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import selectors, services
from apps.ao.models import (
    AppelOffre, BatimentAO, ChaineCotes, ObstacleAO, ToitureAO,
    VarianteCalepinage, ZoneAO,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

LAT, LNG = Decimal('33.5731245'), Decimal('-7.5898431')
CONTOUR_M = [[0.0, 0.0], [30.0, 0.0], [30.0, 12.0], [18.0, 12.0],
             [18.0, 18.0], [0.0, 18.0]]


def _url(toiture):
    return f'/api/django/ao/toitures/{toiture.pk}/reprendre-contour-3d/'


def _calepinages():
    """Le modèle du module, lu par le REGISTRE — jamais importé."""
    return registre.get_model('calepinage', 'Calepinage').objects


class BaseCal241(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CAL241 Co',
                                              slug='cal241-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='cal241_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-CAL241-1',
            objet='Reprise 3D', lead_id=42)
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            forme=ToitureAO.Forme.POLYGONE, contour_local_m=CONTOUR_M,
            origine_lat=LAT, origine_lng=LNG)

    def _calepinage(self, *, outline=None, company=None, pin=None):
        layout = {'version': 2, 'outline': outline if outline is not None
                  else services.contour_ao_vers_outline_latlng(self.toiture)}
        if pin is not None:
            layout['pin'] = pin
        return _calepinages().create(
            company=company or self.company, lead_id=42,
            appel_offre_id=self.ao.pk, titre='Calepinage AO-CAL241-1',
            roof_layout=layout)


class LAllerRetourEstStable(BaseCal241):
    def test_le_contour_repris_retombe_sur_le_contour_releve(self):
        self._calepinage()

        reponse = self.api.post(_url(self.toiture), {}, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.toiture.refresh_from_db()
        ecart = max(max(abs(a[0] - b[0]), abs(a[1] - b[1]))
                    for a, b in zip(CONTOUR_M, self.toiture.contour_local_m))
        self.assertLessEqual(ecart, services.TOLERANCE_ALLER_RETOUR_M)

    def test_la_surface_est_recalculee_depuis_le_contour_repris(self):
        """``surface_m2`` DÉRIVE du contour : 30×18 − 12×6 = 468 m²."""
        self._calepinage()

        self.api.post(_url(self.toiture), {}, format='json')

        self.toiture.refresh_from_db()
        self.assertAlmostEqual(float(self.toiture.surface_m2), 468.0,
                               places=2)

    def test_l_ancre_deja_posee_sur_la_toiture_est_conservee(self):
        """Le relevé fait foi : la reprise ne déplace pas le repère local."""
        self._calepinage(pin={'lat': 31.0, 'lng': -8.0})

        self.api.post(_url(self.toiture), {}, format='json')

        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.origine_lat, LAT)
        self.assertEqual(self.toiture.origine_lng, LNG)

    def test_une_toiture_sans_ancre_adopte_celle_du_document_3d(self):
        sans_ancre = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='06H',
            forme=ToitureAO.Forme.POLYGONE, contour_local_m=[])
        outline = services.contour_ao_vers_outline_latlng(self.toiture)
        self._calepinage(outline=outline)

        reponse = self.api.post(_url(sans_ancre), {}, format='json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        sans_ancre.refresh_from_db()
        self.assertAlmostEqual(float(sans_ancre.origine_lat), float(LAT),
                               places=6)
        self.assertAlmostEqual(float(sans_ancre.origine_lng), float(LNG),
                               places=6)

    def test_deux_reprises_de_suite_donnent_le_meme_contour(self):
        self._calepinage()

        self.api.post(_url(self.toiture), {}, format='json')
        self.toiture.refresh_from_db()
        premier = list(self.toiture.contour_local_m)
        self.api.post(_url(self.toiture), {}, format='json')
        self.toiture.refresh_from_db()

        self.assertEqual(self.toiture.contour_local_m, premier)


class UneAffaireFigeeRendLeMeme409(BaseCal241):
    def test_le_motif_est_celui_du_selecteur_mot_pour_mot(self):
        self._calepinage()
        self.ao.statut = AppelOffre.Statut.DEPOSE
        self.ao.save(update_fields=['statut'])
        # La phrase est lue à SA source, jamais recopiée dans le test.
        attendu = selectors.raison_conception_figee(self.ao)

        reponse = self.api.post(_url(self.toiture), {}, format='json')

        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['detail'], attendu)

    def test_le_contour_de_la_toiture_n_a_pas_bouge(self):
        self._calepinage(outline=[[34.0, -6.0], [34.001, -6.0],
                                  [34.001, -6.001]])
        self.ao.statut = AppelOffre.Statut.DEPOSE
        self.ao.save(update_fields=['statut'])

        self.api.post(_url(self.toiture), {}, format='json')

        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m, CONTOUR_M)


class SeulLeContourVoyage(BaseCal241):
    def setUp(self):
        super().setUp()
        self.retenue = VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            nom='Variante retenue', est_retenue=True,
            role=VarianteCalepinage.Role.RETENUE,
            statut=VarianteCalepinage.Statut.PUBLIABLE)
        self.obstacle = ObstacleAO.objects.create(
            company=self.company, toiture=self.toiture, repere='D',
            nature=ObstacleAO.Nature.SOUCHE,
            rect_x0_m=Decimal('5.000'), rect_x1_m=Decimal('6.000'),
            rect_y0_m=Decimal('4.000'), rect_y1_m=Decimal('5.000'))
        self.zone = ZoneAO.objects.create(
            company=self.company, toiture=self.toiture, repere='Z1',
            sommets=[[0, 0], [5, 0], [5, 5]])
        self.chaine = ChaineCotes.objects.create(
            company=self.company, toiture=self.toiture, libelle='Façade sud',
            segments=[])
        self._calepinage()

    def test_aucune_variante_2d_retenue_n_est_modifiee(self):
        self.api.post(_url(self.toiture), {}, format='json')

        self.retenue.refresh_from_db()
        self.assertTrue(self.retenue.est_retenue)
        self.assertEqual(self.retenue.statut,
                         VarianteCalepinage.Statut.PUBLIABLE)

    def test_ni_obstacle_ni_zone_ni_chaine_ne_bougent(self):
        self.api.post(_url(self.toiture), {}, format='json')

        self.obstacle.refresh_from_db()
        self.zone.refresh_from_db()
        self.assertEqual(self.obstacle.rect_x0_m, Decimal('5.000'))
        self.assertEqual(self.zone.sommets, [[0, 0], [5, 0], [5, 5]])
        self.assertEqual(
            ChaineCotes.objects.filter(toiture=self.toiture).count(), 1)

    def test_le_calepinage_3d_n_est_pas_reecrit(self):
        """La reprise LIT le module ; elle n'y écrit rien."""
        avant = _calepinages().get(appel_offre_id=self.ao.pk).roof_layout

        self.api.post(_url(self.toiture), {}, format='json')

        apres = _calepinages().get(appel_offre_id=self.ao.pk).roof_layout
        self.assertEqual(apres, avant)


class SansContour3dExploitableCEstUn400Francais(BaseCal241):
    def test_sans_calepinage_du_tout(self):
        reponse = self.api.post(_url(self.toiture), {}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('aucun calepinage 3D', reponse.data['detail'])
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m, CONTOUR_M)

    def test_avec_un_contour_vide(self):
        self._calepinage(outline=[])

        reponse = self.api.post(_url(self.toiture), {}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('outline', reponse.data['detail'])

    def test_avec_moins_de_trois_sommets(self):
        self._calepinage(outline=[[33.57, -7.58], [33.58, -7.58]])

        reponse = self.api.post(_url(self.toiture), {}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)

    def test_un_contour_qui_se_croise_est_refuse_en_nommant_le_champ(self):
        """Le refus d'AOF18 tient : un polygone croisé ne rentre pas."""
        croise = services.contour_ao_vers_outline_latlng(self.toiture)
        croise = [croise[0], croise[2], croise[1], croise[3]]
        self._calepinage(outline=croise)

        reponse = self.api.post(_url(self.toiture), {}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('contour_local_m', reponse.data)
        self.toiture.refresh_from_db()
        self.assertEqual(self.toiture.contour_local_m, CONTOUR_M)


class LeMultiTenantTient(BaseCal241):
    def test_une_toiture_d_une_autre_societe_est_un_404(self):
        autre = Company.objects.create(nom='CAL241 Bis', slug='cal241-bis')
        ao = AppelOffre.objects.create(company=autre, reference='AO-X',
                                       objet='Ailleurs', lead_id=1)
        batiment = BatimentAO.objects.create(company=autre, appel_offre=ao,
                                             code='B')
        etrangere = ToitureAO.objects.create(
            company=autre, batiment=batiment, code_document='09H',
            forme=ToitureAO.Forme.POLYGONE, contour_local_m=CONTOUR_M,
            origine_lat=LAT, origine_lng=LNG)

        reponse = self.api.post(_url(etrangere), {}, format='json')

        self.assertEqual(reponse.status_code, 404)

    def test_un_calepinage_d_une_autre_societe_n_est_pas_lu(self):
        autre = Company.objects.create(nom='CAL241 Ter', slug='cal241-ter')
        self._calepinage(company=autre)

        reponse = self.api.post(_url(self.toiture), {}, format='json')

        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('aucun calepinage 3D', reponse.data['detail'])
