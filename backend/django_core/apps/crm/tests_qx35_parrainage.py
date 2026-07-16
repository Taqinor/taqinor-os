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

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Client, Lead, LeadActivity, Parrainage
from apps.crm.services import handle_parrainage_signup
from apps.notifications.models import Notification
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
