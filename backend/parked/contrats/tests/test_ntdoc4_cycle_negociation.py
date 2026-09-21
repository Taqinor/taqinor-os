"""Tests NTDOC4 — Cycle de négociation (ouverture / clôture).

Critère d'acceptation :
- IMPOSSIBLE de clôturer la négociation avec un commentaire non résolu ;
- la transition est JOURNALISÉE (chatter CONTRAT15) ;
- AUCUNE modification du champ ``statut`` hors machine d'états (la porte
  générique ``changer-statut`` refuse les deux bornes du round).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import machine_etats, services
from apps.contrats.models import (
    Contrat, DocumentContrepartie, PartieContrat,
)

User = get_user_model()

BASE = '/api/django/contrats/contrats/'
S = Contrat.Statut


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CycleNegociationTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc4', 'Négociation')
        self.admin = User.objects.create_user(
            username='ntdoc4-admin', password='x', company=self.co,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Contrat cadre')
        for rang, type_partie in enumerate(['client', 'prestataire']):
            PartieContrat.objects.create(
                company=self.co, contrat=self.contrat,
                type_partie=type_partie, nom=f'Partie {rang}', ordre=rang)
        self.api = auth(self.admin)

    def _depot(self, statut=DocumentContrepartie.Statut.NOUVEAU):
        return DocumentContrepartie.objects.create(
            company=self.co, contrat=self.contrat, fichier_key='k/1.docx',
            nom_fichier='redline.docx', statut=statut)

    # ── Ouverture ──────────────────────────────────────────────────────────

    def test_ouverture_refusee_sans_contrepartie(self):
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/demarrer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('contreparties', resp.data['detail'])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.BROUILLON)

    def test_ouverture_refusee_si_tout_est_deja_traite(self):
        self._depot(statut=DocumentContrepartie.Statut.TRAITE)
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/demarrer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)

    def test_ouverture_avec_contrepartie_en_attente(self):
        self._depot()
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/demarrer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.EN_NEGOCIATION)

    def test_double_ouverture_refusee(self):
        self._depot()
        self.api.post(f'{BASE}{self.contrat.id}/demarrer-negociation/', {},
                      format='json')
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/demarrer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('déjà en négociation', resp.data['detail'])

    # ── Clôture ────────────────────────────────────────────────────────────

    def _ouvrir(self):
        self._depot()
        self.api.post(f'{BASE}{self.contrat.id}/demarrer-negociation/', {},
                      format='json')
        self.contrat.refresh_from_db()

    def test_cloture_impossible_avec_un_commentaire_non_resolu(self):
        """LE critère : un point ouvert bloque la clôture."""
        self._ouvrir()
        services.creer_commentaire_redline(
            self.contrat, contenu='Durée refusée')
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/cloturer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ne sont pas résolus', resp.data['detail'])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.EN_NEGOCIATION)

    def test_cloture_possible_quand_tout_est_resolu(self):
        self._ouvrir()
        commentaire = services.creer_commentaire_redline(
            self.contrat, contenu='Durée refusée')
        services.resoudre_commentaire_redline(commentaire)
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/cloturer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.EN_APPROBATION)

    def test_cloture_marque_les_depots_traites(self):
        self._ouvrir()
        self.api.post(f'{BASE}{self.contrat.id}/cloturer-negociation/', {},
                      format='json')
        depot = DocumentContrepartie.objects.get()
        self.assertEqual(depot.statut, DocumentContrepartie.Statut.TRAITE)

    def test_cloture_hors_negociation_refusee(self):
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/cloturer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('demarrer-negociation', resp.data['detail'])

    def test_cloture_refusee_sans_deux_parties(self):
        """La garde « au moins deux parties » de la machine d'états tient."""
        PartieContrat.objects.filter(contrat=self.contrat).delete()
        self._ouvrir()
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/cloturer-negociation/', {},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('deux parties', resp.data['detail'])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.EN_NEGOCIATION)

    # ── Journalisation & intégrité de la machine d'états ───────────────────

    def test_chaque_etape_est_journalisee(self):
        self._ouvrir()
        self.api.post(f'{BASE}{self.contrat.id}/cloturer-negociation/', {},
                      format='json')
        messages = [
            a.message for a in
            self.contrat.activites.filter(field='statut')
        ]
        self.assertIn('ouverture de la négociation', messages)
        self.assertIn('clôture de la négociation', messages)

    def test_porte_generique_refuse_de_poser_en_negociation(self):
        """Aucune écriture du statut hors des portes dédiées."""
        self._depot()
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/changer-statut/',
            {'statut': S.EN_NEGOCIATION}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('demarrer-negociation', resp.data['detail'])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.BROUILLON)

    def test_porte_generique_refuse_de_cloturer(self):
        self._ouvrir()
        services.creer_commentaire_redline(self.contrat, contenu='Ouvert')
        resp = self.api.post(
            f'{BASE}{self.contrat.id}/changer-statut/',
            {'statut': S.EN_APPROBATION}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('cloturer-negociation', resp.data['detail'])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.EN_NEGOCIATION)

    def test_statut_non_writable_par_patch(self):
        """Le champ ``statut`` n'est jamais piloté par le corps de requête."""
        resp = self.api.patch(
            f'{BASE}{self.contrat.id}/',
            {'statut': S.EN_NEGOCIATION}, format='json')
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, S.BROUILLON, resp.data)


class GrapheNegociationTests(TestCase):
    """Le graphe de la machine d'états couvre le nouveau statut."""

    def test_nouveau_statut_dans_le_graphe(self):
        graphe = machine_etats._transitions()
        self.assertIn(S.EN_NEGOCIATION, graphe)
        self.assertEqual(
            set(graphe[S.EN_NEGOCIATION]),
            {S.EN_APPROBATION, S.BROUILLON, S.RESILIE})
        self.assertIn(S.EN_NEGOCIATION, graphe[S.BROUILLON])

    def test_chemin_direct_brouillon_approbation_preserve(self):
        """Le chemin SANS négociation reste strictement inchangé."""
        self.assertTrue(
            machine_etats.transition_permise(S.BROUILLON, S.EN_APPROBATION))

    def test_abandon_retour_en_brouillon(self):
        self.assertTrue(
            machine_etats.transition_permise(S.EN_NEGOCIATION, S.BROUILLON))
