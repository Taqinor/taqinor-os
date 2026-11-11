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
        # CI #997 api-fuzz : id d'ailleurs = id inconnu → 404 (``IdInconnu404Mixin``).
        self.assertEqual(r.status_code, 409, r.data)  # ENF45 a : mise à jour = 409
        self.assertIn(champ, r.data)
        self.assertNotIn('secrète', str(r.data))
        self.ticket.refresh_from_db()
        self.assertIsNone(getattr(self.ticket, f'{champ}_id'))
        # Création refusée aussi.
        avant = Ticket.objects.count()
        r2 = self.api.post(URL, {
            'client': self.client_a.id, 'type': 'correctif',
            'description': 'x', champ: valeur}, format='json')
        self.assertEqual(r2.status_code, 404, r2.data)
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
        self.assertEqual(r_abs.status_code, 409)  # ENF45 a : mise à jour = 409
        self.assertEqual(
            str(r_etr.data['categorie'][0]).replace(str(self.cat_b.id), '?'),
            str(r_abs.data['categorie'][0]).replace('999999', '?'))

    def test_non_facturable_fige(self):
        r = self._patch({'non_facturable': True, 'est_recidive': True})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertFalse(self.ticket.non_facturable)
        self.assertFalse(self.ticket.est_recidive)

    def test_pointeurs_facturation_figes(self):
        """ACSV54 : un Technicien ne change ni les pointeurs de facturation,
        ni la date d'ouverture ; la couverture lui est refusée (403) et le
        responsable la change avec une note au chatter."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        from apps.sav.models import TicketActivity
        role = Role.objects.create(
            company=self.a, nom='Technicien ACSV54',
            permissions=list(TECHNICIEN_PERMISSIONS))
        tech = User.objects.create_user(
            username='acsv54_tech', password='x', company=self.a, role=role)
        # Portée « équipe » du Technicien : le ticket lui est affecté.
        Ticket.objects.filter(pk=self.ticket.pk).update(
            technicien_responsable=tech,
            facture_id_ext=7, devis_id_ext=8, lead_id_ext=9,
            date_ouverture=date(2026, 1, 5))
        api_tech = _api(tech)
        for corps in ({'facture_id_ext': None}, {'devis_id_ext': 9},
                      {'lead_id_ext': 9}, {'intervention_origine_id': 9},
                      {'date_ouverture': '2020-01-01'}):
            r = api_tech.patch(f'{URL}{self.ticket.id}/', corps, format='json')
            self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual((self.ticket.facture_id_ext, self.ticket.devis_id_ext,
                          self.ticket.lead_id_ext), (7, 8, 9))
        self.assertIsNone(self.ticket.intervention_origine_id)
        self.assertEqual(self.ticket.date_ouverture, date(2026, 1, 5))
        r = api_tech.patch(f'{URL}{self.ticket.id}/',
                           {'couverture': 'garantie'}, format='json')
        self.assertEqual(r.status_code, 403, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.couverture, 'a_determiner')
        r = self._patch({'couverture': 'garantie'})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.couverture, 'garantie')
        self.assertTrue(TicketActivity.objects.filter(
            ticket=self.ticket, body__contains='Couverture :').exists())

    def test_creation_couverture_et_ouverture_reservees(self):
        """ACSV107 : à la CRÉATION aussi, un Technicien ne pose ni la
        couverture (403, 0 ticket) ni une date d'ouverture ancienne (date du
        jour) ; le responsable pose les deux."""
        from django.utils import timezone
        from apps.roles.models import Role
        from apps.roles.permissions_registre import TECHNICIEN_PERMISSIONS
        role = Role.objects.create(
            company=self.a, nom='Technicien ACSV107',
            permissions=list(TECHNICIEN_PERMISSIONS))
        tech = User.objects.create_user(
            username='acsv107_tech', password='x', company=self.a, role=role)
        produit = Produit.objects.create(
            company=self.a, nom='Onduleur 2019', sku='ACSV107-OND',
            prix_achat=Decimal('10'), prix_vente=Decimal('20'))
        equipement = Equipement.objects.create(
            company=self.a, produit=produit, client_vente=self.client_a,
            numero_serie='ACSV107', date_pose=date(2019, 3, 1),
            date_fin_garantie=date(2024, 3, 1))
        base = {'client': self.client_a.id, 'equipement': equipement.id,
                'type': 'correctif'}
        api_tech = _api(tech)
        avant = Ticket.objects.count()
        r = api_tech.post(URL, {**base, 'description': 'a',
                                'couverture': 'garantie'}, format='json')
        self.assertEqual(r.status_code, 403)
        self.assertIn('detail', r.data)
        self.assertEqual(Ticket.objects.count(), avant)
        r = api_tech.post(URL, {**base, 'description': 'b',
                                'date_ouverture': '2020-01-01'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['couverture_proposee'], 'facturable')
        ticket = Ticket.objects.get(pk=r.data['id'])
        self.assertEqual(ticket.couverture, 'a_determiner')
        self.assertEqual(ticket.date_ouverture, timezone.localdate())
        r = self.api.post(URL, {**base, 'description': 'c',
                                'couverture': 'garantie',
                                'date_ouverture': '2020-01-01'}, format='json')
        self.assertEqual(r.status_code, 201)
        ticket = Ticket.objects.get(pk=r.data['id'])
        self.assertEqual((ticket.couverture, ticket.date_ouverture),
                         ('garantie', date(2020, 1, 1)))

    def test_creation_affectee_exige_sav_reassign(self):
        """ADRG40 (C-ADRG-015) — créer un ticket DÉJÀ affecté (technicien ou
        équipe) est la même réaffectation que le PATCH : le rôle LIVRÉ
        Technicien reçoit 403 et aucun ticket n'est créé ; sans affectation,
        201 ; le rôle livré Responsable et le compte hérité responsable
        créent affecté (201). Mutant : retirer l'entrée ``create`` ⇒ échec."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import CANONICAL_SYSTEM_ROLES
        livres = dict(CANONICAL_SYSTEM_ROLES)

        def compte(nom, legacy='normal'):
            role = None if nom is None else Role.objects.create(
                company=self.a, nom=nom, est_systeme=True,
                permissions=list(livres[nom]))
            return _api(User.objects.create_user(
                username=f'adrg40_{(nom or "herite").replace(" ", "_").lower()}',
                password='x', role_legacy=legacy, company=self.a, role=role))

        equipe = EquipeMaintenance.objects.create(company=self.a, nom='Équipe A')
        base = {'client': self.client_a.id, 'type': 'correctif',
                'description': 'panne'}
        technicien = compte('Technicien')
        avant = Ticket.objects.count()
        for extra in ({'technicien_responsable': self.tech_a.id},
                      {'equipe': equipe.id}):
            r = technicien.post(URL, {**base, **extra}, format='json')
            self.assertEqual(r.status_code, 403, (extra, r.data))
            self.assertIn('sav_reassign', str(r.data))
        self.assertEqual(Ticket.objects.count(), avant)
        self.assertEqual(
            technicien.post(URL, base, format='json').status_code, 201)
        for api in (compte('Responsable'), compte(None, 'responsable')):
            r = api.post(URL, {**base, 'technicien_responsable': self.tech_a.id,
                               'equipe': equipe.id}, format='json')
            self.assertEqual(r.status_code, 201, r.data)

    def test_cout_fige(self):
        r = self._patch({'cout': '999.00'})
        self.assertEqual(r.status_code, 200, r.data)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.cout, Decimal('100.00'))

    def test_cout_masque_sans_prix_achat_voir(self):
        """ALEC17 (C-ALEC-015) — le coût interne d'un ticket ne sort qu'avec
        ``prix_achat_voir`` : Technicien sans la clé ``cout`` (détail et
        liste), Directeur « 300.00 ». Mutant : vider ``champs_montants_achat``."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            DIRECTEUR_PERMISSIONS, TECHNICIEN_PERMISSIONS)

        def compte(nom, permissions):
            role = Role.objects.create(company=self.a, nom=f'{nom} ALEC17',
                                       permissions=list(permissions))
            return User.objects.create_user(
                username=f'alec17-{nom}', password='x', company=self.a, role=role)
        tech, directeur = (compte('tech', TECHNICIEN_PERMISSIONS),
                           compte('dir', DIRECTEUR_PERMISSIONS))
        Ticket.objects.filter(pk=self.ticket.pk).update(
            cout=Decimal('300.00'), technicien_responsable=tech)
        for user, attendu in ((tech, None), (directeur, '300.00')):
            api = _api(user)
            detail = api.get(f'{URL}{self.ticket.id}/')
            self.assertEqual(detail.status_code, 200, detail.data)
            liste = api.get(URL)
            self.assertEqual(liste.status_code, 200, liste.data)
            lignes = liste.data.get('results', liste.data)
            (ligne,) = [t for t in lignes if t['id'] == self.ticket.id]
            for donnees in (detail.data, ligne):
                self.assertEqual(donnees.get('cout'), attendu)
                if attendu is None:
                    self.assertNotIn('cout', donnees)

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
                ('installation', 'installation'), ('produit', 'produit')):
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
        self.assertEqual(r.status_code, 409, r.data)  # ENF45 a : mise à jour = 409
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
