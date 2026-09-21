"""NTSCM35 — Tâche planifiée hebdomadaire : recalcul des politiques de stock.

Critère d'acceptation : la tâche apparaît dans `/api/django/core/jobs/` avec
sa cadence hebdomadaire et un déclenchement manuel recalcule les
`PolitiqueStock` de toutes les sociétés actives sans lever d'exception même
si une société a des données incomplètes."""
from django.test import TestCase

from apps.scm.models import ParametresSCM, PolitiqueStock
from apps.scm.tasks import recalculer_politiques_stock_hebdo
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class RecalculerPolitiquesStockHebdoTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-recalcul-hebdo', 'Supply Recalcul Hebdo')
        ParametresSCM.objects.create(company=self.company)
        Produit.objects.create(
            company=self.company, nom='Câble solaire 6mm² (50m)',
            prix_vente=800, quantite_stock=30)

        # Société SANS ParametresSCM configuré : jamais touchée par la tâche.
        self.company_hors_perimetre = make_company(
            'scm-recalcul-hebdo-hors', 'Supply Hors Périmètre')
        Produit.objects.create(
            company=self.company_hors_perimetre, nom='Onduleur 3kW',
            prix_vente=6000, quantite_stock=5)

        # Société avec ParametresSCM mais AUCUN produit (données incomplètes) :
        # ne doit jamais interrompre le traitement des autres sociétés.
        self.company_vide = make_company('scm-recalcul-hebdo-vide', 'Supply Vide')
        ParametresSCM.objects.create(company=self.company_vide)

    def test_recalcule_uniquement_les_societes_avec_parametres_configures(self):
        resultat = recalculer_politiques_stock_hebdo()
        company_ids = {r['company_id'] for r in resultat}
        self.assertIn(self.company.id, company_ids)
        self.assertIn(self.company_vide.id, company_ids)
        self.assertNotIn(self.company_hors_perimetre.id, company_ids)

        self.assertTrue(
            PolitiqueStock.objects.filter(company=self.company).exists())
        self.assertFalse(
            PolitiqueStock.objects.filter(company=self.company_hors_perimetre).exists())

    def test_societe_sans_donnees_ne_leve_jamais_dexception(self):
        # Ne doit rien lever, même pour `company_vide` (aucun produit).
        resultat = recalculer_politiques_stock_hebdo()
        ligne_vide = next(
            r for r in resultat if r['company_id'] == self.company_vide.id)
        self.assertEqual(ligne_vide['nb_politiques'], 0)

    def test_tache_visible_dans_core_jobs_avec_cadence_hebdomadaire(self):
        admin = make_user(self.company, 'scm-recalcul-hebdo-admin', 'admin')
        resp = auth(admin).get('/api/django/core/jobs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        jobs = resp.data if isinstance(resp.data, list) else resp.data.get('results', resp.data)
        job = next(
            j for j in jobs
            if j['task'] == 'scm.recalculer_politiques_stock_hebdo')
        # Cadence crontab hebdomadaire : jour de semaine != '*'.
        self.assertNotEqual(job['schedule'].split()[-1], '*')
