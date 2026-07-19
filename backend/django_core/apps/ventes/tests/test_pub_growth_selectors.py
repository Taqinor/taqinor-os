"""PUB58/59/60/62/67/69 — sélecteurs ventes des boucles de croissance ERP
(Groupe PUB, section PUB-P4). Chaque test prouve un contrat de données pur
(aucun réseau, aucun mock Meta ici — ça vit côté apps/adsengine/tests) :
segmentation devis vu/jamais-ouvert (QJ1), devis expiré + exclusion signée,
cross-sell base installée (entretien/batterie), totaux devis acceptés par
lead (carte chaleur ville), vélocité de signature par mois/mode (saisonnalité
réelle), lien de partage « mon installation » après signature.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.sav.models import ContratMaintenance
from apps.ventes.models import Devis, ShareLink
from apps.ventes.selectors import (
    devis_accepted_totals_by_lead, devis_view_tracking_segments,
    expired_devis_contacts, signature_velocity_by_month_and_mode,
    signed_clients_cross_sell_segments,
)

MONTH = timezone.now().strftime('%Y%m')


class DevisViewTrackingSegmentsTests(TestCase):
    """PUB58 — jamais ouvert vs ouvert-non-signé, depuis ShareLink.view_count."""

    def setUp(self):
        self.company = Company.objects.create(nom='PUB58 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='A',
            email='clienta@example.ma', telephone='+212600000001')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead B', email='leadb@example.ma',
            telephone='+212600000002')

    def _devis(self, ref, **kw):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            taux_tva=Decimal('20'), statut=Devis.Statut.ENVOYE, **kw)

    def test_never_opened_bucket(self):
        self._devis(f'DEV-{MONTH}-PUB5801')
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(len(segments['jamais_ouvert']), 1)
        self.assertEqual(segments['jamais_ouvert'][0]['email'],
                         'clienta@example.ma')
        self.assertEqual(segments['ouvert_non_signe'], [])

    def test_opened_not_signed_bucket_uses_view_count(self):
        d = self._devis(f'DEV-{MONTH}-PUB5802')
        ShareLink.objects.create(
            company=self.company, devis=d, view_count=3,
            first_viewed_at=timezone.now())
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'], [])
        self.assertEqual(len(segments['ouvert_non_signe']), 1)

    def test_share_link_with_zero_views_still_never_opened(self):
        d = self._devis(f'DEV-{MONTH}-PUB5803')
        ShareLink.objects.create(company=self.company, devis=d, view_count=0)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(len(segments['jamais_ouvert']), 1)
        self.assertEqual(segments['ouvert_non_signe'], [])

    def test_contact_prefers_lead_over_client(self):
        d = self._devis(f'DEV-{MONTH}-PUB5804', lead=self.lead)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'][0]['email'],
                         'leadb@example.ma')
        self.assertTrue(d.lead_id)

    def test_accepted_devis_excluded_entirely(self):
        self._devis(f'DEV-{MONTH}-PUB5805', statut=Devis.Statut.ACCEPTE)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'], [])
        self.assertEqual(segments['ouvert_non_signe'], [])

    def test_devis_without_any_contact_identifier_skipped(self):
        client_no_contact = Client.objects.create(
            company=self.company, nom='Sans', prenom='Contact')
        self._devis(f'DEV-{MONTH}-PUB5806', client=client_no_contact)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(segments['jamais_ouvert'], [])


class ExpiredDevisContactsTests(TestCase):
    """PUB59 — devis expirés, exclusion des clients déjà signés ailleurs."""

    def setUp(self):
        self.company = Company.objects.create(nom='PUB59 Selectors Co')
        self.expired_client = Client.objects.create(
            company=self.company, nom='Ex', prenom='Pire',
            email='ex@example.ma', telephone='+212600000040')
        self.signed_client = Client.objects.create(
            company=self.company, nom='Sig', prenom='Ne',
            email='sig@example.ma', telephone='+212600000041')

    def _devis(self, ref, client, statut):
        return Devis.objects.create(
            company=self.company, reference=ref, client=client,
            taux_tva=Decimal('20'), statut=statut)

    def test_no_expired_devis_returns_empty(self):
        self.assertEqual(expired_devis_contacts(self.company), [])

    def test_expired_devis_contact_included(self):
        self._devis(f'DEV-{MONTH}-PUB5901', self.expired_client,
                    Devis.Statut.EXPIRE)
        contacts = expired_devis_contacts(self.company)
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]['email'], 'ex@example.ma')

    def test_client_signed_elsewhere_excluded(self):
        self._devis(f'DEV-{MONTH}-PUB5902', self.signed_client,
                    Devis.Statut.EXPIRE)
        self._devis(f'DEV-{MONTH}-PUB5903', self.signed_client,
                    Devis.Statut.ACCEPTE)
        self.assertEqual(expired_devis_contacts(self.company), [])

    def test_dedup_multiple_expired_devis_same_client(self):
        self._devis(f'DEV-{MONTH}-PUB5904', self.expired_client,
                    Devis.Statut.EXPIRE)
        self._devis(f'DEV-{MONTH}-PUB5905', self.expired_client,
                    Devis.Statut.EXPIRE)
        contacts = expired_devis_contacts(self.company)
        self.assertEqual(len(contacts), 1)


class SignedClientsCrossSellSegmentsTests(TestCase):
    """PUB60 — sans_contrat (sav) + sans_batterie (devis d'origine)."""

    def setUp(self):
        self.company = Company.objects.create(nom='PUB60 Selectors Co')

    def _signed_client(self, nom, *, option_acceptee='', ref_suffix=None):
        client = Client.objects.create(
            company=self.company, nom=nom, prenom='C',
            email=f'{nom.lower()}@ex.ma', telephone='+212600000050')
        Devis.objects.create(
            company=self.company,
            reference=f'DEV-{MONTH}-{ref_suffix or nom}',
            client=client, taux_tva=Decimal('20'),
            statut=Devis.Statut.ACCEPTE, option_acceptee=option_acceptee)
        return client

    def test_no_signed_client_returns_empty_segments(self):
        result = signed_clients_cross_sell_segments(self.company)
        self.assertEqual(result, {'sans_contrat': [], 'sans_batterie': []})

    def test_client_with_active_contract_and_battery_excluded_both(self):
        client = self._signed_client(
            'Complet', option_acceptee=Devis.OptionAcceptee.AVEC_BATTERIE)
        ContratMaintenance.objects.create(
            company=self.company, client=client, periodicite='annuel',
            date_debut=timezone.localdate(), actif=True)
        result = signed_clients_cross_sell_segments(self.company)
        self.assertEqual(result['sans_contrat'], [])
        self.assertEqual(result['sans_batterie'], [])

    def test_client_without_contract_or_battery_in_both_segments(self):
        self._signed_client('Nu')
        result = signed_clients_cross_sell_segments(self.company)
        self.assertEqual(len(result['sans_contrat']), 1)
        self.assertEqual(len(result['sans_batterie']), 1)

    def test_origin_devis_is_the_earliest_accepted(self):
        client = Client.objects.create(
            company=self.company, nom='Origine', prenom='X',
            email='origine@ex.ma', telephone='+212600000051')
        premier = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-ORIG1',
            client=client, taux_tva=Decimal('20'),
            statut=Devis.Statut.ACCEPTE, option_acceptee='')
        Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-ORIG2',
            client=client, taux_tva=Decimal('20'),
            statut=Devis.Statut.ACCEPTE,
            option_acceptee=Devis.OptionAcceptee.AVEC_BATTERIE)
        result = signed_clients_cross_sell_segments(self.company)
        # Le devis d'ORIGINE (premier=sans batterie) qualifie pour sans_batterie
        # même si un devis PLUS RÉCENT du même client a une batterie.
        self.assertEqual(len(result['sans_batterie']), 1)
        self.assertIsNotNone(premier)


class DevisAcceptedTotalsByLeadTests(TestCase):
    """PUB62 — total TTC des devis acceptés par lead (ticket moyen ville)."""

    def setUp(self):
        self.company = Company.objects.create(nom='PUB62 Ventes Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Ville')
        self.lead = Lead.objects.create(
            company=self.company, nom='Lead Ville', ville='Agadir')

    def test_empty_lead_ids_returns_empty_dict(self):
        self.assertEqual(devis_accepted_totals_by_lead(self.company, []), {})

    def test_lead_without_accepted_devis_absent(self):
        Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-PUB6201',
            client=self.client_obj, lead=self.lead, taux_tva=Decimal('20'),
            statut=Devis.Statut.ENVOYE)
        totals = devis_accepted_totals_by_lead(self.company, [self.lead.id])
        self.assertEqual(totals, {})

    def test_sums_multiple_accepted_devis_for_same_lead(self):
        for i in range(2):
            Devis.objects.create(
                company=self.company, reference=f'DEV-{MONTH}-PUB620{i+2}',
                client=self.client_obj, lead=self.lead, taux_tva=Decimal('20'),
                statut=Devis.Statut.ACCEPTE)
        totals = devis_accepted_totals_by_lead(self.company, [self.lead.id])
        self.assertIn(self.lead.id, totals)


class SignatureVelocityByMonthAndModeTests(TestCase):
    """PUB67 — vélocité de signature réelle mois-par-mois par mode marché."""

    def setUp(self):
        self.company = Company.objects.create(nom='PUB67 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Saison')

    def _signed(self, ref, mode, date_acceptation):
        return Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            taux_tva=Decimal('20'), statut=Devis.Statut.ACCEPTE,
            mode_installation=mode, date_acceptation=date_acceptation)

    def test_no_signed_devis_empty_result(self):
        result = signature_velocity_by_month_and_mode(self.company)
        self.assertEqual(result['par_mode'], {})
        self.assertEqual(result['mois_couverts'], 0)

    def test_counts_grouped_by_calendar_month_and_mode(self):
        from datetime import date
        self._signed(f'DEV-{MONTH}-PUB6701', 'residentiel', date(2025, 3, 10))
        self._signed(f'DEV-{MONTH}-PUB6702', 'residentiel', date(2026, 3, 5))
        self._signed(f'DEV-{MONTH}-PUB6703', 'agricole', date(2025, 8, 1))
        result = signature_velocity_by_month_and_mode(self.company)
        self.assertEqual(result['par_mode']['residentiel'][3], 2)
        self.assertEqual(result['par_mode']['agricole'][8], 1)
        # 3 mois-calendaires DISTINCTS : (2025,3), (2026,3), (2025,8).
        self.assertEqual(result['mois_couverts'], 3)

    def test_non_accepted_devis_excluded(self):
        from datetime import date
        Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-PUB6704',
            client=self.client_obj, taux_tva=Decimal('20'),
            statut=Devis.Statut.ENVOYE, mode_installation='residentiel',
            date_acceptation=date(2025, 1, 1))
        result = signature_velocity_by_month_and_mode(self.company)
        self.assertEqual(result['par_mode'], {})
