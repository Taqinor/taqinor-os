"""ADEV45 (C-ADEV-003) — les lecteurs agrégés des AUTRES propriétaires ne
proposent ni ne comptent jamais une V1 remplacée par sa révision.

Un devis V1 ENVOYÉ révisé en V2 ENVOYÉE garde sa V1 (``is_active=False``,
statut ``envoye`` inchangé — sondes VB q5 et VC p8). Chaque lecteur passe par
``apps.ventes.selectors.devis_en_jeu`` : « Relances du jour »
(``selectors_cadence``), publicité (``selectors_publicite``), co-achat
(``selectors_stock``), relance d'engagement (``scheduled``), digest
(``notifications.digests``) et relance CRM (``crm.services``). Un devis jamais
révisé apparaît comme avant.

Test-du-test : retirer ``devis_en_jeu`` d'un lecteur ⇒ son test échoue.

Hors périmètre : les lecteurs de devis ACCEPTÉS en vigueur (vélocité,
totaux signés, base installée) — ADEV46, GATED sur D-ADEV-1.
"""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.tests.test_l_niv_niveau import (
    make_client, make_company, make_devis, make_user,
)


class LecteursEnJeuTests(TestCase):

    def setUp(self):
        self.company = make_company('adev45')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.v1 = make_devis(self.company, self.user, self.client_obj,
                             'DEV-ADEV45-0001')
        self.v2 = make_devis(self.company, self.user, self.client_obj,
                             'DEV-ADEV45-0001-V2')
        self.envoye_le = timezone.now() - datetime.timedelta(days=10)
        Devis.objects.filter(pk=self.v1.pk).update(
            is_active=False, superseded_by=self.v2, date_envoi=self.envoye_le)
        Devis.objects.filter(pk=self.v2.pk).update(
            version=2, version_parent=self.v1, date_envoi=self.envoye_le)

    # ── « Relances du jour » (VC p8 : envoyes_sans_reponse = [V1, V2]) ──────

    def test_relances_du_jour_sans_v1(self):
        from apps.ventes.selectors_cadence import devis_action_requise
        paniers = devis_action_requise(self.company)['buckets']
        self.assertEqual(paniers['envoyes_sans_reponse']['ids'],
                         [self.v2.pk])

    def test_refuses_sans_motif_sans_v1(self):
        from apps.ventes.selectors_cadence import devis_action_requise
        Devis.objects.filter(pk__in=[self.v1.pk, self.v2.pk]).update(
            statut=Devis.Statut.REFUSE, motif_refus='')
        paniers = devis_action_requise(self.company)['buckets']
        self.assertEqual(paniers['refuses_sans_motif']['ids'], [self.v2.pk])

    # ── Publicité ───────────────────────────────────────────────────────────

    def test_segments_vues_sans_v1(self):
        from apps.ventes.selectors_publicite import (
            devis_view_tracking_segments)
        segments = devis_view_tracking_segments(self.company)
        self.assertEqual(len(segments['jamais_ouvert']), 1)
        self.assertEqual(segments['ouvert_non_signe'], [])

    def test_contacts_expires_sans_v1(self):
        from apps.ventes.selectors_publicite import expired_devis_contacts
        Devis.objects.filter(pk=self.v1.pk).update(
            statut=Devis.Statut.EXPIRE)
        self.assertEqual(expired_devis_contacts(self.company), [])

    def test_valeur_du_lead_sans_v1(self):
        from apps.crm.models import Lead
        from apps.ventes.selectors_publicite import devis_value_for_lead
        lead = Lead.objects.create(company=self.company, nom='ADEV45')
        Devis.objects.filter(pk__in=[self.v1.pk, self.v2.pk]).update(
            lead=lead)
        # V1 rendue « la plus récente » : sans le filtre, c'est elle qui
        # donnerait la valeur.
        Devis.objects.filter(pk=self.v1.pk).update(
            date_creation=timezone.now() + datetime.timedelta(days=1))
        LigneDevis.objects.filter(devis=self.v1).update(
            prix_unitaire=Decimal('1'))
        valeur = devis_value_for_lead(lead.pk, self.company)
        self.assertEqual(
            Decimal(str(valeur['value'])).quantize(Decimal('0.01')),
            Decimal(str(Devis.objects.get(pk=self.v2.pk).total_ttc))
            .quantize(Decimal('0.01')))

    # ── Co-achat ────────────────────────────────────────────────────────────

    def test_co_achat_sans_v1(self):
        from apps.ventes.selectors_stock import frequence_co_achat
        Devis.objects.filter(pk__in=[self.v1.pk, self.v2.pk]).update(
            statut=Devis.Statut.ACCEPTE)
        a = Produit.objects.create(
            company=self.company, nom='Panneau A', sku='ADEV45-A',
            prix_vente=Decimal('100'), quantite_stock=5)
        b = Produit.objects.create(
            company=self.company, nom='Onduleur B', sku='ADEV45-B',
            prix_vente=Decimal('100'), quantite_stock=5)
        for devis in (self.v1, self.v2):
            for produit in (a, b):
                LigneDevis.objects.create(
                    devis=devis, produit=produit, designation=produit.nom,
                    quantite=Decimal('1'), prix_unitaire=Decimal('100'),
                    remise=Decimal('0'))
        # ``make_devis`` pose aussi ses propres produits (onduleur, panneau)
        # sur chaque version : seuls ceux de la V2 EN JEU comptent, une fois
        # chacun — B compris (2 si la V1 remplacée comptait encore).
        attendu = {pid: 1 for pid in LigneDevis.objects.filter(
            devis=self.v2).exclude(produit=a).values_list(
                'produit_id', flat=True)}
        self.assertIn(b.pk, attendu)
        self.assertEqual(dict(frequence_co_achat(self.company, a.pk)),
                         attendu)

    # ── Relance d'engagement planifiée ──────────────────────────────────────

    def test_engagement_sans_v1(self):
        from apps.ventes.scheduled import engagement_followup_engine
        from apps.ventes.selectors import dates_declencheurs
        lien_v1 = ShareLink.objects.create(
            company=self.company, devis=self.v1, token='adev45-v1')
        lien_v2 = ShareLink.objects.create(
            company=self.company, devis=self.v2, token='adev45-v2')
        engagement_followup_engine()
        lien_v1.refresh_from_db()
        lien_v2.refresh_from_db()
        self.assertEqual(set(dates_declencheurs(lien_v1)), set())
        self.assertIn('not_opened_24h', set(dates_declencheurs(lien_v2)))

    # ── Digest ──────────────────────────────────────────────────────────────

    def test_digest_compte_une_fois(self):
        from apps.notifications.digests import _count_devis_en_attente
        self.assertEqual(_count_devis_en_attente(self.company), 1)

    def test_digest_devis_sans_revision_compte_comme_avant(self):
        from apps.notifications.digests import _count_devis_en_attente
        make_devis(self.company, self.user, self.client_obj,
                   'DEV-ADEV45-0002')
        self.assertEqual(_count_devis_en_attente(self.company), 2)

    # ── Relance CRM (VB q5 : devis_envoyes_pour_relance -> [V2, V1]) ───────

    def test_relance_crm_sans_v1(self):
        from apps.crm.models import Lead
        from apps.crm.services import devis_envoyes_pour_relance
        lead = Lead.objects.create(company=self.company, nom='ADEV45 CRM')
        Devis.objects.filter(pk__in=[self.v1.pk, self.v2.pk]).update(
            lead=lead)
        self.assertEqual(
            [d.pk for d in devis_envoyes_pour_relance(lead)], [self.v2.pk])
