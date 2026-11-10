"""ASAV25 — les actions qui reçoivent des ids de tickets respectent la portée.

Un Technicien de portée équipe (``records_scope_equipe``, sans superviseur →
lui seul) ne peut ni modifier en lot, ni fusionner, ni rattacher à un
problème, ni escalader une alarme vers un ticket qu'il ne voit pas ; ses
propres tickets restent traités ; un responsable de portée société inchangé.

Run :
    python manage.py test apps.sav.tests_asav25_portee_equipe -v2
"""
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
    AlarmeOnduleur, Probleme, ProblemeIncident, Ticket, TicketActivity,
)

User = get_user_model()
BASE = '/api/django/sav'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class PorteeEquipeTests(TestCase):

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='asav25-co', defaults={'nom': 'ASAV25 Co'})
        role = Role.objects.create(
            company=self.company, nom='Technicien ASAV25',
            # ASEC50 — l'op ``technicien`` des actions groupées exige
            # ``sav_reassign`` ; ce module éprouve la PORTÉE, pas ce droit.
            permissions=list(TECHNICIEN_PERMISSIONS) + [
                'records_scope_equipe', 'sav_probleme_gerer', 'sav_reassign'],
            est_systeme=False)
        self.tech = User.objects.create_user(
            username='asav25_tech', password='x', company=self.company,
            role=role, role_legacy='responsable')
        self.autre = User.objects.create_user(
            username='asav25_autre', password='x', company=self.company,
            role_legacy='admin')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ASAV25')
        self.a = self._ticket('A', self.autre)
        self.b = self._ticket('B', self.autre)
        self.d = self._ticket('D', self.autre)
        TicketActivity.objects.create(
            company=self.company, ticket=self.d, user=self.autre,
            kind=TicketActivity.Kind.NOTE, body='NOTE-SECRETE-AUTRE')
        self.m = self._ticket('M', self.tech)
        self.api = auth(self.tech)

    def _ticket(self, nom, user):
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-ASAV25-{nom}',
            client=self.client_obj, type=Ticket.Type.CORRECTIF,
            priorite='normale', created_by=user,
            technicien_responsable=user)

    def test_lot_hors_portee_ignore(self):
        for operation, extra in (('priorite', {'priorite': 'urgente'}),
                                 ('technicien', {'technicien': self.tech.pk}),
                                 ('annuler', {'motif': 'test'})):
            r = self.api.post(f'{BASE}/tickets/actions-groupees/', {
                'ids': [self.a.pk, self.b.pk], 'operation': operation,
                **extra}, format='json')
            self.assertEqual(r.status_code, 200, r.content)
            self.assertEqual(r.data['traites'], [])
            self.assertEqual(
                {e['id'] for e in r.data['echecs']}, {self.a.pk, self.b.pk})
        for t in (self.a, self.b):
            t.refresh_from_db()
            self.assertEqual(t.priorite, 'normale')
            self.assertEqual(t.technicien_responsable_id, self.autre.pk)
            self.assertFalse(t.annule)

    def test_fusion_hors_portee_404(self):
        r = self.api.post(f'{BASE}/tickets/{self.m.pk}/fusionner/',
                          {'doublon_id': self.d.pk}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        self.d.refresh_from_db()
        self.assertFalse(self.d.annule)
        self.assertTrue(TicketActivity.objects.filter(
            ticket=self.d, body='NOTE-SECRETE-AUTRE').exists())
        self.assertFalse(TicketActivity.objects.filter(
            ticket=self.m, body__contains='NOTE-SECRETE-AUTRE').exists())

    def test_lier_ticket_hors_portee_404(self):
        probleme = Probleme.objects.create(
            company=self.company, reference='PRB-ASAV25-0001',
            titre='Série défectueuse')
        r = self.api.post(f'{BASE}/problemes/{probleme.pk}/lier-ticket/',
                          {'ticket': self.a.pk}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        self.assertFalse(ProblemeIncident.objects.filter(
            probleme=probleme, ticket=self.a).exists())

    def test_escalader_hors_portee_404(self):
        alarme = AlarmeOnduleur.objects.create(
            company=self.company, code='E07',
            gravite=AlarmeOnduleur.Gravite.WARNING,
            date_detection=timezone.now())
        r = self.api.post(
            f'{BASE}/alarmes-onduleur/{alarme.pk}/escalader/',
            {'ticket': self.a.pk}, format='json')
        self.assertEqual(r.status_code, 404, r.content)
        alarme.refresh_from_db()
        self.assertIsNone(alarme.ticket_id)

    def test_dans_portee_ok(self):
        r = self.api.post(f'{BASE}/tickets/actions-groupees/', {
            'ids': [self.m.pk], 'operation': 'priorite',
            'priorite': 'haute'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['traites'], [self.m.pk])
        # Un responsable de portée société : inchangé.
        r = auth(self.autre).post(f'{BASE}/tickets/actions-groupees/', {
            'ids': [self.a.pk, self.m.pk], 'operation': 'priorite',
            'priorite': 'haute'}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(sorted(r.data['traites']), sorted([self.a.pk, self.m.pk]))

    def test_telephone_client_masque_sans_client_pii_voir(self):
        """APFS27 (C-APFS-028) — un rôle sans ``client_pii_voir`` lit
        ``client_telephone: null`` sur la fiche et la liste des tickets ;
        témoin (Technicien) et compte hérité : présent."""
        Client.objects.filter(pk=self.client_obj.pk).update(
            telephone='0661028028')
        role = Role.objects.create(
            company=self.company, nom='Technicien sans client_pii_voir',
            permissions=[p for p in TECHNICIEN_PERMISSIONS
                         if p != 'client_pii_voir'], est_systeme=False)
        sans = User.objects.create_user(
            username='apfs27_sans', password='x', company=self.company,
            role=role, role_legacy='responsable')
        # Portée équipe sans superviseur (lui seul) : son propre ticket, pas M.
        propre = self._ticket('S', sans)

        def telephones(user, ticket=None):
            ticket = ticket or self.m
            api = auth(user)
            fiche = api.get(f'{BASE}/tickets/{ticket.pk}/')
            self.assertEqual(fiche.status_code, 200, fiche.content)
            r = api.get(f'{BASE}/tickets/')
            self.assertEqual(r.status_code, 200, r.content)
            rows = r.data['results'] if 'results' in r.data else r.data
            return [fiche.data['client_telephone']] + [
                row['client_telephone'] for row in rows
                if row['id'] == ticket.pk]
        self.assertEqual(telephones(sans, propre), [None, None])
        self.assertEqual(telephones(self.tech), ['0661028028'] * 2)
        self.assertEqual(telephones(self.autre), ['0661028028'] * 2)

    def test_parc_visible_du_chantier_visible(self):
        """ACSV58 (C-ACSV-068, D-ACSV-2) — qui voit un chantier voit tout son
        parc, même créé par un autre ; l'équipement de comptoir du technicien
        reste visible ; le parc d'un chantier hors portée : 0 et 404.
        ROUGE AVANT : 0 équipement du chantier visible."""
        from apps.installations.models import Installation
        from apps.sav.models import Equipement
        from apps.stock.models import Produit
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-ACSV58', prix_achat=0, prix_vente=0)
        ch1 = Installation.objects.create(
            company=self.company, reference='CH-ACSV58-1', client=self.client_obj,
            technicien_responsable=self.tech, created_by=self.autre)
        ch2 = Installation.objects.create(
            company=self.company, reference='CH-ACSV58-2', client=self.client_obj,
            created_by=self.autre)

        def equipement(sn, inst, auteur):
            return Equipement.objects.create(
                company=self.company, produit=produit, installation=inst,
                numero_serie=sn, created_by=auteur)
        e1, e2 = equipement('SN-1', ch1, self.autre), equipement('SN-2', ch1, self.autre)
        comptoir = equipement('SN-C', None, self.tech)
        cache = equipement('SN-X', ch2, self.autre)
        r = self.api.get(f'{BASE}/equipements/?installation={ch1.pk}')
        self.assertEqual(r.status_code, 200, r.content)
        rows = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(sorted(row['id'] for row in rows), sorted([e1.pk, e2.pk]))
        self.assertEqual(self.api.get(f'{BASE}/equipements/{e1.pk}/').status_code, 200)
        self.assertEqual(self.api.get(f'{BASE}/equipements/{comptoir.pk}/').status_code, 200)
        r = self.api.get(f'{BASE}/equipements/?installation={ch2.pk}')
        rows = r.data['results'] if 'results' in r.data else r.data
        self.assertEqual(list(rows), [])
        self.assertEqual(self.api.get(f'{BASE}/equipements/{cache.pk}/').status_code, 404)
