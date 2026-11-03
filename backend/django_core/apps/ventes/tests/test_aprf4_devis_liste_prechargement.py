"""APRF4 (C-APRF-002) — ``DevisViewSet.get_queryset`` précharge tout ce que
``DevisSerializer`` lit en liste : les SELECT sur ``authentication_customuser``,
``authentication_company`` et ``ventes_affectationpaiement`` sont les MÊMES à
5 et à 15 devis listés.

Comptage par table via ``CaptureQueriesContext`` sur la réponse HTTP réelle
(comportemental, aucun espion).

Test-du-test : retirer ``'updated_by'`` du ``select_related`` ⇒ la table
utilisateur repasse à une requête par ligne ; retirer
``factures__affectations_paiement__paiement`` ⇒ une par facture active.
"""
import re
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.ventes.models import Devis, Facture
from authentication.models import Company

User = get_user_model()

TABLES = ('authentication_customuser', 'authentication_company',
          'ventes_affectationpaiement')


class DevisListePrechargementTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='APRF4', slug='aprf4-co')
        self.user = User.objects.create_user(
            username='aprf4_admin', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client APRF4',
            email='aprf4@example.com')
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.n = 0

    def _ajouter(self, nombre):
        for _ in range(nombre):
            self.n += 1
            devis = Devis.objects.create(
                company=self.company, reference='DEV-APRF4-%03d' % self.n,
                client=self.client_obj, statut=Devis.Statut.ACCEPTE,
                created_by=self.user, updated_by=self.user,
                taux_tva=Decimal('20'), date_validite=None)
            for k in (1, 2):
                Facture.objects.create(
                    company=self.company,
                    reference='FAC-APRF4-%03d-%d' % (self.n, k),
                    devis=devis, client=self.client_obj,
                    statut=Facture.Statut.EMISE, type_facture='acompte',
                    montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                    montant_ttc=Decimal('1200'), created_by=self.user)

    def test_resume_sans_etude_params(self):
        # ACVI94 — statut, dates et montant lus sans jamais charger le JSON
        # d'étude (seules les annotations `etude_params ->` sont permises).
        from django.utils import timezone

        from apps.crm.models import Lead
        from apps.ventes.selectors_listes import prefetch_devis_resume

        etude = {'scenario': 'Avec batterie', 'nombre_proprietes': 2,
                 'profil_horaire': [0.37] * 744}
        jour = timezone.localdate()
        for i in range(3):
            lead = Lead.objects.create(
                company=self.company, nom=f'L{i}', client=self.client_obj)
            for j, statut in enumerate((Devis.Statut.ACCEPTE, Devis.Statut.ENVOYE)):
                Devis.objects.create(
                    company=self.company, reference=f'DEV-ACVI94-{i}{j}',
                    client=self.client_obj, lead=lead, statut=statut,
                    taux_tva=Decimal('20'), version=1, etude_params=dict(etude),
                    date_envoi=timezone.now(), date_acceptation=jour)

        def charge_le_json(requetes):
            # Une colonne lue HORS d'un `->` : une annotation ne masque plus le
            # reste du SELECT (retirer `.defer` rougit ce test, prefetch compris).
            return [q['sql'] for q in requetes
                    if re.search(r'"etude_params"(?!\s*->)', q['sql'])]

        leads = Lead.objects.filter(company=self.company)
        with CaptureQueriesContext(connection) as ctx:
            resume = list(leads.prefetch_related(*prefetch_devis_resume()))
            champs = {d.pk: (d.statut, d.date_acceptation, d.date_envoi)
                      for lead in resume for d in lead.devis.all()}
        self.assertEqual(len(ctx.captured_queries), 2)
        self.assertEqual(charge_le_json(ctx.captured_queries), [])
        self.assertEqual(len(champs), 6)

        with CaptureQueriesContext(connection) as ctx:
            montants = {d.pk: d.total_ttc
                        for lead in resume for d in lead.devis.all()}
        self.assertEqual(charge_le_json(ctx.captured_queries), [])
        oracle = Devis.objects.filter(company=self.company)
        self.assertEqual(montants, {d.pk: d.total_ttc for d in oracle})
        self.assertEqual(
            champs, {d.pk: (d.statut, d.date_acceptation, d.date_envoi) for d in oracle})

    def _compter(self):
        with CaptureQueriesContext(connection) as ctx:
            resp = self.api.get('/api/django/ventes/devis/',
                                {'page_size': 50})
        self.assertEqual(resp.status_code, 200)
        compte = {}
        for table in TABLES:
            motif = re.compile(r'FROM\s+"%s"' % table)
            compte[table] = sum(1 for q in ctx.captured_queries
                                if q['sql'].lstrip().upper().startswith('SELECT')
                                and motif.search(q['sql']))
        return compte, resp

    def test_fk_et_factures_constants(self):
        self._ajouter(5)
        a_cinq, resp5 = self._compter()
        self._ajouter(10)
        a_quinze, resp15 = self._compter()
        self.assertEqual(a_cinq, a_quinze)
        lignes = resp15.json()
        lignes = lignes.get('results', lignes) if isinstance(lignes, dict) else lignes
        self.assertEqual(len(lignes), 15)
        for ligne in lignes:
            self.assertIn('solde', ligne)
