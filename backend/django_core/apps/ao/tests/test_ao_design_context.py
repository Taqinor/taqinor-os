"""L'atelier 3D de l'AFFAIRE — contexte de conception + persistance du layout.

Les MÊMES outils pour les ventes et pour les appels d'offres : l'écran
``frontend/src/pages/ventes/ToitureDesign.jsx`` (modes « lead » et « devis »)
gagne un mode « ao » et s'ouvre sur une AFFAIRE. Ce qui est prouvé ici :

* la réponse de ``GET /ao/appels-offres/<id>/design-context/`` est CONFORME à
  l'échantillon committé ``contract_samples/ao_design_context.json`` (PACT10) —
  mêmes clés de premier niveau, mêmes sous-blocs, dans les DEUX états du
  serveur (modifiable / lecture seule). C'est le lien qui manquait le
  03/08/2026 : le test d'écran importe ce MÊME fichier ;
* la géométrie est HYDRATÉE depuis le relevé AO existant — le contour local
  métrique (AOF18) est reprojeté en degrés ``[lat, lng]`` à la frontière
  (AOF19), et l'épingle est l'ANCRE de la toiture ;
* le layout se PERSISTE sur l'affaire sans toucher ni son statut, ni sa
  géométrie opposable (toitures / zones) ;
* un dossier déposé refuse l'écriture (409) avec un motif français ;
* une affaire d'une AUTRE société est INTROUVABLE (404), jamais « interdite ».

Run :
    python manage.py test apps.ao.tests.test_ao_design_context -v2
"""
import json
import pathlib
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import selectors
from apps.ao.models import AppelOffre, BatimentAO, ToitureAO, ZoneAO
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'ao_design_context.json').read_text(encoding='utf-8'))

#: Repère local métrique d'une toiture rectangulaire de 30 × 18 m.
CONTOUR = [[0.0, 0.0], [30.0, 0.0], [30.0, 18.0], [0.0, 18.0]]
ANCRE_LAT = Decimal('33.5731000')
ANCRE_LNG = Decimal('-7.5898000')


def url_contexte(pk):
    return f'/api/django/ao/appels-offres/{pk}/design-context/'


def url_layout(pk):
    return f'/api/django/ao/appels-offres/{pk}/layout/'


class BaseAtelier(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Atelier Co',
                                              slug='atelier-co')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='atelier_dir', password='x', company=self.company,
            role=self.role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.affaire = AppelOffre.objects.create(
            company=self.company, reference='AO-3D-1',
            reference_acheteur='AOO 12/2026', objet='Centrale PV en toiture',
            acheteur='Direction régionale', engagement_modules=618)
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.affaire, code='A')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment,
            code_document='05H', designation='Toiture principale',
            contour_local_m=CONTOUR,
            origine_lat=ANCRE_LAT, origine_lng=ANCRE_LNG)
        self.toiture.recalculer_surface()
        self.toiture.save(update_fields=['surface_m2'])

    def _voisin(self):
        """Une DEUXIÈME société, avec son propre utilisateur authentifié."""
        autre = Company.objects.create(nom='Atelier Voisin',
                                       slug='atelier-voisin')
        role = Role.objects.create(company=autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        user = User.objects.create_user(username='atelier_voisin',
                                        password='x', company=autre,
                                        role=role)
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return client


class LeContratEstRespecte(BaseAtelier):
    """PACT10 — le serveur sert EXACTEMENT la forme de l'échantillon."""

    def test_cles_de_premier_niveau_identiques_a_l_echantillon(self):
        reponse = self.api.get(url_contexte(self.affaire.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))

    def test_sous_blocs_identiques_a_l_echantillon(self):
        reponse = self.api.get(url_contexte(self.affaire.pk))
        for bloc in ('affaire', 'geometrie', 'cible', 'carte'):
            self.assertEqual(sorted(reponse.data[bloc]),
                             sorted(CONTRAT['exemple'][bloc]), bloc)

    def test_bloc_toiture_identique_a_l_echantillon(self):
        ZoneAO.objects.create(
            company=self.company, toiture=self.toiture, repere='Z1',
            nature=ZoneAO.Nature.INTERDITE,
            sommets=[[12.0, 4.0], [18.0, 4.0], [18.0, 9.0], [12.0, 9.0]])
        reponse = self.api.get(url_contexte(self.affaire.pk))
        toiture = reponse.data['geometrie']['toiture']
        attendue = CONTRAT['exemple']['geometrie']['toiture']
        self.assertEqual(sorted(toiture), sorted(attendue))
        self.assertEqual(sorted(toiture['zones'][0]),
                         sorted(attendue['zones'][0]))

    def test_etat_lecture_seule_garde_la_meme_forme(self):
        """Un AUTRE état du serveur, jamais une autre FORME."""
        depose = AppelOffre.objects.create(
            company=self.company, reference='AO-3D-2', objet='Déposé',
            statut=AppelOffre.Statut.DEPOSE)
        reponse = self.api.get(url_contexte(depose.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT['exemple_lecture_seule']))
        self.assertFalse(reponse.data['modifiable'])
        # Le motif est SERVI, jamais rédigé côté écran.
        self.assertIn('ne se modifie plus',
                      reponse.data['raison_lecture_seule'])

    def test_toutes_les_cles_sont_toujours_la_meme_sans_toiture(self):
        nue = AppelOffre.objects.create(
            company=self.company, reference='AO-3D-3', objet='Sans relevé')
        reponse = self.api.get(url_contexte(nue.pk))
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        self.assertEqual(reponse.data['geometrie']['source'], 'none')
        self.assertIsNone(reponse.data['geometrie']['toiture'])
        self.assertEqual(reponse.data['geometrie']['outline'], [])
        self.assertTrue(reponse.data['avertissements'])


class LaGeometrieVientDuReleveAO(BaseAtelier):
    def test_epingle_sur_l_ancre_de_la_toiture(self):
        reponse = self.api.get(url_contexte(self.affaire.pk))
        pin = reponse.data['geometrie']['pin']
        self.assertAlmostEqual(pin['lat'], float(ANCRE_LAT), places=6)
        self.assertAlmostEqual(pin['lng'], float(ANCRE_LNG), places=6)

    def test_contour_reprojete_en_degres_lat_lng(self):
        """Le premier sommet local (0, 0) EST l'ancre — ordre [lat, lng]."""
        reponse = self.api.get(url_contexte(self.affaire.pk))
        outline = reponse.data['geometrie']['outline']
        self.assertEqual(len(outline), len(CONTOUR))
        self.assertAlmostEqual(outline[0][0], float(ANCRE_LAT), places=6)
        self.assertAlmostEqual(outline[0][1], float(ANCRE_LNG), places=6)
        # 30 m vers l'est : la longitude augmente, la latitude ne bouge pas.
        self.assertAlmostEqual(outline[1][0], float(ANCRE_LAT), places=6)
        self.assertGreater(outline[1][1], outline[0][1])
        # 18 m vers le nord sur le troisième sommet.
        self.assertGreater(outline[2][0], outline[0][0])
        self.assertEqual(reponse.data['geometrie']['source'], 'toiture')

    def test_sans_ancre_le_contour_n_est_pas_invente(self):
        self.toiture.origine_lat = None
        self.toiture.origine_lng = None
        self.toiture.save(update_fields=['origine_lat', 'origine_lng'])
        reponse = self.api.get(url_contexte(self.affaire.pk))
        self.assertEqual(reponse.data['geometrie']['outline'], [])
        self.assertTrue(any('ancre géographique' in a
                            for a in reponse.data['avertissements']))

    def test_cible_derivee_de_l_engagement_quand_aucune_variante(self):
        reponse = self.api.get(url_contexte(self.affaire.pk))
        cible = reponse.data['cible']
        self.assertEqual(cible['panneaux'], 618)
        # Aucun wattage n'est INVENTÉ tant que la puissance est inconnue.
        self.assertEqual(cible['panel_watt'], 0)
        self.assertEqual(cible['kwc'], 0)


class LaPersistanceDuLayout(BaseAtelier):
    LAYOUT = {'version': 2, 'zones': [{'id': 'z1'}],
              'pin': {'lat': 33.57, 'lng': -7.58}}

    def test_post_range_le_layout_sur_l_affaire(self):
        reponse = self.api.post(url_layout(self.affaire.pk),
                                {'layout': self.LAYOUT}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.affaire.refresh_from_db()
        self.assertEqual(self.affaire.roof_layout, self.LAYOUT)

    def test_le_statut_et_le_releve_opposable_ne_bougent_pas(self):
        avant_statut = self.affaire.statut
        avant_contour = list(self.toiture.contour_local_m)
        self.api.post(url_layout(self.affaire.pk), {'layout': self.LAYOUT},
                      format='json')
        self.affaire.refresh_from_db()
        self.toiture.refresh_from_db()
        self.assertEqual(self.affaire.statut, avant_statut)
        self.assertEqual(self.toiture.contour_local_m, avant_contour)

    def test_get_relit_le_layout(self):
        self.api.post(url_layout(self.affaire.pk), {'layout': self.LAYOUT},
                      format='json')
        reponse = self.api.get(url_layout(self.affaire.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['roof_layout'], self.LAYOUT)

    def test_le_layout_enregistre_prime_dans_le_contexte(self):
        self.api.post(url_layout(self.affaire.pk), {'layout': self.LAYOUT},
                      format='json')
        reponse = self.api.get(url_contexte(self.affaire.pk))
        self.assertEqual(reponse.data['geometrie']['source'], 'affaire')
        self.assertEqual(reponse.data['geometrie']['roof_layout'], self.LAYOUT)

    def test_corps_vide_refuse_en_400(self):
        reponse = self.api.post(url_layout(self.affaire.pk), {}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.affaire.refresh_from_db()
        self.assertIsNone(self.affaire.roof_layout)

    def test_dossier_depose_refuse_en_409_avec_motif(self):
        depose = AppelOffre.objects.create(
            company=self.company, reference='AO-3D-9', objet='Déposé',
            statut=AppelOffre.Statut.DEPOSE)
        reponse = self.api.post(url_layout(depose.pk),
                                {'layout': self.LAYOUT}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('ne se modifie plus', reponse.data['detail'])
        depose.refresh_from_db()
        self.assertIsNone(depose.roof_layout)

    def test_tous_les_statuts_figes_sont_derives_du_modele(self):
        figes = set(selectors.statuts_conception_figee())
        self.assertIn(AppelOffre.Statut.DEPOSE, figes)
        self.assertIn(AppelOffre.Statut.GAGNE, figes)
        self.assertIn(AppelOffre.Statut.PERDU, figes)
        self.assertNotIn(AppelOffre.Statut.ETUDE, figes)


class LeCloisonnementMultiSociete(BaseAtelier):
    def test_contexte_d_une_autre_societe_introuvable(self):
        voisin = self._voisin()
        reponse = voisin.get(url_contexte(self.affaire.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_layout_d_une_autre_societe_introuvable(self):
        voisin = self._voisin()
        reponse = voisin.post(url_layout(self.affaire.pk),
                              {'layout': {'version': 2}}, format='json')
        self.assertEqual(reponse.status_code, 404)
        self.affaire.refresh_from_db()
        self.assertIsNone(self.affaire.roof_layout)

    def test_le_selector_refuse_une_societe_etrangere(self):
        autre = Company.objects.create(nom='Étranger', slug='etranger')
        self.assertIsNone(
            selectors.contexte_conception_affaire(self.affaire, autre))
