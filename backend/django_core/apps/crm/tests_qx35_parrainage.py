"""QX35 — Wire the parrainage promise.

Covers:
  - `Client.code_parrainage` is generated deterministically on first save;
  - the website webhook auto-creates a `Parrainage(en_attente)` when
    `utm_source=parrainage` carries a known referral code (`utm_campaign`);
  - unknown code / missing utm_source / auto-parrainage → no Parrainage;
  - idempotent (a re-post/replay never creates a duplicate Parrainage);
  - `devis_accepted` flips the matching Parrainage to `converti` when the
    filleul signs (receiver wired via core.events, no ventes import in crm
    production code).
"""
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Client, Lead, LeadActivity, Parrainage
from apps.crm.services import handle_parrainage_signup
from apps.notifications.models import Notification
from apps.records.models import Activity
from apps.ventes.models import Devis
from core.events import devis_accepted

User = get_user_model()
SECRET = 'test-secret-qx35'
MONTH = timezone.now().strftime('%Y%m')


class ClientCodeParrainageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX35', slug='taqinor-qx35')

    def test_code_generated_deterministically_on_first_save(self):
        client = Client.objects.create(company=self.company, nom='Parrain Un')
        self.assertEqual(client.code_parrainage, f'TQ-{client.pk}')

    def test_code_unique_per_client(self):
        c1 = Client.objects.create(company=self.company, nom='A')
        c2 = Client.objects.create(company=self.company, nom='B')
        self.assertNotEqual(c1.code_parrainage, c2.code_parrainage)

    def test_resave_does_not_change_code(self):
        client = Client.objects.create(company=self.company, nom='Stable')
        code = client.code_parrainage
        client.nom = 'Stable modifié'
        client.save()
        client.refresh_from_db()
        self.assertEqual(client.code_parrainage, code)


class HandleParrainageSignupTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX35 Signup', slug='taqinor-qx35-signup')
        self.parrain = Client.objects.create(
            company=self.company, nom='Client Parrain', telephone='+212600111111',
            email='parrain@example.com')

    def _lead(self, **extra):
        defaults = dict(
            company=self.company, nom='Filleul Test', telephone='+212600222222',
            utm_source='parrainage', utm_campaign=self.parrain.code_parrainage)
        defaults.update(extra)
        return Lead.objects.create(**defaults)

    def test_creates_parrainage_en_attente(self):
        lead = self._lead()
        handle_parrainage_signup(lead)
        p = Parrainage.objects.get(filleul_lead=lead)
        self.assertEqual(p.parrain, self.parrain)
        self.assertEqual(p.statut, Parrainage.Statut.EN_ATTENTE)
        self.assertEqual(p.company, self.company)

    def test_notifies_managers(self):
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Directeur', permissions=['crm_voir'])
        manager = User.objects.create_user(
            username='mgr_qx35', password='x', company=self.company, role=role)
        lead = self._lead()
        handle_parrainage_signup(lead)
        self.assertTrue(Notification.objects.filter(recipient=manager).exists())

    def test_chatter_note_on_lead(self):
        lead = self._lead()
        handle_parrainage_signup(lead)
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__icontains='parrain').exists())

    def test_no_utm_source_no_op(self):
        lead = self._lead(utm_source='facebook')
        handle_parrainage_signup(lead)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead).exists())

    def test_unknown_code_no_op(self):
        lead = self._lead(utm_campaign='CODE-INCONNU')
        handle_parrainage_signup(lead)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead).exists())

    def test_missing_code_no_op(self):
        lead = self._lead(utm_campaign='')
        handle_parrainage_signup(lead)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead).exists())

    def test_self_referral_blocked_by_phone(self):
        lead = self._lead(telephone='+212600111111')  # même tel que le parrain
        handle_parrainage_signup(lead)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead).exists())

    def test_self_referral_blocked_by_email(self):
        lead = self._lead(telephone='+212699999999', email='parrain@example.com')
        handle_parrainage_signup(lead)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead).exists())

    def test_idempotent_never_duplicates(self):
        lead = self._lead()
        handle_parrainage_signup(lead)
        handle_parrainage_signup(lead)
        self.assertEqual(Parrainage.objects.filter(filleul_lead=lead).count(), 1)

    def test_idempotent_par_filleul_meme_parrain_lead_different(self):
        """18/08/2026 — chaque soumission du site CRÉE désormais un NOUVEAU
        lead (règle fondateur) : le même filleul (même téléphone) qui
        re-soumet /parrainage obtient donc une fiche DIFFÉRENTE à chaque
        fois. L'idempotence PAR LEAD (test ci-dessus) ne voit plus ces
        reprises — elle doit rester idempotente PAR FILLEUL (téléphone/e-mail
        normalisés) + même parrain : pas de 2e Parrainage en_attente."""
        lead1 = self._lead()
        handle_parrainage_signup(lead1)
        self.assertEqual(Parrainage.objects.count(), 1)

        lead2 = self._lead()  # même téléphone/code — nouvelle fiche.
        handle_parrainage_signup(lead2)

        self.assertEqual(Parrainage.objects.count(), 1)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead2).exists())

    def test_meme_parrain_laisse_une_note_au_lieu_du_silence(self):
        """La sortie « même filleul, même parrain » était SILENCIEUSE : deux
        salariés d'un même client (adresse contact@ partagée) ou un foyer au
        même mobile faisaient disparaître la 2e recommandation du CRM. Elle
        laisse désormais une note sobre sur le NOUVEAU lead."""
        from apps.crm.services import PARRAINAGE_DEJA_ENREGISTRE_MARKER

        lead1 = self._lead()
        handle_parrainage_signup(lead1)
        premier = Parrainage.objects.get(filleul_lead=lead1)

        lead2 = self._lead(nom='Second Filleul')  # même contact, même code
        handle_parrainage_signup(lead2)

        # Toujours aucun doublon de Parrainage.
        self.assertEqual(Parrainage.objects.count(), 1)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead2).exists())
        # …mais la trace existe, sur le nouveau lead, avec parrain + date.
        note = LeadActivity.objects.filter(
            lead=lead2, kind=LeadActivity.Kind.NOTE,
            body__startswith=PARRAINAGE_DEJA_ENREGISTRE_MARKER).first()
        self.assertIsNotNone(note)
        self.assertIsNone(note.user)
        self.assertEqual(note.company, self.company)
        self.assertIn(self.parrain.nom, note.body)
        self.assertIn(
            timezone.localtime(premier.date_creation).strftime('%d/%m/%Y'),
            note.body)
        self.assertIn('pas de doublon créé', note.body)
        # Le premier lead, lui, garde sa seule note de parrainage.
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead1,
            body__startswith=PARRAINAGE_DEJA_ENREGISTRE_MARKER).exists())

    def test_parrain_different_sur_resoumission_garde_le_premier(self):
        """Filleul identique, code de parrain DIFFÉRENT sur la re-soumission :
        cas ambigu — le premier parrainage n'est jamais réattribué, le
        nouveau lead reçoit une note chatter expliquant l'ignoré."""
        lead1 = self._lead()
        handle_parrainage_signup(lead1)
        parrainage = Parrainage.objects.get(filleul_lead=lead1)

        autre_parrain = Client.objects.create(
            company=self.company, nom='Autre Parrain',
            telephone='+212600999999')
        lead2 = self._lead(utm_campaign=autre_parrain.code_parrainage)
        handle_parrainage_signup(lead2)

        self.assertEqual(Parrainage.objects.count(), 1)
        parrainage.refresh_from_db()
        self.assertEqual(parrainage.parrain, self.parrain)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead2).exists())

        note = LeadActivity.objects.filter(
            lead=lead2, kind=LeadActivity.Kind.NOTE,
            body__icontains='2e code de parrainage').first()
        self.assertIsNotNone(note)
        self.assertIn(self.parrain.nom, note.body)

    def test_cross_company_code_never_matches(self):
        other = Company.objects.create(nom='Autre QX35', slug='autre-qx35')
        lead = Lead.objects.create(
            company=other, nom='Filleul Autre Co', telephone='+212600333333',
            utm_source='parrainage', utm_campaign=self.parrain.code_parrainage)
        handle_parrainage_signup(lead)
        self.assertFalse(Parrainage.objects.filter(filleul_lead=lead).exists())


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebhookParrainageIntegrationTests(TestCase):
    """Bout en bout : le webhook site web déclenche handle_parrainage_signup."""

    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor QX35 WH', slug='taqinor-qx35-wh')
        self.parrain = Client.objects.create(
            company=self.company, nom='Parrain WH', telephone='+212611000000')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data), content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_referred_lead_creates_visible_parrainage(self):
        res = self.post({
            'fullName': 'Filleul Webhook',
            'phoneE164': '+212622333344',
            'consent': True,
            'utm': {
                'utm_source': 'parrainage',
                'utm_campaign': self.parrain.code_parrainage,
            },
        })
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        p = Parrainage.objects.get(filleul_lead=lead)
        self.assertEqual(p.parrain, self.parrain)
        self.assertEqual(p.statut, Parrainage.Statut.EN_ATTENTE)


class DevisAcceptedFlipsParrainageTests(TestCase):
    """QX35 — la signature du filleul convertit son Parrainage en_attente."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='qx35-evt-co', defaults={'nom': 'QX35 Evt Co'})
        self.user = User.objects.create_user(
            username='qx35_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.parrain = Client.objects.create(company=self.company, nom='Parrain Evt')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client Filleul', prenom='Evt',
            email='filleul-evt@example.com', telephone='+212600000099')

    def _devis(self, lead, num, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-QX35{num:04d}',
            client=self.client_obj, lead=lead, statut=statut,
            taux_tva=Decimal('20'))

    def test_signal_flips_converti(self):
        lead = Lead.objects.create(company=self.company, nom='Filleul Signe', stage='QUOTE_SENT')
        parrainage = Parrainage.objects.create(
            company=self.company, parrain=self.parrain, filleul_lead=lead,
            statut=Parrainage.Statut.EN_ATTENTE)
        devis = self._devis(lead, num=1, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        parrainage.refresh_from_db()
        self.assertEqual(parrainage.statut, Parrainage.Statut.CONVERTI)

    def test_no_parrainage_no_op(self):
        lead = Lead.objects.create(company=self.company, nom='Sans Parrainage', stage='QUOTE_SENT')
        devis = self._devis(lead, num=2, statut=Devis.Statut.ACCEPTE)
        # Ne doit jamais lever, même sans Parrainage associé.
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')

    def test_already_converti_never_reverted(self):
        lead = Lead.objects.create(company=self.company, nom='Deja Converti', stage='SIGNED')
        parrainage = Parrainage.objects.create(
            company=self.company, parrain=self.parrain, filleul_lead=lead,
            statut=Parrainage.Statut.RECOMPENSE_VERSEE)
        devis = self._devis(lead, num=3, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        parrainage.refresh_from_db()
        self.assertEqual(parrainage.statut, Parrainage.Statut.RECOMPENSE_VERSEE)

    # ── PUB65 — suggestion de graine pub géo/lookalike sur le PARRAIN ────────

    def test_conversion_posts_suggestion_note_on_parrain(self):
        lead = Lead.objects.create(
            company=self.company, nom='Filleul Suggestion', stage='QUOTE_SENT')
        Parrainage.objects.create(
            company=self.company, parrain=self.parrain, filleul_lead=lead,
            statut=Parrainage.Statut.EN_ATTENTE)
        devis = self._devis(lead, num=4, statut=Devis.Statut.ACCEPTE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')

        ct = ContentType.objects.get_for_model(Client)
        note = Activity.objects.filter(
            content_type=ct, object_id=self.parrain.pk,
            kind=Activity.Kind.NOTE).first()
        self.assertIsNotNone(note)
        self.assertIn('graine lookalike', note.body)

    def test_suggestion_never_blocks_conversion_even_if_note_fails(self):
        lead = Lead.objects.create(
            company=self.company, nom='Filleul Robuste', stage='QUOTE_SENT')
        parrainage = Parrainage.objects.create(
            company=self.company, parrain=self.parrain, filleul_lead=lead,
            statut=Parrainage.Statut.EN_ATTENTE)
        devis = self._devis(lead, num=5, statut=Devis.Statut.ACCEPTE)
        with mock.patch(
                'apps.adsengine.audiences.referral_seed_suggestion',
                side_effect=RuntimeError('boom')):
            devis_accepted.send(
                sender=None, devis=devis, user=self.user,
                ancien_statut='envoye')
        parrainage.refresh_from_db()
        self.assertEqual(parrainage.statut, Parrainage.Statut.CONVERTI)
