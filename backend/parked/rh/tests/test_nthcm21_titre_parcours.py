"""Tests NTHCM21 — titre délivré par un parcours (habilitation/certification).

Couvre :
* compléter un parcours lié à une habilitation la CRÉE avec la bonne échéance ;
* un titre encore valide est PROLONGÉ depuis sa fin (les mois restants ne sont
  pas perdus) ;
* une re-complétion (retake) ne duplique jamais le titre ;
* un parcours SANS titre lié n'a aucun effet secondaire ;
* une certification (FG174) suit exactement le même chemin ;
* déclarer les deux familles à la fois est refusé.

Horloge FIGÉE partout (`aujourdhui=`) — aucune date du jour lue en vrai.
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from authentication.models import Company
from apps.rh import services
from apps.rh.models import (
    Certification,
    DossierEmploye,
    EtapeParcours,
    Habilitation,
    ParcoursFormation,
    ProgressionParcours,
)

JOUR_FIGE = date(2026, 4, 10)


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TitreDelivreParcoursTests(TestCase):
    def setUp(self):
        self.co = make_company('nthcm21-a', 'A')
        self.employe = DossierEmploye.objects.create(
            company=self.co, matricule='T-001', nom='Ouazzani', prenom='O')

    def _parcours(self, **kwargs):
        parcours = ParcoursFormation.objects.create(
            company=self.co, titre=kwargs.pop('titre', 'Habilitation BR'),
            **kwargs)
        EtapeParcours.objects.create(
            company=self.co, parcours=parcours, ordre=1, titre='Lecture',
            type_contenu='lien_externe', url_externe='https://exemple.ma/a')
        return parcours

    def _terminer(self, parcours, aujourdhui=JOUR_FIGE):
        progression, _ = ProgressionParcours.objects.get_or_create(
            company=self.co, parcours=parcours, employe=self.employe)
        for etape in parcours.etapes.all():
            services.marquer_etape_parcours(
                progression, etape, aujourdhui=aujourdhui)
        progression.refresh_from_db()
        return progression

    def test_completion_cree_lhabilitation_avec_la_bonne_echeance(self):
        parcours = self._parcours(habilitation_type='br', validite_mois=36)
        progression = self._terminer(parcours)
        self.assertEqual(progression.statut, 'termine')
        habilitation = Habilitation.objects.get(
            employe=self.employe, type_habilitation='br')
        self.assertEqual(habilitation.date_obtention, JOUR_FIGE)
        self.assertEqual(habilitation.date_validite, date(2029, 4, 10))
        self.assertEqual(habilitation.company_id, self.co.id)
        self.assertTrue(habilitation.actif)

    def test_titre_encore_valide_est_prolonge_depuis_sa_fin(self):
        Habilitation.objects.create(
            company=self.co, employe=self.employe, type_habilitation='br',
            date_obtention=date(2025, 1, 1), date_validite=date(2027, 1, 1))
        parcours = self._parcours(habilitation_type='br', validite_mois=12)
        self._terminer(parcours)
        habilitation = Habilitation.objects.get(
            employe=self.employe, type_habilitation='br')
        # Prolongé depuis 2027-01-01, pas depuis aujourd'hui.
        self.assertEqual(habilitation.date_validite, date(2028, 1, 1))

    def test_titre_expire_repart_daujourdhui(self):
        Habilitation.objects.create(
            company=self.co, employe=self.employe, type_habilitation='br',
            date_obtention=date(2020, 1, 1), date_validite=date(2021, 1, 1))
        parcours = self._parcours(habilitation_type='br', validite_mois=12)
        self._terminer(parcours)
        habilitation = Habilitation.objects.get(
            employe=self.employe, type_habilitation='br')
        self.assertEqual(habilitation.date_validite, date(2027, 4, 10))

    def test_retake_ne_duplique_pas(self):
        parcours = self._parcours(habilitation_type='br', validite_mois=36)
        progression = self._terminer(parcours)
        etape = parcours.etapes.first()
        # Retake : on décoche puis on recoche — une seule ligne d'habilitation.
        services.devalider_etape_parcours(
            progression, etape, aujourdhui=JOUR_FIGE)
        services.marquer_etape_parcours(
            progression, etape, aujourdhui=JOUR_FIGE)
        self.assertEqual(
            Habilitation.objects.filter(
                employe=self.employe, type_habilitation='br').count(), 1)

    def test_recalcul_sur_un_parcours_deja_termine_ne_reprolonge_pas(self):
        parcours = self._parcours(habilitation_type='br', validite_mois=12)
        progression = self._terminer(parcours)
        echeance = Habilitation.objects.get(
            employe=self.employe, type_habilitation='br').date_validite
        services.recalculer_progression_parcours(
            progression, aujourdhui=JOUR_FIGE)
        self.assertEqual(
            Habilitation.objects.get(
                employe=self.employe,
                type_habilitation='br').date_validite, echeance)

    def test_parcours_sans_titre_na_aucun_effet(self):
        parcours = self._parcours(titre='Accueil')
        self._terminer(parcours)
        self.assertEqual(Habilitation.objects.count(), 0)
        self.assertEqual(Certification.objects.count(), 0)

    def test_certification_suit_le_meme_chemin(self):
        parcours = self._parcours(
            titre='Travail en hauteur',
            certification_type='travail_hauteur', validite_mois=24)
        self._terminer(parcours)
        certification = Certification.objects.get(
            employe=self.employe, type_certification='travail_hauteur')
        self.assertEqual(certification.date_validite, date(2028, 4, 10))

    def test_les_deux_familles_a_la_fois_refusees(self):
        parcours = ParcoursFormation(
            company=self.co, titre='Incohérent',
            habilitation_type='br', certification_type='harnais',
            validite_mois=12)
        with self.assertRaises(ValidationError):
            parcours.full_clean()

    def test_titre_sans_validite_refuse(self):
        parcours = ParcoursFormation(
            company=self.co, titre='Sans validité', habilitation_type='br')
        with self.assertRaises(ValidationError):
            parcours.full_clean()
