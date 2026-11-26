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
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company
from testkit.time import frozen

User = get_user_model()

PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 40

#: L'HORLOGE DE CE MODULE EST FIGÉE et ses dates de référence sont des
#: CONSTANTES — jamais ``timezone.localdate()`` lu à l'IMPORT. Un shard de CI
#: importe ses modules puis les joue plusieurs minutes plus tard : importé à
#: 23 h 57 et joué après minuit, le « DEMAIN » calculé à l'import était devenu
#: « aujourd'hui », et la règle « date future refusée » ne se déclenchait plus
#: (run 44203259355 du 18/11/2026 : 201 au lieu de 409, ``ReleveRefuse`` non
#: levée). ``BaseReleve.setUp`` fige l'horloge sur ``MAINTENANT`` — MIDI UTC,
#: donc le même jour à Casablanca que le Maroc soit à UTC+0 ou à UTC+1.
MAINTENANT = datetime.datetime(2026, 11, 17, 12, 0,
                               tzinfo=datetime.timezone.utc)
AUJOURD_HUI = MAINTENANT.date()
HIER = AUJOURD_HUI - datetime.timedelta(days=1)
DEMAIN = AUJOURD_HUI + datetime.timedelta(days=1)

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
        # Figée AVANT la première écriture et jusqu'au dernier nettoyage :
        # objets, jeton et requêtes lisent tous ``MAINTENANT``, donc ``HIER``
        # est passé et ``DEMAIN`` est futur à n'importe quelle heure du run.
        gel = frozen(MAINTENANT)
        gel.start()
        self.addCleanup(gel.stop)
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

    def test_date_du_releve_obligatoire_400_nomme(self):
        # ENF11 — la date est SAISIE : le schéma la déclare obligatoire
        # (``format: date``), le serveur la refuse sinon (400 nommé).
        reponse = self.api.post(self.url, {}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('releve_le', reponse.data)

    def test_date_future_est_un_conflit_409_detail(self):
        # ENF11 — règle d'horloge : 409 ``{"detail": …}`` ; illisible = 400.
        reponse = self.api.post(
            self.url, {'releve_le': DEMAIN.isoformat(), 'chaines': []},
            format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('futur', reponse.data['detail'])
        reponse = self.api.post(
            self.url, {'releve_le': 'hier matin', 'chaines': []},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(ReleveTerrain.objects.count(), 0)

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

    def test_creation_sur_calepinage_verrouille_409(self):
        """ACON10 — un calepinage au devis ACCEPTÉ refuse la CRÉATION d'un
        relevé (409, motif ventes mot pour mot), comme sa correction."""
        from apps.crm.models import Client
        from apps.ventes.models import Devis

        devis = Devis.objects.create(
            company=self.company, reference='DEV-ACON10-1',
            client=Client.objects.create(company=self.company,
                                         nom='Client ACON10'),
            statut=Devis.Statut.ACCEPTE)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(devis=devis)
        reponse = self.api.post(
            self.url, {'releve_le': HIER.isoformat(),
                       'chaines': [CHAINE_FRDISI]}, format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('Devis accepté : révisez-le',
                      str(reponse.data['releve']))
        self.assertEqual(ReleveTerrain.objects.count(), 0)
        # Brouillon : la création passe (201).
        Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.BROUILLON)
        reponse = self.api.post(
            self.url, {'releve_le': HIER.isoformat(), 'chaines': []},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)

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


class SaisieIllisibleTest(SimpleTestCase):
    """ERR-ENF11-FUZZ-CALEPINAGE - date inexistante, U+0000 : refus NOMMES."""

    def test_date_inexistante_ou_illisible_est_none(self):
        from apps.calepinage.services.releve import _date_saisie

        self.assertEqual(_date_saisie('2026-02-28'), datetime.date(2026, 2, 28))
        for brut in ('2026-02-30', '2026-13-45', 'abc', '', None, 5):
            self.assertIsNone(_date_saisie(brut), repr(brut))

    def test_caractere_nul_dans_les_notes_ou_les_chaines_refuse(self):
        from apps.calepinage.services.releve import _sans_caractere_interdit

        _sans_caractere_interdit('une note', 'notes')
        _sans_caractere_interdit([{'nom': 'ok', 'cotes': [{'valeur': 1.0}]}],
                                 'chaines')
        for valeur, champ in (('a' + chr(0), 'notes'),
                              ([{'nom': 'a' + chr(0)}], 'chaines')):
            with self.assertRaises(ReleveRefuse) as capture:
                _sans_caractere_interdit(valeur, champ)
            self.assertEqual(capture.exception.champ, champ)


class TechnicienReleveTest(BaseReleve):
    """D-ACAL-106 (fondateur, 25/11/2026) — le Technicien ouvre le calepinage
    du lead de SA visite et y fait le relevé (mesures, pente, orientation,
    photos), sans jamais dessiner, ni lire un devis ou un montant."""

    def setUp(self):
        super().setUp()
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, TECHNICIEN_PERMISSIONS,
        )
        from apps.visites.models import VisiteTerrain

        def compte(nom, permissions):
            role = Role.objects.create(company=self.company, nom=f'r-{nom}',
                                       permissions=list(permissions))
            return User.objects.create_user(username=nom, password='x',
                                            company=self.company, role=role)
        self.commercial = compte('m4-commercial', COMMERCIAL_PERMISSIONS)
        self.tech = compte('m4-tech', TECHNICIEN_PERMISSIONS)
        self.lead.owner = self.commercial
        self.lead.save(update_fields=['owner'])
        self.calepinage.roof_layout = {
            'version': 2, 'zones': [{'id': 'zA', 'label': 'Pan A',
                                     'pitchDeg': 10,
                                     'vertices': [[0, 0], [8, 0], [8, 5], [0, 5]]}]}
        self.calepinage.save(update_fields=['roof_layout'])
        self.visite = VisiteTerrain.objects.create(
            company=self.company, lead=self.lead, commercial=self.tech)
        self.base = f'/api/django/calepinage/calepinages/{self.calepinage.pk}/'

    def _section(self, api, corps):
        from apps.calepinage.services.layout import empreinte_document

        self.calepinage.refresh_from_db()
        return api.post(f'{self.base}layout/section/', dict(
            corps, base_empreinte=empreinte_document(self.calepinage.roof_layout)),
            format='json')

    def test_lit_le_calepinage_de_sa_visite_seulement(self):
        api = self._api(self.tech)
        self.assertEqual(api.get(self.base).status_code, 200)
        self.assertEqual(api.get(f'{self.base}releve/').status_code, 200)
        self.visite.commercial = self.commercial
        self.visite.save(update_fields=['commercial'])
        self.assertEqual(api.get(self.base).status_code, 404)

    def test_fait_le_releve_mesures_pente_orientation_photos(self):
        api = self._api(self.tech)
        cree = api.post(f'{self.base}releve/',
                        {'releve_le': HIER.isoformat(), 'chaines': []},
                        format='json')
        self.assertEqual(cree.status_code, 201, cree.data)
        corrige = api.patch(f"{self.base}releve/{cree.data['releve']['id']}/",
                            {'notes': 'Accès par la terrasse'}, format='json')
        self.assertEqual(corrige.status_code, 200, corrige.data)
        pan = self._section(api, {'cle': 'zones', 'zone_id': 'zA', 'champs': {
            'pitchDeg': 22, 'facingAzimuthDeg': 180, 'facingManual': True,
            'facingAzimuthSource': 'saisie'}})
        self.assertEqual(pan.status_code, 200, pan.data)
        photo = api.post(f'{self.base}photos/', {
            'photo': SimpleUploadedFile('toit.png', PNG, content_type='image/png'),
            'prise_le': HIER.isoformat(), 'genre': 'sol'}, format='multipart')
        self.assertEqual(photo.status_code, 201, photo.data)

    def test_ne_dessine_ni_ne_retire_ni_ne_chiffre(self):
        api = self._api(self.tech)
        releve = enregistrer_releve(self.calepinage, {
            'releve_le': HIER.isoformat(), 'chaines': []}, user=self.user)
        self.assertEqual(api.delete(f'{self.base}releve/{releve.pk}/').status_code, 403)
        geometrie = self._section(api, {'cle': 'zones', 'zone_id': 'zA', 'champs': {
            'vertices': [[0, 0], [9, 0], [9, 5], [0, 5]]}})
        self.assertEqual(geometrie.status_code, 403)
        self.assertEqual(self._section(api, {'cle': 'underlay', 'valeur': {}}).status_code, 403)
        self.assertEqual(api.patch(self.base, {'titre': 'x'}, format='json').status_code, 403)
        self.assertEqual(api.post(f'{self.base}generer-devis/', {}, format='json').status_code, 403)
        self.assertEqual(api.get('/api/django/ventes/devis/').status_code, 403)
        self.assertEqual(api.post('/api/django/ventes/devis/', {'lead': self.lead.pk},
                                  format='json').status_code, 403)

    def test_aucun_montant_dans_le_contexte_de_conception(self):
        reponse = self._api(self.tech).get(f'{self.base}design-context/')
        self.assertEqual(reponse.status_code, 200)
        economie = reponse.data['chiffrage']['economie_annee1_mad']
        self.assertIsNone(economie['valeur'])
        self.assertEqual(economie['etat'], 'non_servi')
        self.assertIsNone((reponse.data.get('consommation_lead') or {})
                          .get('facture_mensuelle_mad'))

    def _pairs_sous_un_directeur(self, permissions_tech):
        """Revue lot 5 : T (technicien) et C (commercial) rendent compte au même
        Directeur D ; C possède le lead L et son calepinage K."""
        directeur = User.objects.create_user(
            username='m4-directeur', password='x', company=self.company,
            role=self.role)
        role = Role.objects.create(company=self.company, nom='r-tech-pair',
                                   permissions=list(permissions_tech))
        pair = User.objects.create_user(username='m4-tech-pair', password='x',
                                        company=self.company, role=role,
                                        supervisor=directeur)
        User.objects.filter(pk=self.commercial.pk).update(supervisor=directeur)
        return pair

    def _sans_lecture_hors_visite(self, tech):
        api = self._api(tech)
        self.assertEqual(api.get(self.base).status_code, 404)
        liste = api.get('/api/django/calepinage/calepinages/')
        self.assertEqual(liste.status_code, 200)
        lignes = liste.data.get('results', liste.data)
        self.assertNotIn(self.calepinage.pk, [ligne['id'] for ligne in lignes])
        self.assertIn(api.post(f'{self.base}releve/', {
            'releve_le': HIER.isoformat(), 'chaines': []},
            format='json').status_code, (403, 404))
        self.assertIn(api.post(f'{self.base}photos/', {
            'photo': SimpleUploadedFile('toit.png', PNG, content_type='image/png'),
            'prise_le': HIER.isoformat(), 'genre': 'sol'},
            format='multipart').status_code, (403, 404))
        self.assertIn(self._section(api, {'cle': 'zones', 'zone_id': 'zA', 'champs': {
            'pitchDeg': 22}}).status_code, (403, 404))
        self.assertEqual(ReleveTerrain.objects.count(), 0)

    def test_technicien_pair_du_commercial_sans_visite_ne_lit_rien(self):
        """Revue lot 5 — SCOPE_TEAM ouvrait au Technicien les leads de ses pairs :
        sans visite assignée sur L, K lui est introuvable partout."""
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS

        self._sans_lecture_hors_visite(
            self._pairs_sous_un_directeur(TECHNICIEN_PERMISSIONS))

    def test_technicien_responsable_sans_visite_ne_lit_rien(self):
        from apps.roles.permissions_registre import TECHNICIEN_RESP_PERMISSIONS

        tech_resp = self._pairs_sous_un_directeur(TECHNICIEN_RESP_PERMISSIONS)
        User.objects.filter(pk=self.commercial.pk).update(supervisor=tech_resp)
        self._sans_lecture_hors_visite(tech_resp)

    def _responsable_et_son_technicien(self):
        """D-ACAL-126 — R (Technicien responsable) et T2 (Technicien) sous R."""
        from apps.roles.permissions_registre import (
            TECHNICIEN_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS,
        )

        resp = self._pairs_sous_un_directeur(TECHNICIEN_RESP_PERMISSIONS)
        role = Role.objects.create(company=self.company, nom='r-tech-equipe',
                                   permissions=list(TECHNICIEN_PERMISSIONS))
        tech = User.objects.create_user(username='m4-tech-equipe', password='x',
                                        company=self.company, role=role,
                                        supervisor=resp)
        return resp, tech

    def test_responsable_lit_les_visites_de_son_equipe(self):
        """D-ACAL-126 — une visite assignée à un technicien de SON sous-arbre :
        R lit le calepinage, y fait le relevé, et ``du-lead`` le sert."""
        from apps.visites.models import VisiteTerrain

        resp, tech = self._responsable_et_son_technicien()
        User.objects.filter(pk=self.commercial.pk).update(supervisor=resp)
        VisiteTerrain.objects.create(company=self.company, lead=self.lead,
                                     commercial=tech)
        api = self._api(resp)
        self.assertEqual(api.get(self.base).status_code, 200)
        cree = api.post(f'{self.base}releve/',
                        {'releve_le': HIER.isoformat(), 'chaines': []},
                        format='json')
        self.assertEqual(cree.status_code, 201, cree.data)
        du_lead, _contenance = self._routes_du_lead(api, self.lead.pk)
        self.assertEqual(du_lead.status_code, 200, du_lead.data)

    def test_responsable_ne_lit_pas_la_visite_d_un_technicien_hors_equipe(self):
        """La visite de ``setUp`` est assignée à ``self.tech``, HORS du
        sous-arbre de R : introuvable pour R."""
        resp, _tech = self._responsable_et_son_technicien()
        api = self._api(resp)
        self.assertEqual(api.get(self.base).status_code, 404)
        lignes = api.get('/api/django/calepinage/calepinages/').data
        lignes = lignes.get('results', lignes)
        self.assertNotIn(self.calepinage.pk, [ligne['id'] for ligne in lignes])

    def test_technicien_simple_ne_lit_pas_la_visite_de_son_pair(self):
        """D-ACAL-126 ne vaut que pour le sous-arbre : un Technicien ne lit pas
        la visite assignée à un autre technicien de la même équipe."""
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.visites.models import VisiteTerrain

        resp, tech = self._responsable_et_son_technicien()
        role = Role.objects.create(company=self.company, nom='r-tech-pair-2',
                                   permissions=list(TECHNICIEN_PERMISSIONS))
        pair = User.objects.create_user(username='m4-tech-pair-2', password='x',
                                        company=self.company, role=role,
                                        supervisor=resp)
        VisiteTerrain.objects.create(company=self.company, lead=self.lead,
                                     commercial=tech)
        self.assertEqual(self._api(pair).get(self.base).status_code, 404)
        self.assertEqual(self._api(tech).get(self.base).status_code, 200)

    def test_technicien_pair_avec_sa_visite_lit_et_releve(self):
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.visites.models import VisiteTerrain

        pair = self._pairs_sous_un_directeur(TECHNICIEN_PERMISSIONS)
        VisiteTerrain.objects.create(company=self.company, lead=self.lead,
                                     commercial=pair)
        api = self._api(pair)
        self.assertEqual(api.get(self.base).status_code, 200)
        cree = api.post(f'{self.base}releve/',
                        {'releve_le': HIER.isoformat(), 'chaines': []},
                        format='json')
        self.assertEqual(cree.status_code, 201, cree.data)

    def _routes_du_lead(self, api, lead_id):
        url = '/api/django/calepinage/calepinages/'
        return (api.get(f'{url}du-lead/', {'lead': lead_id}),
                api.get(f'{url}contenance/', {'lead': lead_id,
                                              'origine': 'visite'}))

    def test_du_lead_et_contenance_hors_visite_introuvables(self):
        """Revue lot 5 — ``du-lead`` et ``contenance`` répondent pour le lead
        d'un pair EXACTEMENT ce qu'ils répondent pour un lead hors portée."""
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS

        api = self._api(self._pairs_sous_un_directeur(TECHNICIEN_PERMISSIONS))
        absent = self._routes_du_lead(api, 999999)
        for reponse, temoin in zip(self._routes_du_lead(api, self.lead.pk),
                                   absent):
            self.assertEqual(temoin.status_code, 404, temoin.data)
            self.assertEqual(reponse.status_code, 404, reponse.data)
            self.assertEqual(reponse.data, temoin.data)

    def test_du_lead_et_contenance_de_sa_visite_servis(self):
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.visites.models import VisiteTerrain

        pair = self._pairs_sous_un_directeur(TECHNICIEN_PERMISSIONS)
        VisiteTerrain.objects.create(company=self.company, lead=self.lead,
                                     commercial=pair)
        du_lead, contenance = self._routes_du_lead(self._api(pair), self.lead.pk)
        self.assertEqual(du_lead.status_code, 200, du_lead.data)
        # Servie : jamais « introuvable » (un refus métier 409 reste possible
        # faute de visite validée — c'est le lead qui est atteint).
        self.assertNotEqual(contenance.status_code, 404, contenance.data)

    def test_bibliotheque_des_modeles_bornee_a_ses_visites(self):
        """Revue lot 5 — ``modeles/`` servait au Technicien TOUS les modèles de
        la société (lead, client, géométrie), hors de ses visites."""
        from apps.calepinage.services.modeles import marquer_modele
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.visites.models import VisiteTerrain

        marquer_modele(self.calepinage, user=self.user)
        url = '/api/django/calepinage/calepinages/modeles/'
        pair = self._pairs_sous_un_directeur(TECHNICIEN_PERMISSIONS)

        def ids(user):
            reponse = self._api(user).get(url)
            self.assertEqual(reponse.status_code, 200, reponse.data)
            return [ligne['id'] for ligne in reponse.data]
        self.assertNotIn(self.calepinage.pk, ids(pair))
        self.assertIn(self.calepinage.pk, ids(self.commercial))
        VisiteTerrain.objects.create(company=self.company, lead=self.lead,
                                     commercial=pair)
        self.assertIn(self.calepinage.pk, ids(pair))

    def test_commercial_et_directeur_inchanges(self):
        """La restriction ne touche que le porteur du seul relevé."""
        from apps.calepinage.selectors import lit_par_le_seul_releve

        self._pairs_sous_un_directeur(DIRECTEUR_PERMISSIONS)
        self.assertFalse(lit_par_le_seul_releve(self.commercial))
        self.assertFalse(lit_par_le_seul_releve(self.user))
        self.assertTrue(lit_par_le_seul_releve(self.tech))
        self.assertEqual(self._api(self.commercial).get(self.base).status_code, 200)

    def test_qui_gere_garde_le_releve_sans_le_code_du_releve(self):
        """Le porteur de ``calepinage_gerer`` (Commercial) n'a pas besoin de
        ``calepinage_releve`` : l'alternative n'enlève rien."""
        reponse = self._api(self.commercial).post(
            f'{self.base}releve/', {'releve_le': HIER.isoformat(), 'chaines': []},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
