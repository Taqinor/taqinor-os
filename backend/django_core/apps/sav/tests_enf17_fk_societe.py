"""ENF17 — SAV : toute FK inscriptible des sérialiseurs est bornée société.

Avant ENF17, 31 FK SAV (``scripts/fk_scoping_allow.txt``) acceptaient l'id
d'une ligne d'une AUTRE société : équipement, chantier, client, produit,
ticket, équipe, cause/remède, modèle de feuille… Attendu désormais, pour
chacune : l'id d'ailleurs reçoit EXACTEMENT la réponse d'un id absent (400
« objet inexistant », aucun oracle d'existence) et l'id de sa propre société
reste accepté.

Les sérialiseurs sont éprouvés directement (requête en contexte, ``partial``
pour ne fournir que le champ visé) ; deux chemins HTTP réels (PATCH ticket,
POST d'activité planifiée) confirment le 400 de bout en bout.

Run:
    python manage.py test apps.sav.tests_enf17_fk_societe -v 2
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
    CategorieEquipement, CauseDefaillance, Equipement, EquipeMaintenance,
    RemedeDefaillance, Ticket, WorksheetMaintenanceModele,
)
from apps.sav.serializers_maintenance import ContratMaintenanceSerializer
from apps.stock.models import Produit
from authentication.models import Company

User = get_user_model()

ID_ABSENT = 99999999


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


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
