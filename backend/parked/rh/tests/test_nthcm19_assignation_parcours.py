"""Tests NTHCM19 — assignation automatique des parcours + rappels.

Couvre :
* l'embauche sur un poste CIBLÉ assigne automatiquement ses parcours
  obligatoires ;
* un embauché sur un poste NON ciblé n'a rien (aucune assignation inventée) ;
* la ré-assignation est idempotente (aucun doublon) ;
* le rappel ne part qu'au-delà du délai société et ne spamme pas (une seule
  notification par jour et par parcours) ;
* isolation société.

Horloge FIGÉE partout : aucune date « du jour » n'est lue en vrai.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.rh import services
from apps.rh.management.commands import rappels_parcours_formation as cmd
from apps.rh.models import (
    Departement,
    DossierEmploye,
    ParcoursFormation,
    Poste,
    ProgressionParcours,
    ReglageRH,
)

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class AssignationParcoursTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm19-a', 'A')
        self.poste_poseur = Poste.objects.create(
            company=self.co, intitule='Poseur PV')
        self.poste_commercial = Poste.objects.create(
            company=self.co, intitule='Commercial')
        self.dept = Departement.objects.create(
            company=self.co, nom='Travaux', code='TRV')
        self.parcours_poseur = ParcoursFormation.objects.create(
            company=self.co, titre='Sécurité poseur', obligatoire=True,
            poste_cible=self.poste_poseur)
        self.parcours_universel = ParcoursFormation.objects.create(
            company=self.co, titre='Accueil société', obligatoire=True)
        self.parcours_optionnel = ParcoursFormation.objects.create(
            company=self.co, titre='Anglais technique', obligatoire=False)

    def test_poste_cible_recoit_ses_parcours_obligatoires(self):
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-001', nom='Alami', prenom='Ali',
            poste_ref=self.poste_poseur)
        creees = services.assigner_parcours_obligatoires(employe)
        titres = sorted(p.parcours.titre for p in creees)
        self.assertEqual(titres, ['Accueil société', 'Sécurité poseur'])

    def test_poste_non_cible_ne_recoit_que_luniversel(self):
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-002', nom='Bennis', prenom='Btissam',
            poste_ref=self.poste_commercial)
        services.assigner_parcours_obligatoires(employe)
        titres = sorted(
            ProgressionParcours.objects.filter(
                employe=employe).values_list('parcours__titre', flat=True))
        self.assertEqual(titres, ['Accueil société'])

    def test_parcours_optionnel_jamais_assigne(self):
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-003', nom='Cherkaoui', prenom='C',
            poste_ref=self.poste_poseur)
        services.assigner_parcours_obligatoires(employe)
        self.assertFalse(
            ProgressionParcours.objects.filter(
                employe=employe,
                parcours=self.parcours_optionnel).exists())

    def test_parcours_inactif_jamais_assigne(self):
        self.parcours_poseur.actif = False
        self.parcours_poseur.save(update_fields=['actif'])
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-004', nom='Doukkali', prenom='D',
            poste_ref=self.poste_poseur)
        services.assigner_parcours_obligatoires(employe)
        self.assertFalse(
            ProgressionParcours.objects.filter(
                employe=employe, parcours=self.parcours_poseur).exists())

    def test_assignation_idempotente(self):
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-005', nom='El Fassi', prenom='E',
            poste_ref=self.poste_poseur)
        services.assigner_parcours_obligatoires(employe)
        second = services.assigner_parcours_obligatoires(employe)
        self.assertEqual(second, [])
        self.assertEqual(
            ProgressionParcours.objects.filter(employe=employe).count(), 2)

    def test_cible_departement(self):
        parcours_dept = ParcoursFormation.objects.create(
            company=self.co, titre='Consignes travaux', obligatoire=True,
            departement_cible=self.dept)
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-006', nom='Filali', prenom='F',
            departement=self.dept)
        services.assigner_parcours_obligatoires(employe)
        self.assertTrue(
            ProgressionParcours.objects.filter(
                employe=employe, parcours=parcours_dept).exists())

    def test_isolation_societe(self):
        autre = make_company('nthcm19-b', 'B')
        ParcoursFormation.objects.create(
            company=autre, titre='Chez le voisin', obligatoire=True)
        employe = DossierEmploye.objects.create(
            company=self.co, matricule='A-007', nom='Guessous', prenom='G')
        services.assigner_parcours_obligatoires(employe)
        titres = sorted(
            ProgressionParcours.objects.filter(
                employe=employe).values_list('parcours__titre', flat=True))
        self.assertEqual(titres, ['Accueil société'])


class RappelsParcoursTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm19-r', 'R')
        self.user = User.objects.create_user(
            username='nthcm19-emp', password='x', company=self.co,
            role_legacy='normal')
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='R-001', nom='Hakimi', prenom='H',
            user=self.user)
        self.parcours = ParcoursFormation.objects.create(
            company=self.co, titre='Accueil société', obligatoire=True)
        self.progression = ProgressionParcours.objects.create(
            company=self.co, parcours=self.parcours, employe=self.employe)

    def _vieillir(self, jours):
        """Recule ``created_at`` (auto_now_add) sans toucher à l'horloge."""
        ProgressionParcours.objects.filter(pk=self.progression.pk).update(
            created_at=timezone.now() - timedelta(days=jours))

    def test_en_retard_seulement_au_dela_du_delai(self):
        self._vieillir(3)
        self.assertEqual(
            cmd.progressions_en_retard(
                self.co, aujourdhui=timezone.localdate(), delai_jours=14),
            [])
        self._vieillir(20)
        retards = cmd.progressions_en_retard(
            self.co, aujourdhui=timezone.localdate(), delai_jours=14)
        self.assertEqual([p.pk for p in retards], [self.progression.pk])

    def test_parcours_termine_ne_remonte_plus(self):
        self._vieillir(30)
        ProgressionParcours.objects.filter(pk=self.progression.pk).update(
            statut=ProgressionParcours.Statut.TERMINE)
        self.assertEqual(
            cmd.progressions_en_retard(
                self.co, aujourdhui=timezone.localdate(), delai_jours=14),
            [])

    def test_delai_lu_du_reglage_societe(self):
        ReglageRH.objects.create(
            company=self.co, rappel_parcours_apres_jours=60)
        self._vieillir(30)
        self.assertEqual(cmd._delai_societe(self.co), 60)
        self.assertEqual(
            cmd.progressions_en_retard(
                self.co, aujourdhui=timezone.localdate(), delai_jours=60),
            [])

    def test_rappel_ne_spamme_pas(self):
        from apps.notifications.models import Notification

        self._vieillir(30)
        call_command('rappels_parcours_formation', verbosity=0)
        premier = Notification.objects.filter(
            recipient=self.user, link=cmd._lien_parcours(self.progression)
        ).count()
        self.assertEqual(premier, 1)

        # Deuxième passage le MÊME jour : aucun second rappel.
        call_command('rappels_parcours_formation', verbosity=0)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.user,
                link=cmd._lien_parcours(self.progression)).count(),
            1)

    def test_dry_run_nemet_rien(self):
        from apps.notifications.models import Notification

        self._vieillir(30)
        call_command(
            'rappels_parcours_formation', '--dry-run', verbosity=0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_employe_sans_compte_nest_pas_notifiable(self):
        from apps.notifications.models import Notification

        self.employe.user = None
        self.employe.save(update_fields=['user'])
        self._vieillir(30)
        call_command('rappels_parcours_formation', verbosity=0)
        self.assertEqual(Notification.objects.count(), 0)
