"""MRY20 — Combien de fois a-t-on VRAIMENT essayé ?

C'est le chiffre qui dit si un dossier a été assez travaillé pour être classé
— et il alimente la moyenne « tentatives avant abandon » du bilan (MRY21). Il
ne compte donc QUE les tentatives humaines : appel, WhatsApp, e-mail, avec un
auteur. Compter les lignes système (créations, changements d'étape
automatiques, notes du moteur de cadence) le gonflerait jusqu'à le rendre
inutilisable — un lead jamais appelé afficherait « 6 tentatives ».

Il arrive par ANNOTATION, jamais par une requête par lead : la liste et le
kanban affichent 50 cartes, un `SerializerMethodField` y serait un N+1 franc.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity
from apps.parametres.models import CompanyProfile

User = get_user_model()


def _company(slug):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    CompanyProfile.objects.get_or_create(company=company)
    return company


class NbTentativesTests(TestCase):
    def setUp(self):
        self.company = _company('mry20')
        self.acteur = User.objects.create_user(
            username='mry20-u', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', owner=self.acteur)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')

    def _activite(self, kind, user=True, **kw):
        return LeadActivity.objects.create(
            company=self.company, lead=self.lead,
            user=self.acteur if user else None, kind=kind, **kw)

    def _ligne_liste(self):
        resp = self.api.get('/api/django/crm/leads/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = (resp.data['results']
                if isinstance(resp.data, dict) else resp.data)
        return next(r for r in rows if r['id'] == self.lead.pk)

    def test_trois_appels_deux_whatsapp_et_une_note_font_cinq(self):
        for _ in range(3):
            self._activite(LeadActivity.Kind.APPEL)
        for _ in range(2):
            self._activite(LeadActivity.Kind.WHATSAPP)
        self._activite(LeadActivity.Kind.NOTE, body='Compte rendu')
        self.assertEqual(self._ligne_liste()['nb_tentatives'], 5)

    def test_lemail_compte_aussi(self):
        self._activite(LeadActivity.Kind.EMAIL)
        self.assertEqual(self._ligne_liste()['nb_tentatives'], 1)

    def test_une_activite_systeme_ne_compte_pas(self):
        """Un appel journalisé par le moteur (`user=None`) n'est pas une
        tentative de Meryem : le compter mentirait sur l'effort réel."""
        self._activite(LeadActivity.Kind.APPEL, user=False)
        self.assertEqual(self._ligne_liste()['nb_tentatives'], 0)

    def test_les_lignes_de_creation_et_de_modification_ne_comptent_pas(self):
        self._activite(LeadActivity.Kind.CREATION, body='Lead créé')
        self._activite(LeadActivity.Kind.MODIFICATION, field='stage')
        self.assertEqual(self._ligne_liste()['nb_tentatives'], 0)

    def test_zero_par_defaut_jamais_null(self):
        """Un trou dans une carte se lit comme un bug ; 0 se lit comme un
        fait."""
        ligne = self._ligne_liste()
        self.assertEqual(ligne['nb_tentatives'], 0)
        self.assertIsNotNone(ligne['nb_tentatives'])

    def test_le_detail_est_coherent_avec_la_liste(self):
        for _ in range(2):
            self._activite(LeadActivity.Kind.APPEL)
        resp = self.api.get(f'/api/django/crm/leads/{self.lead.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['nb_tentatives'],
                         self._ligne_liste()['nb_tentatives'])

    def test_les_activites_dun_autre_lead_ne_comptent_pas(self):
        autre = Lead.objects.create(
            company=self.company, nom='Autre', owner=self.acteur)
        LeadActivity.objects.create(
            company=self.company, lead=autre, user=self.acteur,
            kind=LeadActivity.Kind.APPEL)
        self.assertEqual(self._ligne_liste()['nb_tentatives'], 0)

    def test_le_compteur_ne_coute_pas_une_requete_par_lead(self):
        """L'annotation existe précisément pour que 50 cartes ne coûtent pas
        50 requêtes. On ne fige AUCUN budget absolu (il dépend d'autres
        champs) : on vérifie que le coût du listing NE GRIMPE PAS quand on
        ajoute des leads — la signature exacte d'un N+1."""
        self._activite(LeadActivity.Kind.APPEL)
        avec_un = self._cout_listing()
        for i in range(5):
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead {i}', owner=self.acteur)
            LeadActivity.objects.create(
                company=self.company, lead=lead, user=self.acteur,
                kind=LeadActivity.Kind.APPEL)
        self.assertEqual(self._cout_listing(), avec_un)

    def _cout_listing(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as ctx:
            self.api.get('/api/django/crm/leads/')
        return len(ctx)
