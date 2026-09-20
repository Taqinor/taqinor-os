"""CAL64 — le relevé terrain mobile : photos, cotes, boussole. Rien d'inventé.

CE QUI EST PROUVÉ ICI
---------------------
* **LA GARANTIE CENTRALE** — un relevé à qui il manque UNE cote rend une
  géométrie dont la cote déduite est marquée « à confirmer », deux fois : sur
  la cote (``a_confirmer``) et dans ``cotes_a_confirmer``. AUCUNE cote n'est
  inventée en silence ;
* le solveur est celui du NOYAU (``core.calepinage.solveur_cotes``) : le cas
  de référence du relevé FRDISI (51,10 − 19,36 − 7,92 − 4,50 − 10,50 = 8,82)
  est retrouvé au millimètre ;
* une chaîne dont la fermeture n'est pas tenue REMONTE (``ok: false`` + motif
  + résidu) au lieu de faire tomber le calcul ;
* deux cotes manquantes ⇒ refus, en nommant la chaîne (deux inconnues, une
  seule équation) ;
* **un azimut sans précision déclarée est REFUSÉ** en nommant
  ``precision_azimut_deg`` : une boussole de téléphone se trompe de plusieurs
  degrés, et le libellé rendu porte toujours le « ± » ;
* la date du relevé est SAISIE (absente, illisible ou future ⇒ refus nommé) ;
* les photos rattachées sont celles de CAL52 (un seul magasin), et une photo
  d'un AUTRE calepinage n'est jamais rattachée ;
* le relevé n'écrit PAS le ``roof_layout`` et ne bouge aucun statut.

Run :
    python manage.py test apps.calepinage.tests.test_releve_terrain -v2
"""
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage, PhotoSite, ReleveTerrain
from apps.calepinage.selectors import releves_terrain
from apps.calepinage.services.photos import ajouter_photo_site
from apps.calepinage.services.releve import (
    ReleveRefuse,
    enregistrer_releve,
    resoudre_chaines,
)
from apps.crm.models import Lead
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40
HIER = datetime.date.today() - datetime.timedelta(days=1)
DEMAIN = datetime.date.today() + datetime.timedelta(days=1)

#: Le cas de référence du relevé FRDISI : la profondeur de cage est la seule
#: cote MANQUANTE, déduite par fermeture (8,82 quand le client annonçait 8,5).
CHAINE_FRDISI = {
    'nom': 'façade',
    'tolerance_m': 0.05,
    'total_mesure': 51.10,
    'cotes': [
        {'nom': 'A', 'valeur': 19.36},
        {'nom': 'B', 'valeur': 7.92},
        {'nom': 'C', 'valeur': 4.50},
        {'nom': 'cage'},                 # MANQUANTE — à déduire
        {'nom': 'D', 'valeur': 10.50},
    ],
}

CHAINE_FERMEE = {
    'nom': 'pignon',
    'tolerance_m': 0.05,
    'total_mesure': 12.00,
    'cotes': [{'nom': 'a', 'valeur': 5.00}, {'nom': 'b', 'valeur': 7.00}],
}


class SolveurTest(SimpleTestCase):
    """La résolution : le noyau, et rien que le noyau."""

    def test_cote_manquante_deduite_et_a_confirmer(self):
        geometrie = resoudre_chaines([CHAINE_FRDISI])
        chaine = geometrie['chaines'][0]
        cage = [c for c in chaine['cotes'] if c['nom'] == 'cage'][0]
        self.assertAlmostEqual(cage['valeur'], 8.82, places=3)
        self.assertTrue(cage['a_confirmer'])
        self.assertEqual(cage['statut'], 'A_CONFIRMER')
        self.assertEqual(geometrie['cotes_a_confirmer'], ['façade / cage'])
        self.assertIn('DÉDUITE', chaine['motif'])

    def test_les_cotes_mesurees_ne_sont_pas_a_confirmer(self):
        chaine = resoudre_chaines([CHAINE_FRDISI])['chaines'][0]
        mesurees = [c for c in chaine['cotes'] if c['nom'] != 'cage']
        self.assertTrue(all(not c['a_confirmer'] for c in mesurees))
        self.assertTrue(all(c['statut'] == 'MESUREE' for c in mesurees))

    def test_chaine_fermee_n_a_rien_a_confirmer(self):
        geometrie = resoudre_chaines([CHAINE_FERMEE])
        self.assertTrue(geometrie['chaines'][0]['ok'])
        self.assertEqual(geometrie['cotes_a_confirmer'], [])
        self.assertTrue(geometrie['toutes_fermees'])

    def test_fermeture_non_tenue_remonte_sans_exception(self):
        chaine = dict(CHAINE_FERMEE, total_mesure=13.00)
        geometrie = resoudre_chaines([chaine])
        resolue = geometrie['chaines'][0]
        self.assertFalse(resolue['ok'])
        self.assertFalse(geometrie['toutes_fermees'])
        self.assertIn('fermeture', resolue['motif'])
        self.assertAlmostEqual(resolue['residu_m'], -1.0, places=3)

    def test_sans_chaine_geometrie_vide(self):
        geometrie = resoudre_chaines([])
        self.assertEqual(geometrie['chaines'], [])
        self.assertEqual(geometrie['cotes_a_confirmer'], [])
        self.assertTrue(geometrie['toutes_fermees'])

    def test_deux_cotes_manquantes_refusees(self):
        chaine = dict(CHAINE_FRDISI,
                      cotes=[{'nom': 'a'}, {'nom': 'b'},
                             {'nom': 'c', 'valeur': 3.0}])
        with self.assertRaises(ReleveRefuse) as capture:
            resoudre_chaines([chaine])
        self.assertEqual(capture.exception.champ, 'chaines[0]')

    def test_chaine_sans_cote_refusee(self):
        with self.assertRaises(ReleveRefuse) as capture:
            resoudre_chaines([{'nom': 'vide', 'cotes': []}])
        self.assertEqual(capture.exception.champ, 'chaines[0]')

    def test_cote_non_numerique_refusee(self):
        chaine = {'nom': 'x', 'cotes': [{'nom': 'a', 'valeur': 'cinq'}]}
        with self.assertRaises(ReleveRefuse) as capture:
            resoudre_chaines([chaine])
        self.assertEqual(capture.exception.champ, 'chaines[0]')

    def test_chaines_non_liste_refusees(self):
        with self.assertRaises(ReleveRefuse) as capture:
            resoudre_chaines({'nom': 'x'})
        self.assertEqual(capture.exception.champ, 'chaines')


class BaseReleve(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Relevé Co',
                                              slug='releve-co-64')
        self.autre = Company.objects.create(nom='Voisine Relevé',
                                            slug='voisine-releve-64')
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='cal64', password='x', company=self.company,
            role=self.role)
        self.lead = Lead.objects.create(company=self.company, nom='Toit Anfa')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit Anfa')
        self.autre_calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Autre toit')

        mock.patch('apps.ventes.services.stocker_image_toiture').start()
        mock.patch('apps.ventes.services.url_image_toiture',
                   return_value='https://minio/presigne').start()
        self.addCleanup(mock.patch.stopall)

    def _photo(self, calepinage=None):
        return ajouter_photo_site(
            calepinage or self.calepinage,
            SimpleUploadedFile('vol.png', PNG, content_type='image/png'),
            prise_le=HIER, user=self.user)

    def _api(self, user=None):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(user or self.user)}'))
        return api


class EnregistrementTest(BaseReleve):
    """Le chemin d'écriture : saisie brute gardée, géométrie résolue."""

    def _releve(self, **surcharges):
        donnees = {'releve_le': HIER.isoformat(),
                   'chaines': [CHAINE_FRDISI]}
        donnees.update(surcharges)
        return enregistrer_releve(self.calepinage, donnees, user=self.user)

    def test_saisie_brute_conservee(self):
        releve = self._releve()
        self.assertEqual(releve.chaines, [CHAINE_FRDISI])

    def test_geometrie_resolue_enregistree(self):
        releve = self._releve()
        self.assertEqual(releve.geometrie['cotes_a_confirmer'],
                         ['façade / cage'])

    def test_societe_et_auteur_du_serveur(self):
        releve = self._releve()
        self.assertEqual(releve.company, self.company)
        self.assertEqual(releve.releve_par, self.user)

    def test_aucun_statut_ni_layout_touche(self):
        self._releve()
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.statut, Calepinage.Statut.BROUILLON)
        self.assertIsNone(self.calepinage.roof_layout)

    def test_azimut_avec_precision_accepte(self):
        releve = self._releve(azimut_boussole_deg=172.5,
                              precision_azimut_deg=5)
        self.assertEqual(releve.azimut_boussole_deg, 172.5)
        self.assertEqual(releve.precision_azimut_deg, 5.0)

    def test_photos_rattachees_au_releve(self):
        photo = self._photo()
        releve = self._releve(photo_ids=[photo.pk])
        photo.refresh_from_db()
        self.assertEqual(photo.releve, releve)

    def test_photo_d_un_autre_calepinage_jamais_rattachee(self):
        etrangere = self._photo(self.autre_calepinage)
        self._releve(photo_ids=[etrangere.pk])
        etrangere.refresh_from_db()
        self.assertIsNone(etrangere.releve)

    def test_une_photo_seule_reste_de_premiere_classe(self):
        photo = self._photo()
        self.assertIsNone(photo.releve)
        self.assertEqual(PhotoSite.objects.filter(releve=None).count(), 1)


class RefusTest(BaseReleve):
    """Chaque refus nomme SON champ, en français."""

    def _refus(self, champ, **surcharges):
        donnees = {'releve_le': HIER.isoformat(), 'chaines': []}
        donnees.update(surcharges)
        with self.assertRaises(ReleveRefuse) as capture:
            enregistrer_releve(self.calepinage, donnees, user=self.user)
        self.assertEqual(capture.exception.champ, champ,
                         str(capture.exception))
        return capture.exception

    def test_date_manquante_refusee(self):
        erreur = self._refus('releve_le', releve_le=None)
        self.assertIn('SAISIE', str(erreur))

    def test_date_illisible_refusee(self):
        self._refus('releve_le', releve_le='hier matin')

    def test_date_future_refusee(self):
        self._refus('releve_le', releve_le=DEMAIN.isoformat())

    def test_azimut_sans_precision_refuse(self):
        erreur = self._refus('precision_azimut_deg',
                             azimut_boussole_deg=172.5)
        self.assertIn('précision déclarée', str(erreur))

    def test_azimut_hors_bornes_refuse(self):
        self._refus('azimut_boussole_deg', azimut_boussole_deg=400.0,
                    precision_azimut_deg=5)

    def test_precision_negative_refusee(self):
        self._refus('precision_azimut_deg', azimut_boussole_deg=10.0,
                    precision_azimut_deg=-2)

    def test_un_refus_n_ecrit_rien(self):
        with self.assertRaises(ReleveRefuse):
            enregistrer_releve(self.calepinage,
                               {'releve_le': HIER.isoformat(),
                                'azimut_boussole_deg': 172.5}, user=self.user)
        self.assertEqual(ReleveTerrain.objects.count(), 0)


class LectureTest(BaseReleve):
    """La relecture : toutes les clés, l'azimut toujours avec son « ± »."""

    def test_liste_vide(self):
        self.assertEqual(releves_terrain(self.calepinage), [])

    def test_clefs_toujours_presentes(self):
        enregistrer_releve(self.calepinage,
                           {'releve_le': HIER.isoformat(),
                            'chaines': [CHAINE_FRDISI],
                            'azimut_boussole_deg': 172.5,
                            'precision_azimut_deg': 5,
                            'notes': 'vent fort'}, user=self.user)
        ligne = releves_terrain(self.calepinage)[0]
        self.assertEqual(sorted(ligne), sorted([
            'id', 'releve_le', 'notes', 'chaines', 'geometrie', 'azimut',
            'cotes_a_confirmer', 'photos', 'releve_par', 'created_at']))
        self.assertEqual(ligne['cotes_a_confirmer'], ['façade / cage'])
        self.assertEqual(ligne['notes'], 'vent fort')

    def test_azimut_porte_sa_precision(self):
        enregistrer_releve(self.calepinage,
                           {'releve_le': HIER.isoformat(), 'chaines': [],
                            'azimut_boussole_deg': 172.5,
                            'precision_azimut_deg': 5}, user=self.user)
        azimut = releves_terrain(self.calepinage)[0]['azimut']
        self.assertEqual(azimut['precision_deg'], 5.0)
        self.assertIn('±', azimut['libelle'])
        self.assertIn('boussole', azimut['libelle'])

    def test_sans_azimut_la_cle_vaut_null(self):
        enregistrer_releve(self.calepinage,
                           {'releve_le': HIER.isoformat(), 'chaines': []},
                           user=self.user)
        self.assertIsNone(releves_terrain(self.calepinage)[0]['azimut'])


class EndpointTest(BaseReleve):
    """``calepinages/<pk>/releve/`` — l'objet d'abord, puis la saisie."""

    def setUp(self):
        super().setUp()
        self.url = ('/api/django/calepinage/calepinages/'
                    f'{self.calepinage.pk}/releve/')
        self.api = self._api()

    def test_post_enregistre_et_marque_a_confirmer(self):
        reponse = self.api.post(
            self.url,
            {'releve_le': HIER.isoformat(), 'chaines': [CHAINE_FRDISI]},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(reponse.data['releve']['cotes_a_confirmer'],
                         ['façade / cage'])
        self.assertEqual(len(reponse.data['releves']), 1)

    def test_get_liste_les_releves(self):
        enregistrer_releve(self.calepinage,
                           {'releve_le': HIER.isoformat(), 'chaines': []},
                           user=self.user)
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data['releves']), 1)

    def test_azimut_sans_precision_refuse_en_nommant_le_champ(self):
        reponse = self.api.post(
            self.url,
            {'releve_le': HIER.isoformat(), 'chaines': [],
             'azimut_boussole_deg': 172.5},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('precision_azimut_deg', reponse.data)
        self.assertEqual(ReleveTerrain.objects.count(), 0)

    def test_calepinage_d_une_autre_societe_introuvable(self):
        role = Role.objects.create(company=self.autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        voisin = User.objects.create_user(username='cal64_voisin',
                                          password='x', company=self.autre,
                                          role=role)
        reponse = self._api(voisin).post(
            self.url, {'releve_le': HIER.isoformat(), 'chaines': []},
            format='json')
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(ReleveTerrain.objects.count(), 0)
