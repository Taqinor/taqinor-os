"""LB39 — l'undo VX95 d'un changement d'étape était MORT en production.

Le toast « Annuler » PATCHait l'étape EN ARRIÈRE ; la garde funnel du
``LeadSerializer`` (« On ne recule pas une étape. ») 400ait tout recul, donc
chaque annulation finissait en « Annulation impossible ». Le test unitaire
front mockait le dispatch : il n'a jamais vu le 400.

Correction côté SERVEUR : un marqueur ``undo`` (champ write-only HORS modèle)
autorise le recul UNIQUEMENT si le serveur revérifie lui-même, dans le chatter
``LeadActivity``, que la demande est le mouvement INVERSE EXACT du dernier
changement d'étape de ce lead et qu'elle date de moins de
``LeadSerializer.UNDO_WINDOW_SECONDS``. Toute autre marche arrière — y compris
avec ``undo=true`` — reste refusée : le marqueur n'autorise rien à lui seul.

Les clés d'étape suivent la convention des tests existants ; la source
canonique reste STAGES.py (règle #2).

Run :
    docker compose exec django_core python manage.py test \
        apps.crm.tests_lb39_undo_stage -v 2
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

import apps.crm.stages as stages
from apps.crm.models import Lead, LeadActivity
from apps.crm.serializers import LeadSerializer

User = get_user_model()


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class UndoStageBase(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company, _ = Company.objects.get_or_create(
            slug='lb39-co', defaults={'nom': 'LB39 Co'})
        # Multi-tenant : une SECONDE société, pour prouver que l'undo ne
        # franchit jamais la frontière de tenant.
        self.other_company, _ = Company.objects.get_or_create(
            slug='lb39-other', defaults={'nom': 'LB39 Autre'})
        self.user = User.objects.create_user(
            username='lb39_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Undo', prenom='Test',
            stage=stages.NEW)

    def url(self, lead=None):
        return f'/api/django/crm/leads/{(lead or self.lead).id}/'

    def avance(self, api, cible):
        """Avance d'une étape via l'API (le serveur journalise le chatter)."""
        r = api.patch(self.url(), {'stage': cible}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.lead.refresh_from_db()
        return r


class TestUndoStageChange(UndoStageBase):
    def test_recul_sans_marqueur_reste_refuse(self):
        """La garde funnel est INCHANGÉE : un recul nu vaut toujours 400."""
        api = auth(self.user)
        self.avance(api, stages.CONTACTED)

        r = api.patch(self.url(), {'stage': stages.NEW}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('stage', r.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_recul_avec_marqueur_undo_aboutit(self):
        """Le toast « Annuler » revient EXACTEMENT à l'étape antérieure."""
        api = auth(self.user)
        self.avance(api, stages.CONTACTED)

        r = api.patch(
            self.url(), {'stage': stages.NEW, 'undo': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)

    def test_le_marqueur_nest_jamais_persiste(self):
        """``undo`` est hors modèle : il ne doit jamais sortir en réponse ni
        atteindre ``.save()`` (sinon un AttributeError au premier PATCH)."""
        api = auth(self.user)
        self.avance(api, stages.CONTACTED)
        r = api.patch(
            self.url(), {'stage': stages.NEW, 'undo': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn('undo', r.data)
        self.assertFalse(hasattr(Lead.objects.get(pk=self.lead.pk), 'undo'))

    def test_marqueur_sur_un_autre_recul_reste_refuse(self):
        """Le marqueur n'est PAS un passe-droit : seul le mouvement inverse
        EXACT du dernier changement est annulable."""
        api = auth(self.user)
        self.avance(api, stages.CONTACTED)
        self.avance(api, stages.QUOTE_SENT)

        # Le dernier changement est CONTACTED → QUOTE_SENT ; sauter jusqu'à
        # NEW n'en est pas l'annulation.
        r = api.patch(
            self.url(), {'stage': stages.NEW, 'undo': True}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.QUOTE_SENT)

        # …alors que l'annulation exacte, elle, passe.
        r = api.patch(
            self.url(), {'stage': stages.CONTACTED, 'undo': True},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_marqueur_hors_fenetre_reste_refuse(self):
        """Passé la fenêtre courte, ce n'est plus une annulation mais un
        recul manuel — refusé."""
        api = auth(self.user)
        self.avance(api, stages.CONTACTED)

        vieux = timezone.now() - timedelta(
            seconds=LeadSerializer.UNDO_WINDOW_SECONDS + 60)
        (LeadActivity.objects
         .filter(lead=self.lead, field='stage')
         .update(created_at=vieux))

        r = api.patch(
            self.url(), {'stage': stages.NEW, 'undo': True}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.CONTACTED)

    def test_sans_aucune_trace_de_chatter_le_marqueur_nautorise_rien(self):
        """Étape posée sans passer par l'API (import, script) : aucune entrée
        de chatter → rien à annuler, la garde funnel s'applique."""
        Lead.objects.filter(pk=self.lead.pk).update(stage=stages.CONTACTED)
        LeadActivity.objects.filter(lead=self.lead).delete()

        api = auth(self.user)
        r = api.patch(
            self.url(), {'stage': stages.NEW, 'undo': True}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_lead_perdu_reste_verrouille_meme_avec_le_marqueur(self):
        """La garde « lead perdu » précède l'exception d'annulation."""
        api = auth(self.user)
        self.avance(api, stages.CONTACTED)
        Lead.objects.filter(pk=self.lead.pk).update(perdu=True)

        r = api.patch(
            self.url(), {'stage': stages.NEW, 'undo': True}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_undo_ne_franchit_pas_la_frontiere_de_societe(self):
        """Multi-tenant : un lead d'une AUTRE société reste invisible — le
        marqueur ne change rien à ce filtrage (404, jamais 200)."""
        autre = Lead.objects.create(
            company=self.other_company, nom='Autre', prenom='Tenant',
            stage=stages.CONTACTED)
        LeadActivity.objects.create(
            company=self.other_company, lead=autre,
            kind=LeadActivity.Kind.MODIFICATION, field='stage',
            field_label='Étape',
            old_value=stages.STAGE_LABELS[stages.NEW],
            new_value=stages.STAGE_LABELS[stages.CONTACTED])

        api = auth(self.user)
        r = api.patch(
            self.url(autre), {'stage': stages.NEW, 'undo': True},
            format='json')
        self.assertEqual(r.status_code, 404, r.data)
        autre.refresh_from_db()
        self.assertEqual(autre.stage, stages.CONTACTED)

    def test_le_chatter_journalise_le_retour_en_arriere(self):
        """L'annulation reste une modification tracée (jamais un effacement
        silencieux de l'historique)."""
        api = auth(self.user)
        self.avance(api, stages.CONTACTED)
        api.patch(self.url(), {'stage': stages.NEW, 'undo': True},
                  format='json')

        entrees = list(
            LeadActivity.objects
            .filter(lead=self.lead, field='stage')
            .order_by('created_at', 'id'))
        self.assertGreaterEqual(len(entrees), 2)
        derniere = entrees[-1]
        self.assertIn(
            derniere.new_value,
            (stages.STAGE_LABELS[stages.NEW], stages.NEW))
