"""Tests XCTR7 — Cascade MRR (new/expansion/contraction/churn/net) + motif.

Couvre :
- new+expansion-contraction-churn = variation du MRR entre deux instantanés ;
- ventilation churn par motif exacte ;
- endpoint /contrats/mrr-mouvements/.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Client

from apps.contrats import selectors, services
from apps.contrats.models import Contrat, EcheancierContrat

User = get_user_model()

MRR_MOUV = "/api/django/contrats/contrats/mrr-mouvements/"


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role
    )


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {AccessToken.for_user(user)}")
    return api


def make_contrat_avec_mrr(company, montant_mensuel):
    cli = Client.objects.create(company=company, nom="Client SARL")
    contrat = Contrat.objects.create(
        company=company, objet="Contrat O&M", montant=montant_mensuel,
        type_contrat="om", statut="actif", client_id=cli.id)
    EcheancierContrat.objects.create(
        company=company, contrat=contrat, periodicite="mensuelle",
        facturation_active=True, statut=EcheancierContrat.Statut.ACTIF,
        montant_total=montant_mensuel)
    return contrat


class MouvementsMrrTests(TestCase):
    def setUp(self):
        self.co = make_company("mrr-mouv", "MrrMouv")
        self.user = make_user(self.co, "mrr-mouv-admin")

    def test_new_detecte_contrat_recent(self):
        contrat = make_contrat_avec_mrr(self.co, Decimal("1000"))
        debut = contrat.date_creation.date()
        fin = debut
        data = selectors.mouvements_mrr(self.co, debut, fin)
        self.assertEqual(data['new'], Decimal('1000.00'))

    def test_expansion_et_contraction(self):
        contrat = make_contrat_avec_mrr(self.co, Decimal("1000"))
        today = contrat.date_creation.date()
        services.creer_avenant(
            contrat, objet="Hausse", date_effet=today,
            montant_delta=Decimal("200"))
        services.creer_avenant(
            contrat, objet="Baisse", date_effet=today,
            montant_delta=Decimal("-50"))
        data = selectors.mouvements_mrr(self.co, today, today)
        self.assertEqual(data['expansion'], Decimal('200.00'))
        self.assertEqual(data['contraction'], Decimal('-50.00'))

    def test_churn_ventile_par_motif(self):
        c1 = make_contrat_avec_mrr(self.co, Decimal("1000"))
        c2 = make_contrat_avec_mrr(self.co, Decimal("500"))
        today = c1.date_creation.date()
        services.resilier_contrat(
            c1, motif="Prix trop élevé", date_effet=today, today=today)
        services.resilier_contrat(
            c2, motif="Prix trop élevé", date_effet=today, today=today)
        data = selectors.mouvements_mrr(self.co, today, today)
        self.assertEqual(data['churn'], Decimal('-1500.00'))
        self.assertEqual(
            data['churn_par_motif']["Prix trop élevé"], Decimal('-1500.00'))

    def test_net_egale_somme_algebrique(self):
        contrat = make_contrat_avec_mrr(self.co, Decimal("1000"))
        today = contrat.date_creation.date()
        services.creer_avenant(
            contrat, objet="Hausse", date_effet=today,
            montant_delta=Decimal("200"))
        data = selectors.mouvements_mrr(self.co, today, today)
        attendu = data['new'] + data['expansion'] + data['contraction'] \
            + data['churn']
        self.assertEqual(data['net'], attendu)

    def test_new_plus_expansion_moins_contraction_moins_churn_egale_variation(self):
        """new + expansion − contraction − churn = variation du MRR observée
        entre deux instantanés (contraction/churn étant déjà négatifs ici,
        -contraction/-churn les rend positifs — cohérent avec le Done= du
        plan qui les exprime en valeur absolue soustraite)."""
        mrr_avant = selectors.mrr_contrats(self.co)
        contrat = make_contrat_avec_mrr(self.co, Decimal("1000"))
        today = contrat.date_creation.date()
        services.creer_avenant(
            contrat, objet="Hausse", date_effet=today,
            montant_delta=Decimal("200"))
        mrr_apres = selectors.mrr_contrats(self.co)
        data = selectors.mouvements_mrr(self.co, today, today)
        variation = mrr_apres - mrr_avant
        recompose = (
            data['new'] + data['expansion']
            - abs(data['contraction']) - abs(data['churn']))
        self.assertEqual(recompose, variation)

    def test_scope_societe(self):
        autre = make_company("mrr-mouv-autre", "MrrMouvAutre")
        make_contrat_avec_mrr(autre, Decimal("999"))
        contrat = make_contrat_avec_mrr(self.co, Decimal("1000"))
        today = contrat.date_creation.date()
        data = selectors.mouvements_mrr(self.co, today, today)
        self.assertEqual(data['new'], Decimal('1000.00'))


class MrrMouvementsApiTests(TestCase):
    def setUp(self):
        self.co = make_company("mrr-mouv-api", "MrrMouvApi")
        self.admin = make_user(self.co, "mrr-mouv-api-admin")

    def test_endpoint_retourne_cascade(self):
        contrat = make_contrat_avec_mrr(self.co, Decimal("1000"))
        today = contrat.date_creation.date().isoformat()
        api = auth(self.admin)
        res = api.get(f"{MRR_MOUV}?debut={today}&fin={today}")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.data['new'], '1000.00')
        self.assertIn('churn_par_motif', res.data)

    def test_endpoint_400_dates_invalides(self):
        api = auth(self.admin)
        res = api.get(f"{MRR_MOUV}?debut=2026-07-10&fin=2026-07-01")
        self.assertEqual(res.status_code, 400)

    def test_role_gate(self):
        commercial = make_user(self.co, "mrr-mouv-api-com", role="commercial")
        api = auth(commercial)
        res = api.get(MRR_MOUV)
        self.assertEqual(res.status_code, 403)
