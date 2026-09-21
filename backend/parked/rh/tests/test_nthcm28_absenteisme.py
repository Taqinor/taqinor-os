"""Tests NTHCM28 — taux d'absentéisme unifié (congés + maladie + AT + injustifié).

Couvre :
* le taux s'agrège tous motifs confondus ;
* la ventilation par motif SOMME exactement au total ;
* une demande à cheval sur la fenêtre est BORNÉE (pas de gonflement) ;
* division par zéro gardée (``taux_pct=None``, jamais 0 %) ;
* comparaison département vs société ;
* isolation société ;
* bornes obligatoires côté API (400 explicite, jamais un défaut implicite).

Toutes les dates sont FIXES (aucune lecture d'horloge).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors
from apps.rh.models import (
    AccidentTravail,
    DemandeConge,
    Departement,
    DossierEmploye,
    IncidentPresence,
    TypeAbsence,
)

User = get_user_model()

DEBUT = date(2026, 3, 1)
FIN = date(2026, 3, 31)


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


class TauxAbsenteismeTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm28-a', 'A')
        self.rh = make_user(self.co, 'nthcm28-rh')
        self.api = auth(self.rh)
        self.dept = Departement.objects.create(
            company=self.co, nom='Production', code='PRD')
        self.employes = [
            DossierEmploye.objects.create(
                company=self.co, matricule=f'A-{i}', nom=f'Nom{i}',
                prenom='P', departement=self.dept,
                date_embauche=date(2024, 1, 1))
            for i in range(4)
        ]
        self.conge = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True)
        self.maladie = TypeAbsence.objects.create(
            company=self.co, code='MAL', libelle='Congé maladie',
            decompte_jours_ouvres=True)

    def _demande(self, employe, type_absence, debut, fin,
                 statut=DemandeConge.Statut.VALIDEE):
        return DemandeConge.objects.create(
            company=self.co, employe=employe, type_absence=type_absence,
            date_debut=debut, date_fin=fin, jours=Decimal('0'),
            statut=statut)

    def test_ventilation_somme_au_total(self):
        # 2026-03-02 → 2026-03-06 : 5 jours ouvrés (lundi→vendredi).
        self._demande(self.employes[0], self.conge,
                      date(2026, 3, 2), date(2026, 3, 6))
        # 2026-03-09 → 2026-03-10 : 2 jours ouvrés.
        self._demande(self.employes[1], self.maladie,
                      date(2026, 3, 9), date(2026, 3, 10))
        AccidentTravail.objects.create(
            company=self.co, employe=self.employes[2],
            date_accident=date(2026, 3, 12), arret_travail=True,
            nb_jours_arret=3)
        IncidentPresence.objects.create(
            company=self.co, employe=self.employes[3],
            type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE,
            date=date(2026, 3, 16))

        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['par_motif']['conge'], 5.0)
        self.assertEqual(resultat['par_motif']['maladie'], 2.0)
        self.assertEqual(resultat['par_motif']['accident_travail'], 3.0)
        self.assertEqual(resultat['par_motif']['non_justifie'], 1.0)
        self.assertEqual(resultat['jours_absence_total'], 11.0)
        self.assertEqual(
            round(sum(resultat['par_motif'].values()), 2),
            resultat['jours_absence_total'])

    def test_taux_calcule_sur_effectif_x_jours_ouvres(self):
        self._demande(self.employes[0], self.conge,
                      date(2026, 3, 2), date(2026, 3, 6))
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        attendu = round(
            100 * 5.0 / (resultat['effectif']
                         * resultat['jours_ouvres_periode']), 2)
        self.assertEqual(resultat['effectif'], 4)
        self.assertEqual(resultat['taux_pct'], attendu)

    def test_demande_a_cheval_est_bornee(self):
        # Du 2026-02-23 au 2026-03-06 : seuls les jours de MARS comptent
        # (2, 3, 4, 5, 6 → 5 jours ouvrés).
        self._demande(self.employes[0], self.conge,
                      date(2026, 2, 23), date(2026, 3, 6))
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['par_motif']['conge'], 5.0)

    def test_demande_non_validee_ignoree(self):
        self._demande(self.employes[0], self.conge,
                      date(2026, 3, 2), date(2026, 3, 6),
                      statut=DemandeConge.Statut.SOUMISE)
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['jours_absence_total'], 0.0)

    def test_incident_regularise_ignore(self):
        IncidentPresence.objects.create(
            company=self.co, employe=self.employes[0],
            type_incident=IncidentPresence.TypeIncident.ABSENCE_INJUSTIFIEE,
            date=date(2026, 3, 16), justifie=True)
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['par_motif']['non_justifie'], 0.0)

    def test_division_par_zero_gardee(self):
        vide = make_company('nthcm28-vide', 'V')
        resultat = selectors.taux_absenteisme(vide, DEBUT, FIN)
        self.assertEqual(resultat['effectif'], 0)
        self.assertIsNone(resultat['taux_pct'])

    def test_ventilation_par_mois(self):
        self._demande(self.employes[0], self.conge,
                      date(2026, 3, 2), date(2026, 3, 6))
        resultat = selectors.taux_absenteisme(
            self.co, date(2026, 1, 1), date(2026, 12, 31))
        mois = {ligne['mois']: ligne for ligne in resultat['par_mois']}
        self.assertEqual(list(mois), ['2026-03'])
        self.assertEqual(mois['2026-03']['conge'], 5.0)

    def test_comparaison_departement_societe(self):
        hors_dept = DossierEmploye.objects.create(
            company=self.co, matricule='A-HORS', nom='Hors', prenom='D',
            date_embauche=date(2024, 1, 1))
        self._demande(hors_dept, self.conge,
                      date(2026, 3, 2), date(2026, 3, 6))
        comparaison = selectors.comparaison_absenteisme(
            self.co, DEBUT, FIN, self.dept.id)
        self.assertEqual(
            comparaison['departement']['jours_absence_total'], 0.0)
        self.assertEqual(comparaison['societe']['jours_absence_total'], 5.0)

    def test_isolation_societe(self):
        autre = make_company('nthcm28-b', 'B')
        voisin = DossierEmploye.objects.create(
            company=autre, matricule='B-1', nom='Voisin', prenom='V')
        type_voisin = TypeAbsence.objects.create(
            company=autre, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=True)
        DemandeConge.objects.create(
            company=autre, employe=voisin, type_absence=type_voisin,
            date_debut=date(2026, 3, 2), date_fin=date(2026, 3, 6),
            jours=Decimal('5'), statut=DemandeConge.Statut.VALIDEE)
        resultat = selectors.taux_absenteisme(self.co, DEBUT, FIN)
        self.assertEqual(resultat['jours_absence_total'], 0.0)

    # ── API ───────────────────────────────────────────────────────────────
    def test_endpoint_absenteisme(self):
        reponse = self.api.get(
            '/api/django/rh/analytics/absenteisme/'
            '?debut=2026-03-01&fin=2026-03-31')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(reponse.data['effectif'], 4)

    def test_endpoint_sans_bornes_refuse(self):
        reponse = self.api.get('/api/django/rh/analytics/absenteisme/')
        self.assertEqual(reponse.status_code, 400, reponse.content)

    def test_endpoint_bornes_inversees_refuse(self):
        reponse = self.api.get(
            '/api/django/rh/analytics/absenteisme/'
            '?debut=2026-03-31&fin=2026-03-01')
        self.assertEqual(reponse.status_code, 400, reponse.content)

    def test_endpoint_comparaison_departement(self):
        reponse = self.api.get(
            '/api/django/rh/analytics/absenteisme/'
            f'?debut=2026-03-01&fin=2026-03-31&departement={self.dept.id}')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertIn('departement', reponse.data)
        self.assertIn('societe', reponse.data)
