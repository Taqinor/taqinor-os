"""XPLT21 — Softphone VoIP intégré (SIP/WebRTC, gated).

Couvre :
  - sans configuration (`VoipParametres` par défaut, `actif=False`) → AUCUN
    appel possible (409), rien ne change (comportement FG208 inchangé) ;
  - configuré (fournisseur `sip_generique` factice, `actif=True`) → un appel
    sortant se journalise, se clôture avec durée/issue et écrit une entrée de
    chatter `records.Activity` sur la fiche résolue ;
  - un appel entrant résout le numéro vers le lead/client correspondant
    (« call-pop ») ;
  - cross-tenant : un appel d'une autre société est invisible/inaccessible ;
  - identifiants VoIP strictement personnels (jamais ceux d'un collègue) ;
  - configuration réservée responsable/admin.

Run :
    docker compose exec django_core python manage.py test apps.voip -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.records.models import Activity
from apps.voip.models import Appel, VoipIdentifiantUtilisateur, VoipParametres
from authentication.models import Company

User = get_user_model()


def _company(slug='voip-co', nom='VoIP Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def _user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='pw', role_legacy=role, company=company)


def _api_for(user):
    api = APIClient()
    token = str(AccessToken.for_user(user))
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return api


class VoipSansConfigurationTest(TestCase):
    """Sans configuration : le softphone reste inerte (comportement
    historique préservé — sans config rien ne change)."""

    def setUp(self):
        self.company = _company()
        self.user = _user(self.company, 'voip_admin', role='admin')
        self.api = _api_for(self.user)

    def test_appel_sortant_refuse_sans_configuration(self):
        resp = self.api.post(
            '/api/django/voip/appels/sortant/', {'numero': '0612345678'})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(Appel.objects.count(), 0)

    def test_appel_entrant_refuse_sans_configuration(self):
        resp = self.api.post(
            '/api/django/voip/appels/entrant/', {'numero': '0612345678'})
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(Appel.objects.count(), 0)

    def test_parametres_get_montre_inactif_par_defaut(self):
        resp = self.api.get('/api/django/voip/parametres/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['actif'])
        self.assertFalse(resp.data['est_configure'])
        self.assertEqual(resp.data['fournisseur'], 'noop')


class VoipConfigureTest(TestCase):
    """Configuré (fournisseur SIP générique factice) : le softphone
    fonctionne — appel sortant journalisé + clôturé, appel entrant résolu."""

    def setUp(self):
        self.company = _company(slug='voip-co-2', nom='VoIP Co 2')
        self.admin = _user(self.company, 'voip_admin2', role='admin')
        self.commercial = _user(self.company, 'voip_commercial', role='normal')
        VoipParametres.objects.create(
            company=self.company, fournisseur='sip_generique', actif=True,
            serveur_sip='sip.example.test')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            telephone='+212612345678')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='+212698765432')
        self.api = _api_for(self.admin)

    def test_appel_sortant_configure_se_journalise(self):
        resp = self.api.post(
            '/api/django/voip/appels/sortant/', {'numero': '0612345678'})
        self.assertEqual(resp.status_code, 201)
        appel = Appel.objects.get(id=resp.data['id'])
        self.assertEqual(appel.direction, Appel.Direction.SORTANT)
        self.assertEqual(appel.company_id, self.company.id)
        self.assertEqual(resp.data['cible'], {'type': 'client', 'id': self.client_obj.id})

    def test_appel_sortant_numero_sans_correspondance_reste_journalise(self):
        resp = self.api.post(
            '/api/django/voip/appels/sortant/', {'numero': '0699999999'})
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.data['cible'])

    def test_terminer_appel_pose_duree_issue_et_journalise_chatter(self):
        appel = self.api.post(
            '/api/django/voip/appels/sortant/', {'numero': '0612345678'}).data
        resp = self.api.post(
            f"/api/django/voip/appels/{appel['id']}/terminer/",
            {'duree_secondes': 192, 'issue': 'répondu'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['duree_secondes'], 192)
        self.assertEqual(resp.data['issue'], 'répondu')
        self.assertEqual(resp.data['statut'], 'termine')

        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Client)
        activites = Activity.objects.filter(
            company=self.company, content_type=ct, object_id=self.client_obj.id)
        self.assertEqual(activites.count(), 1)
        activite = activites.first()
        self.assertIn('3 min 12 s', activite.summary)
        self.assertIn('répondu', activite.note)
        self.assertTrue(activite.done)

    def test_appel_entrant_resout_lead_ouvre_bonne_fiche(self):
        resp = self.api.post(
            '/api/django/voip/appels/entrant/', {'numero': '0698765432'})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['direction'], 'entrant')
        self.assertEqual(resp.data['cible'], {'type': 'lead', 'id': self.lead.id})

    def test_appel_entrant_priorise_client_sur_lead_si_deux_matches(self):
        Lead.objects.create(
            company=self.company, nom='Bennani-dup',
            telephone='+212612345678')
        resp = self.api.post(
            '/api/django/voip/appels/entrant/', {'numero': '0612345678'})
        self.assertEqual(resp.data['cible'], {'type': 'client', 'id': self.client_obj.id})

    def test_liste_appels_scopee_societe(self):
        self.api.post('/api/django/voip/appels/sortant/', {'numero': '0612345678'})
        resp = self.api.get('/api/django/voip/appels/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data['results'] if 'results' in resp.data else resp.data), 1)

    def test_config_patch_refuse_pour_role_normal(self):
        api_normal = _api_for(self.commercial)
        resp = api_normal.patch(
            '/api/django/voip/parametres/', {'actif': False})
        self.assertEqual(resp.status_code, 403)

    def test_config_patch_ok_pour_admin(self):
        resp = self.api.patch(
            '/api/django/voip/parametres/', {'actif': False})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['actif'])
        # Redevient inerte : plus aucun appel possible.
        resp2 = self.api.post(
            '/api/django/voip/appels/sortant/', {'numero': '0612345678'})
        self.assertEqual(resp2.status_code, 409)


class VoipCrossTenantTest(TestCase):
    """Isolation stricte multi-société : aucune fuite d'un appel/config/
    identifiant d'une autre société."""

    def setUp(self):
        self.company_a = _company(slug='voip-a', nom='VoIP A')
        self.company_b = _company(slug='voip-b', nom='VoIP B')
        self.user_a = _user(self.company_a, 'voip_user_a', role='admin')
        self.user_b = _user(self.company_b, 'voip_user_b', role='admin')
        VoipParametres.objects.create(
            company=self.company_a, fournisseur='sip_generique', actif=True,
            serveur_sip='sip.a.test')
        VoipParametres.objects.create(
            company=self.company_b, fournisseur='sip_generique', actif=True,
            serveur_sip='sip.b.test')
        self.api_a = _api_for(self.user_a)
        self.api_b = _api_for(self.user_b)

    def test_appel_dune_societe_invisible_de_lautre(self):
        appel = self.api_a.post(
            '/api/django/voip/appels/sortant/', {'numero': '0612345678'}).data
        resp = self.api_b.get(f"/api/django/voip/appels/{appel['id']}/")
        self.assertEqual(resp.status_code, 404)

    def test_terminer_appel_dune_autre_societe_refuse(self):
        appel = self.api_a.post(
            '/api/django/voip/appels/sortant/', {'numero': '0612345678'}).data
        resp = self.api_b.post(
            f"/api/django/voip/appels/{appel['id']}/terminer/",
            {'duree_secondes': 10})
        self.assertEqual(resp.status_code, 404)

    def test_parametres_isoles_par_societe(self):
        self.api_a.patch('/api/django/voip/parametres/', {'serveur_sip': 'sip.a2.test'})
        resp_b = self.api_b.get('/api/django/voip/parametres/')
        self.assertEqual(resp_b.data['serveur_sip'], 'sip.b.test')


class VoipIdentifiantsUtilisateurTest(TestCase):
    """Identifiants SIP strictement personnels — jamais ceux d'un collègue."""

    def setUp(self):
        self.company = _company(slug='voip-ident', nom='VoIP Ident')
        self.alice = _user(self.company, 'voip_alice', role='normal')
        self.bob = _user(self.company, 'voip_bob', role='normal')

    def test_get_cree_identifiant_vide_pour_soi(self):
        api = _api_for(self.alice)
        resp = api.get('/api/django/voip/mes-identifiants/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['identifiant_sip'], '')

    def test_patch_ne_touche_que_son_propre_identifiant(self):
        api_alice = _api_for(self.alice)
        api_bob = _api_for(self.bob)
        api_alice.patch(
            '/api/django/voip/mes-identifiants/', {'identifiant_sip': 'alice-sip'})
        resp_bob = api_bob.get('/api/django/voip/mes-identifiants/')
        self.assertEqual(resp_bob.data['identifiant_sip'], '')

        alice_row = VoipIdentifiantUtilisateur.objects.get(
            company=self.company, utilisateur=self.alice)
        self.assertEqual(alice_row.identifiant_sip, 'alice-sip')
