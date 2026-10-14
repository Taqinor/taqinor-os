"""Tests N25 — acceptation explicite d'un devis (date + nom) + chatter."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def make_company(slug='acc-co', nom='Acc Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDevisAcceptation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='acc_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Acc',
            email='acc@example.com', telephone='+212600000001')

    def _devis(self, num=1, statut=Devis.Statut.ENVOYE):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'))

    def _devis_deux_options(self, num=20):
        """Devis à deux options (réseau + hybride/batterie) → nb_options == 2.

        PV86 — le devis DÉCLARE son alternative dans ``etude_params['scenario']``
        (ce que le générateur persiste toujours). Sans déclaration, deux
        onduleurs en lignes non optionnelles ne sont plus un document à deux
        options mais un artefact de données rendu en une seule présentation.
        """
        devis = self._devis(num=num)
        devis.etude_params = {'scenario': 'Les deux (Sans + Avec)'}
        devis.save(update_fields=['etude_params'])
        lignes = [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ]
        for desig, qty, pu in lignes:
            sku = f'{num}-{desig[:12]}'
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=sku,
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def test_accepter_sets_metadata_and_chatter(self):
        devis = self._devis()
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Bennani', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertEqual(str(devis.date_acceptation), '2026-06-10')
        self.assertEqual(devis.accepte_par_nom, 'M. Bennani')
        acts = DevisActivity.objects.filter(devis=devis)
        self.assertEqual(acts.count(), 1)
        self.assertIn('Bennani', acts.first().body)

    def test_accepter_defaults_date_to_today(self):
        devis = self._devis(num=2)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.date_acceptation, timezone.now().date())

    def test_acceptation_fige_l_echeancier(self):
        """AMET2 (D-ECH-FIGE) — l'échéancier est FIGÉ en base AVANT
        ``devis_accepted`` : un abonné relit déjà le plan figé ; la
        dés-acceptation le garde (trace), seul le statut recule."""
        from apps.ventes.domain.cycle_vie import annuler_acceptation
        from core.events import devis_accepted
        devis = self._devis(num=5)
        self.assertFalse(devis.echeancier)
        vus = []

        def _abonne(sender, devis, **kwargs):
            vus.append(Devis.objects.get(pk=devis.pk).echeancier)

        devis_accepted.connect(_abonne, weak=False)
        try:
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/accepter/',
                {'nom': 'Client'}, format='json')
        finally:
            devis_accepted.disconnect(_abonne)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(vus), 1)
        self.assertTrue(vus[0])
        devis.refresh_from_db()
        self.assertEqual(devis.echeancier, vus[0])
        self.assertEqual(devis.date_acceptation, timezone.now().date())
        annuler_acceptation(devis=devis, user=self.user)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.echeancier, vus[0])

    def test_invalid_date_rejected(self):
        devis = self._devis(num=3)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'date': 'pas-une-date'}, format='json')
        self.assertEqual(r.status_code, 400)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')

    def test_corps_mal_type_rejete_sans_accepter(self):
        # ENF11 — champ de mauvais type / corps non objet : 400, rien n'est accepté.
        devis = self._devis(num=30)
        for corps in ({'nom': 5}, {'date': 20260610}, {'override_credit': 1},
                      {'override_avertissement': 'true'}, {'entreprise': 'x'},
                      [1]):
            r = self.api.post(
                f'/api/django/ventes/devis/{devis.id}/accepter/',
                corps, format='json')
            self.assertEqual(r.status_code, 400, (corps, r.data))
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')

    def test_historique_and_noter(self):
        devis = self._devis(num=4)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/noter/',
            {'body': 'Relancé le client par téléphone.'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        h = self.api.get(f'/api/django/ventes/devis/{devis.id}/historique/')
        self.assertEqual(h.status_code, 200)
        bodies = [a['body'] for a in h.data]
        self.assertTrue(any('Relancé' in (b or '') for b in bodies))

    def test_empty_note_rejected(self):
        devis = self._devis(num=5)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/noter/',
            {'body': '   '}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_acceptation_enables_chantier_creation(self):
        """L'acceptation est le déclencheur : creer-depuis-devis exige accepté."""
        devis = self._devis(num=6)
        # Avant acceptation : refusé — 409 (conflit d'ÉTAT : le devis existe
        # mais n'est pas accepté), le 400 étant réservé au corps mal formé et
        # le 404 au devis inconnu (ERR-ENF11-FUZZ-INSTALLATIONS, 3160247c8).
        r0 = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r0.status_code, 409, r0.data)
        # Après acceptation : autorisé.
        self.api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                      {'nom': 'Client', 'date': '2026-06-05'}, format='json')
        r1 = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        # U6 : l'acceptation crée DÉJÀ le chantier automatiquement (événement
        # devis_accepted → receiver installations) ; l'endpoint manuel est donc
        # idempotent et renvoie le chantier existant (200) au lieu d'en créer un
        # second.
        self.assertEqual(r1.status_code, 200, r1.data)
        # La date de signature du chantier reprend la date d'acceptation.
        self.assertEqual(r1.data.get('date_signature'), '2026-06-05')

    # ── A1 — option retenue (Sans batterie / Avec batterie) ──────────────

    def test_single_option_devis_infers_option(self):
        """Devis à option unique (ici vide) : l'option est déduite, pas exigée,
        et le comportement N25 (date + nom) reste intact."""
        devis = self._devis(num=10)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'M. Bennani', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertEqual(devis.option_acceptee, 'sans_batterie')

    def test_two_option_devis_requires_explicit_option(self):
        """Devis à deux options accepté SANS option → refusé (400)."""
        devis = self._devis_deux_options(num=21)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')
        self.assertEqual(devis.option_acceptee, '')

    def test_two_option_devis_records_chosen_option(self):
        """Devis à deux options accepté AVEC option → stockée + consignée."""
        devis = self._devis_deux_options(num=22)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10',
             'option': 'avec_batterie'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'accepte')
        self.assertEqual(devis.option_acceptee, 'avec_batterie')
        act = DevisActivity.objects.filter(devis=devis).first()
        self.assertIn('Avec batterie', act.body)

    # ── A2 — filtre ?lead= (dialogue « Signé » liste les devis du lead) ──────

    def test_devis_filtered_by_lead(self):
        """GET /ventes/devis/?lead=<id> ne renvoie que les devis de ce lead."""
        lead_a = Lead.objects.create(
            company=self.company, nom='Lead A', stage='QUOTE_SENT')
        lead_b = Lead.objects.create(
            company=self.company, nom='Lead B', stage='QUOTE_SENT')
        da = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0030',
            client=self.client_obj, lead=lead_a, taux_tva=Decimal('20'))
        Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0031',
            client=self.client_obj, lead=lead_b, taux_tva=Decimal('20'))
        r = self.api.get(f'/api/django/ventes/devis/?lead={lead_a.id}')
        self.assertEqual(r.status_code, 200, r.data)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        ids = {row['id'] for row in rows}
        self.assertEqual(ids, {da.id})

    # ── A4 — la fiche lead expose chantier + option sur ses devis ────────────

    def test_lead_devis_exposes_chantier_and_option(self):
        """Après acceptation + création du chantier, le devis du lead porte son
        chantier (anti-doublon dans l'UI) et l'option retenue."""
        lead = Lead.objects.create(
            company=self.company, nom='Lead A4', stage='QUOTE_SENT')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0060',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                      {'nom': 'Client', 'date': '2026-06-10'}, format='json')
        self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                      {'devis': devis.id}, format='json')
        r = self.api.get(f'/api/django/crm/leads/{lead.id}/')
        self.assertEqual(r.status_code, 200, r.data)
        row = [d for d in r.data['devis'] if d['id'] == devis.id][0]
        self.assertEqual(row['option_acceptee'], 'sans_batterie')
        self.assertIsNotNone(row['chantier'])
        self.assertTrue(row['chantier']['reference'])

    def test_invalid_option_rejected(self):
        """Une option inconnue est refusée (400) avant tout changement."""
        devis = self._devis_deux_options(num=23)
        r = self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10',
             'option': 'banane'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        devis.refresh_from_db()
        self.assertNotEqual(devis.statut, 'accepte')

    # ── VNT54 — une seule vente en vigueur par lead ─────────────────────────

    def _vente_388(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead VNT54', stage='QUOTE_SENT')
        vente = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0380',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        return lead, vente

    def _accepter(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/accepter/',
            {'nom': 'Client', 'date': '2026-06-10'}, format='json')

    def test_vnt54_variante_d_une_vente_acceptee_refusee(self):
        lead, vente = self._vente_388()
        variante = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0390',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
            version_parent=vente, taux_tva=Decimal('20'))
        r = self._accepter(variante)
        self.assertEqual(r.status_code, 409, r.data)
        self.assertEqual(r.data['code'], 'vente_active_existante')
        self.assertEqual(r.data['vente_active']['id'], vente.pk)
        variante.refresh_from_db()
        self.assertEqual(variante.statut, Devis.Statut.ENVOYE)

    def test_vnt54_revision_de_la_vente_acceptee(self):
        lead, vente = self._vente_388()
        v2 = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0400',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
            version_parent=vente, version=2, taux_tva=Decimal('20'))
        Devis.objects.filter(pk=vente.pk).update(
            is_active=False, superseded_by=v2)
        r = self._accepter(v2)
        self.assertEqual(r.status_code, 200, r.data)
        v2.refresh_from_db()
        self.assertEqual(v2.statut, Devis.Statut.ACCEPTE)

    def test_vnt54_lead_sans_vente_accepte(self):
        lead = Lead.objects.create(
            company=self.company, nom='Lead libre', stage='QUOTE_SENT')
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0410',
            client=self.client_obj, lead=lead, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        self.assertEqual(self._accepter(devis).status_code, 200)

    # ── VNT62 — échéancier figé + brouillon d'acompte, défait à la sortie ──

    def test_vnt62_acceptation_pose_l_acompte_la_sortie_de_signe_l_annule(
            self):
        import apps.crm.stages as stages
        from apps.ventes.models import Facture
        from apps.ventes.tests.test_echeancier_somme_total import (
            creer_devis_388)
        lead = Lead.objects.create(
            company=self.company, nom='Lead VNT62', stage=stages.FOLLOW_UP)
        devis = creer_devis_388(self.company, self.user, self.client_obj,
                                f'DEV-{MONTH}-0620', statut='envoye',
                                lead=lead)
        r = self.api.post(f'/api/django/ventes/devis/{devis.id}/accepter/',
                          {'nom': 'Client 388'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        brouillon = Facture.objects.get(
            devis=devis, statut=Facture.Statut.BROUILLON,
            type_facture='acompte')
        self.assertEqual(brouillon.total_ttc, Decimal('14700.00'))
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.SIGNED)

        r = self.api.patch(f'/api/django/crm/leads/{lead.id}/',
                           {'stage': stages.FOLLOW_UP,
                            'confirme_recul': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        lead.refresh_from_db()
        devis.refresh_from_db()
        brouillon.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(brouillon.statut, Facture.Statut.ANNULEE)
