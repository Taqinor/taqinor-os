# -*- coding: utf-8 -*-
"""Mapping COMPLET des réponses d'Instant Form Meta vers les champs CRM.

Le formulaire Taqinor pose trois vraies questions de qualification (facture
moyenne / où installer / quand commencer) : elles doivent atterrir dans les
CHAMPS structurés du lead (facture_hiver, type_installation, priorite), pas
seulement nom+téléphone — et TOUTES les réponses verbatim vont dans une note
chatter idempotente. Les leads capturés AVANT ce mapping sont enrichis
(backfill) à la repasse du pull, sans jamais écraser une saisie humaine.
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.crm.models import Lead, LeadActivity
from apps.crm.services import create_lead_from_meta_lead_ads

# Clés/valeurs RÉELLES des formulaires TAQINOR FORM-4.0 (snake_case accentué,
# tel que renvoyé par le Graph API).
Q_INSTALL = 'où_souhaitez-vous_installer_votre_système_solaire_?'
Q_FACTURE = "quelle_est_votre_facture_moyenne_d'électricité_par_mois_?"
Q_QUAND = "quand_comptez-vous_commencer_l'installation_?"


def _field_data(*, nom='Amine Testeur', phone='+212600000101',
                ville='casablanca', install='sur_ma_villa',
                facture='entre_1000_dh_à_2000_dh',
                quand='le_plus_tôt_possible_(ce_mois-ci)'):
    rows = [
        {'name': 'full_name', 'values': [nom]},
        {'name': 'phone_number', 'values': [phone]},
        {'name': 'city', 'values': [ville]},
    ]
    if install is not None:
        rows.append({'name': Q_INSTALL, 'values': [install]})
    if facture is not None:
        rows.append({'name': Q_FACTURE, 'values': [facture]})
    if quand is not None:
        rows.append({'name': Q_QUAND, 'values': [quand]})
    return rows


class MetaFormMappingTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Mapping', slug='taqinor-mapping')

    def _create(self, leadgen_id='9001', **kw):
        return create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id=leadgen_id,
            field_data=_field_data(**kw), form_id='FORM-4.0')

    def test_full_form_lands_in_structured_fields(self):
        lead = self._create()
        self.assertEqual(lead.facture_hiver, Decimal('1500'))
        self.assertEqual(
            lead.type_installation, Lead.TypeInstallation.RESIDENTIEL)
        self.assertEqual(lead.priorite, Lead.Priorite.HAUTE)
        self.assertEqual(lead.ville, 'casablanca')
        # Le numéro sert aussi de lien wa.me pour la première touche.
        self.assertEqual(lead.whatsapp, lead.telephone)

    def test_open_range_uses_declared_bound_never_invents(self):
        lead = self._create(leadgen_id='9002', phone='+212600000102',
                            facture='plus_de_4000dh')
        self.assertEqual(lead.facture_hiver, Decimal('4000'))

    def test_entreprise_maps_commercial_and_renseigne_basse(self):
        lead = self._create(leadgen_id='9003', phone='+212600000103',
                            install='pour_mon_entreprise',
                            quand='je_me_renseigne_seulement')
        self.assertEqual(
            lead.type_installation, Lead.TypeInstallation.COMMERCIAL)
        self.assertEqual(lead.priorite, Lead.Priorite.BASSE)

    def test_verbatim_note_created_once(self):
        lead = self._create(leadgen_id='9004', phone='+212600000104')
        notes = LeadActivity.objects.filter(
            lead=lead, body__startswith='[Formulaire Meta]')
        self.assertEqual(notes.count(), 1)
        body = notes.first().body
        # Verbatim lisible (underscores → espaces), et la provenance de
        # l'estimation documentée.
        self.assertIn('sur ma villa', body)
        self.assertIn('entre 1000 dh à 2000 dh', body)
        self.assertIn('1500', body)
        # Retry webhook (même leadgen_id) → toujours UNE seule note.
        self._create(leadgen_id='9004', phone='+212600000104')
        self.assertEqual(
            LeadActivity.objects.filter(
                lead=lead, body__startswith='[Formulaire Meta]').count(), 1)

    def test_backfill_enriches_existing_lead_without_overwriting(self):
        # Lead capturé AVANT le mapping : contact seul (le pull historique).
        lead = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='9005',
            field_data=[
                {'name': 'full_name', 'values': ['Sara Backfill']},
                {'name': 'phone_number', 'values': ['+212600000105']},
            ])
        self.assertIsNone(lead.facture_hiver)
        # Meryem a saisi un type à la main entre-temps : il doit GAGNER.
        lead.type_installation = Lead.TypeInstallation.COMMERCIAL
        lead.save(update_fields=['type_installation'])
        # Repasse du pull, cette fois avec les réponses complètes.
        enriched = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='9005',
            field_data=_field_data(nom='Sara Backfill',
                                   phone='+212600000105'),
            form_id='FORM-4.0')
        self.assertEqual(enriched.pk, lead.pk)
        enriched.refresh_from_db()
        self.assertEqual(enriched.facture_hiver, Decimal('1500'))
        self.assertEqual(enriched.priorite, Lead.Priorite.HAUTE)
        self.assertEqual(enriched.ville, 'casablanca')
        # La saisie humaine n'est jamais écrasée.
        self.assertEqual(
            enriched.type_installation, Lead.TypeInstallation.COMMERCIAL)
        # Et la note verbatim est posée au backfill, une seule fois.
        self.assertEqual(
            LeadActivity.objects.filter(
                lead=enriched,
                body__startswith='[Formulaire Meta]').count(), 1)


# AGR410 — FORM-AGRI-1 : clés PROVISOIRES (à remplacer par les clés brutes du
# premier lead réel reçu ; le formulaire et la campagne se créent à la main,
# PAUSED — règle #3, jamais par du code).
Q_SOURCE_EAU = "d'où_vient_l'eau_de_votre_exploitation_?"
Q_ENERGIE_POMPE = 'votre_pompe_actuelle_fonctionne_avec_quelle_énergie_?'
Q_SURFACE_HA = 'combien_d\'hectares_irriguez-vous_?'
Q_DEPENSE = 'combien_dépensez-vous_en_carburant_pour_la_pompe_par_mois_?'


def _field_data_agri(*, phone='+212600000201', source='un_forage',
                     energie='butane_(gaz)', surface='4_ha',
                     depense='3000_dh', facture=None):
    rows = [
        {'name': 'full_name', 'values': ['Fellah Testeur']},
        {'name': 'phone_number', 'values': [phone]},
        {'name': 'city', 'values': ['taroudant']},
        {'name': Q_SOURCE_EAU, 'values': [source]},
        {'name': Q_ENERGIE_POMPE, 'values': [energie]},
        {'name': Q_SURFACE_HA, 'values': [surface]},
        {'name': Q_DEPENSE, 'values': [depense]},
    ]
    if facture is not None:
        rows.append({'name': Q_FACTURE, 'values': [facture]})
    return rows


class MetaFormAgricoleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor Agri', slug='taqinor-agri')

    def _create(self, leadgen_id='9101', **kw):
        return create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id=leadgen_id,
            field_data=_field_data_agri(**kw), form_id='FORM-AGRI-1')

    def test_les_reponses_de_pompage_remplissent_les_colonnes(self):
        lead = self._create()
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation,
                         Lead.TypeInstallation.AGRICOLE)
        self.assertEqual(lead.source_eau, 'forage')
        self.assertEqual(lead.pompe_alim_actuelle, 'butane')
        self.assertEqual(lead.surface_irriguee_ha, Decimal('4'))
        self.assertEqual(lead.depense_carburant_mad_mois, Decimal('3000'))

    def test_une_tranche_n_est_jamais_convertie(self):
        lead = self._create(leadgen_id='9102', phone='+212600000202',
                            surface='1_à_3_ha', depense='plus_de_2000_dh')
        lead.refresh_from_db()
        self.assertIsNone(lead.surface_irriguee_ha)
        self.assertIsNone(lead.depense_carburant_mad_mois)
        note = LeadActivity.objects.get(
            lead=lead, body__startswith='[Formulaire Meta]')
        self.assertIn('1 à 3 ha', note.body)
        self.assertIn('plus de 2000 dh', note.body)

    def test_la_facture_n_est_pas_copiee_sur_un_agricole(self):
        lead = self._create(leadgen_id='9103', phone='+212600000203',
                            facture='entre_1000_dh_à_2000_dh')
        lead.refresh_from_db()
        self.assertIsNone(lead.facture_hiver)
        note = LeadActivity.objects.get(
            lead=lead, body__startswith='[Formulaire Meta]')
        self.assertIn('entre 1000 dh à 2000 dh', note.body)
        self.assertNotIn('pré-remplie', note.body)

    def test_jamais_d_ecrasement(self):
        lead = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='9104',
            field_data=[
                {'name': 'full_name', 'values': ['Fellah Deux']},
                {'name': 'phone_number', 'values': ['+212600000204']},
            ])
        lead.type_installation = Lead.TypeInstallation.RESIDENTIEL
        lead.source_eau = 'puits'
        lead.save(update_fields=['type_installation', 'source_eau'])
        create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='9104',
            field_data=_field_data_agri(phone='+212600000204'),
            form_id='FORM-AGRI-1')
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation,
                         Lead.TypeInstallation.RESIDENTIEL)
        self.assertEqual(lead.source_eau, 'puits')
        self.assertEqual(lead.pompe_alim_actuelle, 'butane')


class MetaFormAgricoleParseTests(SimpleTestCase):
    """Le parseur seul (aucun lead) : mots-clés et nombre unique."""

    def _extras(self, rows):
        from apps.crm.services import _parse_meta_form_extras
        return _parse_meta_form_extras(rows)

    def test_gazoil_est_du_diesel_pas_du_butane(self):
        extras = self._extras([{'name': Q_ENERGIE_POMPE,
                                'values': ['gazoil']}])
        self.assertEqual(extras['pompe_alim_actuelle'], 'diesel')

    def test_formulaire_residentiel_inchange(self):
        extras = self._extras(_field_data())
        self.assertNotIn('source_eau', extras)
        self.assertEqual(extras['type_installation'],
                         Lead.TypeInstallation.RESIDENTIEL)
