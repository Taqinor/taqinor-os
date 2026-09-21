"""Tests NTHCM27 — analytics diversité (agrégée, seuil d'anonymat).

Couvre :
* la répartition s'agrège correctement, et par département ;
* un segment de moins de 5 personnes est MASQUÉ (pas de ré-identification) ;
* AUCUN champ nominatif ne figure dans la réponse (test d'exhaustivité,
  patron XRH28) ;
* la tranche d'âge est exclue proprement (pas de date de naissance au
  dossier), jamais estimée ;
* isolation société + gate Administrateur/Responsable.

Horloge FIGÉE (``aujourdhui=``) pour l'ancienneté moyenne.
"""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import Departement, DossierEmploye

User = get_user_model()

JOUR_FIGE = date(2026, 1, 1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class AnalyticsDiversiteTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm27-a', 'A')
        self.rh = make_user(self.co, 'nthcm27-rh')
        self.api = auth(self.rh)
        self.dept = Departement.objects.create(
            company=self.co, nom='Production', code='PRD')
        # 6 femmes (au-dessus du seuil), 2 hommes (en dessous).
        for i in range(6):
            DossierEmploye.objects.create(
                company=self.co, matricule=f'D-F{i}', nom=f'Femme{i}',
                prenom='X', genre='femme', departement=self.dept,
                date_embauche=date(2024, 1, 1))
        for i in range(2):
            DossierEmploye.objects.create(
                company=self.co, matricule=f'D-H{i}', nom=f'Homme{i}',
                prenom='Y', genre='homme', departement=self.dept,
                date_embauche=date(2024, 1, 1))

    def _segment(self, resultat, genre):
        return next(
            ligne for ligne in resultat['repartition_genre']
            if ligne['genre'] == genre)

    def test_segment_au_dessus_du_seuil_est_chiffre(self):
        resultat = selectors.analytics_diversite(
            self.co, aujourdhui=JOUR_FIGE)
        femmes = self._segment(resultat, 'femme')
        self.assertFalse(femmes['masque'])
        self.assertEqual(femmes['effectif'], 6)
        self.assertEqual(femmes['part_pct'], 75.0)
        self.assertEqual(resultat['effectif'], 8)

    def test_segment_sous_le_seuil_est_masque(self):
        resultat = selectors.analytics_diversite(
            self.co, aujourdhui=JOUR_FIGE)
        hommes = self._segment(resultat, 'homme')
        self.assertTrue(hommes['masque'])
        self.assertIsNone(hommes['effectif'])
        self.assertIsNone(hommes['part_pct'])

    def test_sortis_exclus(self):
        DossierEmploye.objects.create(
            company=self.co, matricule='D-SORTI', nom='Parti', prenom='Z',
            genre='femme', statut=DossierEmploye.Statut.SORTI)
        resultat = selectors.analytics_diversite(
            self.co, aujourdhui=JOUR_FIGE)
        self.assertEqual(resultat['effectif'], 8)

    def test_filtre_par_departement(self):
        autre_dept = Departement.objects.create(
            company=self.co, nom='Commercial', code='COM')
        DossierEmploye.objects.create(
            company=self.co, matricule='D-C1', nom='Commercial', prenom='W',
            genre='homme', departement=autre_dept)
        resultat = selectors.analytics_diversite(
            self.co, departement_id=autre_dept.id, aujourdhui=JOUR_FIGE)
        self.assertEqual(resultat['effectif'], 1)
        self.assertEqual(resultat['departement_id'], autre_dept.id)

    def test_anciennete_moyenne_masquee_sous_le_seuil(self):
        autre = make_company('nthcm27-petite', 'P')
        DossierEmploye.objects.create(
            company=autre, matricule='P-1', nom='Seul', prenom='S',
            date_embauche=date(2024, 1, 1))
        resultat = selectors.analytics_diversite(
            autre, aujourdhui=JOUR_FIGE)
        self.assertTrue(resultat['anciennete_masquee'])
        self.assertIsNone(resultat['anciennete_moyenne_annees'])

    def test_anciennete_moyenne_calculee(self):
        resultat = selectors.analytics_diversite(
            self.co, aujourdhui=JOUR_FIGE)
        self.assertFalse(resultat['anciennete_masquee'])
        # 8 dossiers embauchés le 2024-01-01, horloge figée au 2026-01-01.
        self.assertEqual(resultat['anciennete_moyenne_annees'], 2.0)
        self.assertEqual(resultat['nb_dates_embauche_connues'], 8)

    def test_tranche_age_exclue_proprement(self):
        resultat = selectors.analytics_diversite(
            self.co, aujourdhui=JOUR_FIGE)
        self.assertEqual(resultat['tranches_age'], [])
        self.assertFalse(resultat['age_disponible'])
        self.assertTrue(resultat['age_indisponible_raison'])

    def test_aucun_champ_nominatif_dans_la_reponse(self):
        """Exhaustivité (patron XRH28) : la charge utile entière est balayée."""
        resultat = selectors.analytics_diversite(
            self.co, aujourdhui=JOUR_FIGE)
        brut = json.dumps(resultat, default=str)
        for interdit in ('Femme0', 'Homme0', 'D-F0', 'D-H0'):
            self.assertNotIn(interdit, brut)

    def test_isolation_societe(self):
        autre = make_company('nthcm27-b', 'B')
        for i in range(7):
            DossierEmploye.objects.create(
                company=autre, matricule=f'B-{i}', nom=f'Voisin{i}',
                prenom='V', genre='homme')
        resultat = selectors.analytics_diversite(
            self.co, aujourdhui=JOUR_FIGE)
        self.assertEqual(resultat['effectif'], 8)

    # ── API ───────────────────────────────────────────────────────────────
    def test_endpoint_diversite(self):
        reponse = self.api.get('/api/django/rh/analytics/diversite/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['seuil_anonymat'], 5)

    def test_endpoint_refuse_un_role_non_responsable(self):
        simple = make_user(self.co, 'nthcm27-simple', role='normal')
        reponse = auth(simple).get('/api/django/rh/analytics/diversite/')
        self.assertEqual(reponse.status_code, 403, reponse.content)
