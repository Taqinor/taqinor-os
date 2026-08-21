"""WREF2-L3 — tests du endpoint public de relève de la référence serveur
(``apps/crm/public_lead_ref_views.py``). Réutilise le helper ``payload_site``
et le secret de ``tests_webhook.py`` — même charge utile que le site réel."""
import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .models import Lead, WebsiteLeadPayload
from .tests_webhook import SECRET, payload_site


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class LeadRefLookupTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='L3 Co', slug='l3-co')
        self.webhook_url = reverse('website-lead-webhook')

    def post_webhook(self, data, secret=SECRET):
        headers = {'HTTP_X_WEBHOOK_SECRET': secret} if secret is not None else {}
        return self.client.post(
            self.webhook_url, data=json.dumps(data),
            content_type='application/json', **headers)

    def lookup(self, key):
        return self.client.get(reverse('public-lead-ref-lookup', args=[key]))

    def test_lookup_heureux_renvoie_la_reference_serveur(self):
        idem = 'idem-l3-happy-01'
        res = self.post_webhook(payload_site(
            fullName='Youssef El Amrani', idempotencyKey=idem))
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()['client_ref'], 'AMRANI-1')

        lookup_res = self.lookup(idem)
        self.assertEqual(lookup_res.status_code, 200)
        self.assertEqual(lookup_res.json(), {'client_ref': 'AMRANI-1'})

    def test_lead_sans_reference_encore_attribuee_404_opaque(self):
        # Simule un lead créé sans que `assign_client_ref` ait réussi (best-
        # effort) : la ligne raw existe, le lead est rattaché, mais sans
        # `client_ref` — la relève ne peut rien renvoyer de plus qu'un 404.
        idem = 'idem-l3-no-ref-02'
        raw = WebsiteLeadPayload.objects.create(
            company=self.company, payload={'idempotencyKey': idem})
        lead = Lead.objects.create(company=self.company, nom='Sans Ref')
        raw.lead = lead
        raw.processed = True
        raw.save(update_fields=['lead', 'processed'])

        res = self.lookup(idem)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {'detail': 'Introuvable.'})

    def test_cle_inconnue_404_opaque(self):
        res = self.lookup('idem-jamais-vue-abcdefgh')
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {'detail': 'Introuvable.'})

    def test_cle_mal_formee_404_opaque_sans_toucher_la_base(self):
        # Trop courte (< 8 caractères, même discipline que lib/lead.ts côté
        # site) : rejetée avant toute requête DB.
        res = self.lookup('abc')
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {'detail': 'Introuvable.'})

    def test_corps_opaque_identique_dans_tous_les_cas_d_echec(self):
        idem = 'idem-l3-no-ref-corps-03'
        raw = WebsiteLeadPayload.objects.create(
            company=self.company, payload={'idempotencyKey': idem})
        lead = Lead.objects.create(company=self.company, nom='Sans Ref')
        raw.lead = lead
        raw.processed = True
        raw.save(update_fields=['lead', 'processed'])

        bodies = {
            self.lookup('abc').json()['detail'],                    # mal formée
            self.lookup('idem-jamais-vue-xyz9').json()['detail'],    # inconnue
            self.lookup(idem).json()['detail'],                     # sans ref
        }
        self.assertEqual(bodies, {'Introuvable.'})

    def test_scoping_par_societe_jamais_de_fuite_entre_locataires(self):
        idem = 'idem-l3-scoping-04'
        res = self.post_webhook(payload_site(
            fullName='Salma Amrani', idempotencyKey=idem))
        self.assertEqual(res.status_code, 201, res.content)

        # Sous la société d'origine (résolution serveur par défaut, 1 seule
        # Company à ce stade) : la référence est bien retrouvable.
        res_ok = self.lookup(idem)
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.json(), {'client_ref': 'AMRANI-1'})

        # Bascule la résolution serveur sur un AUTRE tenant : la ligne existe
        # bien en base, mais sous un `company` différent — la relève ne doit
        # RIEN retrouver (même discipline company-scoped que le webhook).
        autre = Company.objects.create(nom='L3 Autre', slug='l3-autre')
        with override_settings(WEBSITE_LEADS_COMPANY_ID=autre.pk):
            res_leak = self.lookup(idem)
        self.assertEqual(res_leak.status_code, 404)
        self.assertEqual(res_leak.json(), {'detail': 'Introuvable.'})

    def test_idempotency_key_snake_case_en_repli(self):
        # Repli tolérant : une ligne dont le payload brut ne porte QUE la
        # variante snake_case (anciens formats) reste retrouvable — même
        # tolérance que `webhooks._map_and_link_lead`.
        idem = 'idem-l3-snake-05'
        raw = WebsiteLeadPayload.objects.create(
            company=self.company, payload={'idempotency_key': idem})
        lead = Lead.objects.create(
            company=self.company, nom='Snake Case', client_ref='SNAKECASE-1')
        raw.lead = lead
        raw.processed = True
        raw.save(update_fields=['lead', 'processed'])

        res = self.lookup(idem)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'client_ref': 'SNAKECASE-1'})
