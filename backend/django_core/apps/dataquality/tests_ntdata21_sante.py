"""NTDATA21 — carte « Santé des données » (3 indicateurs, tous réels).

Couvre :
  * le critère d'acceptation : la carte rend 3 indicateurs LIVE, et est
    MASQUÉE (`disponible=false`) tant que la société n'a aucune règle ;
  * une règle bloquante JAMAIS ÉVALUÉE n'est pas comptée conforme : elle est
    comptée à part, pour que « 0 violation » ne veuille pas dire « 0 mesure » ;
  * seules les règles BLOQUANTES actives entrent dans l'indicateur ;
  * un score de complétude non mesurable reste VIDE, jamais 0 ;
  * la carte est enregistrée dans `ALL_DASHBOARD_CARDS` ;
  * le scoping société + l'endpoint `/dataquality/sante/`.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.crm.models import Client
from apps.dataquality import selectors, services
from apps.dataquality.models import (
    GoldenRecord, PropositionFusion, RegleQualite,
)
from apps.dataquality.views import SanteDonneesView
from apps.reporting.models import ALL_DASHBOARD_CARDS
from authentication.models import Company

User = get_user_model()


class SanteDonneesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA21 SA',
                                             slug='ntdata21-sa')
        cls.autre = Company.objects.create(nom='NTDATA21 Autre',
                                           slug='ntdata21-autre')
        cls.user = User.objects.create_user(
            username='ntdata21_u', password='x', company=cls.company,
            role_legacy='admin')

    def _regle_bloquante(self, champ='ice', company=None):
        return RegleQualite.objects.create(
            company=company or self.company, entite='crm_clients',
            champ=champ, type_regle=RegleQualite.TypeRegle.NON_VIDE,
            severite=RegleQualite.Severite.BLOQUANT)

    def test_carte_enregistree_dans_le_catalogue(self):
        self.assertIn('sante_donnees', ALL_DASHBOARD_CARDS)

    def test_masquee_sans_aucune_regle(self):
        sante = selectors.sante_donnees(self.company, self.user)
        self.assertFalse(sante['disponible'])
        # Aucun zéro fabriqué : tout est VIDE tant qu'il n'y a rien à mesurer.
        self.assertIsNone(sante['completude_globale_pct'])
        self.assertIsNone(sante['regles_bloquantes_en_violation'])
        self.assertIsNone(sante['doublons_en_attente'])

    def test_trois_indicateurs_live(self):
        """Critère : complétude + règles bloquantes en violation + doublons."""
        Client.objects.create(company=self.company, nom='Partiel')
        self._regle_bloquante()
        services.evaluer_regles(self.company, user=self.user)

        sante = selectors.sante_donnees(self.company, self.user)
        self.assertTrue(sante['disponible'])
        # 1 client sur 4 champs critiques, seul `nom` est rempli ⇒ 25 %.
        self.assertEqual(sante['completude_globale_pct'], 25.0)
        # La règle « ICE renseigné » est violée par ce client.
        self.assertEqual(sante['regles_bloquantes_en_violation'], 1)
        self.assertEqual(sante['bloquantes_non_evaluees'], 0)
        self.assertEqual(sante['doublons_en_attente'], 0)

    def test_regle_bloquante_jamais_evaluee_comptee_a_part(self):
        Client.objects.create(company=self.company, nom='Partiel')
        self._regle_bloquante()
        sante = selectors.sante_donnees(self.company, self.user)
        # Jamais mesurée ⇒ ni « en violation » ni « conforme ».
        self.assertEqual(sante['regles_bloquantes_en_violation'], 0)
        self.assertEqual(sante['bloquantes_non_evaluees'], 1)

    def test_seules_les_regles_bloquantes_comptent(self):
        Client.objects.create(company=self.company, nom='Partiel')
        RegleQualite.objects.create(
            company=self.company, entite='crm_clients', champ='ice',
            type_regle=RegleQualite.TypeRegle.NON_VIDE,
            severite=RegleQualite.Severite.AVERTISSEMENT)
        services.evaluer_regles(self.company, user=self.user)
        sante = selectors.sante_donnees(self.company, self.user)
        self.assertTrue(sante['disponible'])
        self.assertEqual(sante['regles_bloquantes_en_violation'], 0)
        self.assertEqual(sante['bloquantes_non_evaluees'], 0)

    def test_regle_bloquante_inactive_ignoree(self):
        Client.objects.create(company=self.company, nom='Partiel')
        regle = self._regle_bloquante()
        services.evaluer_regles(self.company, user=self.user)
        regle.actif = False
        regle.save(update_fields=['actif'])
        sante = selectors.sante_donnees(self.company, self.user)
        self.assertEqual(sante['regles_bloquantes_en_violation'], 0)

    def test_completude_non_mesurable_reste_vide(self):
        """Aucune fiche du tout : le score est VIDE, jamais 0 ni 100."""
        self._regle_bloquante()
        sante = selectors.sante_donnees(self.company, self.user)
        self.assertTrue(sante['disponible'])
        self.assertIsNone(sante['completude_globale_pct'])

    def test_doublons_en_attente_comptes(self):
        self._regle_bloquante()
        PropositionFusion.objects.create(
            company=self.company, entite=GoldenRecord.Entite.CLIENT,
            ids_groupe=[1, 2], empreinte='1-2', score=0.95)
        PropositionFusion.objects.create(
            company=self.company, entite=GoldenRecord.Entite.CLIENT,
            ids_groupe=[3, 4], empreinte='3-4', score=0.90,
            statut=PropositionFusion.Statut.IGNORE)
        sante = selectors.sante_donnees(self.company, self.user)
        # Seule la proposition EN ATTENTE compte : une décision prise n'est
        # plus une dette de qualité.
        self.assertEqual(sante['doublons_en_attente'], 1)

    def test_scoping_societe(self):
        self._regle_bloquante(company=self.autre)
        PropositionFusion.objects.create(
            company=self.autre, entite=GoldenRecord.Entite.CLIENT,
            ids_groupe=[1, 2], empreinte='1-2', score=0.95)
        sante = selectors.sante_donnees(self.company, self.user)
        self.assertFalse(sante['disponible'])


class SanteDonneesEndpointTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='NTDATA21 API',
                                             slug='ntdata21-api')
        cls.responsable = User.objects.create_user(
            username='ntdata21_resp', password='x', company=cls.company,
            role_legacy='admin')
        cls.simple = User.objects.create_user(
            username='ntdata21_simple', password='x', company=cls.company,
            role_legacy='normal')

    def _get(self, user=None):
        requete = APIRequestFactory().get('/api/django/dataquality/sante/')
        force_authenticate(requete, user=user or self.responsable)
        return SanteDonneesView.as_view()(requete)

    def test_endpoint(self):
        reponse = self._get()
        self.assertEqual(reponse.status_code, status.HTTP_200_OK)
        self.assertIn('disponible', reponse.data)
        self.assertIn('completude_globale_pct', reponse.data)
        self.assertIn('regles_bloquantes_en_violation', reponse.data)
        self.assertIn('doublons_en_attente', reponse.data)

    def test_utilisateur_non_responsable_refuse(self):
        self.assertEqual(self._get(user=self.simple).status_code,
                         status.HTTP_403_FORBIDDEN)
