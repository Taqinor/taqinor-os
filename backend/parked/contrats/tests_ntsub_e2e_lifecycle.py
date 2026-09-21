"""Test e2e NTSUB32 — parcours complet essai → conversion → upgrade → dunning
→ suspension.

Enchaîne les mécaniques NTSUB1/5/7/8 mises bout à bout, déterministe (horloge
injectée, aucun sleep réel) :

  1. contrat créé EN ESSAI (NTSUB5) — facturation gelée ;
  2. conversion à la fin d'essai (NTSUB5) — facturation activée ;
  3. upgrade de plan (NTSUB7) — avenant + montant au nouveau tarif ;
  4. 2 échéances impayées + séquence de dunning (NTSUB8) — étapes envoyées
     puis suspension via ZCTR2 à la dernière étape.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import (
    Contrat,
    EcheancierContrat,
    EtapeDunning,
    EtapeDunningLog,
    LigneEcheance,
    PlanAbonnement,
    PlanRecurrent,
    SequenceDunning,
)
from apps.crm.models import Client
from apps.ventes.models import Facture


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_plan(company, code, prix):
    return PlanAbonnement.objects.create(
        company=company, code=code, nom=f"Plan {code}",
        plan_recurrent=PlanRecurrent.objects.create(
            company=company, nom=f"C{code}",
            unite=PlanRecurrent.Unite.MENSUEL, intervalle=1),
        prix_base=Decimal(prix))


class NtsubLifecycleE2ETests(TestCase):
    def test_essai_conversion_upgrade_dunning_suspension(self):
        co = make_company("ntsub-e2e", "NtsubE2E")
        plan_basic = make_plan(co, "BASIC", "500")
        plan_pro = make_plan(co, "PRO", "900")

        # ── 1. Contrat créé EN ESSAI (NTSUB5) ───────────────────────────────
        contrat = Contrat.objects.create(
            company=co, objet="Abonnement SaaS", montant=Decimal("500"),
            type_contrat="om", statut=Contrat.Statut.ACTIF,
            plan_abonnement=plan_basic, plan_recurrent=plan_basic.plan_recurrent,
            date_debut=datetime.date(2026, 1, 1))
        ech = EcheancierContrat.objects.create(
            company=co, contrat=contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE,
            facturation_active=True, statut=EcheancierContrat.Statut.ACTIF)
        services.demarrer_essai_contrat(
            contrat, date_fin_essai=datetime.date(2026, 2, 1),
            plan_apres_essai=plan_basic)
        ech.refresh_from_db()
        self.assertFalse(ech.facturation_active)  # facturation gelée

        # ── 2. Conversion à la fin d'essai (NTSUB5) ─────────────────────────
        res = services.convertir_essais_expires(
            co, today=datetime.date(2026, 2, 1))
        self.assertEqual(res['convertis'], 1)
        ech.refresh_from_db()
        self.assertTrue(ech.facturation_active)  # facturation active

        # ── 3. Upgrade de plan (NTSUB7) ─────────────────────────────────────
        up = services.changer_plan_contrat(
            contrat, plan_pro, type_changement='immediat')
        contrat.refresh_from_db()
        self.assertEqual(contrat.montant, Decimal("900"))
        self.assertEqual(up['avenant'].montant_delta, Decimal("400"))
        self.assertEqual(contrat.plan_abonnement_id, plan_pro.id)

        # ── 4. Dunning multi-étapes → suspension (NTSUB8 + ZCTR2) ───────────
        seq = SequenceDunning.objects.create(company=co, nom="Relances")
        EtapeDunning.objects.create(
            company=co, sequence=seq, jour_offset=1,
            canal=EtapeDunning.Canal.EMAIL, ordre=0)
        EtapeDunning.objects.create(
            company=co, sequence=seq, jour_offset=14,
            canal=EtapeDunning.Canal.NOTIFICATION_INTERNE, ordre=1,
            declenche_suspension=True)
        contrat.sequence_dunning = seq
        contrat.save(update_fields=['sequence_dunning'])

        # 2 échéances impayées facturées depuis > 14 jours.
        client = Client.objects.create(company=co, nom="Client E2E")
        for numero, jours in ((1, 40), (2, 20)):
            facture = Facture.objects.create(
                company=co, client=client, statut=Facture.Statut.EMISE,
                reference=f"E2E-DUN-{numero}",
                taux_tva=Decimal("20"), montant_ttc=Decimal("900"),
                date_echeance=(
                    timezone.localdate() - datetime.timedelta(days=jours)))
            LigneEcheance.objects.create(
                company=co, echeancier=ech, numero=numero,
                date_echeance=(
                    timezone.localdate() - datetime.timedelta(days=jours)),
                montant=Decimal("900"), facture_id=facture.id)

        dun = services.executer_dunning_contrat(contrat)
        self.assertEqual(dun['etapes_jouees'], 2)  # J+1 et J+14
        self.assertTrue(dun['suspendu'])
        contrat.refresh_from_db()
        self.assertEqual(contrat.statut, Contrat.Statut.SUSPENDU)
        self.assertEqual(
            EtapeDunningLog.objects.filter(contrat=contrat).count(), 2)

        # Re-run le même jour : idempotent (0 nouvelle étape, reste suspendu).
        dun2 = services.executer_dunning_contrat(contrat)
        self.assertEqual(dun2['etapes_jouees'], 0)
