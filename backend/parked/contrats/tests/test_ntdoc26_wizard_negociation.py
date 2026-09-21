"""Tests NTDOC26 — Wizard guidé « Ouvrir une négociation » (3 étapes fixes).

Critère d'acceptation :
- l'étape 3 est INDISPONIBLE tant que l'étape 1 n'a pas de contrepartie
  déposée ;
- l'appel renvoie TOUJOURS les 3 étapes avec leur statut RÉEL recalculé à
  chaque requête (jamais de statut caché en base).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import Contrat, DocumentContrepartie

User = get_user_model()

BASE = '/api/django/contrats/contrats/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class WizardNegociationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc26', 'Wizard')
        self.admin = User.objects.create_user(
            username='ntdoc26-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(company=self.co, objet='C')

    def _etapes(self):
        return selectors.etapes_wizard_negociation(self.contrat)

    def _depot(self, statut=DocumentContrepartie.Statut.NOUVEAU):
        return DocumentContrepartie.objects.create(
            company=self.co, contrat=self.contrat,
            fichier_key='k/1.docx', nom_fichier='r.docx', statut=statut)

    def test_toujours_trois_etapes_dans_l_ordre(self):
        etapes = self._etapes()
        self.assertEqual([e['numero'] for e in etapes], [1, 2, 3])
        self.assertEqual(
            [e['cle'] for e in etapes],
            ['deposer_contrepartie', 'comparer_annoter', 'cloturer'])

    def test_etape3_indisponible_sans_contrepartie(self):
        """Le critère : pas de dépôt → étape 3 indisponible."""
        etapes = self._etapes()
        self.assertFalse(etapes[0]['complete'])
        self.assertFalse(etapes[1]['disponible'])
        self.assertFalse(etapes[2]['disponible'])
        self.assertIn('étape 1', etapes[2]['detail'])

    def test_depot_debloque_les_etapes_2_et_3(self):
        self._depot()
        etapes = self._etapes()
        self.assertTrue(etapes[0]['complete'])
        self.assertTrue(etapes[1]['disponible'])
        self.assertTrue(etapes[2]['disponible'])

    def test_commentaire_ouvert_rebloque_l_etape3(self):
        self._depot()
        services.creer_commentaire_redline(
            self.contrat, contenu='Durée refusée')
        etapes = self._etapes()
        self.assertTrue(etapes[1]['complete'])
        self.assertFalse(etapes[2]['disponible'])
        self.assertIn('ne sont pas résolus', etapes[2]['detail'])

    def test_etape3_complete_quand_tout_est_resolu_et_traite(self):
        depot = self._depot()
        commentaire = services.creer_commentaire_redline(
            self.contrat, contenu='Durée refusée')
        services.resoudre_commentaire_redline(commentaire)
        depot.statut = DocumentContrepartie.Statut.TRAITE
        depot.save(update_fields=['statut'])
        etapes = self._etapes()
        self.assertTrue(etapes[2]['disponible'])
        self.assertTrue(etapes[2]['complete'])

    def test_statut_recalcule_jamais_stocke(self):
        """Rouvrir un commentaire refait basculer l'étape 3 — pur recalcul."""
        depot = self._depot(statut=DocumentContrepartie.Statut.TRAITE)
        commentaire = services.creer_commentaire_redline(
            self.contrat, contenu='Point ouvert')
        services.resoudre_commentaire_redline(commentaire)
        self.assertTrue(self._etapes()[2]['complete'])
        services.rouvrir_commentaire_redline(commentaire)
        self.assertFalse(self._etapes()[2]['disponible'])
        self.assertFalse(self._etapes()[2]['complete'])
        # Aucun champ de wizard n'existe sur le dépôt/contrat.
        depot.refresh_from_db()
        self.assertFalse(hasattr(depot, 'etape_wizard'))

    def test_depot_archive_ne_compte_pas(self):
        depot = self._depot()
        depot.archiver()
        etapes = self._etapes()
        self.assertFalse(etapes[0]['complete'])
        self.assertFalse(etapes[2]['disponible'])


class WizardNegociationApiTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc26-api', 'API')
        self.admin = User.objects.create_user(
            username='ntdoc26-api-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(company=self.co, objet='C')

    def test_endpoint_renvoie_les_trois_etapes(self):
        api = auth(self.admin)
        resp = api.get(f'{BASE}{self.contrat.id}/wizard-negociation/etapes/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['etapes']), 3)
        self.assertFalse(resp.data['etapes'][2]['disponible'])

    def test_contrat_d_une_autre_societe_404(self):
        autre = make_company('ntdoc26-api-b', 'B')
        user_b = User.objects.create_user(
            username='ntdoc26-api-b-admin', password='x', company=autre,
            role_legacy='admin')
        resp = auth(user_b).get(
            f'{BASE}{self.contrat.id}/wizard-negociation/etapes/')
        self.assertEqual(resp.status_code, 404)
