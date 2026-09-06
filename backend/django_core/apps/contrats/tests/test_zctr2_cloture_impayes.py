"""Tests ZCTR2 — Clôture (suspension) automatique des contrats impayés.

Couvre :
- Un contrat ACTIF rattaché à un ``PlanRecurrent`` avec ``delai_cloture_auto_
  jours`` dont une facture de cycle est impayée depuis PLUS que le délai est
  suspendu automatiquement, une seule fois, avec trace (chatter) + notif.
- Un contrat à jour (facture payée / dans le délai) reste actif.
- ``delai_cloture_auto_jours`` NULL = jamais de clôture auto (no-op).
- Sans plan rattaché = jamais de clôture auto (no-op).
- Idempotence : re-run n'ajoute pas une seconde entrée de chatter.
- Isolation multi-société (tenant) : un contrat d'une autre société n'est
  jamais touché par ``cloturer_contrats_impayes(company=...)``.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat,
    ContratActivity,
    EcheancierContrat,
    LigneEcheance,
    PlanRecurrent,
)
from apps.crm.models import Client
from apps.ventes.models import Facture

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_contrat(company, *, plan=None, montant="12000"):
    return Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=Decimal(montant),
        type_contrat="om", statut=Contrat.Statut.ACTIF,
        plan_recurrent=plan,
        date_debut=timezone.localdate() - timedelta(days=90))


def make_facture_impayee(company, client, *, montant="1000", jours_retard=45):
    today = timezone.localdate()
    return Facture.objects.create(
        company=company, client=client, statut=Facture.Statut.EMISE,
        taux_tva=Decimal("20"), montant_ttc=Decimal(montant),
        date_echeance=today - timedelta(days=jours_retard))


def make_ligne_facturee(company, contrat, facture, *, montant="1000"):
    echeancier = EcheancierContrat.objects.create(
        company=company, contrat=contrat,
        periodicite=EcheancierContrat.Periodicite.MENSUELLE,
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
    return LigneEcheance.objects.create(
        company=company, echeancier=echeancier, numero=1,
        date_echeance=timezone.localdate() - timedelta(days=45),
        montant=Decimal(montant), facture_id=facture.id)


class ClotureContratsImpayesTests(TestCase):
    def setUp(self):
        self.co = make_company("zctr2-co", "Zctr2Co")
        self.client_obj = Client.objects.create(
            company=self.co, nom="Client", prenom="Impaye",
            telephone="+212600000010")
        self.plan = PlanRecurrent.objects.create(
            company=self.co, nom="Mensuel délai 30j",
            unite=PlanRecurrent.Unite.MENSUEL, intervalle=1,
            delai_cloture_auto_jours=30)

    def test_contrat_impaye_au_dela_du_delai_est_suspendu(self):
        contrat = make_contrat(self.co, plan=self.plan)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=45)
        make_ligne_facturee(self.co, contrat, facture)

        suspendus = services.cloturer_contrats_impayes(self.co)

        self.assertEqual(len(suspendus), 1)
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.SUSPENDU)
        self.assertTrue(
            ContratActivity.objects.filter(
                contrat=contrat, field='statut',
                new_value=Contrat.Statut.SUSPENDU).exists())

    def test_contrat_a_jour_reste_actif(self):
        contrat = make_contrat(self.co, plan=self.plan)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=45)
        facture.statut = Facture.Statut.PAYEE
        facture.save(update_fields=['statut'])
        make_ligne_facturee(self.co, contrat, facture)

        suspendus = services.cloturer_contrats_impayes(self.co)

        self.assertEqual(suspendus, [])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_impaye_dans_le_delai_reste_actif(self):
        contrat = make_contrat(self.co, plan=self.plan)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=10)
        make_ligne_facturee(self.co, contrat, facture)

        suspendus = services.cloturer_contrats_impayes(self.co)

        self.assertEqual(suspendus, [])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_delai_null_ne_cloture_jamais(self):
        plan_sans_delai = PlanRecurrent.objects.create(
            company=self.co, nom="Sans délai",
            unite=PlanRecurrent.Unite.MENSUEL, intervalle=1,
            delai_cloture_auto_jours=None)
        contrat = make_contrat(self.co, plan=plan_sans_delai)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=9999)
        make_ligne_facturee(self.co, contrat, facture)

        suspendus = services.cloturer_contrats_impayes(self.co)

        self.assertEqual(suspendus, [])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_sans_plan_rattache_ne_cloture_jamais(self):
        contrat = make_contrat(self.co, plan=None)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=9999)
        make_ligne_facturee(self.co, contrat, facture)

        suspendus = services.cloturer_contrats_impayes(self.co)

        self.assertEqual(suspendus, [])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.ACTIF)

    def test_idempotence_rerun_meme_jour(self):
        contrat = make_contrat(self.co, plan=self.plan)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=45)
        make_ligne_facturee(self.co, contrat, facture)

        services.cloturer_contrats_impayes(self.co)
        suspendus_2 = services.cloturer_contrats_impayes(self.co)

        self.assertEqual(suspendus_2, [])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.SUSPENDU)
        self.assertEqual(
            ContratActivity.objects.filter(
                contrat=contrat, field='statut',
                new_value=Contrat.Statut.SUSPENDU).count(),
            1)

    def test_isolation_multi_societe(self):
        autre_co = make_company("zctr2-autre", "Zctr2Autre")
        autre_client = Client.objects.create(
            company=autre_co, nom="Autre", prenom="Client",
            telephone="+212600000011")
        autre_plan = PlanRecurrent.objects.create(
            company=autre_co, nom="Mensuel délai 30j",
            unite=PlanRecurrent.Unite.MENSUEL, intervalle=1,
            delai_cloture_auto_jours=30)
        autre_contrat = make_contrat(autre_co, plan=autre_plan)
        autre_facture = make_facture_impayee(
            autre_co, autre_client, jours_retard=45)
        make_ligne_facturee(autre_co, autre_contrat, autre_facture)

        contrat = make_contrat(self.co, plan=self.plan)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=45)
        make_ligne_facturee(self.co, contrat, facture)

        suspendus = services.cloturer_contrats_impayes(self.co)

        self.assertEqual(len(suspendus), 1)
        self.assertEqual(suspendus[0].id, contrat.id)
        autre_contrat.refresh_from_db()
        self.assertEqual(autre_contrat.statut, Contrat.Statut.ACTIF)


class SuspensionGeleEcheancierTests(TestCase):
    """AUD182 — la suspension pour impayé GÈLE l'échéancier (et sort du MRR).

    `_appliquer_suspension_impaye` ne changeait que `Contrat.statut`, alors que
    le beat quotidien ne filtre QUE sur l'échéancier : le lendemain de la
    suspension, une NOUVELLE facture ÉMISE était produite pour ce même contrat,
    jamais payée, aggravant `jours_impaye` au passage suivant.
    """

    def setUp(self):
        self.co = make_company("aud182-co", "Aud182Co")
        self.client_obj = Client.objects.create(
            company=self.co, nom="Client", prenom="Aud182",
            telephone="+212600000012")
        self.plan = PlanRecurrent.objects.create(
            company=self.co, nom="Mensuel délai 30j",
            unite=PlanRecurrent.Unite.MENSUEL, intervalle=1,
            delai_cloture_auto_jours=30)
        self.contrat = make_contrat(self.co, plan=self.plan)
        facture = make_facture_impayee(
            self.co, self.client_obj, jours_retard=45)
        self.ligne_facturee = make_ligne_facturee(
            self.co, self.contrat, facture)
        self.echeancier = self.ligne_facturee.echeancier
        # Une échéance DUE non encore facturée : c'est elle que le beat
        # ramasserait au passage suivant.
        self.ligne_due = LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=2,
            date_echeance=timezone.localdate(), montant=Decimal("1000"))

    def _suspendre(self):
        suspendus = services.cloturer_contrats_impayes(self.co)
        self.assertEqual(len(suspendus), 1)
        self.contrat.refresh_from_db()
        self.echeancier.refresh_from_db()

    def test_suspension_gele_l_echeancier(self):
        self.assertTrue(self.echeancier.facturation_active)
        self._suspendre()
        self.assertEqual(self.contrat.statut, Contrat.Statut.SUSPENDU)
        self.assertFalse(self.echeancier.facturation_active)
        self.assertTrue(self.echeancier.gele_par_suspension)

    def test_beat_ne_facture_plus_un_contrat_suspendu(self):
        from apps.contrats import scheduled
        self._suspendre()
        avant = Facture.objects.filter(company=self.co).count()
        scheduled.generer_factures_recurrentes_dues()
        self.assertEqual(
            Facture.objects.filter(company=self.co).count(), avant)
        self.ligne_due.refresh_from_db()
        self.assertIsNone(self.ligne_due.facture_id)

    def test_mrr_cesse_de_compter_un_contrat_suspendu(self):
        from apps.contrats import selectors
        self.echeancier.montant_total = Decimal("1200")
        self.echeancier.save(update_fields=["montant_total"])
        self.assertEqual(selectors.mrr_contrats(self.co), Decimal("1200.00"))
        self.assertEqual(
            selectors.mrr_contrat_actif(self.contrat), Decimal("1200.00"))
        self._suspendre()
        self.assertEqual(selectors.mrr_contrats(self.co), Decimal("0.00"))
        self.assertEqual(
            selectors.mrr_contrat_actif(self.contrat), Decimal("0.00"))

    def test_reactivation_restaure_exactement_les_echeanciers_geles(self):
        # Un SECOND échéancier volontairement désactivé AVANT la suspension :
        # il ne doit JAMAIS être rallumé par la réactivation.
        autre = EcheancierContrat.objects.create(
            company=self.co, contrat=self.contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=False,
            statut=EcheancierContrat.Statut.ACTIF)
        self._suspendre()
        services.changer_statut(self.contrat, Contrat.Statut.ACTIF)
        self.echeancier.refresh_from_db()
        autre.refresh_from_db()
        self.assertTrue(self.echeancier.facturation_active)
        self.assertFalse(self.echeancier.gele_par_suspension)
        self.assertFalse(autre.facturation_active)
        self.assertFalse(autre.gele_par_suspension)
