"""XSAL17 — Placeholder {lien_rdv} dans l'email de proposition (QJ14).

Couvre :
  - le gabarit ``envoi_devis`` par défaut (sans {lien_rdv}) : comportement
    inchangé, aucun ``crm.BookingLink`` créé ;
  - un gabarit ``envoi_devis`` personnalisé AVEC {lien_rdv} : le corps de
    l'email envoyé contient un lien de réservation fonctionnel, rattaché au
    lead source du devis.
"""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from authentication.models import Company

from apps.crm import stages
from apps.crm.models import BookingLink, Client, Lead
from apps.parametres.models_email import EmailTemplate
from apps.ventes.models import Devis

User = get_user_model()


def make_company(slug):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': slug})[0]


def make_user(company, username):
    return User.objects.create_user(
        username=username, password='x', role_legacy='responsable',
        company=company)


def url(devis_id):
    return f'/api/django/ventes/devis/{devis_id}/envoyer-email/'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class LienRdvEmailTests(TestCase):
    def setUp(self):
        self.company = make_company('xsal17-email-co')
        self.user = make_user(self.company, 'xsal17_email_user')
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Tahiri', email='yasmine@test.ma')
        self.lead = Lead.objects.create(
            company=self.company, nom='Tahiri', stage=stages.NEW)

    def _devis(self):
        return Devis.objects.create(
            company=self.company, reference='DEV-XSAL17-EMAIL',
            client=self.client_obj, lead=self.lead,
            statut=Devis.Statut.BROUILLON, created_by=self.user)

    def test_gabarit_par_defaut_sans_placeholder_ne_cree_aucun_bookinglink(self):
        devis = self._devis()
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(BookingLink.objects.count(), 0)

    def test_gabarit_personnalise_avec_placeholder_insere_un_lien(self):
        EmailTemplate.objects.create(
            company=self.company, cle='envoi_devis',
            sujet='Votre devis {reference}',
            corps=('{nom}\n\nVoici votre devis {reference} : {lien}\n'
                   'Réservez une visite : {lien_rdv}'),
        )
        devis = self._devis()
        resp = self.api.post(url(devis.id), {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(BookingLink.objects.count(), 1)
        link = BookingLink.objects.get()
        self.assertEqual(link.lead_id, self.lead.pk)
        self.assertTrue(len(mail.outbox) >= 1)
        self.assertIn(link.token, mail.outbox[-1].body)
