"""ADEV47 (C-ADEV-013) — l'expiration nocturne des devis est CONDITIONNELLE :
un devis accepté entre la lecture et l'écriture de la boucle reste ACCEPTÉ,
sans chatter « expiré » ni événement d'expiration ; un devis non accepté
expire comme avant.

La course est rendue déterministe : le point d'injection déclaré est
``apps.ventes.utils.expiry.is_expired`` (appelé par la boucle APRÈS la
sélection et AVANT l'écriture) — l'enveloppe commet l'acceptation puis rend
le verdict réel. Le reste (boucle, `is_expired`, chatter, événement) est réel.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.ventes.tests.test_xfac_adev47_expiration_conditionnelle"
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone


class ExpirationConditionnelleTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from authentication.models import Company
        self.company = Company.objects.create(nom='ADEV47', slug='adev47-co')
        client = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV47',
            email='adev47@example.invalid')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-ADEV47-1', client=client,
            statut=Devis.Statut.ENVOYE, taux_tva=Decimal('20'),
            date_envoi=timezone.now() - timedelta(days=90))
        Devis.objects.filter(pk=self.devis.pk).update(
            date_validite=timezone.now().date() - timedelta(days=30))

    def _expirer(self):
        from apps.ventes.domain.recouvrement import expire_stale_devis
        return expire_stale_devis()

    def test_accepte_pendant_boucle_reste_accepte(self):
        from apps.ventes.models import Devis
        from apps.ventes.utils import expiry
        reel = expiry.is_expired
        maintenant = timezone.now().date()

        def _course(devis, today=None):
            verdict = reel(devis, today=today)
            # Acceptation committée ENTRE la sélection et l'écriture.
            Devis.objects.filter(pk=devis.pk).update(
                statut=Devis.Statut.ACCEPTE, date_acceptation=maintenant)
            return verdict

        from core.events import devis_expired
        recus = []

        def _ecoute(sender, **kwargs):
            recus.append(kwargs.get('devis'))
        devis_expired.connect(_ecoute)
        self.addCleanup(devis_expired.disconnect, _ecoute)
        with patch.object(expiry, 'is_expired', side_effect=_course):
            resultat = self._expirer()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ACCEPTE)
        self.assertIsNotNone(self.devis.date_acceptation)
        self.assertEqual(resultat['expired'], 0)
        self.assertEqual(recus, [])

    def _lead_inactif(self):
        """Un lead « Relance » sans activité depuis 31 jours, lié au devis."""
        from apps.crm import stages
        from apps.crm.models import Lead, LeadActivity
        from apps.ventes.models import Devis
        lead = Lead.objects.create(
            company=self.company, nom='Inactif', stage=stages.FOLLOW_UP,
            telephone='+212661470001')
        LeadActivity.objects.filter(lead=lead).update(
            created_at=timezone.now() - timedelta(days=31))
        Devis.objects.filter(pk=self.devis.pk).update(lead=lead)
        return lead

    def test_l_expiration_range_au_froid_avec_une_raison(self):
        """CADV84 — Froid, raison en champ, devis expiré (règle #4) ; une 2e
        nuit n'écrit rien. Deux lignes de chatter : parc_raison puis stage.
        Mutant : retirer ``parquer_lead`` ⇒ ``parc_raison`` vide."""
        from apps.crm import stages
        from apps.ventes.models import Devis
        lead = self._lead_inactif()
        resultat = self._expirer()
        self.assertEqual(resultat['funnel_cold'], 1)
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.COLD)
        self.assertEqual((lead.parc_etat, lead.parc_raison, lead.parc_jusqu_au),
                         ('nurture', 'pas_maintenant_sans_date', None))
        self.assertEqual(lead.activites.filter(field='parc_raison').count(), 1)
        self.assertEqual(lead.activites.filter(field='stage').count(), 1)
        self.assertEqual(Devis.objects.get(pk=self.devis.pk).statut,
                         Devis.Statut.EXPIRE)
        self.assertEqual(self._expirer()['funnel_cold'], 0)
        self.assertEqual(lead.activites.filter(field='parc_raison').count(), 1)

    def test_un_lead_en_standby_a_date_future_n_est_pas_parque(self):
        """Le garde ``lead_en_attente_ou_veille`` tient : touche datée à venir."""
        from apps.crm import stages
        from apps.crm.models import RelanceEtape
        from apps.ventes.domain.recouvrement import NOTE_EXPIRATION_EN_ATTENTE
        lead = self._lead_inactif()
        dans_20 = timezone.now().date() + timedelta(days=20)
        RelanceEtape.objects.create(
            company=self.company, lead=lead, cadence='contact', ordre=1,
            due_date=dans_20, canal=RelanceEtape.Canal.APPEL)
        lead.__class__.objects.filter(pk=lead.pk).update(
            parc_etat='standby', parc_raison='plus_tard_date',
            parc_jusqu_au=dans_20)
        self._expirer()
        lead.refresh_from_db()
        self.assertEqual(lead.stage, stages.FOLLOW_UP)
        self.assertEqual(lead.parc_etat, 'standby')
        self.assertTrue(lead.activites.filter(
            body=NOTE_EXPIRATION_EN_ATTENTE).exists())

    def test_mort_avant_les_effets_rejoue_tout(self):
        """ACEL69 (C-ACEL-011) — une mort dure (BaseException) pendant la note
        d'historique annule le statut : devis « envoyé », lead à QUOTE_SENT,
        aucun événement ; le passage suivant fait tout. Mutant : ressortir la
        note de la transaction ⇒ devis expiré sans note."""
        from apps.crm import stages
        from apps.crm.models import Lead
        from apps.ventes import activity
        from apps.ventes.models import Devis, DevisActivity
        from core.events import devis_expired
        lead = Lead.objects.create(
            company=self.company, nom='Mort', stage=stages.QUOTE_SENT,
            telephone='+212661470002')
        Devis.objects.filter(pk=self.devis.pk).update(lead=lead)
        recus = []

        def _ecoute(sender, **kwargs):
            recus.append(kwargs.get('devis'))
        devis_expired.connect(_ecoute)
        self.addCleanup(devis_expired.disconnect, _ecoute)

        class _Mort(BaseException):
            pass
        with patch.object(activity, 'log_devis_note', side_effect=_Mort):
            with self.assertRaises(_Mort):
                self._expirer()
        self.devis.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.ENVOYE)
        self.assertEqual(lead.stage, stages.QUOTE_SENT)
        self.assertEqual(recus, [])

        self.assertEqual(self._expirer()['expired'], 1)
        self.devis.refresh_from_db()
        lead.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.EXPIRE)
        self.assertEqual(DevisActivity.objects.filter(
            devis=self.devis,
            body__startswith='Devis expiré automatiquement').count(), 1)
        self.assertEqual(len(recus), 1)
        self.assertEqual(lead.stage, stages.FOLLOW_UP)

    def test_envoye_expire(self):
        from apps.ventes.models import Devis
        resultat = self._expirer()
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, Devis.Statut.EXPIRE)
        self.assertEqual(resultat['expired'], 1)
