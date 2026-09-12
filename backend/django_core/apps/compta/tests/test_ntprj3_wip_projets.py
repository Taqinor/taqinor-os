"""Tests NTPRJ3 — Régularisation WIP/PCA auto-alimentée depuis les projets.

Couvre : un projet FACTURÉ EN AVANCE de son avancement génère un PCA ; un
projet en avance de PRODUCTION génère un WIP ; un écart nul ne crée rien ;
ré-exécuter la commande sur la même période ne double jamais l'écriture ; le
verrou de période est respecté ; la lecture cross-app passe par
``gestion_projet.selectors`` (jamais ses ``models``).
"""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from authentication.models import Company

from apps.compta import services
from apps.compta.models import TravauxEnCours
from apps.gestion_projet.models import Jalon, Projet, Tache

User = get_user_model()

PERIODE = '2026-03'
DATE_ARRETE = date(2026, 3, 31)


def make_company(slug, nom=None):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom or slug})
    return company


class GenererRegularisationWipProjetTests(TestCase):
    def setUp(self):
        self.co = make_company('ntprj3', 'NTPRJ3 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.projet = Projet.objects.create(
            company=self.co, code='P-NTPRJ3', nom='Chantier pilote',
            statut=Projet.Statut.EN_COURS,
            budget_total=Decimal('100000'))

    def _avancer(self, pct):
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Lot 1',
            avancement_pct=pct, charge_estimee=Decimal('10'), ordre=1)

    def _facturer(self, pct):
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 15), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal(pct))

    def test_production_en_avance_genere_un_wip(self):
        self._avancer(60)   # 60 000 produits
        self._facturer(30)  # 30 000 facturés
        reg = services.generer_regularisation_wip_projet(
            self.projet, PERIODE)
        self.assertIsNotNone(reg)
        self.assertEqual(reg.nature, TravauxEnCours.Nature.WIP)
        self.assertEqual(reg.montant, Decimal('30000.00'))
        self.assertEqual(reg.date_arrete, DATE_ARRETE)
        self.assertEqual(reg.chantier_ref, f'PROJ-{self.projet.pk}')
        self.assertIsNotNone(reg.ecriture_id)

    def test_facturation_en_avance_genere_un_pca(self):
        self._avancer(20)   # 20 000 produits
        self._facturer(50)  # 50 000 facturés
        reg = services.generer_regularisation_wip_projet(
            self.projet, PERIODE)
        self.assertIsNotNone(reg)
        self.assertEqual(reg.nature, TravauxEnCours.Nature.PCA)
        self.assertEqual(reg.montant, Decimal('30000.00'))

    def test_ecart_nul_ne_cree_rien(self):
        self._avancer(40)
        self._facturer(40)
        self.assertIsNone(
            services.generer_regularisation_wip_projet(self.projet, PERIODE))
        self.assertFalse(TravauxEnCours.objects.filter(company=self.co)
                         .exists())

    def test_idempotence_par_projet_et_periode(self):
        self._avancer(60)
        self._facturer(30)
        premier = services.generer_regularisation_wip_projet(
            self.projet, PERIODE)
        second = services.generer_regularisation_wip_projet(
            self.projet, PERIODE)
        self.assertIsNotNone(premier)
        self.assertIsNone(second)
        self.assertEqual(
            TravauxEnCours.objects.filter(company=self.co).count(), 1)

    def test_une_autre_periode_reste_regularisable(self):
        self._avancer(60)
        self._facturer(30)
        services.generer_regularisation_wip_projet(self.projet, PERIODE)
        suivante = services.generer_regularisation_wip_projet(
            self.projet, '2026-04')
        self.assertIsNotNone(suivante)
        self.assertEqual(suivante.date_arrete, date(2026, 4, 30))

    def test_periode_invalide_refusee_en_francais(self):
        with self.assertRaises(ValueError) as ctx:
            services.generer_regularisation_wip_projet(self.projet, '2026/03')
        self.assertIn('AAAA-MM', str(ctx.exception))

    def test_periode_verrouillee_refuse_l_ecriture(self):
        from django.core.exceptions import ValidationError

        from apps.compta.models import PeriodeComptable

        PeriodeComptable.objects.create(
            company=self.co, date_debut=date(2026, 3, 1),
            date_fin=DATE_ARRETE, verrouillee=True)
        self._avancer(60)
        self._facturer(30)
        with self.assertRaises(ValidationError):
            services.generer_regularisation_wip_projet(self.projet, PERIODE)


class RegulariserWipProjetsCommandTests(TestCase):
    def setUp(self):
        self.co = make_company('ntprj3-cmd', 'NTPRJ3 Cmd')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.projet = Projet.objects.create(
            company=self.co, code='P-CMD', nom='Chantier commande',
            statut=Projet.Statut.EN_COURS, budget_total=Decimal('50000'))
        Tache.objects.create(
            company=self.co, projet=self.projet, libelle='Lot',
            avancement_pct=80, charge_estimee=Decimal('10'), ordre=1)
        Jalon.objects.create(
            company=self.co, projet=self.projet, libelle='Acompte',
            date_prevue=date(2026, 1, 15), statut=Jalon.Statut.ATTEINT,
            facturation_pct=Decimal('20'))

    def _run(self, *extra):
        out = StringIO()
        call_command(
            'regulariser_wip_projets', '--company', self.co.slug,
            '--periode', PERIODE, *extra, stdout=out)
        return out.getvalue()

    def test_la_commande_cree_puis_ne_double_pas(self):
        self._run()
        self.assertEqual(
            TravauxEnCours.objects.filter(company=self.co).count(), 1)
        reg = TravauxEnCours.objects.get(company=self.co)
        self.assertEqual(reg.nature, TravauxEnCours.Nature.WIP)
        self.assertEqual(reg.montant, Decimal('30000.00'))

        self._run()
        self.assertEqual(
            TravauxEnCours.objects.filter(company=self.co).count(), 1)

    def test_dry_run_n_ecrit_rien(self):
        sortie = self._run('--dry-run')
        self.assertIn('WIP', sortie)
        self.assertFalse(
            TravauxEnCours.objects.filter(company=self.co).exists())

    def test_projet_brouillon_hors_perimetre(self):
        self.projet.statut = Projet.Statut.BROUILLON
        self.projet.save(update_fields=['statut'])
        self._run()
        self.assertFalse(
            TravauxEnCours.objects.filter(company=self.co).exists())

    def test_isolation_societe(self):
        autre = make_company('ntprj3-b', 'NTPRJ3 B')
        services.seed_plan_comptable(autre)
        services.seed_journaux(autre)
        projet_b = Projet.objects.create(
            company=autre, code='P-B', nom='Projet B',
            statut=Projet.Statut.EN_COURS, budget_total=Decimal('10000'))
        Tache.objects.create(
            company=autre, projet=projet_b, libelle='Lot B',
            avancement_pct=90, charge_estimee=Decimal('5'), ordre=1)
        self._run()
        self.assertFalse(
            TravauxEnCours.objects.filter(company=autre).exists())

    def test_periode_invalide_refusee_par_la_commande(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                'regulariser_wip_projets', '--company', self.co.slug,
                '--periode', 'mars-2026', stdout=StringIO())
