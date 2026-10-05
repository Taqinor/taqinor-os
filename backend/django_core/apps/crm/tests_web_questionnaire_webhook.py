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

    def test_roof_type_fabrique_du_tunnel_n_est_plus_enregistre(self):
        """QJR657 — le tunnel émet roofType='autre' pour tout visiteur non pro :
        une valeur inventée ne devient plus un « Type de toiture (site) »."""
        res = self.post(payload_site(roofType='autre'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertFalse(lead.roof_type)
        self.assertNotIn('roof_type', Lead.CHAMPS_SITE)

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
        # QJR595 — la puissance souscrite est promue vers sa colonne.
        self.assertEqual(str(lead.compteur_puissance_kva), '250.00')
        # CIQ406 — tension, type de surface et groupe électrogène quittent le
        # sac pour leurs colonnes ; tension pré-cochée (pas de tensionSource)
        # = défaut visible du site, jamais une déclaration.
        self.assertEqual(lead.tension_raccordement, 'mt')
        self.assertEqual(lead.tension_source, 'site_defaut_visible')
        self.assertEqual(lead.type_surface, 'toiture')
        self.assertEqual(lead.type_toiture, 'bac_acier')
        self.assertEqual(lead.groupe_electrogene, 'oui')
        self.assertEqual(lead.puissance_souscrite_source, 'site_web')
        # Le reste (sans colonne) atterrit dans web_questionnaire.
        self.assertEqual(lead.web_questionnaire, {
            'activity_profile': 'day',
            'surface_m2': 800.0,
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
        self.assertEqual(str(lead.pompe_actuelle_cv), '7.50')
        # AGR402 — les réponses agricoles quittent le sac pour leurs colonnes.
        self.assertEqual(lead.web_questionnaire, {})
        self.assertEqual(lead.source_eau, 'forage')
        self.assertEqual(str(lead.niveau_statique_m), '45.00')
        self.assertEqual(lead.niveau_statique_source, 'site_web')
        self.assertEqual(str(lead.besoin_eau_m3j), '84.00')
        self.assertEqual(lead.besoin_eau_source, 'site_web')
        self.assertEqual(lead.pompe_hmt_source, 'site_web')
        self.assertEqual(lead.irrigation_methode, 'goutte')
        self.assertEqual(lead.culture, 'olivier')
        self.assertEqual(str(lead.surface_irriguee_ha), '5.00')
        self.assertEqual(str(lead.depense_carburant_mad_mois), '2500.00')
        # CAD149 — les deux réponses de pompage PROMUES en colonne : elles
        # quittent le sac, exactement comme HMT/débit/CV au-dessus.
        self.assertEqual(str(lead.pompage_heures_jour), '7.0')
        self.assertEqual(lead.pompe_alim_actuelle, 'diesel')
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
        # AGR402 — promue vers sa colonne (plus dans le sac).
        self.assertEqual(lead.region_agricole, 'souss-massa')
        self.assertNotIn('region_agricole', lead.web_questionnaire)
        note = LeadActivity.objects.filter(
            lead=lead, body__startswith='Questionnaire web').first()
        self.assertIn('région souss-massa', note.body)

    def test_region_agricole_hors_liste_ignoree(self):
        res = self.post(payload_site(
            mode='agricole', regionAgricole='atlantide', culture='olivier'))
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertNotIn('region_agricole', lead.web_questionnaire)
        self.assertIsNone(lead.region_agricole)

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
        # CIQ406 — équipes, cos φ et groupe électrogène promus en colonnes ;
        # `weekend` et `surface_m2` restent au sac.
        self.assertEqual(lead.web_questionnaire, {
            'weekend': True,
            'surface_m2': 3100.0,
        })
        self.assertEqual(lead.regime_equipes, '3x8')
        self.assertEqual(str(lead.cos_phi), '0.920')
        self.assertEqual(lead.cos_phi_source, 'site_web')
        self.assertEqual(lead.groupe_electrogene, 'oui')
        self.assertEqual(str(lead.groupe_kva), '400.00')
        self.assertEqual(str(lead.groupe_depense_mad_mois), '18000.00')
        # QJR595 — la surface de toiture du client pro est promue vers la
        # colonne du lead (elle ne quitte la bag que promue) ; surface_m2
        # (peut être au sol) reste dans la bag.
        self.assertEqual(float(lead.surface_toiture_m2), 2600.0)
        # CAD149 — `heures_pompage` a désormais sa colonne dédiée.
        self.assertEqual(str(lead.pompage_heures_jour), '7.0')

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


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class LWebt2TunnelEquipementsDetailWebhookTests(TestCase):
    """L-WEBT2 (24/08/2026) — précisions kW/créneau FACULTATIVES, désormais
    saisissables par le CLIENT lui-même depuis la section « Affiner mon
    profil » (avant : commercial-only, L-BACK/L-BACK2 sur ``crm.Lead``).
    Mêmes 8 colonnes dédiées, jamais laissées dans ``web_questionnaire``."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJ Web Co 4', slug='qj-web-co-4')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_payload_complet_atterrit_sur_les_colonnes_dediees(self):
        res = self.post(payload_site(
            equip_chauffe_eau_kw=2.2, equip_chauffe_eau_creneau='nuit',
            equip_ve_chargeur_kw=7.4, equip_ve_creneau='soir',
            equip_clim_kw=3.5, equip_clim_creneau='matin',
            equip_piscine_heures_jour=6.5, equip_piscine_creneau='soir',
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(str(lead.equip_chauffe_eau_kw), '2.20')
        self.assertEqual(lead.equip_chauffe_eau_creneau, 'nuit')
        self.assertEqual(str(lead.equip_ve_chargeur_kw), '7.40')
        self.assertEqual(lead.equip_ve_creneau, 'soir')
        self.assertEqual(str(lead.equip_clim_kw), '3.50')
        self.assertEqual(lead.equip_clim_creneau, 'matin')
        self.assertEqual(str(lead.equip_piscine_heures_jour), '6.5')
        self.assertEqual(lead.equip_piscine_creneau, 'soir')
        # Aucune de ces 8 réponses ne pollue web_questionnaire.
        self.assertEqual(lead.web_questionnaire, {})

    def test_absence_des_cles_ne_touche_rien(self):
        res = self.post(payload_site(mode='residentiel'))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.equip_chauffe_eau_kw)
        self.assertIsNone(lead.equip_chauffe_eau_creneau)
        self.assertIsNone(lead.equip_ve_chargeur_kw)
        self.assertIsNone(lead.equip_ve_creneau)
        self.assertIsNone(lead.equip_clim_kw)
        self.assertIsNone(lead.equip_clim_creneau)
        self.assertIsNone(lead.equip_piscine_heures_jour)
        self.assertIsNone(lead.equip_piscine_creneau)

    def test_creneaux_hors_vocabulaire_sont_ignores(self):
        """Un créneau hors des 4 choix réels (whitelist stricte sur les
        enums ``crm.Lead``) est silencieusement ignoré — jamais une erreur
        4xx, jamais une valeur hors-contrat persistée."""
        res = self.post(payload_site(
            equip_chauffe_eau_creneau='minuit',
            equip_ve_creneau='apres_midi',  # pas dans CreneauVe (nuit/jour/soir)
            equip_clim_creneau='aube',
            equip_piscine_creneau='crepuscule',
        ))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.equip_chauffe_eau_creneau)
        self.assertIsNone(lead.equip_ve_creneau)
        self.assertIsNone(lead.equip_clim_creneau)
        self.assertIsNone(lead.equip_piscine_creneau)

    def test_kw_hors_bornes_est_ignore(self):
        """Une puissance kW hors bornes raisonnables (> 1000) est rejetée
        silencieusement, comme le reste des champs kW du webhook."""
        res = self.post(payload_site(equip_clim_kw=50000))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.equip_clim_kw)

    def test_heures_jour_hors_bornes_est_ignore(self):
        """``equip_piscine_heures_jour`` > 24 h/jour est physiquement
        impossible — rejeté silencieusement (même borne que
        ``heuresPompage``)."""
        res = self.post(payload_site(equip_piscine_heures_jour=30))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.equip_piscine_heures_jour)

    def test_ne_touche_pas_une_valeur_existante_quand_le_renvoi_est_vide(self):
        """Renvoi de la MÊME soumission (< 1 min, même téléphone) sans ces
        clés : la valeur déjà captée n'est jamais écrasée par du vide —
        même discipline que le reste du webhook (``existing`` merge).

        RECALAGE (24/08/2026) — le 2e envoi renvoie **200**, pas 201 : la
        déduplication « même envoi < 1 min » du webhook (``created=False`` →
        « Lead mis à jour (même envoi < 1 min). ») MET À JOUR le lead existant
        au lieu d'en créer un second. C'est exactement le comportement que ce
        test veut prouver ; le 201 initialement écrit contredisait sa propre
        prémisse (un 201 signifierait un lead DOUBLON créé)."""
        first = self.post(payload_site(
            phoneE164='+212661000999', equip_clim_kw=3.5,
            equip_clim_creneau='matin'))
        self.assertEqual(first.status_code, 201, first.content)
        second = self.post(payload_site(phoneE164='+212661000999'))
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json()['lead_id'], second.json()['lead_id'])
        lead = Lead.objects.get(pk=second.json()['lead_id'])
        self.assertEqual(str(lead.equip_clim_kw), '3.50')
        self.assertEqual(lead.equip_clim_creneau, 'matin')


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class Qjr595PromotionProCoupleTests(TestCase):
    """QJR595 — kVA et surface de toiture du client pro → colonnes du lead."""

    def setUp(self):
        self.company = Company.objects.create(nom='QJ595 Co', slug='qj595-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_puissance_kva_promue_et_absente_des_questions_a_poser(self):
        res = self.post(payload_site(
            mode='professionnel', puissanceKva=250, surfaceToitureM2=900))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(str(lead.compteur_puissance_kva), '250.00')
        self.assertEqual(str(lead.surface_toiture_m2), '900.00')
        self.assertNotIn('puissance_kva', lead.web_questionnaire or {})
        self.assertNotIn('surface_toiture_m2', lead.web_questionnaire or {})

    def test_puissance_hors_borne_reste_dans_la_bag(self):
        res = self.post(payload_site(
            mode='professionnel', puissanceKva=100000))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertIsNone(lead.compteur_puissance_kva)
        self.assertEqual(lead.web_questionnaire['puissance_kva'], 100000.0)


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class Agr402PromotionPompageTests(TestCase):
    """AGR402 — les réponses agricoles du site quittent le sac pour leurs
    colonnes AGR400 (webhook + reprise de l'existant)."""

    PAYLOAD_AGRICOLE = dict(
        mode='agricole', waterSource='puits', profondeurM=30, hmtM=55,
        besoinM3j=90, irrigation='aspersion', culture='agrumes',
        surfaceHa=3, regionAgricole='haouz', fuelSpendMad=1800)
    CLES_SAC = ('water_source', 'profondeur_m', 'hmt_m', 'besoin_m3j',
                'irrigation', 'culture', 'surface_ha', 'region_agricole',
                'fuel_spend_mad')

    def setUp(self):
        self.company = Company.objects.create(
            nom='AGR402 Co', slug='agr402-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def test_payload_agricole_complet_remplit_les_colonnes_et_vide_le_sac(self):
        res = self.post(payload_site(**self.PAYLOAD_AGRICOLE))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(lead.source_eau, 'puits')
        self.assertEqual(str(lead.niveau_statique_m), '30.00')
        self.assertEqual(lead.niveau_statique_source, 'site_web')
        self.assertEqual(str(lead.pompe_hmt_m), '55.00')
        self.assertEqual(lead.pompe_hmt_source, 'site_web')
        self.assertEqual(str(lead.besoin_eau_m3j), '90.00')
        self.assertEqual(lead.irrigation_methode, 'aspersion')
        self.assertEqual(lead.culture, 'agrumes')
        self.assertEqual(str(lead.surface_irriguee_ha), '3.00')
        self.assertEqual(lead.region_agricole, 'haouz')
        self.assertEqual(str(lead.depense_carburant_mad_mois), '1800.00')
        for cle in self.CLES_SAC:
            self.assertNotIn(cle, lead.web_questionnaire or {}, cle)

    def test_besoin_seul_remplit_besoin_avec_la_source_site_web(self):
        res = self.post(payload_site(mode='agricole', besoinM3j=84))
        self.assertEqual(res.status_code, 201, res.content)
        lead = Lead.objects.get(pk=res.json()['lead_id'])
        self.assertEqual(str(lead.besoin_eau_m3j), '84.00')
        self.assertEqual(lead.besoin_eau_source, 'site_web')
        self.assertIsNone(lead.niveau_statique_source)

    def test_une_colonne_deja_remplie_n_est_pas_ecrasee(self):
        self.post(payload_site(mode='agricole', profondeurM=30, hmtM=55))
        # Renvoi de la MÊME soumission (< 60 s, même téléphone) : complète
        # les colonnes vides, ne réécrit jamais une colonne déjà remplie.
        self.post(payload_site(mode='agricole', profondeurM=80, hmtM=90,
                               culture='olivier'))
        leads = Lead.objects.filter(company=self.company)
        self.assertEqual(leads.count(), 1)
        lead = leads.get()
        self.assertEqual(str(lead.niveau_statique_m), '30.00')
        self.assertEqual(str(lead.pompe_hmt_m), '55.00')
        self.assertEqual(lead.culture, 'olivier')

    def test_une_valeur_hors_colonne_reste_dans_le_sac(self):
        from apps.crm.webhooks import promouvoir_pompage_du_sac
        sac = {'fuel_spend_mad': 1e9, 'culture': 'blé'}
        fields = {}
        promouvoir_pompage_du_sac(sac, fields)
        self.assertEqual(sac, {'fuel_spend_mad': 1e9})
        self.assertEqual(fields, {'culture': 'blé'})


class Agr402RepriseDeLExistantTests(TestCase):
    """La migration de données : déplace si la colonne est vide, retire la
    clé déplacée, idempotente."""

    def _migration(self):
        import importlib
        return importlib.import_module(
            'apps.crm.migrations.0120_agr402_sac_pompage_vers_colonnes')

    def test_reprise_idempotente_et_sans_ecrasement(self):
        from django.apps import apps as django_apps
        company = Company.objects.create(nom='AGR402 R', slug='agr402-r')
        vierge = Lead.objects.create(
            company=company, nom='Vierge', web_questionnaire={
                'water_source': 'forage', 'besoin_m3j': 120,
                'region_agricole': 'souss-massa', 'equipes': '2x8'})
        rempli = Lead.objects.create(
            company=company, nom='Rempli', besoin_eau_m3j=50,
            web_questionnaire={'besoin_m3j': 120})
        migration = self._migration()
        migration.deplacer(django_apps, None)
        vierge.refresh_from_db()
        rempli.refresh_from_db()
        self.assertEqual(vierge.source_eau, 'forage')
        self.assertEqual(str(vierge.besoin_eau_m3j), '120.00')
        self.assertEqual(vierge.besoin_eau_source, 'site_web')
        self.assertEqual(vierge.region_agricole, 'souss-massa')
        self.assertEqual(vierge.web_questionnaire, {'equipes': '2x8'})
        # Colonne déjà remplie : rien n'est déplacé, la clé reste au sac.
        self.assertEqual(str(rempli.besoin_eau_m3j), '50.00')
        self.assertEqual(rempli.web_questionnaire, {'besoin_m3j': 120})
        etat = list(Lead.objects.filter(company=company).order_by('pk')
                    .values())
        migration.deplacer(django_apps, None)
        self.assertEqual(
            list(Lead.objects.filter(company=company).order_by('pk')
                 .values()), etat)


@override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=SECRET)
class Ciq406PromotionProTests(TestCase):
    """CIQ406 — les réponses PRO du site quittent le sac pour leurs colonnes
    CIQ401 (contrat ``tunnel_webhook_keys.json`` → ``ajout_ciq400``)."""

    def setUp(self):
        self.company = Company.objects.create(
            nom='CIQ406 Co', slug='ciq406-co')
        self.url = reverse('website-lead-webhook')

    def post(self, data):
        return self.client.post(
            self.url, data=json.dumps(data),
            content_type='application/json',
            HTTP_X_WEBHOOK_SECRET=SECRET)

    def _lead(self, **extra):
        res = self.post(payload_site(mode='professionnel', **extra))
        self.assertEqual(res.status_code, 201, res.content)
        return Lead.objects.get(pk=res.json()['lead_id'])

    def test_contrat_declare_les_cles_promues(self):
        from pathlib import Path
        contrat = json.loads(
            (Path(__file__).resolve().parent / 'contract_samples'
             / 'tunnel_webhook_keys.json').read_text(encoding='utf-8'))
        ajout = contrat['ajout_ciq400']
        self.assertEqual(ajout['cle_nouvelle']['tensionSource']['champ_lead'],
                         'tension_source')
        self.assertEqual(
            {v['champ_lead'] for v in ajout['promues_en_colonne'].values()},
            {'categorie_commerciale', 'reponses_categorie', 'regime_equipes',
             'type_surface', 'groupe_electrogene', 'groupe_kva',
             'groupe_depense_mad_mois', 'cos_phi'})

    def test_industriel_sans_tension_source_defaut_visible(self):
        lead = self._lead(tensionRaccordement='bt')
        self.assertEqual(lead.tension_raccordement, 'bt')
        self.assertEqual(lead.tension_source, 'site_defaut_visible')
        self.assertNotIn('tension_raccordement', lead.web_questionnaire or {})

    def test_tension_touchee_site_web(self):
        lead = self._lead(tensionRaccordement='mt', tensionSource='touchee')
        self.assertEqual(lead.tension_source, 'site_web')
        self.assertNotIn('tension_source', lead.web_questionnaire or {})

    def test_categorie_et_reponses_promues_activite_reste_au_sac(self):
        lead = self._lead(categorieCommerciale='hotel', chambres=40,
                          piscine=True, effectif=12, activityProfile='day',
                          fermetureEstivale=True, weekend=False)
        self.assertEqual(lead.categorie_commerciale, 'hotel')
        self.assertEqual(lead.reponses_categorie,
                         {'chambres': 40, 'piscine': True})
        # `effectif` n'est pas une question hôtel : il reste au sac.
        self.assertEqual(lead.web_questionnaire, {
            'effectif': 12.0, 'activity_profile': 'day',
            'fermeture_estivale': True, 'weekend': False})

    def test_surface_terrasse_donne_toiture_et_terrasse_beton(self):
        lead = self._lead(surfaceType='terrasse')
        self.assertEqual(lead.type_surface, 'toiture')
        self.assertEqual(lead.type_toiture, 'terrasse_beton')
        lead = self._lead(surfaceType='ombriere', phoneE164='+212661000999')
        self.assertEqual(lead.type_surface, 'ombriere')
        self.assertIsNone(lead.type_toiture)

    def test_une_colonne_deja_remplie_n_est_jamais_ecrasee(self):
        self._lead(tensionRaccordement='bt', tensionSource='touchee',
                   equipes='1x8')
        self.post(payload_site(mode='professionnel',
                               tensionRaccordement='mt', equipes='3x8',
                               categorieCommerciale='bureau'))
        leads = Lead.objects.filter(company=self.company)
        self.assertEqual(leads.count(), 1)
        lead = leads.get()
        self.assertEqual(lead.tension_raccordement, 'bt')
        self.assertEqual(lead.tension_source, 'site_web')
        self.assertEqual(lead.regime_equipes, '1x8')
        self.assertEqual(lead.categorie_commerciale, 'bureau')


class Ciq406RepriseDeLExistantTests(TestCase):
    """La migration de données 0125 : déplace si la colonne est vide, retire
    la clé déplacée, idempotente, sans écrasement."""

    def _migration(self):
        import importlib
        return importlib.import_module(
            'apps.crm.migrations.0125_ciq406_sac_pro_vers_colonnes')

    def test_reprise_idempotente_et_sans_ecrasement(self):
        from django.apps import apps as django_apps
        company = Company.objects.create(nom='CIQ406 R', slug='ciq406-r')
        # Forme PROD 03/10/2026 du lead industriel.
        industriel = Lead.objects.create(
            company=company, nom='Usine', type_installation='industriel',
            web_questionnaire={'puissance_kva': 250,
                               'activity_profile': 'day',
                               'tension_raccordement': 'bt'})
        rempli = Lead.objects.create(
            company=company, nom='Rempli', tension_raccordement='mt',
            tension_source='facture',
            web_questionnaire={'tension_raccordement': 'bt',
                               'equipes': '2x8'})
        migration = self._migration()
        migration.deplacer(django_apps, None)
        industriel.refresh_from_db()
        rempli.refresh_from_db()
        self.assertEqual(industriel.tension_raccordement, 'bt')
        self.assertEqual(industriel.tension_source, 'site_defaut_visible')
        self.assertEqual(industriel.web_questionnaire, {
            'puissance_kva': 250, 'activity_profile': 'day'})
        self.assertEqual(rempli.tension_raccordement, 'mt')
        self.assertEqual(rempli.tension_source, 'facture')
        self.assertEqual(rempli.regime_equipes, '2x8')
        self.assertEqual(rempli.web_questionnaire,
                         {'tension_raccordement': 'bt'})
        etat = list(Lead.objects.filter(company=company).order_by('pk')
                    .values())
        migration.deplacer(django_apps, None)
        self.assertEqual(
            list(Lead.objects.filter(company=company).order_by('pk')
                 .values()), etat)
