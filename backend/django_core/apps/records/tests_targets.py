"""AUD416 — une cible à ``company_id IS NULL`` n'est pas partagée entre
sociétés (garde de diffusion sur ``resolve_target``/``notify_followers``).

SOLMVP20 — les tests ARC26 des 4 cibles ajoutées par la lane ARC (contrats,
flotte, gestion_projet, ao — toutes des apps PARQUÉES, Groupe SOLMVP) ont été
retirés avec les apps elles-mêmes ; ``ALLOWED_TARGETS`` continue de résoudre
dynamiquement depuis les manifestes des apps GARDÉES (``core.platform``,
ARC30 — voir ``apps/records/models.py``), rien à figer ici.
"""
from django.test import TestCase
from testkit.base import TenantAPITestCase

from apps.records.serializers import resolve_target


class Aud416CibleSansSocieteTests(TenantAPITestCase):
    """AUD416 — une cible à ``company_id IS NULL`` n'est PAS partagée.

    ``resolve_target`` la laissait passer pour n'importe quel appelant (le
    garde disait ``obj_company not in (None, company.id)``), et
    ``notify_followers`` ne filtrait que sur ``content_type``+``object_id``.
    Sur une telle cible — schéma-permis pour 13 des 39 cibles autorisées,
    ``crm.Client`` en tête — deux sociétés attachaient notes et pièces jointes
    sans le savoir, et chaque note d'une société notifiait les followers de
    l'autre. La LECTURE, elle, restait scopée : c'est une fuite de DIFFUSION,
    pas de lecture.
    """

    def _client_sans_societe(self):
        from apps.crm.models import Client
        # `company` est nullable au niveau du SCHÉMA sur ce modèle : on force
        # l'état que rien n'empêche en base.
        return Client.objects.create(nom='Orphelin', prenom='Sans société')

    def test_resolve_target_refuse_une_cible_sans_societe(self):
        cible = self._client_sans_societe()
        self.assertIsNone(cible.company_id)
        with self.assertRaises(ValueError):
            resolve_target('crm.client', cible.pk, self.company)

    def test_refusee_aussi_pour_lautre_societe(self):
        """Le refus vaut pour TOUT appelant — sinon la cible reste partagée."""
        cible = self._client_sans_societe()
        with self.assertRaises(ValueError):
            resolve_target('crm.client', cible.pk, self.other_company)

    def test_une_cible_normale_reste_acceptee(self):
        from apps.crm.models import Client
        normal = Client.objects.create(
            company=self.company, nom='Normal', prenom='Client')
        ct, resolved = resolve_target('crm.client', normal.pk, self.company)
        self.assertEqual(resolved.pk, normal.pk)
        self.assertEqual(f'{ct.app_label}.{ct.model}', 'crm.client')

    def test_la_diffusion_ne_traverse_plus_les_societes(self):
        """Un follower d'une AUTRE société ne reçoit plus le corps de la note."""
        from django.contrib.contenttypes.models import ContentType
        from apps.crm.models import Client
        from apps.records.models import Follower
        from apps.records.services import notify_followers
        from testkit.factories import UserFactory

        cible = Client.objects.create(
            company=self.company, nom='Cible', prenom='Suivie')
        ct = ContentType.objects.get_for_model(Client)
        mien = UserFactory(company=self.company)
        etranger = UserFactory(company=self.other_company)
        Follower.objects.create(
            company=self.company, content_type=ct, object_id=cible.pk,
            user=mien)
        Follower.objects.create(
            company=self.other_company, content_type=ct, object_id=cible.pk,
            user=etranger)

        envoyes = notify_followers(
            content_type=ct, object_id=cible.pk, title='Note',
            body='Contenu confidentiel')

        # Seul le follower de la société PROPRIÉTAIRE est notifié.
        self.assertEqual(envoyes, 1)

    def test_diffusion_normale_inchangee(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.crm.models import Client
        from apps.records.models import Follower
        from apps.records.services import notify_followers
        from testkit.factories import UserFactory

        cible = Client.objects.create(
            company=self.company, nom='Cible2', prenom='Suivie')
        ct = ContentType.objects.get_for_model(Client)
        Follower.objects.create(
            company=self.company, content_type=ct, object_id=cible.pk,
            user=UserFactory(company=self.company))
        self.assertEqual(
            notify_followers(content_type=ct, object_id=cible.pk,
                             title='Note', body='ok'),
            1)


class Acvi6PorteeDesCiblesLeadTests(TestCase):
    """ACVI6 — pièces et commentaires d'un lead hors portée : absents."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.contenttypes.models import ContentType

        from apps.crm.models import Lead
        from apps.records.models import Attachment
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            CANONICAL_SYSTEM_ROLES, COMMERCIAL_PERMISSIONS)
        from authentication.models import Company

        User = get_user_model()
        self.company = Company.objects.create(nom='ACVI6', slug='acvi6')
        commercial = Role.objects.create(
            company=self.company, nom='Commercial soi',
            permissions=list(COMMERCIAL_PERMISSIONS))
        rh = Role.objects.create(
            company=self.company, nom='RH',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Admin RH']))
        self.c1 = User.objects.create_user(
            username='acvi6-c1', password='x', company=self.company, role=commercial)
        self.c2 = User.objects.create_user(
            username='acvi6-c2', password='x', company=self.company, role=commercial)
        self.rh = User.objects.create_user(
            username='acvi6-rh', password='x', company=self.company, role=rh)
        self.lead = Lead.objects.create(
            company=self.company, nom='L1', owner=self.c1)
        self.piece = Attachment.objects.create(
            company=self.company, uploaded_by=self.c1,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=self.lead.pk, filename='p.pdf', file_key='k/p.pdf',
            size=1, mime='application/pdf')

    def _api(self, user):
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(user)
        return api

    def test_collegue_ne_liste_ni_ne_telecharge(self):
        base = '/api/django/records/attachments/'
        api = self._api(self.c2)
        cible = api.get(base, {'model': 'crm.lead', 'id': self.lead.pk})
        self.assertEqual(cible.status_code, 200, cible.data)
        self.assertEqual(cible.data['results'] if isinstance(cible.data, dict) else cible.data, [])
        libre = api.get(base)
        lignes = libre.data['results'] if isinstance(libre.data, dict) else libre.data
        self.assertNotIn(self.piece.pk, [r['id'] for r in lignes])
        self.assertEqual(api.get(f'{base}{self.piece.pk}/download/').status_code, 404)

    def test_collegue_ne_lit_ni_commentaire_ni_activite(self):
        """ACVI105 — sans cible, c2 « soi » ne lit ni le commentaire ni
        l'activité du lead de c1 (détail 404) ; l'activité qui lui est
        assignée reste lisible ; c1 voit tout."""
        from django.contrib.contenttypes.models import ContentType

        from apps.crm.models import Lead
        from apps.records.models import Activity, Comment
        ct = ContentType.objects.get_for_model(Lead)
        com = Comment.objects.create(company=self.company, content_type=ct,
                                     object_id=self.lead.pk, body='note c1', author=self.c1)
        act = Activity.objects.create(company=self.company, content_type=ct,
                                      object_id=self.lead.pk, summary='a c1',
                                      assigned_to=self.c1, created_by=self.c1)
        a_moi = Activity.objects.create(company=self.company, content_type=ct,
                                        object_id=self.lead.pk, summary='a c2',
                                        assigned_to=self.c2, created_by=self.c1)

        def ids(api, base):
            rep = api.get(base)
            self.assertEqual(rep.status_code, 200, rep.data)
            return [r['id'] for r in (rep.data['results'] if isinstance(rep.data, dict) else rep.data)]

        c2, c1 = self._api(self.c2), self._api(self.c1)
        coms, acts = '/api/django/records/comments/', '/api/django/records/activities/'
        self.assertNotIn(com.pk, ids(c2, coms))
        self.assertEqual(c2.get(f'{coms}{com.pk}/').status_code, 404)
        self.assertNotIn(act.pk, ids(c2, acts))
        self.assertEqual(c2.get(f'{acts}{act.pk}/').status_code, 404)
        self.assertIn(a_moi.pk, ids(c2, acts))
        self.assertEqual(c2.get(f'{acts}{a_moi.pk}/').status_code, 200)
        self.assertIn(com.pk, ids(c1, coms))
        self.assertTrue({act.pk, a_moi.pk} <= set(ids(c1, acts)))

    def test_role_sans_droit_crm_ne_depose_rien(self):
        from apps.records.models import Comment
        reponse = self._api(self.rh).post(
            '/api/django/records/comments/',
            {'model': 'crm.lead', 'id': self.lead.pk, 'body': 'x'}, format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)
        self.assertEqual(Comment.objects.filter(object_id=self.lead.pk).count(), 0)
