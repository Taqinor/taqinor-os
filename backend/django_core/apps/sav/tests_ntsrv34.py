"""NTSRV34 — Modèles de réponse par canal (extension XSAV23).

Critère d'acceptation : une macro non listée pour WhatsApp n'apparaît pas
dans le sélecteur d'un ticket ouvert par ce canal.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv34 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import ReponseType, Ticket

User = get_user_model()

LISTE = '/api/django/sav/reponses-type/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV34ReponseTypeCanauxTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv34', defaults={'nom': 'Sav Co NTSRV34'})
        self.admin = User.objects.create_user(
            username='ntsrv34_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV34')
        # Macro « ton formel » réservée à l'e-mail, macro générique libre.
        self.formelle = ReponseType.objects.create(
            company=self.company, titre='Ton formel',
            corps='Madame, Monsieur,', canaux_autorises=['email'])
        self.libre = ReponseType.objects.create(
            company=self.company, titre='Accusé de réception',
            corps='Bien reçu, nous revenons vers vous.')
        self.ticket_whatsapp = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV34-WA',
            client=self.client_obj, statut=Ticket.Statut.EN_COURS,
            canal_ouverture=Ticket.CanalOuverture.WHATSAPP)
        self.ticket_email = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV34-ML',
            client=self.client_obj, statut=Ticket.Statut.EN_COURS,
            canal_ouverture=Ticket.CanalOuverture.EMAIL)

    def _titres(self, url):
        resp = self.api.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        lignes = data['results'] if isinstance(data, dict) else data
        return {ligne['titre'] for ligne in lignes}

    # ── Non-régression : sans paramètre, la liste ne change pas ──────────
    def test_liste_sans_canal_inchangee(self):
        self.assertEqual(self._titres(LISTE),
                         {'Ton formel', 'Accusé de réception'})

    def test_defaut_aucune_restriction(self):
        self.assertIsNone(self.libre.canaux_autorises)
        self.assertTrue(self.libre.autorise_canal('whatsapp'))
        self.assertTrue(self.libre.autorise_canal('email'))

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_macro_email_absente_du_selecteur_whatsapp(self):
        titres = self._titres(f'{LISTE}?ticket={self.ticket_whatsapp.pk}')
        self.assertNotIn('Ton formel', titres)
        self.assertIn('Accusé de réception', titres)

    def test_macro_email_presente_sur_un_ticket_email(self):
        titres = self._titres(f'{LISTE}?ticket={self.ticket_email.pk}')
        self.assertEqual(titres, {'Ton formel', 'Accusé de réception'})

    def test_filtre_par_canal_direct(self):
        self.assertNotIn('Ton formel', self._titres(f'{LISTE}?canal=whatsapp'))
        self.assertIn('Ton formel', self._titres(f'{LISTE}?canal=email'))

    def test_canal_inconnu_ne_masque_rien(self):
        self.assertEqual(self._titres(f'{LISTE}?canal=pigeon'),
                         {'Ton formel', 'Accusé de réception'})

    def test_ticket_dune_autre_societe_ne_filtre_pas(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv34-bis', defaults={'nom': 'Autre NTSRV34'})
        client_autre = Client.objects.create(
            company=autre, nom='Client', prenom='NTSRV34bis')
        etranger = Ticket.objects.create(
            company=autre, reference='SAV-NTSRV34-X',
            client=client_autre, statut=Ticket.Statut.EN_COURS,
            canal_ouverture=Ticket.CanalOuverture.WHATSAPP)
        # Ticket hors société : introuvable pour cet utilisateur, donc aucun
        # filtre appliqué (jamais une fuite du canal d'un autre tenant).
        self.assertEqual(self._titres(f'{LISTE}?ticket={etranger.pk}'),
                         {'Ton formel', 'Accusé de réception'})

    # ── Mapping canal d'ouverture -> canal de réponse ────────────────────
    def test_canal_de_ticket(self):
        manuel = Ticket(canal_ouverture=Ticket.CanalOuverture.MANUEL)
        tel = Ticket(canal_ouverture=Ticket.CanalOuverture.TELEPHONE)
        portail = Ticket(canal_ouverture=Ticket.CanalOuverture.PORTAIL)
        self.assertEqual(ReponseType.canal_de_ticket(manuel), 'interne')
        self.assertEqual(ReponseType.canal_de_ticket(tel), 'interne')
        self.assertEqual(ReponseType.canal_de_ticket(portail), 'portail')
        self.assertEqual(
            ReponseType.canal_de_ticket(self.ticket_whatsapp), 'whatsapp')

    def test_valeur_heritee_malformee_ne_masque_pas(self):
        self.libre.canaux_autorises = 'email'  # chaîne, pas une liste
        self.libre.save(update_fields=['canaux_autorises'])
        self.assertEqual(self.libre.canaux_normalises(), [])
        self.assertTrue(self.libre.autorise_canal('whatsapp'))

    # ── Écriture : canal inconnu refusé ──────────────────────────────────
    def test_creation_canal_inconnu_refusee(self):
        resp = self.api.post(
            LISTE, {'titre': 'Bidon', 'corps': 'x',
                    'canaux_autorises': ['pigeon']}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn('canaux_autorises', resp.json())

    def test_creation_canaux_dedoublonnes(self):
        resp = self.api.post(
            LISTE, {'titre': 'Multi', 'corps': 'x',
                    'canaux_autorises': ['email', 'email', 'portail']},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()['canaux_autorises'],
                         ['email', 'portail'])

    # ── Refus serveur sur `noter` (défense en profondeur) ────────────────
    def test_noter_refuse_macro_hors_canal(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket_whatsapp.pk}/noter/',
            {'reponse_type_id': self.formelle.pk}, format='json')
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_noter_accepte_macro_du_bon_canal(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket_email.pk}/noter/',
            {'reponse_type_id': self.formelle.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_noter_accepte_macro_sans_restriction(self):
        resp = self.api.post(
            f'/api/django/sav/tickets/{self.ticket_whatsapp.pk}/noter/',
            {'reponse_type_id': self.libre.pk}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
