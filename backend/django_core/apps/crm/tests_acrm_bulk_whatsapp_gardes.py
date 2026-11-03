"""ACRM15 (C-ACRM-010) — la file WhatsApp en masse passe par les GARDES et
la discipline de rendu des relances.

Sonde V_VC LSVC3-3 : « Préparer WhatsApp » sur une sélection rendait un
message au lead « ne plus contacter » (count 1), et le gabarit « Réservez
votre visite : {lien_rdv} » partait avec un blanc final. Désormais : les
leads opposés, perdus ou archivés sortent dans ``skipped`` avec leur motif,
aucun lien de réservation n'est créé pour eux, et une phrase dont le
placeholder n'a pas de valeur réelle est OMISE.

POST réel de la vue ``bulk`` ; aucun mock.
"""
import datetime
from urllib.parse import unquote

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm.models import BookingLink, Lead, LeadActivity, MessageTemplate

User = get_user_model()
URL = '/api/django/crm/leads/bulk/'


class BulkWhatsappGardesTests(TestCase):

    def test_le_conseiller_est_rendu_dans_la_file(self):
        """ACVI53 — `{conseiller}` rendu, aucun `{` ne part au client ; un
        placeholder inconnu est refusé à l'enregistrement."""
        from apps.crm.fiche_funnel import _corps_whatsapp_en_masse

        self.user.first_name = 'Sara'
        self.user.save(update_fields=['first_name'])
        tpl = MessageTemplate.objects.create(
            company=self.company, nom='Conseiller', langue='fr',
            corps='Bonjour {prenom}, ici {conseiller}. Dossier {reference}.')
        texte = _corps_whatsapp_en_masse(self.c, tpl)
        self.assertIn('ici Sara', texte)
        self.assertNotIn('{', texte)
        refus = self.api.post('/api/django/crm/message-templates/', {
            'nom': 'Faux', 'langue': 'fr', 'corps': 'Bonjour {inconnu}'},
            format='json')
        self.assertEqual(refus.status_code, 400, refus.data)
        self.assertIn('corps', refus.data)
        self.assertFalse(MessageTemplate.objects.filter(nom='Faux').exists())

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM15 Solaire', slug='acrm15-bulk')
        self.user = User.objects.create_user(
            username='acrm15-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.a = Lead.objects.create(
            company=self.company, nom='Oppose', prenom='A', owner=self.user,
            telephone='+212661151501', ne_plus_contacter=True)
        self.b = Lead.objects.create(
            company=self.company, nom='Perdu', prenom='B', owner=self.user,
            telephone='+212661151502', perdu=True, is_archived=True)
        self.c = Lead.objects.create(
            company=self.company, nom='Normal', prenom='C', owner=self.user,
            telephone='+212661151503')
        self.tpl = MessageTemplate.objects.create(
            company=self.company, nom='RDV', langue='fr',
            corps='Bonjour {prenom}. Réservez votre visite : {lien_rdv}')
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))

    def test_sans_pii_aucun_numero_servi(self):
        # ACVI4 — un rôle sans `client_pii_voir` : ni `phone` ni numéro dans
        # `wa_url`, partout où la liste masque déjà le téléphone.
        from apps.crm.models import Appointment
        from apps.crm.models_cadence import RelanceEtape
        from apps.roles.models import Role

        role = Role.objects.create(
            company=self.company, nom='Sans PII',
            permissions=['crm_voir', 'crm_modifier'])
        sans_pii = User.objects.create_user(
            username='acvi4-sans-pii', password='x', company=self.company,
            role=role)
        Lead.objects.filter(pk=self.c.pk).update(owner=sans_pii)
        touche = RelanceEtape.objects.create(
            company=self.company, lead=self.c, cadence='contact', ordre=1,
            canal=RelanceEtape.Canal.WHATSAPP, template_cle='identite',
            due_date=timezone.localdate(), due_at=timezone.now())
        api = APIClient()
        api.force_authenticate(sans_pii)

        rendu = api.get(f'/api/django/crm/relance-etapes/{touche.pk}/message/')
        self.assertEqual(rendu.status_code, 200, rendu.data)
        self.assertEqual(rendu.data['phone'], '')
        self.assertIsNone(rendu.data['wa_url'])
        self.assertTrue(rendu.data['message'])

        lot = api.post(URL, {
            'action': 'prepare_whatsapp', 'ids': [self.c.pk],
            'body': 'Bonjour.'}, format='json')
        self.assertEqual(lot.status_code, 200, lot.data)
        self.assertEqual(
            [(e['phone'], e['wa_url']) for e in lot.data['queue']], [('', None)])

        rdv = Appointment.objects.create(
            company=self.company, lead=self.c,
            scheduled_at=timezone.now() + datetime.timedelta(days=2))
        refus = api.post(
            f'/api/django/crm/appointments/{rdv.pk}/confirmer-whatsapp/')
        self.assertEqual(refus.status_code, 403, refus.data)
        self.assertEqual(refus.data.get('code'), 'droit_manquant')

    def test_plafond_journalier_et_trace_par_lead(self):
        """CADV10 — 24 traces ce jour : A passe (25e), B et C sortent avec le
        motif ; le lendemain le plafond se libère. Mutant : plafond 1000."""
        trace = 'WhatsApp préparé en lot'
        LeadActivity.objects.bulk_create([
            LeadActivity(company=self.company, lead=self.c, user=self.user,
                         kind=LeadActivity.Kind.NOTE, body=trace)
            for _ in range(24)])
        a, b, c = (
            Lead.objects.create(
                company=self.company, nom=nom, owner=self.user,
                telephone=f'+21266115160{rang}')
            for rang, nom in enumerate(('Eligible A', 'Eligible B', 'Eligible C')))
        ids = [a.pk, b.pk, c.pk]
        corps = {'action': 'prepare_whatsapp', 'ids': ids, 'body': 'Bonjour.'}
        data = self.api.post(URL, corps, format='json').data
        self.assertEqual([q['lead_id'] for q in data['queue']], [a.pk])
        self.assertEqual({s['id'] for s in data['skipped']}, {b.pk, c.pk})
        self.assertEqual({s['reason'] for s in data['skipped']},
                         {'plafond journalier atteint (25)'})
        self.assertEqual(
            LeadActivity.objects.filter(lead=a, body=trace).count(), 1)
        self.assertFalse(
            LeadActivity.objects.filter(lead=b, body=trace).exists())
        self.assertEqual(LeadActivity.objects.filter(
            user=self.user, body=trace).count(), 25)
        # Le lendemain : les 25 traces sont d'hier.
        hier = timezone.now() - datetime.timedelta(days=1, hours=1)
        LeadActivity.objects.filter(body=trace).update(created_at=hier)
        data = self.api.post(URL, corps, format='json').data
        self.assertEqual(len(data['queue']), 3)

    def _preparer(self):
        resp = self.api.post(URL, {
            'action': 'prepare_whatsapp',
            'ids': [self.a.pk, self.b.pk, self.c.pk],
            'template_id': self.tpl.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.data

    def test_oppose_exclu(self):
        data = self._preparer()
        self.assertEqual([q['lead_id'] for q in data['queue']], [self.c.pk])
        motifs = {s['id']: s['reason'] for s in data['skipped']}
        self.assertEqual(motifs.get(self.a.pk), 'ne plus contacter')
        self.assertFalse(BookingLink.objects.filter(lead=self.a).exists())

    def test_perdu_archive_exclu(self):
        data = self._preparer()
        motifs = {s['id']: s['reason'] for s in data['skipped']}
        self.assertEqual(motifs.get(self.b.pk), 'perdu/archivé')
        self.assertFalse(BookingLink.objects.filter(lead=self.b).exists())

    def test_phrase_lien_vide_omise(self):
        data = self._preparer()
        [ligne] = data['queue']
        texte = unquote(ligne['wa_url'].split('text=', 1)[-1])
        self.assertIn('Bonjour C', texte)
        if 'Réservez votre visite' in texte:
            # Le lien existe : il suit la phrase.
            self.assertRegex(texte, r'Réservez votre visite : \S+')
        self.assertFalse(texte.rstrip().endswith(':'))

    def test_blanc_a_completer_refuse_et_nomme(self):
        """CAD69 — même règle que l'aperçu d'une touche : un ``[plateforme]``
        non complété n'est JAMAIS mis en file ; le lead sort avec le blanc
        nommé. Mutant : retirer la garde ⇒ le lien part avec le crochet."""
        resp = self.api.post(URL, {
            'action': 'prepare_whatsapp', 'ids': [self.c.pk],
            'body': 'Bonjour. Retrouvez-nous sur [plateforme] ou [jour].'},
            format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['queue'], [])
        [saute] = resp.data['skipped']
        self.assertEqual(saute['id'], self.c.pk)
        self.assertEqual(saute['reason'], 'à compléter : [plateforme], [jour]')
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.c, body__startswith='WhatsApp préparé en lot').exists())

    def test_jumeau_darija_rendu_pour_lead_darija(self):
        # ACRM70 — « RDV » FR et « RDV » darija coexistent (unicité société +
        # nom + langue) ; le lead darija reçoit le texte darija, le lead FR
        # le texte FR, pour le MÊME ``template_id`` (le FR).
        MessageTemplate.objects.create(
            company=self.company, nom='RDV', langue='darija',
            corps='Salam {prenom}, bghiti nji nchouf s-sath dyalek ?')
        darija = Lead.objects.create(
            company=self.company, nom='Darija', prenom='D', owner=self.user,
            telephone='+212661151504', langue_preferee='darija')
        francais = Lead.objects.create(
            company=self.company, nom='Francais', prenom='F', owner=self.user,
            telephone='+212661151505', langue_preferee='fr')
        resp = self.api.post(URL, {
            'action': 'prepare_whatsapp', 'ids': [darija.pk, francais.pk],
            'template_id': self.tpl.pk}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        textes = {q['lead_id']: unquote(q['wa_url'].split('text=', 1)[-1])
                  for q in resp.data['queue']}
        self.assertIn('Salam D', textes[darija.pk])
        self.assertNotIn('Bonjour', textes[darija.pk])
        self.assertIn('Bonjour F', textes[francais.pk])
        self.assertNotIn('Salam', textes[francais.pk])

    def test_second_modele_meme_nom_meme_langue_refuse(self):
        # ACRM70 — la contrainte reste serrée : un second « RDV » FR de la
        # même société est refusé, seul le jumeau d'une AUTRE langue passe.
        with self.assertRaises(IntegrityError), transaction.atomic():
            MessageTemplate.objects.create(
                company=self.company, nom='RDV', langue='fr', corps='doublon')
        MessageTemplate.objects.create(
            company=self.company, nom='RDV', langue='darija', corps='jumeau')
        self.assertEqual(
            MessageTemplate.objects.filter(
                company=self.company, nom='RDV').count(), 2)
