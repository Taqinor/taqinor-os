"""Revue critique 25/08/2026, finding #13 — l'effacement 09-08 était TROUÉ.

``dsr_provider.erase_crm`` vidait les PII « classiques » du lead (nom, email,
téléphone, adresse) mais laissait intacts les identifiants de TRAÇAGE ajoutés
par T-TRACE : ``Lead.appareil_id`` et, sur chaque ``crm.VisiteExterne`` du
lead, l'IP, le navigateur, l'``appareil_id`` et le suffixe de jeton. Un lead
« anonymisé » restait donc parfaitement ré-identifiable — et une visite
ultérieure du même navigateur le rattachait à sa fiche effacée
(``visites.rattacher_visites_au_lead``).

DOCTRINE DU MODULE : on ANONYMISE, on ne supprime pas. Les lignes de visite
survivent (leur finalité anti-fraude ne porte plus aucune PII une fois les
identifiants vidés), comme survivent les activités et les documents comptables.
"""
from django.test import TestCase

from authentication.models import Company

from apps.crm.dsr_provider import erase_crm
from apps.crm.models import Lead, VisiteExterne


class EffacementTracageTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor DSR', slug='taqinor-dsr-trace')
        self.lead = Lead.objects.create(
            company=self.company, nom='Benali', prenom='Amina',
            email='amina@example.ma', telephone='+212600000000',
            appareil_id='appareil-amina-uuid')
        self.visite = VisiteExterne.objects.create(
            company=self.company, lead=self.lead,
            point=VisiteExterne.Point.PROPOSITION,
            contexte='Ouverture devis', token_suffixe='aBc123',
            ip='41.77.1.5', user_agent='Mozilla/5.0 (Android)',
            appareil_id='appareil-amina-uuid', duree_s=120)

    def test_l_appareil_id_du_lead_est_efface(self):
        self.assertEqual(erase_crm(self.company, 'amina@example.ma'), 1)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.nom, 'Anonymisé')
        self.assertIsNone(self.lead.appareil_id)

    def test_les_visites_perdent_tous_leurs_identifiants(self):
        erase_crm(self.company, 'amina@example.ma')
        self.visite.refresh_from_db()
        self.assertEqual(self.visite.ip, '')
        self.assertEqual(self.visite.user_agent, '')
        self.assertEqual(self.visite.appareil_id, '')
        self.assertEqual(self.visite.token_suffixe, '')

    def test_la_ligne_de_visite_survit_avec_sa_mesure(self):
        """On anonymise, on ne supprime pas : combien de passages, quand et sur
        quelle page restent lisibles — ce ne sont plus des PII."""
        erase_crm(self.company, 'amina@example.ma')
        self.assertEqual(
            VisiteExterne.objects.filter(lead=self.lead).count(), 1)
        self.visite.refresh_from_db()
        self.assertEqual(self.visite.duree_s, 120)
        self.assertEqual(self.visite.contexte, 'Ouverture devis')

    def test_plus_aucun_rattachement_possible_apres_effacement(self):
        """LA CONSÉQUENCE CONCRÈTE : l'appareil ne ramène plus personne à la
        fiche effacée."""
        from apps.crm import visites as trace

        erase_crm(self.company, 'amina@example.ma')
        self.lead.refresh_from_db()
        self.assertEqual(trace.rattacher_visites_au_lead(self.lead), 0)
        self.assertIsNone(
            trace.historique_appareil(self.company, 'appareil-amina-uuid'))

    def test_les_visites_d_un_autre_lead_ne_sont_pas_touchees(self):
        """Rien au-delà de la personne concernée — même société, autre fiche."""
        autre = Lead.objects.create(
            company=self.company, nom='Autre', email='autre@example.ma',
            appareil_id='appareil-autre-uuid')
        visite_autre = VisiteExterne.objects.create(
            company=self.company, lead=autre,
            point=VisiteExterne.Point.PROPOSITION,
            ip='41.77.9.9', user_agent='Mozilla/5.0 (iPhone)',
            appareil_id='appareil-autre-uuid')

        erase_crm(self.company, 'amina@example.ma')

        autre.refresh_from_db()
        visite_autre.refresh_from_db()
        self.assertEqual(autre.appareil_id, 'appareil-autre-uuid')
        self.assertEqual(visite_autre.ip, '41.77.9.9')
        self.assertEqual(visite_autre.appareil_id, 'appareil-autre-uuid')

    def test_lead_sans_visite_ne_leve_pas(self):
        lead = Lead.objects.create(
            company=self.company, nom='Sans trace',
            email='sanstrace@example.ma')
        self.assertEqual(erase_crm(self.company, 'sanstrace@example.ma'), 1)
        lead.refresh_from_db()
        self.assertEqual(lead.nom, 'Anonymisé')
