"""MSGACC1 — Message d'accueil : posé par un responsable/admin pour UN
employé, affiché EN PLEIN ÉCRAN à sa PREMIÈRE ouverture de l'ERP à partir
d'une heure choisie.

Couverture :
  - visibilité à l'heure (avant `visible_a_partir_de` → absent de `a-lire` ;
    après → présent, plus ancien d'abord) ;
  - `lu` idempotent, réservé au destinataire (jamais l'auteur ni un admin) ;
  - `create` réservé au palier Responsable/Admin, `auteur`/`company` posés
    côté serveur (jamais depuis le corps) ;
  - erreurs par champ (destinataire inactif/autre société, corps vide) ;
  - isolation multi-tenant (société A ne voit jamais les messages de B) ;
  - `list` : mes messages envoyés, ou toute la société pour un
    Responsable/Admin ;
  - suppression refusée une fois lu, autorisée à l'auteur/admin sinon ;
  - CE N'EST PAS UNE NOTIFICATION : aucune ligne `Notification` créée.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from .models import MessageAccueil, Notification

User = get_user_model()

URL_LIST = '/api/django/notifications/messages-accueil/'
URL_A_LIRE = '/api/django/notifications/messages-accueil/a-lire/'


def _company(nom='MsgAccCo'):
    return Company.objects.create(nom=nom)


def _user(company, username, role_legacy='normal', is_active=True):
    return User.objects.create_user(
        username=username, password='pw', company=company,
        role_legacy=role_legacy, is_active=is_active)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class VisibiliteALHeureTests(TestCase):
    """Le coeur de la fonctionnalité : visible seulement à partir de l'heure
    choisie, jamais avant."""

    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'admin1', role_legacy='admin')
        self.employe = _user(self.company, 'employe1')

    def test_absent_avant_heure(self):
        futur = timezone.now() + timedelta(hours=1)
        MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=futur, corps='Bonjour')
        res = _auth(self.employe).get(URL_A_LIRE)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['messages'], [])

    def test_present_apres_heure(self):
        passe = timezone.now() - timedelta(minutes=5)
        msg = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=passe, corps='Bonjour l’équipe')
        res = _auth(self.employe).get(URL_A_LIRE)
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(len(res.data['messages']), 1)
        entree = res.data['messages'][0]
        self.assertEqual(entree['id'], msg.id)
        self.assertEqual(entree['corps'], 'Bonjour l’équipe')
        self.assertEqual(entree['auteur_nom'], 'admin1')

    def test_plus_ancien_d_abord(self):
        now = timezone.now()
        recent = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=now - timedelta(minutes=1), corps='Récent')
        ancien = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=now - timedelta(hours=2), corps='Ancien')
        res = _auth(self.employe).get(URL_A_LIRE)
        ids = [m['id'] for m in res.data['messages']]
        self.assertEqual(ids, [ancien.id, recent.id])

    def test_deja_lu_absent_de_a_lire(self):
        passe = timezone.now() - timedelta(minutes=5)
        msg = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=passe, corps='Bonjour', lu_le=timezone.now())
        res = _auth(self.employe).get(URL_A_LIRE)
        self.assertEqual(res.data['messages'], [])
        self.assertIsNotNone(msg.lu_le)

    def test_auteur_nom_direction_si_auteur_supprime(self):
        """`auteur` SET_NULL : perdre la trace de l'auteur ne doit jamais
        empêcher l'affichage du message (auteur_nom=None → « Direction »
        est un repli CÔTÉ FRONTEND, ici on vérifie juste None, pas de crash)."""
        passe = timezone.now() - timedelta(minutes=5)
        MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=None,
            visible_a_partir_de=passe, corps='Bonjour')
        res = _auth(self.employe).get(URL_A_LIRE)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['messages'][0]['auteur_nom'])

    def test_ce_n_est_pas_une_notification(self):
        """Aucune ligne `Notification` ne doit jamais être créée par cette
        fonctionnalité — règle fondateur explicite."""
        passe = timezone.now() - timedelta(minutes=5)
        MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=passe, corps='Bonjour')
        _auth(self.employe).get(URL_A_LIRE)
        self.assertEqual(Notification.objects.count(), 0)


class MarquageLuTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'admin2', role_legacy='admin')
        self.employe = _user(self.company, 'employe2')
        self.autre_employe = _user(self.company, 'employe3')
        self.msg = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=timezone.now() - timedelta(minutes=5),
            corps='Bonjour')

    def test_destinataire_peut_marquer_lu(self):
        res = _auth(self.employe).post(f'{URL_LIST}{self.msg.id}/lu/')
        self.assertEqual(res.status_code, 200, res.data)
        self.msg.refresh_from_db()
        self.assertIsNotNone(self.msg.lu_le)

    def test_idempotent(self):
        api = _auth(self.employe)
        api.post(f'{URL_LIST}{self.msg.id}/lu/')
        self.msg.refresh_from_db()
        premiere_lecture = self.msg.lu_le
        api.post(f'{URL_LIST}{self.msg.id}/lu/')
        self.msg.refresh_from_db()
        self.assertEqual(self.msg.lu_le, premiere_lecture)

    def test_un_autre_utilisateur_ne_peut_pas_marquer_lu(self):
        """Réservé au destinataire : ni un collègue, ni l'auteur/admin ne
        peuvent poser `lu_le` à sa place — le message reste actionnable pour
        le vrai destinataire."""
        res = _auth(self.autre_employe).post(f'{URL_LIST}{self.msg.id}/lu/')
        self.assertEqual(res.status_code, 404, res.data)
        self.msg.refresh_from_db()
        self.assertIsNone(self.msg.lu_le)

    def test_auteur_ne_peut_pas_marquer_lu_a_la_place_du_destinataire(self):
        res = _auth(self.admin).post(f'{URL_LIST}{self.msg.id}/lu/')
        self.assertEqual(res.status_code, 404, res.data)
        self.msg.refresh_from_db()
        self.assertIsNone(self.msg.lu_le)


class CreationPermissionsTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'admin3', role_legacy='admin')
        self.responsable = _user(self.company, 'resp3', role_legacy='responsable')
        self.normal = _user(self.company, 'normal3', role_legacy='normal')
        self.employe = _user(self.company, 'employe4')

    def _payload(self, destinataire_id):
        return {
            'destinataire': destinataire_id,
            'visible_a_partir_de': (
                timezone.now() + timedelta(hours=1)).isoformat(),
            'corps': 'Bonjour, un message pour toi.',
        }

    def test_admin_peut_creer(self):
        res = _auth(self.admin).post(
            URL_LIST, self._payload(self.employe.id), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['auteur'], self.admin.id)

    def test_responsable_peut_creer(self):
        res = _auth(self.responsable).post(
            URL_LIST, self._payload(self.employe.id), format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_normal_ne_peut_pas_creer(self):
        res = _auth(self.normal).post(
            URL_LIST, self._payload(self.employe.id), format='json')
        self.assertEqual(res.status_code, 403, res.data)
        self.assertEqual(MessageAccueil.objects.count(), 0)

    def test_auteur_et_company_poses_cote_serveur(self):
        """Un `auteur`/`company` fourni dans le corps est IGNORÉ — posé par
        `perform_create`, jamais lu de la requête (règle fondateur)."""
        autre_societe = _company('AutreCo')
        payload = self._payload(self.employe.id)
        payload['auteur'] = 999999
        payload['company'] = autre_societe.id
        res = _auth(self.admin).post(URL_LIST, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        msg = MessageAccueil.objects.get(id=res.data['id'])
        self.assertEqual(msg.auteur_id, self.admin.id)
        self.assertEqual(msg.company_id, self.company.id)

    def test_passe_accepte(self):
        """Un message « pour tout de suite » (heure déjà passée) est
        légitime — jamais rejeté."""
        payload = self._payload(self.employe.id)
        payload['visible_a_partir_de'] = (
            timezone.now() - timedelta(minutes=1)).isoformat()
        res = _auth(self.admin).post(URL_LIST, payload, format='json')
        self.assertEqual(res.status_code, 201, res.data)


class ValidationParChampTests(TestCase):
    """Règle fondateur : jamais un message générique — l'erreur nomme le
    champ fautif."""

    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'admin4', role_legacy='admin')
        self.employe = _user(self.company, 'employe5')

    def test_corps_vide_rejete_sous_le_champ(self):
        res = _auth(self.admin).post(URL_LIST, {
            'destinataire': self.employe.id,
            'visible_a_partir_de': timezone.now().isoformat(),
            'corps': '   ',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('corps', res.data)

    def test_destinataire_inactif_rejete(self):
        inactif = _user(self.company, 'inactif5', is_active=False)
        res = _auth(self.admin).post(URL_LIST, {
            'destinataire': inactif.id,
            'visible_a_partir_de': timezone.now().isoformat(),
            'corps': 'Bonjour',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('destinataire', res.data)

    def test_destinataire_autre_societe_rejete(self):
        autre = _company('AutreCo2')
        etranger = _user(autre, 'etranger5')
        res = _auth(self.admin).post(URL_LIST, {
            'destinataire': etranger.id,
            'visible_a_partir_de': timezone.now().isoformat(),
            'corps': 'Bonjour',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('destinataire', res.data)

    def test_datetime_invalide_rejete(self):
        res = _auth(self.admin).post(URL_LIST, {
            'destinataire': self.employe.id,
            'visible_a_partir_de': 'pas-une-date',
            'corps': 'Bonjour',
        }, format='json')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertIn('visible_a_partir_de', res.data)


class IsolationSocieteTests(TestCase):
    def setUp(self):
        self.company_a = _company('SocieteA')
        self.company_b = _company('SocieteB')
        self.admin_a = _user(self.company_a, 'adminA', role_legacy='admin')
        self.employe_a = _user(self.company_a, 'employeA')
        self.admin_b = _user(self.company_b, 'adminB', role_legacy='admin')
        self.employe_b = _user(self.company_b, 'employeB')
        passe = timezone.now() - timedelta(minutes=5)
        self.msg_a = MessageAccueil.objects.create(
            company=self.company_a, destinataire=self.employe_a,
            auteur=self.admin_a, visible_a_partir_de=passe, corps='Pour A')
        self.msg_b = MessageAccueil.objects.create(
            company=self.company_b, destinataire=self.employe_b,
            auteur=self.admin_b, visible_a_partir_de=passe, corps='Pour B')

    def test_a_lire_isole_par_societe(self):
        res = _auth(self.employe_a).get(URL_A_LIRE)
        ids = [m['id'] for m in res.data['messages']]
        self.assertEqual(ids, [self.msg_a.id])

    def test_liste_gestion_isolee_par_societe(self):
        res = _auth(self.admin_a).get(URL_LIST)
        ids = [row['id'] for row in res.data['results']] if isinstance(res.data, dict) and 'results' in res.data else [row['id'] for row in res.data]
        self.assertIn(self.msg_a.id, ids)
        self.assertNotIn(self.msg_b.id, ids)


class ListeGestionTests(TestCase):
    """`list` : mes messages envoyés, ou toute la société pour un
    Responsable/Admin."""

    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'adminL', role_legacy='admin')
        self.responsable = _user(self.company, 'respL', role_legacy='responsable')
        self.employe1 = _user(self.company, 'employeL1')
        self.employe2 = _user(self.company, 'employeL2')
        passe = timezone.now() - timedelta(minutes=5)
        self.msg_admin = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe1, auteur=self.admin,
            visible_a_partir_de=passe, corps='De admin')
        self.msg_responsable = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe2,
            auteur=self.responsable, visible_a_partir_de=passe, corps='De resp')

    @staticmethod
    def _ids(data):
        rows = data['results'] if isinstance(data, dict) and 'results' in data else data
        return [row['id'] for row in rows]

    def test_admin_voit_toute_la_societe(self):
        res = _auth(self.admin).get(URL_LIST)
        ids = self._ids(res.data)
        self.assertIn(self.msg_admin.id, ids)
        self.assertIn(self.msg_responsable.id, ids)

    def test_responsable_voit_toute_la_societe(self):
        res = _auth(self.responsable).get(URL_LIST)
        ids = self._ids(res.data)
        self.assertIn(self.msg_admin.id, ids)
        self.assertIn(self.msg_responsable.id, ids)

    def test_employe_ne_voit_que_ses_propres_envois_vide(self):
        """Un employé normal n'a jamais rien envoyé — la liste est vide,
        jamais les messages d'autrui."""
        res = _auth(self.employe1).get(URL_LIST)
        ids = self._ids(res.data)
        self.assertEqual(ids, [])


class SuppressionTests(TestCase):
    def setUp(self):
        self.company = _company()
        self.admin = _user(self.company, 'adminS', role_legacy='admin')
        self.autre_admin = _user(self.company, 'adminS2', role_legacy='admin')
        self.employe = _user(self.company, 'employeS')
        self.passe = timezone.now() - timedelta(minutes=5)

    def test_suppression_refusee_si_lu(self):
        msg = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=self.passe, corps='Bonjour', lu_le=timezone.now())
        res = _auth(self.admin).delete(f'{URL_LIST}{msg.id}/')
        self.assertEqual(res.status_code, 400, res.data)
        self.assertTrue(MessageAccueil.objects.filter(id=msg.id).exists())

    def test_auteur_peut_supprimer_si_non_lu(self):
        msg = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=self.passe, corps='Bonjour')
        res = _auth(self.admin).delete(f'{URL_LIST}{msg.id}/')
        self.assertEqual(res.status_code, 204, res.data)
        self.assertFalse(MessageAccueil.objects.filter(id=msg.id).exists())

    def test_un_autre_admin_peut_supprimer_si_non_lu(self):
        msg = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=self.passe, corps='Bonjour')
        res = _auth(self.autre_admin).delete(f'{URL_LIST}{msg.id}/')
        self.assertEqual(res.status_code, 204, res.data)

    def test_employe_normal_ne_peut_pas_supprimer(self):
        msg = MessageAccueil.objects.create(
            company=self.company, destinataire=self.employe, auteur=self.admin,
            visible_a_partir_de=self.passe, corps='Bonjour')
        res = _auth(self.employe).delete(f'{URL_LIST}{msg.id}/')
        self.assertEqual(res.status_code, 403, res.data)
        self.assertTrue(MessageAccueil.objects.filter(id=msg.id).exists())
