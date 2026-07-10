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
