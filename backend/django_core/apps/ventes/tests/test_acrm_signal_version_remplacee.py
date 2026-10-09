"""ACRM11 (C-ACRM-006, volet signaux) — les signaux de lecture d'une version
REMPLACÉE n'animent plus la cadence.

Sondes V_VC LSVC3-6 : un devis ENVOYÉ révisé en V2 ; l'ancien lien V1,
jamais ouvert depuis 3 jours, déclenchait « non ouverte depuis 24 h », et
trois ouvertures espacées posaient la touche « Proposition rouverte —
appeler ». Désormais : rien sur V1 de la part du moteur ; à l'ouverture du
lien V1, UNE note « ancienne version … (remplacée par …) » et rien d'autre
(ni touche, ni report de la prochaine touche) ; V2 inchangée.

Révision RÉELLE (``reviser_devis``), vues de lecture réelles ; aucun mock.
Le statut des devis n'est jamais écrit par le code testé (règle #4).
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from testkit.time import frozen

from apps.crm.models import Client, Lead, LeadActivity, RelanceEtape
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public.lecture_views import _notify_open, _stamp_view
from apps.ventes.scheduled import engagement_followup_engine
from apps.ventes.selectors import dates_declencheurs

User = get_user_model()
TOUCHE_ROUVERTE = 'Proposition rouverte — appeler'


class SignalVersionRemplaceeTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM11 Solaire', slug='acrm11-signaux')
        self.user = User.objects.create_user(
            username='acrm11-resp', password='x', company=self.company,
            role_legacy='responsable')
        self.client_c = Client.objects.create(
            company=self.company, nom='Client', prenom='Version')
        self.lead = Lead.objects.create(
            company=self.company, nom='Version', owner=self.user,
            client=self.client_c)
        envoye_le = timezone.now() - datetime.timedelta(days=3)
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-ACRM11-0001',
            client=self.client_c, lead=self.lead, statut='envoye',
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, date_envoi=envoye_le)
        produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='ACRM11-P',
            prix_vente=Decimal('1400'), quantite_stock=10)
        LigneDevis.objects.create(
            devis=self.v1, produit=produit, designation='Panneau 550W',
            quantite=Decimal('10'), prix_unitaire=Decimal('1400'),
            remise=Decimal('0'))
        v2 = reviser_devis(self.v1, user=self.user)
        Devis.objects.filter(pk=v2.pk).update(
            statut='envoye', date_envoi=envoye_le)
        self.v1.refresh_from_db()
        self.v2 = Devis.objects.get(pk=v2.pk)
        self.lien_v1 = ShareLink.objects.create(
            company=self.company, devis=self.v1, token='acrm11-lien-v1')
        self.lien_v2 = ShareLink.objects.create(
            company=self.company, devis=self.v2, token='acrm11-lien-v2')
        self.prochaine = RelanceEtape.objects.create(
            company=self.company, lead=self.lead, cadence='apres_devis',
            ordre=1, canal=RelanceEtape.Canal.APPEL, libelle='Relancer',
            due_date=timezone.localdate() + datetime.timedelta(days=5))

    def _ouvrir(self, token, instant):
        with frozen(instant):
            link = ShareLink.objects.select_related(
                'devis', 'devis__lead', 'devis__superseded_by').get(
                    token=token)
            is_first = _stamp_view(link)
            _notify_open(link, None, is_first=is_first)

    def _echeances(self):
        return list(RelanceEtape.objects.filter(lead=self.lead)
                    .order_by('pk').values_list('due_date', flat=True))

    def test_engine_ignore_v1_remplacee(self):
        engagement_followup_engine()
        self.lien_v1.refresh_from_db()
        self.assertEqual(set(dates_declencheurs(self.lien_v1)), set())
        self.lien_v2.refresh_from_db()
        self.assertIn('not_opened_24h', set(dates_declencheurs(self.lien_v2)))

    def test_ouverture_v1_note_sans_touche(self):
        avant = self._echeances()
        debut = timezone.now()
        for i in range(3):
            self._ouvrir('acrm11-lien-v1',
                         debut + datetime.timedelta(minutes=16 * i))
        with frozen(debut + datetime.timedelta(minutes=60)):
            engagement_followup_engine()
        notes = list(LeadActivity.objects.filter(
            lead=self.lead, body__startswith='Ancienne version'
        ).values_list('body', flat=True))
        self.assertEqual(len(notes), 1, notes)
        self.assertIn(self.v1.reference, notes[0])
        self.assertIn(self.v2.reference, notes[0])
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='ouvert le devis').exists())
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__icontains='rouvert le devis').exists())
        self.assertFalse(RelanceEtape.objects.filter(
            lead=self.lead, libelle=TOUCHE_ROUVERTE).exists())
        self.assertEqual(self._echeances(), avant)

    def test_v2_inchangee(self):
        self._ouvrir('acrm11-lien-v2', timezone.now())
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead,
            body=f'Le client a ouvert le devis {self.v2.reference}').exists())
        self.assertFalse(LeadActivity.objects.filter(
            lead=self.lead, body__startswith='Ancienne version').exists())
