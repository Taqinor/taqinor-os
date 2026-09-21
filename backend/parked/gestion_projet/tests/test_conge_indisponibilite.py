"""Tests congés RH approuvés → indisponibilités planning (XPRJ9).

Couvre : la validation d'une ``rh.DemandeConge`` crée/synchronise
l'``Indisponibilite`` (type congé) de la ``RessourceProfil`` liée au même
utilisateur SANS saisie manuelle, sans doublon sur re-validation
(idempotent), l'annulation d'un congé validé CLÔT (supprime) l'indisponibilité,
un utilisateur sans ``RessourceProfil`` est ignoré proprement.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.gestion_projet.models import Indisponibilite, RessourceProfil
from apps.rh import services as rh_services
from apps.rh.models import DemandeConge, DossierEmploye, TypeAbsence

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', company=company,
        role_legacy='responsable')


class CongeIndisponibiliteTests(TestCase):
    def setUp(self):
        self.co = make_company('gp-conge-svc', 'S')
        self.user = make_user(self.co, 'conge-svc')
        self.employe = DossierEmploye.objects.create(
            company=self.co, user=self.user, matricule='M-100', nom='N',
            prenom='P')
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='R', user=self.user)
        self.type_absence = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé')
        self.demande = DemandeConge.objects.create(
            company=self.co, employe=self.employe,
            type_absence=self.type_absence,
            date_debut=date(2026, 8, 3), date_fin=date(2026, 8, 7),
            jours=Decimal('5'))

    def test_validation_cree_indisponibilite(self):
        rh_services.valider_demande(self.demande)
        indispo = Indisponibilite.objects.get(
            ressource=self.ressource, motif=f'conge_rh:{self.demande.id}')
        self.assertEqual(indispo.type_indispo, Indisponibilite.TypeIndispo.CONGE)
        self.assertEqual(indispo.date_debut, date(2026, 8, 3))
        self.assertEqual(indispo.date_fin, date(2026, 8, 7))

    def test_revalidation_ne_duplique_pas(self):
        rh_services.valider_demande(self.demande)
        # Force re-signal en rappelant directement le synchroniseur (simulateur
        # de re-déclenchement) — le compteur ne doit jamais dépasser 1.
        from apps.gestion_projet.services import synchroniser_indisponibilite_conge
        synchroniser_indisponibilite_conge(self.demande, annule=False)
        self.assertEqual(
            Indisponibilite.objects.filter(
                ressource=self.ressource,
                motif=f'conge_rh:{self.demande.id}').count(),
            1)

    def test_annulation_ferme_indisponibilite(self):
        rh_services.valider_demande(self.demande)
        self.assertTrue(
            Indisponibilite.objects.filter(
                ressource=self.ressource,
                motif=f'conge_rh:{self.demande.id}').exists())
        rh_services.annuler_demande(self.demande)
        self.assertFalse(
            Indisponibilite.objects.filter(
                ressource=self.ressource,
                motif=f'conge_rh:{self.demande.id}').exists())

    def test_annulation_demande_non_validee_ne_leve_pas(self):
        # La demande est encore SOUMISE : annuler ne doit ni lever, ni créer
        # d'indisponibilité fantôme.
        rh_services.annuler_demande(self.demande)
        self.assertEqual(
            Indisponibilite.objects.filter(ressource=self.ressource).count(),
            0)

    def test_utilisateur_sans_ressource_profil_ignore(self):
        user_sans_ressource = make_user(self.co, 'conge-sans-res')
        employe2 = DossierEmploye.objects.create(
            company=self.co, user=user_sans_ressource, matricule='M-200',
            nom='N2', prenom='P2')
        demande2 = DemandeConge.objects.create(
            company=self.co, employe=employe2, type_absence=self.type_absence,
            date_debut=date(2026, 9, 1), date_fin=date(2026, 9, 2),
            jours=Decimal('2'))
        # Ne doit jamais lever, même si aucune RessourceProfil n'existe.
        rh_services.valider_demande(demande2)
        self.assertEqual(
            Indisponibilite.objects.filter(company=self.co).count(), 0)
