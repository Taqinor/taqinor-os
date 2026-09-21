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
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from core.models import ConsentRecord

from apps.crm import services
from apps.crm.models import Lead
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
                         services.CONSENT_PURPOSE_PROSPECTION)
        self.assertIn(services.CONSENT_SOURCE_SAISIE_MANUELLE, entree.source)
        self.assertIn('loi 09-08 art. 5', entree.source)
        # Aucune case cochée : on ne fabrique pas un consentement.
        self.assertFalse(entree.granted)

    def test_le_lead_est_cree_meme_si_le_registre_echoue(self):
        """Un registre en panne ne fait jamais perdre une demande client.

        Le numéro est relu sous sa forme CANONIQUE (`212…`, posée par
        `LeadSerializer.validate_telephone` avant CAD90) : c'est elle qui est
        en base, jamais la graphie `06…` postée.
        """
        with patch.object(services, 'enregistrer_consentement_lead',
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
        self.assertIsNone(services.enregistrer_base_legale_lead(
            lead, source=services.CONSENT_SOURCE_SAISIE_MANUELLE,
            base_legale=services.BASE_LEGALE_SOLLICITATION))


class BasesLegalesTests(_Base):
    slug = 'cad90-bases'

    def test_donnees_non_collectees_citent_art5_3_et_le_decret(self):
        lead = Lead.objects.create(
            company=self.company, nom='Import', telephone='0600000013')
        services.enregistrer_base_legale_lead(
            lead, source=services.CONSENT_SOURCE_DOCUMENT,
            base_legale=services.BASE_LEGALE_NON_COLLECTEE)
        entree = self._entrees('0600000013')[0]
        self.assertIn('art. 5', entree.source)
        self.assertIn('2-09-165', entree.source)

    def test_sollicitation_cite_la_relation_precontractuelle(self):
        lead = Lead.objects.create(
            company=self.company, nom='Entrant', telephone='0600000014')
        services.enregistrer_base_legale_lead(
            lead, source=services.CONSENT_SOURCE_WHATSAPP_ENTRANT,
            base_legale=services.BASE_LEGALE_SOLLICITATION)
        entree = self._entrees('0600000014')[0]
        self.assertIn('précontractuelle', entree.source)
        self.assertIn(services.CONSENT_SOURCE_WHATSAPP_ENTRANT, entree.source)

    def test_la_source_tient_dans_la_colonne(self):
        """`ConsentRecord.source` fait 120 caractères : rien n'est tronqué
        en silence au point de perdre la base légale."""
        for base in (services.BASE_LEGALE_NON_COLLECTEE,
                     services.BASE_LEGALE_SOLLICITATION):
            for source in (services.CONSENT_SOURCE_SAISIE_MANUELLE,
                           services.CONSENT_SOURCE_META_LEAD_ADS,
                           services.CONSENT_SOURCE_WHATSAPP_ENTRANT,
                           services.CONSENT_SOURCE_DOCUMENT):
                self.assertLessEqual(len(f'{source} — {base}'), 120,
                                     f'{source} / {base}')

    def test_isolation_entre_societes(self):
        autre, _ = Company.objects.get_or_create(
            slug='cad90-autre', defaults={'nom': 'cad90-autre'})
        CompanyProfile.objects.get_or_create(company=autre)
        lead = Lead.objects.create(
            company=autre, nom='Voisin', telephone='0600000015')
        services.enregistrer_base_legale_lead(
            lead, source=services.CONSENT_SOURCE_SAISIE_MANUELLE,
            base_legale=services.BASE_LEGALE_SOLLICITATION)
        self.assertEqual(self._entrees('0600000015'), [])
        self.assertEqual(ConsentRecord.objects.filter(
            company=autre, subject_identifier='0600000015').count(), 1)
