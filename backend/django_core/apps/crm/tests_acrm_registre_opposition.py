"""ACRM59 (C-ACRM-044) — le registre d'opposition est cohérent.

Sonde V_VB LSVC5-2 : après une opposition, (b) la ligne ``whatsapp
granted=True`` de l'intake restait la dernière (« accordé »), (c) rien
n'était écrit sous le TÉLÉPHONE d'un lead qui a un e-mail, (d) décocher la
case ne laissait aucune trace. Désormais : une ligne refusée par finalité de
contact et sous chaque identifiant ; la décoche écrit une ligne accordée qui
nomme l'utilisateur.

Gestes réels (PATCH de la fiche) ; aucun mock.
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ConsentRecord

from apps.crm.models import Lead
from apps.crm.leads_consentement import FINALITES_CONTACT, enregistrer_consentement_lead

User = get_user_model()
EMAIL = 'personne-acrm59@example.com'
TELEPHONE = '+212661595959'


class RegistreOppositionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM59 Solaire', slug='acrm59-registre')
        self.user = User.objects.create_user(
            username='acrm59-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.lead = Lead.objects.create(
            company=self.company, nom='Opposant', owner=self.user,
            email=EMAIL, telephone=TELEPHONE)
        # La ligne « WhatsApp accordé » posée à l'intake (CRX39).
        enregistrer_consentement_lead(
            self.lead, purpose='whatsapp', granted=True,
            source='formulaire site web',
            occurred_at=datetime.datetime(
                2026, 1, 1, tzinfo=datetime.timezone.utc))
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION=(
            f'Bearer {AccessToken.for_user(self.user)}'))
        self.url = f'/api/django/crm/leads/{self.lead.pk}/'

    def _patch(self, valeur):
        resp = self.api.patch(self.url, {'ne_plus_contacter': valeur},
                              format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def _derniere(self, identifiant, finalite):
        return (ConsentRecord.objects
                .filter(company=self.company, subject_identifier=identifiant,
                        purpose=finalite)
                .order_by('-occurred_at', '-pk').first())

    def test_whatsapp_refuse_apres_opposition(self):
        self._patch(True)
        for finalite in FINALITES_CONTACT:
            derniere = self._derniere(EMAIL, finalite)
            self.assertIsNotNone(derniere, finalite)
            self.assertFalse(derniere.granted, finalite)

    def test_ligne_sous_telephone(self):
        self._patch(True)
        for finalite in FINALITES_CONTACT:
            derniere = self._derniere(TELEPHONE, finalite)
            self.assertIsNotNone(derniere, finalite)
            self.assertFalse(derniere.granted, finalite)

    def test_decoche_tracee(self):
        self._patch(True)
        self._patch(False)
        for identifiant in (EMAIL, TELEPHONE):
            for finalite in FINALITES_CONTACT:
                derniere = self._derniere(identifiant, finalite)
                self.assertTrue(derniere.granted, (identifiant, finalite))
                self.assertIn('opposition levée par acrm59-resp',
                              derniere.source)

    # ── APUB39 (D-APUB-1 = confirmer_par_commercial ; remplace ACRM63) ────

    def test_rappel_par_lien_ne_leve_pas_opposition(self):
        """Le rappel demandé par le lien du devis ne lève pas l'opposition :
        lead opposé, empreinte et registre intacts ; note « opposition
        active » et touche « rappel demandé » posées."""
        from apps.crm.cadence_reperes import RAPPEL_DEMANDE_LIBELLE
        from apps.crm.cadence_signaux import notify_client_contact_request
        from apps.crm.leads_doublons import poser_empreintes_opposition
        from apps.crm.models import EmpreinteOpposition, LeadActivity, RelanceEtape

        self._patch(True)
        self.lead.refresh_from_db()
        poser_empreintes_opposition(self.company, self.lead)
        empreintes = EmpreinteOpposition.objects.filter(
            company=self.company, nature='telephone').count()
        self.assertEqual(empreintes, 1)

        notify_client_contact_request(
            'DEV-APUB39', self.lead, canal='rappel', message='')

        self.lead.refresh_from_db()
        self.assertTrue(self.lead.ne_plus_contacter)
        self.assertEqual(EmpreinteOpposition.objects.filter(
            company=self.company, nature='telephone').count(), empreintes)
        for identifiant in (EMAIL, TELEPHONE):
            for finalite in FINALITES_CONTACT:
                self.assertFalse(self._derniere(identifiant, finalite).granted,
                                 (identifiant, finalite))
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body__startswith='Rappel demandé — opposition loi 09-08 active').exists())
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead,
            body__contains='opposition levée à la demande du client').exists())
        self.assertTrue(RelanceEtape.objects.filter(
            lead=self.lead, libelle=RAPPEL_DEMANDE_LIBELLE,
            statut=RelanceEtape.Statut.A_FAIRE).exists())

    def test_rappel_client_lead_non_oppose_sans_note(self):
        from apps.crm.models import LeadActivity
        from apps.crm.cadence_signaux import notify_client_contact_request

        notify_client_contact_request(
            'DEV-ACRM63', self.lead, canal='rappel', message='')

        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead,
            body__contains='opposition levée à la demande du client').exists())

    def test_autre_canal_ne_leve_pas_opposition(self):
        from apps.crm.cadence_signaux import notify_client_contact_request

        self._patch(True)
        self.lead.refresh_from_db()
        notify_client_contact_request(
            'DEV-ACRM63', self.lead, canal='revision', message='')
        self.lead.refresh_from_db()
        self.assertTrue(self.lead.ne_plus_contacter)

    # ── AMSG3 (D-AMSG-2 = toutes_les_fiches) ───────────────────────────────

    def test_stop_coche_les_fiches_existantes_aux_memes_contacts(self):
        """STOP sur A : les fiches EXISTANTES de la société aux mêmes contacts
        (B même numéro écrit autrement, D archivée au même e-mail) sont
        cochées avec la ligne ancien → nouveau ; C d'une autre société ne
        bouge pas ; un numéro opposé collé sur E la rend opposée ; une case
        décochée n'est pas recochée par l'enregistrement suivant."""
        from apps.crm.cadence_reponses import (
            CONSENT_SOURCE_OPPOSITION_TOUCHE, tracer_opposition_registre)
        from apps.crm.models import LeadActivity
        from apps.crm.selectors import peut_contacter

        b = Lead.objects.create(company=self.company, nom='B',
                                telephone='06 61 59 59 59')
        d = Lead.objects.create(company=self.company, nom='D',
                                email=EMAIL.upper(), is_archived=True)
        autre = Company.objects.create(nom='AMSG3 Autre', slug='amsg3-autre')
        c = Lead.objects.create(company=autre, nom='C', telephone=TELEPHONE)
        e = Lead.objects.create(company=self.company, nom='E',
                                telephone='+212600000303')
        Lead.objects.filter(pk=self.lead.pk).update(ne_plus_contacter=True)
        self.lead.refresh_from_db()
        tracer_opposition_registre(
            self.lead, source=CONSENT_SOURCE_OPPOSITION_TOUCHE)

        for fiche in (b, d):
            fiche.refresh_from_db()
            self.assertTrue(fiche.ne_plus_contacter, fiche.nom)
            self.assertTrue(LeadActivity.objects.filter(
                lead=fiche, kind=LeadActivity.Kind.MODIFICATION,
                field='ne_plus_contacter').exists(), fiche.nom)
        self.assertFalse(peut_contacter(b))
        c.refresh_from_db()
        self.assertFalse(c.ne_plus_contacter)
        e.refresh_from_db()
        self.assertFalse(e.ne_plus_contacter)

        e.telephone = TELEPHONE
        e.save()
        e.refresh_from_db()
        self.assertTrue(e.ne_plus_contacter)

        b.ne_plus_contacter = False
        b.save()
        b.ville = 'Rabat'
        b.save()
        b.refresh_from_db()
        self.assertFalse(b.ne_plus_contacter)
