"""AUD525 — FG233 (ticket SAV depuis le portail) cesse d'être du code mort.

Constat d'audit (le ROUGE figé ici) : le SEUL ViewSet de
``DemandeTicketPortail`` est gardé par ``IsResponsableOrAdmin`` — une garde
INTERNE refusée à tout rôle ``portail_*``. Aucun compte portail réel ne pouvait
donc ouvrir une demande (403 sur POST), et la déflection KB
(``suggestions-kb``/``consulter-article-kb``) héritait de la même garde : elle
n'était jamais exercée par un vrai client.

Le correctif ajoute la surface authentifiée manquante
(``/portail/mes-demandes-sav/…``, garde ``IsPortalClientUser``), société et
client résolus du COMPTE connecté.

Run :
    python manage.py test apps.portail.tests.test_aud525_demandes_sav_client -v2
"""
import itertools

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.kb.models import KbArticle
from apps.portail.models import DemandeTicketPortail
from apps.roles.models import (
    PORTAIL_CLIENT_PERMISSIONS,
    PORTAIL_FOURNISSEUR_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
    ROLE_PORTAIL_FOURNISSEUR,
    Role,
)
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

BASE = '/api/django/portail/mes-demandes-sav/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_client(company, nom='Client'):
    n = next(_seq)
    return Client.objects.create(
        company=company, nom=nom, prenom=f'AUD525-{n}',
        email=f'aud525-{company.id}-{n}@example.invalid')


_PORTAIL = {
    CustomUser.PORTEE_PORTAIL_CLIENT: (
        ROLE_PORTAIL_CLIENT, 'portail_client_id', PORTAIL_CLIENT_PERMISSIONS),
    CustomUser.PORTEE_PORTAIL_FOURNISSEUR: (
        ROLE_PORTAIL_FOURNISSEUR, 'portail_fournisseur_id',
        PORTAIL_FOURNISSEUR_PERMISSIONS),
}


def make_portal_user(company, username, portee, scope_id):
    role_nom, champ, perms = _PORTAIL[portee]
    role, _ = Role.objects.get_or_create(
        company=company, nom=role_nom,
        defaults={'permissions': list(perms), 'est_systeme': True})
    user = CustomUser.objects.create_user(
        username=username, password='motdepasse-test-1234',
        company=company, role=role)
    user.portee = portee
    setattr(user, champ, scope_id)
    user.save()
    return user


class AUD525DemandesSavClientTests(TestCase):
    def setUp(self):
        self.company = make_company('aud525-co', 'AUD525 Société')
        self.client_a = make_client(self.company, 'Alpha')
        self.client_b = make_client(self.company, 'Beta')
        self.user_a = make_portal_user(
            self.company, 'aud525-portail-a',
            CustomUser.PORTEE_PORTAIL_CLIENT, self.client_a.id)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user_a)

    # ── ROUGE — l'ancienne surface reste interdite au client ────────────────

    def test_ancien_viewset_interne_toujours_refuse_au_client(self):
        """C'était l'unique chemin : un compte portail y prend 403 (le ROUGE
        d'origine — il n'est pas « ouvert », il est REMPLACÉ)."""
        resp = self.api.post(
            '/api/django/portail/demandes-ticket-portail/',
            {'sujet': 'Onduleur en défaut'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    # ── La surface client ───────────────────────────────────────────────────

    def test_client_peut_ouvrir_une_demande(self):
        resp = self.api.post(
            BASE, {'sujet': 'Onduleur en défaut',
                   'description': 'Code erreur E07 depuis hier.'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        demande = DemandeTicketPortail.objects.get(pk=resp.data['id'])
        self.assertEqual(demande.statut, DemandeTicketPortail.Statut.SOUMISE)
        # Société ET client viennent du compte, jamais du corps.
        self.assertEqual(demande.company_id, self.company.id)
        self.assertEqual(demande.client_id, self.client_a.id)

    def test_client_ne_peut_pas_usurper_un_autre_client(self):
        resp = self.api.post(
            BASE, {'sujet': 'Usurpation', 'client': self.client_b.id,
                   'company': 999}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        demande = DemandeTicketPortail.objects.get(pk=resp.data['id'])
        self.assertEqual(demande.client_id, self.client_a.id)
        self.assertEqual(demande.company_id, self.company.id)

    def test_sujet_obligatoire(self):
        resp = self.api.post(BASE, {'description': 'sans sujet'},
                             format='json')
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(DemandeTicketPortail.objects.count(), 0)

    def test_chantier_etranger_ignore(self):
        chantier_b = Installation.objects.create(
            company=self.company, client=self.client_b,
            reference='CH-AUD525-B')
        resp = self.api.post(
            BASE, {'sujet': 'Panne', 'chantier': chantier_b.id},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        demande = DemandeTicketPortail.objects.get(pk=resp.data['id'])
        self.assertIsNone(demande.chantier_id)

    def test_liste_bornee_au_client_rattache(self):
        DemandeTicketPortail.objects.create(
            company=self.company, client_id=self.client_a.id, sujet='À moi')
        DemandeTicketPortail.objects.create(
            company=self.company, client_id=self.client_b.id, sujet='Au voisin')
        resp = self.api.get(BASE)
        self.assertEqual(resp.status_code, 200, resp.content)
        sujets = {ligne['sujet'] for ligne in resp.data['results']}
        self.assertEqual(sujets, {'À moi'})

    def test_detail_dun_autre_client_introuvable(self):
        autre = DemandeTicketPortail.objects.create(
            company=self.company, client_id=self.client_b.id, sujet='Voisin')
        resp = self.api.get(f'{BASE}{autre.id}/')
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_compte_fournisseur_refuse(self):
        """Portée EXACTE : un compte portail fournisseur n'est pas un client."""
        fournisseur = make_portal_user(
            self.company, 'aud525-portail-fourn',
            CustomUser.PORTEE_PORTAIL_FOURNISSEUR, 4242)
        api = APIClient()
        api.force_authenticate(user=fournisseur)
        resp = api.post(BASE, {'sujet': 'Panne'}, format='json')
        self.assertEqual(resp.status_code, 403, resp.content)

    # ── Déflection KB, enfin exercée par un vrai client ─────────────────────

    def test_suggestions_kb_servies_au_client(self):
        article = KbArticle.objects.create(
            company=self.company, titre='Onduleur en défaut — que faire ?',
            corps='Vérifiez le code erreur.',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        KbArticle.objects.create(
            company=self.company, titre='Onduleur — note interne',
            statut=KbArticle.Statut.PUBLIE, visible_portail=False)
        resp = self.api.get(f'{BASE}suggestions-kb/?q=onduleur')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(
            {s['id'] for s in resp.data['suggestions']}, {article.id})

    def test_consultation_kb_comptee(self):
        article = KbArticle.objects.create(
            company=self.company, titre='Onduleur en défaut',
            corps='Vérifiez le code erreur.',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        resp = self.api.post(
            f'{BASE}consulter-article-kb/', {'article_id': article.id},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data['enregistre'])
        article.refresh_from_db()
        self.assertEqual(article.consultations_portail_ticket, 1)

    def test_kb_isolee_par_societe(self):
        autre = make_company('aud525-co-b', 'AUD525 B')
        KbArticle.objects.create(
            company=autre, titre='Onduleur autre société',
            statut=KbArticle.Statut.PUBLIE, visible_portail=True)
        resp = self.api.get(f'{BASE}suggestions-kb/?q=onduleur')
        self.assertEqual(resp.data['suggestions'], [])
