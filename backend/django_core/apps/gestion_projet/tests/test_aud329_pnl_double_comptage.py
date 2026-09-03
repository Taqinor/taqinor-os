"""AUD329 — REPRODUCTION puis correctif du double-comptage de `pnl_projet`.

Le constat était requalifié PLAUSIBLE (et non CONFIRMED) : le test existant
prouvait le MÉCANISME (`cout_reel = affectations + timesheets`) mais pas que le
recouvrement survient sur des données produites par le parcours normal des
écrans. C'est donc une VÉRIFICATION D'ABORD.

Prémisse vérifiée par lecture des deux écrans réellement branchés :

* `RessourcesPage.jsx` gère les `AffectationRessource` (`tache`, `ressource`,
  `charge_jours`) — valorisées PLANIFIÉ par `selectors._mo_reelle`
  (`charge_jours × 8 h × cout_horaire`) ;
* `TempsPage.jsx` poste ses `Timesheet` avec `{projet, tache, ressource, date,
  heures}` (`TempsPage.jsx`, appels `créer une saisie`) — dont le `cout` est
  calculé côté serveur (`TimesheetSerializer`, lecture seule) et agrégé RÉEL
  par `selectors.synthese_temps_projet`.

Les deux écrans écrivent donc bien sur la MÊME tâche et la MÊME ressource : le
recouvrement est atteignable par le flux normal, pas seulement en laboratoire.
Les classes ci-dessous construisent cette fixture réaliste et mesurent le
recouvrement, puis verrouillent le comportement corrigé.

Règle retenue (option 1 de la fiche) : le pointage fait foi POUR LA RESSOURCE
POINTÉE ; l'affectation reste le repli pour les ressources non pointées.

Run :
    docker compose exec django_core python manage.py test \
        apps.gestion_projet.tests.test_aud329_pnl_double_comptage -v 2
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    AffectationRessource, Projet, RessourceProfil, Tache, Timesheet,
)
from authentication.models import Company


class _Fixture(TestCase):
    """Fixture construite comme les DEUX écrans le feraient réellement."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud329-co', defaults={'nom': 'AUD329 Co'})[0]
        self.projet = Projet.objects.create(
            company=self.co, code='P-AUD329', nom='Projet AUD329')
        self.tache = Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Pose', ordre=1)
        self.technicien = RessourceProfil.objects.create(
            company=self.co, nom='Technicien', cout_horaire=Decimal('100'))

    def _affecter(self, ressource=None, charge=Decimal('2')):
        """Ce que fait RessourcesPage : affecter une ressource à une tâche."""
        return AffectationRessource.objects.create(
            company=self.co, tache=self.tache,
            ressource=ressource or self.technicien,
            date_debut=date(2026, 4, 6), date_fin=date(2026, 4, 7),
            charge_jours=charge)

    def _pointer(self, ressource=None, heures=Decimal('5'), tache=True):
        """Ce que fait TempsPage : pointer des heures réelles sur la tâche.

        Le `cout` est calculé côté serveur exactement comme le sérialiseur :
        `services.cout_timesheet(ressource, heures)`.
        """
        from apps.gestion_projet.services import cout_timesheet
        res = ressource or self.technicien
        return Timesheet.objects.create(
            company=self.co, projet=self.projet,
            tache=self.tache if tache else None, ressource=res,
            date=date(2026, 4, 6), heures=heures,
            cout=cout_timesheet(res, heures))


class ReproductionDuRecouvrementTests(_Fixture):
    """VÉRIFICATION : le recouvrement existe-t-il sur ce flux ?"""

    def test_les_deux_ecrans_produisent_bien_un_recouvrement(self):
        self._affecter()      # 2 j × 8 h × 100 = 1600 (PLANIFIÉ)
        self._pointer()       # 5 h × 100 = 500 (RÉEL)

        data = selectors.pnl_projet(self.co, self.projet)

        # Les deux sources décrivent LE MÊME travail (même tâche, même
        # ressource, même période) : leur somme brute (2100) surestime le coût.
        self.assertEqual(data['cout_reel_affectations'], Decimal('1600.00'))
        self.assertEqual(data['cout_reel_timesheets'], Decimal('500.00'))
        self.assertEqual(
            data['cout_reel_mo_deja_pointee'], Decimal('1600.00'))
        self.assertNotEqual(
            data['cout_reel'],
            data['cout_reel_affectations'] + data['cout_reel_timesheets'])
        # Le pointage fait foi pour cette ressource.
        self.assertEqual(data['cout_reel'], Decimal('500.00'))

    def test_la_somme_se_reconcilie_toujours(self):
        self._affecter()
        self._pointer()

        data = selectors.pnl_projet(self.co, self.projet)

        self.assertEqual(
            data['cout_reel'],
            data['cout_reel_affectations']
            - data['cout_reel_mo_deja_pointee']
            + data['cout_reel_timesheets'])

    def test_pointage_sans_tache_compte_aussi_pour_la_ressource(self):
        """TempsPage envoie `tache: undefined` sur une ligne projet."""
        self._affecter()
        self._pointer(tache=False)

        data = selectors.pnl_projet(self.co, self.projet)

        self.assertEqual(data['cout_reel'], Decimal('500.00'))


class PasDeRecouvrementTests(_Fixture):
    """Sans recouvrement, RIEN ne change : les deux sources restent additives."""

    def test_affectation_seule_reste_valorisee_au_planifie(self):
        self._affecter()

        data = selectors.pnl_projet(self.co, self.projet)

        self.assertEqual(data['cout_reel_mo_deja_pointee'], Decimal('0.00'))
        self.assertEqual(data['cout_reel'], Decimal('1600.00'))

    def test_pointage_seul_reste_valorise_au_reel(self):
        self._pointer()

        data = selectors.pnl_projet(self.co, self.projet)

        self.assertEqual(data['cout_reel_affectations'], Decimal('0.00'))
        self.assertEqual(data['cout_reel'], Decimal('500.00'))

    def test_deux_ressources_distinctes_ne_se_deduisent_pas_lune_lautre(self):
        """Ressource A affectée seulement, ressource B pointée seulement."""
        planificateur = RessourceProfil.objects.create(
            company=self.co, nom='Planificateur', cout_horaire=Decimal('50'))
        self._affecter(ressource=planificateur, charge=Decimal('1'))  # 400
        self._pointer(ressource=self.technicien, heures=Decimal('5'))  # 500

        data = selectors.pnl_projet(self.co, self.projet)

        self.assertEqual(data['cout_reel_affectations'], Decimal('400.00'))
        self.assertEqual(data['cout_reel_timesheets'], Decimal('500.00'))
        self.assertEqual(data['cout_reel_mo_deja_pointee'], Decimal('0.00'))
        # Deux travaux DIFFÉRENTS : leur somme est légitime.
        self.assertEqual(data['cout_reel'], Decimal('900.00'))

    def test_seule_la_ressource_pointee_est_deduite(self):
        planificateur = RessourceProfil.objects.create(
            company=self.co, nom='Planificateur', cout_horaire=Decimal('50'))
        self._affecter(ressource=planificateur, charge=Decimal('1'))   # 400
        self._affecter(ressource=self.technicien, charge=Decimal('2'))  # 1600
        self._pointer(ressource=self.technicien, heures=Decimal('5'))   # 500

        data = selectors.pnl_projet(self.co, self.projet)

        self.assertEqual(data['cout_reel_affectations'], Decimal('2000.00'))
        self.assertEqual(
            data['cout_reel_mo_deja_pointee'], Decimal('1600.00'))
        # 400 (planifié, non pointé) + 500 (réel pointé).
        self.assertEqual(data['cout_reel'], Decimal('900.00'))

    def test_projet_dune_autre_societe_jamais_lu(self):
        autre = Company.objects.get_or_create(
            slug='aud329-autre', defaults={'nom': 'Autre'})[0]
        projet_autre = Projet.objects.create(
            company=autre, code='P-AUTRE329', nom='Autre')
        tache_autre = Tache.objects.create(
            company=autre, projet=projet_autre, libelle='T', ordre=1)
        ressource_autre = RessourceProfil.objects.create(
            company=autre, nom='R autre', cout_horaire=Decimal('100'))
        Timesheet.objects.create(
            company=autre, projet=projet_autre, tache=tache_autre,
            ressource=ressource_autre, date=date(2026, 4, 6),
            heures=Decimal('5'), cout=Decimal('500'))
        self._affecter()

        data = selectors.pnl_projet(self.co, self.projet)

        self.assertEqual(data['cout_reel_mo_deja_pointee'], Decimal('0.00'))
        self.assertEqual(data['cout_reel'], Decimal('1600.00'))
