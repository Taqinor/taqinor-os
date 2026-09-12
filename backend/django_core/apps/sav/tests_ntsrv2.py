"""NTSRV2 — Formulaire portail client → ticket SAV (endpoint public tokenisé).

Critère d'acceptation :
  * un POST valide crée un ticket visible au back-office (statut NOUVEAU,
    canal_ouverture=portail, note initiale au chatter) et renvoie un numéro
    de suivi ;
  * un POST avec jeton invalide / expiré (compte révoqué) renvoie 404 SANS
    fuite d'information (message identique dans les deux cas).

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv2 -v 2
"""
from django.core.cache import cache
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.portail.models import ComptePortailClient
from apps.sav.models import Ticket, TicketActivity

URL = '/api/django/sav/portail/tickets/'


class NTSRV2PortailTicketTest(TestCase):
    def setUp(self):
        # Le throttle public (30/min/IP) est cache-based : on repart d'un
        # compteur vide pour ne jamais dépendre des tests voisins.
        cache.clear()
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv2', defaults={'nom': 'Sav Co NTSRV2'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV2',
            email='portail@example.invalid')
        self.compte = ComptePortailClient.objects.create(
            company=self.company, client=self.client_obj,
            token_acces='jeton-portail-ntsrv2')

    def _post(self, payload):
        return self.client.post(URL, payload, content_type='application/json')

    def test_post_valide_cree_un_ticket(self):
        resp = self._post({
            'token': 'jeton-portail-ntsrv2',
            'sujet': 'Onduleur en défaut',
            'description': 'Voyant rouge depuis ce matin.',
            'priorite': 'haute',
        })
        self.assertEqual(resp.status_code, 201, resp.content)
        ticket = Ticket.objects.get()
        self.assertEqual(ticket.company, self.company)
        self.assertEqual(ticket.client, self.client_obj)
        self.assertEqual(ticket.statut, Ticket.Statut.NOUVEAU)
        self.assertEqual(ticket.canal_ouverture, Ticket.CanalOuverture.PORTAIL)
        self.assertEqual(ticket.priorite, Ticket.Priorite.HAUTE)
        self.assertEqual(resp.json()['numero_suivi'], ticket.reference)
        self.assertTrue(resp.json()['suivi_token'])
        self.assertTrue(TicketActivity.objects.filter(
            ticket=ticket, kind=TicketActivity.Kind.NOTE).exists())

    def test_priorite_par_defaut_normale(self):
        resp = self._post({'token': 'jeton-portail-ntsrv2', 'sujet': 'Question'})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Ticket.objects.get().priorite, Ticket.Priorite.NORMALE)

    def test_jeton_invalide_renvoie_404_sans_fuite(self):
        resp = self._post({'token': 'jeton-inconnu', 'sujet': 'Panne'})
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(Ticket.objects.count(), 0)
        self.assertNotIn('portail@example.invalid', resp.content.decode())

    def test_compte_revoque_renvoie_le_meme_404(self):
        inconnu = self._post({'token': 'jeton-inconnu', 'sujet': 'Panne'})
        self.compte.actif = False
        self.compte.save(update_fields=['actif'])
        revoque = self._post({'token': 'jeton-portail-ntsrv2', 'sujet': 'Panne'})
        self.assertEqual(revoque.status_code, 404)
        self.assertEqual(revoque.content, inconnu.content,
                         'le 404 doit être indistinguable (aucune fuite)')
        self.assertEqual(Ticket.objects.count(), 0)

    def test_jeton_absent_renvoie_404(self):
        self.assertEqual(self._post({'sujet': 'Panne'}).status_code, 404)

    def test_sujet_vide_refuse_en_nommant_le_champ(self):
        resp = self._post({'token': 'jeton-portail-ntsrv2', 'sujet': ''})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('sujet', resp.json())
        self.assertEqual(Ticket.objects.count(), 0)

    def test_priorite_inconnue_refusee_en_francais(self):
        resp = self._post({'token': 'jeton-portail-ntsrv2', 'sujet': 'X',
                           'priorite': 'catastrophique'})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('priorite', resp.json())

    def test_honeypot_ne_cree_rien(self):
        resp = self._post({'token': 'jeton-portail-ntsrv2', 'sujet': 'Spam',
                           'site_web': 'http://spam.invalid'})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_reponse_publique_est_noindex(self):
        resp = self._post({'token': 'jeton-portail-ntsrv2', 'sujet': 'Panne'})
        self.assertIn('noindex', resp['X-Robots-Tag'])

    def test_la_societe_ne_vient_jamais_du_corps(self):
        """Un corps qui tente d'imposer une autre société est ignoré : la
        société est déduite du jeton, point."""
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv2-autre', defaults={'nom': 'Autre'})
        resp = self._post({'token': 'jeton-portail-ntsrv2', 'sujet': 'Panne',
                           'company': autre.pk})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Ticket.objects.get().company, self.company)
