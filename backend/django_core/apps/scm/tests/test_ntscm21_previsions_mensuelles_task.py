"""NTSCM21 — Tâche planifiée mensuelle : génération automatique des
prévisions.

Critère d'acceptation : la tâche apparaît dans ``/api/django/core/jobs/`` et
un déclenchement manuel produit le résumé attendu sur un jeu de données de
test."""
from django.test import TestCase
from django.utils import timezone

from apps.notifications.models import Notification
from apps.scm.models import PrevisionDemande
from apps.scm.tasks import generer_previsions_mensuelles_task
from apps.stock.models import MouvementStock, Produit

from .helpers import auth, make_company, make_user


class GenererPrevisionsMensuellesTaskTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-tache-prevision', 'Supply Tâche Prévision')
        self.admin = make_user(self.company, 'scm-tache-prevision-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Micro-onduleur', prix_vente=900,
            quantite_stock=500)

        today = timezone.localdate()
        idx_dernier = today.year * 12 + (today.month - 1) - 1
        qty_restante = 100000
        for offset in range(2, -1, -1):
            idx = idx_dernier - offset
            y, m0 = divmod(idx, 12)
            mvt = MouvementStock.objects.create(
                company=self.company, produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=100, quantite_avant=qty_restante,
                quantite_apres=qty_restante - 100)
            qty_restante -= 100
            mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
            mvt.save(update_fields=['date'])

        idx_horizon = today.year * 12 + (today.month - 1) + 1
        y_h, m0_h = divmod(idx_horizon, 12)
        self.periode_horizon = f'{y_h:04d}-{m0_h + 1:02d}'
        # Valeur volontairement très basse : la vraie prévision recalculée
        # (~100, historique stable) s'en écarte de loin plus de 30%.
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=self.periode_horizon, quantite_prevue=1)

    def test_genere_previsions_et_detecte_ecart(self):
        resume = generer_previsions_mensuelles_task(horizon_mois=1)
        entree = next(r for r in resume if r['company_id'] == self.company.id)
        self.assertGreater(entree['nb_maj'], 0)
        self.assertGreaterEqual(entree['nb_ecarts'], 1)

        prevision = PrevisionDemande.objects.get(
            company=self.company, produit=self.produit, segment='',
            periode=self.periode_horizon)
        self.assertGreater(prevision.quantite_prevue, 10)

    def test_notifie_administrateur_du_resume(self):
        generer_previsions_mensuelles_task(horizon_mois=1)
        notif = Notification.objects.filter(
            company=self.company, recipient=self.admin,
            event_type='scm_previsions_generees').first()
        self.assertIsNotNone(notif)

    def test_tache_apparait_dans_core_jobs(self):
        resp = auth(self.admin).get('/api/django/core/jobs/')
        self.assertEqual(resp.status_code, 200, resp.data)
        taches = resp.data if isinstance(resp.data, list) else resp.data.get('results', [])
        self.assertTrue(any(
            job.get('task') == 'scm.generer_previsions_mensuelles' for job in taches))
