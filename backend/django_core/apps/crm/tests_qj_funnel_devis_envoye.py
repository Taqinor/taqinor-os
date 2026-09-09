"""QJ-FUNNEL (fondateur 09/09/2026) — le milieu du funnel bouge enfin.

Constat fondateur : « ça marche pour le bouger à Contacté, ça marche pour le
bouger à Froid » — mais rien ne poussait jamais un lead vers « Devis envoyé »
ni vers « Relance » dans le vrai flux de travail. Deux mouvements, même
doctrine 07/09/2026 (le funnel ne bouge que sur un geste/une réponse
confirmés, jamais sur un comportement observé) :

  (a) cocher FAIT la touche « Préparer et envoyer le devis » (la même
      détection RELANCE-SUITE qui démarre le plan après-devis) place le lead
      à QUOTE_SENT — ``avancer_stage_devis_envoye_sur_touche`` ;
  (b) une réponse « joint »/« intéressé » journalisée après l'envoi passe le
      lead QUOTE_SENT → FOLLOW_UP — ``avancer_stage_sur_reponse_devis``,
      déclenchée par le MÊME récepteur d'activité que NEW → CONTACTED
      (mêmes kinds, rien d'élargi), donc couvre la clôture de touche ET
      l'appel journalisé à la main.

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.tests_qj_funnel_devis_envoye -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import Lead, LeadActivity, RelanceEtape
from apps.crm.services import (
    FILET_JOINT_LIBELLE,
    avancer_stage_devis_envoye_sur_touche,
    avancer_stage_sur_reponse_devis,
    marquer_etape_relance,
)

User = get_user_model()


class _Base(TestCase):
    slug = 'qjf'

    def setUp(self):
        self.company = Company.objects.get_or_create(
            slug=f'{self.slug}-co', defaults={'nom': f'{self.slug} Co'})[0]
        self.user = User.objects.create_user(
            username=f'{self.slug}-u', password='x',
            role_legacy='responsable', company=self.company)

    def _lead(self, stage=stages.CONTACTED, **kw):
        return Lead.objects.create(
            company=self.company, nom='Funnel', stage=stage, **kw)

    def _touche_envoi(self, lead, libelle=FILET_JOINT_LIBELLE):
        now = timezone.now()
        return RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1, canal='appel',
            due_date=now.date(), due_at=now, cadence='generique',
            libelle=libelle)


class TestToucheEnvoiDevisFaite(_Base):
    """(a) FAIT sur la touche d'envoi → QUOTE_SENT."""
    slug = 'qjf-touche'

    def test_fait_place_le_lead_a_devis_envoye(self):
        lead = self._lead(stage=stages.CONTACTED)
        etape = self._touche_envoi(lead)
        marquer_etape_relance(etape, self.user, RelanceEtape.Statut.FAIT)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.MODIFICATION, field='stage')
        self.assertTrue(any(
            'envoyer le devis' in (n.body or '') for n in notes))

    def test_sauter_la_touche_ne_bouge_rien(self):
        lead = self._lead(stage=stages.CONTACTED)
        etape = self._touche_envoi(lead)
        marquer_etape_relance(etape, self.user, RelanceEtape.Statut.SAUTEE)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_cold_est_reactive_vers_devis_envoye(self):
        # Même doctrine que _rang_funnel : COLD est un parking (rang -1),
        # l'envoi d'un devis le réactive.
        lead = self._lead(stage=stages.COLD)
        etape = self._touche_envoi(lead)
        marquer_etape_relance(etape, self.user, RelanceEtape.Statut.FAIT)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)

    def test_jamais_en_arriere_depuis_follow_up(self):
        lead = self._lead(stage=stages.FOLLOW_UP)
        etape = self._touche_envoi(lead)
        marquer_etape_relance(etape, self.user, RelanceEtape.Statut.FAIT)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)

    def test_perdu_ignore(self):
        lead = self._lead(stage=stages.CONTACTED, perdu=True)
        self.assertFalse(
            avancer_stage_devis_envoye_sur_touche(lead, self.user))
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_une_autre_touche_generique_ne_bouge_rien(self):
        lead = self._lead(stage=stages.CONTACTED)
        etape = self._touche_envoi(lead, libelle='Décider la suite')
        marquer_etape_relance(etape, self.user, RelanceEtape.Statut.FAIT)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)


class TestReponseApresDevis(_Base):
    """(b) réponse joint/intéressé sur un lead QUOTE_SENT → FOLLOW_UP."""
    slug = 'qjf-rep'

    def _activite(self, lead, outcome, kind=None, user='defaut'):
        return LeadActivity.objects.create(
            company=self.company, lead=lead,
            user=self.user if user == 'defaut' else user,
            kind=kind or LeadActivity.Kind.APPEL,
            outcome=outcome, body='Appel de relance')

    def test_joint_avance_vers_relance(self):
        lead = self._lead(stage=stages.QUOTE_SENT)
        self._activite(lead, 'joint')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.MODIFICATION, field='stage')
        self.assertTrue(any(
            'réponse du client' in (n.body or '') for n in notes))

    def test_interesse_avance_vers_relance(self):
        lead = self._lead(stage=stages.QUOTE_SENT)
        self._activite(lead, 'interesse')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)

    def test_contacted_ne_saute_jamais_detape(self):
        # Aucun devis envoyé → une réponse laisse le lead à CONTACTED
        # (l'avance NEW→CONTACTED garde son périmètre, rien d'autre).
        lead = self._lead(stage=stages.CONTACTED)
        self._activite(lead, 'joint')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.CONTACTED)

    def test_non_joint_rappel_refuse_ne_bougent_pas(self):
        for outcome in ('non_joint', 'rappel', 'refuse'):
            lead = self._lead(stage=stages.QUOTE_SENT)
            self._activite(lead, outcome)
            lead.refresh_from_db()
            self.assertEqual(lead.stage, stages.QUOTE_SENT, outcome)

    def test_activite_systeme_sans_user_ne_bouge_pas(self):
        lead = self._lead(stage=stages.QUOTE_SENT)
        self._activite(lead, 'joint', user=None)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.QUOTE_SENT)

    def test_touche_appel_cloturee_joint_avance_vers_relance(self):
        """Bout en bout par la cadence : une touche APPEL après devis marquée
        FAIT avec l'issue « joint » (le geste réel de Meryem) avance le lead."""
        lead = self._lead(stage=stages.QUOTE_SENT)
        now = timezone.now()
        etape = RelanceEtape.objects.create(
            company=self.company, lead=lead, ordre=1, canal='appel',
            due_date=now.date(), due_at=now, cadence='apres_devis',
            libelle='Appel de suivi')
        marquer_etape_relance(
            etape, self.user, RelanceEtape.Statut.FAIT, outcome='joint')
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)

    def test_service_direct_exige_quote_sent_exact(self):
        lead = self._lead(stage=stages.FOLLOW_UP)
        self.assertFalse(avancer_stage_sur_reponse_devis(lead, self.user))
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
