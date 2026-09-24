"""CAD55 — « Relancer la cadence — Après devis » depuis la fiche porte le devis.

Avant : l'écran n'envoyait que le nom de la cadence et
``initialiser_plan_relance`` partait sans ``devis=`` — toutes les touches
perdaient leur lien (``materialiser_touche_suivante`` recopie le devis de la
touche close), les messages leur phrase de proposition, et la validité du devis
n'était jamais posée.

Done : le devis ENVOYÉ du lead est rattaché (un seul → d'office ; plusieurs →
la question « lequel ? », le plus récent proposé) ; toutes les touches le
portent, la validité est posée ; sans devis → l'avertissement part AVANT le
lancement (409), jamais découvert touche par touche. Contrat partagé :
``contract_samples/lead_relance_initialiser.json``.
"""
import datetime
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import horaires, services
from apps.crm.models import Client, Lead, RelanceEtape
from authentication.models import Company

User = get_user_model()

CONTRATS = Path(__file__).resolve().parent / 'contract_samples'
CONTRAT = json.loads(
    (CONTRATS / 'lead_relance_initialiser.json').read_text(encoding='utf-8'))


def _instant(jour):
    return datetime.datetime(2026, 9, jour, 10, 0, tzinfo=horaires.CASABLANCA)


class DevisRattacheTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='CAD55 Solaire',
                                              slug='cad55')
        self.acteur = User.objects.create_user(
            username='cad55-resp', password='x', role_legacy='responsable',
            company=self.company)
        self.lead = Lead.objects.create(
            company=self.company, nom='Idrissi', prenom='Salma',
            owner=self.acteur, telephone='+212661550055')
        self.client_crm = Client.objects.create(
            company=self.company, nom='Salma Idrissi',
            email='cad55@example.com')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        self.url = (f'/api/django/crm/leads/{self.lead.pk}'
                    '/relance/initialiser/')

    def _devis(self, reference, jour, *, lead=None, statut=None):
        from apps.ventes.models import Devis
        return Devis.objects.create(
            company=self.company, reference=reference,
            client=self.client_crm, lead=lead or self.lead,
            statut=statut or Devis.Statut.ENVOYE,
            taux_tva=Decimal('20.00'), date_envoi=_instant(jour))

    def _touches(self):
        return RelanceEtape.objects.filter(lead=self.lead,
                                           cadence='apres_devis')

    def test_un_seul_devis_rattache_a_toutes_les_touches_validite_posee(self):
        devis = self._devis('DEV-2609-0042', 5)
        reponse = self.api.post(
            self.url, CONTRAT['corps_apres_devis'], format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data)
        self.assertEqual({r['devis'] for r in reponse.data}, {devis.pk})
        self.assertEqual({r['devis_reference'] for r in reponse.data},
                         {'DEV-2609-0042'})
        # La touche SUIVANTE naît de l'issue (cadence réactive) : elle aussi
        # porte le devis — tout le plan, pas seulement la première touche.
        premiere = self._touches().filter(
            statut=RelanceEtape.Statut.A_FAIRE).order_by('ordre').first()
        services.marquer_etape_relance(
            premiere, self.acteur, RelanceEtape.Statut.FAIT,
            outcome='non_joint')
        self.assertGreaterEqual(self._touches().count(), 2)
        self.assertEqual(
            set(self._touches().values_list('devis_id', flat=True)),
            {devis.pk})
        devis.refresh_from_db()
        self.assertIsNotNone(devis.date_validite)

    def test_plusieurs_devis_la_question_affirme_le_contrat(self):
        ancien = self._devis('DEV-2609-0042', 5)
        recent = self._devis('DEV-2609-0057', 12)
        reponse = self.api.post(
            self.url, CONTRAT['corps_apres_devis'], format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        attendu = CONTRAT['exemple_devis_a_choisir']
        self.assertEqual(set(reponse.data), set(attendu))
        self.assertEqual(reponse.data['detail'], attendu['detail'])
        self.assertEqual(reponse.data['erreurs'], attendu['erreurs'])
        # Les identifiants sont ceux de la base ; tout le reste = le contrat.
        ids = {911: recent.pk, 903: ancien.pk}
        exemple = attendu['devis_a_choisir']
        self.assertEqual(
            reponse.data['devis_a_choisir'],
            {'choix': [dict(c, id=ids[c['id']]) for c in exemple['choix']],
             'propose': ids[exemple['propose']]})
        self.assertFalse(self._touches().exists())

        # La réponse revient en `devis` : le plan cite CE devis-là.
        corps = dict(CONTRAT['corps_devis_choisi'], devis=ancien.pk)
        reponse = self.api.post(self.url, corps, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual({r['devis'] for r in reponse.data}, {ancien.pk})

    def test_sans_devis_avertissement_avant_lancement(self):
        reponse = self.api.post(
            self.url, CONTRAT['corps_apres_devis'], format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data, CONTRAT['exemple_sans_devis'])
        self.assertFalse(self._touches().exists())

        reponse = self.api.post(
            self.url, CONTRAT['corps_sans_devis'], format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data)
        self.assertEqual({r['devis'] for r in reponse.data}, {None})

    def test_devis_accepte_ou_brouillon_ne_compte_pas(self):
        from apps.ventes.models import Devis
        self._devis('DEV-2609-0001', 3, statut=Devis.Statut.ACCEPTE)
        self._devis('DEV-2609-0002', 4, statut=Devis.Statut.BROUILLON)
        reponse = self.api.post(
            self.url, CONTRAT['corps_apres_devis'], format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertTrue(reponse.data.get('sans_devis'))

    def test_devis_dun_autre_lead_refuse_en_nommant_le_champ(self):
        self._devis('DEV-2609-0042', 5)
        autre = Lead.objects.create(company=self.company, nom='Autre',
                                    owner=self.acteur)
        etranger = self._devis('DEV-2609-0099', 6, lead=autre)
        corps = dict(CONTRAT['corps_devis_choisi'], devis=etranger.pk)
        reponse = self.api.post(self.url, corps, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(reponse.data, CONTRAT['exemple_erreur_devis'])
        self.assertFalse(self._touches().exists())

    def test_cumul_remplacement_et_sans_devis_dans_un_seul_409(self):
        due = timezone.now() + datetime.timedelta(days=1)
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='contact', ordre=3,
            canal=RelanceEtape.Canal.APPEL, libelle='Appel 2',
            due_at=due, due_date=due.date())
        reponse = self.api.post(
            self.url, CONTRAT['corps_apres_devis'], format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('remplacement', reponse.data)
        self.assertTrue(reponse.data['sans_devis'])
        self.assertEqual(set(reponse.data['erreurs']),
                         {'confirmer_remplacement', 'devis'})
        self.assertIn('« Prise de contact »', reponse.data['detail'])
        self.assertIn(CONTRAT['exemple_sans_devis']['detail'],
                      reponse.data['detail'])

    def test_plan_apres_devis_deja_ouvert_renvoye_sans_question(self):
        devis = self._devis('DEV-2609-0042', 5)
        premier = self.api.post(
            self.url, CONTRAT['corps_apres_devis'], format='json')
        self.assertEqual(premier.status_code, 200, premier.data)
        self._devis('DEV-2609-0057', 12)
        second = self.api.post(
            self.url, CONTRAT['corps_apres_devis'], format='json')
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual([r['id'] for r in second.data],
                         [r['id'] for r in premier.data])
        self.assertEqual({r['devis'] for r in second.data}, {devis.pk})
