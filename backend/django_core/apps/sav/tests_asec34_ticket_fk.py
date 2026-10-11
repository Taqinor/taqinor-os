"""ASEC34 — ticket SAV : FK inscriptibles bornées à la société, champs posés
par le serveur figés.

Constat C-ASEC-005 site (g) + C-ASEC-009 volet ticket : ``TicketSerializer``
acceptait l'id d'un technicien, d'une catégorie de ticket ou d'une catégorie
d'équipement d'une AUTRE société, et laissait PATCHer ``non_facturable``,
``est_recidive`` et ``cout``. Attendu : un id d'ailleurs reçoit la même
réponse qu'un id absent (400), et les trois champs serveur restent inchangés
en base après un PATCH.

ENF17 — étendu à TOUTES les FK inscriptibles des sérialiseurs SAV (31 sites :
équipement, ticket, pièces, prêt, garantie, KB, alarme, catégorie,
immobilisation, relevé, compatibilité, feuille de maintenance, contrat de
maintenance) : l'id d'ailleurs = l'id absent (400), l'id de la société reste
accepté (``FkSavBorneesSocieteTests``).
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.installations.models import Installation
from apps.sav import serializers as S
from apps.sav.models import (
    CategorieEquipement, CategorieTicket, CauseDefaillance, Equipement,
    EquipeMaintenance, RemedeDefaillance, Ticket, WorksheetMaintenanceModele,
)
from apps.sav.serializers_maintenance import ContratMaintenanceSerializer
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

URL = '/api/django/sav/tickets/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TicketFkEtChampsServeurTests(TestCase):
    def setUp(self):
        self.a = Company.objects.create(nom='ASEC34 A', slug='asec34-a')
        self.b = Company.objects.create(nom='ASEC34 B', slug='asec34-b')
        self.user_a = User.objects.create_user(
            username='asec34_admin_a', password='x', role_legacy='admin',
            company=self.a)
        self.tech_a = User.objects.create_user(
            username='asec34_tech_a', password='x',
            role_legacy='normal', company=self.a)
        self.tech_b = User.objects.create_user(
            username='asec34_tech_b', password='x',
            role_legacy='normal', company=self.b)
        self.cat_a = CategorieTicket.objects.create(
            company=self.a, libelle='Panne A')
        self.cat_b = CategorieTicket.objects.create(
            company=self.b, libelle='Panne B secrète')
        self.cateq_a = CategorieEquipement.objects.create(
            company=self.a, nom='Onduleurs A')
        self.cateq_b = CategorieEquipement.objects.create(
            company=self.b, nom='Pompes B secrètes')
        self.client_a = Client.objects.create(company=self.a, nom='Client A')
        self.ticket = Ticket.objects.create(
            company=self.a, reference='ASEC34-1', client=self.client_a,
            cout=Decimal('100.00'))
        self.api = _api(self.user_a)

    def _patch(self, body):
        return self.api.patch(f'{URL}{self.ticket.id}/', body, format='json')

    def _assert_refus(self, champ, valeur):
        r = self._patch({champ: valeur})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn(champ, r.data)
        self.assertNotIn('secrète', str(r.data))
        self.ticket.refresh_from_db()
        self.assertIsNone(getattr(self.ticket, f'{champ}_id'))
        # Création refusée aussi.
        avant = Ticket.objects.count()
        r2 = self.api.post(URL, {
            'client': self.client_a.id, 'type': 'correctif',
            'description': 'x', champ: valeur}, format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertIn(champ, r2.data)
        self.assertEqual(Ticket.objects.count(), avant)

    def test_technicien_etranger_400(self):
        self._assert_refus('technicien_responsable', self.tech_b.id)

    def test_categorie_etrangere_400(self):
        self._assert_refus('categorie', self.cat_b.id)

    def test_categorie_equipement_etrangere_400(self):
        self._assert_refus('categorie_equipement', self.cateq_b.id)

    def test_id_inexistant_meme_reponse(self):
        r_etr = self._patch({'categorie': self.cat_b.id})
        r_abs = self._patch({'categorie': 999999})
        self.assertEqual(r_abs.status_code, 400)
        self.assertEqual(
            str(r_etr.data['categorie'][0]).replace(str(self.cat_b.id), '?'),
            str(r_abs.data['categorie'][0]).replace('999999', '?'))

    def test_non_facturable_fige(self):
        r = self._patch({'non_facturable': True, 'est_recidive': True})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.non_facturable)
        self.assertFalse(self.ticket.est_recidive)

    def test_cout_fige(self):
        r = self._patch({'cout': '999.00'})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.cout, Decimal('100.00'))

    def test_ids_societe_ok(self):
        r = self._patch({
            'technicien_responsable': self.tech_a.id,
            'categorie': self.cat_a.id,
            'categorie_equipement': self.cateq_a.id})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.technicien_responsable_id, self.tech_a.id)
        self.assertEqual(self.ticket.categorie_id, self.cat_a.id)
        self.assertEqual(self.ticket.categorie_equipement_id, self.cateq_a.id)
        r2 = self.api.post(URL, {
            'client': self.client_a.id, 'type': 'correctif',
            'description': 'ok', 'technicien_responsable': self.tech_a.id,
            'categorie': self.cat_a.id}, format='json')
        self.assertEqual(r2.status_code, 201, r2.data)


ID_ABSENT = 99999999


class _Societe:
    """Un jeu complet de lignes cibles pour UNE société."""

    def __init__(self, company, suffixe):
        self.user = User.objects.create_user(
            username=f'enf17-sav-{suffixe}', password='x',
            role_legacy='admin', company=company)
        self.client = Client.objects.create(
            company=company, nom=f'Client {suffixe}')
        self.installation = Installation.objects.create(
            company=company, reference=f'ENF17-SAV-{suffixe}',
            client=self.client)
        self.produit = Produit.objects.create(
            company=company, nom=f'Produit {suffixe}',
            sku=f'ENF17-SAV-{suffixe}', prix_achat=Decimal('10'),
            prix_vente=Decimal('20'))
        self.categorie = CategorieEquipement.objects.create(
            company=company, nom=f'Onduleurs {suffixe}')
        self.equipe = EquipeMaintenance.objects.create(
            company=company, nom=f'Équipe {suffixe}')
        self.cause = CauseDefaillance.objects.create(
            company=company, nom=f'Cause {suffixe}')
        self.remede = RemedeDefaillance.objects.create(
            company=company, nom=f'Remède {suffixe}')
        self.modele = WorksheetMaintenanceModele.objects.create(
            company=company, nom=f'Feuille {suffixe}')
        self.equipement = Equipement.objects.create(
            company=company, produit=self.produit,
            installation=self.installation,
            numero_serie=f'ENF17-SAV-SN-{suffixe}')
        self.ticket = Ticket.objects.create(
            company=company, reference=f'ENF17-SAV-T-{suffixe}',
            client=self.client)


class FkSavBorneesSocieteTests(TestCase):
    def setUp(self):
        self.co_a = Company.objects.create(nom='enf17-sav-a', slug='enf17-sav-a')
        self.co_b = Company.objects.create(nom='enf17-sav-b', slug='enf17-sav-b')
        self.a = _Societe(self.co_a, 'A')
        self.b = _Societe(self.co_b, 'B')
        self.ctx = {'request': SimpleNamespace(user=self.a.user)}

    # ── aide ─────────────────────────────────────────────────────────────

    def _assert_borne(self, cls, champ, attribut):
        """``champ`` de ``cls`` : id d'ailleurs = id absent (400), id de la
        société accepté. ``attribut`` désigne la ligne cible dans ``_Societe``."""
        propre = getattr(self.a, attribut)
        etranger = getattr(self.b, attribut)
        with self.subTest(serializer=cls.__name__, champ=champ):
            ser = cls(data={champ: etranger.pk}, partial=True,
                      context=self.ctx)
            self.assertFalse(ser.is_valid())
            self.assertIn(champ, ser.errors)
            self.assertEqual(ser.errors[champ][0].code, 'does_not_exist')
            absent = cls(data={champ: ID_ABSENT}, partial=True,
                         context=self.ctx)
            self.assertFalse(absent.is_valid())
            self.assertEqual(
                str(ser.errors[champ][0]).replace(str(etranger.pk), '<ID>'),
                str(absent.errors[champ][0]).replace(str(ID_ABSENT), '<ID>'))
            champ_lie = cls(context=self.ctx).fields[champ]
            self.assertEqual(champ_lie.to_internal_value(propre.pk), propre)

    # ── sérialiseurs ─────────────────────────────────────────────────────

    def test_equipement(self):
        for champ, attribut in (
                ('categorie', 'categorie'), ('client_vente', 'client'),
                ('installation', 'installation'), ('produit', 'produit'),
                ('remplace_par_ticket', 'ticket')):
            self._assert_borne(S.EquipementSerializer, champ, attribut)

    def test_ticket(self):
        for champ, attribut in (
                ('cause', 'cause'), ('client', 'client'),
                ('equipe', 'equipe'), ('equipement', 'equipement'),
                ('installation', 'installation'), ('remede', 'remede')):
            self._assert_borne(S.TicketSerializer, champ, attribut)

    def test_activite_a_faire_assigne(self):
        self._assert_borne(S.TicketActiviteAFaireSerializer, 'assigne', 'user')

    def test_produit_des_pieces_et_kb(self):
        for cls in (S.PieceRetireeSerializer, S.PieceConsommeeSerializer,
                    S.KbArticleSerializer, S.PretEquipementSerializer):
            self._assert_borne(cls, 'produit', 'produit')

    def test_ticket_et_equipement_lies(self):
        for cls, champ, attribut in (
                (S.PretEquipementSerializer, 'ticket', 'ticket'),
                (S.WarrantyClaimSerializer, 'equipement', 'equipement'),
                (S.WarrantyClaimSerializer, 'ticket', 'ticket'),
                (S.AlarmeOnduleurSerializer, 'equipement', 'equipement'),
                (S.EquipementDowntimeSerializer, 'equipement', 'equipement'),
                (S.EquipementDowntimeSerializer, 'ticket', 'ticket'),
                (S.ReleveCompteurEquipementSerializer, 'equipement',
                 'equipement'),
                (S.TicketWorksheetSerializer, 'ticket', 'ticket'),
                (S.TicketWorksheetSerializer, 'modele', 'modele')):
            self._assert_borne(cls, champ, attribut)

    def test_categorie_equipe_responsable(self):
        self._assert_borne(
            S.CategorieEquipementSerializer, 'equipe_responsable', 'equipe')

    def test_compatibilite_piece(self):
        for champ in ('piece', 'produit_equipement', 'remplace_par'):
            self._assert_borne(S.CompatibilitePieceSerializer, champ, 'produit')

    def test_contrat_maintenance(self):
        for champ, attribut in (('client', 'client'),
                                ('installation', 'installation')):
            self._assert_borne(ContratMaintenanceSerializer, champ, attribut)

    # ── bout en bout ─────────────────────────────────────────────────────

    def test_patch_ticket_equipement_etranger_400(self):
        api = _api(self.a.user)
        url = f'/api/django/sav/tickets/{self.a.ticket.pk}/'
        r = api.patch(url, {'equipement': self.b.equipement.pk},
                      format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('equipement', r.data)
        self.a.ticket.refresh_from_db()
        self.assertIsNone(self.a.ticket.equipement_id)
        r_ok = api.patch(url, {'cause': self.a.cause.pk,
                               'remede': self.a.remede.pk}, format='json')
        self.assertEqual(r_ok.status_code, 200, r_ok.data)
        self.a.ticket.refresh_from_db()
        self.assertEqual(self.a.ticket.cause_id, self.a.cause.pk)

    def test_post_activite_assigne_etranger_400(self):
        api = _api(self.a.user)
        url = f'/api/django/sav/tickets/{self.a.ticket.pk}/activites/'
        corps = {'type': 'appel', 'titre': 'Rappel',
                 'echeance': date.today().isoformat()}
        r = api.post(url, {**corps, 'assigne': self.b.user.pk},
                     format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('assigne', r.data)
        r_ok = api.post(url, {**corps, 'assigne': self.a.user.pk},
                        format='json')
        self.assertEqual(r_ok.status_code, 201, r_ok.data)
