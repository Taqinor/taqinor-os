"""CIQ416 (D-CIQ-20) — routage et notification d'un lead pro : le responsable
désigné (``CompanyProfile.responsable_leads_pro``, CIQ415) reçoit le lead, et
la notification dit que c'est un pro. Rien ne change pour les autres segments
ni quand le réglage est vide.

Appelants qui créent un lead au type CONNU et le transmettent : le webhook du
site (``fields``), la création manuelle (``LeadViewSet.perform_create`` —
``validated_data``), l'import (``lead_attrs``) et, depuis CIQ416, Meta Lead
Ads (type lu sur le formulaire). Ceux qui ne le connaissent pas (OCR,
WhatsApp CTWA, livechat, événement marketing) restent inchangés.

Run :
    python manage.py test apps.crm.tests_ciq416_routage_pro -v 2
"""
import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company
from apps.crm import leads_meta
from apps.crm import leads_notifications
from apps.crm import leads_attribution
from apps.crm.models import Lead
from apps.parametres.models import CompanyProfile

from .tests_webhook import SECRET, payload_site

User = get_user_model()


class RoutagePro(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ416 Co',
                                              slug='ciq416-co')
        self.defaut = User.objects.create_user(
            username='ciq416_defaut', password='x',
            role_legacy='responsable', company=self.company)
        self.pro = User.objects.create_user(
            username='ciq416_pro', password='x', role_legacy='responsable',
            company=self.company)
        self.profile, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        self.profile.responsable_defaut_leads = self.defaut
        self.profile.save()

    def _avec_reglage(self):
        self.profile.responsable_leads_pro = self.pro
        self.profile.save()

    def test_commercial_avec_reglage_va_au_responsable_pro(self):
        self._avec_reglage()
        for segment in ('commercial', 'industriel'):
            self.assertEqual(leads_attribution.default_responsable_for(
                self.company, {'type_installation': segment}), self.pro)

    def test_sans_reglage_comportement_identique(self):
        self.assertEqual(leads_attribution.default_responsable_for(
            self.company, {'type_installation': 'commercial'}), self.defaut)

    def test_residentiel_et_type_inconnu_inchanges(self):
        self._avec_reglage()
        for attrs in ({'type_installation': 'residentiel'},
                      {'type_installation': 'agricole'}, {}, None):
            self.assertEqual(
                leads_attribution.default_responsable_for(self.company, attrs),
                self.defaut, attrs)

    def test_responsable_pro_inactif_ignore(self):
        self._avec_reglage()
        self.pro.is_active = False
        self.pro.save()
        self.assertEqual(leads_attribution.default_responsable_for(
            self.company, {'type_installation': 'commercial'}), self.defaut)

    @override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
    def test_lead_pro_du_webhook(self):
        self._avec_reglage()
        res = self.client.post(
            reverse('website-lead-webhook'),
            data=json.dumps(payload_site(mode='professionnel')),
            content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET)
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.owner, self.pro)

    @override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
    def test_lead_residentiel_du_webhook_inchange(self):
        self._avec_reglage()
        res = self.client.post(
            reverse('website-lead-webhook'),
            data=json.dumps(payload_site()),
            content_type='application/json', HTTP_X_WEBHOOK_SECRET=SECRET)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.owner, self.defaut)

    def test_lead_meta_commercial(self):
        self._avec_reglage()
        lead = leads_meta.create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='ciq416-1',
            field_data=[
                {'name': 'full_name', 'values': ['Hôtel Atlas']},
                {'name': 'phone_number', 'values': ['+212600000416']},
                {'name': 'où_souhaitez-vous_installer_votre_système_solaire_?',
                 'values': ['pour_mon_entreprise']},
            ], form_id='FORM-PRO')
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation, 'commercial')
        self.assertEqual(lead.owner, self.pro)


class NotificationPro(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ416 N', slug='ciq416-n')
        self.owner = User.objects.create_user(
            username='ciq416_owner', password='x', role_legacy='responsable',
            company=self.company)
        self.pro = User.objects.create_user(
            username='ciq416_pro_n', password='x', role_legacy='responsable',
            company=self.company)
        profile, _ = CompanyProfile.objects.get_or_create(
            company=self.company)
        profile.responsable_leads_pro = self.pro
        profile.save()

    def _notifier(self, lead):
        with mock.patch('apps.notifications.services.notify_many') as envoi:
            leads_notifications.notify_new_lead(lead)
        self.assertEqual(envoi.call_count, 1)
        destinataires, _type, titre = envoi.call_args.args[:3]
        return list(destinataires), titre, envoi.call_args.kwargs['body']

    def test_titre_et_corps_pro_sans_chiffre_non_declare(self):
        lead = Lead.objects.create(
            company=self.company, nom='Hôtel Atlas', owner=self.owner,
            type_installation='commercial', categorie_commerciale='hotel',
            facture_hiver=Decimal('25000'), tension_raccordement='bt',
            tension_source='declare')
        destinataires, titre, corps = self._notifier(lead)
        self.assertEqual(titre, 'Nouveau lead PRO (commercial) : Hôtel Atlas')
        self.assertIn('Activité : Hôtel / riad.', corps)
        self.assertIn('Facture déclarée : 25 000 MAD/mois.', corps)
        self.assertIn('Raccordement : basse tension (BT).', corps)
        self.assertNotIn('kWh', corps)
        self.assertIn(self.pro, destinataires)

    def test_tension_par_defaut_du_site_non_affichee(self):
        lead = Lead.objects.create(
            company=self.company, nom='Usine', owner=self.owner,
            type_installation='industriel', tension_raccordement='bt',
            tension_source='site_defaut_visible', bill_kwh=Decimal('40000'))
        _d, titre, corps = self._notifier(lead)
        self.assertTrue(titre.startswith('Nouveau lead PRO (industriel)'))
        self.assertNotIn('Raccordement', corps)
        self.assertIn('Consommation déclarée : 40 000 kWh/mois.', corps)

    def test_residentiel_inchange(self):
        lead = Lead.objects.create(
            company=self.company, nom='Villa', owner=self.owner,
            type_installation='residentiel')
        destinataires, titre, corps = self._notifier(lead)
        self.assertEqual(titre, 'Nouveau lead : Villa')
        self.assertNotIn(self.pro, destinataires)
        self.assertNotIn('Activité', corps)
