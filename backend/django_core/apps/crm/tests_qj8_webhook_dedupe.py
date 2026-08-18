"""Webhook du site web — RÈGLE FONDATEUR du 18/08/2026 : chaque soumission
crée un NOUVEAU lead, toujours.

Ce fichier portait auparavant la « couche 2 » QJ8 (dédup visiteur revenant :
un re-POST au même e-mail/téléphone METTAIT À JOUR le lead existant, sans
limite de temps). Cette fusion silencieuse a été SUPPRIMÉE — c'est elle qui a
fait disparaître un lead de test dans une ancienne fiche au même e-mail, que
son auteur n'a jamais pu retrouver. Le fichier garde désormais le contrat
INVERSE :

  - une soumission dont le téléphone/e-mail est déjà connu CRÉE un lead ;
  - le lead existant ressort INTACT (son nom n'est plus jamais écrasé — mort
    du QW7 sur ce chemin) ;
  - le rapprochement est posé EN VISIBILITÉ : note chatter « Doublon
    possible » sur le NOUVEAU lead, et le rail identité s'allume seul ;
  - « identité forte » (même e-mail ET même téléphone) est signalée
    explicitement — « très probablement le même client » ;
  - le SEUL chemin qui touche encore un lead existant est la garde technique
    anti-rejeu < 60 s (double-clic / relance réseau).

N.B. : `dedupe_event` (YDATA12) court-circuite deux POSTs au payload
STRICTEMENT identique — chaque envoi de ces tests porte donc son propre
`idempotencyKey`, comme le fait le site (un jeton par session de saisie).
"""
import json

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity

SECRET = 'test-secret-qj8'


def payload_site(**extra):
    """Charge utile minimale valide pour le webhook."""
    base = {
        'fullName': 'Karim Alaoui',
        'phoneE164': '+212661000001',
        'whatsappOptIn': False,
        'city': 'Rabat',
        'roofType': 'villa',
        'billRange': '1500-3000',
        'qualified': True,
        'band': {'kwcLabel': '5 à 9 kWc', 'paybackLabel': '4 à 6 ans'},
        'utm': {
            'utm_source': 'facebook',
            'utm_medium': 'cpc',
            'utm_campaign': 'promo_ete',
        },
        'fbclid': 'fb.1.ABC.XYZ',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class TestSoumissionCreeToujoursUnNouveauLead(TestCase):
    """Le contrat central : plus aucune fusion automatique."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QJ8', slug='taqinor-qj8')
        self.url = reverse('website-lead-webhook')
        self._idem = 0

    def post(self, data, secret=SECRET):
        self._idem += 1
        data = dict(data)
        data.setdefault('idempotencyKey', f'idem-{self._idem}')
        headers = {'HTTP_X_WEBHOOK_SECRET': secret} if secret else {}
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json', **headers)

    def _make_existing_lead(self, telephone='+212661000001', email=None,
                            nom='Karim Alaoui', utm_source='facebook',
                            fbclid='fb.1.ABC.XYZ', ville='Fès'):
        """Lead déjà en base, HORS de la fenêtre anti-rejeu de 60 s."""
        lead = Lead.objects.create(
            company=self.company,
            nom=nom,
            telephone=telephone,
            email=email,
            ville=ville,
            source=Lead.Source.SITE_WEB,
            canal=Lead.Canal.SITE_WEB,
            utm_source=utm_source,
            utm_medium='cpc',
            utm_campaign='promo_ete',
            fbclid=fbclid,
        )
        # `date_creation` est auto_now_add → on la force en arrière pour sortir
        # de la garde < 60 s (seul chemin qui touche encore un lead existant).
        Lead.objects.filter(pk=lead.pk).update(
            date_creation=timezone.now() - timezone.timedelta(days=2))
        lead.refresh_from_db()
        return lead

    def _notes(self, lead):
        return list(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE))

    # ── Le nouveau lead est CRÉÉ, l'ancien reste INTACT ─────────────────

    def test_meme_telephone_cree_un_nouveau_lead(self):
        existing = self._make_existing_lead()
        res = self.post(payload_site(city='Casablanca'))

        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Lead.objects.count(), 2)
        nouveau = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertNotEqual(nouveau.pk, existing.pk)
        self.assertEqual(nouveau.ville, 'Casablanca')

    def test_le_lead_existant_ressort_intact(self):
        """QW7 — le nom (et le reste) d'une fiche existante n'est plus JAMAIS
        écrasé par une soumission du site."""
        existing = self._make_existing_lead(
            nom='Karim Alaoui', ville='Fès', fbclid='fb.1.ABC.ORIGINAL')
        avant = timezone.now()

        res = self.post(payload_site(
            fullName='test1',
            city='Casablanca',
            fbclid='fb.2.NEW.FBCLID',
            utm={'utm_source': 'instagram', 'utm_medium': 'organic',
                 'utm_campaign': 'nouvelle_campagne'},
        ))
        self.assertEqual(res.status_code, 201, res.content)

        existing.refresh_from_db()
        self.assertEqual(existing.nom, 'Karim Alaoui')
        self.assertEqual(existing.ville, 'Fès')
        self.assertEqual(existing.fbclid, 'fb.1.ABC.ORIGINAL')
        self.assertEqual(existing.utm_source, 'facebook')
        self.assertEqual(existing.utm_campaign, 'promo_ete')
        # Aucune activité n'est écrite sur la fiche existante.
        self.assertFalse(
            LeadActivity.objects.filter(
                lead=existing, created_at__gte=avant).exists())
        # …et le lead de test est bien retrouvable, sous SON nom.
        nouveau = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(nouveau.nom, 'test1')

    def test_lead_sans_telephone_cree_aussi_un_nouveau_lead(self):
        """Le rapprochement par e-mail seul ne fusionne pas davantage."""
        existing = Lead.objects.create(
            company=self.company, nom='Sara Bennis', telephone=None,
            email='sara@example.ma', ville='Rabat',
            source=Lead.Source.SITE_WEB, canal=Lead.Canal.SITE_WEB)
        res = self.post(payload_site(
            fullName='Sara Bennis', phoneE164='', phone='',
            email='sara@example.ma', city='Marrakech'))

        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Lead.objects.count(), 2)
        existing.refresh_from_db()
        self.assertEqual(existing.ville, 'Rabat')

    def test_lead_sous_le_seuil_cree_aussi_un_nouveau_lead(self):
        """Un lead `qualified:false` (< 1 000 MAD) est accepté, étiqueté, et
        suit exactement la même règle — jamais rejeté, jamais fusionné."""
        self._make_existing_lead()
        res = self.post(payload_site(
            billRange='800-1000', qualified=False, city='Salé'))

        self.assertEqual(res.status_code, 201, res.content)
        nouveau = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(nouveau.tags, 'Sous le seuil 1 000 MAD')
        self.assertEqual(Lead.objects.count(), 2)

    # ── Détection posée EN VISIBILITÉ (note chatter + réponse HTTP) ──────────

    def test_note_doublon_possible_sur_le_nouveau_lead(self):
        existing = self._make_existing_lead()
        res = self.post(payload_site(city='Casablanca'))
        nouveau = Lead.objects.get(pk=res.json()['lead_id'])

        bodies = [n.body for n in self._notes(nouveau)]
        doublon = [b for b in bodies if b.startswith('Doublon possible')]
        self.assertEqual(len(doublon), 1, bodies)
        self.assertIn(f'#{existing.pk}', doublon[0])
        self.assertIn('Karim Alaoui', doublon[0])
        self.assertIn('à examiner', doublon[0])
        # La réponse HTTP porte le même signal, exploitable par l'émetteur.
        self.assertEqual(res.json()['doublons'], [existing.pk])
        self.assertFalse(res.json()['match_fort'])

    def test_identite_forte_meme_email_ET_meme_telephone(self):
        existing = self._make_existing_lead(email='karim@example.ma')
        res = self.post(payload_site(email='Karim@Example.MA'))
        nouveau = Lead.objects.get(pk=res.json()['lead_id'])

        note = [n.body for n in self._notes(nouveau)
                if n.body.startswith('Doublon possible')][0]
        self.assertIn('très probablement le même client', note)
        self.assertIn(f'#{existing.pk}', note)
        self.assertTrue(res.json()['match_fort'])
        self.assertIn('très probablement le même client',
                      res.json()['detail'])

    def test_email_seul_nest_pas_une_identite_forte(self):
        self._make_existing_lead(
            telephone='+212699999999', email='karim@example.ma')
        res = self.post(payload_site(
            phoneE164='+212661000001', email='karim@example.ma'))
        nouveau = Lead.objects.get(pk=res.json()['lead_id'])

        note = [n.body for n in self._notes(nouveau)
                if n.body.startswith('Doublon possible')][0]
        self.assertNotIn('très probablement le même client', note)
        self.assertFalse(res.json()['match_fort'])

    def test_telephone_seul_nest_pas_une_identite_forte(self):
        """Le lead existant n'a pas d'e-mail : rapprochement possible, jamais
        « le même client »."""
        self._make_existing_lead(email=None)
        res = self.post(payload_site(email='karim@example.ma'))

        self.assertFalse(res.json()['match_fort'])

    def test_aucun_doublon_aucune_note(self):
        res = self.post(payload_site())
        nouveau = Lead.objects.get(pk=res.json()['lead_id'])

        self.assertEqual(res.json()['detail'], 'Lead créé.')
        self.assertEqual(res.json()['doublons'], [])
        self.assertFalse(any(b.body.startswith('Doublon possible')
                             for b in self._notes(nouveau)))

    # ── Bornes : personnes distinctes, sociétés distinctes ──────────────────

    def test_personnes_differentes_aucun_rapprochement(self):
        self._make_existing_lead(telephone='+212661000001')
        res = self.post(payload_site(
            fullName='Autre Personne', phoneE164='+212661000099'))

        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(Lead.objects.count(), 2)
        self.assertEqual(res.json()['doublons'], [])

    def test_isolation_cross_company(self):
        """Même e-mail/téléphone dans deux sociétés : ni fusion, ni
        rapprochement — la détection reste bornée à `company`."""
        company_b = Company.objects.create(
            nom='Autre Société QJ8', slug='autre-qj8')
        Lead.objects.create(
            company=company_b, nom='Ali Benali',
            telephone='+212661000001', email='ali@example.ma',
            source=Lead.Source.SITE_WEB)

        res = self.post(payload_site(
            fullName='Ali Benali', email='ali@example.ma'))

        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()['doublons'], [])
        self.assertEqual(Lead.objects.filter(company=company_b).count(), 1)
        self.assertEqual(Lead.objects.filter(company=self.company).count(), 1)

    # ── La garde < 60 s reste le SEUL chemin de mise à jour ──────────────────

    def test_garde_60s_est_le_seul_chemin_de_mise_a_jour(self):
        first = self.post(payload_site())
        self.assertEqual(first.status_code, 201, first.content)

        # Renvoi immédiat (double-clic) : complète la fiche en cours.
        retry = self.post(payload_site(city='Rabat'))
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(retry.json()['lead_id'], first.json()['lead_id'])

        # Hors fenêtre : la soumission suivante est un lead à part entière.
        Lead.objects.filter(pk=first.json()['lead_id']).update(
            date_creation=timezone.now() - timezone.timedelta(minutes=5))
        plus_tard = self.post(payload_site(city='Agadir'))
        self.assertEqual(plus_tard.status_code, 201, plus_tard.content)
        self.assertEqual(Lead.objects.count(), 2)
