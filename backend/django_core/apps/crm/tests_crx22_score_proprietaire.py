"""CRX22 — le score de lead a UN seul propriétaire.

Trois défauts relevés par l'audit L3 :

1. **Badge vs tri.** Le badge (``LeadSerializer.get_score`` /
   ``get_score_label``) recalculait le score À LA VOLÉE par ligne, alors que
   le TRI (``ordering_fields = [... 'score']``) et « Ma file »
   (``selectors.leads_chauds_non_contactes``, filtre ``score__gte``) lisent la
   COLONNE persistée : deux valeurs pour le même lead, donc une liste « triée
   par score » dont les badges n'étaient pas dans l'ordre.
2. **Décote de récence morte.** ``Lead.score`` n'était recalculé qu'à la
   création/édition : un lead jamais rouvert gardait éternellement le score de
   son premier jour (12 pts de récence au lieu de 1).
3. **Ajustement effacé.** Une automatisation qui écrivait ``Lead.score``
   voyait son delta écrasé au premier recalcul. Le delta vit maintenant dans
   ``Lead.score_ajustement``, appliqué PAR ``compute_score``.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm import stages
from apps.crm.models import Lead
from apps.crm.scoring import compute_score, score_label, score_reasons
from apps.crm.selectors import leads_chauds_non_contactes
from apps.crm.serializers import LeadSerializer
from apps.crm.services import (
    DELAI_SCORE_OBSOLETE_JOURS, recalculer_scores_obsoletes,
    recompute_lead_score,
)
from apps.roles.models import Role
from authentication.models import Company

User = get_user_model()


class AjustementPersistantTests(TestCase):
    """Le delta survit à tout recalcul — c'est toute la raison du champ."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX22 ajust', slug='taqinor-crx22-ajust')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead ajusté', stage=stages.NEW,
            telephone='0612345678', ville='Casablanca')

    def test_sans_ajustement_le_score_est_inchange(self):
        """NULL = aucun ajustement : comportement historique strictement égal."""
        self.assertIsNone(self.lead.score_ajustement)
        avant = compute_score(self.lead)
        self.lead.score_ajustement = 0
        self.assertEqual(compute_score(self.lead), avant)

    def test_ajustement_positif_ajoute_au_score(self):
        base = compute_score(self.lead)
        self.lead.score_ajustement = 7
        self.assertEqual(compute_score(self.lead), base + 7)

    def test_ajustement_negatif_retire_du_score(self):
        base = compute_score(self.lead)
        self.lead.score_ajustement = -5
        self.assertEqual(compute_score(self.lead), base - 5)

    def test_score_reste_borne_entre_0_et_100(self):
        self.lead.score_ajustement = 500
        self.assertEqual(compute_score(self.lead), 100)
        self.lead.score_ajustement = -500
        self.assertEqual(compute_score(self.lead), 0)

    def test_le_delta_survit_au_recalcul(self):
        """LE défaut corrigé : avant, un recalcul écrasait le delta."""
        self.lead.score_ajustement = 9
        self.lead.save(update_fields=['score_ajustement'])
        attendu = compute_score(self.lead)

        recompute_lead_score(self.lead)
        self.lead.refresh_from_db()

        self.assertEqual(self.lead.score_ajustement, 9)
        self.assertEqual(self.lead.score, attendu)

        # Un SECOND recalcul (édition suivante, job nocturne…) non plus.
        recompute_lead_score(self.lead)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.score_ajustement, 9)
        self.assertEqual(self.lead.score, attendu)

    def test_ajustement_visible_dans_la_decomposition(self):
        self.lead.score_ajustement = 6
        facteurs = {r['facteur']: r['points'] for r in score_reasons(self.lead)}
        self.assertEqual(facteurs.get('ajustement'), 6)

    def test_ajustement_negatif_visible_dans_la_decomposition(self):
        """Un score rabaissé à la main doit s'EXPLIQUER : la décomposition
        n'affiche que les facteurs positifs, sauf celui-ci."""
        self.lead.score_ajustement = -4
        facteurs = {r['facteur']: r['points'] for r in score_reasons(self.lead)}
        self.assertEqual(facteurs.get('ajustement'), -4)

    def test_ajustement_nul_absent_de_la_decomposition(self):
        facteurs = [r['facteur'] for r in score_reasons(self.lead)]
        self.assertNotIn('ajustement', facteurs)


class BadgeSertLaColonnePersisteeTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX22 badge', slug='taqinor-crx22-badge')
        self.role = Role.objects.create(
            company=self.company, nom='Commercial CRX22',
            permissions=['crm_creer', 'crm_modifier'])
        self.user = User.objects.create_user(
            username='resp_crx22', password='x', company=self.company,
            role=self.role)
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead badge', stage=stages.NEW,
            telephone='0612345678')

    def test_le_badge_lit_la_colonne_pas_un_calcul_live(self):
        """Colonne volontairement DÉSYNCHRONISÉE du calcul : si le badge
        renvoyait le calcul, il ignorerait cette valeur — et le tri, qui lit
        la colonne, afficherait un autre ordre que les badges."""
        fige = min(100, compute_score(self.lead) + 25)
        Lead.objects.filter(pk=self.lead.pk).update(score=fige)
        self.lead.refresh_from_db()
        self.assertNotEqual(fige, compute_score(self.lead))

        donnees = LeadSerializer(self.lead).data

        self.assertEqual(donnees['score'], fige)
        self.assertEqual(donnees['score_label'], score_label(fige))

    def test_colonne_nulle_retombe_sur_le_calcul(self):
        """Leads importés avant QJ6 : le badge ne doit pas afficher un trou."""
        Lead.objects.filter(pk=self.lead.pk).update(score=None)
        self.lead.refresh_from_db()

        donnees = LeadSerializer(self.lead).data

        self.assertEqual(donnees['score'], compute_score(self.lead))
        self.assertIsNotNone(donnees['score_label'])

    def test_badge_et_ma_file_sur_la_meme_valeur(self):
        """« Ma file » filtre sur ``score__gte=60`` : le badge doit annoncer
        exactement la valeur qui a fait entrer (ou non) le lead dans la file."""
        Lead.objects.filter(pk=self.lead.pk).update(
            score=75, owner=self.user, first_contacted_at=None)
        self.lead.refresh_from_db()

        file_items = list(leads_chauds_non_contactes(self.company, self.user))
        donnees = LeadSerializer(self.lead).data

        self.assertIn(self.lead.pk, [item.pk for item in file_items])
        self.assertEqual(donnees['score'], 75)

    def test_api_liste_expose_la_colonne(self):
        Lead.objects.filter(pk=self.lead.pk).update(score=63)
        client_api = APIClient()
        client_api.force_authenticate(self.user)

        res = client_api.get(f'/api/django/crm/leads/{self.lead.pk}/')

        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['score'], 63)


class RecalculQuotidienTests(TestCase):
    """La décote de récence redevient vraie sur les leads dormants."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CRX22 beat', slug='taqinor-crx22-beat')

    def _lead_dormant(self, **extra):
        """Lead créé il y a longtemps ET non modifié depuis (les deux colonnes
        sont ``auto_now_add``/``auto_now`` : on les repousse par ``update``,
        qui ne les rafraîchit pas)."""
        from django.utils import timezone

        lead = Lead.objects.create(
            company=self.company, nom='Lead dormant', stage=stages.NEW,
            telephone='0612345678', ville='Casablanca', **extra)
        vieux = timezone.now() - datetime.timedelta(days=200)
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=vieux, date_modification=vieux, score=95)
        lead.refresh_from_db()
        return lead

    def test_le_score_dormant_est_rafraichi(self):
        lead = self._lead_dormant()
        attendu = compute_score(lead)
        self.assertNotEqual(attendu, 95)

        resume = recalculer_scores_obsoletes()

        lead.refresh_from_db()
        self.assertEqual(lead.score, attendu)
        self.assertEqual(resume['mis_a_jour'], 1)

    def test_le_recalcul_ne_rajeunit_pas_le_lead(self):
        """``save(update_fields=['score'])`` ne touche pas ``date_modification``
        (auto_now n'est rafraîchi que si le champ est dans update_fields) :
        sans quoi le passage nocturne ferait passer chaque lead dormant pour
        un lead fraîchement édité."""
        lead = self._lead_dormant()
        avant = lead.date_modification

        recalculer_scores_obsoletes()

        lead.refresh_from_db()
        self.assertEqual(lead.date_modification, avant)

    def test_un_lead_touche_aujourd_hui_est_ignore(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead du jour', stage=stages.NEW)
        Lead.objects.filter(pk=lead.pk).update(score=95)

        resume = recalculer_scores_obsoletes()

        lead.refresh_from_db()
        self.assertEqual(lead.score, 95)
        self.assertEqual(resume['examines'], 0)

    def test_un_score_deja_juste_n_est_pas_reecrit(self):
        lead = self._lead_dormant()
        Lead.objects.filter(pk=lead.pk).update(score=compute_score(lead))

        resume = recalculer_scores_obsoletes()

        self.assertEqual(resume['examines'], 1)
        self.assertEqual(resume['mis_a_jour'], 0)

    def test_l_ajustement_est_applique_par_le_passage_nocturne(self):
        lead = self._lead_dormant()
        Lead.objects.filter(pk=lead.pk).update(score_ajustement=11)
        lead.refresh_from_db()
        attendu = compute_score(lead)

        recalculer_scores_obsoletes()

        lead.refresh_from_db()
        self.assertEqual(lead.score, attendu)
        self.assertEqual(lead.score_ajustement, 11)

    def test_le_delai_est_une_constante_de_module(self):
        """Le seuil « non touché » est nommé, pas un nombre magique."""
        self.assertGreaterEqual(DELAI_SCORE_OBSOLETE_JOURS, 1)


class TacheBeatDeclareeTests(TestCase):
    """La tâche existe ET est planifiée : une tâche absente du beat est le
    mode de défaillance dominant du dépôt (bâtie, testée, jamais exécutée)."""

    def test_la_tache_celery_delegue_au_service(self):
        from apps.crm.tasks import recalculer_scores_obsoletes_task

        resume = recalculer_scores_obsoletes_task()

        self.assertEqual(set(resume), {'examines', 'mis_a_jour'})

    def test_la_tache_est_dans_le_beat_schedule(self):
        from erp_agentique.celery import app

        entree = app.conf.beat_schedule.get('crm-recalculer-scores-obsoletes')
        self.assertIsNotNone(entree)
        self.assertEqual(entree['task'], 'crm.recalculer_scores_obsoletes')
