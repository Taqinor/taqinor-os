"""CAD141 — le passage nocturne de scores ignore les dossiers CLOS.

Aujourd'hui : `recalculer_scores_obsoletes` (CRX22) filtrait uniquement sur
`date_modification__lt=seuil`, sans écarter les leads ARCHIVÉS ni PERDUS
(`apps/crm/services.py`). Un lead clos, jamais retouché, était donc recalculé
chaque nuit pour rien — et risquait de remonter dans un tri par score
(CAD83) alors qu'il n'a plus sa place dans le pipeline actif. Écarter ces
deux états : même résultat utile pour les leads actifs, coût divisé, et zéro
risque de réapparition d'un dossier clos.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.crm import stages
from apps.crm.models import Lead
from apps.crm.scoring import compute_score
from apps.crm.services import recalculer_scores_obsoletes
from authentication.models import Company


class LeadsClosIgnoresParLePassageNocturneTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CAD141', slug='taqinor-cad141')

    def _lead_dormant(self, **extra):
        """Même recette que CRX22 (`tests_crx22_score_proprietaire.py`) :
        créé il y a longtemps ET non modifié depuis (les deux colonnes sont
        auto_now_add/auto_now, repoussées par ``update`` qui ne les
        rafraîchit pas)."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead dormant', stage=stages.NEW,
            telephone='0612345678', ville='Casablanca', **extra)
        vieux = timezone.now() - datetime.timedelta(days=200)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=vieux, date_modification=vieux, score=95)
        lead.refresh_from_db()
        return lead

    def test_un_lead_perdu_n_est_plus_recalcule_la_nuit(self):
        lead = self._lead_dormant(perdu=True)

        resume = recalculer_scores_obsoletes()

        lead.refresh_from_db()
        self.assertEqual(resume['examines'], 0)
        self.assertEqual(resume['mis_a_jour'], 0)
        self.assertEqual(lead.score, 95)

    def test_un_lead_archive_n_est_plus_recalcule_la_nuit(self):
        lead = self._lead_dormant(is_archived=True)

        resume = recalculer_scores_obsoletes()

        lead.refresh_from_db()
        self.assertEqual(resume['examines'], 0)
        self.assertEqual(resume['mis_a_jour'], 0)
        self.assertEqual(lead.score, 95)

    def test_un_lead_actif_dormant_reste_recalcule(self):
        """Non-régression : le comportement CRX22 normal est intact pour un
        lead ACTIF (ni archivé, ni perdu)."""
        lead = self._lead_dormant()
        attendu = compute_score(lead)
        self.assertNotEqual(attendu, 95)

        resume = recalculer_scores_obsoletes()

        lead.refresh_from_db()
        self.assertEqual(resume['examines'], 1)
        self.assertEqual(resume['mis_a_jour'], 1)
        self.assertEqual(lead.score, attendu)
