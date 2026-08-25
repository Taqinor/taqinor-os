"""L-QUEST — « questionnaire envoyable au client ».

Couvre les promesses du contrat
``apps/crm/contract_samples/questionnaire_lead.json`` :

  - la whitelist de sections est la seule vérité (clé inconnue → 400) ;
  - `manquantes` par cas, y compris le TROIS-ÉTATS des equip_* (``None`` =
    jamais posée ≠ ``False`` = le client a dit non) ;
  - le mint est IDEMPOTENT (même lien tant qu'il n'a pas expiré) et son
    défaut = les informations manquantes ;
  - le POST public est PARTIEL et REPRENABLE (le client revient là où il
    s'est arrêté) ;
  - on n'efface jamais une valeur déjà connue, et une section n'écrit que
    ses propres champs (le GPS survit à une réponse « contact ») ;
  - un lien expiré n'ouvre plus rien (404 à corps constant) ;
  - le jeton INTERNE donne un aperçu MUET (aucune trace au GET, 403 au POST)
    et n'est jamais l'URL du client.

Le débit (throttle) n'est pas testé ici — le patron de référence
``tests_xsal17_booking_link.py`` ne le teste pas non plus.
"""
import datetime
import json

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.crm import questionnaire as quest
from apps.crm.models import Lead, LeadActivity, QuestionnaireLien
from apps.records.models import Attachment

User = get_user_model()

PUBLIC = '/api/django/crm/public/questionnaire/{}/'


def make_api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def lead_complet(company, **extra):
    """Lead dont TOUTES les sections sont renseignées — le point de départ
    des tests qui vérifient qu'on ne casse rien."""
    champs = dict(
        nom='Benali', prenom='Amina',
        email='amina@example.ma', adresse='12 rue X', ville='Casablanca',
        gps_lat=33.5, gps_lng=-7.6,
        facture_hiver=3500, ete_differente=False,
        tranche_onee='T3', raccordement=Lead.Raccordement.MONOPHASE,
        type_toiture=Lead.TypeToiture.TERRASSE_BETON, surface_toiture_m2=120,
        roof_age=5, ownership=Lead.Ownership.PROPRIETAIRE,
        occupation_jour=Lead.OccupationJour.PRESENT,
        equip_piscine=False, equip_voiture_electrique=False,
        equip_clim=True, equip_chauffe_eau_electrique=False,
    )
    champs.update(extra)
    return Lead.objects.create(company=company, **champs)


def joindre_photo(lead, filename):
    """Pièce jointe MINIMALE (aucun MinIO) : seul le LIBELLÉ compte pour la
    reconnaissance de section — c'est l'approximation documentée."""
    return Attachment.objects.create(
        company=lead.company,
        content_type=ContentType.objects.get_for_model(Lead),
        object_id=lead.pk,
        file_key='attachments/factice', filename=filename,
        size=1, mime='image/jpeg')


# ── Règles métier pures ──────────────────────────────────────────────────

class ManquantesTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor LQUEST', slug='taqinor-lquest')

    def test_lead_vide_tout_est_manquant(self):
        lead = Lead.objects.create(company=self.company, nom='Vide')
        manq = quest.manquantes(lead)
        self.assertEqual(sorted(manq), sorted(quest.SECTIONS))
        self.assertTrue(all(manq.values()), manq)

    def test_lead_complet_plus_les_trois_photos_ne_manque_rien(self):
        lead = lead_complet(self.company)
        joindre_photo(lead, 'facture-onee.jpg')
        joindre_photo(lead, 'compteur.jpg')
        joindre_photo(lead, 'tableau-electrique.jpg')
        manq = quest.manquantes(lead)
        self.assertFalse(any(manq.values()), manq)

    def test_equipements_none_manque_mais_false_ne_manque_pas(self):
        """Le cœur du trois-états : « jamais posée » ≠ « le client a dit non »."""
        lead = lead_complet(self.company)
        self.assertFalse(quest.manquantes(lead)['equipements'])
        # Le client a répondu NON à tout : la question a bien été posée.
        Lead.objects.filter(pk=lead.pk).update(
            equip_piscine=False, equip_voiture_electrique=False,
            equip_clim=False, equip_chauffe_eau_electrique=False)
        lead.refresh_from_db()
        self.assertFalse(quest.manquantes(lead)['equipements'])
        # Une seule jamais posée suffit à re-poser la section.
        Lead.objects.filter(pk=lead.pk).update(equip_clim=None)
        lead.refresh_from_db()
        self.assertTrue(quest.manquantes(lead)['equipements'])

    def test_gps_manque_des_qu_une_coordonnee_est_absente(self):
        lead = lead_complet(self.company, gps_lng=None)
        self.assertTrue(quest.manquantes(lead)['gps'])

    def test_energie_manque_quand_la_tranche_est_vide(self):
        lead = lead_complet(self.company, tranche_onee='')
        self.assertTrue(quest.manquantes(lead)['energie'])

    def test_energie_manque_quand_la_regle_du_devis_auto_manque(self):
        lead = lead_complet(self.company, facture_hiver=None)
        self.assertTrue(quest.manquantes(lead)['energie'])

    def test_photo_reconnue_au_libelle_et_seulement_la_bonne(self):
        lead = lead_complet(self.company)
        joindre_photo(lead, 'ma-facture-de-janvier.JPG')
        manq = quest.manquantes(lead)
        self.assertFalse(manq['photo_facture'])
        # En cas de doute la section reste manquante : on repose la question.
        self.assertTrue(manq['photo_compteur'])
        self.assertTrue(manq['photo_tableau'])

    def test_prefill_ne_rend_que_les_sections_actives_sans_defaut_invente(self):
        lead = lead_complet(self.company, facture_ete=None)
        pre = quest.prefill(lead, ['gps', 'energie'])
        self.assertEqual(set(pre), set(
            quest.CHAMPS_PAR_SECTION['gps']
            + quest.CHAMPS_PAR_SECTION['energie']))
        # Une valeur absente vaut null — JAMAIS un défaut forfaitaire.
        self.assertIsNone(pre['facture_ete'])
        self.assertEqual(pre['facture_hiver'], 3500.0)

    def test_valider_questions_refuse_une_section_inconnue(self):
        with self.assertRaises(quest.SectionInconnue):
            quest.valider_questions({'gps': True, 'jardin': True})


class NeJamaisRedemanderTests(TestCase):
    """Ordre fondateur 25/08/2026 — « you are adding the address while the
    client already have given its GPS position ».

    Le grain de la décision est le CHAMP : une donnée déjà portée par le lead
    revient PRÉ-REMPLIE, et une donnée vide que le GPS couvre déjà DISPARAÎT.
    """

    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor LQUEST Redemande', slug='taqinor-lquest-redemande')

    def test_gps_connu_l_adresse_n_est_plus_une_question(self):
        lead = lead_complet(self.company, adresse='')
        self.assertTrue(quest._gps_connu(lead))
        carte = quest.champs_a_poser(lead, ['contact'])
        self.assertNotIn('adresse', carte['contact'])
        # Les deux autres colonnes de la section restent servies (connues →
        # pré-remplies, confirmables) : on ne cache que ce qui est REDONDANT.
        self.assertEqual(carte['contact'], ['email', 'ville'])

    def test_sans_gps_l_adresse_reste_une_vraie_question(self):
        lead = lead_complet(
            self.company, adresse='', gps_lat=None, gps_lng=None)
        carte = quest.champs_a_poser(lead, ['contact'])
        self.assertIn('adresse', carte['contact'])

    def test_gps_connu_l_adresse_deja_saisie_reste_confirmable(self):
        """Connue ET couverte : on l'affiche quand même, pré-remplie — elle
        n'est jamais reposée À VIDE, ce qui est la promesse exacte."""
        lead = lead_complet(self.company, adresse='12 rue X')
        self.assertIn('adresse', quest.champs_a_poser(lead, ['contact'])['contact'])

    def test_manquantes_contact_ignore_l_adresse_quand_le_gps_est_la(self):
        lead = lead_complet(self.company, adresse='')
        self.assertFalse(quest.manquantes(lead)['contact'])
        # Sans GPS, la même fiche redevient incomplète.
        Lead.objects.filter(pk=lead.pk).update(gps_lat=None, gps_lng=None)
        lead.refresh_from_db()
        self.assertTrue(quest.manquantes(lead)['contact'])

    def test_manquantes_contact_reste_vrai_si_l_email_manque(self):
        """Le GPS couvre l'ADRESSE, jamais l'e-mail ni la ville."""
        lead = lead_complet(self.company, adresse='', email='')
        self.assertTrue(quest.manquantes(lead)['contact'])
        lead = lead_complet(self.company, adresse='', ville='',
                            nom='Autre')
        self.assertTrue(quest.manquantes(lead)['contact'])

    def test_les_sections_photo_restent_servies_avec_une_liste_vide(self):
        lead = lead_complet(self.company)
        sections = ['photo_facture', 'contact']
        self.assertEqual(
            quest.champs_a_poser(lead, sections)['photo_facture'], [])
        self.assertIn('photo_facture',
                      quest.sections_a_servir(lead, sections))

    def test_une_section_sans_rien_a_montrer_n_ouvre_pas_d_ecran_mort(self):
        """Cas limite : si la seule colonne restante d'une section est vide ET
        couverte, l'écran n'a plus rien à dessiner — on ne l'ouvre pas."""
        lead = lead_complet(self.company, adresse='')
        original = dict(quest.CHAMPS_PAR_SECTION)
        quest.CHAMPS_PAR_SECTION['contact'] = ('adresse',)
        try:
            self.assertEqual(quest.champs_a_poser(lead, ['contact']),
                             {'contact': []})
            self.assertEqual(quest.sections_a_servir(lead, ['contact']), [])
        finally:
            quest.CHAMPS_PAR_SECTION.clear()
            quest.CHAMPS_PAR_SECTION.update(original)


# ── Mint (endpoint privé) ────────────────────────────────────────────────

class MintTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor LQUEST Mint', slug='taqinor-lquest-mint')
        self.user = User.objects.create_user(
            username='lquest_resp', password='x',
            role_legacy='responsable', company=self.company)
        self.api = make_api(self.user)
        self.lead = lead_complet(self.company, gps_lat=None, gps_lng=None)

    def _post(self, body=None, api=None):
        api = api or self.api
        return api.post(
            f'/api/django/crm/leads/{self.lead.pk}/questionnaire-lien/',
            data=json.dumps(body or {}), content_type='application/json')

    def test_defaut_les_informations_manquantes(self):
        res = self._post()
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()
        # Seul le GPS manque sur ce lead : c'est la seule question posée.
        self.assertTrue(data['questions']['gps'])
        self.assertFalse(data['questions']['contact'])
        self.assertEqual(data['manquantes']['gps'], True)
        self.assertIn('/questionnaire/', data['url'])
        self.assertTrue(data['token'])

    def test_url_interne_differente_de_l_url_client(self):
        data = self._post().json()
        self.assertNotEqual(data['url_interne'], data['url'])
        lien = QuestionnaireLien.objects.get(lead=self.lead)
        self.assertIn(lien.token, data['url'])
        self.assertIn(lien.token_interne, data['url_interne'])
        self.assertNotIn(lien.token_interne, data['url'])
        # Le jeton interne n'est JAMAIS renvoyé nu au client.
        self.assertEqual(data['token'], lien.token)

    def test_idempotent_meme_lien_questions_mises_a_jour(self):
        premier = self._post().json()
        second = self._post({'questions': {'gps': False, 'toiture': True}})
        self.assertEqual(second.status_code, 200, second.content)
        second = second.json()
        self.assertEqual(QuestionnaireLien.objects.filter(
            lead=self.lead).count(), 1)
        self.assertEqual(second['token'], premier['token'])
        self.assertFalse(second['questions']['gps'])
        self.assertTrue(second['questions']['toiture'])

    def test_le_lien_pointe_sur_le_site_public_jamais_sur_l_api(self):
        """Revue critique 25/08/2026, finding #6 — LE LIEN ÉTAIT MORT.

        La page ``/questionnaire/<token>/`` vit dans ``apps/web`` (Astro,
        taqinor.ma) ; l'ERP ne la sert nulle part. Construite avec
        ``build_absolute_uri``, l'URL sortait sur l'hôte de la requête
        (api.taqinor.ma en prod, ``testserver`` ici) : le client cliquait sur
        un 404. Les DEUX URL (client et aperçu interne) doivent partir de
        ``PUBLIC_SITE_URL``."""
        with self.settings(PUBLIC_SITE_URL='https://exemple-site.ma'):
            data = self._post().json()
        for cle in ('url', 'url_interne'):
            self.assertTrue(
                data[cle].startswith('https://exemple-site.ma/questionnaire/'),
                f'{cle} = {data[cle]}')
            self.assertNotIn('testserver', data[cle])

    def test_un_host_forge_ne_choisit_pas_le_domaine_du_lien(self):
        """Corollaire : aucun en-tête entrant ne décide plus où pointe un lien
        envoyé à un client."""
        with self.settings(PUBLIC_SITE_URL='https://exemple-site.ma',
                           ALLOWED_HOSTS=['*']):
            res = self.api.post(
                f'/api/django/crm/leads/{self.lead.pk}/questionnaire-lien/',
                data=json.dumps({}), content_type='application/json',
                HTTP_HOST='pirate.example')
        self.assertEqual(res.status_code, 200, res.content)
        self.assertNotIn('pirate.example', res.json()['url'])

    def test_section_inconnue_400(self):
        res = self._post({'questions': {'jardin': True}})
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('jardin', res.json()['detail'])
        self.assertEqual(QuestionnaireLien.objects.count(), 0)

    def test_note_chatter_a_la_creation_puis_silence_si_rien_ne_change(self):
        # Recalage fold 25/08 — le libellé ne dit JAMAIS « envoyé » : le mint
        # se produit aussi à la simple OUVERTURE du dialogue ERP (lecture des
        # manquantes), et l'envoi WhatsApp réel n'est pas observable côté
        # serveur. Création → « créé » ; changement de questions → « mis à
        # jour » ; re-POST identique → aucune trace.
        self._post()
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Lien questionnaire créé')
        self.assertEqual(notes.count(), 1)
        self.assertIn('localisation GPS', notes.first().body)
        self._post()  # re-POST identique → aucune nouvelle trace
        self.assertEqual(notes.count(), 1)
        toutes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE,
            body__startswith='Lien questionnaire')
        self.assertEqual(toutes.count(), 1)

    def test_company_scope_un_intrus_ne_voit_pas_le_lead(self):
        autre = Company.objects.create(nom='Autre', slug='autre-lquest')
        intrus = User.objects.create_user(
            username='lquest_intrus', password='x',
            role_legacy='responsable', company=autre)
        self.assertEqual(self._post(api=make_api(intrus)).status_code, 404)

    def test_role_fin_commerciale_autorise(self):
        """get_permissions() PRIME sur l'@action : sans la ligne ajoutée dans
        la branche WRITE, la Commerciale — qui envoie le questionnaire —
        serait refusée."""
        from apps.roles.models import Role
        role = Role.objects.create(
            company=self.company, nom='Commerciale LQUEST',
            permissions=['crm_voir', 'crm_creer', 'crm_modifier'])
        commerciale = User.objects.create_user(
            username='lquest_commerciale', password='x',
            role=role, company=self.company)
        self.assertEqual(self._post(api=make_api(commerciale)).status_code, 200)


# ── Page publique ────────────────────────────────────────────────────────

class PublicQuestionnaireTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor LQUEST Public', slug='taqinor-lquest-public')
        self.lead = lead_complet(
            self.company, gps_lat=None, gps_lng=None, facture_ete=None)
        self.lien = QuestionnaireLien.objects.create(
            company=self.company, lead=self.lead,
            questions={'gps': True, 'energie': True, 'contact': True,
                       'toiture': False, 'occupation': False,
                       'equipements': False, 'photo_facture': False,
                       'photo_compteur': False, 'photo_tableau': False})

    def _get(self, token=None):
        return self.client.get(PUBLIC.format(token or self.lien.token))

    def _post(self, body, token=None):
        return self.client.post(
            PUBLIC.format(token or self.lien.token),
            data=json.dumps(body), content_type='application/json')

    def test_get_sert_les_sections_actives_et_le_prefill(self):
        res = self._get()
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()
        self.assertEqual(data['sections'], ['contact', 'gps', 'energie'])
        self.assertEqual(data['entreprise'], 'Taqinor LQUEST Public')
        self.assertEqual(data['prenom'], 'Amina')
        self.assertFalse(data['interne'])
        self.assertEqual(data['repondu'], {})
        # Prefill : la valeur connue est servie, l'inconnue vaut null.
        self.assertEqual(data['prefill']['ville'], 'Casablanca')
        self.assertIsNone(data['prefill']['gps_lat'])
        self.assertIsNone(data['prefill']['facture_ete'])
        # Aucun champ d'une section NON demandée ne fuit.
        self.assertNotIn('type_toiture', data['prefill'])

    def test_le_payload_servi_ne_reposte_pas_l_adresse_quand_le_gps_est_la(self):
        """LA garantie d'entrée (ordre fondateur) : un lead qui a DÉJÀ donné
        sa position ne voit AUCUNE question d'adresse dans ce qu'on lui sert.
        """
        Lead.objects.filter(pk=self.lead.pk).update(
            gps_lat=33.5, gps_lng=-7.6, adresse='')
        res = self._get()
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()
        # La section GPS elle-même n'est plus servie (elle est renseignée)…
        self.assertNotIn('gps', data['sections'])
        # …et surtout, l'adresse ne figure NULLE PART dans les questions.
        for colonnes in data['champs'].values():
            self.assertNotIn('adresse', colonnes)
        # Ce que le client a lui-même fourni reste servi, pré-rempli.
        self.assertEqual(data['champs']['contact'], ['email', 'ville'])
        self.assertEqual(data['prefill']['ville'], 'Casablanca')

    def test_sans_gps_l_adresse_est_bien_posee(self):
        Lead.objects.filter(pk=self.lead.pk).update(adresse='')
        data = self._get().json()
        self.assertIn('adresse', data['champs']['contact'])

    def test_champs_couvre_exactement_les_sections_servies(self):
        """Aucune fuite : `champs` ne parle que des sections servies — jamais
        d'une colonne d'une section que le commercial n'a pas demandée."""
        data = self._get().json()
        self.assertEqual(sorted(data['champs']), sorted(data['sections']))
        for section, colonnes in data['champs'].items():
            self.assertLessEqual(
                set(colonnes), set(quest.CHAMPS_PAR_SECTION[section]))

    def test_jeton_inconnu_404_a_corps_constant(self):
        res = self._get('jeton-qui-nexiste-pas')
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {'detail': 'Introuvable.'})

    def test_jeton_expire_404_meme_corps(self):
        QuestionnaireLien.objects.filter(pk=self.lien.pk).update(
            expires_at=timezone.now() - datetime.timedelta(minutes=1))
        res = self._get()
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {'detail': 'Introuvable.'})
        self.assertEqual(self._post(
            {'section': 'gps', 'reponses': {'gps_lat': 1}}).status_code, 404)

    def test_lead_supprime_ferme_le_lien(self):
        """``Lead.objects`` masque la corbeille : sans garde, la page
        s'ouvrirait encore et l'écriture planterait plus loin."""
        self.lead.soft_delete()
        self.assertEqual(self._get().status_code, 404)
        self.assertEqual(self._post(
            {'section': 'gps', 'reponses': {'gps_lat': 1}}).status_code, 404)

    def test_post_partiel_puis_reprise(self):
        res = self._post({'section': 'gps',
                          'reponses': {'gps_lat': 33.9, 'gps_lng': -6.9}})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['ok'], True)
        self.assertEqual(sorted(res.json()['enregistrees']),
                         ['gps_lat', 'gps_lng'])
        self.lead.refresh_from_db()
        self.assertEqual(float(self.lead.gps_lat), 33.9)
        # Le client revient : la page lui montre où il en est.
        data = self._get().json()
        self.assertEqual(data['repondu'], {'gps': True})
        self.assertEqual(data['prefill']['gps_lat'], 33.9)
        # …et il finit une AUTRE section.
        res2 = self._post({'section': 'energie',
                           'reponses': {'facture_ete': 4200,
                                        'ete_differente': True}})
        self.assertEqual(res2.status_code, 200, res2.content)
        self.assertEqual(sorted(self._get().json()['repondu']),
                         ['energie', 'gps'])
        self.lien.refresh_from_db()
        self.assertIsNotNone(self.lien.derniere_reponse_at)

    def test_jamais_ecraser_une_valeur_non_vide_par_du_vide(self):
        res = self._post({'section': 'contact',
                          'reponses': {'ville': '', 'adresse': None,
                                       'email': 'nouvelle@example.ma'}})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['enregistrees'], ['email'])
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.ville, 'Casablanca')
        self.assertEqual(self.lead.adresse, '12 rue X')
        self.assertEqual(self.lead.email, 'nouvelle@example.ma')

    def test_l_email_normalise_de_dedup_suit_la_correction_du_client(self):
        """``Lead.save()`` recalcule les colonnes de dédup (QW10) : un
        ``update_fields`` qui les oublierait laisserait la fiche introuvable
        par son NOUVEL e-mail."""
        self._post({'section': 'contact',
                    'reponses': {'email': 'Amina.NOUVELLE@Example.MA'}})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.email_normalise, 'amina.nouvelle@example.ma')

    def test_une_reponse_contact_ne_touche_jamais_le_gps(self):
        Lead.objects.filter(pk=self.lead.pk).update(gps_lat=33.5, gps_lng=-7.6)
        self._post({'section': 'contact',
                    'reponses': {'ville': 'Rabat', 'adresse': '3 av Y',
                                 'gps_lat': 0, 'gps_lng': 0}})
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.ville, 'Rabat')
        self.assertEqual(float(self.lead.gps_lat), 33.5)
        self.assertEqual(float(self.lead.gps_lng), -7.6)

    def test_section_inconnue_400(self):
        res = self._post({'section': 'jardin', 'reponses': {}})
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn('jardin', res.json()['detail'])

    def test_section_non_demandee_400(self):
        res = self._post({'section': 'toiture',
                          'reponses': {'roof_age': 3}})
        self.assertEqual(res.status_code, 400, res.content)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.roof_age, 5)

    def test_section_manquante_400(self):
        self.assertEqual(self._post({'reponses': {}}).status_code, 400)

    def test_reponse_ecrit_une_note_de_section_et_le_detail_des_champs(self):
        self._post({'section': 'gps',
                    'reponses': {'gps_lat': 34.0, 'gps_lng': -6.8}})
        notes = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.NOTE)
        self.assertEqual(notes.count(), 1)
        self.assertIn('localisation GPS', notes.first().body)
        modifs = LeadActivity.objects.filter(
            lead=self.lead, kind=LeadActivity.Kind.MODIFICATION)
        self.assertEqual(
            sorted(modifs.values_list('field', flat=True)),
            ['gps_lat', 'gps_lng'])

    def test_equipements_le_client_peut_repondre_non(self):
        QuestionnaireLien.objects.filter(pk=self.lien.pk).update(
            questions={'equipements': True})
        self.lien.refresh_from_db()
        Lead.objects.filter(pk=self.lead.pk).update(equip_piscine=None)
        res = self._post({'section': 'equipements',
                          'reponses': {'equip_piscine': False}})
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['enregistrees'], ['equip_piscine'])
        self.lead.refresh_from_db()
        # « Non » est une RÉPONSE : elle est enregistrée, pas ignorée.
        self.assertIs(self.lead.equip_piscine, False)


# ── Jeton interne : aperçu MUET ──────────────────────────────────────────

class ApercuInterneTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor LQUEST Interne', slug='taqinor-lquest-interne')
        self.lead = lead_complet(self.company, gps_lat=None, gps_lng=None)
        self.lien = QuestionnaireLien.objects.create(
            company=self.company, lead=self.lead, questions={'gps': True})

    def test_get_interne_meme_page_marquee_et_sans_aucune_trace(self):
        avant = LeadActivity.objects.filter(lead=self.lead).count()
        res = self.client.get(PUBLIC.format(self.lien.token_interne))
        self.assertEqual(res.status_code, 200, res.content)
        data = res.json()
        self.assertTrue(data['interne'])
        self.assertIn('gps', data['sections'])
        # Rien n'a bougé : ni chatter, ni progression, ni horodatage.
        self.assertEqual(
            LeadActivity.objects.filter(lead=self.lead).count(), avant)
        self.lien.refresh_from_db()
        self.assertEqual(self.lien.sections_repondues, {})
        self.assertIsNone(self.lien.derniere_reponse_at)

    def test_post_interne_refuse_et_n_ecrit_rien(self):
        res = self.client.post(
            PUBLIC.format(self.lien.token_interne),
            data=json.dumps({'section': 'gps',
                             'reponses': {'gps_lat': 30.0, 'gps_lng': -9.0}}),
            content_type='application/json')
        self.assertEqual(res.status_code, 403, res.content)
        self.lead.refresh_from_db()
        self.assertIsNone(self.lead.gps_lat)
        self.lien.refresh_from_db()
        self.assertEqual(self.lien.sections_repondues, {})
        self.assertIsNone(self.lien.derniere_reponse_at)


# ── Base d'URL publique (revue critique 25/08/2026, finding #6) ───────────

class UrlPubliqueTests(TestCase):
    """``url_publique`` est la SEULE convention d'URL du questionnaire, et
    elle part TOUJOURS du site public — jamais de l'hôte de la requête."""

    def test_base_prise_sur_le_site_public(self):
        with self.settings(PUBLIC_SITE_URL='https://exemple-site.ma'):
            self.assertEqual(
                quest.url_publique('AbC'),
                'https://exemple-site.ma/questionnaire/AbC/')

    def test_barre_finale_du_reglage_jamais_doublee(self):
        with self.settings(PUBLIC_SITE_URL='https://exemple-site.ma/'):
            self.assertEqual(
                quest.url_publique('AbC'),
                'https://exemple-site.ma/questionnaire/AbC/')

    def test_reglage_vide_replie_sur_site_url_jamais_une_url_relative(self):
        """Un déploiement qui n'a configuré que ``SITE_URL`` continue de
        produire un lien ABSOLU — jamais ``/questionnaire/...`` tout court."""
        with self.settings(PUBLIC_SITE_URL='',
                           SITE_URL='https://repli-site.ma'):
            self.assertEqual(
                quest.url_publique('AbC'),
                'https://repli-site.ma/questionnaire/AbC/')

    def test_request_est_ignore_meme_quand_il_est_fourni(self):
        """La signature reste tolérante pour les appelants historiques, mais
        aucun hôte entrant ne décide plus où pointe le lien."""
        from django.test import RequestFactory
        requete = RequestFactory().get('/', HTTP_HOST='pirate.example')
        with self.settings(PUBLIC_SITE_URL='https://exemple-site.ma'):
            url = quest.url_publique('AbC', request=requete)
        self.assertEqual(url, 'https://exemple-site.ma/questionnaire/AbC/')
