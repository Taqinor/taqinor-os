"""Tests NTHCM24 — tâches d'offboarding multi-acteurs + rapport de retard.

Couvre :
* une tâche IT de révocation d'accès non faite après l'échéance remonte EN
  TÊTE du rapport (risque de sécurité) ;
* une tâche récupérée, ou sans échéance, n'y figure jamais ;
* l'assignation est résolue côté serveur à la création (manager/IT/employé) ;
* ``sortir_employe`` pose l'échéance des lignes générées à la date de sortie ;
* isolation société.

Horloge FIGÉE : ``aujourdhui=`` est injecté dans le sélecteur, les échéances
sont des dates fixes — aucune date « du jour » lue en vrai.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import selectors, services
from apps.rh.models import DossierEmploye, ElementSortie, ReglageRH

User = get_user_model()

JOUR_FIGE = date(2026, 7, 15)


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


class OffboardingRetardTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm24-a', 'A')
        self.rh = make_user(self.co, 'nthcm24-rh')
        self.u_it = make_user(self.co, 'nthcm24-it', role='normal')
        self.api = auth(self.rh)
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='S-001', nom='Tazi', prenom='Tarik',
            date_sortie=date(2026, 7, 1))

    def _ligne(self, libelle, *, acteur='rh', echeance=None, recupere=False):
        return ElementSortie.objects.create(
            company=self.co, employe=self.employe, libelle=libelle,
            acteur_type=acteur, echeance=echeance, recupere=recupere)

    def test_tache_it_remonte_en_tete(self):
        # L'élément RH est plus ANCIEN, donc premier par ancienneté — et
        # pourtant la tâche IT doit passer devant (criticité).
        self._ligne('Badge à rendre', acteur='rh',
                    echeance=date(2026, 6, 1))
        self._ligne("Révocation des accès", acteur='it',
                    echeance=date(2026, 7, 1))
        rapport = selectors.offboarding_en_retard(
            self.co, aujourdhui=JOUR_FIGE)
        self.assertEqual(
            [ligne['libelle'] for ligne in rapport],
            ['Révocation des accès', 'Badge à rendre'])
        self.assertTrue(rapport[0]['critique'])
        self.assertEqual(rapport[0]['jours_de_retard'], 14)

    def test_tache_recuperee_ou_sans_echeance_absente(self):
        self._ligne('Déjà rendu', acteur='it',
                    echeance=date(2026, 6, 1), recupere=True)
        self._ligne('Sans échéance', acteur='it')
        self.assertEqual(
            selectors.offboarding_en_retard(self.co, aujourdhui=JOUR_FIGE),
            [])

    def test_echeance_future_pas_en_retard(self):
        self._ligne('À venir', acteur='it', echeance=date(2026, 8, 1))
        self.assertEqual(
            selectors.offboarding_en_retard(self.co, aujourdhui=JOUR_FIGE),
            [])

    def test_en_retard_propriete_du_modele(self):
        ligne = self._ligne('Passée', echeance=date(2020, 1, 1))
        self.assertTrue(ligne.en_retard)
        ligne.recupere = True
        self.assertFalse(ligne.en_retard)

    def test_isolation_societe(self):
        autre = make_company('nthcm24-b', 'B')
        voisin = DossierEmploye.objects.create(
            company=autre, matricule='S-999', nom='Voisin', prenom='V')
        ElementSortie.objects.create(
            company=autre, employe=voisin, libelle='Chez le voisin',
            acteur_type='it', echeance=date(2026, 6, 1))
        self.assertEqual(
            selectors.offboarding_en_retard(self.co, aujourdhui=JOUR_FIGE),
            [])

    # ── assignation résolue serveur ───────────────────────────────────────
    def test_creation_api_resout_le_contact_it(self):
        ReglageRH.objects.create(company=self.co, contact_it_defaut=self.u_it)
        reponse = self.api.post(
            '/api/django/rh/elements-sortie/',
            {'employe': self.employe.id, 'libelle': 'Révocation des accès',
             'acteur_type': 'it', 'echeance': '2026-07-01'},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        ligne = ElementSortie.objects.get(pk=reponse.data['id'])
        self.assertEqual(ligne.assigne_a_id, self.u_it.id)

    def test_creation_api_sans_contact_it_reste_non_assignee(self):
        reponse = self.api.post(
            '/api/django/rh/elements-sortie/',
            {'employe': self.employe.id, 'libelle': 'Révocation des accès',
             'acteur_type': 'it'},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.content)
        ligne = ElementSortie.objects.get(pk=reponse.data['id'])
        self.assertIsNone(ligne.assigne_a_id)

    def test_endpoint_en_retard(self):
        self._ligne("Révocation des accès", acteur='it',
                    echeance=date(2020, 1, 1))
        reponse = self.api.get('/api/django/rh/elements-sortie/en-retard/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(len(reponse.data), 1)
        self.assertTrue(reponse.data[0]['critique'])


class EcheanceGenereeALaSortieTests(TestCase):
    """``sortir_employe`` date les lignes qu'il génère (NTHCM24)."""

    def test_ligne_avance_datee_a_la_sortie(self):
        from decimal import Decimal

        from apps.rh.models import AvanceSalaire

        co = make_company('nthcm24-c', 'C')
        employe = DossierEmploye.objects.create(
            company=co, matricule='S-010', nom='Zniber', prenom='Z')
        AvanceSalaire.objects.create(
            company=co, employe=employe, montant=Decimal('1000'),
            statut=AvanceSalaire.Statut.DEMANDEE)
        sortie = date(2026, 7, 10)
        services.sortir_employe(
            employe, date_sortie=sortie,
            motif=DossierEmploye.MotifSortie.DEMISSION)
        ligne = ElementSortie.objects.get(
            employe=employe, libelle='Avances sur salaire non soldées')
        self.assertEqual(ligne.echeance, sortie)
