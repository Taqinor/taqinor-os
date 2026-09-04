"""ARC26 — activation des nouvelles cibles génériques ``records``.

Les 4 cibles ajoutées par la lane ARC (ARC8 : ``contrats.contrat`` +
``flotte.vehicule`` ; ARC26 : ``gestion_projet.projet`` + ``ao.appeloffre``)
sont actives dans ``ALLOWED_TARGETS`` : ``resolve_target`` les accepte
(scopé société) et l'API générique fonctionne dessus (commentaire posé sur un
projet / un appel d'offres). Isolation multi-tenant asservie.
"""
from testkit.base import TenantAPITestCase

from apps.records.models import ALLOWED_TARGETS
from apps.records.serializers import resolve_target


def _make_targets(company):
    """Construit une instance minimale de chacune des 4 nouvelles cibles."""
    from apps.contrats.models import Contrat
    from apps.flotte.models import Vehicule
    from apps.gestion_projet.models import Projet
    from apps.ao.models import AppelOffre
    return {
        'contrats.contrat': Contrat.objects.create(
            company=company, objet='Maintenance PV'),
        'flotte.vehicule': Vehicule.objects.create(
            company=company, immatriculation='5678-B-40'),
        'gestion_projet.projet': Projet.objects.create(
            company=company, code='PRJ-1', nom='Centrale 100 kWc'),
        'ao.appeloffre': AppelOffre.objects.create(
            company=company, reference='AO-2026-01', objet='Pompage solaire'),
    }


class TestNewAllowedTargets(TenantAPITestCase):
    def test_the_four_lane_targets_are_whitelisted(self):
        for pair in [('contrats', 'contrat'), ('flotte', 'vehicule'),
                     ('gestion_projet', 'projet'), ('ao', 'appeloffre')]:
            self.assertIn(pair, ALLOWED_TARGETS)

    def test_resolve_target_accepts_all_four(self):
        targets = _make_targets(self.company)
        for label, obj in targets.items():
            ct, resolved = resolve_target(label, obj.pk, self.company)
            self.assertEqual(resolved.pk, obj.pk, label)
            self.assertEqual(f'{ct.app_label}.{ct.model}', label)

    def test_resolve_target_rejects_other_company(self):
        """Une cible d'une AUTRE société lève ValueError (jamais de fuite)."""
        targets = _make_targets(self.other_company)
        for label, obj in targets.items():
            with self.assertRaises(ValueError, msg=label):
                resolve_target(label, obj.pk, self.company)

    def test_comment_api_on_projet_and_appeloffre(self):
        """L'API générique (records.Comment) fonctionne sur les cibles ARC26."""
        targets = _make_targets(self.company)
        api = self.client_as(role='responsable')
        for label in ('gestion_projet.projet', 'ao.appeloffre'):
            r = api.post('/api/django/records/comments/', {
                'model': label, 'id': targets[label].pk,
                'body': f'Note sur {label}',
            }, format='json')
            self.assertEqual(r.status_code, 201, (label, r.content))
            self.assertEqual(r.data['target_model'], label)


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
