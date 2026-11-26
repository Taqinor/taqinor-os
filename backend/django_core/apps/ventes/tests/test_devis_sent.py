"""U4 — Partager un devis par WhatsApp le marque « envoyé » et fait avancer le
funnel CRM (→ QUOTE_SENT).

Couvre, via le service ``mark_devis_sent`` (le SEUL chemin de changement de
statut, règle #4) et l'endpoint ``whatsapp-devis`` qui l'appelle :

  * brouillon → envoyé + horodatage ``date_envoi`` posé une fois ;
  * avance du lead lié vers QUOTE_SENT via l'événement ``devis_sent`` ;
  * idempotence (re-partage = no-op, pas de second horodatage/événement) ;
  * jamais de régression d'un devis déjà accepté / refusé ;
  * isolation multi-société (un devis d'une autre société n'est jamais touché).

Les noms d'étapes viennent de ``apps.crm.stages`` (STAGES.py — jamais codés en
dur, règle #2).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm import stages
from apps.crm.models import Client, Lead, LeadActivity
from apps.ventes.models import Devis, DevisActivity
from apps.ventes.services import mark_devis_sent

User = get_user_model()


def make_company(slug='u4-co', nom='U4 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestMarkDevisSentService(TestCase):
    """Le service ``mark_devis_sent`` — l'unique transition brouillon → envoyé."""

    def setUp(self):
        self.company = make_company()
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678')
        self.lead = Lead.objects.create(
            company=self.company, nom='Alaoui', telephone='0612345678')

    def _devis(self, statut=Devis.Statut.BROUILLON, lead=None):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-{statut}-{id(statut)}',
            client=self.client_obj, lead=lead, statut=statut)

    def _devis_deux_options(self, reference):
        """Un VRAI devis à deux options (réseau / hybride + batterie), fiches
        techniques complètes, 30 panneaux au toit et en ligne."""
        from decimal import Decimal
        from apps.stock.models import FicheTechnique, Produit
        from apps.ventes.models import LigneDevis
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            roof_layout={'_pans_geometry': [{'label': 'Sud', 'nb_panneaux': 30,
                                             'azimut_deg': 180, 'inclinaison_deg': 20}]})
        onduleur = dict(ond_n_mppt=2, ond_mppt_v_min=Decimal('200.0'), ond_mppt_v_max=Decimal('650.0'),
                        ond_v_max_abs=Decimal('800.0'), ond_i_max_mppt_a=Decimal('26.0'),
                        ond_ac_kw=Decimal('15'), ond_phases=3, ond_rendement_euro_pct=Decimal('97.0'))
        materiel = (
            ('Panneau Canadien Solar 710W', 'Canadien Solar', 30, 'module', dict(
                pmax_wc=Decimal('710.00'), voc_v=Decimal('48.30'), isc_a=Decimal('18.59'),
                vmp_v=Decimal('40.40'), imp_a=Decimal('17.59'),
                temp_coeff_voc_pct_c=Decimal('-0.250'), temp_coeff_pmax_pct_c=Decimal('-0.290'))),
            ('Onduleur réseau Huawei 15kW Triphasé', 'Huawei', 1, 'onduleur', onduleur),
            ('Onduleur hybride Deye 15kW Triphasé', 'Deye', 1, 'onduleur', onduleur),
            ('Batterie Dyness 15,4 kWh', 'Dyness', 1, 'batterie', dict(
                bat_kwh_nominal=Decimal('15.36'), bat_v_nominal=Decimal('51.2'))))
        for rang, (nom, marque, quantite, type_fiche, fiche) in enumerate(materiel):
            produit = Produit.objects.create(company=self.company, nom=nom, marque=marque,
                                             sku=f'{reference}-{rang}', prix_vente=Decimal('1000'))
            FicheTechnique.objects.create(company=self.company, produit=produit,
                                          type_fiche=type_fiche, **fiche)
            LigneDevis.objects.create(devis=devis, produit=produit, designation=nom,
                                      quantite=Decimal(quantite), prix_unitaire=Decimal('1000'),
                                      remise=Decimal('0'))
        return devis

    def test_d_acal_158_un_vrai_envoi_range_une_vraie_conception_par_option(self):
        """D-ACAL-158 — un vrai envoi (aucun calcul simulé) range la conception
        de l'option que ``electrical_design`` ne porte pas ; la page client sert
        alors les deux options, l'étude rangée et son empreinte n'ont pas bougé."""
        from apps.ventes import electrical_service as es
        devis = self._devis_deux_options('DEV-ACAL158-1')
        es.build_electrical_design(devis)
        devis.refresh_from_db()
        design, empreinte = devis.electrical_design, devis.electrical_design_hash
        self.assertIsNotNone(design)
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual((devis.electrical_design, devis.electrical_design_hash), (design, empreinte))
        entree = [c for c in devis.clauses_appliquees if c.get('type') == 'conceptions_options_figees']
        self.assertEqual(len(entree), 1)
        self.assertEqual(set(entree[0]['options']), {'sans_batterie'})
        sans = entree[0]['options']['sans_batterie']
        self.assertEqual(sans['design']['materiel']['nb_modules'], 30)
        self.assertTrue(sans['design']['chaines'])
        self.assertEqual(len(sans['hash']), 64)
        public = es.schema_electrique_public(devis, standard=False, option_totals={
            'sans_batterie': {'ttc': 1}, 'avec_batterie': {'ttc': 1}})['options']
        self.assertIn('Huawei', public['sans_batterie']['onduleurs'][0]['designation'])
        self.assertIsNone(public['sans_batterie']['batterie'])
        self.assertIn('Deye', public['avec_batterie']['onduleurs'][0]['designation'])
        self.assertIsNotNone(public['avec_batterie']['batterie'])

    def test_d_acal_158_un_calcul_qui_leve_n_arrete_pas_l_envoi(self):
        from unittest import mock
        from apps.ventes import conceptions_options
        devis = self._devis_deux_options('DEV-ACAL158-2')
        with mock.patch.object(conceptions_options, '_conception_de_l_option',
                               side_effect=RuntimeError('fiche absente')):
            mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        entree = [c for c in devis.clauses_appliquees if c.get('type') == 'conceptions_options_figees']
        self.assertEqual([e['options'] for e in entree], [{}])

    def test_kwh_incoherent_factures_refuse_l_envoi(self):
        """ADVS48 (règle fondateur 30/09) — un brouillon au kWh déclaré contredit
        par les factures ne part par aucun geste : 409 nommé, brouillon, 0 mail ;
        lead corrigé : envoyé."""
        from decimal import Decimal

        from django.core import mail
        from apps.ventes.horaire.conso import CODE_KWH_INCOHERENT, MESSAGE_KWH_INCOHERENT
        from core.conflit_etat import ConflitEtat
        Lead.objects.filter(pk=self.lead.pk).update(
            conso_mensuelle_kwh=Decimal('46'), facture_hiver=Decimal('10000'), ete_differente=False)
        self.lead.refresh_from_db()
        self.client_obj.email = 'alaoui@example.com'
        self.client_obj.save(update_fields=['email'])
        devis = self._devis(lead=self.lead)
        with self.assertRaises(ConflitEtat):
            mark_devis_sent(devis=devis, user=None)
        api = make_api(User.objects.create_user(
            username='advs48-resp', password='x', company=self.company, role_legacy='responsable'))
        base = f'/api/django/ventes/devis/{devis.id}/'
        for chemin, corps in (('share-link/', {'envoi': True}), ('envoyer-email/', {}),
                              ('whatsapp/', {}), ('pdf-partage/', {})):
            with self.subTest(chemin=chemin):
                resp = api.post(base + chemin, corps, format='json')
                self.assertEqual(resp.status_code, 409, resp.content)
                self.assertEqual(str(resp.data['code']), CODE_KWH_INCOHERENT)
                self.assertEqual(str(resp.data['detail']), MESSAGE_KWH_INCOHERENT)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(devis.date_envoi)
        self.assertEqual(len(mail.outbox), 0)
        Lead.objects.filter(pk=self.lead.pk).update(
            conso_mensuelle_kwh=Decimal('650'), facture_hiver=Decimal('1200'))
        devis.refresh_from_db()
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_conception_divergente_refuse_l_envoi(self):
        """ACON86 (C-ACON-021) — calepinage lié (lien direct) à une conception
        différente de celle du brouillon : 409 nommé par tous les gestes, devis
        brouillon, 0 mail ; resynchronisé (même empreinte) : envoyé."""
        from django.core import mail
        from apps.calepinage.models import Calepinage
        from core.conflit_etat import ConflitEtat
        self.client_obj.email = 'alaoui@example.com'
        self.client_obj.save(update_fields=['email'])
        devis = self._devis()
        Devis.objects.filter(pk=devis.pk).update(layout_hash='a' * 64)
        devis.refresh_from_db()
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj, devis=devis,
            titre='Toit ACON86', layout_hash='b' * 64)
        with self.assertRaises(ConflitEtat):
            mark_devis_sent(devis=devis, user=None)
        api = make_api(User.objects.create_user(
            username='acon86-resp', password='x', company=self.company, role_legacy='responsable'))
        base = f'/api/django/ventes/devis/{devis.id}/'
        for chemin, corps in (('envoyer-email/', {}), ('share-link/', {'envoi': True}),
                              ('whatsapp/', {})):
            with self.subTest(chemin=chemin):
                resp = api.post(base + chemin, corps, format='json')
                self.assertEqual(resp.status_code, 409, resp.content)
                self.assertEqual(str(resp.data['code']), 'conception_a_resynchroniser')
                self.assertIn('« Toit ACON86 »', str(resp.data['detail']))
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(devis.date_envoi)
        self.assertEqual(len(mail.outbox), 0)
        Calepinage.objects.filter(pk=calepinage.pk).update(layout_hash='')  # inconnu : part
        devis.refresh_from_db()
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_ligne_a_prix_zero_refuse_l_envoi_en_nommant_les_lignes(self):
        """T4-U3-007 — une ligne de quantité > 0 au prix 0 ne part au client
        par aucun geste : 409 qui nomme les lignes et dit quoi faire ; le
        brouillon s'enregistre toujours ; prix saisi : envoyé ; un devis DÉJÀ
        envoyé n'est jamais touché."""
        from decimal import Decimal

        from django.core import mail
        from apps.ventes.models import LigneDevis
        from core.conflit_etat import ConflitEtat
        self.client_obj.email = 'alaoui@example.com'
        self.client_obj.save(update_fields=['email'])
        devis = self._devis(lead=self.lead)
        LigneDevis.objects.create(devis=devis, designation='Panneaux 550 W',
                                  quantite=Decimal('10'), prix_unitaire=Decimal('900'))
        tableau = LigneDevis.objects.create(
            devis=devis, designation='Tableau De Protection AC/DC',
            quantite=Decimal('1'), prix_unitaire=Decimal('0'))
        LigneDevis.objects.create(devis=devis, designation='Accessoires',
                                  quantite=Decimal('1'), prix_unitaire=None)
        LigneDevis.objects.create(devis=devis, designation='Matériel',
                                  type_ligne=LigneDevis.TypeLigne.SECTION)
        LigneDevis.objects.create(devis=devis, designation='Option retirée',
                                  quantite=Decimal('0'), prix_unitaire=Decimal('0'))
        with self.assertRaises(ConflitEtat) as refus:
            mark_devis_sent(devis=devis, user=None)
        detail = str(refus.exception.detail['detail'])
        self.assertIn('« Tableau De Protection AC/DC »', detail)
        self.assertIn('« Accessoires »', detail)
        self.assertNotIn('Matériel', detail)
        self.assertNotIn('Option retirée', detail)
        self.assertIn('saisissez un prix ou retirez la ligne', detail)
        api = make_api(User.objects.create_user(
            username='t4u3007-resp', password='x', company=self.company,
            role_legacy='responsable'))
        base = f'/api/django/ventes/devis/{devis.id}/'
        for chemin, corps in (('share-link/', {'envoi': True}), ('envoyer-email/', {}),
                              ('whatsapp/', {}), ('pdf-partage/', {})):
            with self.subTest(chemin=chemin):
                resp = api.post(base + chemin, corps, format='json')
                self.assertEqual(resp.status_code, 409, resp.content)
                self.assertEqual(str(resp.data['code']), 'lignes_prix_zero')
                self.assertEqual(resp.data['lignes'],
                                 ['Tableau De Protection AC/DC', 'Accessoires'])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(len(mail.outbox), 0)
        # Le brouillon s'enregistre toujours (aucun refus à la sauvegarde).
        resp = api.patch(base, {'notes': 'à compléter'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        # Prix saisis : il part.
        LigneDevis.objects.filter(pk=tableau.pk).update(prix_unitaire=Decimal('1500'))
        LigneDevis.objects.filter(devis=devis, designation='Accessoires').update(
            prix_unitaire=Decimal('300'))
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        # Un devis déjà envoyé n'est jamais touché : re-partage sans refus.
        LigneDevis.objects.filter(pk=tableau.pk).update(prix_unitaire=Decimal('0'))
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_brouillon_flips_to_envoye_and_stamps_date(self):
        devis = self._devis()
        self.assertIsNone(devis.date_envoi)
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertIsNotNone(devis.date_envoi)

    def test_writes_chatter_entry(self):
        devis = self._devis()
        mark_devis_sent(devis=devis, user=None)
        act = DevisActivity.objects.filter(
            devis=devis, kind=DevisActivity.Kind.MODIFICATION).first()
        self.assertIsNotNone(act)
        self.assertEqual(act.new_value, 'Envoyé')
        self.assertEqual(act.company, self.company)

    def test_advances_linked_lead_to_quote_sent(self):
        lead = Lead.objects.create(
            company=self.company, nom='Funnel', stage=stages.NEW)
        devis = self._devis(lead=lead)
        mark_devis_sent(devis=devis, user=None)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'QUOTE_SENT')

    def test_idempotent_on_already_envoye(self):
        devis = self._devis()
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        first_stamp = devis.date_envoi
        before = DevisActivity.objects.filter(devis=devis).count()
        # Deuxième appel : aucun changement, pas de second horodatage/chatter.
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(devis.date_envoi, first_stamp)
        self.assertEqual(
            DevisActivity.objects.filter(devis=devis).count(), before)

    def test_never_downgrades_accepted_devis(self):
        devis = self._devis(statut=Devis.Statut.ACCEPTE)
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ACCEPTE)
        self.assertIsNone(devis.date_envoi)

    def test_never_downgrades_refused_devis(self):
        devis = self._devis(statut=Devis.Statut.REFUSE)
        mark_devis_sent(devis=devis, user=None)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.REFUSE)

    def test_does_not_regress_lead_already_signed(self):
        # Un lead déjà SIGNED ne recule pas vers QUOTE_SENT à l'envoi.
        lead = Lead.objects.create(
            company=self.company, nom='Signed', stage='SIGNED')
        devis = self._devis(lead=lead)
        mark_devis_sent(devis=devis, user=None)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, 'SIGNED')


class TestWhatsAppDevisFlipsSent(TestCase):
    """L'endpoint ``whatsapp-devis`` marque chaque devis partagé « envoyé »."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='u4_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            telephone='0612345678', stage=stages.NEW)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', telephone='0612345678')
        self.d1 = Devis.objects.create(
            company=self.company, reference='DEV-U4-1',
            client=self.client_obj, lead=self.lead)

    def _url(self):
        return f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis/'

    def test_sharing_flips_devis_to_envoye(self):
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.statut, Devis.Statut.ENVOYE)
        self.assertIsNotNone(self.d1.date_envoi)

    def test_sharing_advances_lead_to_quote_sent(self):
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, 'QUOTE_SENT')
        # Une entrée d'historique auto a tracé l'avance du funnel.
        self.assertTrue(LeadActivity.objects.filter(
            lead=self.lead, field='stage').exists())

    def test_sharing_does_not_regress_accepted_devis(self):
        self.d1.statut = Devis.Statut.ACCEPTE
        self.d1.save(update_fields=['statut'])
        resp = self.api.post(
            self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.statut, Devis.Statut.ACCEPTE)

    def test_resharing_is_idempotent(self):
        self.api.post(self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.d1.refresh_from_db()
        first_stamp = self.d1.date_envoi
        before = DevisActivity.objects.filter(devis=self.d1).count()
        self.api.post(self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.date_envoi, first_stamp)
        self.assertEqual(
            DevisActivity.objects.filter(devis=self.d1).count(), before)

    def test_un_devis_refuse_n_envoie_aucun_devis(self):
        """ADVS51 — partage multi-devis tout-ou-rien : A (12 kWh mesurés, sans
        garde) puis B (kWh déclaré contredit) ⇒ 409, A et B brouillons, lead à
        son étape, aucun lien ni AuditLog WHATSAPP ; [A] seul : 200, A envoyé."""
        from decimal import Decimal
        from django.apps import apps as django_apps
        from apps.ventes.horaire.conso import CODE_KWH_INCOHERENT
        from apps.ventes.models import ShareLink
        AuditLog = django_apps.get_model('audit', 'AuditLog')
        Lead.objects.filter(pk=self.lead.pk).update(
            conso_mensuelle_kwh=Decimal('46'), facture_hiver=Decimal('10000'), ete_differente=False)
        Devis.objects.filter(pk=self.d1.pk).update(etude_params={'conso_kwh_mensuelles': [300] * 12})
        d2 = Devis.objects.create(
            company=self.company, reference='DEV-U4-2', client=self.client_obj, lead=self.lead)
        resp = self.api.post(self._url(), {'devis_ids': [self.d1.id, d2.id]}, format='json')
        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(str(resp.data['code']), CODE_KWH_INCOHERENT)
        for d in (self.d1, d2):
            d.refresh_from_db()
            self.assertEqual((d.statut, d.date_envoi), (Devis.Statut.BROUILLON, None))
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.stage, stages.NEW)
        self.assertFalse(ShareLink.objects.filter(devis__in=[self.d1, d2]).exists())
        self.assertFalse(AuditLog.objects.filter(action=AuditLog.Action.WHATSAPP).exists())
        resp = self.api.post(self._url(), {'devis_ids': [self.d1.id]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.statut, Devis.Statut.ENVOYE)


class TestCrossTenantIsolation(TestCase):
    """Un devis d'une autre société n'est jamais marqué envoyé via ce chemin."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='u4_iso', password='x', role_legacy='responsable',
            company=self.company)
        self.api = make_api(self.user)
        self.lead = Lead.objects.create(
            company=self.company, nom='Local', telephone='0612345678')

        self.other = make_company('u4-other', 'Other Co')
        self.other_client = Client.objects.create(
            company=self.other, nom='Foreign')
        self.foreign_devis = Devis.objects.create(
            company=self.other, reference='DEV-FOR-1',
            client=self.other_client, statut=Devis.Statut.BROUILLON)

    def test_foreign_devis_id_is_rejected_and_untouched(self):
        resp = self.api.post(
            f'/api/django/crm/leads/{self.lead.id}/whatsapp-devis/',
            {'devis_ids': [self.foreign_devis.id]}, format='json')
        # L'endpoint refuse un devis hors société/hors lead (409, comme un id
        # inexistant — ENF48, règle ENF40) — et surtout le devis étranger
        # n'est PAS passé à « envoyé ».
        self.assertEqual(resp.status_code, 409)
        self.foreign_devis.refresh_from_db()
        self.assertEqual(self.foreign_devis.statut, Devis.Statut.BROUILLON)
        self.assertIsNone(self.foreign_devis.date_envoi)
