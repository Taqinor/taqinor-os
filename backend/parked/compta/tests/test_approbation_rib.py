"""Tests XACC24 — Approbation des changements de coordonnées bancaires
(compta) + validation RIB sur les comptes de trésorerie.

Couvre : un changement de RIB fournisseur non approuvé n'apparaît pas dans
le fichier de virement (le payment run continue d'utiliser l'ancien RIB),
l'approbation admin le bascule, et un RIB de compte de trésorerie à clé
fausse est signalé en warning (jamais un blocage).

PACT160 ajoute la couverture API (``DemandeApprobationRibViewSet``) : la
surface était construite côté service mais totalement inatteignable (aucune
route, aucun sérialiseur, aucun écran) avant cette tâche.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import CompteTresorerie, DemandeApprobationRib

User = get_user_model()

RIB_VALIDE_ANCIEN = '123456789012345678901213'
RIB_VALIDE_NOUVEAU = '070001234598765432109842'
RIB_INVALIDE = '070001234598765432109999'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class DemandeApprobationRibTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc24-svc', 'XACC24 Svc')

    def test_changement_non_approuve_paiement_utilise_ancien_rib(self):
        services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        coord = services._coordonnees_fournisseur(self.co, 42)
        # Pas de fournisseur stock réel ici (id=42 inconnu) mais une demande
        # non approuvée existe : le payment run doit quand même utiliser
        # l'ANCIEN RIB (jamais le nouveau tant qu'il n'est pas approuvé).
        self.assertEqual(coord['rib'], RIB_VALIDE_ANCIEN)

    def test_rib_actif_avant_approbation_est_ancien(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        self.assertEqual(demande.rib_actif, RIB_VALIDE_ANCIEN)

    def test_approbation_bascule_le_rib_actif(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        services.approuver_demande_rib(demande, decideur=None, commentaire='OK')
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.APPROUVEE)
        self.assertEqual(demande.rib_actif, RIB_VALIDE_NOUVEAU)

    def test_refus_conserve_ancien_rib_definitivement(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        services.refuser_demande_rib(demande, decideur=None, commentaire='Non')
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.REFUSEE)
        self.assertEqual(demande.rib_actif, RIB_VALIDE_ANCIEN)

    def test_idempotent_decision_deja_prise(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=42, fournisseur_nom='ACME',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        services.approuver_demande_rib(demande, decideur=None)
        demande.refresh_from_db()
        # Un refus après approbation ne change rien (déjà décidée).
        services.refuser_demande_rib(demande, decideur=None)
        demande.refresh_from_db()
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.APPROUVEE)

    def test_diagnostic_rib_signale_cle_fausse(self):
        diagnostic = services.diagnostic_rib(RIB_INVALIDE)
        self.assertFalse(diagnostic['valide'])


class CompteTresorerieRibTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc24-treso', 'XACC24 Treso')
        self.compte_comptable = services._assurer_compte(self.co, '5141')

    def test_rib_invalide_signale_en_warning(self):
        CompteTresorerie.objects.create(
            company=self.co, libelle='Compte BP',
            compte_comptable=self.compte_comptable, rib=RIB_INVALIDE,
            solde_initial=Decimal('0'))
        invalides = selectors.comptes_tresorerie_rib_invalides(self.co)
        self.assertEqual(len(invalides), 1)
        self.assertEqual(invalides[0]['rib'], RIB_INVALIDE)

    def test_rib_valide_non_signale(self):
        CompteTresorerie.objects.create(
            company=self.co, libelle='Compte BP',
            compte_comptable=self.compte_comptable, rib=RIB_VALIDE_ANCIEN,
            solde_initial=Decimal('0'))
        invalides = selectors.comptes_tresorerie_rib_invalides(self.co)
        self.assertEqual(invalides, [])

    def test_rib_vide_jamais_signale(self):
        CompteTresorerie.objects.create(
            company=self.co, libelle='Compte sans RIB',
            compte_comptable=self.compte_comptable, rib='',
            solde_initial=Decimal('0'))
        invalides = selectors.comptes_tresorerie_rib_invalides(self.co)
        self.assertEqual(invalides, [])

    def test_saisie_historique_jamais_bloquee(self):
        # Créer un compte avec un RIB invalide ne lève AUCUNE exception —
        # seul le rapport signale l'anomalie, jamais un blocage de saisie.
        compte = CompteTresorerie.objects.create(
            company=self.co, libelle='Ancien compte', rib=RIB_INVALIDE,
            compte_comptable=self.compte_comptable, solde_initial=Decimal('0'))
        self.assertEqual(compte.rib, RIB_INVALIDE)


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


# ── PACT160 — API de la file d'approbation RIB (XACC24) ────────────────────

class DemandeApprobationRibApiTests(TestCase):
    def setUp(self):
        self.co = make_company('pact160', 'PACT160 Co')
        self.autre_co = make_company('pact160-autre', 'PACT160 Autre')
        self.user = make_user(self.co, 'pact160-user')

    def test_creation_pose_company_et_demandeur_serveur(self):
        api = auth(self.user)
        resp = api.post('/api/django/compta/approbations-rib/', {
            'fournisseur_id': 501, 'fournisseur_nom': 'ACME',
            'ancien_rib': RIB_VALIDE_ANCIEN, 'nouveau_rib': RIB_VALIDE_NOUVEAU,
            'company': 99999,  # doit être ignoré
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        demande = DemandeApprobationRib.objects.get(id=resp.data['id'])
        self.assertEqual(demande.company_id, self.co.id)
        self.assertEqual(demande.demandeur_id, self.user.id)
        self.assertEqual(demande.statut, DemandeApprobationRib.Statut.EN_ATTENTE)

    def test_approuver_bascule_le_statut_et_trace_le_decideur(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=502, fournisseur_nom='Fournisseur X',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/approbations-rib/{demande.id}/approuver/',
            {'commentaire': 'RIB vérifié par téléphone.'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], DemandeApprobationRib.Statut.APPROUVEE)
        self.assertEqual(resp.data['rib_actif'], RIB_VALIDE_NOUVEAU)
        demande.refresh_from_db()
        self.assertEqual(demande.decideur_id, self.user.id)
        self.assertEqual(demande.commentaire_decision, 'RIB vérifié par téléphone.')
        self.assertIsNotNone(demande.date_decision)

    def test_refuser_bascule_le_statut(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=503, fournisseur_nom='Fournisseur Y',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        api = auth(self.user)
        resp = api.post(
            f'/api/django/compta/approbations-rib/{demande.id}/refuser/',
            {'commentaire': 'RIB non confirmé.'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['statut'], DemandeApprobationRib.Statut.REFUSEE)
        self.assertEqual(resp.data['rib_actif'], RIB_VALIDE_ANCIEN)

    def test_decision_idempotente_via_api(self):
        demande = services.demander_changement_rib(
            self.co, fournisseur_id=504, fournisseur_nom='Fournisseur Z',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        api = auth(self.user)
        api.post(f'/api/django/compta/approbations-rib/{demande.id}/approuver/',
                 {}, format='json')
        autre_user = make_user(self.co, 'pact160-user2')
        api2 = auth(autre_user)
        resp = api2.post(
            f'/api/django/compta/approbations-rib/{demande.id}/refuser/',
            {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Déjà décidée : le second appel (refus) ne change rien.
        self.assertEqual(resp.data['statut'], DemandeApprobationRib.Statut.APPROUVEE)
        demande.refresh_from_db()
        self.assertEqual(demande.decideur_id, self.user.id)

    def test_scopee_par_societe(self):
        demande_autre = services.demander_changement_rib(
            self.autre_co, fournisseur_id=505, fournisseur_nom='Hors société',
            ancien_rib=RIB_VALIDE_ANCIEN, nouveau_rib=RIB_VALIDE_NOUVEAU)
        api = auth(self.user)
        resp = api.get('/api/django/compta/approbations-rib/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
        resp = api.post(
            f'/api/django/compta/approbations-rib/{demande_autre.id}/approuver/',
            {}, format='json')
        self.assertEqual(resp.status_code, 404)
