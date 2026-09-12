"""VTA6 — progression terrain, « Ma journée » serveur, et la PORTÉE DURE.

Ce que le test prouve :

* **la portée est SERVEUR, sur TOUTES les routes** — sans ``visites_valider``,
  la liste, le détail et les actions ne servent que ``commercial=self`` (et un
  détail hors portée rend 404, jamais 403 : on ne confirme pas l'existence
  d'un enregistrement qu'on n'a pas le droit de voir). Un valideur voit
  l'équipe ; ``?mine=1`` le restreint encore, il n'élargit personne ;
* **les horodatages viennent du SERVEUR** — le corps de requête ne peut pas
  poser une heure, les deux actions sont IDEMPOTENTES (double tap sur un
  réseau faible) et RÉSERVÉES à l'assigné ;
* **« Ma journée »** sert le jour + les retards, dans l'ordre attendu, avec la
  complétude calculée serveur, et respecte la même portée ;
* ``/visites`` est une route d'accueil mobile PERSISTABLE (NTMOB6) et
  l'accueil par défaut du rôle « Commercial terrain ».

Aucune horloge vive n'est asservie : les dates sont posées RELATIVEMENT au
jour courant du serveur, jamais écrites en dur.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Lead
from apps.roles.models import COMMERCIAL_TERRAIN_PERMISSIONS, Role
from apps.visites.models import VisiteTerrain
from authentication.models import Company

User = get_user_model()

TERRAIN = ['visites_voir', 'visites_creer', 'visites_modifier']
BUREAU = TERRAIN + ['visites_valider']


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VtaBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='VTA6 Solaire', slug='vta6-a')
        # Tenant-distinctness : une SECONDE société RÉELLE, avec ses données.
        cls.autre = Company.objects.create(nom='VTA6 Concurrent',
                                           slug='vta6-b')
        cls.terrain = cls._user(cls.company, 'vta6-terrain', TERRAIN)
        cls.collegue = cls._user(cls.company, 'vta6-collegue', TERRAIN)
        cls.bureau = cls._user(cls.company, 'vta6-bureau', BUREAU)
        cls.etranger = cls._user(cls.autre, 'vta6-etranger', BUREAU)
        cls.lead = Lead.objects.create(
            company=cls.company, nom='Bennani', prenom='Karim',
            ville='Bouskoura', adresse='Lotissement Démo')
        cls.lead_autre = Lead.objects.create(
            company=cls.autre, nom='Client concurrent', ville='Rabat')
        cls.aujourdhui = timezone.localdate()

    @staticmethod
    def _user(company, username, permissions):
        role = Role.objects.create(company=company, nom=f'role-{username}',
                                   permissions=list(permissions))
        return User.objects.create_user(
            username=username, password='x', company=company,
            role_legacy='normal', role=role)

    def _visite(self, commercial, *, date_prevue=None, company=None,
                lead=None, statut=VisiteTerrain.Statut.BROUILLON):
        return VisiteTerrain.objects.create(
            company=company or self.company, lead=lead or self.lead,
            commercial=commercial, date_prevue=date_prevue, statut=statut)


class PorteeDureTests(VtaBase):
    """Sans ``visites_valider`` : ``commercial=self``, partout."""

    def test_la_liste_ne_montre_que_mes_visites(self):
        mienne = self._visite(self.terrain)
        self._visite(self.collegue)
        lignes = auth(self.terrain).get('/api/django/visites/visites/').data
        self.assertEqual([ligne['id'] for ligne in lignes], [mienne.id])

    def test_le_detail_d_un_collegue_rend_404_pas_403(self):
        """404 : on ne confirme pas l'existence de ce qu'on ne peut pas voir."""
        autre = self._visite(self.collegue)
        reponse = auth(self.terrain).get(
            f'/api/django/visites/visites/{autre.id}/')
        self.assertEqual(reponse.status_code, 404, reponse.status_code)

    def test_une_action_sur_la_visite_d_un_collegue_est_hors_portee(self):
        autre = self._visite(self.collegue)
        reponse = auth(self.terrain).post(
            f'/api/django/visites/visites/{autre.id}/demarrer-route/', {},
            format='json')
        self.assertEqual(reponse.status_code, 404, reponse.status_code)

    def test_un_valideur_voit_l_equipe(self):
        mienne = self._visite(self.terrain)
        collegue = self._visite(self.collegue)
        lignes = auth(self.bureau).get('/api/django/visites/visites/').data
        self.assertEqual({ligne['id'] for ligne in lignes},
                         {mienne.id, collegue.id})

    def test_mine_restreint_un_valideur_sans_elargir_personne(self):
        sienne = self._visite(self.bureau)
        self._visite(self.terrain)
        lignes = auth(self.bureau).get(
            '/api/django/visites/visites/?mine=1').data
        self.assertEqual([ligne['id'] for ligne in lignes], [sienne.id])

        # Le même paramètre n'ouvre RIEN à un terrain.
        self._visite(self.collegue)
        lignes = auth(self.terrain).get(
            '/api/django/visites/visites/?mine=1').data
        self.assertTrue(all(ligne['id'] != sienne.id for ligne in lignes))

    def test_la_societe_reste_la_premiere_frontiere(self):
        chez_nous = self._visite(self.terrain)
        self._visite(self.etranger, company=self.autre, lead=self.lead_autre)
        lignes = auth(self.bureau).get('/api/django/visites/visites/').data
        self.assertEqual([ligne['id'] for ligne in lignes], [chez_nous.id])


class ProgressionTerrainTests(VtaBase):
    """Deux jalons, horodatés SERVEUR, idempotents, réservés à l'assigné."""

    def test_demarrer_route_puis_arriver(self):
        visite = self._visite(self.terrain)
        api = auth(self.terrain)

        depart = api.post(
            f'/api/django/visites/visites/{visite.id}/demarrer-route/', {},
            format='json')
        self.assertEqual(depart.status_code, 200, depart.data)
        self.assertIsNotNone(depart.data['en_route_le'])
        self.assertIsNone(depart.data['arrivee_le'])

        arrivee = api.post(
            f'/api/django/visites/visites/{visite.id}/arriver/', {},
            format='json')
        self.assertEqual(arrivee.status_code, 200, arrivee.data)
        self.assertIsNotNone(arrivee.data['arrivee_le'])
        # Un jalon franchi passe la visite « en cours ».
        self.assertEqual(arrivee.data['statut'],
                         VisiteTerrain.Statut.EN_COURS)

    def test_l_heure_du_client_est_ignoree(self):
        """Le corps de requête ne pose JAMAIS un horodatage."""
        visite = self._visite(self.terrain)
        menteur = (timezone.now() - timedelta(days=30)).isoformat()
        reponse = auth(self.terrain).post(
            f'/api/django/visites/visites/{visite.id}/arriver/',
            {'arrivee_le': menteur}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        visite.refresh_from_db()
        self.assertNotEqual(visite.arrivee_le.isoformat(), menteur)
        self.assertGreater(visite.arrivee_le,
                           timezone.now() - timedelta(minutes=5))

    def test_les_deux_actions_sont_idempotentes(self):
        visite = self._visite(self.terrain)
        api = auth(self.terrain)
        for chemin in ('demarrer-route', 'arriver'):
            api.post(f'/api/django/visites/visites/{visite.id}/{chemin}/', {},
                     format='json')
        visite.refresh_from_db()
        depart, arrivee = visite.en_route_le, visite.arrivee_le
        for chemin in ('demarrer-route', 'arriver'):
            api.post(f'/api/django/visites/visites/{visite.id}/{chemin}/', {},
                     format='json')
        visite.refresh_from_db()
        self.assertEqual(visite.en_route_le, depart)
        self.assertEqual(visite.arrivee_le, arrivee)

    def test_un_valideur_ne_pointe_pas_a_la_place_de_l_assigne(self):
        visite = self._visite(self.terrain)
        reponse = auth(self.bureau).post(
            f'/api/django/visites/visites/{visite.id}/arriver/', {},
            format='json')
        self.assertEqual(reponse.status_code, 403, reponse.status_code)
        self.assertIn('commercial', reponse.data['erreurs'])
        visite.refresh_from_db()
        self.assertIsNone(visite.arrivee_le)

    def test_arriver_sans_avoir_pointe_le_depart_est_permis(self):
        """Une donnée perdue pour un bouton oublié serait absurde."""
        visite = self._visite(self.terrain)
        reponse = auth(self.terrain).post(
            f'/api/django/visites/visites/{visite.id}/arriver/', {},
            format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNone(reponse.data['en_route_le'])
        self.assertIsNotNone(reponse.data['arrivee_le'])

    def test_une_visite_validee_est_gelee(self):
        visite = self._visite(self.terrain,
                              statut=VisiteTerrain.Statut.VALIDEE)
        reponse = auth(self.terrain).post(
            f'/api/django/visites/visites/{visite.id}/demarrer-route/', {},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.status_code)
        self.assertIn('statut', reponse.data['erreurs'])


class MaJourneeTests(VtaBase):
    """L'accueil de l'app : le jour + les retards, jamais un dashboard."""

    def test_le_jour_et_les_retards_avec_les_compteurs(self):
        hier = self.aujourdhui - timedelta(days=1)
        demain = self.aujourdhui + timedelta(days=1)
        retard = self._visite(self.terrain, date_prevue=hier)
        aujourdhui = self._visite(self.terrain, date_prevue=self.aujourdhui)
        self._visite(self.terrain, date_prevue=demain)

        reponse = auth(self.terrain).get('/api/django/visites/ma-journee/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['date'], self.aujourdhui.isoformat())
        self.assertEqual(reponse.data['en_retard_count'], 1)
        # Le retard le plus ancien d'abord, puis le jour ; demain est absent.
        self.assertEqual([ligne['id'] for ligne in reponse.data['visites']],
                         [retard.id, aujourdhui.id])

    def test_une_visite_close_n_est_plus_un_retard(self):
        hier = self.aujourdhui - timedelta(days=1)
        self._visite(self.terrain, date_prevue=hier,
                     statut=VisiteTerrain.Statut.TERMINEE)
        reponse = auth(self.terrain).get('/api/django/visites/ma-journee/')
        self.assertEqual(reponse.data['en_retard_count'], 0)
        self.assertEqual(reponse.data['visites'], [])

    def test_une_visite_sans_date_n_est_jamais_en_retard(self):
        self._visite(self.terrain, date_prevue=None)
        reponse = auth(self.terrain).get('/api/django/visites/ma-journee/')
        self.assertEqual(reponse.data['en_retard_count'], 0)
        self.assertEqual(reponse.data['visites'], [])

    def test_la_carte_porte_les_champs_du_contrat(self):
        visite = self._visite(self.terrain, date_prevue=self.aujourdhui)
        carte = auth(self.terrain).get(
            '/api/django/visites/ma-journee/').data['visites'][0]
        self.assertEqual(set(carte), {
            'id', 'lead_nom', 'ville', 'adresse', 'gps_lat', 'gps_lng',
            'date_prevue', 'statut', 'en_route_le', 'arrivee_le', 'complet',
            'manquants_count'})
        self.assertEqual(carte['id'], visite.id)
        self.assertEqual(carte['lead_nom'], 'Karim Bennani')
        self.assertEqual(carte['ville'], 'Bouskoura')
        # La complétude est calculée SERVEUR — le front l'affiche.
        self.assertFalse(carte['complet'])
        self.assertGreater(carte['manquants_count'], 0)

    def test_ma_journee_respecte_la_portee_dure(self):
        mienne = self._visite(self.terrain, date_prevue=self.aujourdhui)
        self._visite(self.collegue, date_prevue=self.aujourdhui)
        reponse = auth(self.terrain).get('/api/django/visites/ma-journee/')
        self.assertEqual([ligne['id'] for ligne in reponse.data['visites']],
                         [mienne.id])

    def test_un_terrain_ne_peut_pas_s_accorder_la_journee_de_l_equipe(self):
        self._visite(self.collegue, date_prevue=self.aujourdhui)
        reponse = auth(self.terrain).get(
            '/api/django/visites/ma-journee/?tous=1')
        self.assertEqual(reponse.data['visites'], [])

    def test_un_valideur_voit_l_equipe_avec_tous(self):
        collegue = self._visite(self.collegue, date_prevue=self.aujourdhui)
        reponse = auth(self.bureau).get(
            '/api/django/visites/ma-journee/?tous=1')
        self.assertEqual([ligne['id'] for ligne in reponse.data['visites']],
                         [collegue.id])

    def test_la_journee_d_une_autre_societe_reste_invisible(self):
        self._visite(self.etranger, date_prevue=self.aujourdhui,
                     company=self.autre, lead=self.lead_autre)
        reponse = auth(self.bureau).get(
            '/api/django/visites/ma-journee/?tous=1')
        self.assertEqual(reponse.data['visites'], [])

    def test_un_anonyme_est_refuse(self):
        reponse = APIClient().get('/api/django/visites/ma-journee/')
        self.assertIn(reponse.status_code, (401, 403))


class AccueilMobileTests(TestCase):
    """NTMOB6 — ``/visites`` est persistable, et c'est l'accueil du terrain."""

    def test_la_route_est_dans_la_whitelist(self):
        from authentication.selectors import MOBILE_HOME_ALLOWED_ROUTES

        self.assertIn('/visites', MOBILE_HOME_ALLOWED_ROUTES)

    def test_accueil_par_defaut_du_commercial_terrain(self):
        from authentication.selectors import default_mobile_home_route

        company = Company.objects.create(nom='VTA6 Mobile', slug='vta6-m')
        role = Role.objects.create(
            company=company, nom='Commercial terrain',
            permissions=list(COMMERCIAL_TERRAIN_PERMISSIONS))
        user = User.objects.create_user(
            username='vta6-mobile', password='x', company=company,
            role_legacy='normal', role=role)
        self.assertEqual(default_mobile_home_route(user), '/visites')

    def test_l_accueil_des_techniciens_est_intouche(self):
        """``/ma-journee`` appartient à ``installations`` — deux métiers."""
        from authentication.selectors import default_mobile_home_route

        company = Company.objects.create(nom='VTA6 Tech', slug='vta6-t')
        role = Role.objects.create(company=company, nom='Technicien',
                                   permissions=[])
        user = User.objects.create_user(
            username='vta6-tech', password='x', company=company,
            role_legacy='normal', role=role)
        self.assertEqual(default_mobile_home_route(user), '/ma-journee')

    def test_la_route_est_reellement_persistable(self):
        company = Company.objects.create(nom='VTA6 Persist', slug='vta6-p')
        role = Role.objects.create(
            company=company, nom='Commercial terrain',
            permissions=list(COMMERCIAL_TERRAIN_PERMISSIONS))
        user = User.objects.create_user(
            username='vta6-persist', password='x', company=company,
            role_legacy='normal', role=role)
        api = auth(user)
        reponse = api.post('/api/django/auth/mobile-home-route/',
                           {'route': '/visites'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        user.refresh_from_db()
        self.assertEqual(user.mobile_home_route, '/visites')
