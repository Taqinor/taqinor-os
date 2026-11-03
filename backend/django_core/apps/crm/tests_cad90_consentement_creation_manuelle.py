"""CAD90 — le registre de consentement couvre TOUTES les créations de lead.

Audit L3 du 21/09/2026, section CAD-I. ``enregistrer_consentement_lead``
n'était appelée que depuis le webhook du formulaire du site : un lead créé à
la main par la commerciale (appel entrant, message reçu au salon), un lead
Meta Lead Ads ou un lead venu d'un document n'écrivaient RIEN au registre
``core.ConsentRecord`` — alors que la cadence démarre quand même et que sa
touche n°1 est un WhatsApp, le canal le plus encadré.

Ce fichier verrouille :

  * un lead créé à la main écrit une entrée au registre, avec SA SOURCE et
    SA BASE LÉGALE ;
  * la base légale est la bonne des deux, sur texte primaire — art. 5 §3 de
    la loi 09-08 (+ art. 34 du décret 2-09-165) quand les données ne sont pas
    collectées auprès de la personne, relation précontractuelle à SA demande
    quand elle a elle-même sollicité le contact ;
  * ``granted`` reste FAUX : aucune case n'a été cochée sur ces chemins, et
    une preuve de consentement fabriquée serait pire qu'une preuve absente ;
  * le registre n'est jamais bloquant : une création de lead aboutit même si
    l'écriture au registre échoue.
"""
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ConsentRecord

from apps.crm import horaires, leads_consentement, stages
from apps.crm.fiche_bulk import _preparations_whatsapp_du_jour, apply_bulk_action
from apps.crm.models import Lead, LeadActivity
from apps.parametres.models import CompanyProfile

User = get_user_model()

LEADS_URL = '/api/django/crm/leads/'


class _Base(TestCase):
    slug = 'cad90'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        CompanyProfile.objects.get_or_create(company=self.company)
        self.acteur = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.acteur)}')
        return api

    def _entrees(self, identifiant):
        return list(ConsentRecord.objects.filter(
            company=self.company, subject_identifier=identifiant))


class SaisieManuelleTests(_Base):
    slug = 'cad90-manuel'

    def test_un_lead_saisi_a_la_main_ecrit_au_registre(self):
        """L'identifiant inscrit au registre est le numéro CANONIQUE.

        `LeadSerializer.validate_telephone` canonicalise tout numéro marocain
        en `212…` à l'écriture (comportement antérieur à CAD90) : le lead
        n'a JAMAIS `06…` en base, et `enregistrer_consentement_lead` inscrit
        `lead.telephone`. On relit donc l'identifiant sur le lead créé plutôt
        que la graphie postée.
        """
        resp = self._api().post(LEADS_URL, {
            'nom': 'Benali', 'prenom': 'Aziz', 'telephone': '0600000011',
        }, format='json')
        self.assertIn(resp.status_code, (200, 201), resp.data)

        lead = Lead.objects.get(company=self.company, nom='Benali')
        entrees = self._entrees(lead.telephone)
        self.assertEqual(len(entrees), 1, entrees)
        entree = entrees[0]
        self.assertEqual(entree.purpose,
                         leads_consentement.CONSENT_PURPOSE_PROSPECTION)
        self.assertIn(leads_consentement.CONSENT_SOURCE_SAISIE_MANUELLE, entree.source)
        self.assertIn('loi 09-08 art. 5', entree.source)
        # Aucune case cochée : on ne fabrique pas un consentement.
        self.assertFalse(entree.granted)

    def test_le_lead_est_cree_meme_si_le_registre_echoue(self):
        """Un registre en panne ne fait jamais perdre une demande client.

        Le numéro est relu sous sa forme CANONIQUE (`212…`, posée par
        `LeadSerializer.validate_telephone` avant CAD90) : c'est elle qui est
        en base, jamais la graphie `06…` postée.
        """
        with patch.object(leads_consentement, 'enregistrer_consentement_lead',
                          side_effect=RuntimeError('registre indisponible')):
            resp = self._api().post(LEADS_URL, {
                'nom': 'Chraibi', 'telephone': '0600000012',
            }, format='json')
        self.assertIn(resp.status_code, (200, 201), resp.data)
        lead = Lead.objects.filter(
            company=self.company, nom='Chraibi').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.telephone, '212600000012')
        self.assertEqual(self._entrees(lead.telephone), [])

    def test_lead_sans_email_ni_telephone_n_ecrit_rien(self):
        """Sans identifiant de personne, il n'y a rien à inscrire."""
        lead = Lead.objects.create(company=self.company, nom='Anonyme')
        self.assertIsNone(leads_consentement.enregistrer_base_legale_lead(
            lead, source=leads_consentement.CONSENT_SOURCE_SAISIE_MANUELLE,
            base_legale=leads_consentement.BASE_LEGALE_SOLLICITATION))


class BasesLegalesTests(_Base):
    slug = 'cad90-bases'

    def test_donnees_non_collectees_citent_art5_3_et_le_decret(self):
        lead = Lead.objects.create(
            company=self.company, nom='Import', telephone='0600000013')
        leads_consentement.enregistrer_base_legale_lead(
            lead, source=leads_consentement.CONSENT_SOURCE_DOCUMENT,
            base_legale=leads_consentement.BASE_LEGALE_NON_COLLECTEE)
        entree = self._entrees('0600000013')[0]
        self.assertIn('art. 5', entree.source)
        self.assertIn('2-09-165', entree.source)

    def test_sollicitation_cite_la_relation_precontractuelle(self):
        lead = Lead.objects.create(
            company=self.company, nom='Entrant', telephone='0600000014')
        leads_consentement.enregistrer_base_legale_lead(
            lead, source=leads_consentement.CONSENT_SOURCE_WHATSAPP_ENTRANT,
            base_legale=leads_consentement.BASE_LEGALE_SOLLICITATION)
        entree = self._entrees('0600000014')[0]
        self.assertIn('précontractuelle', entree.source)
        self.assertIn(leads_consentement.CONSENT_SOURCE_WHATSAPP_ENTRANT, entree.source)

    def test_la_source_tient_dans_la_colonne(self):
        """`ConsentRecord.source` fait 120 caractères : rien n'est tronqué
        en silence au point de perdre la base légale."""
        for base in (leads_consentement.BASE_LEGALE_NON_COLLECTEE,
                     leads_consentement.BASE_LEGALE_SOLLICITATION):
            for source in (leads_consentement.CONSENT_SOURCE_SAISIE_MANUELLE,
                           leads_consentement.CONSENT_SOURCE_META_LEAD_ADS,
                           leads_consentement.CONSENT_SOURCE_WHATSAPP_ENTRANT,
                           leads_consentement.CONSENT_SOURCE_DOCUMENT):
                self.assertLessEqual(len(f'{source} — {base}'), 120,
                                     f'{source} / {base}')

    def test_isolation_entre_societes(self):
        autre, _ = Company.objects.get_or_create(
            slug='cad90-autre', defaults={'nom': 'cad90-autre'})
        CompanyProfile.objects.get_or_create(company=autre)
        lead = Lead.objects.create(
            company=autre, nom='Voisin', telephone='0600000015')
        leads_consentement.enregistrer_base_legale_lead(
            lead, source=leads_consentement.CONSENT_SOURCE_SAISIE_MANUELLE,
            base_legale=leads_consentement.BASE_LEGALE_SOLLICITATION)
        self.assertEqual(self._entrees('0600000015'), [])
        self.assertEqual(ConsentRecord.objects.filter(
            company=autre, subject_identifier='0600000015').count(), 1)

    def test_la_preparation_de_reactivation_trace_la_base_legale_et_ferme_le_palier_2(self):
        """CADV109. Mutant : ignorer l'interrupteur ⇒ les 3 liens sortent
        interrupteur faux et échoue."""
        trois = Lead.objects.bulk_create([
            Lead(company=self.company, nom=f'K6 {rang}', stage=stages.COLD,
                 source=Lead.Source.META_LEAD_ADS, telephone=f'21260000002{rang}')
            for rang in range(3)])
        oppose = Lead.objects.bulk_create([Lead(
            company=self.company, nom='Opposé', stage=stages.COLD, ne_plus_contacter=True,
            source=Lead.Source.META_LEAD_ADS, telephone='212600000029')])[0]
        ids = [lead.pk for lead in trois]
        Lead.objects.filter(pk__in=ids + [oppose.pk]).update(
            date_creation=datetime.datetime(2026, 6, 15, 10, 0, tzinfo=horaires.CASABLANCA))
        marqueur = 'Réactivation K6 palier 2 — message préparé'

        def preparer(interrupteur, plateforme='Meta'):
            with override_settings(REACTIVATION_K6_PALIER2=interrupteur):
                return apply_bulk_action(
                    company=self.company, user=self.acteur, lead_ids=ids + [oppose.pk],
                    op='prepare_whatsapp',
                    params={'seau': 'k6_p2', 'template_cle': 'reactivation_k6_p2',
                            'plateforme': plateforme})

        def lignes():
            return LeadActivity.objects.filter(company=self.company, body=marqueur).count()

        # ERR-CADV-REACTIVATION-BLANC — « [plateforme] » non complété : jamais de
        # lien, jamais de trace ; chaque lead sort avec le blanc nommé.
        sans_blanc = preparer(True, plateforme='')
        self.assertEqual(sans_blanc['queue'], [])
        self.assertEqual({s['id']: s['reason'] for s in sans_blanc['skipped']},
                         {**dict.fromkeys(ids, 'à compléter : [plateforme]'),
                          oppose.pk: 'ne plus contacter'})
        self.assertEqual(lignes(), 0)
        self.assertFalse(ConsentRecord.objects.filter(company=self.company).exists())

        ferme = preparer(False)
        self.assertEqual(ferme['queue'], [])
        self.assertEqual({s['id']: s['reason'] for s in ferme['skipped']},
                         {**dict.fromkeys(ids, 'palier2_ferme'), oppose.pk: 'ne plus contacter'})
        self.assertEqual(lignes(), 0)
        self.assertFalse(ConsentRecord.objects.filter(company=self.company).exists())

        ouvert = preparer(True)
        self.assertEqual([q['lead_id'] for q in ouvert['queue']], ids)
        for ligne in ouvert['queue']:
            self.assertIn('wa.me', ligne['wa_url'])
            self.assertIn('STOP', ligne['wa_url'])
            self.assertIn('Meta', ligne['wa_url'])
            self.assertNotIn('plateforme', ligne['wa_url'])
        self.assertEqual([s['id'] for s in ouvert['skipped']], [oppose.pk])
        for lead in trois:
            self.assertEqual(LeadActivity.objects.filter(lead=lead, body=marqueur).count(), 1)
            entree, = self._entrees(lead.telephone)
            self.assertFalse(entree.granted)
            self.assertIn('K6 palier 2', entree.source)
            self.assertIn(leads_consentement.BASE_LEGALE_SOLLICITATION, entree.source)
        self.assertEqual(_preparations_whatsapp_du_jour(self.company, self.acteur), 3)

        # Rejouer le même jour rend les liens sans rien ajouter ; refermer n'écrit rien.
        self.assertEqual(len(preparer(True)['queue']), 3)
        self.assertEqual(preparer(False)['queue'], [])
        self.assertEqual(lignes(), 3)
        self.assertEqual(ConsentRecord.objects.filter(company=self.company).count(), 3)

    def test_la_preparation_de_reactivation_refuse_un_seau_inconnu_et_un_lead_hors_seau(self):
        """CADV109 — seau inconnu : 400 (ValueError) ; un lead qui n'est pas dans le
        seau demandé sort avec son motif."""
        lead = Lead.objects.bulk_create([Lead(
            company=self.company, nom='Vivant', telephone='212600000030')])[0]
        with self.assertRaisesMessage(ValueError, 'Seau de réactivation inconnu.'):
            apply_bulk_action(company=self.company, user=self.acteur, lead_ids=[lead.pk],
                              op='prepare_whatsapp', params={'seau': 'k9'})
        resultat = apply_bulk_action(
            company=self.company, user=self.acteur, lead_ids=[lead.pk],
            op='prepare_whatsapp', params={'seau': 'k5', 'body': 'Bonjour.'})
        self.assertEqual(resultat['queue'], [])
        self.assertEqual(resultat['skipped'][0]['reason'], 'hors seau')
