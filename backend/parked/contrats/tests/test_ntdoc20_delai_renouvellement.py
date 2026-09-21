"""Tests NTDOC20 — Délai de prévenance d'échéance PAR type de contrat.

Critère d'acceptation :
- un contrat de type maintenance réglé à 90 j alerte 90 jours avant échéance ;
- un contrat d'un type réglé à 30 j alerte 30 jours avant ;
- la valeur PAR DÉFAUT (aucun réglage) reproduit EXACTEMENT le comportement
  actuel.
"""
import inspect
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import (
    DELAI_RENOUVELLEMENT_DEFAUT,
    AlerteContrat, Contrat, ParametreRenouvellement,
)

User = get_user_model()

BASE = '/api/django/contrats/parametres-renouvellement/'
AUJOURD_HUI = date(2026, 3, 1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DelaiRenouvellementTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc20', 'Délais')
        self.admin = User.objects.create_user(
            username='ntdoc20-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.admin)

    def contrat(self, type_contrat, jours_avant_fin):
        """Contrat actif dont la ``date_fin`` tombe dans N jours."""
        return Contrat.objects.create(
            company=self.co, objet=f'{type_contrat} J+{jours_avant_fin}',
            type_contrat=type_contrat, statut=Contrat.Statut.ACTIF,
            date_fin=AUJOURD_HUI + timedelta(days=jours_avant_fin))

    def semer(self):
        return services.semer_alertes_echeances(self.co, today=AUJOURD_HUI)

    def types_alertes(self):
        return set(
            AlerteContrat.objects
            .filter(company=self.co)
            .values_list('contrat_id', flat=True))

    # ── Neutralité : aucun réglage = comportement historique ───────────────

    def test_defaut_reproduit_le_comportement_actuel(self):
        """Sans aucune ligne réglée : exactement le semis d'avant (30 j)."""
        dedans = self.contrat(Contrat.TypeContrat.MAINTENANCE, 20)
        dehors = self.contrat(Contrat.TypeContrat.MAINTENANCE, 60)
        self.semer()
        self.assertEqual(self.types_alertes(), {dedans.id})
        self.assertNotIn(dehors.id, self.types_alertes())

    def test_constante_par_defaut_alignee_sur_la_signature_historique(self):
        """La constante NE DOIT PAS diverger du ``within_days`` du service."""
        signature = inspect.signature(services.semer_alertes_echeances)
        self.assertEqual(
            signature.parameters['within_days'].default,
            DELAI_RENOUVELLEMENT_DEFAUT)

    def test_selecteur_vide_sans_configuration(self):
        self.assertEqual(selectors.delais_renouvellement(self.co), {})

    # ── Délai configuré par type ───────────────────────────────────────────

    def test_maintenance_a_90_jours_alerte_90_jours_avant(self):
        ParametreRenouvellement.objects.create(
            company=self.co, type_contrat=Contrat.TypeContrat.MAINTENANCE,
            delai_avant_echeance_jours=90)
        proche = self.contrat(Contrat.TypeContrat.MAINTENANCE, 80)
        loin = self.contrat(Contrat.TypeContrat.MAINTENANCE, 120)
        self.semer()
        alertes = self.types_alertes()
        self.assertIn(proche.id, alertes)
        self.assertNotIn(loin.id, alertes)

    def test_deux_types_deux_delais_simultanement(self):
        ParametreRenouvellement.objects.create(
            company=self.co, type_contrat=Contrat.TypeContrat.MAINTENANCE,
            delai_avant_echeance_jours=90)
        ParametreRenouvellement.objects.create(
            company=self.co, type_contrat=Contrat.TypeContrat.LOCATION,
            delai_avant_echeance_jours=30)
        maintenance = self.contrat(Contrat.TypeContrat.MAINTENANCE, 80)
        location_proche = self.contrat(Contrat.TypeContrat.LOCATION, 20)
        location_loin = self.contrat(Contrat.TypeContrat.LOCATION, 80)
        self.semer()
        alertes = self.types_alertes()
        self.assertIn(maintenance.id, alertes)
        self.assertIn(location_proche.id, alertes)
        # Même à 80 jours, une location réglée à 30 j n'est PAS alertée alors
        # que la maintenance du même horizon l'est : c'est tout le sujet.
        self.assertNotIn(location_loin.id, alertes)

    def test_type_non_regle_garde_le_delai_recu(self):
        ParametreRenouvellement.objects.create(
            company=self.co, type_contrat=Contrat.TypeContrat.MAINTENANCE,
            delai_avant_echeance_jours=120)
        vente_dedans = self.contrat(Contrat.TypeContrat.VENTE, 20)
        vente_dehors = self.contrat(Contrat.TypeContrat.VENTE, 60)
        self.semer()
        alertes = self.types_alertes()
        self.assertIn(vente_dedans.id, alertes)
        self.assertNotIn(vente_dehors.id, alertes)

    def test_semis_reste_idempotent(self):
        ParametreRenouvellement.objects.create(
            company=self.co, type_contrat=Contrat.TypeContrat.MAINTENANCE,
            delai_avant_echeance_jours=90)
        self.contrat(Contrat.TypeContrat.MAINTENANCE, 80)
        premier = self.semer()
        second = self.semer()
        self.assertEqual(premier['nb_creees'], 1)
        self.assertEqual(second['nb_creees'], 0)

    def test_preavis_suit_aussi_le_delai_du_type(self):
        """Le délai règle AUSSI la fenêtre de préavis, pas seulement l'échéance."""
        ParametreRenouvellement.objects.create(
            company=self.co, type_contrat=Contrat.TypeContrat.OM,
            delai_avant_echeance_jours=90)
        contrat = Contrat.objects.create(
            company=self.co, objet='O&M avec préavis',
            type_contrat=Contrat.TypeContrat.OM,
            statut=Contrat.Statut.ACTIF,
            date_fin=AUJOURD_HUI + timedelta(days=130),
            preavis_jours=60)
        # Échéance de préavis = fin − 60 j = J+70 → dans la fenêtre de 90 j,
        # hors de la fenêtre historique de 30 j.
        self.semer()
        self.assertTrue(
            AlerteContrat.objects.filter(
                contrat=contrat,
                type_alerte=AlerteContrat.TypeAlerte.PREAVIS).exists())

    # ── API ────────────────────────────────────────────────────────────────

    def test_crud_pose_la_societe_cote_serveur(self):
        resp = self.api.post(
            BASE,
            {'type_contrat': Contrat.TypeContrat.MAINTENANCE,
             'delai_avant_echeance_jours': 90},
            format='json')
        self.assertEqual(resp.status_code, 201)
        ligne = ParametreRenouvellement.objects.get(id=resp.data['id'])
        self.assertEqual(ligne.company_id, self.co.id)
        self.assertNotIn('company', resp.data)

    def test_doublon_refuse_en_francais(self):
        ParametreRenouvellement.objects.create(
            company=self.co, type_contrat=Contrat.TypeContrat.MAINTENANCE,
            delai_avant_echeance_jours=90)
        resp = self.api.post(
            BASE,
            {'type_contrat': Contrat.TypeContrat.MAINTENANCE,
             'delai_avant_echeance_jours': 60},
            format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('déjà réglé', str(resp.data))

    def test_isolation_societe(self):
        autre_co = make_company('ntdoc20-autre', 'Autre délais')
        ParametreRenouvellement.objects.create(
            company=autre_co, type_contrat=Contrat.TypeContrat.MAINTENANCE,
            delai_avant_echeance_jours=90)
        resp = self.api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        resultats = resp.data.get('results', resp.data)
        self.assertEqual(len(resultats), 0)
        self.assertEqual(selectors.delais_renouvellement(self.co), {})

    def test_suggestions_ne_creent_rien(self):
        resp = self.api.get(BASE + 'suggestions/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['defaut'], DELAI_RENOUVELLEMENT_DEFAUT)
        self.assertEqual(resp.data['suggestions']['maintenance'], 90)
        # Une SUGGESTION n'écrit rien : le comportement reste l'historique.
        self.assertEqual(
            ParametreRenouvellement.objects.filter(company=self.co).count(), 0)
