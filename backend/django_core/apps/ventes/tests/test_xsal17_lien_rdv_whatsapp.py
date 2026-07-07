"""XSAL17 — Placeholder {lien_rdv} dans le message WhatsApp devis.

Couvre :
  - un gabarit ``devis_unique`` SANS {lien_rdv} : comportement inchangé,
    AUCUN ``crm.BookingLink`` créé (pas de coût inutile) ;
  - un gabarit avec {lien_rdv} : le message contient un lien de réservation
    fonctionnel, rattaché au lead source du devis.
"""
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import BookingLink, Client, Lead
from apps.parametres.models import MessageTemplate
from apps.ventes.models import Devis
from apps.ventes.utils.whatsapp import build_devis_whatsapp

User = get_user_model()


class LienRdvWhatsappTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL17 WA', slug='taqinor-xsal17-wa')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Idrissi', telephone='0612345678')
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Karim',
            stage=stages.NEW)
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-XSAL17-1',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.BROUILLON)
        self.rf = RequestFactory()

    def _request(self):
        return self.rf.get('/')

    def test_gabarit_sans_placeholder_ne_cree_aucun_bookinglink(self):
        # Gabarit par défaut (aucun {lien_rdv}) — comportement inchangé.
        message, _links = build_devis_whatsapp(
            self._request(), self.lead, [self.devis], langue='fr')
        self.assertNotIn('{lien_rdv}', message)
        self.assertEqual(BookingLink.objects.count(), 0)

    def test_gabarit_avec_placeholder_insere_un_lien_fonctionnel(self):
        MessageTemplate.objects.create(
            company=self.company, cle='devis_unique',
            corps_fr=('Bonjour {nom}, voici votre devis {reference} : '
                      '{lien}\nRéservez une visite : {lien_rdv}'))
        message, _links = build_devis_whatsapp(
            self._request(), self.lead, [self.devis], langue='fr')
        self.assertNotIn('{lien_rdv}', message)
        self.assertEqual(BookingLink.objects.count(), 1)
        link = BookingLink.objects.get()
        self.assertEqual(link.lead_id, self.lead.pk)
        self.assertIn(link.token, message)
