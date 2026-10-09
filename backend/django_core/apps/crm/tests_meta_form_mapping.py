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
        # CIQ407 (D-CIQ-19) — une tranche OUVERTE n'est jamais un montant :
        # la facture reste vide, la tranche est déclarée telle quelle.
        lead = self._create(leadgen_id='9002', phone='+212600000102',
                            facture='plus_de_4000dh')
        self.assertIsNone(lead.facture_hiver)
        self.assertEqual(lead.facture_tranche_declaree, {
            'min_mad': 4000, 'max_mad': None, 'libelle': 'plus de 4000dh',
            'source': 'meta'})

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


class MetaFormEntrepriseCIQ407Tests(TestCase):
    """CIQ407 (D-CIQ-19) — formulaire « pour mon entreprise » : une tranche
    ouverte n'est jamais un montant, l'industrie n'est plus rangée en
    commerce, raison sociale et fonction recopiées en remplissage."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor CIQ407', slug='taqinor-ciq407')
        self.n = 0

    def _create(self, *, install='pour_mon_entreprise',
                facture='plus_de_4000dh', extra=()):
        self.n += 1
        rows = _field_data(phone=f'+2126000004{self.n:02d}',
                           install=install, facture=facture,
                           quand=None) + list(extra)
        return create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id=f'94{self.n:02d}',
            field_data=rows, form_id='FORM-PRO')

    def test_tranche_fermee_pro_garde_le_milieu_et_pose_la_tranche(self):
        lead = self._create(facture='entre_1000_et_2000_dh')
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation, 'commercial')
        self.assertEqual(lead.facture_hiver, Decimal('1500'))
        self.assertEqual(lead.facture_tranche_declaree['min_mad'], 1000)
        self.assertEqual(lead.facture_tranche_declaree['max_mad'], 2000)
        self.assertEqual(lead.facture_tranche_declaree['source'], 'meta')

    def test_tranche_ouverte_aucun_montant(self):
        lead = self._create()
        lead.refresh_from_db()
        self.assertIsNone(lead.facture_hiver)
        self.assertEqual(lead.facture_tranche_declaree['min_mad'], 4000)
        self.assertIsNone(lead.facture_tranche_declaree['max_mad'])
        note = LeadActivity.objects.get(
            lead=lead, body__startswith='[Formulaire Meta]')
        self.assertNotIn('pré-remplie à', note.body)

    def test_industrie_avant_entreprise(self):
        for reponse in ('entreprise_industrielle',
                        'usine_/_entreprise_industrielle',
                        'local_industriel', 'atelier'):
            lead = self._create(install=reponse)
            self.assertEqual(lead.type_installation, 'industriel', reponse)

    def test_clinique_commercial_categorie_sante(self):
        lead = self._create(install='clinique')
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation, 'commercial')
        self.assertEqual(lead.categorie_commerciale, 'sante')

    def test_ambigu_aucun_type(self):
        lead = self._create(install='maison_ou_entreprise')
        self.assertFalse(lead.type_installation)
        lead = self._create(install='entrepot')
        self.assertFalse(lead.type_installation)

    def test_mot_entier_seulement(self):
        from apps.crm.services import _meta_type_installation
        self.assertEqual(_meta_type_installation('localisation'), '')
        self.assertEqual(_meta_type_installation('cafetiere'), '')

    def test_company_name_et_job_title(self):
        lead = self._create(extra=[
            {'name': 'company_name', 'values': ['Hôtel Atlas SARL']},
            {'name': 'job_title', 'values': ['Directeur']}])
        lead.refresh_from_db()
        self.assertEqual(lead.societe, 'Hôtel Atlas SARL')
        self.assertEqual(lead.fonction_contact, 'Directeur')

    def test_residentiel_form_4_inchange(self):
        lead = self._create(install='sur_ma_villa',
                            facture='entre_1000_dh_à_2000_dh')
        lead.refresh_from_db()
        self.assertEqual(lead.type_installation, 'residentiel')
        self.assertEqual(lead.facture_hiver, Decimal('1500'))
        self.assertIsNone(lead.facture_tranche_declaree)


# ── Formulaire TQ-F6-HI-2610 (plan pub octobre 2026, `4_MESSAGES.md` §1) ────
# Libellés BILINGUES (FR / darija) : Meta renvoie la question et l'option en
# snake_case du libellé complet, arabe compris. Le mapping lit les mots FR.
Q6_LOGEMENT = 'votre_logement_/_الدار_ديالك'
Q6_VOUS = 'vous_êtes_/_واش_نتا_مول_الدار_ولا_كاري_?'
Q6_FACTURE = "votre_facture_d'électricité,_par_mois_/_شحال_الفاتورة_ديال_الضو_فالشهر_?"
Q6_QUAND = 'quand_voulez-vous_installer_?_/_وقتاش_بغيتي_تركّب_?'
Q6_CONTACT = 'comment_préférez-vous_être_contacté_?_/_كيفاش_بغيتي_نتواصلو_معاك_?'


def _field_data_f6(*, phone, logement='villa_ou_maison_individuelle_/_فيلا_ولا_دار',
                   vous='propriétaire_/_مول_الدار', facture='1_000-2_000_dh',
                   quand='ce_mois-ci', contact='appel_/_عيطو_ليا'):
    rows = [
        {'name': 'full_name', 'values': ['Salma Testeuse']},
        {'name': 'phone_number', 'values': [phone]},
        {'name': 'city', 'values': ['Bouskoura']},
        {'name': Q6_LOGEMENT, 'values': [logement]},
        {'name': Q6_VOUS, 'values': [vous]},
        {'name': Q6_FACTURE, 'values': [facture]},
        {'name': Q6_QUAND, 'values': [quand]},
        {'name': Q6_CONTACT, 'values': [contact]},
    ]
    return rows


class MetaFormF6MappingTests(TestCase):
    """Les 5 questions du formulaire TQ-F6 atterrissent dans les champs
    structurés ; une tranche ouverte vers le bas (« moins de 500 DH ») n'est
    JAMAIS un montant ; rien n'est inventé pour un libellé inconnu."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor F6', slug='taqinor-f6')
        self.n = 0

    def _create(self, **kw):
        self.n += 1
        return create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id=f'f6-{self.n}',
            field_data=_field_data_f6(phone=f'+2126000002{self.n:02d}', **kw),
            form_id='TQ-F6-HI-2610')

    def test_villa_proprietaire_facture_fermee_ce_mois_appel(self):
        lead = self._create()
        self.assertEqual(lead.type_installation,
                         Lead.TypeInstallation.RESIDENTIEL)
        self.assertEqual(lead.ownership, Lead.Ownership.PROPRIETAIRE)
        self.assertEqual(lead.facture_hiver, Decimal('1500'))
        self.assertIsNone(lead.facture_tranche_declaree)
        self.assertEqual(lead.priorite, Lead.Priorite.HAUTE)
        self.assertEqual(lead.project_timeline, Lead.ProjectTimeline.IMMEDIAT)
        self.assertEqual(lead.contact_preference,
                         Lead.ContactPreference.PHONE_OK)
        self.assertIsNotNone(lead.contact_preference_set_at)

    def test_local_pro_ou_usine_part_en_file_pro(self):
        lead = self._create(logement='local_professionnel_ou_usine_/_محل_ولا_معمل')
        self.assertEqual(lead.type_installation,
                         Lead.TypeInstallation.INDUSTRIEL)

    def test_appartement_reste_residentiel(self):
        lead = self._create(logement='appartement_/_شقة')
        self.assertEqual(lead.type_installation,
                         Lead.TypeInstallation.RESIDENTIEL)

    def test_locataire(self):
        lead = self._create(vous='locataire_/_كاري')
        self.assertEqual(lead.ownership, Lead.Ownership.LOCATAIRE)

    def test_moins_de_500_vaut_la_tranche_0_500(self):
        # « Moins de 500 DH » n'est JAMAIS 500 DH : plancher 0, milieu 250
        # (même convention que les autres tranches fermées, verbatim en note).
        lead = self._create(facture='moins_de_500_dh')
        self.assertEqual(lead.facture_hiver, Decimal('250'))
        self.assertIsNone(lead.facture_tranche_declaree)

    def test_tranche_500_1000_donne_le_milieu(self):
        lead = self._create(facture='500-1_000_dh')
        self.assertEqual(lead.facture_hiver, Decimal('750'))

    def test_plus_de_4000_reste_ouverte(self):
        lead = self._create(facture='plus_de_4_000_dh')
        self.assertIsNone(lead.facture_hiver)
        self.assertEqual(lead.facture_tranche_declaree['min_mad'], 4000)
        self.assertIsNone(lead.facture_tranche_declaree['max_mad'])

    def test_je_compare_seulement_est_basse_et_plus_tard(self):
        lead = self._create(quand='je_compare_seulement')
        # À la CRÉATION la priorité déclarée s'applique (comme « je me renseigne »
        # dans FORM-4.0) ; « jamais de downgrade » ne vaut que pour l'enrichissement.
        self.assertEqual(lead.priorite, Lead.Priorite.BASSE)
        self.assertEqual(lead.project_timeline,
                         Lead.ProjectTimeline.PLUS_TARD)

    def test_dans_1_a_3_mois(self):
        lead = self._create(quand='dans_1_à_3_mois')
        self.assertEqual(lead.project_timeline,
                         Lead.ProjectTimeline.MOINS_3_MOIS)
        self.assertEqual(lead.priorite, Lead.Priorite.NORMALE)

    def test_whatsapp_prefere(self):
        lead = self._create(contact='whatsapp_/_واتساب')
        self.assertEqual(lead.contact_preference,
                         Lead.ContactPreference.WHATSAPP_ONLY)

    def test_preference_existante_jamais_ecrasee(self):
        lead = self._create()
        lead.contact_preference = Lead.ContactPreference.WHATSAPP_ONLY
        lead.ownership = Lead.Ownership.LOCATAIRE
        lead.save(update_fields=['contact_preference', 'ownership'])
        # Rejeu du même leadgen_id (retry Meta) : enrichissement sans écrasement.
        again = create_lead_from_meta_lead_ads(
            company=self.company, leadgen_id='f6-1',
            field_data=_field_data_f6(phone='+212600000201'),
            form_id='TQ-F6-HI-2610')
        self.assertEqual(again.pk, lead.pk)
        again.refresh_from_db()
        self.assertEqual(again.contact_preference,
                         Lead.ContactPreference.WHATSAPP_ONLY)
        self.assertEqual(again.ownership, Lead.Ownership.LOCATAIRE)
