"""ACAL110 (C-ACAL-088) — créer, modifier et supprimer une variante se
journalisent AVEC leur auteur ; un PATCH sans changement réel n'écrit rien.

HTTP réel ; le journal est relu de la base (onglet Activité).

Run :
    python manage.py test apps.calepinage.tests.test_acal_journal_variantes -v2
"""
from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import Calepinage
from apps.records.models import Activity

from .test_api_liste import BaseApiCalepinage, url_detail


class JournalVariantesTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL110')
        self.base = url_detail(self.calepinage.pk)

    def _journal(self):
        return (Activity.objects
                .filter(content_type=ContentType.objects.get_for_model(
                    Calepinage), object_id=self.calepinage.pk,
                    field__startswith='variante_')
                .order_by('id'))

    def test_creation_modification_suppression_journalisees_avec_auteur(self):
        reponse = self.api.post(f'{self.base}variantes/',
                                {'nom': 'X', 'roof_layout': {'panels': 4}},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        variante_id = reponse.data['id']
        reponse = self.api.patch(f'{self.base}variantes/{variante_id}/',
                                 {'roof_layout': {'panels': 6}},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        reponse = self.api.delete(f'{self.base}variantes/{variante_id}/')
        self.assertEqual(reponse.status_code, 204)

        lignes = list(self._journal())
        self.assertEqual([ligne.new_value for ligne in lignes], [
            'Variante « X » créée',
            'Variante « X » modifiée (conception)',
            'Variante « X » supprimée',
        ])
        for ligne in lignes:
            self.assertEqual(ligne.created_by_id, self.user.pk)

    def test_patch_sans_changement_sans_journal(self):
        reponse = self.api.post(f'{self.base}variantes/',
                                {'nom': 'X', 'roof_layout': {'panels': 4}},
                                format='json')
        variante_id = reponse.data['id']
        avant = self._journal().count()
        reponse = self.api.patch(f'{self.base}variantes/{variante_id}/',
                                 {'nom': 'X', 'roof_layout': {'panels': 4}},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self._journal().count(), avant)
        reponse = self.api.patch(f'{self.base}variantes/{variante_id}/',
                                 {'nom': 'Y'}, format='json')
        self.assertEqual(self._journal().last().new_value,
                         'Variante « Y » modifiée (nom)')
