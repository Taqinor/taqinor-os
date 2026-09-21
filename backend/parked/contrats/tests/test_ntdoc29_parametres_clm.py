"""Tests NTDOC29 — Réglages CLM par société.

Critère d'acceptation :
- désactiver ``resolution_commentaires_obligatoire`` permet de clôturer une
  négociation AVEC des commentaires non résolus ;
- la valeur par défaut reproduit le comportement STRICT de NTDOC4.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import machine_etats, selectors, services
from apps.contrats.models import (
    CommentaireRedline, Contrat, DocumentContrepartie, ParametresCLM,
    PartieContrat,
)

User = get_user_model()

BASE = '/api/django/contrats/parametres-clm/'
COURANT = BASE + 'courant/'
CONTRATS = '/api/django/contrats/contrats/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ParametresCLMBase(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc29', 'Réglages CLM')
        self.admin = User.objects.create_user(
            username='ntdoc29-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.admin)

    def contrat_deux_parties(self, objet='Contrat cadre',
                             statut=Contrat.Statut.BROUILLON):
        contrat = Contrat.objects.create(
            company=self.co, objet=objet, statut=statut)
        for rang, type_partie in enumerate(['client', 'prestataire']):
            PartieContrat.objects.create(
                company=self.co, contrat=contrat, type_partie=type_partie,
                nom=f'Partie {rang}', ordre=rang)
        return contrat


class DefautsTests(ParametresCLMBase):
    """Les défauts reproduisent le comportement d'avant, à l'identique."""

    def test_lecture_pure_sans_ligne_ne_cree_rien(self):
        reglages = selectors.reglages_clm(self.co)
        self.assertTrue(reglages.resolution_commentaires_obligatoire)
        self.assertFalse(reglages.negociation_obligatoire_avant_signature)
        self.assertFalse(reglages.parapheur_notification_quotidienne)
        self.assertEqual(
            reglages.duree_defaut_expiration_salle_donnees_jours, 30)
        # AUCUNE ligne créée : une garde ne doit pas écrire en passant.
        self.assertEqual(
            ParametresCLM.objects.filter(company=self.co).count(), 0)

    def test_raccourci_brouillon_vers_approbation_reste_ouvert(self):
        contrat = self.contrat_deux_parties()
        services.changer_statut(contrat, Contrat.Statut.EN_APPROBATION)
        self.assertEqual(contrat.statut, Contrat.Statut.EN_APPROBATION)


class ResolutionCommentairesTests(ParametresCLMBase):
    """La garde NTDOC4, désormais réglable."""

    def setUp(self):
        super().setUp()
        self.contrat = self.contrat_deux_parties('Négociation')
        DocumentContrepartie.objects.create(
            company=self.co, contrat=self.contrat,
            fichier_key='k/ntdoc29.docx', nom_fichier='redline.docx')
        services.demarrer_negociation(self.contrat, user=self.admin)
        self.commentaire = CommentaireRedline.objects.create(
            company=self.co, contrat=self.contrat,
            contenu='Le plafond de responsabilité est trop bas.')

    def test_defaut_strict_refuse_la_cloture(self):
        with self.assertRaises(services.NegociationError):
            services.cloturer_negociation(self.contrat, user=self.admin)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, Contrat.Statut.EN_NEGOCIATION)

    def test_assoupli_autorise_la_cloture_avec_un_point_ouvert(self):
        ParametresCLM.objects.create(
            company=self.co, resolution_commentaires_obligatoire=False)
        services.cloturer_negociation(self.contrat, user=self.admin)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, Contrat.Statut.EN_APPROBATION)
        # Le commentaire reste OUVERT : on assouplit la garde, on ne
        # referme pas les points à la place de l'utilisateur.
        self.commentaire.refresh_from_db()
        self.assertFalse(self.commentaire.resolu)

    def test_assouplissement_trace_au_chatter(self):
        ParametresCLM.objects.create(
            company=self.co, resolution_commentaires_obligatoire=False)
        services.cloturer_negociation(self.contrat, user=self.admin)
        messages = [
            entree.message
            for entree in self.contrat.activites.filter(field='statut')]
        self.assertTrue(
            any('encore ouvert' in (m or '') for m in messages), messages)

    def test_reglage_dune_autre_societe_ne_sapplique_pas(self):
        autre_co = make_company('ntdoc29-autre', 'Autre CLM')
        ParametresCLM.objects.create(
            company=autre_co, resolution_commentaires_obligatoire=False)
        with self.assertRaises(services.NegociationError):
            services.cloturer_negociation(self.contrat, user=self.admin)


class NegociationObligatoireTests(ParametresCLMBase):
    """Le raccourci brouillon → approbation, fermable par réglage."""

    def setUp(self):
        super().setUp()
        ParametresCLM.objects.create(
            company=self.co, negociation_obligatoire_avant_signature=True)
        self.contrat = self.contrat_deux_parties('Sans négociation')

    def test_raccourci_refuse_quand_la_negociation_est_obligatoire(self):
        with self.assertRaises(machine_etats.TransitionInterdite):
            services.changer_statut(
                self.contrat, Contrat.Statut.EN_APPROBATION)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.statut, Contrat.Statut.BROUILLON)

    def test_le_chemin_par_la_negociation_reste_ouvert(self):
        services.changer_statut(
            self.contrat, Contrat.Statut.EN_NEGOCIATION)
        services.changer_statut(
            self.contrat, Contrat.Statut.EN_APPROBATION)
        self.assertEqual(self.contrat.statut, Contrat.Statut.EN_APPROBATION)

    def test_porte_generique_changer_statut_refuse_aussi(self):
        resp = self.api.post(
            f'{CONTRATS}{self.contrat.id}/changer-statut/',
            {'statut': Contrat.Statut.EN_APPROBATION}, format='json')
        self.assertEqual(resp.status_code, 400)


class EndpointTests(ParametresCLMBase):
    """Le singleton, en lecture/écriture."""

    def test_get_courant_cree_le_singleton_avec_les_defauts(self):
        resp = self.api.get(COURANT)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['resolution_commentaires_obligatoire'])
        self.assertFalse(resp.data['negociation_obligatoire_avant_signature'])
        self.assertEqual(
            ParametresCLM.objects.filter(company=self.co).count(), 1)
        # Idempotent : un second GET ne crée pas de doublon.
        self.api.get(COURANT)
        self.assertEqual(
            ParametresCLM.objects.filter(company=self.co).count(), 1)

    def test_patch_courant_enregistre(self):
        resp = self.api.patch(
            COURANT, {'resolution_commentaires_obligatoire': False},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['resolution_commentaires_obligatoire'])
        self.assertFalse(
            selectors.reglages_clm(self.co).resolution_commentaires_obligatoire)

    def test_company_jamais_exposee_ni_acceptee(self):
        autre_co = make_company('ntdoc29-fuite', 'Fuite CLM')
        resp = self.api.patch(
            COURANT,
            {'company': autre_co.id,
             'parapheur_notification_quotidienne': True},
            format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('company', resp.data)
        parametres = ParametresCLM.objects.get(company=self.co)
        self.assertEqual(parametres.company_id, self.co.id)
        self.assertTrue(parametres.parapheur_notification_quotidienne)

    def test_duree_salle_de_donnees_zero_refusee_en_francais(self):
        resp = self.api.patch(
            COURANT,
            {'duree_defaut_expiration_salle_donnees_jours': 0}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('au moins', str(resp.data))

    def test_isolation_societe_sur_la_liste(self):
        autre_co = make_company('ntdoc29-liste', 'Liste CLM')
        ParametresCLM.objects.create(company=autre_co)
        resp = self.api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        resultats = resp.data.get('results', resp.data)
        self.assertEqual(len(resultats), 0)
