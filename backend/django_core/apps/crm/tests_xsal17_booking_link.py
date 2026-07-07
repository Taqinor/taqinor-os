"""XSAL17 — Placeholder {lien_rdv} : lien de réservation de visite tokenisé.

Couvre :
  - ``MessageTemplate.render()`` substitue {lien_rdv} ; un template SANS le
    placeholder reste INCHANGÉ ;
  - ``services.resoudre_lien_rdv`` ne crée un ``BookingLink`` QUE si le
    placeholder est présent (no-op sinon) ;
  - ``services.public_booking_url`` réutilise un lien non expiré/non utilisé
    au lieu d'en créer un nouveau à chaque appel ;
  - le lien de réservation résout vers le BON lead (booking-to-lead) ;
  - un jeton expiré/déjà utilisé/inconnu est rejeté (message honnête) ;
  - la réservation crée un ``Appointment`` rattaché au lead et marque le
    lien comme utilisé (idempotent — pas de second RDV) ;
  - company-scopée (jamais de fuite cross-tenant) ;
  - les endpoints publics répondent correctement (200/201/404/410).
"""
import datetime
import json

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Appointment, BookingLink, Lead, MessageTemplate
from apps.crm.services import (
    BookingLinkUnavailable,
    public_booking_url,
    reserver_creneau_public,
    resoudre_lien_rdv,
    resolve_booking_link,
)


class MessageTemplateRenderLienRdvTests(TestCase):
    def test_template_sans_placeholder_inchange(self):
        tpl = MessageTemplate(corps='Bonjour {prenom}, voici votre devis.')
        rendu = tpl.render(prenom='Amina', lien_rdv='https://x/rdv/abc')
        self.assertEqual(rendu, 'Bonjour Amina, voici votre devis.')

    def test_template_avec_placeholder_substitue(self):
        tpl = MessageTemplate(corps='Réservez votre visite : {lien_rdv}')
        rendu = tpl.render(lien_rdv='https://x/rdv/abc123')
        self.assertEqual(rendu, 'Réservez votre visite : https://x/rdv/abc123')

    def test_placeholder_sans_valeur_devient_vide(self):
        tpl = MessageTemplate(corps='Lien : {lien_rdv}')
        self.assertEqual(tpl.render(), 'Lien : ')


class ResoudreLienRdvTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL17', slug='taqinor-xsal17')
        self.lead = Lead.objects.create(company=self.company, nom='Prospect RDV')

    def test_sans_placeholder_ninvente_aucun_lien_ni_bookinglink(self):
        texte = resoudre_lien_rdv('Bonjour, voici votre devis.', self.lead)
        self.assertEqual(texte, 'Bonjour, voici votre devis.')
        self.assertEqual(BookingLink.objects.count(), 0)

    def test_avec_placeholder_cree_un_lien_fonctionnel(self):
        texte = resoudre_lien_rdv('Réservez ici : {lien_rdv}', self.lead)
        self.assertNotIn('{lien_rdv}', texte)
        self.assertEqual(BookingLink.objects.count(), 1)
        link = BookingLink.objects.get()
        self.assertIn(link.token, texte)
        self.assertEqual(link.lead, self.lead)
        self.assertEqual(link.company, self.company)


class PublicBookingUrlReuseTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL17 Reuse', slug='taqinor-xsal17-reuse')
        self.lead = Lead.objects.create(company=self.company, nom='Prospect Reuse')

    def test_reutilise_un_lien_valide_non_utilise(self):
        url1 = public_booking_url(self.lead)
        url2 = public_booking_url(self.lead)
        self.assertEqual(url1, url2)
        self.assertEqual(BookingLink.objects.count(), 1)

    def test_cree_un_nouveau_lien_si_le_precedent_est_expire(self):
        first = BookingLink.objects.create(company=self.company, lead=self.lead)
        BookingLink.objects.filter(pk=first.pk).update(
            expires_at=timezone.now() - datetime.timedelta(days=1))
        public_booking_url(self.lead)
        self.assertEqual(BookingLink.objects.count(), 2)

    def test_cree_un_nouveau_lien_si_le_precedent_est_deja_utilise(self):
        first = BookingLink.objects.create(company=self.company, lead=self.lead)
        BookingLink.objects.filter(pk=first.pk).update(used_at=timezone.now())
        public_booking_url(self.lead)
        self.assertEqual(BookingLink.objects.count(), 2)


class ResolveBookingLinkTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL17 Resolve', slug='taqinor-xsal17-resolve')
        self.lead = Lead.objects.create(company=self.company, nom='Prospect Resolve')

    def test_jeton_inconnu_leve(self):
        with self.assertRaises(BookingLinkUnavailable):
            resolve_booking_link('jeton-inexistant')

    def test_jeton_expire_leve(self):
        link = BookingLink.objects.create(company=self.company, lead=self.lead)
        BookingLink.objects.filter(pk=link.pk).update(
            expires_at=timezone.now() - datetime.timedelta(minutes=1))
        with self.assertRaises(BookingLinkUnavailable):
            resolve_booking_link(link.token)

    def test_jeton_deja_utilise_leve(self):
        link = BookingLink.objects.create(company=self.company, lead=self.lead)
        BookingLink.objects.filter(pk=link.pk).update(used_at=timezone.now())
        with self.assertRaises(BookingLinkUnavailable):
            resolve_booking_link(link.token)

    def test_jeton_valide_resout_le_bon_lead(self):
        link = BookingLink.objects.create(company=self.company, lead=self.lead)
        resolved = resolve_booking_link(link.token)
        self.assertEqual(resolved.lead_id, self.lead.pk)


class ReserverCreneauPublicTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL17 Reserve', slug='taqinor-xsal17-reserve')
        self.lead = Lead.objects.create(company=self.company, nom='Prospect Reserve')
        self.link = BookingLink.objects.create(
            company=self.company, lead=self.lead)

    def test_reserve_cree_un_appointment_sur_le_bon_lead(self):
        creneau = timezone.now() + datetime.timedelta(days=3)
        appt = reserver_creneau_public(self.link.token, scheduled_at=creneau)
        self.assertEqual(appt.lead_id, self.lead.pk)
        self.assertEqual(Appointment.objects.count(), 1)

    def test_marque_le_lien_utilise_idempotent(self):
        creneau = timezone.now() + datetime.timedelta(days=3)
        reserver_creneau_public(self.link.token, scheduled_at=creneau)
        self.link.refresh_from_db()
        self.assertTrue(self.link.is_used)
        with self.assertRaises(BookingLinkUnavailable):
            reserver_creneau_public(self.link.token, scheduled_at=creneau)
        # Un seul RDV créé, jamais un second.
        self.assertEqual(Appointment.objects.count(), 1)

    def test_jeton_inconnu_leve_sans_creer_de_rdv(self):
        with self.assertRaises(BookingLinkUnavailable):
            reserver_creneau_public(
                'jeton-inconnu', scheduled_at=timezone.now())
        self.assertEqual(Appointment.objects.count(), 0)


class PublicBookingEndpointTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor XSAL17 Endpoint', slug='taqinor-xsal17-endpoint')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect', prenom='Amina')
        self.link = BookingLink.objects.create(
            company=self.company, lead=self.lead)

    def test_status_valide_200(self):
        res = self.client.get(f'/api/django/crm/public/booking/{self.link.token}/')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['prenom'], 'Amina')

    def test_status_jeton_inconnu_404(self):
        res = self.client.get('/api/django/crm/public/booking/inconnu/')
        self.assertEqual(res.status_code, 404)

    def test_status_jeton_expire_404(self):
        BookingLink.objects.filter(pk=self.link.pk).update(
            expires_at=timezone.now() - datetime.timedelta(minutes=1))
        res = self.client.get(f'/api/django/crm/public/booking/{self.link.token}/')
        self.assertEqual(res.status_code, 404)

    def test_reserve_201_et_lead_correct(self):
        creneau = (timezone.now() + datetime.timedelta(days=2)).isoformat()
        res = self.client.post(
            f'/api/django/crm/public/booking/{self.link.token}/reserve/',
            data=json.dumps({'scheduled_at': creneau}),
            content_type='application/json')
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()['lead_id'], self.lead.pk)

    def test_reserve_deux_fois_le_meme_jeton_410(self):
        creneau = (timezone.now() + datetime.timedelta(days=2)).isoformat()
        first = self.client.post(
            f'/api/django/crm/public/booking/{self.link.token}/reserve/',
            data=json.dumps({'scheduled_at': creneau}),
            content_type='application/json')
        self.assertEqual(first.status_code, 201)
        second = self.client.post(
            f'/api/django/crm/public/booking/{self.link.token}/reserve/',
            data=json.dumps({'scheduled_at': creneau}),
            content_type='application/json')
        self.assertEqual(second.status_code, 410)

    def test_reserve_sans_date_400(self):
        res = self.client.post(
            f'/api/django/crm/public/booking/{self.link.token}/reserve/',
            data=json.dumps({}), content_type='application/json')
        self.assertEqual(res.status_code, 400)

    def test_company_scope_ne_fuit_pas(self):
        other = Company.objects.create(nom='Autre XSAL17', slug='xsal17-autre')
        other_lead = Lead.objects.create(company=other, nom='Autre prospect')
        other_link = BookingLink.objects.create(company=other, lead=other_lead)
        res = self.client.get(
            f'/api/django/crm/public/booking/{other_link.token}/')
        self.assertEqual(res.status_code, 200)
        # Le lien de l'AUTRE société résout bien SON propre lead, jamais celui
        # de self.company (scoping correct — pas de mélange).
        creneau = (timezone.now() + datetime.timedelta(days=1)).isoformat()
        reserve = self.client.post(
            f'/api/django/crm/public/booking/{other_link.token}/reserve/',
            data=json.dumps({'scheduled_at': creneau}),
            content_type='application/json')
        self.assertEqual(reserve.json()['lead_id'], other_lead.pk)
