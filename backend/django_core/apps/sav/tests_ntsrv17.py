"""NTSRV17 — Détection automatique de tickets candidats à un Problème.

Critère d'acceptation : 3 tickets sur le MÊME produit + la MÊME cause en
30 jours apparaissent GROUPÉS dans la suggestion — et aucun ``Probleme``
n'est jamais créé automatiquement.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv17 -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.sav.models import (
    CauseDefaillance, Equipement, Probleme, ProblemeIncident, Ticket,
)
from apps.sav.selectors import tickets_candidats_probleme
from apps.stock.models import Produit

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class NTSRV17CandidatsProblemeTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv17', defaults={'nom': 'Sav Co NTSRV17'})
        self.admin = User.objects.create_user(
            username='ntsrv17_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV17')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur X', sku='NTSRV17-ONDX',
            prix_achat=500, prix_vente=900)
        self.autre_produit = Produit.objects.create(
            company=self.company, nom='Onduleur Y', sku='NTSRV17-ONDY',
            prix_achat=500, prix_vente=900)
        self.cause = CauseDefaillance.objects.create(
            company=self.company, nom='Surchauffe')
        self.autre_cause = CauseDefaillance.objects.create(
            company=self.company, nom='Usure normale')
        self.compteur = 0

    def _ticket(self, produit=None, cause=None, statut=None):
        self.compteur += 1
        equipement = Equipement.objects.create(
            company=self.company, produit=produit or self.produit,
            numero_serie=f'NTSRV17-SN-{self.compteur}')
        return Ticket.objects.create(
            company=self.company, reference=f'SAV-NTSRV17-{self.compteur}',
            client=self.client_obj, equipement=equipement,
            cause=cause if cause is not None else self.cause,
            statut=statut or Ticket.Statut.EN_COURS,
            date_ouverture=timezone.localdate())

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_trois_tickets_meme_produit_meme_cause_sont_groupes(self):
        tickets = [self._ticket() for _ in range(3)]
        groupes = tickets_candidats_probleme(self.company)
        self.assertEqual(len(groupes), 1)
        groupe = groupes[0]
        self.assertEqual(groupe['nb_tickets'], 3)
        self.assertEqual(groupe['produit_nom'], 'Onduleur X')
        self.assertEqual(groupe['cause_libelle'], 'Surchauffe')
        self.assertEqual(
            {ligne['reference'] for ligne in groupe['tickets']},
            {t.reference for t in tickets})

    def test_titre_suggere_reprend_equipement_et_cause(self):
        for _ in range(3):
            self._ticket()
        groupe = tickets_candidats_probleme(self.company)[0]
        self.assertEqual(groupe['titre_suggere'], 'Onduleur X — Surchauffe')

    def test_deux_occurrences_sous_le_seuil_ne_sont_pas_proposees(self):
        self._ticket()
        self._ticket()
        self.assertEqual(tickets_candidats_probleme(self.company), [])

    def test_cause_differente_ne_groupe_pas(self):
        self._ticket()
        self._ticket()
        self._ticket(cause=self.autre_cause)
        self.assertEqual(tickets_candidats_probleme(self.company), [])

    def test_produit_different_ne_groupe_pas(self):
        self._ticket()
        self._ticket()
        self._ticket(produit=self.autre_produit)
        self.assertEqual(tickets_candidats_probleme(self.company), [])

    # ── Exclusions ───────────────────────────────────────────────────────
    def test_ticket_sans_cause_jamais_groupe(self):
        for _ in range(3):
            self._ticket(cause=None)
        self.assertEqual(tickets_candidats_probleme(self.company), [])

    def test_ticket_sans_equipement_jamais_groupe(self):
        for index in range(3):
            Ticket.objects.create(
                company=self.company, reference=f'SAV-NTSRV17-NOEQ-{index}',
                client=self.client_obj, cause=self.cause,
                statut=Ticket.Statut.EN_COURS)
        self.assertEqual(tickets_candidats_probleme(self.company), [])

    def test_ticket_clos_ou_annule_hors_regroupement(self):
        self._ticket()
        self._ticket()
        clos = self._ticket()
        clos.statut = Ticket.Statut.CLOTURE
        clos.save(update_fields=['statut'])
        self.assertEqual(tickets_candidats_probleme(self.company), [])

    def test_ticket_deja_rattache_a_un_probleme_est_exclu(self):
        tickets = [self._ticket() for _ in range(3)]
        probleme = Probleme.objects.create(
            company=self.company, reference='PRB-NTSRV17-0001',
            titre='Déjà traité')
        ProblemeIncident.objects.create(
            company=self.company, probleme=probleme, ticket=tickets[0])
        self.assertEqual(tickets_candidats_probleme(self.company), [])

    def test_hors_fenetre_exclu(self):
        for _ in range(3):
            ticket = self._ticket()
            Ticket.objects.filter(pk=ticket.pk).update(
                date_creation=timezone.now() - timedelta(days=90))
        self.assertEqual(tickets_candidats_probleme(self.company), [])
        # …mais une fenêtre plus large les retrouve.
        self.assertEqual(
            tickets_candidats_probleme(self.company, 180)[0]['nb_tickets'], 3)

    def test_autre_societe_jamais_melangee(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv17-b', defaults={'nom': 'Autre NTSRV17'})
        for _ in range(3):
            self._ticket()
        self.assertEqual(tickets_candidats_probleme(autre), [])

    # ── AUCUNE création automatique ──────────────────────────────────────
    def test_le_selecteur_ne_cree_jamais_de_probleme(self):
        for _ in range(3):
            self._ticket()
        avant = Probleme.objects.count()
        tickets_candidats_probleme(self.company)
        self.assertEqual(Probleme.objects.count(), avant)

    # ── Endpoint ─────────────────────────────────────────────────────────
    def test_endpoint_regroupements_suggeres(self):
        for _ in range(3):
            self._ticket()
        resp = self.api.get(
            '/api/django/sav/problemes/regroupements-suggeres/')
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['fenetre_jours'], 30)
        self.assertEqual(data['seuil'], 3)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['nb_tickets'], 3)

    def test_endpoint_fenetre_invalide_nomme_le_champ(self):
        resp = self.api.get(
            '/api/django/sav/problemes/regroupements-suggeres/'
            '?fenetre_jours=trente')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('fenetre_jours', resp.json())

    def test_endpoint_ne_cree_rien(self):
        for _ in range(3):
            self._ticket()
        self.api.get('/api/django/sav/problemes/regroupements-suggeres/')
        self.assertEqual(Probleme.objects.count(), 0)
        self.assertEqual(ProblemeIncident.objects.count(), 0)
