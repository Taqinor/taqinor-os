"""ACRM14 (C-ACRM-009) — un lead Meta Lead Ads n'est enrichi qu'UNE fois.

Sonde V_VB LSVC2-6 : la commerciale repassait la priorité à « normale » et
vidait le WhatsApp ; un rejeu du webhook (ou la repasse du pull) rétablissait
« haute » et le numéro, sans une ligne de chatter. Désormais une passe
suivante ne réécrit rien quand la note « [Formulaire Meta] » existe déjà, et
la première passe journalise chaque champ enrichi (ancien → nouveau).

Payload de fixture (forme réelle du Graph API) ; aucun appel réseau.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity
from apps.crm.leads_meta import create_lead_from_meta_lead_ads

User = get_user_model()
Q_INSTALL = 'où_souhaitez-vous_installer_votre_système_solaire_?'
Q_FACTURE = "quelle_est_votre_facture_moyenne_d'électricité_par_mois_?"
Q_QUAND = "quand_comptez-vous_commencer_l'installation_?"
FIELD_DATA = [
    {'name': 'full_name', 'values': ['Amine Rejeu']},
    {'name': 'phone_number', 'values': ['+212600014014']},
    {'name': 'city', 'values': ['casablanca']},
    {'name': Q_INSTALL, 'values': ['sur_ma_villa']},
    {'name': Q_FACTURE, 'values': ['entre_1000_dh_à_2000_dh']},
    {'name': Q_QUAND, 'values': ['le_plus_tôt_possible_(ce_mois-ci)']},
]


class MetaRejeuTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM14 Solaire', slug='acrm14-meta')
        self.user = User.objects.create_user(
            username='acrm14-resp', password='x', company=self.company,
            role_legacy='responsable')

    def _passe(self):
        return create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='ACRM14-1',
            field_data=FIELD_DATA, form_id='FORM-4.0')

    def test_correction_survit_au_rejeu(self):
        lead = self._passe()
        self.assertEqual(lead.priorite, Lead.Priorite.HAUTE)
        self.assertEqual(lead.whatsapp, lead.telephone)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        resp = api.patch(f'/api/django/crm/leads/{lead.pk}/',
                         {'priorite': 'normale', 'whatsapp': ''},
                         format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        lignes_avant = LeadActivity.objects.filter(lead=lead).count()
        rejoue = self._passe()
        self.assertEqual(rejoue.pk, lead.pk)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, Lead.Priorite.NORMALE)
        self.assertIn(lead.whatsapp, (None, ''))
        self.assertEqual(LeadActivity.objects.filter(lead=lead).count(),
                         lignes_avant)

    def test_premiere_passe_tracee(self):
        lead = self._passe()
        lignes = {a.field: a for a in LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.MODIFICATION)}
        for champ in ('facture_hiver', 'type_installation', 'whatsapp'):
            self.assertIn(champ, lignes, champ)
            self.assertIsNone(lignes[champ].user_id)
            self.assertEqual(lignes[champ].old_value, '—')
            self.assertNotEqual(lignes[champ].new_value, '—')

    def _lead_existant(self, saisies):
        """Lead Meta déjà capturé SANS note « [Formulaire Meta] » (importé
        avant le mapping) : le rejeu l'enrichit — c'est le chemin d'AMET19."""
        return Lead.objects.create(
            company=self.company, nom='Amine Rejeu', telephone='+212600014014',
            whatsapp='', priorite=Lead.Priorite.NORMALE,
            external_system='meta_lead_ads', external_id='ACRM14-1',
            saisies_humaines=saisies)

    def test_rejeu_meta_respecte_les_saisies_humaines(self):
        """AMET19 — WhatsApp vidé et priorité baissée à la main (clés dans
        ``saisies_humaines``) : le rejeu ne les remet pas."""
        lead = self._lead_existant(['priorite', 'whatsapp'])
        self.assertEqual(self._passe().pk, lead.pk)
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, Lead.Priorite.NORMALE)
        self.assertIn(lead.whatsapp, (None, ''))
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, user__isnull=True,
            field__in=('priorite', 'whatsapp')).exists())

    def test_rejeu_meta_remplit_un_lead_jamais_touche(self):
        """AMET19 — sans saisie humaine, le rejeu remplit comme avant."""
        lead = self._lead_existant([])
        self._passe()
        lead.refresh_from_db()
        self.assertEqual(lead.priorite, Lead.Priorite.HAUTE)
        self.assertEqual(lead.whatsapp, lead.telephone)
