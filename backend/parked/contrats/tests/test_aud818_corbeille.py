"""AUD818 — supprimer un contrat l'envoie dans la corbeille 30 jours.

Preuve fonctionnelle du premier branchement de PRODUCTION de l'événement
`core.events.record_soft_deleted` : avant AUD818, la corbeille transverse
(`apps.trash`) était livrée complète mais rien ne l'alimentait — toute
suppression hors `crm.Lead` était dure et définitive malgré la promesse de
rétention 30 jours affichée aux Directeurs.

`Contrat` est le premier objet À VALEUR LÉGALE branché : DELETE sur l'API le
masque (soft-delete) au lieu de l'effacer, et l'entrée de corbeille devient
listable/restaurable. Le viewset n'importe RIEN de `apps.trash` — le lien est
l'événement (règle M6).

Test ROUGE d'abord : sur l'arbre d'avant AUD818, `Contrat` n'héritait pas de
`core.SoftDeleteModel`, `perform_destroy` n'existait pas, la ligne disparaissait
définitivement et `ElementSupprime.objects.count()` restait à 0.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.contrats.models import Contrat
from apps.trash.models import ElementSupprime
from apps.trash.services import restaurer
from authentication.models import Company

User = get_user_model()

BASE = '/api/django/contrats/contrats/'


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ContratCorbeilleTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='aud818-co', defaults={'nom': 'AUD818'})
        self.admin = User.objects.create_user(
            username='aud818-admin', password='x', company=self.company,
            role_legacy='admin')
        self.contrat = Contrat.objects.create(
            company=self.company, objet='Contrat O&M centrale',
            reference='CTR-2026-0001')

    def test_delete_est_une_suppression_douce(self):
        resp = auth(self.admin).delete(f'{BASE}{self.contrat.pk}/')
        self.assertEqual(resp.status_code, 204, getattr(resp, 'data', None))
        # La ligne EXISTE toujours (valeur légale préservée) mais est masquée
        # du manager par défaut — donc de l'API.
        self.assertTrue(
            Contrat.all_objects.filter(pk=self.contrat.pk).exists())
        self.assertFalse(Contrat.objects.filter(pk=self.contrat.pk).exists())
        self.contrat.refresh_from_db()
        self.assertTrue(self.contrat.is_deleted)
        self.assertEqual(self.contrat.deleted_by, self.admin)

    def test_delete_alimente_la_corbeille_transverse(self):
        auth(self.admin).delete(f'{BASE}{self.contrat.pk}/')
        element = ElementSupprime.objects.get()
        self.assertEqual(element.company, self.company)
        self.assertEqual(element.cle_modele, 'contrats.contrat')
        self.assertEqual(element.object_id, self.contrat.pk)
        self.assertEqual(element.type_libelle, 'Contrat')
        self.assertEqual(element.libelle_snapshot, 'CTR-2026-0001')
        self.assertEqual(
            element.donnees_snapshot['objet'], 'Contrat O&M centrale')
        self.assertEqual(element.supprime_par, self.admin)
        self.assertIsNone(element.restaure_le)

    def test_la_corbeille_restaure_le_contrat(self):
        auth(self.admin).delete(f'{BASE}{self.contrat.pk}/')
        element = ElementSupprime.objects.get()
        restaurer(element, user=self.admin)
        self.assertTrue(Contrat.objects.filter(pk=self.contrat.pk).exists())
        self.contrat.refresh_from_db()
        self.assertFalse(self.contrat.is_deleted)

    def test_le_contrat_supprime_sort_de_la_liste_api(self):
        api = auth(self.admin)
        api.delete(f'{BASE}{self.contrat.pk}/')
        resp = api.get(BASE)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        lignes = data['results'] if isinstance(data, dict) and 'results' in data else data
        self.assertEqual(
            [ligne['id'] for ligne in lignes if ligne['id'] == self.contrat.pk],
            [])

    def test_suppression_rejouee_ne_duplique_pas_lentree(self):
        """`soft_delete()` est idempotent — pas de doublon de corbeille."""
        self.contrat.soft_delete(user=self.admin, type_libelle='Contrat')
        self.contrat.soft_delete(user=self.admin, type_libelle='Contrat')
        self.assertEqual(ElementSupprime.objects.count(), 1)
