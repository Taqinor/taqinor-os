"""AUDV16/GP-4 — N+1 sur `tableau_portefeuille` (écran Portefeuille chantiers).

`tableau_portefeuille` appelait, DANS sa boucle `for projet in projets:`,
`rollup_avancement`/`retards_projet`/`pnl_projet`/un aggregate `charge`/un
lookup « dernier point » — un jeu complet de requêtes PAR PROJET (~10-14,
mesuré) au lieu d'un préchargement en bloc (même défaut qu'AUD325
`plan_de_charge`, corrigé avec la même stratégie ici).

Rouge d'abord : le nombre de requêtes CROISSAIT avec le nombre de projets.
Vert : il est FIXE (3 → 12 projets, même compte), et les VALEURS restent
identiques à ce que renvoient encore, projet par projet, les sélecteurs non
vectorisés `rollup_avancement`/`retards_projet`/`pnl_projet` (non touchés par
cette tâche).

Run :
    docker compose exec django_core python manage.py test \
        apps.gestion_projet.tests.test_audv16_portefeuille_n1 -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from authentication.models import Company

from apps.gestion_projet import selectors
from apps.gestion_projet.models import (
    AffectationRessource,
    Jalon,
    PointAvancement,
    Projet,
    RessourceProfil,
    Tache,
    Timesheet,
)

AUJOURD_HUI = date.today()


class _Base(TestCase):
    SLUG = 'audv16-co'

    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug=self.SLUG, defaults={'nom': 'AUDV16 Co'})[0]
        self._compteur = 0

    def _peupler(self, nb):
        """`nb` projets de plus, chacun avec une tâche en retard, un jalon en
        retard, une affectation ET une feuille de temps pour la MÊME
        ressource (exerce le déca de double-comptage AUD329) et un point
        d'avancement — assez pour exercer les 5 tables préchargées."""
        for _ in range(nb):
            self._compteur += 1
            projet = Projet.objects.create(
                company=self.co, code=f'P-{self._compteur:03d}',
                nom=f'Projet {self._compteur}')
            tache = Tache.objects.create(
                company=self.co, projet=projet, libelle='T1', ordre=1,
                charge_estimee=Decimal('10'), avancement_pct=40,
                date_fin_prevue=AUJOURD_HUI - timedelta(days=2))
            Jalon.objects.create(
                company=self.co, projet=projet, libelle='J1',
                date_prevue=AUJOURD_HUI - timedelta(days=1))
            ressource = RessourceProfil.objects.create(
                company=self.co, nom=f'R{self._compteur}',
                cout_horaire=Decimal('100'))
            AffectationRessource.objects.create(
                company=self.co, tache=tache, ressource=ressource,
                date_debut=AUJOURD_HUI, date_fin=AUJOURD_HUI,
                charge_jours=Decimal('1'))
            Timesheet.objects.create(
                company=self.co, projet=projet, ressource=ressource,
                date=AUJOURD_HUI, heures=Decimal('2'), cout=Decimal('150'))
            PointAvancement.objects.create(
                company=self.co, projet=projet,
                sante=PointAvancement.Sante.ORANGE, date_point=AUJOURD_HUI)


class TableauPortefeuilleRequetesFixesTests(_Base):
    def test_compte_de_requetes_independant_du_nombre_de_projets(self):
        self._peupler(3)
        with CaptureQueriesContext(connection) as ctx3:
            portefeuille3 = selectors.tableau_portefeuille(self.co)

        self._peupler(9)
        with CaptureQueriesContext(connection) as ctx12:
            portefeuille12 = selectors.tableau_portefeuille(self.co)

        self.assertEqual(portefeuille3['nb_projets'], 3)
        self.assertEqual(portefeuille12['nb_projets'], 12)
        self.assertEqual(
            len(ctx3), len(ctx12),
            f'N+1 : {len(ctx3)} requêtes pour 3 projets, '
            f'{len(ctx12)} pour 12.')


class TableauPortefeuilleCorrectnessTests(_Base):
    """La vectorisation ne doit rien changer aux VALEURS : chaque ligne doit
    rester identique à ce que renvoient encore, projet par projet,
    `rollup_avancement`/`retards_projet`/`pnl_projet` (non touchés)."""

    def test_valeurs_identiques_aux_selecteurs_par_projet(self):
        self._peupler(4)
        data = selectors.tableau_portefeuille(self.co)
        self.assertEqual(len(data['projets']), 4)
        projets_par_id = {
            p.id: p for p in Projet.objects.filter(company=self.co)}
        for ligne in data['projets']:
            projet = projets_par_id[ligne['projet_id']]
            avancement = selectors.rollup_avancement(projet)
            retards = selectors.retards_projet(projet)
            pnl = selectors.pnl_projet(self.co, projet)
            self.assertEqual(
                ligne['avancement_pct'], avancement['avancement_pct'])
            self.assertEqual(
                ligne['nb_retards'],
                retards['nb_taches_en_retard']
                + retards['nb_jalons_en_retard'])
            self.assertEqual(
                ligne['nb_risques'],
                retards['nb_taches_a_risque'] + retards['nb_jalons_a_risque'])
            self.assertEqual(ligne['marge_reelle'], pnl['marge_reelle'])

    def test_charge_totale_et_derniere_sante(self):
        self._peupler(1)
        data = selectors.tableau_portefeuille(self.co)
        ligne = data['projets'][0]
        self.assertEqual(ligne['charge_totale'], Decimal('10'))
        self.assertEqual(ligne['derniere_sante'], PointAvancement.Sante.ORANGE)
        # AUD329 réconcilié : affectation 800 (1j×8h×100) − déjà pointée 800
        # (même ressource pointée sur ce projet) + timesheet 150 = 150 réel ;
        # revenu toujours 0 (dégradé cross-app) → marge réelle = -150.
        self.assertEqual(ligne['marge_reelle'], Decimal('-150.00'))

    def test_filtre_statut(self):
        self._peupler(1)
        autre = Projet.objects.create(
            company=self.co, code='P-AUTRE', nom='Autre',
            statut=Projet.Statut.TERMINE)
        data = selectors.tableau_portefeuille(
            self.co, statut=Projet.Statut.TERMINE)
        self.assertEqual(len(data['projets']), 1)
        self.assertEqual(data['projets'][0]['projet_id'], autre.id)

    def test_projet_sans_donnee_degrade_proprement(self):
        """Un projet sans tâche/jalon/affectation/point d'avancement ne doit
        jamais lever d'exception (KeyError sur les dicts préchargés)."""
        Projet.objects.create(company=self.co, code='P-VIDE', nom='Vide')
        data = selectors.tableau_portefeuille(self.co)
        self.assertEqual(len(data['projets']), 1)
        ligne = data['projets'][0]
        self.assertEqual(ligne['avancement_pct'], 0)
        self.assertEqual(ligne['nb_retards'], 0)
        self.assertEqual(ligne['nb_risques'], 0)
        self.assertEqual(ligne['charge_totale'], Decimal('0'))
        self.assertIsNone(ligne['derniere_sante'])
        self.assertEqual(ligne['marge_reelle'], Decimal('0'))
