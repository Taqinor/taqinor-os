"""Tests NTHCM23 — tâches d'onboarding multi-acteurs (RH/manager/IT/employé).

Couvre :
* une tâche « manager » s'assigne automatiquement au bon manager (NTHCM1) ;
* une tâche IT sans contact IT configuré reste NON-ASSIGNÉE (signalée) ;
* l'échéance est calculée depuis la date d'embauche + ``delai_jours`` ;
* ``en_retard`` est vrai seulement si l'échéance est passée ET la tâche non
  faite (horloge FIGÉE : l'échéance est posée dans le passé, jamais
  « aujourd'hui » lu en vrai) ;
* ``mes-taches-onboarding/`` ne montre QUE mes tâches ;
* isolation société (aucune assignation cross-tenant).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    DossierEmploye,
    ElementIntegration,
    ElementIntegrationEmploye,
    ModeleIntegration,
    ReglageRH,
)

User = get_user_model()

EMBAUCHE = date(2026, 6, 1)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TachesOnboardingTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm23-a', 'A')
        self.u_rh = make_user(self.co, 'nthcm23-rh', role='responsable')
        self.u_chef = make_user(self.co, 'nthcm23-chef')
        self.u_it = make_user(self.co, 'nthcm23-it')
        self.u_emp = make_user(self.co, 'nthcm23-emp')
        self.chef = DossierEmploye.objects.create(
            company=self.co, matricule='O-001', nom='Chef', prenom='Le',
            user=self.u_chef)
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='O-002', nom='Naciri', prenom='Nadia',
            user=self.u_emp, manager=self.chef, date_embauche=EMBAUCHE)
        self.modele = ModeleIntegration.objects.create(
            company=self.co, nom='Intégration standard')
        ElementIntegration.objects.create(
            company=self.co, modele=self.modele, libelle='Entretien d’accueil',
            ordre=1, acteur_type='manager', delai_jours=2)
        ElementIntegration.objects.create(
            company=self.co, modele=self.modele, libelle='Création des accès',
            ordre=2, acteur_type='it', delai_jours=1)
        ElementIntegration.objects.create(
            company=self.co, modele=self.modele, libelle='Signer le règlement',
            ordre=3, acteur_type='employe_lui_meme', delai_jours=5)

    def _lignes(self):
        return {
            ligne.libelle: ligne
            for ligne in ElementIntegrationEmploye.objects.filter(
                employe=self.employe)}

    def test_tache_manager_sassigne_au_bon_manager(self):
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        ligne = self._lignes()['Entretien d’accueil']
        self.assertEqual(ligne.assigne_a_id, self.u_chef.id)
        self.assertEqual(ligne.echeance, EMBAUCHE + timedelta(days=2))

    def test_tache_it_sans_contact_reste_non_assignee(self):
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        ligne = self._lignes()['Création des accès']
        self.assertIsNone(ligne.assigne_a_id)
        self.assertEqual(ligne.acteur_type, 'it')

    def test_tache_it_sassigne_au_contact_configure(self):
        ReglageRH.objects.create(company=self.co, contact_it_defaut=self.u_it)
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        ligne = self._lignes()['Création des accès']
        self.assertEqual(ligne.assigne_a_id, self.u_it.id)

    def test_tache_employe_et_tache_rh(self):
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        lignes = self._lignes()
        self.assertEqual(
            lignes['Signer le règlement'].assigne_a_id, self.u_emp.id)
        # XRH5 — l'item bloquant ajouté d'office porte l'acteur RH.
        bloquant = lignes["Déclaration d'entrée CNSS/AMO"]
        self.assertEqual(bloquant.acteur_type, 'rh')
        self.assertEqual(bloquant.assigne_a_id, self.u_rh.id)

    def test_manager_sans_compte_laisse_la_tache_non_assignee(self):
        self.chef.user = None
        self.chef.save(update_fields=['user'])
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        self.assertIsNone(self._lignes()['Entretien d’accueil'].assigne_a_id)

    def test_acteur_dune_autre_societe_jamais_assigne(self):
        autre = make_company('nthcm23-b', 'B')
        etranger = make_user(autre, 'nthcm23-etranger')
        ReglageRH.objects.create(company=self.co, contact_it_defaut=etranger)
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        self.assertIsNone(self._lignes()['Création des accès'].assigne_a_id)

    def test_echeance_sans_date_embauche_part_du_jour(self):
        self.employe.date_embauche = None
        self.employe.save(update_fields=['date_embauche'])
        jour = date(2026, 9, 9)
        self.assertEqual(
            services.echeance_tache_integration(
                self.employe, 3, aujourdhui=jour),
            date(2026, 9, 12))

    def test_en_retard_calcule(self):
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        ligne = self._lignes()['Entretien d’accueil']
        # Échéance posée dans le passé — aucune lecture de « maintenant » dans
        # l'assertion, seulement un ordre relatif garanti.
        ligne.echeance = timezone.localdate() - timedelta(days=1)
        ligne.save(update_fields=['echeance'])
        self.assertTrue(ligne.en_retard)
        ligne.fait = True
        self.assertFalse(ligne.en_retard)

    def test_tache_sans_echeance_jamais_en_retard(self):
        ligne = ElementIntegrationEmploye.objects.create(
            company=self.co, employe=self.employe, libelle='Libre', ordre=9)
        self.assertIsNone(ligne.echeance)
        self.assertFalse(ligne.en_retard)

    # ── API ───────────────────────────────────────────────────────────────
    def test_mes_taches_onboarding_ne_montre_que_les_miennes(self):
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        reponse = auth(self.u_chef).get(
            '/api/django/rh/elements-integration-employe/'
            'mes-taches-onboarding/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        libelles = [ligne['libelle'] for ligne in reponse.data]
        self.assertEqual(libelles, ['Entretien d’accueil'])

    def test_mes_taches_onboarding_vide_pour_un_non_acteur(self):
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        passant = make_user(self.co, 'nthcm23-passant')
        reponse = auth(passant).get(
            '/api/django/rh/elements-integration-employe/'
            'mes-taches-onboarding/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(list(reponse.data), [])

    def test_mes_taches_onboarding_isolee_par_societe(self):
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        autre = make_company('nthcm23-c', 'C')
        voisin = make_user(autre, 'nthcm23-voisin', role='responsable')
        reponse = auth(voisin).get(
            '/api/django/rh/elements-integration-employe/'
            'mes-taches-onboarding/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        self.assertEqual(list(reponse.data), [])
