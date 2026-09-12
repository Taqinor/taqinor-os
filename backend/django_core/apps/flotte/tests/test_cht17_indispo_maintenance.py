"""CHT17 — Camion en maintenance = indisponible au planning.

``selectors.ressource_indisponible`` (installations, FG299-303) lisait déjà
``IndisponibiliteRessource`` pour exclure une camionnette du planning, mais
rien ne posait automatiquement cette indisponibilité quand un véhicule
(``flotte.Vehicule``) passait en MAINTENANCE : rien n'empêchait de programmer
une intervention sur un camion à l'arrêt. Ce module couvre le nouveau
``installations.services.sync_indisponibilite_maintenance``, câblé depuis
``flotte.services.changer_statut_vehicule``.

Run :
    python manage.py test apps.flotte.tests.test_cht17_indispo_maintenance -v2
"""
import itertools
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.flotte.models import Vehicule
from apps.flotte.services import changer_statut_vehicule
from apps.installations.models import IndisponibiliteRessource
from apps.stock.models import EmplacementStock
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)
MOTIF_SYNC = 'sync-auto-maintenance'


def make_company(slug=None, nom=None):
    n = next(_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'cht17-co-{n}', defaults={'nom': nom or f'CHT17 Co {n}'})
    return company


def make_user(company):
    return User.objects.create_user(
        username=f'cht17-{next(_seq)}', password='x',
        role_legacy='admin', company=company)


def make_emplacement(company):
    n = next(_seq)
    return EmplacementStock.objects.create(
        company=company, nom=f'Camionnette CHT17-{n}')


def make_vehicule(company, emplacement=None, statut=Vehicule.Statut.ACTIF):
    n = next(_seq)
    return Vehicule.objects.create(
        company=company, immatriculation=f'CHT17-{n}', energie='diesel',
        statut=statut,
        emplacement_stock_id=emplacement.id if emplacement else None)


def indispos_sync(company, emplacement):
    return IndisponibiliteRessource.objects.filter(
        company=company, camionnette_id=emplacement.id, motif=MOTIF_SYNC)


class TestEntreeMaintenance(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.emplacement = make_emplacement(self.company)
        self.veh = make_vehicule(self.company, self.emplacement)

    def test_entree_maintenance_cree_une_indisponibilite(self):
        changer_statut_vehicule(
            self.veh, Vehicule.Statut.MAINTENANCE, user=self.user)
        indispos = indispos_sync(self.company, self.emplacement)
        self.assertEqual(indispos.count(), 1)
        indispo = indispos.first()
        self.assertEqual(
            indispo.type_indispo, IndisponibiliteRessource.Type.ARRET)
        self.assertEqual(indispo.date_debut, timezone.localdate())
        self.assertGreater(indispo.date_fin, timezone.localdate())

    def test_idempotence_entree_ne_duplique_pas(self):
        changer_statut_vehicule(
            self.veh, Vehicule.Statut.MAINTENANCE, user=self.user)
        # Rejouer le même appel de service directement (le second appel via
        # changer_statut_vehicule serait un no-op de statut identique).
        from apps.installations.services import (
            sync_indisponibilite_maintenance,
        )
        sync_indisponibilite_maintenance(
            self.company, self.emplacement.id, True, user=self.user)
        self.assertEqual(
            indispos_sync(self.company, self.emplacement).count(), 1)


class TestSortieMaintenance(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.emplacement = make_emplacement(self.company)
        self.veh = make_vehicule(self.company, self.emplacement)  # ACTIF
        changer_statut_vehicule(
            self.veh, Vehicule.Statut.MAINTENANCE, user=self.user)

    def test_sortie_ramene_la_date_fin_a_aujourd_hui(self):
        changer_statut_vehicule(
            self.veh, Vehicule.Statut.ACTIF, user=self.user)
        indispo = indispos_sync(self.company, self.emplacement).first()
        self.assertEqual(indispo.date_fin, timezone.localdate())

    def test_indisponibilite_manuelle_jamais_touchee(self):
        manuelle = IndisponibiliteRessource.objects.create(
            company=self.company, camionnette_id=self.emplacement.id,
            type_indispo=IndisponibiliteRessource.Type.FORMATION,
            motif='Formation sécurité — saisie manuelle',
            date_debut=timezone.localdate(),
            date_fin=timezone.localdate() + timedelta(days=30))
        changer_statut_vehicule(
            self.veh, Vehicule.Statut.ACTIF, user=self.user)
        manuelle.refresh_from_db()
        self.assertEqual(
            manuelle.date_fin, timezone.localdate() + timedelta(days=30))

    def test_idempotence_sortie_ne_leve_aucune_erreur(self):
        changer_statut_vehicule(
            self.veh, Vehicule.Statut.ACTIF, user=self.user)
        # Rejouer directement le service (deuxième « sortie ») : aucune
        # erreur, aucun doublon.
        from apps.installations.services import (
            sync_indisponibilite_maintenance,
        )
        sync_indisponibilite_maintenance(
            self.company, self.emplacement.id, False, user=self.user)
        self.assertEqual(
            indispos_sync(self.company, self.emplacement).count(), 1)


class TestVehiculeSansEmplacement(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.veh = make_vehicule(self.company, emplacement=None)

    def test_entree_maintenance_sans_emplacement_est_un_no_op(self):
        changer_statut_vehicule(
            self.veh, Vehicule.Statut.MAINTENANCE, user=self.user)
        self.assertFalse(
            IndisponibiliteRessource.objects.filter(
                company=self.company, motif=MOTIF_SYNC).exists())
