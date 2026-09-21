"""XMKT22 — Politique « sunset » d'engagement.

Couvre : un contact dormant est sauté aux envois (journalisé), la campagne
de re-permission le réactive au clic, fenêtre désactivable (défaut OFF).
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import Campagne, EnvoiCampagne, StatutEngagementContact
from apps.parametres.models_company import CompanyProfile


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class SunsetEngagementTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt22', 'XMKT22')

    def test_desactive_par_defaut_no_op(self):
        marques = services.recalculer_dormants(self.co)
        self.assertEqual(marques, 0)

    def test_contact_sans_engagement_marque_dormant(self):
        CompanyProfile.objects.create(company=self.co, sunset_fenetre_jours=90)
        camp = Campagne.objects.create(
            company=self.co, nom='C', canal=Campagne.Canal.EMAIL)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='dormant@x.ma',
            envoye_le=timezone.now() - datetime.timedelta(days=200))
        marques = services.recalculer_dormants(self.co)
        self.assertEqual(marques, 1)
        self.assertTrue(services.est_dormant(self.co, 'dormant@x.ma'))

    def test_contact_engage_recemment_reste_actif(self):
        CompanyProfile.objects.create(company=self.co, sunset_fenetre_jours=90)
        camp = Campagne.objects.create(
            company=self.co, nom='C2', canal=Campagne.Canal.EMAIL)
        EnvoiCampagne.objects.create(
            company=self.co, campagne=camp, destinataire='actif@x.ma',
            ouvert_le=timezone.now() - datetime.timedelta(days=10))
        services.recalculer_dormants(self.co)
        self.assertFalse(services.est_dormant(self.co, 'actif@x.ma'))

    def test_dormant_saute_a_lenvoi_et_journalise(self):
        StatutEngagementContact.objects.create(
            company=self.co, destinataire='dormant2@x.ma',
            statut=StatutEngagementContact.Statut.DORMANT)
        camp = Campagne.objects.create(
            company=self.co, nom='C3', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(
            camp, destinataires=['ok@x.ma', 'dormant2@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.nb_destinataires, 1)
        envoi = EnvoiCampagne.objects.get(campagne=camp, destinataire='dormant2@x.ma')
        self.assertEqual(envoi.raison_smtp, 'contact_dormant_sunset')

    def test_clic_reactive_contact_dormant(self):
        StatutEngagementContact.objects.create(
            company=self.co, destinataire='reactive@x.ma',
            statut=StatutEngagementContact.Statut.DORMANT)
        camp = Campagne.objects.create(
            company=self.co, nom='C4', canal=Campagne.Canal.EMAIL,
            corps='https://taqinor.ma/repermission')
        services.envoyer_campagne(camp, destinataires=['other@x.ma'])
        from apps.marketing.models import LienTrackee
        lien = LienTrackee.objects.get(campagne=camp)
        services.traiter_clic_lien(lien.token, destinataire='reactive@x.ma')
        self.assertFalse(services.est_dormant(self.co, 'reactive@x.ma'))

    def test_isolation_multi_tenant(self):
        other = make_company('xmkt22-b', 'XMKT22-B')
        StatutEngagementContact.objects.create(
            company=self.co, destinataire='shared@x.ma',
            statut=StatutEngagementContact.Statut.DORMANT)
        self.assertFalse(services.est_dormant(other, 'shared@x.ma'))
