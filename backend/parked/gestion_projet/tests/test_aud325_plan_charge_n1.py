"""AUD325 — N+1 sur le plan de charge / nivellement (écran Ressources).

`plan_de_charge` préchargeait en bloc équipes, membres et TOUTES les
affectations, mais appelait `indisponibilites_sur_periode(ressource, …)` DANS
la boucle `for ressource in ressources:` — une requête `Indisponibilite` PAR
ressource, sans préchargement, contrairement aux affectations juste à côté.
`nivellement_charge` (bouton « Nivellement ») héritait du même coût. Les deux
sont branchés à un écran réel (`RessourcesPage.jsx` via
`getPlanDeCharge`/`getNivellementCharge`).

Rouge d'abord : le nombre de requêtes CROISSAIT avec le nombre de ressources.
Vert : il est FIXE (3 → 15 ressources, même compte), et les valeurs calculées
sont inchangées.

Run :
    docker compose exec django_core python manage.py test \
        apps.gestion_projet.tests.test_aud325_plan_charge_n1 -v 2
"""
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.gestion_projet.models import (
    Indisponibilite, RessourceProfil,
)
from apps.gestion_projet.selectors import nivellement_charge, plan_de_charge
from authentication.models import Company

DEBUT = date(2026, 6, 1)   # lundi
FIN = date(2026, 6, 30)


class _Base(TestCase):
    SLUG = 'aud325-co'

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug=self.SLUG, defaults={'nom': 'AUD325 Co'})[0]
        self._compteur = 0

    def _peupler(self, nb):
        """`nb` ressources ACTIVES de plus, chacune avec une indisponibilité."""
        for _ in range(nb):
            ressource = RessourceProfil.objects.create(
                company=self.co, nom=f'R{self._compteur:03d}',
                cout_horaire=Decimal('0'))
            Indisponibilite.objects.create(
                company=self.co, ressource=ressource,
                type_indispo=Indisponibilite.TypeIndispo.CONGE,
                date_debut=date(2026, 6, 8), date_fin=date(2026, 6, 12))
            self._compteur += 1


class PlanDeChargeRequetesFixesTests(_Base):
    SLUG = 'aud325-req'

    def test_compte_de_requetes_independant_du_nombre_de_ressources(self):
        self._peupler(3)
        with CaptureQueriesContext(connection) as ctx3:
            plan3 = plan_de_charge(self.co, DEBUT, FIN)

        self._peupler(12)
        with CaptureQueriesContext(connection) as ctx15:
            plan15 = plan_de_charge(self.co, DEBUT, FIN)

        self.assertEqual(len(plan3['lignes']), 3)
        self.assertEqual(len(plan15['lignes']), 15)
        self.assertEqual(
            len(ctx3), len(ctx15),
            f'N+1 : {len(ctx3)} requêtes pour 3 ressources, '
            f'{len(ctx15)} pour 15.')

    def test_nivellement_herite_du_compte_fixe(self):
        self._peupler(3)
        with CaptureQueriesContext(connection) as ctx3:
            nivellement_charge(self.co, DEBUT, FIN)

        self._peupler(12)
        with CaptureQueriesContext(connection) as ctx15:
            nivellement_charge(self.co, DEBUT, FIN)

        self.assertEqual(
            len(ctx3), len(ctx15),
            f'N+1 hérité : {len(ctx3)} requêtes pour 3 ressources, '
            f'{len(ctx15)} pour 15.')


class PlanDeChargeValeursInchangeesTests(TestCase):
    """Le préchargement ne doit RIEN changer aux chiffres produits."""

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='aud325-val', defaults={'nom': 'AUD325 Val'})[0]
        self.ressource = RessourceProfil.objects.create(
            company=self.co, nom='Technicien', cout_horaire=Decimal('0'))

    def test_indisponibilite_toujours_deduite_de_la_capacite(self):
        sans_indispo = plan_de_charge(self.co, DEBUT, FIN)['lignes'][0]

        Indisponibilite.objects.create(
            company=self.co, ressource=self.ressource,
            type_indispo=Indisponibilite.TypeIndispo.CONGE,
            date_debut=date(2026, 6, 8), date_fin=date(2026, 6, 12))
        avec_indispo = plan_de_charge(self.co, DEBUT, FIN)['lignes'][0]

        # Une semaine ouvrée complète (5 jours) retranchée.
        self.assertEqual(avec_indispo['jours_indispo'], 5)
        self.assertEqual(
            sans_indispo['jours_ouvres'], avec_indispo['jours_ouvres'])
        self.assertEqual(
            avec_indispo['capacite_heures'],
            sans_indispo['capacite_heures'] - 5 * 8)

    def test_indisponibilite_hors_fenetre_ignoree(self):
        Indisponibilite.objects.create(
            company=self.co, ressource=self.ressource,
            type_indispo=Indisponibilite.TypeIndispo.CONGE,
            date_debut=date(2026, 8, 1), date_fin=date(2026, 8, 5))

        ligne = plan_de_charge(self.co, DEBUT, FIN)['lignes'][0]

        self.assertEqual(ligne['jours_indispo'], 0)

    def test_deux_indisponibilites_sont_toutes_deux_deduites(self):
        for debut, fin in ((date(2026, 6, 8), date(2026, 6, 9)),
                           (date(2026, 6, 15), date(2026, 6, 16))):
            Indisponibilite.objects.create(
                company=self.co, ressource=self.ressource,
                type_indispo=Indisponibilite.TypeIndispo.CONGE,
                date_debut=debut, date_fin=fin)

        ligne = plan_de_charge(self.co, DEBUT, FIN)['lignes'][0]

        self.assertEqual(ligne['jours_indispo'], 4)

    def test_indisponibilite_dune_autre_societe_jamais_lue(self):
        autre = Company.objects.get_or_create(
            slug='aud325-autre', defaults={'nom': 'Autre'})[0]
        ressource_autre = RessourceProfil.objects.create(
            company=autre, nom='Technicien B', cout_horaire=Decimal('0'))
        Indisponibilite.objects.create(
            company=autre, ressource=ressource_autre,
            type_indispo=Indisponibilite.TypeIndispo.CONGE,
            date_debut=date(2026, 6, 8), date_fin=date(2026, 6, 12))

        lignes = plan_de_charge(self.co, DEBUT, FIN)['lignes']

        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['jours_indispo'], 0)
