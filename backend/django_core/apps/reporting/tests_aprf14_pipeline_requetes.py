"""APRF14 (C-APRF-004 + C-APRF-026) — ``reporting/pipeline/``,
``reporting/commercial/dashboard/`` et ``reporting/pipeline/velocity/`` à
requêtes CONSTANTES.

Sonde V_VB (avant) : +20 leads à 1 devis → ``pipeline/`` 42 → 181,
``commercial/dashboard/`` 50 → 110, ``velocity/`` 40 → 60 ; +200 devis actifs
→ ``pipeline/`` 41 → 441. Ici : le nombre de requêtes de chaque endpoint est
IDENTIQUE à deux tailles (base, puis +20 leads à 1 devis + changements
d'étape, puis +200 devis actifs), et les valeurs servies sont celles calculées
indépendamment (montants par étape = somme des ``total_ttc`` relus un à un,
durées moyennes par étape connues).

Test-du-test : remettre la requête ``LeadActivity`` par lead dans
``durees_par_etape`` ⇒ +1 requête par lead, ``test_requetes_constantes``
échoue ; retirer ``leads_avec_devis_totaux`` ⇒ idem.

Run :
    docker compose exec django_core python manage.py test \
        apps.reporting.tests_aprf14_pipeline_requetes -v 2
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.crm import stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/reporting'
ENDPOINTS = ('pipeline/', 'commercial/dashboard/', 'pipeline/velocity/')


class PipelineRequetesConstantesTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='APRF14 Co', slug='aprf14-co')
        self.admin = User.objects.create_user(
            username='aprf14_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.admin)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client APRF14')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 710W', sku='APRF14-PV',
            prix_vente=Decimal('1450'), quantite_stock=0)
        self.n = 0
        # Base : quelques leads, devis et changements d'étape.
        self._ajouter_leads(3)

    def _devis(self, lead=None):
        self.n += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-APRF14-{self.n:04d}',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal(str(1 + self.n % 9)),
            prix_unitaire=Decimal('1450'), remise=Decimal('0'))
        return devis

    def _ajouter_leads(self, nombre):
        maintenant = timezone.now()
        for _ in range(nombre):
            self.n += 1
            lead = Lead.objects.create(
                company=self.company, nom=f'Lead {self.n}',
                stage=stages.QUOTE_SENT)
            Lead.objects.filter(pk=lead.pk).update(
                date_creation=maintenant - timedelta(days=10))
            self._devis(lead)
            # NEW pendant 4 j, CONTACTED pendant 2 j, puis QUOTE_SENT.
            for jours, cle in ((6, stages.CONTACTED), (4, stages.QUOTE_SENT)):
                activite = LeadActivity.objects.create(
                    company=self.company, lead=lead,
                    kind=LeadActivity.Kind.MODIFICATION, field='stage',
                    new_value=stages.STAGE_LABELS[cle])
                LeadActivity.objects.filter(pk=activite.pk).update(
                    created_at=maintenant - timedelta(days=jours))

    def _compter(self, endpoint):
        # Échauffement : premier appel (profil société créé à la volée, etc.).
        self.assertEqual(self.api.get(f'{BASE}/{endpoint}').status_code, 200)
        with CaptureQueriesContext(connection) as ctx:
            reponse = self.api.get(f'{BASE}/{endpoint}')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return len(ctx.captured_queries)

    def _comptes(self):
        return {e: self._compter(e) for e in ENDPOINTS}

    def test_requetes_constantes(self):
        base = self._comptes()
        self._ajouter_leads(20)
        self.assertEqual(self._comptes(), base, '+20 leads à 1 devis')
        for _ in range(200):
            self._devis()
        self.assertEqual(self._comptes(), base, '+200 devis actifs')

    def test_valeurs_inchangees(self):
        self._ajouter_leads(5)
        attendu = sum(
            (Decimal(str(Devis.objects.get(pk=d.pk).total_ttc))
             for d in Devis.objects.filter(company=self.company,
                                           lead__isnull=False)),
            Decimal('0'))
        reponse = self.api.get(f'{BASE}/pipeline/')
        etape = next(e for e in reponse.data['par_etape']
                     if e['stage'] == stages.QUOTE_SENT)
        self.assertEqual(etape['count'], 8)
        self.assertEqual(Decimal(etape['valeur']), attendu)

        dashboard = self.api.get(f'{BASE}/commercial/dashboard/').data
        funnel = next(e for e in dashboard['funnel']
                      if e['stage'] == stages.QUOTE_SENT)
        self.assertEqual(Decimal(funnel['valeur']), attendu)

        for donnees, cle in ((dashboard['time_in_stage'], 'time_in_stage'),
                             (self.api.get(f'{BASE}/pipeline/velocity/')
                              .data['velocity'], 'velocity')):
            with self.subTest(source=cle):
                par_cle = {e['stage']: e for e in donnees}
                self.assertEqual(par_cle[stages.NEW]['avg_days'], 4.0)
                self.assertEqual(par_cle[stages.NEW]['sample_count'], 8)
                self.assertEqual(par_cle[stages.CONTACTED]['avg_days'], 2.0)
                self.assertEqual(par_cle[stages.CONTACTED]['sample_count'], 8)
