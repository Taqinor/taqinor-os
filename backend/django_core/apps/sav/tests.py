"""
Tests du module Après-vente — parc d'équipements & tickets SAV (2026-06-13).

Couvre :
  * calcul des dates de fin de garantie (= date_pose + Produit.garantie_mois ;
    vide quand la durée n'est pas renseignée) ;
  * filtres du parc global (par modèle, par état de garantie, expirant ≤ 90 j)
    et tri par date de fin de garantie ;
  * la garantie d'un ticket reflète l'équipement lié (sinon valeur manuelle) ;
  * un changement de statut écrit une ligne de chatter et refuse les statuts
    hors liste ;
  * lier une intervention à un ticket marche et ne casse pas le lien
    chantier→intervention existant ;
  * isolation par société sur tous les nouveaux modèles ;
  * numérotation de référence via l'utilitaire (SAV-AAAAMM-NNNN) ;
  * habilitations (equipement_voir/gerer, sav_voir/gerer).

Run :
    docker compose exec django_core python manage.py test apps.sav -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.installations.models import Installation
from apps.sav.models import (
    ContratMaintenance, Equipement, Ticket, TicketActivity,
)
from apps.sav.services import add_months

User = get_user_model()


def make_company(slug='sav-co', nom='Sav Co'):
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


def make_produit(company, nom='Onduleur X', sku='OND-X', marque='Huawei',
                 garantie_mois=None, garantie_production_mois=None):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku, marque=marque,
        prix_achat=Decimal('100'), prix_vente=Decimal('200'),
        garantie_mois=garantie_mois,
        garantie_production_mois=garantie_production_mois)


def make_installation(company, ref='CHT-T-1'):
    client = Client.objects.create(
        company=company, nom='Client', prenom='Test',
        email=f'c-{company.id}-{ref}@example.invalid')
    inst = Installation.objects.create(
        company=company, reference=ref, client=client)
    return inst, client


class TestWarrantyComputation(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='sav_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, self.client_obj = make_installation(self.company)

    def _create_equip(self, produit, date_pose):
        return self.api.post('/api/django/sav/equipements/', {
            'produit': produit.id, 'installation': self.inst.id,
            'numero_serie': 'SN-1', 'date_pose': date_pose,
        }, format='json')

    def test_fin_garantie_computes_from_garantie_mois(self):
        produit = make_produit(self.company, garantie_mois=120,
                               garantie_production_mois=300)
        r = self._create_equip(produit, '2020-01-15')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['date_fin_garantie'], '2030-01-15')
        self.assertEqual(r.data['date_fin_garantie_production'], '2045-01-15')

    def test_fin_garantie_empty_when_duration_unset(self):
        produit = make_produit(self.company, sku='OND-NOGAR', garantie_mois=None)
        r = self._create_equip(produit, '2020-01-15')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['date_fin_garantie'])
        self.assertEqual(r.data['garantie_etat'], 'non_renseignee')

    def test_fin_garantie_empty_when_no_pose_date(self):
        produit = make_produit(self.company, sku='OND-NODATE', garantie_mois=120)
        r = self.api.post('/api/django/sav/equipements/', {
            'produit': produit.id, 'installation': self.inst.id,
            'numero_serie': 'SN-2',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['date_fin_garantie'])

    def test_add_months_clamps_end_of_month(self):
        self.assertEqual(add_months(date(2021, 1, 31), 1), date(2021, 2, 28))
        self.assertEqual(add_months(date(2020, 1, 31), 1), date(2020, 2, 29))
        self.assertEqual(add_months(date(2020, 1, 15), 12), date(2021, 1, 15))


class TestEquipementFilters(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='sav_admin2', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, _ = make_installation(self.company)
        self.prod_a = make_produit(self.company, nom='Onduleur A', sku='A',
                                   marque='Huawei')
        self.prod_b = make_produit(self.company, nom='Panneau B', sku='B',
                                   marque='Canadian')
        today = timezone.localdate()
        # 4 états de garantie distincts (date posée directement sur la colonne).
        self.sous = Equipement.objects.create(
            company=self.company, produit=self.prod_a, installation=self.inst,
            numero_serie='SOUS', date_fin_garantie=today + timedelta(days=300))
        self.expire = Equipement.objects.create(
            company=self.company, produit=self.prod_a, installation=self.inst,
            numero_serie='EXP', date_fin_garantie=today + timedelta(days=30))
        self.hors = Equipement.objects.create(
            company=self.company, produit=self.prod_b, installation=self.inst,
            numero_serie='HORS', date_fin_garantie=today - timedelta(days=10))
        self.vide = Equipement.objects.create(
            company=self.company, produit=self.prod_b, installation=self.inst,
            numero_serie='VIDE', date_fin_garantie=None)

    def test_filter_by_model(self):
        r = self.api.get('/api/django/sav/equipements/',
                         {'produit': self.prod_a.id})
        got = set(ids_of(r))
        self.assertEqual(got, {self.sous.id, self.expire.id})

    def test_filter_by_marque(self):
        r = self.api.get('/api/django/sav/equipements/', {'marque': 'Canadian'})
        self.assertEqual(set(ids_of(r)), {self.hors.id, self.vide.id})

    def test_filter_expiring_soon(self):
        r = self.api.get('/api/django/sav/equipements/',
                         {'garantie': 'expire_bientot'})
        self.assertEqual(set(ids_of(r)), {self.expire.id})

    def test_filter_warranty_states(self):
        for etat, expected in [
            ('sous_garantie', {self.sous.id}),
            ('hors_garantie', {self.hors.id}),
            ('non_renseignee', {self.vide.id}),
        ]:
            r = self.api.get('/api/django/sav/equipements/', {'garantie': etat})
            self.assertEqual(set(ids_of(r)), expected, etat)

    def test_sort_by_fin_garantie(self):
        r = self.api.get('/api/django/sav/equipements/',
                         {'ordering': 'date_fin_garantie'})
        # Les vides (NULL) en premier sous tri ascendant Postgres, puis dates.
        ordered = [x['numero_serie'] for x in ids_payload(r)]
        # On vérifie l'ordre relatif des dates non nulles.
        non_null = [s for s in ordered if s != 'VIDE']
        self.assertEqual(non_null, ['HORS', 'EXP', 'SOUS'])


def ids_payload(resp):
    data = resp.data
    return data['results'] if isinstance(data, dict) and 'results' in data else data


class TestTicketWarrantyAndChatter(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='sav_admin3', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, self.client_obj = make_installation(self.company)
        self.produit = make_produit(self.company, garantie_mois=120)
        today = timezone.localdate()
        self.eq_sous = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            numero_serie='EQ-SOUS', date_fin_garantie=today + timedelta(days=400))
        self.eq_hors = Equipement.objects.create(
            company=self.company, produit=self.produit, installation=self.inst,
            numero_serie='EQ-HORS', date_fin_garantie=today - timedelta(days=400))

    def _open_ticket(self, **extra):
        body = {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'type': 'correctif', 'description': 'Panne onduleur',
        }
        body.update(extra)
        return self.api.post('/api/django/sav/tickets/', body, format='json')

    def test_reference_uses_utility(self):
        r = self._open_ticket()
        self.assertEqual(r.status_code, 201, r.data)
        prefix = 'SAV-' + timezone.now().strftime('%Y%m')
        self.assertTrue(r.data['reference'].startswith(prefix), r.data['reference'])

    def test_sous_garantie_from_linked_equipment(self):
        r = self._open_ticket(equipement=self.eq_sous.id)
        self.assertEqual(r.data['sous_garantie_effectif'], 'oui', r.data)
        r2 = self._open_ticket(equipement=self.eq_hors.id)
        self.assertEqual(r2.data['sous_garantie_effectif'], 'non', r2.data)

    def test_sous_garantie_manual_without_equipment(self):
        r = self._open_ticket(sous_garantie='a_determiner')
        self.assertEqual(r.data['sous_garantie_effectif'], 'a_determiner', r.data)
        tid = r.data['id']
        r2 = self.api.patch(f'/api/django/sav/tickets/{tid}/',
                            {'sous_garantie': 'oui'}, format='json')
        self.assertEqual(r2.data['sous_garantie_effectif'], 'oui', r2.data)

    def test_status_change_logs_chatter(self):
        tid = self._open_ticket().data['id']
        r = self.api.patch(f'/api/django/sav/tickets/{tid}/',
                           {'statut': 'en_cours'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        acts = TicketActivity.objects.filter(ticket_id=tid, kind='modification',
                                             field='statut')
        self.assertEqual(acts.count(), 1)
        self.assertEqual(acts.first().old_value, 'Nouveau')
        self.assertEqual(acts.first().new_value, 'En cours')
        self.assertEqual(acts.first().user_id, self.user.id)

    def test_invalid_status_rejected(self):
        tid = self._open_ticket().data['id']
        r = self.api.patch(f'/api/django/sav/tickets/{tid}/',
                           {'statut': 'pas_un_statut'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_default_list_shows_open_only(self):
        open_id = self._open_ticket().data['id']
        closed_id = self._open_ticket().data['id']
        self.api.patch(f'/api/django/sav/tickets/{closed_id}/',
                       {'statut': 'cloture'}, format='json')
        r = self.api.get('/api/django/sav/tickets/')
        got = set(ids_of(r))
        self.assertIn(open_id, got)
        self.assertNotIn(closed_id, got)
        r_all = self.api.get('/api/django/sav/tickets/', {'ouvert': 'tous'})
        self.assertIn(closed_id, set(ids_of(r_all)))

    def test_annuler_is_flag_with_reason(self):
        tid = self._open_ticket().data['id']
        r = self.api.post(f'/api/django/sav/tickets/{tid}/annuler/',
                          {'motif': 'Doublon'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['annule'])
        self.assertEqual(r.data['motif_annulation'], 'Doublon')
        self.assertTrue(Ticket.objects.filter(pk=tid).exists())


class TestTicketInterventionLink(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='sav_admin4', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, self.client_obj = make_installation(self.company)
        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-T-1', client=self.client_obj,
            installation=self.inst)

    def test_link_intervention_to_ticket(self):
        r = self.api.post('/api/django/installations/interventions/', {
            'installation': self.inst.id, 'ticket': self.ticket.id,
            'type_intervention': 'depannage',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        r2 = self.api.get('/api/django/installations/interventions/',
                          {'ticket': self.ticket.id})
        self.assertEqual(len(ids_of(r2)), 1)

    def test_existing_installation_link_still_works(self):
        # Intervention SANS ticket — comportement historique intact.
        r = self.api.post('/api/django/installations/interventions/', {
            'installation': self.inst.id, 'type_intervention': 'pose',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertIsNone(r.data['ticket'])
        r2 = self.api.get('/api/django/installations/interventions/',
                          {'installation': self.inst.id})
        self.assertEqual(len(ids_of(r2)), 1)


class TestTenantScoping(TestCase):
    def setUp(self):
        self.a = make_company(slug='sav-a', nom='A')
        self.b = make_company(slug='sav-b', nom='B')
        self.ua = User.objects.create_user(
            username='u_a', password='x', role_legacy='admin', company=self.a)
        self.ub = User.objects.create_user(
            username='u_b', password='x', role_legacy='admin', company=self.b)
        self.inst_a, self.client_a = make_installation(self.a, ref='CHT-A')
        self.prod_a = make_produit(self.a, sku='PA')
        self.eq_a = Equipement.objects.create(
            company=self.a, produit=self.prod_a, installation=self.inst_a,
            numero_serie='A-EQ')
        self.tk_a = Ticket.objects.create(
            company=self.a, reference='SAV-A-1', client=self.client_a,
            installation=self.inst_a)

    def test_other_company_cannot_see_equipment(self):
        api_b = auth(self.ub)
        self.assertEqual(ids_of(api_b.get('/api/django/sav/equipements/')), [])
        self.assertEqual(
            api_b.get(f'/api/django/sav/equipements/{self.eq_a.id}/').status_code,
            404)

    def test_other_company_cannot_see_ticket(self):
        api_b = auth(self.ub)
        self.assertEqual(
            ids_of(api_b.get('/api/django/sav/tickets/', {'ouvert': 'tous'})), [])
        self.assertEqual(
            api_b.get(f'/api/django/sav/tickets/{self.tk_a.id}/').status_code,
            404)

    def test_company_forced_server_side(self):
        # Même si B tente d'injecter company=A, le serveur force sa société.
        api_b = auth(self.ub)
        inst_b, client_b = make_installation(self.b, ref='CHT-B')
        r = api_b.post('/api/django/sav/tickets/', {
            'company': self.a.id, 'client': client_b.id,
            'installation': inst_b.id, 'type': 'correctif',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Ticket.objects.get(pk=r.data['id']).company_id, self.b.id)


class TestPermissions(TestCase):
    def setUp(self):
        self.company = make_company()
        self.inst, self.client_obj = make_installation(self.company)
        self.produit = make_produit(self.company)
        # Rôle fin « lecture seule SAV + équipements ».
        self.role_voir = Role.objects.create(
            company=self.company, nom='Lecteur SAV',
            permissions=['equipement_voir', 'sav_voir'])
        self.viewer = User.objects.create_user(
            username='viewer', password='x', company=self.company)
        self.viewer.role = self.role_voir
        self.viewer.save(update_fields=['role'])
        # Rôle fin « Commerciale » : voit le parc, ouvre/traite les tickets.
        self.role_com = Role.objects.create(
            company=self.company, nom='Commerciale',
            permissions=['equipement_voir', 'sav_voir', 'sav_gerer'])
        self.com = User.objects.create_user(
            username='com', password='x', company=self.company)
        self.com.role = self.role_com
        self.com.save(update_fields=['role'])

    def test_viewer_can_read_but_not_write(self):
        api = auth(self.viewer)
        self.assertEqual(api.get('/api/django/sav/equipements/').status_code, 200)
        self.assertEqual(api.get('/api/django/sav/tickets/').status_code, 200)
        # Pas de equipement_gerer → création refusée.
        r = api.post('/api/django/sav/equipements/', {
            'produit': self.produit.id, 'installation': self.inst.id,
        }, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        # Pas de sav_gerer → création de ticket refusée.
        r2 = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
        }, format='json')
        self.assertEqual(r2.status_code, 403, r2.data)

    def test_commerciale_can_open_and_work_tickets(self):
        api = auth(self.com)
        r = api.post('/api/django/sav/tickets/', {
            'client': self.client_obj.id, 'installation': self.inst.id,
            'type': 'correctif',
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        tid = r.data['id']
        r2 = api.patch(f'/api/django/sav/tickets/{tid}/',
                       {'statut': 'en_cours'}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
        # Mais la Commerciale ne GÈRE pas le parc (pas de equipement_gerer).
        r3 = api.post('/api/django/sav/equipements/', {
            'produit': self.produit.id, 'installation': self.inst.id,
        }, format='json')
        self.assertEqual(r3.status_code, 403, r3.data)


class TestContratMaintenance(TestCase):
    """Contrats de maintenance préventive : échéance calculée à la lecture,
    génération de ticket à la demande, idempotence, scoping société."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='sav_contrat', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.user)
        self.inst, self.client_obj = make_installation(self.company)

    def _create(self, **extra):
        body = {'installation': self.inst.id, 'intervalle_mois': 12,
                'date_debut': '2026-01-01'}
        body.update(extra)
        return self.api.post('/api/django/sav/contrats/', body, format='json')

    def test_create_resolves_client_from_chantier(self):
        # Le client n'est jamais lu du corps : il vient du chantier.
        r = self.api.post('/api/django/sav/contrats/', {
            'installation': self.inst.id, 'intervalle_mois': 6,
            'date_debut': '2026-01-01', 'client': 999999,
        }, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        c = ContratMaintenance.objects.get(pk=r.data['id'])
        self.assertEqual(c.client_id, self.client_obj.id)
        self.assertEqual(c.company_id, self.company.id)

    def test_prochaine_visite_computed_on_the_fly(self):
        # Jamais visité → première échéance = date de début.
        r = self._create(date_debut='2026-01-01')
        self.assertEqual(r.data['prochaine_visite'], '2026-01-01')
        c = ContratMaintenance.objects.get(pk=r.data['id'])
        # Après une visite, échéance = visite + intervalle (calculé, non stocké).
        c.derniere_visite = date(2026, 1, 1)
        c.save(update_fields=['derniere_visite'])
        self.assertEqual(c.prochaine_visite, date(2027, 1, 1))

    def test_not_due_before_echeance(self):
        # Début dans le futur → pas due, aucun ticket même via génération.
        future = (timezone.localdate() + timedelta(days=400)).isoformat()
        r = self._create(date_debut=future)
        cid = r.data['id']
        self.assertFalse(r.data['est_due'])
        gen = self.api.post(f'/api/django/sav/contrats/{cid}/generer-dus/')
        self.assertEqual(gen.status_code, 200, gen.data)
        self.assertIsNone(gen.data['ticket_genere'])
        self.assertEqual(
            Ticket.objects.filter(installation=self.inst,
                                  type='preventif').count(), 0)

    def test_generate_due_creates_one_preventive_ticket(self):
        past = (timezone.localdate() - timedelta(days=10)).isoformat()
        r = self._create(date_debut=past)
        cid = r.data['id']
        self.assertTrue(r.data['est_due'])
        gen = self.api.post(f'/api/django/sav/contrats/{cid}/generer-dus/')
        self.assertEqual(gen.status_code, 200, gen.data)
        self.assertIsNotNone(gen.data['ticket_genere'])
        tickets = Ticket.objects.filter(installation=self.inst, type='preventif')
        self.assertEqual(tickets.count(), 1)
        self.assertEqual(tickets.first().statut, 'nouveau')
        # La dernière visite a avancé à l'échéance traitée.
        c = ContratMaintenance.objects.get(pk=cid)
        self.assertEqual(c.derniere_visite.isoformat(), past)

    def test_generation_is_idempotent(self):
        past = (timezone.localdate() - timedelta(days=10)).isoformat()
        cid = self._create(date_debut=past).data['id']
        # Deux appels successifs : un seul ticket.
        self.api.post(f'/api/django/sav/contrats/{cid}/generer-dus/')
        second = self.api.post(f'/api/django/sav/contrats/{cid}/generer-dus/')
        self.assertIsNone(second.data['ticket_genere'])
        self.assertEqual(
            Ticket.objects.filter(installation=self.inst,
                                  type='preventif').count(), 1)

    def test_a_venir_lists_due_without_generating(self):
        past = (timezone.localdate() - timedelta(days=10)).isoformat()
        far = (timezone.localdate() + timedelta(days=400)).isoformat()
        due_id = self._create(date_debut=past).data['id']
        self._create(date_debut=far)
        r = self.api.get('/api/django/sav/contrats/a-venir/')
        self.assertEqual(r.status_code, 200, r.data)
        got = {row['id'] for row in r.data}
        self.assertEqual(got, {due_id})
        # La simple lecture ne génère AUCUN ticket.
        self.assertEqual(
            Ticket.objects.filter(installation=self.inst,
                                  type='preventif').count(), 0)

    def test_a_venir_with_generer_creates_tickets(self):
        past = (timezone.localdate() - timedelta(days=10)).isoformat()
        self._create(date_debut=past)
        r = self.api.get('/api/django/sav/contrats/a-venir/', {'generer': '1'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(
            Ticket.objects.filter(installation=self.inst,
                                  type='preventif').count(), 1)

    def test_inactive_contract_never_due(self):
        past = (timezone.localdate() - timedelta(days=10)).isoformat()
        cid = self._create(date_debut=past, actif=False).data['id']
        gen = self.api.post(f'/api/django/sav/contrats/{cid}/generer-dus/')
        self.assertIsNone(gen.data['ticket_genere'])
        r = self.api.get('/api/django/sav/contrats/a-venir/')
        self.assertEqual([row['id'] for row in r.data], [])

    def test_tenant_scoping(self):
        cid = self._create(date_debut='2026-01-01').data['id']
        other = make_company(slug='sav-other', nom='Other')
        ou = User.objects.create_user(
            username='other_u', password='x', role_legacy='admin',
            company=other)
        api_o = auth(ou)
        self.assertEqual(
            ids_of(api_o.get('/api/django/sav/contrats/')), [])
        self.assertEqual(
            api_o.get(f'/api/django/sav/contrats/{cid}/').status_code, 404)
