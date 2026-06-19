"""
Tests du module Chantiers / Installations (2026-06-13).

Couvre : création depuis un devis accepté (pré-remplissage + anti-doublon),
changement de statut → ligne de chatter + statuts hors liste refusés, mise en
service qui pose le statut, isolation par société (A ne voit/touche pas B), et
le type de client + identifiants.

Run :
    docker compose exec django_core python manage.py test apps.installations -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import Installation, Intervention, InstallationActivity

User = get_user_model()


def make_company(slug='cht-co', nom='Cht Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ids_of(resp):
    data = resp.data
    rows = data['results'] if isinstance(data, dict) and 'results' in data else data
    return [x['id'] for x in rows]


_devis_seq = itertools.count(1)


def make_accepted_devis(company, with_lead=True):
    # Suffixe unique par appel : permet plusieurs devis/chantiers pour la même
    # société dans un seul test sans violer l'unicité (company, email) /
    # (company, reference).
    n = next(_devis_seq)
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'site-{company.id}-{n}@example.invalid')
    lead = None
    if with_lead:
        lead = Lead.objects.create(
            company=company, nom='Site', prenom='Client', stage='SIGNED',
            adresse='Douar Test, route de Tit Mellil', ville='Médiouna',
            gps_lat=Decimal('33.456789'), gps_lng=Decimal('-7.512345'),
            raccordement='triphase', type_installation='residentiel',
            taille_souhaitee_kwc=Decimal('6.5'))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-CHT-{company.id}-{n}', client=client,
        lead=lead, statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
        mode_installation='residentiel',
        etude_params={'puissance_kwc': 7.2})
    return devis, client, lead


class TestCreateFromDevis(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cht_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.devis, self.client_obj, self.lead = make_accepted_devis(self.company)

    def test_create_prefills_from_devis_and_lead(self):
        r = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                          {'devis': self.devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(r.data['created'])
        self.assertTrue(r.data['reference'].startswith('CHT-'))
        # Pré-remplissage
        self.assertEqual(r.data['client'], self.client_obj.id)
        self.assertEqual(r.data['devis'], self.devis.id)
        self.assertEqual(r.data['lead'], self.lead.id)
        self.assertEqual(r.data['site_adresse'], 'Douar Test, route de Tit Mellil')
        self.assertEqual(r.data['site_ville'], 'Médiouna')
        self.assertEqual(r.data['raccordement'], 'triphase')  # gelé depuis le lead
        self.assertEqual(r.data['type_installation'], 'residentiel')
        self.assertEqual(Decimal(r.data['puissance_installee_kwc']), Decimal('7.20'))
        # Entonnoir N1 : un chantier créé depuis un devis accepté démarre « Signé ».
        self.assertEqual(r.data['statut'], 'signe')
        self.assertEqual(str(r.data['gps_lat']), '33.456789')

    def test_create_is_idempotent_no_duplicate(self):
        first = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                              {'devis': self.devis.id}, format='json')
        self.assertEqual(first.status_code, 201)
        again = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                              {'devis': self.devis.id}, format='json')
        self.assertEqual(again.status_code, 200, again.data)
        self.assertFalse(again.data['created'])
        self.assertEqual(again.data['id'], first.data['id'])
        self.assertEqual(Installation.objects.filter(devis=self.devis).count(), 1)

    def test_refuses_non_accepted_devis(self):
        self.devis.statut = Devis.Statut.BROUILLON
        self.devis.save()
        r = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                          {'devis': self.devis.id}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_creation_writes_a_chatter_line(self):
        r = self.api.post('/api/django/installations/chantiers/creer-depuis-devis/',
                          {'devis': self.devis.id}, format='json')
        acts = InstallationActivity.objects.filter(installation_id=r.data['id'])
        self.assertTrue(any(a.kind == 'creation' for a in acts))


class TestDefaultInstaller(TestCase):
    """N66 — installateur par défaut configuré en Paramètres."""
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cht_creator', password='x', role_legacy='responsable',
            company=self.company)
        self.installer = User.objects.create_user(
            username='cht_installer', password='x', role_legacy='normal',
            company=self.company)
        self.api = auth(self.user)

    def test_default_installer_used_when_configured(self):
        from apps.parametres.models import CompanyProfile
        prof = CompanyProfile.get(self.company)
        prof.default_installer = self.installer
        prof.save(update_fields=['default_installer'])
        devis, _, _ = make_accepted_devis(self.company)
        r = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['technicien_responsable'], self.installer.id)

    def test_falls_back_to_creator_without_default(self):
        devis, _, _ = make_accepted_devis(self.company)
        r = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['technicien_responsable'], self.user.id)


class TestStatusAndMES(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cht_resp2', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        devis, _, _ = make_accepted_devis(self.company)
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])

    def test_status_change_logs_chatter(self):
        r = self.api.patch(f'/api/django/installations/chantiers/{self.inst.id}/',
                           {'statut': 'planifie'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'planifie')
        logged = InstallationActivity.objects.filter(
            installation=self.inst, field='statut')
        self.assertTrue(logged.exists())
        entry = logged.first()
        self.assertEqual(entry.new_value, 'Planifié')

    def test_invalid_status_rejected(self):
        r = self.api.patch(f'/api/django/installations/chantiers/{self.inst.id}/',
                           {'statut': 'en_orbite'}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_mise_en_service_sets_status(self):
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20',
             'mes_pv_notes': 'PV signé, production OK',
             'mes_production_test': '32.5', 'mes_tension': '230'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'mise_en_service')
        self.assertEqual(r.data['date_mise_en_service'], '2026-06-20')
        self.assertEqual(Decimal(r.data['mes_production_test']), Decimal('32.50'))
        # La note de chatter inclut les valeurs mesurées (production + tension).
        note = self.inst.activites.filter(kind='note').order_by('-id').first()
        self.assertIsNotNone(note)
        self.assertIn('32.5', note.body)
        self.assertIn('230', note.body)

    def test_cancel_is_a_flag_with_reason(self):
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/annuler/',
            {'motif': 'Client a renoncé'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['annule'])
        self.assertEqual(r.data['motif_annulation'], 'Client a renoncé')
        # Toujours visible (drapeau, pas une suppression)
        self.assertTrue(Installation.objects.filter(pk=self.inst.id).exists())

    def test_add_intervention(self):
        r = self.api.post('/api/django/installations/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'pose',
            'date_prevue': '2026-06-18', 'compte_rendu': 'Pose prévue',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Intervention.objects.filter(installation=self.inst).count(), 1)
        # L'ajout est tracé dans le chatter du chantier
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__icontains='Intervention ajoutée').exists())
        # Un compte rendu rempli sans date_realisee la tamponne côté serveur.
        interv = Intervention.objects.get(installation=self.inst)
        self.assertIsNotNone(interv.date_realisee)

    def test_intervention_edit_and_delete_log_chantier_chatter(self):
        created = self.api.post('/api/django/installations/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'controle',
            'date_prevue': '2026-06-18',
        }, format='json')
        iv_id = created.data['id']
        # Édition → note au chatter du chantier
        r = self.api.patch(
            f'/api/django/installations/interventions/{iv_id}/',
            {'compte_rendu': 'RAS'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__icontains='Intervention modifiée').exists())
        # Le compte rendu tamponne aussi la date réalisée.
        self.assertIsNotNone(Intervention.objects.get(pk=iv_id).date_realisee)
        # Suppression → note au chatter du chantier
        r = self.api.delete(
            f'/api/django/installations/interventions/{iv_id}/')
        self.assertIn(r.status_code, (200, 204), getattr(r, 'data', None))
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__icontains='Intervention supprimée').exists())


class TestChantierFunnelParcChecklist(TestCase):
    """N1/N2/N4/N7/N9 — entonnoir N1, parc installé, checklist, séries."""

    def setUp(self):
        self.company = make_company(slug='cht-funnel', nom='Funnel')
        self.user = User.objects.create_user(
            username='funnel_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        devis, _, _ = make_accepted_devis(self.company)
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])

    def test_starts_signed_and_installer_defaulted(self):
        self.assertEqual(self.inst.statut, 'signe')
        self.assertEqual(self.inst.technicien_responsable_id, self.user.id)
        self.assertIsInstance(self.inst.bom, list)

    def test_reception_stamps_date_and_enters_parc(self):
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': 'receptionne'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['est_parc'])
        self.assertIsNotNone(r.data['date_reception'])
        # Présent dans la vue parc.
        parc = self.api.get('/api/django/installations/chantiers/?parc=1')
        self.assertIn(self.inst.id, ids_of(parc))

    def test_legacy_status_maps_to_canonical_column(self):
        self.inst.statut = 'mise_en_service'
        self.inst.save(update_fields=['statut'])
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/')
        self.assertEqual(r.data['statut_canonique'], 'receptionne')
        self.assertTrue(r.data['est_parc'])

    def test_labour_days_editable(self):
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'labour_jours_estimes': '2.5', 'labour_jours_reels': '3'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data['labour_jours_estimes']), Decimal('2.5'))

    def test_checklist_seeds_and_tracks_completion(self):
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['items']), 7)
        self.assertEqual(r.data['completion'], 0)
        cle = r.data['items'][0]['cle']
        r2 = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/cocher-checklist/',
            {'cle': cle, 'fait': True}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        self.assertGreater(r2.data['completion'], 0)

    def test_serial_capture_on_checklist_creates_equipement(self):
        from apps.stock.models import Produit
        from apps.sav.models import Equipement
        produit = Produit.objects.create(
            company=self.company, nom='Onduleur X', prix_vente=Decimal('100'))
        self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/cocher-checklist/',
            {'cle': 'onduleur_raccorde', 'fait': True,
             'equipements': [{'produit': produit.id, 'numero_serie': 'SN-001'}]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['equipements_crees'], 1)
        self.assertTrue(Equipement.objects.filter(
            installation=self.inst, numero_serie='SN-001').exists())
        # N16 — la note de chatter liste le produit et la série capturés.
        note = self.inst.activites.filter(
            kind='note', body__icontains='Checklist').order_by('-id').first()
        self.assertIsNotNone(note)
        self.assertIn('Onduleur X', note.body)
        self.assertIn('SN-001', note.body)

    def test_serial_capture_optional_never_blocks(self):
        self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/checklist/')
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/cocher-checklist/',
            {'cle': 'panneaux_poses', 'fait': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['equipements_crees'], 0)

    def test_checklist_etapes_seeded_for_parametres(self):
        r = self.api.get('/api/django/installations/checklist-etapes/')
        self.assertEqual(r.status_code, 200)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        self.assertEqual(len(rows), 7)

    def test_parc_garantie_etat_aggregates_worst(self):
        # Parc — l'état de garantie du système est None sans équipement, puis le
        # PIRE état parmi les équipements posés (hors_garantie > sous_garantie).
        from datetime import date, timedelta
        from apps.stock.models import Produit
        from apps.sav.models import Equipement
        produit = Produit.objects.create(
            company=self.company, nom='Panneau X', prix_vente=Decimal('100'))
        url = f'/api/django/installations/chantiers/{self.inst.id}/'
        self.assertIsNone(self.api.get(url).data['parc_garantie_etat'])
        today = date.today()
        # Un équipement encore largement sous garantie.
        Equipement.objects.create(
            company=self.company, installation=self.inst, produit=produit,
            date_fin_garantie=today + timedelta(days=400))
        self.assertEqual(
            self.api.get(url).data['parc_garantie_etat'], 'sous_garantie')
        # Un second hors garantie → l'agrégat bascule sur le pire état.
        Equipement.objects.create(
            company=self.company, installation=self.inst, produit=produit,
            date_fin_garantie=today - timedelta(days=10))
        self.assertEqual(
            self.api.get(url).data['parc_garantie_etat'], 'hors_garantie')

    def test_regulatory_dossier_and_filters(self):
        # N40/N42 — pose un régime + statut + drapeau Article 33.
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'regime_8221': 'declaration_bt', 'dossier_statut': 'a_deposer',
             'art33_regularisation': True}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['regime_8221'], 'declaration_bt')
        self.assertTrue(r.data['art33_regularisation'])
        # N41 — filtres serveur par régime / statut / art33.
        self.assertIn(self.inst.id, ids_of(self.api.get(
            '/api/django/installations/chantiers/?regime=declaration_bt')))
        self.assertIn(self.inst.id, ids_of(self.api.get(
            '/api/django/installations/chantiers/?art33=1')))
        self.assertNotIn(self.inst.id, ids_of(self.api.get(
            '/api/django/installations/chantiers/?regime=autorisation_anre')))


class TestTenantScoping(TestCase):
    def setUp(self):
        self.a = make_company(slug='cht-a', nom='A')
        self.b = make_company(slug='cht-b', nom='B')
        self.ua = User.objects.create_user(
            username='cht_a', password='x', role_legacy='responsable', company=self.a)
        self.ub = User.objects.create_user(
            username='cht_b', password='x', role_legacy='admin', company=self.b)
        devis_a, _, _ = make_accepted_devis(self.a)
        self.inst_a = Installation.objects.get(pk=auth(self.ua).post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis_a.id}, format='json').data['id'])

    def test_other_company_cannot_see(self):
        r = auth(self.ub).get('/api/django/installations/chantiers/')
        self.assertNotIn(self.inst_a.id, ids_of(r))

    def test_other_company_cannot_retrieve_or_touch(self):
        api = auth(self.ub)
        self.assertEqual(
            api.get(f'/api/django/installations/chantiers/{self.inst_a.id}/').status_code, 404)
        self.assertEqual(
            api.patch(f'/api/django/installations/chantiers/{self.inst_a.id}/',
                      {'statut': 'planifie'}, format='json').status_code, 404)


class TestClientType(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='cli_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)

    def test_default_is_particulier(self):
        c = Client.objects.create(company=self.company, nom='Sans ICE')
        self.assertEqual(c.type_client, 'particulier')

    def test_entreprise_with_identifiers_persist(self):
        r = self.api.post('/api/django/crm/clients/', {
            'nom': 'STE Solaire', 'email': 'ste@example.invalid', 'type_client': 'entreprise',
            'ice': '001234567890123', 'if_fiscal': '12345678', 'rc': 'RC-9001',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['type_client'], 'entreprise')
        self.assertEqual(r.data['ice'], '001234567890123')
        self.assertEqual(r.data['rc'], 'RC-9001')

    def test_particulier_with_cin(self):
        r = self.api.post('/api/django/crm/clients/', {
            'nom': 'Particulier', 'email': 'part@example.invalid', 'type_client': 'particulier', 'cin': 'BK123456',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['cin'], 'BK123456')


class TestChecklistTemplates(TestCase):
    """N74 — checklists configurables en modèles nommés, auto-sélectionnés par
    type d'installation. Couvre : auto-sélection par type, repli sur « Défaut »,
    préservation du comportement (pas de type correspondant → étapes par défaut),
    isolation par société + société posée côté serveur."""

    def setUp(self):
        from apps.installations.models import (
            ChecklistTemplate, ChecklistEtapeModele)
        self.ChecklistTemplate = ChecklistTemplate
        self.ChecklistEtapeModele = ChecklistEtapeModele
        self.company = make_company(slug='cht-tmpl', nom='Tmpl')
        self.admin = User.objects.create_user(
            username='tmpl_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)

    def _make_inst(self, type_install):
        """Crée un chantier (depuis un devis accepté) du type donné."""
        devis, _, _ = make_accepted_devis(self.company)
        devis.mode_installation = type_install
        devis.save(update_fields=['mode_installation'])
        r = self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return Installation.objects.get(pk=r.data['id'])

    def test_default_template_seeded_with_todays_steps(self):
        # L'amorçage via l'endpoint Paramètres crée le modèle « Défaut » avec
        # exactement les 7 étapes d'aujourd'hui.
        r = self.api.get('/api/django/installations/checklist-templates/')
        self.assertEqual(r.status_code, 200, r.data)
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        defaut = [t for t in rows if t['type_installation'] in (None, '')]
        self.assertEqual(len(defaut), 1)
        self.assertEqual(defaut[0]['nom'], 'Défaut')
        self.assertTrue(defaut[0]['protege'])
        self.assertEqual(len(defaut[0]['etapes']), 7)

    def test_no_matching_type_uses_default_steps(self):
        # Comportement préservé : sans modèle typé, un chantier reçoit les 7
        # étapes du modèle « Défaut » (identique à avant N74).
        inst = self._make_inst('residentiel')
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/checklist/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['items']), 7)
        cles = {it['cle'] for it in r.data['items']}
        self.assertIn('pv_reception_signe', cles)
        self.assertIn('panneaux_poses', cles)

    def test_template_auto_selected_by_type(self):
        # Un modèle typé « agricole » avec ses propres étapes est
        # auto-sélectionné pour un chantier agricole.
        from apps.installations.services import ensure_default_template
        ensure_default_template(self.company)
        tmpl = self.ChecklistTemplate.objects.create(
            company=self.company, nom='Pompage', type_installation='agricole',
            ordre=1, actif=True)
        for i, (cle, lib) in enumerate(
                [('forage_ok', 'Forage vérifié'),
                 ('pompe_posee', 'Pompe posée'),
                 ('debit_mesure', 'Débit mesuré')]):
            self.ChecklistEtapeModele.objects.create(
                company=self.company, template=tmpl, cle=cle, libelle=lib,
                ordre=i)
        inst = self._make_inst('agricole')
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/checklist/')
        self.assertEqual(r.status_code, 200, r.data)
        cles = [it['cle'] for it in r.data['items']]
        self.assertEqual(cles, ['forage_ok', 'pompe_posee', 'debit_mesure'])
        # Et un chantier résidentiel garde, lui, le modèle « Défaut ».
        inst_res = self._make_inst('residentiel')
        r2 = self.api.get(
            f'/api/django/installations/chantiers/{inst_res.id}/checklist/')
        self.assertEqual(len(r2.data['items']), 7)

    def test_inactive_typed_template_falls_back_to_default(self):
        from apps.installations.services import ensure_default_template
        ensure_default_template(self.company)
        tmpl = self.ChecklistTemplate.objects.create(
            company=self.company, nom='Indus (off)',
            type_installation='industriel', ordre=1, actif=False)
        self.ChecklistEtapeModele.objects.create(
            company=self.company, template=tmpl, cle='etape_indus',
            libelle='Étape indus', ordre=0)
        inst = self._make_inst('industriel')
        r = self.api.get(
            f'/api/django/installations/chantiers/{inst.id}/checklist/')
        # Modèle typé inactif → repli sur « Défaut » (7 étapes).
        self.assertEqual(len(r.data['items']), 7)

    def test_company_force_assigned_not_from_body(self):
        # La société est posée côté serveur, jamais lue du corps.
        other = make_company(slug='cht-tmpl-other', nom='Other')
        r = self.api.post(
            '/api/django/installations/checklist-templates/',
            {'nom': 'Mon modèle', 'type_installation': 'residentiel',
             'company': other.id}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        tmpl = self.ChecklistTemplate.objects.get(pk=r.data['id'])
        self.assertEqual(tmpl.company_id, self.company.id)

    def test_tenant_scoping_other_company_cannot_see_or_touch(self):
        from apps.installations.services import ensure_default_template
        ensure_default_template(self.company)
        mine = self.ChecklistTemplate.objects.create(
            company=self.company, nom='À moi', type_installation='residentiel')
        b = make_company(slug='cht-tmpl-b', nom='B')
        ub = User.objects.create_user(
            username='tmpl_b', password='x', role_legacy='admin', company=b)
        api_b = auth(ub)
        # B ne voit pas le modèle de la société courante.
        listed = api_b.get('/api/django/installations/checklist-templates/')
        self.assertNotIn(mine.id, ids_of(listed))
        # B ne peut pas le récupérer ni le modifier.
        self.assertEqual(
            api_b.get(
                f'/api/django/installations/checklist-templates/{mine.id}/'
            ).status_code, 404)
        self.assertEqual(
            api_b.patch(
                f'/api/django/installations/checklist-templates/{mine.id}/',
                {'nom': 'Piraté'}, format='json').status_code, 404)
        # B ne peut pas créer une étape rattachée au modèle d'une autre société.
        bad = api_b.post(
            '/api/django/installations/checklist-etapes/',
            {'template': mine.id, 'cle': 'x', 'libelle': 'X'}, format='json')
        self.assertEqual(bad.status_code, 400, bad.data)

    def test_default_template_is_protected_from_delete(self):
        r = self.api.get('/api/django/installations/checklist-templates/')
        rows = r.data['results'] if isinstance(r.data, dict) else r.data
        defaut = next(t for t in rows if t['nom'] == 'Défaut')
        d = self.api.delete(
            f"/api/django/installations/checklist-templates/{defaut['id']}/")
        self.assertEqual(d.status_code, 409, d.data)


class TestInterventionF3(TestCase):
    """F3 — Intervention (sortie chantier) : statut PROPRE (machine à états
    distincte du chantier + STAGES.py), équipe par défaut = installateur,
    camionnette scopée société, chatter propre, GPS/client/devis tirés du
    chantier."""

    def setUp(self):
        from apps.stock.models import EmplacementStock
        from apps.installations.models import InterventionActivity
        self.InterventionActivity = InterventionActivity
        self.company = make_company()
        self.user = User.objects.create_user(
            username='interv_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        devis, _, _ = make_accepted_devis(self.company)
        # Sans installateur par défaut → technicien_responsable = créateur.
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])
        self.camion = EmplacementStock.objects.create(
            company=self.company, nom='Camionnette 1')

    def _create_interv(self, **extra):
        body = {'installation': self.inst.id, 'type_intervention': 'pose'}
        body.update(extra)
        return self.api.post(
            '/api/django/installations/interventions/', body, format='json')

    def test_statut_defaults_to_a_preparer(self):
        r = self._create_interv()
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'a_preparer')
        self.assertEqual(r.data['statut_ordre'], 0)

    def test_equipe_defaults_to_chantier_installer(self):
        r = self._create_interv()
        self.assertEqual(r.status_code, 201, r.data)
        # technicien_responsable du chantier = self.user (fallback créateur).
        self.assertIn(self.user.id, r.data['equipe'])
        self.assertIn(self.user.username, r.data['equipe_noms'])

    def test_explicit_equipe_is_kept(self):
        other = User.objects.create_user(
            username='interv_tech', password='x', role_legacy='normal',
            company=self.company)
        r = self._create_interv(equipe=[other.id])
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(set(r.data['equipe']), {other.id})

    def test_gps_client_devis_pulled_from_chantier(self):
        r = self._create_interv()
        self.assertEqual(r.data['installation_reference'], self.inst.reference)
        # Le lead du devis porte un GPS (make_accepted_devis) → repris sur le
        # chantier, exposé en lecture sur l'intervention.
        self.assertIsNotNone(r.data['gps_lat'])
        self.assertIsNotNone(r.data['gps_lng'])
        self.assertTrue(r.data['client_nom'])

    def _confirmer_preparation(self, iid):
        """F5 — confirme « Tout est chargé » pour pouvoir quitter « À préparer »
        (la nomenclature est vide dans ces tests → confirmation triviale)."""
        from apps.installations.models import Intervention
        from apps.installations import field_services
        interv = Intervention.objects.get(pk=iid)
        prep = field_services.ensure_preparation(interv)
        field_services.confirm_charge(prep, self.user)

    def test_statut_change_logs_own_chatter_not_chantier(self):
        iid = self._create_interv().data['id']
        self._confirmer_preparation(iid)  # F5 — garde de transition
        chantier_statut_avant = self.inst.statut
        r = self.api.patch(
            f'/api/django/installations/interventions/{iid}/',
            {'statut': 'en_route'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'en_route')
        # Le chatter PROPRE de l'intervention a une ligne statut.
        logged = self.InterventionActivity.objects.filter(
            intervention_id=iid, field='statut')
        self.assertTrue(logged.exists())
        self.assertEqual(logged.first().new_value, 'En route')
        # CRUCIAL : le statut du chantier n'a PAS bougé (séparation F3).
        self.inst.refresh_from_db()
        self.assertEqual(self.inst.statut, chantier_statut_avant)

    def test_historique_and_noter_endpoints(self):
        iid = self._create_interv().data['id']
        # La création a écrit une ligne « creation » dans le chatter propre.
        h = self.api.get(
            f'/api/django/installations/interventions/{iid}/historique/')
        self.assertEqual(h.status_code, 200)
        self.assertTrue(any(e['kind'] == 'creation' for e in h.data))
        n = self.api.post(
            f'/api/django/installations/interventions/{iid}/noter/',
            {'body': 'Prévoir une nacelle.'}, format='json')
        self.assertEqual(n.status_code, 201, n.data)
        h2 = self.api.get(
            f'/api/django/installations/interventions/{iid}/historique/')
        self.assertTrue(any(e['body'] == 'Prévoir une nacelle.' for e in h2.data))

    def test_noter_rejects_empty(self):
        iid = self._create_interv().data['id']
        n = self.api.post(
            f'/api/django/installations/interventions/{iid}/noter/',
            {'body': '   '}, format='json')
        self.assertEqual(n.status_code, 400)

    def test_camionnette_assignable_and_scoped(self):
        r = self._create_interv(camionnette=self.camion.id)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['camionnette'], self.camion.id)
        self.assertEqual(r.data['camionnette_nom'], 'Camionnette 1')

    def test_foreign_camionnette_rejected(self):
        from apps.stock.models import EmplacementStock
        b = make_company(slug='interv-b', nom='Interv B')
        cam_b = EmplacementStock.objects.create(company=b, nom='Camion B')
        r = self._create_interv(camionnette=cam_b.id)
        self.assertEqual(r.status_code, 400, r.data)

    def test_statut_filter(self):
        from unittest import mock
        from apps.installations.models import Intervention, ShotListSlot
        from apps.installations import field_services
        i1 = self._create_interv().data['id']
        i2 = self._create_interv().data['id']
        # F5/F8 — satisfaire les gardes : confirmer la préparation et déposer une
        # photo par créneau obligatoire avant de pouvoir passer à « Terminée ».
        self._confirmer_preparation(i2)
        interv2 = Intervention.objects.get(pk=i2)
        field_services.seed_shotlist_slots(self.company)
        from django.contrib.contenttypes.models import ContentType
        from apps.records.models import Attachment
        ct = ContentType.objects.get_for_model(Intervention)
        for slot in ShotListSlot.objects.filter(
                company=self.company, obligatoire=True, actif=True):
            Attachment.objects.create(
                company=self.company, content_type=ct, object_id=interv2.id,
                file_key='k', filename=field_services.encode_slot_filename(
                    slot.cle, 'p.png'), mime='image/png',
                uploaded_by=self.user)
        with mock.patch('apps.records.storage.get_minio_client'):
            self.api.patch(
                f'/api/django/installations/interventions/{i2}/',
                {'statut': 'terminee'}, format='json')
        r = self.api.get(
            '/api/django/installations/interventions/?statut=terminee')
        got = ids_of(r)
        self.assertIn(i2, got)
        self.assertNotIn(i1, got)
