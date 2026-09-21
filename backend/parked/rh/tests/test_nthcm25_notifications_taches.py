"""Tests NTHCM25 — notifications des tâches d'on/offboarding assignées.

Couvre :
* assigner une tâche notifie l'acteur UNE fois (à l'instanciation) ;
* une tâche en retard relance UNE fois par jour maximum (dédoublonnage) ;
* une tâche NON assignée ne notifie personne ;
* une tâche faite/récupérée ne relance plus ;
* isolation société.

Horloge FIGÉE : les échéances sont des dates passées explicites ; la date du
jour n'entre que par ``aujourdhui=`` là où le code la demande.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    DossierEmploye,
    ElementIntegration,
    ElementIntegrationEmploye,
    ElementSortie,
    ModeleIntegration,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


class NotificationAssignationTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm25-a', 'A')
        self.u_rh = make_user(self.co, 'nthcm25-rh', role='responsable')
        self.u_chef = make_user(self.co, 'nthcm25-chef')
        self.chef = DossierEmploye.objects.create(
            company=self.co, matricule='N-001', nom='Chef', prenom='Le',
            user=self.u_chef)
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='N-002', nom='Oujdi', prenom='Omar',
            manager=self.chef, date_embauche=date(2026, 6, 1))
        self.modele = ModeleIntegration.objects.create(
            company=self.co, nom='Standard')
        ElementIntegration.objects.create(
            company=self.co, modele=self.modele, libelle='Entretien accueil',
            ordre=1, acteur_type='manager', delai_jours=2)

    def test_assignation_notifie_lacteur_une_fois(self):
        from apps.notifications.models import Notification

        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        tache = ElementIntegrationEmploye.objects.get(
            employe=self.employe, libelle='Entretien accueil')
        notifications = Notification.objects.filter(
            recipient=self.u_chef,
            link=services.lien_tache_onboarding(tache))
        self.assertEqual(notifications.count(), 1)

    def test_tache_non_assignee_ne_notifie_personne(self):
        from apps.notifications.models import Notification

        ElementIntegration.objects.create(
            company=self.co, modele=self.modele, libelle='Accès SI',
            ordre=2, acteur_type='it', delai_jours=1)
        services.instancier_integration(
            self.employe, modele=self.modele, createur=self.u_rh)
        tache = ElementIntegrationEmploye.objects.get(
            employe=self.employe, libelle='Accès SI')
        self.assertIsNone(tache.assigne_a_id)
        self.assertFalse(
            Notification.objects.filter(
                link=services.lien_tache_onboarding(tache)).exists())


class RappelsTachesEnRetardTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm25-r', 'R')
        self.u_acteur = make_user(self.co, 'nthcm25-acteur')
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='R-001', nom='Rami', prenom='R')
        self.hier = timezone.localdate() - timedelta(days=1)
        self.tache = ElementIntegrationEmploye.objects.create(
            company=self.co, employe=self.employe, libelle='Contrat signé',
            ordre=1, acteur_type='rh', assigne_a=self.u_acteur,
            echeance=self.hier)

    def test_rappel_une_seule_fois_par_jour(self):
        from apps.notifications.models import Notification

        lien = services.lien_tache_onboarding(self.tache)
        call_command('notifier_taches_integration_sortie', verbosity=0)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.u_acteur, link=lien,
                event_type=services.EVENT_TACHE_RAPPEL).count(), 1)

        # Second passage le MÊME jour : aucun second rappel.
        call_command('notifier_taches_integration_sortie', verbosity=0)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.u_acteur, link=lien,
                event_type=services.EVENT_TACHE_RAPPEL).count(), 1)

    def test_tache_faite_ne_relance_plus(self):
        from apps.notifications.models import Notification

        self.tache.fait = True
        self.tache.save(update_fields=['fait'])
        call_command('notifier_taches_integration_sortie', verbosity=0)
        self.assertFalse(
            Notification.objects.filter(
                event_type=services.EVENT_TACHE_RAPPEL).exists())

    def test_tache_de_sortie_en_retard_relancee(self):
        from apps.notifications.models import Notification

        sortie = ElementSortie.objects.create(
            company=self.co, employe=self.employe,
            libelle='Révocation des accès', acteur_type='it',
            assigne_a=self.u_acteur, echeance=self.hier)
        call_command('notifier_taches_integration_sortie', verbosity=0)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.u_acteur,
                link=services.lien_tache_offboarding(sortie),
                event_type=services.EVENT_TACHE_RAPPEL).count(), 1)

    def test_dry_run_nemet_rien(self):
        from apps.notifications.models import Notification

        call_command(
            'notifier_taches_integration_sortie', '--dry-run', verbosity=0)
        self.assertFalse(
            Notification.objects.filter(
                event_type=services.EVENT_TACHE_RAPPEL).exists())

    def test_isolation_societe(self):
        from apps.notifications.models import Notification

        autre = make_company('nthcm25-b', 'B')
        voisin = make_user(autre, 'nthcm25-voisin')
        call_command(
            'notifier_taches_integration_sortie',
            f'--company={autre.id}', verbosity=0)
        self.assertFalse(
            Notification.objects.filter(recipient=voisin).exists())
        self.assertFalse(
            Notification.objects.filter(recipient=self.u_acteur).exists())
