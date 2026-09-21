"""Tests NTDOC3 — Commentaires par clause / par ligne sur le diff de négociation.

Critère d'acceptation :
- un commentaire posé sur une ligne modifiée reste VISIBLE tant que non résolu ;
- la résolution trace QUI et QUAND.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import (
    Clause, CommentaireRedline, Contrat, DocumentContrepartie,
)

User = get_user_model()

BASE = '/api/django/contrats/contrats/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def rows(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data \
        else data


class CommentaireRedlineApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc3', 'Redline')
        self.admin = User.objects.create_user(
            username='ntdoc3-admin', password='x', company=self.co,
            role_legacy='admin')
        self.autre_user = User.objects.create_user(
            username='ntdoc3-resolveur', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Contrat cadre')
        self.depot = DocumentContrepartie.objects.create(
            company=self.co, contrat=self.contrat,
            fichier_key='k/1.docx', nom_fichier='redline.docx')
        self.url = f'{BASE}{self.contrat.id}/commentaires-redline/'

    def _poser(self, api=None, **extra):
        api = api or auth(self.admin)
        payload = {
            'contenu': 'La durée de 24 mois est refusée.',
            'document_contrepartie': self.depot.id,
            'ligne_reference': 4,
            'extrait_ligne': '+Article 2 — Durée de vingt-quatre mois.',
        }
        payload.update(extra)
        return api.post(self.url, payload, format='json')

    def test_creation_pose_auteur_et_societe_cote_serveur(self):
        resp = self._poser()
        self.assertEqual(resp.status_code, 201, resp.data)
        com = CommentaireRedline.objects.get(id=resp.data['id'])
        self.assertEqual(com.company_id, self.co.id)
        self.assertEqual(com.contrat_id, self.contrat.id)
        self.assertEqual(com.auteur_id, self.admin.id)
        self.assertFalse(com.resolu)
        self.assertEqual(com.ligne_reference, 4)

    def test_company_du_corps_est_ignoree(self):
        """La société n'est JAMAIS lue du corps de requête."""
        autre = make_company('ntdoc3-pirate', 'Pirate')
        resp = self._poser(company=autre.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        com = CommentaireRedline.objects.get(id=resp.data['id'])
        self.assertEqual(com.company_id, self.co.id)

    def test_commentaire_reste_visible_tant_que_non_resolu(self):
        """Le critère : visible tant que non résolu, puis filtrable."""
        self._poser()
        api = auth(self.admin)
        ouverts = rows(api.get(f'{self.url}?resolu=0'))
        self.assertEqual(len(ouverts), 1)
        self.assertFalse(ouverts[0]['resolu'])

        com = CommentaireRedline.objects.get()
        resp = api.post(f'{self.url}{com.id}/resoudre/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(rows(api.get(f'{self.url}?resolu=0'))), 0)
        self.assertEqual(len(rows(api.get(f'{self.url}?resolu=1'))), 1)
        # Toujours en base : la résolution n'efface rien.
        self.assertEqual(CommentaireRedline.objects.count(), 1)

    def test_resolution_trace_qui_et_quand(self):
        self._poser()
        com = CommentaireRedline.objects.get()
        api = auth(self.autre_user)
        resp = api.post(f'{self.url}{com.id}/resoudre/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        com.refresh_from_db()
        self.assertTrue(com.resolu)
        self.assertEqual(com.resolu_par_id, self.autre_user.id)
        self.assertIsNotNone(com.date_resolution)
        self.assertEqual(resp.data['resolu_par_nom'], 'ntdoc3-resolveur')

    def test_resolution_idempotente(self):
        self._poser()
        com = CommentaireRedline.objects.get()
        api = auth(self.admin)
        api.post(f'{self.url}{com.id}/resoudre/', {}, format='json')
        com.refresh_from_db()
        premiere = com.date_resolution
        api.post(f'{self.url}{com.id}/resoudre/', {}, format='json')
        com.refresh_from_db()
        self.assertEqual(com.date_resolution, premiere)

    def test_rouvrir_efface_la_trace_de_resolution(self):
        self._poser()
        com = CommentaireRedline.objects.get()
        api = auth(self.admin)
        api.post(f'{self.url}{com.id}/resoudre/', {}, format='json')
        resp = api.post(f'{self.url}{com.id}/rouvrir/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        com.refresh_from_db()
        self.assertFalse(com.resolu)
        self.assertIsNone(com.resolu_par_id)
        self.assertIsNone(com.date_resolution)

    def test_edition_et_suppression(self):
        self._poser()
        com = CommentaireRedline.objects.get()
        api = auth(self.admin)
        resp = api.patch(
            f'{self.url}{com.id}/', {'contenu': 'Corrigé'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        com.refresh_from_db()
        self.assertEqual(com.contenu, 'Corrigé')

        resp = api.delete(f'{self.url}{com.id}/')
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(CommentaireRedline.objects.count(), 0)

    def test_contenu_vide_refuse(self):
        resp = self._poser(contenu='   ')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('contenu', resp.data)

    def test_depot_d_un_autre_contrat_404(self):
        autre = Contrat.objects.create(company=self.co, objet='Autre')
        autre_depot = DocumentContrepartie.objects.create(
            company=self.co, contrat=autre, fichier_key='k/2.pdf',
            nom_fichier='x.pdf')
        resp = self._poser(document_contrepartie=autre_depot.id)
        self.assertEqual(resp.status_code, 404)
        self.assertIn('document_contrepartie', resp.data['detail'])

    def test_clause_d_une_autre_societe_404(self):
        autre_co = make_company('ntdoc3-b', 'B')
        clause = Clause.objects.create(
            company=autre_co, titre='Responsabilité', corps='…')
        resp = self._poser(clause=clause.id)
        self.assertEqual(resp.status_code, 404)
        self.assertIn('clause', resp.data['detail'])

    def test_commentaire_sur_une_clause_de_la_bibliotheque(self):
        clause = Clause.objects.create(
            company=self.co, titre='Responsabilité', corps='…')
        resp = self._poser(clause=clause.id, document_contrepartie=None)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['clause'], clause.id)

    def test_chatter_journalise_commentaire_et_resolution(self):
        self._poser()
        com = CommentaireRedline.objects.get()
        auth(self.admin).post(
            f'{self.url}{com.id}/resoudre/', {}, format='json')
        journal = list(self.contrat.activites.filter(field='redline'))
        self.assertEqual(len(journal), 2)


class CommentaireRedlineIsolationTests(TestCase):
    def setUp(self):
        self.co_a = make_company('ntdoc3-iso-a', 'A')
        self.co_b = make_company('ntdoc3-iso-b', 'B')
        self.user_b = User.objects.create_user(
            username='ntdoc3-iso-b-admin', password='x', company=self.co_b,
            role_legacy='admin')
        self.contrat_a = Contrat.objects.create(
            company=self.co_a, objet='A')

    def test_contrat_d_une_autre_societe_404(self):
        api = auth(self.user_b)
        resp = api.get(
            f'{BASE}{self.contrat_a.id}/commentaires-redline/')
        self.assertEqual(resp.status_code, 404)


class CommentaireRedlineSelectorTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc3-sel', 'Sel')
        self.contrat = Contrat.objects.create(company=self.co, objet='S')

    def test_selecteur_ouverts(self):
        services.creer_commentaire_redline(self.contrat, contenu='ouvert')
        resolu = services.creer_commentaire_redline(
            self.contrat, contenu='à résoudre')
        services.resoudre_commentaire_redline(resolu)
        ouverts = list(selectors.commentaires_redline_ouverts(self.contrat))
        self.assertEqual(len(ouverts), 1)
        self.assertEqual(ouverts[0].contenu, 'ouvert')

    def test_service_refuse_contenu_vide(self):
        with self.assertRaises(services.CommentaireRedlineError) as ctx:
            services.creer_commentaire_redline(self.contrat, contenu='')
        self.assertIn('contenu', str(ctx.exception))
