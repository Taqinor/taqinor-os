"""
Tests du module Chantiers / Installations (2026-06-13).

Couvre : création depuis un devis accepté (pré-remplissage + anti-doublon),
changement de statut → ligne de chatter + statuts hors liste refusés, mise en
service qui pose le statut, isolation par société (A ne voit/touche pas B), et
le type de client + identifiants.

Run :
    docker compose exec django_core python manage.py test apps.installations -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.ventes.models import Devis
from apps.installations.models import (
    ChecklistItem, Installation, Intervention, InstallationActivity,
)

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


def make_accepted_devis(company, with_lead=True):
    client = Client.objects.create(
        company=company, nom='Site', prenom='Client',
        email=f'site-{company.id}@example.invalid')
    lead = None
    if with_lead:
        lead = Lead.objects.create(
            company=company, nom='Site', prenom='Client', stage='SIGNED',
            adresse='Douar Test, route de Tit Mellil', ville='Médiouna',
            gps_lat=Decimal('33.456789'), gps_lng=Decimal('-7.512345'),
            raccordement='triphase', type_installation='residentiel',
            taille_souhaitee_kwc=Decimal('6.5'))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-CHT-{company.id}', client=client,
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
        self.assertEqual(r.data['statut'], 'a_planifier')
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


class TestChecklist(TestCase):
    """N3 — checklist d'exécution : auto-remplissage depuis les défauts société,
    bascule (qui/quand + journal chatter) et pourcentage d'avancement."""

    def setUp(self):
        self.company = make_company(slug='cl-co', nom='CL Co')
        self.user = User.objects.create_user(
            username='cl_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.devis, _, _ = make_accepted_devis(self.company)
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': self.devis.id}, format='json').data['id'])

    def test_checklist_autopopulated_on_creation(self):
        items = ChecklistItem.objects.filter(installation=self.inst)
        labels = list(items.order_by('ordre').values_list('label', flat=True))
        from apps.parametres.models import CHANTIER_CHECKLIST_DEFAUT
        self.assertEqual(labels, list(CHANTIER_CHECKLIST_DEFAUT))

    def test_checklist_endpoint_lazy_populates(self):
        # Chantier créé directement (sans checklist), puis GET la remplit.
        client = Client.objects.create(
            company=self.company, nom='Direct', email='direct@example.invalid')
        bare = Installation.objects.create(
            company=self.company, reference='CHT-BARE', client=client)
        self.assertEqual(bare.checklist.count(), 0)
        r = self.api.get(
            f'/api/django/installations/chantiers/{bare.id}/checklist/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(len(r.data) > 0)
        self.assertEqual(bare.checklist.count(), len(r.data))

    def test_toggle_records_who_and_when_and_logs(self):
        item = ChecklistItem.objects.filter(installation=self.inst).first()
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}'
            f'/checklist/{item.id}/toggle/', {}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['done'])
        self.assertEqual(r.data['done_by'], self.user.id)
        self.assertIsNotNone(r.data['done_at'])
        item.refresh_from_db()
        self.assertTrue(item.done)
        # Journalisé dans le chatter du chantier.
        self.assertTrue(InstallationActivity.objects.filter(
            installation=self.inst, body__icontains=item.label).exists())
        # Re-bascule = décoche, efface qui/quand.
        r2 = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}'
            f'/checklist/{item.id}/toggle/', {}, format='json')
        self.assertFalse(r2.data['done'])
        self.assertIsNone(r2.data['done_by'])

    def test_completion_percentage(self):
        items = list(ChecklistItem.objects.filter(installation=self.inst)
                     .order_by('ordre'))
        total = len(items)
        # Coche la moitié.
        for it in items[:total // 2]:
            self.api.post(
                f'/api/django/installations/chantiers/{self.inst.id}'
                f'/checklist/{it.id}/toggle/', {}, format='json')
        r = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/')
        comp = r.data['completion']
        self.assertEqual(comp['total'], total)
        self.assertEqual(comp['done'], total // 2)
        self.assertEqual(comp['percent'], round((total // 2) * 100 / total))

    def test_toggle_other_company_404(self):
        other = make_company(slug='cl-other', nom='CL Other')
        ub = User.objects.create_user(
            username='cl_b', password='x', role_legacy='admin', company=other)
        item = ChecklistItem.objects.filter(installation=self.inst).first()
        r = auth(ub).post(
            f'/api/django/installations/chantiers/{self.inst.id}'
            f'/checklist/{item.id}/toggle/', {}, format='json')
        self.assertEqual(r.status_code, 404)


class TestTypeIntervention(TestCase):
    """Types d'intervention éditables (T6) : scoping, blocage suppression
    en usage, seed par migration."""

    def setUp(self):
        from apps.roles.models import Role, ALL_PERMISSIONS
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.company = make_company(slug='ti-co', nom='TI Co')
        admin_role = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=ALL_PERMISSIONS, est_systeme=True)
        self.admin = User.objects.create_user(
            username='ti_admin', password='x', role=admin_role,
            role_legacy='admin', company=self.company)
        self.commerciale = User.objects.create_user(
            username='ti_comm', password='x', role_legacy='responsable',
            company=self.company)

    def test_backfill_seeds_legacy_types(self):
        from importlib import import_module
        from django.apps import apps as django_apps
        from apps.installations.models import TypeIntervention
        mod = import_module(
            'apps.installations.migrations.0004_backfill_typeintervention')
        mod.backfill(django_apps, None)
        keys = set(TypeIntervention.objects.filter(company=self.company)
                   .values_list('key', flat=True))
        self.assertIn('pose', keys)
        self.assertIn('depannage', keys)

    def test_admin_create_derives_key(self):
        from apps.installations.models import TypeIntervention
        r = auth(self.admin).post(
            '/api/django/installations/types-intervention/',
            {'label': 'Audit Énergétique'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        obj = TypeIntervention.objects.get(
            company=self.company, label='Audit Énergétique')
        self.assertEqual(obj.key, 'audit_energetique')

    def test_commerciale_cannot_write(self):
        r = auth(self.commerciale).post(
            '/api/django/installations/types-intervention/',
            {'label': 'X'}, format='json')
        self.assertEqual(r.status_code, 403)

    def test_cannot_delete_type_in_use(self):
        from apps.installations.models import (
            TypeIntervention, Installation, Intervention,
        )
        client = Client.objects.create(
            company=self.company, nom='C', email='c-ti@example.invalid')
        inst = Installation.objects.create(
            company=self.company, reference='CHT-TI-1', client=client)
        ti = TypeIntervention.objects.create(
            company=self.company, key='controle', label='Contrôle', ordre=40)
        Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='controle')
        r = auth(self.admin).delete(
            f'/api/django/installations/types-intervention/{ti.id}/')
        self.assertEqual(r.status_code, 409, getattr(r, 'data', None))
        self.assertTrue(TypeIntervention.objects.filter(id=ti.id).exists())

    def test_unused_type_can_be_deleted(self):
        from apps.installations.models import TypeIntervention
        ti = TypeIntervention.objects.create(
            company=self.company, key='libre', label='Libre', ordre=99)
        r = auth(self.admin).delete(
            f'/api/django/installations/types-intervention/{ti.id}/')
        self.assertEqual(r.status_code, 204)

    def test_list_company_scoped(self):
        from apps.installations.models import TypeIntervention
        other = make_company(slug='ti-other', nom='TI Other')
        TypeIntervention.objects.create(
            company=other, key='secret', label='Secret', ordre=10)
        r = auth(self.admin).get(
            '/api/django/installations/types-intervention/')
        keys = [t['key'] for t in (r.data['results']
                if 'results' in r.data else r.data)]
        self.assertNotIn('secret', keys)


# ── Parc installé (système installé / asset base) — N7–N10 ──

def make_produit(company, nom, sku, marque='ACME', garantie_mois=None):
    from apps.stock.models import Produit
    return Produit.objects.create(
        company=company, nom=nom, sku=sku, marque=marque,
        prix_achat=Decimal('100'), prix_vente=Decimal('200'),
        garantie_mois=garantie_mois)


def make_devis_with_lines(company, designations_produits, **kw):
    """Crée un devis accepté + lignes (produit, désignation). Retourne le devis.

    designations_produits : liste de (produit, designation).
    """
    from apps.ventes.models import Devis, LigneDevis
    client = Client.objects.create(
        company=company, nom='Parc', prenom='Client',
        email=f'parc-{company.id}-{kw.get("ref", "x")}@example.invalid')
    lead = Lead.objects.create(
        company=company, nom='Parc', prenom='Client', stage='SIGNED',
        adresse='Route X', ville=kw.get('ville', 'Casablanca'),
        gps_lat=Decimal('33.5'), gps_lng=Decimal('-7.6'),
        raccordement='triphase', type_installation='residentiel',
        taille_souhaitee_kwc=Decimal('6.5'))
    devis = Devis.objects.create(
        company=company, reference=f'DEV-PARC-{company.id}-{kw.get("ref", "x")}',
        client=client, lead=lead, statut=Devis.Statut.ACCEPTE,
        taux_tva=Decimal('20'), mode_installation='residentiel',
        etude_params={'puissance_kwc': kw.get('kwc', 7.2)})
    for produit, designation in designations_produits:
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=designation,
            quantite=Decimal('1'), prix_unitaire=Decimal('200'))
    return devis


class TestParcReception(TestCase):
    """N7 — système installé auto-créé à la réception (MES / clôture)."""

    def setUp(self):
        self.company = make_company(slug='parc-co', nom='Parc Co')
        self.user = User.objects.create_user(
            username='parc_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(
            self.company, 'Panneau 550W', 'PAN-550', garantie_mois=144)
        self.onduleur = make_produit(
            self.company, 'Onduleur hybride 5kW', 'OND-5', garantie_mois=60)
        self.batterie = make_produit(self.company, 'Batterie 5kWh', 'BAT-5')
        self.pose = make_produit(self.company, 'Pose et main d\'œuvre', 'POSE')
        devis = make_devis_with_lines(self.company, [
            (self.panneau, '12 panneaux 550 W'),
            (self.onduleur, 'Onduleur hybride 5kW'),
            (self.batterie, 'Batterie lithium 5kWh'),
            (self.pose, 'Pose et mise en service'),
        ], ref='r')
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])

    def test_mise_en_service_creates_equipements_and_reception(self):
        from apps.sav.models import Equipement
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertTrue(self.inst.parc_actif)
        self.assertEqual(str(self.inst.date_reception), '2026-06-20')
        # Un équipement par composant (panneau/onduleur/batterie) — PAS la pose.
        produits = set(Equipement.objects.filter(installation=self.inst)
                       .values_list('produit_id', flat=True))
        self.assertEqual(
            produits, {self.panneau.id, self.onduleur.id, self.batterie.id})

    def test_garanties_computed_on_auto_equipements(self):
        from apps.sav.models import Equipement
        self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20'}, format='json')
        eq = Equipement.objects.get(
            installation=self.inst, produit=self.panneau)
        # 2026-06-20 + 144 mois = 2038-06-20.
        self.assertEqual(str(eq.date_fin_garantie), '2038-06-20')

    def test_reception_is_idempotent(self):
        from apps.sav.models import Equipement
        self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20'}, format='json')
        count1 = Equipement.objects.filter(installation=self.inst).count()
        # Re-trigger : passe à clôturé via PATCH — ne doit PAS dupliquer.
        self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': 'cloture'}, format='json')
        count2 = Equipement.objects.filter(installation=self.inst).count()
        self.assertEqual(count1, count2)
        self.assertEqual(count1, 3)

    def test_patch_to_cloture_triggers_reception(self):
        from apps.sav.models import Equipement
        r = self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': 'cloture'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.inst.refresh_from_db()
        self.assertIsNotNone(self.inst.date_reception)
        self.assertEqual(
            Equipement.objects.filter(installation=self.inst).count(), 3)

    def test_non_received_status_does_not_materialise(self):
        from apps.sav.models import Equipement
        self.api.patch(
            f'/api/django/installations/chantiers/{self.inst.id}/',
            {'statut': 'planifie'}, format='json')
        self.inst.refresh_from_db()
        self.assertIsNone(self.inst.date_reception)
        self.assertEqual(
            Equipement.objects.filter(installation=self.inst).count(), 0)

    def test_existing_equipement_not_duplicated(self):
        from apps.sav.models import Equipement
        # Pré-crée manuellement l'équipement onduleur → réception ne le double pas.
        Equipement.objects.create(
            company=self.company, produit=self.onduleur, installation=self.inst)
        self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20'}, format='json')
        self.assertEqual(
            Equipement.objects.filter(
                installation=self.inst, produit=self.onduleur).count(), 1)


class TestSerialCapture(TestCase):
    """N9 — saisie des n° de série par composant, sans bloquer la checklist."""

    def setUp(self):
        self.company = make_company(slug='ser-co', nom='Ser Co')
        self.user = User.objects.create_user(
            username='ser_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(self.company, 'Panneau', 'PAN')
        devis = make_devis_with_lines(
            self.company, [(self.panneau, 'Panneau 550W')], ref='s')
        self.inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])
        self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20'}, format='json')

    def test_set_serials_updates_equipements(self):
        from apps.sav.models import Equipement
        eq = Equipement.objects.get(installation=self.inst)
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/set-serials/',
            {'serials': {str(eq.id): 'SN-ABC-123'}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        eq.refresh_from_db()
        self.assertEqual(eq.numero_serie, 'SN-ABC-123')

    def test_empty_serial_clears_and_does_not_block(self):
        from apps.sav.models import Equipement
        eq = Equipement.objects.get(installation=self.inst)
        eq.numero_serie = 'OLD'
        eq.save(update_fields=['numero_serie'])
        r = self.api.post(
            f'/api/django/installations/chantiers/{self.inst.id}/set-serials/',
            {'serials': {str(eq.id): ''}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        eq.refresh_from_db()
        self.assertIsNone(eq.numero_serie)

    def test_checklist_completes_with_empty_serials(self):
        # Cocher toutes les étapes ne dépend JAMAIS des n° de série.
        items = list(ChecklistItem.objects.filter(installation=self.inst))
        for it in items:
            r = self.api.post(
                f'/api/django/installations/chantiers/{self.inst.id}'
                f'/checklist/{it.id}/toggle/', {'done': True}, format='json')
            self.assertEqual(r.status_code, 200, r.data)
        detail = self.api.get(
            f'/api/django/installations/chantiers/{self.inst.id}/')
        self.assertEqual(detail.data['completion']['percent'], 100)


class TestParcListAndHub(TestCase):
    """N8/N10 — liste parc (filtres + scope + carte) et hub détail."""

    def setUp(self):
        self.company = make_company(slug='pl-co', nom='PL Co')
        self.user = User.objects.create_user(
            username='pl_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.panneau = make_produit(
            self.company, 'Panneau', 'PAN', marque='Longi')
        self.onduleur = make_produit(
            self.company, 'Onduleur', 'OND', marque='Huawei')

    def _received_inst(self, ref='a', ville='Casablanca', kwc=7.2):
        devis = make_devis_with_lines(self.company, [
            (self.panneau, 'Panneau 550W'),
            (self.onduleur, 'Onduleur hybride'),
        ], ref=ref, ville=ville, kwc=kwc)
        inst = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis.id}, format='json').data['id'])
        self.api.post(
            f'/api/django/installations/chantiers/{inst.id}/mise-en-service/',
            {'date_mise_en_service': '2026-06-20'}, format='json')
        inst.refresh_from_db()
        return inst

    def test_only_received_appear_in_parc(self):
        received = self._received_inst(ref='a')
        # Un chantier non réceptionné ne doit PAS apparaître.
        devis2 = make_devis_with_lines(
            self.company, [(self.panneau, 'Panneau')], ref='b')
        not_received = Installation.objects.get(pk=self.api.post(
            '/api/django/installations/chantiers/creer-depuis-devis/',
            {'devis': devis2.id}, format='json').data['id'])
        r = self.api.get('/api/django/installations/parc/')
        ids = ids_of(r)
        self.assertIn(received.id, ids)
        self.assertNotIn(not_received.id, ids)

    def test_filter_by_ville_and_kwc_and_marque(self):
        a = self._received_inst(ref='a', ville='Casablanca', kwc=5.0)
        b = self._received_inst(ref='b', ville='Marrakech', kwc=12.0)
        # ville
        r = self.api.get('/api/django/installations/parc/?ville=marrak')
        self.assertEqual(ids_of(r), [b.id])
        # kwc band
        r = self.api.get('/api/django/installations/parc/?kwc_min=10')
        self.assertEqual(ids_of(r), [b.id])
        # marque de composant
        r = self.api.get('/api/django/installations/parc/?marque=Longi')
        self.assertEqual(set(ids_of(r)), {a.id, b.id})
        r = self.api.get('/api/django/installations/parc/?marque=Inexistante')
        self.assertEqual(ids_of(r), [])

    def test_filter_by_annee(self):
        a = self._received_inst(ref='a')
        r = self.api.get('/api/django/installations/parc/?annee=2026')
        self.assertIn(a.id, ids_of(r))
        r = self.api.get('/api/django/installations/parc/?annee=2099')
        self.assertNotIn(a.id, ids_of(r))

    def test_carte_returns_only_geolocated(self):
        a = self._received_inst(ref='a')
        r = self.api.get('/api/django/installations/parc/carte/')
        self.assertEqual(r.status_code, 200)
        pts = r.data
        self.assertTrue(any(p['id'] == a.id for p in pts))
        for p in pts:
            self.assertIsNotNone(p['gps_lat'])
            self.assertIsNotNone(p['gps_lng'])

    def test_hub_aggregates_related_objects(self):
        from apps.sav.models import (
            Equipement, Ticket, ContratMaintenance,
        )
        a = self._received_inst(ref='a')
        eq = Equipement.objects.filter(installation=a).first()
        Ticket.objects.create(
            company=self.company, reference='SAV-1', client=a.client,
            installation=a, equipement=eq)
        ContratMaintenance.objects.create(
            company=self.company, installation=a, client=a.client,
            date_debut='2026-06-20')
        r = self.api.get(f'/api/django/installations/parc/{a.id}/hub/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(len(r.data['equipements']), 2)
        self.assertEqual(len(r.data['tickets']), 1)
        self.assertEqual(len(r.data['contrats_maintenance']), 1)
        self.assertEqual(r.data['monitoring']['statut'], 'non_configure')

    def test_parc_no_buy_price_exposed(self):
        a = self._received_inst(ref='a')
        r = self.api.get(f'/api/django/installations/parc/{a.id}/hub/')
        blob = str(r.data).lower()
        self.assertNotIn('prix_achat', blob)

    def test_parc_company_scoped(self):
        a = self._received_inst(ref='a')
        other = make_company(slug='pl-other', nom='PL Other')
        ub = User.objects.create_user(
            username='pl_b', password='x', role_legacy='admin', company=other)
        r = auth(ub).get('/api/django/installations/parc/')
        self.assertNotIn(a.id, ids_of(r))
        r2 = auth(ub).get(f'/api/django/installations/parc/{a.id}/hub/')
        self.assertEqual(r2.status_code, 404)
