"""Tests NTDOC6 — Alerte de déviation de clause.

Critère d'acceptation :
- surcharger une clause OBLIGATOIRE fait apparaître le contrat dans les
  déviations AVEC le delta de texte ;
- une clause NON obligatoire surchargée n'apparaît pas.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors, services
from apps.contrats.models import Clause, ClauseContrat, Contrat

User = get_user_model()

BASE = '/api/django/contrats/contrats/'
DEVIATIONS = BASE + 'deviations/'
TABLEAU = BASE + 'tableau-de-bord/'

SOURCE = "Le prestataire répond des dommages causés.\nPlafond : 100 000 MAD."
SURCHARGE = "Le prestataire ne répond pas des dommages.\nPlafond : 100 000 MAD."


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DeviationsTests(TestCase):
    def setUp(self):
        self.co = make_company('ntdoc6', 'Déviations')
        self.admin = User.objects.create_user(
            username='ntdoc6-admin', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.admin)
        self.contrat = Contrat.objects.create(
            company=self.co, reference='CT-6-001', objet='Maintenance',
            type_contrat=Contrat.TypeContrat.MAINTENANCE)
        self.obligatoire = Clause.objects.create(
            company=self.co, titre='Responsabilité', corps=SOURCE,
            obligatoire_pour_types=[Contrat.TypeContrat.MAINTENANCE])
        self.facultative = Clause.objects.create(
            company=self.co, titre='Communication', corps=SOURCE)

    def _resoudre(self, clause, corps, *, surchargee=True, ordre=1):
        return ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, clause=clause,
            titre=clause.titre, corps=corps, ordre=ordre,
            surchargee=surchargee)

    # ── Détection ──────────────────────────────────────────────────────────

    def test_clause_obligatoire_surchargee_est_une_deviation(self):
        self._resoudre(self.obligatoire, SURCHARGE)
        deviations = services.detecter_deviations(self.contrat)
        self.assertEqual(len(deviations), 1)
        ecart = deviations[0]
        self.assertEqual(ecart['clause_source'], self.obligatoire.id)
        self.assertEqual(ecart['texte_source'], SOURCE)
        self.assertEqual(ecart['texte_surcharge'], SURCHARGE)
        # Le DELTA de texte est bien là (et pas juste un drapeau).
        self.assertIn('+Le prestataire ne répond pas des dommages.',
                      ecart['diff'])
        self.assertIn('-Le prestataire répond des dommages causés.',
                      ecart['diff'])
        self.assertEqual(ecart['lignes_ajoutees'], 1)
        self.assertEqual(ecart['lignes_supprimees'], 1)

    def test_clause_non_obligatoire_surchargee_nest_pas_une_deviation(self):
        self._resoudre(self.facultative, SURCHARGE)
        self.assertEqual(services.detecter_deviations(self.contrat), [])

    def test_clause_obligatoire_non_surchargee_nest_pas_une_deviation(self):
        self._resoudre(self.obligatoire, SOURCE, surchargee=False)
        self.assertEqual(services.detecter_deviations(self.contrat), [])

    def test_clause_ad_hoc_sans_source_nest_pas_une_deviation(self):
        """Sans clause-source, il n'y a rien à comparer — jamais une alerte."""
        ClauseContrat.objects.create(
            company=self.co, contrat=self.contrat, titre='Ad hoc',
            corps=SURCHARGE, surchargee=True)
        self.assertEqual(services.detecter_deviations(self.contrat), [])

    def test_surcharge_sans_ecart_reel_ne_crie_pas_au_loup(self):
        """Drapeau posé mais texte identique (fins de ligne) : aucune déviation."""
        self._resoudre(self.obligatoire, SOURCE.replace('\n', '\r\n'))
        self.assertEqual(services.detecter_deviations(self.contrat), [])

    def test_obligatoire_pour_un_AUTRE_type_nest_pas_une_deviation(self):
        autre = Clause.objects.create(
            company=self.co, titre='Clause PPA', corps=SOURCE,
            obligatoire_pour_types=[Contrat.TypeContrat.PPA])
        self._resoudre(autre, SURCHARGE)
        self.assertEqual(services.detecter_deviations(self.contrat), [])

    def test_contrat_en_deviation_drapeau(self):
        self.assertFalse(services.contrat_en_deviation(self.contrat))
        self._resoudre(self.obligatoire, SURCHARGE)
        self.assertTrue(services.contrat_en_deviation(self.contrat))

    # ── Sélecteur / carte de tableau de bord ───────────────────────────────

    def test_selecteur_liste_les_contrats_deviants(self):
        self._resoudre(self.obligatoire, SURCHARGE)
        lignes = selectors.contrats_en_deviation(self.co)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['contrat'], self.contrat.id)
        self.assertEqual(lignes[0]['reference'], 'CT-6-001')
        self.assertEqual(lignes[0]['nb_deviations'], 1)

    def test_selecteur_ignore_un_contrat_sans_deviation(self):
        self._resoudre(self.facultative, SURCHARGE)
        self.assertEqual(selectors.contrats_en_deviation(self.co), [])

    def test_selecteur_scope_societe(self):
        autre_co = make_company('ntdoc6-autre', 'Autre déviations')
        contrat_voisin = Contrat.objects.create(
            company=autre_co, objet='Voisin',
            type_contrat=Contrat.TypeContrat.MAINTENANCE)
        clause_voisine = Clause.objects.create(
            company=autre_co, titre='Responsabilité', corps=SOURCE,
            obligatoire_pour_types=[Contrat.TypeContrat.MAINTENANCE])
        ClauseContrat.objects.create(
            company=autre_co, contrat=contrat_voisin, clause=clause_voisine,
            titre='Responsabilité', corps=SURCHARGE, surchargee=True)
        self.assertEqual(selectors.contrats_en_deviation(self.co), [])
        self.assertEqual(
            [row['contrat']
             for row in selectors.contrats_en_deviation(autre_co)],
            [contrat_voisin.id])

    def test_tableau_de_bord_porte_la_carte_deviations(self):
        self._resoudre(self.obligatoire, SURCHARGE)
        resp = self.api.get(TABLEAU)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['deviations'], 1)
        # Clé ADDITIVE : les indicateurs existants sont toujours là.
        for cle in ('total', 'actifs', 'a_renouveler', 'mrr'):
            self.assertIn(cle, resp.data)

    # ── Endpoints ──────────────────────────────────────────────────────────

    def test_endpoint_liste_des_deviations(self):
        self._resoudre(self.obligatoire, SURCHARGE)
        resp = self.api.get(DEVIATIONS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['contrat'], self.contrat.id)

    def test_endpoint_detail_rend_le_diff(self):
        self._resoudre(self.obligatoire, SURCHARGE)
        resp = self.api.get(f'{BASE}{self.contrat.id}/deviations/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 1)
        self.assertIn('+Le prestataire ne répond pas des dommages.',
                      resp.data['results'][0]['diff'])

    def test_endpoint_detail_sans_deviation_rend_une_liste_vide(self):
        resp = self.api.get(f'{BASE}{self.contrat.id}/deviations/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
        self.assertEqual(resp.data['results'], [])

    def test_contrat_confidentiel_absent_pour_un_non_admin(self):
        """La carte respecte le filtre de confidentialité CONTRAT6."""
        self.contrat.confidentialite = (
            Contrat.NiveauConfidentialite.CONFIDENTIEL)
        self.contrat.save(update_fields=['confidentialite'])
        self._resoudre(self.obligatoire, SURCHARGE)
        responsable = User.objects.create_user(
            username='ntdoc6-responsable', password='x', company=self.co,
            role_legacy='responsable')
        resp = auth(responsable).get(DEVIATIONS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['count'], 0)
        # L'administrateur, lui, le voit toujours.
        self.assertEqual(self.api.get(DEVIATIONS).data['count'], 1)
