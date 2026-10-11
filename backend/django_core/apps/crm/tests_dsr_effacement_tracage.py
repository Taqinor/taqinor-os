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
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.crm import dsr_provider
from apps.crm.cadence_reponses import creer_lead_proprietaire
from apps.crm.dsr_provider import erase_crm
from apps.crm.leads_doublons import normalize_email, normalize_phone
from apps.crm.models import (
    EmpreinteOpposition, Lead, RelanceEtape, VisiteExterne,
)

User = get_user_model()


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


# ═══════════════════════════════════════════════════════════════════════════
# ACRM62 — l'opposition survit à l'effacement (empreinte hachée)
# ═══════════════════════════════════════════════════════════════════════════
# ACRM62 (C-ACRM-028, D-ACRM-5 (2)=(a)) — l'opposition survit à l'effacement.
#
# Sonde V_VB LSVC5-3 : un lead « ne plus contacter » effacé (DSR) puis recréé
# repartait vierge — drapeau faux, cadence posée. Désormais l'effacement
# (chemin unique ``dsr_provider.anonymiser_lead``) laisse une EMPREINTE hachée
# seule de l'e-mail et du téléphone, et tout lead qui naît avec l'une d'elles
# naît « ne plus contacter ».
#
# Aucun mock : effacement, création et cadence réels.

EMAIL = 'Sara.Opposee@Example.com'
TELEPHONE = '+212661626262'
TELEPHONE_LOCAL = '0661 62 62 62'


class EmpreinteOppositionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM62 Solaire', slug='acrm62-opposition')
        self.autre = Company.objects.create(
            nom='ACRM62 Autre', slug='acrm62-autre')
        self.user = User.objects.create_user(
            username='acrm62-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.oppose = Lead.objects.create(
            company=self.company, nom='Sara', email=EMAIL,
            telephone=TELEPHONE, ne_plus_contacter=True, owner=self.user)
        self.locataire = Lead.objects.create(
            company=self.company, nom='Locataire', telephone='+212700000062',
            owner=self.user)

    def _effacer(self):
        dsr_provider.erase_crm(self.company, EMAIL)

    def test_lead_recree_nait_oppose(self):
        self._effacer()
        proprietaire, cree = creer_lead_proprietaire(
            self.locataire, self.user,
            {'nom': 'Sara', 'telephone': TELEPHONE_LOCAL})
        self.assertTrue(cree)
        proprietaire = Lead.objects.get(pk=proprietaire.pk)
        self.assertTrue(proprietaire.ne_plus_contacter)
        self.assertFalse(
            RelanceEtape.objects.filter(lead=proprietaire).exists())
        # Même personne par une autre porte, e-mail en casse différente.
        par_email = Lead.objects.create(
            company=self.company, nom='Sara', email='  SARA.opposee@example.COM')
        self.assertTrue(Lead.objects.get(pk=par_email.pk).ne_plus_contacter)

    def test_aucune_valeur_en_clair(self):
        self._effacer()
        empreintes = list(EmpreinteOpposition.objects.filter(
            company=self.company).values_list('nature', 'empreinte'))
        self.assertEqual(sorted(n for n, _ in empreintes),
                         ['email', 'telephone'])
        clairs = {EMAIL, EMAIL.lower(), TELEPHONE, normalize_email(EMAIL),
                  normalize_phone(TELEPHONE)}
        for _nature, empreinte in empreintes:
            self.assertRegex(empreinte, r'^[0-9a-f]{64}$')
            for clair in clairs:
                self.assertNotIn(clair, empreinte)
        # Un second effacement de la même personne ne duplique rien.
        self._effacer()
        self.assertEqual(EmpreinteOpposition.objects.filter(
            company=self.company).count(), 2)

    def test_non_oppose_sans_empreinte(self):
        Lead.objects.filter(pk=self.oppose.pk).update(ne_plus_contacter=False)
        self._effacer()
        self.assertFalse(EmpreinteOpposition.objects.exists())
        recree = Lead.objects.create(
            company=self.company, nom='Sara', email=EMAIL, telephone=TELEPHONE)
        self.assertFalse(Lead.objects.get(pk=recree.pk).ne_plus_contacter)

    def test_autre_societe_intacte(self):
        self._effacer()
        ailleurs = Lead.objects.create(
            company=self.autre, nom='Sara', email=EMAIL, telephone=TELEPHONE)
        self.assertFalse(Lead.objects.get(pk=ailleurs.pk).ne_plus_contacter)
        self.assertFalse(
            EmpreinteOpposition.objects.filter(company=self.autre).exists())
