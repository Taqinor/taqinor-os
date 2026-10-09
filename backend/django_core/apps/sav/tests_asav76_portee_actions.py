"""ASAV76 — garde de CLASSE : rejoue TOUTES les `@action` de `TicketViewSet`,
`ProblemeViewSet` et `AlarmeOnduleurViewSet` (découvertes par introspection,
jamais une liste à la main) avec un Technicien de portée équipe et un id hors
portée. Échoue dès qu'une écriture ou une lecture hors portée réussit : une
nouvelle action non bornée fait donc échouer la CI.

Run :
    python manage.py test apps.sav.tests_asav76_portee_actions -v2
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
from apps.sav.models import (
    AlarmeOnduleur, PieceConsommee, Probleme, ProblemeIncident, Ticket,
    TicketActivity, TicketFollower,
)
from apps.sav.views import (
    AlarmeOnduleurViewSet, ProblemeViewSet, TicketViewSet,
)

User = get_user_model()
BASE = '/api/django/sav'
PREFIXES = {
    TicketViewSet: 'tickets', ProblemeViewSet: 'problemes',
    AlarmeOnduleurViewSet: 'alarmes-onduleur',
}
SECRET = 'NOTE-SECRETE-ASAV76'


class PorteeActionsTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav76-co', defaults={'nom': 'ASAV76 Co'})
        role = Role.objects.create(
            company=self.company, nom='Technicien ASAV76',
            permissions=list(TECHNICIEN_PERMISSIONS) + [
                'records_scope_equipe', 'sav_probleme_gerer'],
            est_systeme=False)
        self.tech = User.objects.create_user(
            username='asav76_tech', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.autre = User.objects.create_user(
            username='asav76_autre', password='x', company=self.company,
            role_legacy='admin')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV76')
        self.hors = Ticket.objects.create(
            company=self.company, reference='SAV-ASAV76-HORS', client=client,
            type=Ticket.Type.CORRECTIF, priorite='normale',
            created_by=self.autre, technicien_responsable=self.autre)
        TicketActivity.objects.create(
            company=self.company, ticket=self.hors, user=self.autre,
            kind=TicketActivity.Kind.NOTE, body=SECRET)
        self.probleme = Probleme.objects.create(
            company=self.company, reference='PRB-ASAV76-0001',
            titre='Série défectueuse')
        self.alarme = AlarmeOnduleur.objects.create(
            company=self.company, code='E07',
            gravite=AlarmeOnduleur.Gravite.WARNING,
            date_detection=timezone.now())
        self.api = APIClient(raise_request_exception=False)
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.tech)}')

    def _etat(self):
        """Instantané du ticket hors portée et de tout ce qui s'y rattache."""
        t = Ticket.objects.filter(pk=self.hors.pk).values().first()
        return (
            t,
            TicketActivity.objects.filter(ticket=self.hors).count(),
            PieceConsommee.objects.filter(ticket=self.hors).count(),
            TicketFollower.objects.filter(ticket=self.hors).count(),
            ProblemeIncident.objects.filter(ticket=self.hors).count(),
            AlarmeOnduleur.objects.filter(ticket=self.hors).count(),
        )

    def _corps(self):
        pk = self.hors.pk
        return {
            'ids': [pk], 'ticket': pk, 'ticket_id': pk, 'ticket_ids': [pk],
            'doublon_id': pk, 'id': pk, 'titre': 'Probleme ASAV76',
            'operation': 'priorite', 'priorite': 'urgente',
            'statut': 'en_cours', 'motif': 'test', 'note': 'test',
            'technicien': self.tech.pk, 'produit': 1, 'quantite': '1',
        }

    def _actions(self):
        for viewset, prefixe in PREFIXES.items():
            for action in viewset.get_extra_actions():
                chemin = action.url_path
                if any(c in chemin for c in '(<'):
                    continue
                for methode in action.mapping:
                    yield viewset, prefixe, action, methode.upper()

    def _appeler(self, prefixe, action, methode, ressource_pk):
        base = f'{BASE}/{prefixe}/'
        if action.detail:
            base += f'{ressource_pk}/'
        url = f'{base}{action.url_path}/'
        return self.api.generic(
            methode, url, json.dumps(self._corps()),
            content_type='application/json')

    def test_actions_decouvertes(self):
        """Garde de la garde : l'introspection trouve bien les actions."""
        noms = {(prefixe, a.url_path) for _, prefixe, a, _m in self._actions()}
        self.assertIn(('tickets', 'actions-groupees'), noms)
        self.assertIn(('tickets', 'fusionner'), noms)
        self.assertIn(('problemes', 'lier-ticket'), noms)
        self.assertIn(('alarmes-onduleur', 'escalader'), noms)

    def test_actions_bornees(self):
        avant = self._etat()
        for viewset, prefixe, action, methode in self._actions():
            if prefixe == 'tickets':
                ressource = self.hors.pk
            elif prefixe == 'problemes':
                ressource = self.probleme.pk
            else:
                ressource = self.alarme.pk
            reponse = self._appeler(prefixe, action, methode, ressource)
            contexte = f'{methode} {prefixe}/{action.url_path}'
            contenu = reponse.content.decode('utf-8', 'ignore')
            self.assertNotIn(SECRET, contenu, contexte)
            self.assertNotIn(self.hors.reference, contenu, contexte)
            self.assertEqual(self._etat(), avant, contexte)
