"""Quote-journey — le webhook du site persiste le questionnaire pro/agricole.

Couvre :
  - Le bug 'professionnel' : le mode pro du site (LEAD_MODES) obtient enfin
    un type_installation (industriel) au lieu d'être silencieusement jeté ;
  - Le RÉEMPLOI des colonnes Lead existantes (HMT/débit/CV pompe → pompe_*,
    kWh/MAD pro → bill_kwh/facture_hiver) — seul le reste va dans
    web_questionnaire (clés snake_case, vocabulaire etude_params) ;
  - estimateShown → web_estimate re-whitelisté CÔTÉ SERVEUR (clés inconnues
    et valeurs non scalaires jetées) ;
  - UNE note chatter automatique FR résumant le questionnaire à la création ;
  - Un payload SANS les nouveaux champs → comportement identique à avant
    (dicts vides, aucune note questionnaire).
"""

import json

from django.test import TestCase, override_settings
from django.urls import reverse

from authentication.models import Company

from .models import Lead, LeadActivity, WebsiteLeadPayload

SECRET = 'test-secret-web-questionnaire'


def payload_site(**extra):
    """Charge utile de la forme émise par apps/web (capture-lead.ts)."""
    base = {
        'fullName': 'Youssef El Amrani',
        'phoneE164': '+212661000222',
        'whatsappOptIn': True,
        'city': 'Meknès',
        'consent': True,
        'qualified': True,
        'page': '/devis/mon-toit',
    }
    base.update(extra)
    return base


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class WebQuestionnaireWebhookTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='QJ Web Co', slug='qj-web-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    # ── (a) Bug confirmé : le mode 'professionnel' était jeté ──────────────
    def test_mode_professionnel_donne_un_type_installation(self):
        res = self.post(payload_site(mode='professionnel'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.type_installation, 'industriel')

    def test_payload_professionnel_complet_reemploi_des_colonnes(self):
        res = self.post(payload_site(
            mode='professionnel',
            raisonSociale='Atlas Plast',
            facilityType='usine',
            siteCount='2-5',
            tensionRaccordement='mt',
            puissanceKva=250,
            activityProfile='day',
            surfaceType='bac_acier',
            surfaceM2=800,
            hasGenerator=True,
            proMonthlyKwh=12000,
            proMonthlyMad=15000,
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        # Champs pro existants inchangés.
        self.assertEqual(lead.type_installation, 'industriel')
        self.assertEqual(lead.societe, 'Atlas Plast')
        self.assertEqual(lead.facility_type, 'usine')
        self.assertEqual(lead.site_count, '2-5')
        # Réemploi des colonnes énergie existantes.
        self.assertEqual(str(lead.bill_kwh), '12000.00')
        self.assertEqual(str(lead.facture_hiver), '15000.00')
        # Le reste (sans colonne) atterrit dans web_questionnaire.
        self.assertEqual(lead.web_questionnaire, {
            'tension_raccordement': 'mt',
            'puissance_kva': 250.0,
            'activity_profile': 'day',
            'surface_type': 'bac_acier',
            'surface_m2': 800.0,
            'has_generator': True,
        })
        # Note chatter créée (résumé FR, réponses fournies uniquement).
        note = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Questionnaire web').first()
        self.assertIsNotNone(note)
        self.assertEqual(note.company, self.company)
        self.assertIsNone(note.user)
        self.assertIn('(industriel)', note.body)
        self.assertIn('raccordement MT', note.body)
        self.assertIn('250 kVA', note.body)
        self.assertIn('groupe électrogène présent', note.body)

    def test_bill_kwh_explicite_prime_sur_pro_monthly_kwh(self):
        """billKwh/factureHiver explicites priment ; la réponse pro reste
        alors visible dans web_questionnaire (jamais perdue)."""
        res = self.post(payload_site(
            mode='professionnel',
            billKwh='420', factureHiver='1850.50',
            proMonthlyKwh=12000, proMonthlyMad=15000,
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(str(lead.bill_kwh), '420.00')
        self.assertEqual(str(lead.facture_hiver), '1850.50')
        self.assertEqual(lead.web_questionnaire, {
            'pro_monthly_kwh': 12000.0,
            'pro_monthly_mad': 15000.0,
        })

    # ── (b) Agricole : colonnes pompage + web_questionnaire + note ─────────
    def test_payload_agricole_colonnes_pompage_questionnaire_et_note(self):
        res = self.post(payload_site(
            mode='agricole',
            waterSource='forage',
            profondeurM=45,
            hmtM=60,
            debitM3h=12,
            besoinM3j=84,
            heuresPompage=7,
            irrigation='goutte',
            culture='olivier',
            surfaceHa=5,
            pompeActuelle='diesel',
            pompeCvActuelle=7.5,
            fuelSpendMad=2500,
            estimateShown={'pompeCv': 10, 'champKwc': 10.3, 'm3Jour': 84},
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.type_installation, 'agricole')
        # Réemploi des colonnes pompage existantes (jamais dupliquées).
        self.assertEqual(str(lead.pompe_hmt_m), '60.00')
        self.assertEqual(str(lead.pompe_debit_m3h), '12.00')
        self.assertEqual(str(lead.pompe_cv), '7.50')
        self.assertEqual(lead.web_questionnaire, {
            'water_source': 'forage',
            'profondeur_m': 45.0,
            'besoin_m3j': 84.0,
            'heures_pompage': 7.0,
            'irrigation': 'goutte',
            'culture': 'olivier',
            'surface_ha': 5.0,
            'pompe_actuelle': 'diesel',
            'fuel_spend_mad': 2500.0,
        })
        self.assertEqual(lead.web_estimate,
                         {'pompeCv': 10, 'champKwc': 10.3, 'm3Jour': 84})
        # UNE note chatter, résumé complet (y compris les valeurs mappées
        # sur colonnes : HMT, débit, CV) + estimation montrée.
        notes = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Questionnaire web')
        self.assertEqual(notes.count(), 1)
        body = notes.first().body
        self.assertIn('(agricole)', body)
        self.assertIn('forage', body)
        self.assertIn('profondeur 45 m', body)
        self.assertIn('HMT 60 m', body)
        self.assertIn('12 m³/h', body)
        self.assertIn('besoin 84 m³/j', body)
        self.assertIn('7 h/j', body)
        self.assertIn('goutte-à-goutte', body)
        self.assertIn('culture olivier', body)
        self.assertIn('pompe diesel 7,5 CV', body)
        self.assertIn('carburant 2 500 MAD/mois', body)
        self.assertIn('Estimation montrée', body)
        self.assertIn('pompe 10 CV', body)
        self.assertIn('champ 10,3 kWc', body)
        self.assertIn('84 m³/j', body)

    # ── (c) estimateShown re-whitelisté côté serveur ───────────────────────
    def test_estimate_shown_whitelist_serveur(self):
        res = self.post(payload_site(
            mode='residentiel',
            estimateShown={
                'kwc': 8.2,
                'prodKwh': 13500,
                'paybackLabel': '4 à 6 ans',
                'evil': 'dropped',            # clé inconnue → jetée
                'is_admin': True,             # booléen → jeté
                'nested': {'a': 1},           # non scalaire → jeté
                'listy': [1, 2],              # non scalaire → jeté
                'tauxAutoconso': None,        # None → jeté
            },
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.web_estimate, {
            'kwc': 8.2,
            'prodKwh': 13500,
            'paybackLabel': '4 à 6 ans',
        })

    def test_nb_panneaux_et_bassin_traversent_la_whitelist(self):
        """WJ124 — le tunnel ANNONCE « 12,4 kWc · 28 panneaux » et un bassin
        recommandé ; les deux clés (`nbPanneaux`, `bassinM3`) sont émises par
        le site (lead.ts:ESTIMATE_SHOWN_NUMERIC_KEYS) et étaient jetées ici :
        le commercial recomptait les modules à la main."""
        res = self.post(payload_site(
            mode='agricole',
            estimateShown={'champKwc': 12.4, 'nbPanneaux': 28,
                           'bassinM3': 45, 'm3Jour': 45},
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.web_estimate, {
            'champKwc': 12.4, 'nbPanneaux': 28, 'bassinM3': 45, 'm3Jour': 45,
        })

    def test_valeurs_invalides_ignorees_jamais_de_crash(self):
        res = self.post(payload_site(
            mode='agricole',
            waterSource='ocean',        # hors choix → jeté
            heuresPompage=99,           # > 24 → jeté
            puissanceKva='abc',         # non numérique → jeté
            profondeurM=-3,             # négatif → jeté
            estimateShown='pas-un-dict',
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.type_installation, 'agricole')
        self.assertEqual(lead.web_questionnaire, {})
        self.assertEqual(lead.web_estimate, {})

    # ── (d) Sans les nouveaux champs : comportement identique à avant ──────
    def test_payload_sans_nouveaux_champs_comportement_inchange(self):
        res = self.post(payload_site(mode='residentiel'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.type_installation, 'residentiel')
        self.assertEqual(lead.web_questionnaire, {})
        self.assertEqual(lead.web_estimate, {})
        # Aucune note questionnaire — seule l'activité de création habituelle.
        self.assertFalse(LeadActivity.objects.filter(
            lead=lead, body__startswith='Questionnaire web').exists())
        self.assertTrue(LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.CREATION).exists())


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class TrousDeMappingCombles(TestCase):
    """Clés émises par le site qui n'atterrissaient nulle part, ou dont il faut
    verrouiller l'atterrissage dans le blob `web_questionnaire`."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJ Web Co 2', slug='qj-web-co-2')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_region_agricole_persistee_et_resumee(self):
        """WJ124 — `regionAgricole` était émise par le site et jetée par le
        webhook (aucune colonne, absente de la whitelist)."""
        res = self.post(payload_site(
            mode='agricole', regionAgricole='souss-massa', culture='olivier'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.web_questionnaire.get('region_agricole'),
                         'souss-massa')
        note = LeadActivity.objects.filter(
            lead=lead, body__startswith='Questionnaire web').first()
        self.assertIn('région souss-massa', note.body)

    def test_region_agricole_hors_liste_ignoree(self):
        res = self.post(payload_site(
            mode='agricole', regionAgricole='atlantide', culture='olivier'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertNotIn('region_agricole', lead.web_questionnaire)

    def test_cles_gatees_atterrissent_toutes_dans_le_blob(self):
        """Clés déjà acceptées mais rarement émises : on verrouille qu'elles
        arrivent bien TOUTES dans `web_questionnaire` quand le site les
        envoie (industriel v2 + surface commerciale + pompage)."""
        res = self.post(payload_site(
            mode='professionnel',
            equipes='3x8', weekend=True, cosPhiConnu=0.92,
            hasGenerator=True, groupeKva=400, dieselDhMois=18000,
            surfaceToitureM2=2600, surfaceM2=3100, heuresPompage=7,
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.web_questionnaire, {
            'equipes': '3x8',
            'weekend': True,
            'cos_phi_connu': 0.92,
            'has_generator': True,
            'groupe_kva': 400.0,
            'diesel_dh_mois': 18000.0,
            'surface_toiture_m2': 2600.0,
            'surface_m2': 3100.0,
            'heures_pompage': 7.0,
        })

    def test_cle_inconnue_survit_dans_le_payload_brut(self):
        """Une clé que le backend ne connaît pas encore n'est jamais perdue :
        elle reste dans `WebsiteLeadPayload.payload` (règle « jamais perdre un
        lead »), sans polluer le blob questionnaire."""
        res = self.post(payload_site(
            mode='agricole', cleTotalementInconnue='valeur-du-futur'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertNotIn('cle_totalement_inconnue', lead.web_questionnaire)
        raw = WebsiteLeadPayload.objects.get(lead=lead)
        self.assertEqual(raw.payload['cleTotalementInconnue'],
                         'valeur-du-futur')


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class LBackTunnelEquipementsWebhookTests(TestCase):
    """L-BACK (24/08/2026) — le tunnel web reprend occupation_jour + les 7
    champs équipements (script d'appel) : ce sont des colonnes ``crm.Lead``
    DÉDIÉES (L4/L-BACK), jamais laissées dans le blob ``web_questionnaire``."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJ Web Co 3', slug='qj-web-co-3')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_payload_complet_atterrit_sur_les_colonnes_dediees(self):
        res = self.post(payload_site(
            occupation_jour='partiel',
            equip_piscine=True, equip_piscine_pompe_kw=1.1,
            equip_voiture_electrique=True, equip_ve_km_semaine=150,
            equip_clim=True, equip_clim_pieces=3,
            equip_chauffe_eau_electrique=False,
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.occupation_jour, 'partiel')
        self.assertTrue(lead.equip_piscine)
        self.assertEqual(str(lead.equip_piscine_pompe_kw), '1.10')
        self.assertTrue(lead.equip_voiture_electrique)
        self.assertEqual(lead.equip_ve_km_semaine, 150)
        self.assertTrue(lead.equip_clim)
        self.assertEqual(lead.equip_clim_pieces, 3)
        self.assertFalse(lead.equip_chauffe_eau_electrique)
        # Aucune de ces 8 réponses ne pollue web_questionnaire.
        self.assertEqual(lead.web_questionnaire, {})

    def test_absence_des_cles_ne_touche_rien(self):
        """Comportement inchangé pour un payload sans ces 8 clés — même
        style tolérant que le reste du webhook (jamais un défaut inventé)."""
        res = self.post(payload_site(mode='residentiel'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.occupation_jour)
        self.assertIsNone(lead.equip_piscine)
        self.assertIsNone(lead.equip_piscine_pompe_kw)
        self.assertIsNone(lead.equip_voiture_electrique)
        self.assertIsNone(lead.equip_ve_km_semaine)
        self.assertIsNone(lead.equip_clim)
        self.assertIsNone(lead.equip_clim_pieces)
        self.assertIsNone(lead.equip_chauffe_eau_electrique)

    def test_valeur_choice_invalide_est_ignoree(self):
        """``occupation_jour`` hors vocabulaire (present/absent/partiel) est
        silencieusement ignorée — jamais une erreur 4xx, jamais un défaut."""
        res = self.post(payload_site(occupation_jour='peut-etre'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.occupation_jour)

    def test_seule_la_moitie_kw_sans_bool_reste_coherente(self):
        """``equip_piscine_pompe_kw`` seule (sans le booléen) est acceptée
        telle quelle sur la colonne — c'est ``courbes_journalieres`` qui
        exige les DEUX pour composer une couche, pas le webhook."""
        res = self.post(payload_site(equip_piscine_pompe_kw=1.5))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.equip_piscine)
        self.assertEqual(str(lead.equip_piscine_pompe_kw), '1.50')
