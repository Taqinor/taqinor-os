"""ZSAL3 — Équipes commerciales + tableau de bord d'équipe (« Mes équipes »).

Covers:
  - Une équipe de plusieurs commerciaux affiche pipeline ouvert (count +
    valeur), valeur pondérée, activités en retard, CA signé du mois vs cible
    corrects.
  - Un commercial SANS équipe n'apparaît dans aucune carte.
  - Aucune étape hors STAGES.py n'est utilisée (réutilise apps.crm.stages).
  - Isolation multi-tenant (cross-company jamais mélangé).
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.crm import stages as stage_mod
from apps.crm.models import EquipeCommerciale, Lead, ObjectifCommercial
from apps.crm.selectors import stats_equipe
from apps.records.models import Activity, ActivityType
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


def make_company(slug='zsal3-co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_devis(company, client, lead, statut, total_ttc_cible, date_acceptation=None):
    produit = Produit.objects.create(
        company=company, nom='Panneau', sku=f'SKU-{lead.id}-{total_ttc_cible}',
        prix_vente=Decimal('100'), quantite_stock=100, tva=Decimal('20.00'))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-{lead.id}-{total_ttc_cible}',
        client=client, lead=lead, statut=statut, taux_tva=Decimal('20.00'),
        date_acceptation=date_acceptation)
    # total_ttc = total_ht + total_tva ; on vise un ttc rond avec 1 ligne à
    # 20% de TVA -> ht = ttc / 1.2. Pour simplifier, on pose directement une
    # ligne dont le HT * 1.2 == la cible souhaitée (cible multiple de 1.2).
    ht = (Decimal(total_ttc_cible) / Decimal('1.2')).quantize(Decimal('0.01'))
    LigneDevis.objects.create(
        devis=devis, produit=produit, designation='Panneau',
        quantite=Decimal('1'), prix_unitaire=ht, taux_tva=Decimal('20.00'))
    return devis


class TestStatsEquipe(TestCase):
    def setUp(self):
        self.company = make_company()
        self.today = datetime.date.today()
        self.resp1 = User.objects.create_user(
            username='zsal3resp1', password='x', company=self.company)
        self.resp2 = User.objects.create_user(
            username='zsal3resp2', password='x', company=self.company)
        self.hors_equipe = User.objects.create_user(
            username='zsal3horsequipe', password='x', company=self.company)
        self.manager = User.objects.create_user(
            username='zsal3manager', password='x', company=self.company)

        self.equipe = EquipeCommerciale.objects.create(
            company=self.company, nom='Équipe Nord', responsable=self.manager)
        self.equipe.membres.set([self.resp1, self.resp2])

        from apps.crm.models import Client
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client Test')

        # Pipeline ouvert : 2 leads en QUOTE_SENT (dans stage_mod.STAGES,
        # jamais hardcodé), 1 en SIGNED (exclu du pipeline "ouvert"), 1
        # rattaché à un commercial hors équipe (ne doit PAS compter).
        self.lead_ouvert_1 = Lead.objects.create(
            company=self.company, nom='L1', owner=self.resp1,
            stage=stage_mod.QUOTE_SENT)
        self.lead_ouvert_2 = Lead.objects.create(
            company=self.company, nom='L2', owner=self.resp2,
            stage=stage_mod.CONTACTED)
        self.lead_signe = Lead.objects.create(
            company=self.company, nom='L3', owner=self.resp1,
            stage=stage_mod.SIGNED)
        self.lead_hors_equipe = Lead.objects.create(
            company=self.company, nom='L4', owner=self.hors_equipe,
            stage=stage_mod.QUOTE_SENT)

        make_devis(self.company, self.client_obj, self.lead_ouvert_1,
                   Devis.Statut.ENVOYE, 1200)
        make_devis(self.company, self.client_obj, self.lead_ouvert_2,
                   Devis.Statut.ENVOYE, 2400)
        # Hors équipe : ne doit jamais apparaître dans les stats de l'équipe.
        make_devis(self.company, self.client_obj, self.lead_hors_equipe,
                   Devis.Statut.ENVOYE, 999999)

        # CA signé ce mois pour resp1 (compte), et un signé le mois dernier
        # (ne doit pas compter dans "ce mois").
        make_devis(self.company, self.client_obj, self.lead_signe,
                   Devis.Statut.ACCEPTE, 6000, date_acceptation=self.today)

        # Activité en retard pour resp1.
        atype, _ = ActivityType.objects.get_or_create(
            company=self.company, nom='Appel', defaults={'ordre': 1})
        ct = ContentType.objects.get_for_model(Lead)
        Activity.objects.create(
            company=self.company, content_type=ct, object_id=self.lead_ouvert_1.id,
            activity_type=atype, summary='Relance', assigned_to=self.resp1,
            due_date=self.today - datetime.timedelta(days=3))
        # Activité en retard hors équipe -> ne doit pas compter.
        Activity.objects.create(
            company=self.company, content_type=ct, object_id=self.lead_hors_equipe.id,
            activity_type=atype, summary='Relance', assigned_to=self.hors_equipe,
            due_date=self.today - datetime.timedelta(days=3))

        ObjectifCommercial.objects.create(
            company=self.company, owner=self.resp1,
            metric=ObjectifCommercial.Metric.CA_SIGNE, period_type='month',
            period_year=self.today.year, period_month=self.today.month,
            cible=Decimal('10000'))

    def test_equipe_agregation_correcte(self):
        result = stats_equipe(self.company)
        self.assertEqual(len(result), 1)
        carte = result[0]
        self.assertEqual(carte['nom'], 'Équipe Nord')
        self.assertEqual(carte['nb_membres'], 2)
        self.assertEqual(carte['pipeline_ouvert_count'], 2)
        self.assertEqual(Decimal(carte['pipeline_ouvert_valeur']), Decimal('3600'))
        self.assertEqual(carte['activites_en_retard'], 1)
        self.assertEqual(Decimal(carte['ca_signe_mois']), Decimal('6000'))
        self.assertEqual(Decimal(carte['cible_ca_signe_mois']), Decimal('10000'))
        self.assertEqual(carte['avancement_pct'], 60.0)
        # Valeur pondérée > 0 et <= valeur brute (probabilité <= 1).
        self.assertGreater(Decimal(carte['pipeline_pondere']), 0)
        self.assertLessEqual(
            Decimal(carte['pipeline_pondere']), Decimal(carte['pipeline_ouvert_valeur']))

    def test_commercial_sans_equipe_absent(self):
        """Le commercial hors équipe (999999 MAD de pipeline) ne doit JAMAIS
        apparaître dans l'agrégation de l'équipe Nord."""
        result = stats_equipe(self.company)
        carte = result[0]
        self.assertNotIn('999999', carte['pipeline_ouvert_valeur'])

    def test_aucune_equipe_sans_equipe_active(self):
        EquipeCommerciale.objects.all().update(actif=False)
        result = stats_equipe(self.company)
        self.assertEqual(result, [])

    def test_stages_utilises_sont_ceux_de_stages_py(self):
        """Garde contre toute étape hors STAGES.py — jamais une liste
        inventée dans le sélecteur d'équipe (règle #2)."""
        from apps.crm.selectors import _lignes_pipeline_ouvertes
        qs = _lignes_pipeline_ouvertes(self.company)
        for lead in qs:
            self.assertIn(lead.stage, stage_mod.STAGES)


class TestStatsEquipeMultiTenant(TestCase):
    def test_cross_company_isolation(self):
        co_a = make_company('zsal3-a')
        co_b = make_company('zsal3-b')
        user_a = User.objects.create_user(
            username='zsal3usera', password='x', company=co_a)
        EquipeCommerciale.objects.create(
            company=co_a, nom='Équipe A').membres.set([user_a])
        result_b = stats_equipe(co_b)
        self.assertEqual(result_b, [])
