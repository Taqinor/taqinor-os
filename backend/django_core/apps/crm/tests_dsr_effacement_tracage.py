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
    EmpreinteOpposition, Lead, LeadActivity, RelanceEtape, VisiteExterne,
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

    def test_l_effacement_arrete_les_cadences(self):
        """ACVI39 — après l'effacement, 0 touche à faire."""
        from django.utils import timezone

        from apps.crm.models import RelanceEtape

        for ordre in (1, 2):
            RelanceEtape.objects.create(
                company=self.company, lead=self.lead, cadence='contact',
                ordre=ordre, canal=RelanceEtape.Canal.APPEL, libelle='Appel',
                due_at=timezone.now(), due_date=timezone.localdate())
        self.assertEqual(erase_crm(self.company, 'amina@example.ma'), 1)
        self.assertFalse(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.A_FAIRE).exists())
        self.assertEqual(self.lead.relance_etapes.filter(
            statut=RelanceEtape.Statut.ANNULEE, note='effacement').count(), 2)

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

    def test_un_stop_vivant_suit_la_personne(self):
        """ACVI43 (D-ACVI-6) — B née opposée au numéro de A ; après la levée
        sur A, C naît contactable."""
        from apps.crm.cadence_reponses import (
            CONSENT_SOURCE_OPPOSITION_TOUCHE, tracer_opposition_registre)
        from apps.crm.leads_consentement import tracer_levee_opposition_registre

        numero = '+212612349061'
        a = Lead.objects.create(company=self.company, nom='A', telephone=numero,
                                owner=self.user)
        Lead.objects.filter(pk=a.pk).update(ne_plus_contacter=True)
        a.refresh_from_db()
        tracer_opposition_registre(a, source=CONSENT_SOURCE_OPPOSITION_TOUCHE)
        b = Lead.objects.create(company=self.company, nom='B', telephone=numero)
        self.assertTrue(b.ne_plus_contacter)
        Lead.objects.filter(pk=a.pk).update(ne_plus_contacter=False)
        a.refresh_from_db()
        tracer_levee_opposition_registre(a, self.user)
        c = Lead.objects.create(company=self.company, nom='C', telephone=numero)
        self.assertFalse(c.ne_plus_contacter)

    def test_levee_garde_l_empreinte_si_un_autre_lead_reste_oppose(self):
        """ERR-ACVI6-OPPOSITION — l'opposition suit la personne : lever A ne
        libère pas un numéro que B (opposé) porte encore."""
        from apps.crm.leads_consentement import tracer_levee_opposition_registre

        numero = '+212612349081'
        a = Lead.objects.create(company=self.company, nom='A', telephone=numero,
                                ne_plus_contacter=True, owner=self.user)
        Lead.objects.create(company=self.company, nom='B', telephone=numero,
                            ne_plus_contacter=True, owner=self.user)
        Lead.objects.filter(pk=a.pk).update(ne_plus_contacter=False)
        a.refresh_from_db()
        tracer_levee_opposition_registre(a, self.user)
        c = Lead.objects.create(company=self.company, nom='C', telephone=numero)
        self.assertTrue(c.ne_plus_contacter)

    def test_contact_ajoute_a_un_lead_deja_oppose_porte_l_opposition(self):
        """ERR-ACVI6-OPPOSITION — un téléphone/e-mail posé APRÈS l'opposition
        laisse son empreinte."""
        a = Lead.objects.create(company=self.company, nom='A', owner=self.user,
                                ne_plus_contacter=True)
        a.telephone = '+212612349082'
        a.email = 'tard.acvi6@example.com'
        a.save()
        for contact in ({'telephone': '+212612349082'},
                        {'email': 'tard.acvi6@example.com'}):
            with self.subTest(contact=contact):
                n = Lead.objects.create(company=self.company, nom='N', **contact)
                self.assertTrue(n.ne_plus_contacter)

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

    def _fusionner(self, survivant, *absorbes):
        from apps.crm.leads_fusion import merge_leads
        return merge_leads(survivant, list(absorbes), self.user)

    def _opposition_au_registre(self, identifiant):
        from core.models import ConsentRecord
        return ConsentRecord.objects.filter(
            company=self.company, subject_identifier=identifiant,
            granted=False, source__startswith='fusion de fiches').exists()

    def test_fusion_contact_comble_sur_un_survivant_oppose(self):
        """D-ACVI-6 — l'absorbé n'est pas opposé, le survivant l'est : le
        téléphone et l'e-mail venus de l'absorbé portent l'opposition."""
        numero = '+212612349073'
        courriel = 'comble.acvi6@example.com'
        survivant = Lead.objects.create(
            company=self.company, nom='S', whatsapp='+212612349074',
            ne_plus_contacter=True, owner=self.user)
        absorbe = Lead.objects.create(
            company=self.company, nom='A', telephone=numero, email=courriel,
            owner=self.user)

        self._fusionner(survivant, absorbe)

        survivant.refresh_from_db()
        self.assertEqual(survivant.telephone, numero)
        self.assertEqual(survivant.email, courriel)
        for contact in ({'telephone': numero}, {'email': courriel}):
            with self.subTest(contact=contact):
                recree = Lead.objects.create(
                    company=self.company, nom='Recrée', **contact)
                self.assertTrue(recree.ne_plus_contacter)
        self.assertTrue(self._opposition_au_registre(numero))
        self.assertTrue(self._opposition_au_registre(courriel))

    def test_fusion_sans_contact_comble_n_ecrit_rien_au_registre(self):
        """Survivant opposé, aucun contact comblé : rien de neuf à tracer."""
        from core.models import ConsentRecord
        survivant = Lead.objects.create(
            company=self.company, nom='S', telephone='+212612349075',
            ne_plus_contacter=True, owner=self.user)
        absorbe = Lead.objects.create(
            company=self.company, nom='A', ville='Rabat', owner=self.user)
        avant = ConsentRecord.objects.count()

        self._fusionner(survivant, absorbe)

        self.assertEqual(ConsentRecord.objects.count(), avant)

    def test_fusion_sans_opposition_ne_laisse_aucune_empreinte(self):
        survivant = Lead.objects.create(
            company=self.company, nom='S', email='libre.acvi6@example.com',
            owner=self.user)
        absorbe = Lead.objects.create(
            company=self.company, nom='A', telephone='+212612349076',
            owner=self.user)

        self._fusionner(survivant, absorbe)

        self.assertFalse(EmpreinteOpposition.objects.exists())

    def test_fusion_absorbe_oppose_garde_son_propre_numero(self):
        """D-ACVI-6 — l'absorbé opposé a son numéro, le survivant le sien (qui
        n'est donc pas comblé) : les deux numéros portent l'opposition."""
        du_survivant = '+212612349077'
        de_l_absorbe = '+212612349078'
        survivant = Lead.objects.create(
            company=self.company, nom='S', telephone=du_survivant,
            owner=self.user)
        absorbe = Lead.objects.create(
            company=self.company, nom='A', telephone=de_l_absorbe,
            owner=self.user)
        Lead.objects.filter(pk=absorbe.pk).update(ne_plus_contacter=True)
        absorbe.refresh_from_db()

        self._fusionner(survivant, absorbe)

        survivant.refresh_from_db()
        self.assertEqual(survivant.telephone, du_survivant)
        self.assertTrue(survivant.ne_plus_contacter)
        for numero in (du_survivant, de_l_absorbe):
            with self.subTest(numero=numero):
                recree = Lead.objects.create(
                    company=self.company, nom='Recrée', telephone=numero)
                self.assertTrue(recree.ne_plus_contacter)
                self.assertTrue(self._opposition_au_registre(numero))

    def test_fusion_absorbe_oppose_meme_numero_une_seule_trace(self):
        """Le même numéro des deux côtés : pas de ligne de registre en double."""
        from core.models import ConsentRecord
        numero = '+212612349079'
        survivant = Lead.objects.create(
            company=self.company, nom='S', telephone=numero, owner=self.user)
        absorbe = Lead.objects.create(
            company=self.company, nom='A', telephone=numero, owner=self.user)
        Lead.objects.filter(pk=absorbe.pk).update(ne_plus_contacter=True)
        absorbe.refresh_from_db()

        self._fusionner(survivant, absorbe)

        from apps.crm.leads_consentement import FINALITES_CONTACT
        self.assertEqual(ConsentRecord.objects.filter(
            company=self.company, subject_identifier=numero, granted=False,
            source__startswith='fusion de fiches').count(),
            len(FINALITES_CONTACT))

    def _rattraper(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps as registre
        from django.db import connection
        migration = import_module(
            'apps.crm.migrations.0154_acvi6_empreintes_opposition_existantes')
        migration.poser_empreintes_existantes(
            registre, SimpleNamespace(connection=connection))

    def test_rattrapage_des_personnes_deja_opposees(self):
        """D-ACVI-6 — une opposition antérieure à ACVI43 n'a aucune empreinte :
        sans rattrapage, une nouvelle fiche à ce numéro naît contactable."""
        numero_archive = '+212612349071'
        archive = Lead.objects.create(
            company=self.company, nom='Archive', telephone=numero_archive,
            ne_plus_contacter=True, is_archived=True, owner=self.user)
        ailleurs = Lead.objects.create(
            company=self.autre, nom='Ailleurs', telephone='+212612349072',
            ne_plus_contacter=True)
        self.assertFalse(EmpreinteOpposition.objects.exists())
        modifie_le = Lead.objects.filter(pk=self.oppose.pk).values_list(
            'date_modification', flat=True).get()
        chatter = LeadActivity.objects.count()

        self._rattraper()

        # Aucun champ de lead, aucun chatter.
        self.assertEqual(Lead.objects.filter(pk=self.oppose.pk).values_list(
            'date_modification', flat=True).get(), modifie_le)
        self.assertEqual(LeadActivity.objects.count(), chatter)
        archive.refresh_from_db()
        self.assertTrue(archive.is_archived)
        self.assertEqual(EmpreinteOpposition.objects.filter(
            company=self.company, nature='telephone').count(), 2)
        self.assertEqual(EmpreinteOpposition.objects.filter(
            company=self.company, nature='email').count(), 1)
        self.assertEqual(EmpreinteOpposition.objects.filter(
            company=self.autre).count(), 1)
        # Le lecteur retrouve ce que la migration a écrit, à chaque porte.
        for contact in ({'telephone': TELEPHONE_LOCAL},
                        {'email': '  SARA.opposee@example.COM'},
                        {'whatsapp': TELEPHONE},
                        {'telephone': numero_archive}):
            with self.subTest(contact=contact):
                recree = Lead.objects.create(
                    company=self.company, nom='Recrée', **contact)
                self.assertTrue(recree.ne_plus_contacter)
        # Le cloisonnement tient : le numéro de l'autre société reste libre ici.
        libre = Lead.objects.create(
            company=self.company, nom='Libre', telephone=ailleurs.telephone)
        self.assertFalse(libre.ne_plus_contacter)
        # Un non-opposé ne laisse rien.
        non_oppose = Lead.objects.create(
            company=self.company, nom='Non', telephone=self.locataire.telephone)
        self.assertFalse(non_oppose.ne_plus_contacter)

    def test_rattrapage_idempotent(self):
        self._rattraper()
        avant = sorted(EmpreinteOpposition.objects.values_list(
            'pk', 'nature', 'empreinte'))
        self.assertEqual(len(avant), 2)
        self._rattraper()
        self.assertEqual(sorted(EmpreinteOpposition.objects.values_list(
            'pk', 'nature', 'empreinte')), avant)

    def test_rattrapage_garde_une_empreinte_deja_posee(self):
        """Une empreinte d'effacement (ACRM62) survit au rattrapage."""
        self._effacer()
        self.assertEqual(EmpreinteOpposition.objects.count(), 2)
        self._rattraper()
        self.assertEqual(EmpreinteOpposition.objects.count(), 2)

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
