"""ACAL210 — « Mettre à jour depuis la visite » : remplacer la reprise.

Le relevé repris de la visite V (pente 10) ; la visite est renvoyée à refaire,
remesurée (15) puis re-validée : ``a_jour: false`` et un ``ecart`` publié ;
``POST {remplacer: true}`` met le MÊME relevé à jour (mesures, photos, une
ligne de chatter) ; sans ``remplacer`` rien n'est touché ; ``deja_repris``
reste vrai quand la visite repasse non validée.

Run ::

    manage.py test apps.calepinage.tests.test_acal_reprise_visite_maj
"""
from __future__ import annotations

from apps.calepinage.models import PhotoSite, ReleveTerrain
from apps.calepinage.tests.test_calx364_reprise_visite import (
    RepriseVisiteEnBase,
    url_reprise,
)


class BaseMaj(RepriseVisiteEnBase):

    def setUp(self):
        super().setUp()
        self.url = url_reprise(self.calepinage.pk)
        self.visite = self._validee(
            mesures={'toiture': {'longueur_m': 12.5, 'pente_deg': 10}})
        self.photo_a = self._photo(self.visite, 'toiture_vue_generale')
        self.photo_b = self._photo(self.visite, 'toiture_obstacles')
        premier = self.api.post(self.url)
        self.assertEqual(premier.status_code, 201, premier.data)
        self.releve = ReleveTerrain.objects.get(calepinage=self.calepinage)

    def _renvoyer_remesurer_revalider(self, pente=15):
        """La visite revient à refaire, est remesurée, puis re-validée."""
        from apps.visites.models import VisiteMedia, VisiteTerrain

        self.visite.statut = VisiteTerrain.Statut.TERMINEE
        self.visite.save(update_fields=['statut'])
        self.visite.mesures = {'toiture': {'longueur_m': 12.5,
                                           'pente_deg': pente}}
        self.visite.statut = VisiteTerrain.Statut.VALIDEE
        self.visite.save(update_fields=['mesures', 'statut'])
        # La photo « obstacles » est à refaire ; une nouvelle vue la remplace.
        VisiteMedia.objects.filter(
            visite=self.visite, slot_code='toiture_obstacles'
        ).update(a_refaire=True)
        self.nouvelle = self._photo(self.visite, 'general_facade')


class EcartTest(BaseMaj):

    def test_ecart_publie_apres_renvoi_et_revalidation(self):
        self._renvoyer_remesurer_revalider()
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['a_jour'])
        self.assertTrue(reponse.data['deja_repris'])
        ecart = [e for e in reponse.data['ecart']
                 if e['code'] == 'pente_deg']
        self.assertEqual(len(ecart), 1, reponse.data['ecart'])
        self.assertEqual((ecart[0]['releve'], ecart[0]['visite']),
                         (10, 15))

    def test_a_jour_tant_que_rien_ne_diverge(self):
        reponse = self.api.get(self.url)
        self.assertTrue(reponse.data['a_jour'])
        self.assertEqual(reponse.data['ecart'], [])


class RemplacerTest(BaseMaj):

    def test_remplacer_met_a_jour_mesures_et_photos(self):
        from apps.records.models import Attachment

        self._renvoyer_remesurer_revalider()
        pieces = Attachment.objects.count()
        reponse = self.api.post(self.url, {'remplacer': True}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(ReleveTerrain.objects.filter(
            calepinage=self.calepinage).count(), 1)     # EN PLACE
        self.releve.refresh_from_db()
        pente = [m for m in self.releve.mesures
                 if m['code'] == 'pente_deg'][0]
        self.assertEqual(pente['valeur'], 15)
        attachements = set(PhotoSite.objects.filter(
            calepinage=self.calepinage, releve=self.releve
        ).values_list('attachment_id', flat=True))
        self.assertIn(self.nouvelle.pk, attachements)       # rattachée
        self.assertNotIn(self.photo_b.pk, attachements)     # « à refaire »
        self.assertEqual(Attachment.objects.count(), pieces)  # rien copié
        self.assertTrue(reponse.data['a_jour'])
        # Persistance : relue, plus d'écart.
        relue = self.api.get(self.url)
        self.assertTrue(relue.data['a_jour'])
        self.assertEqual(relue.data['ecart'], [])

    def test_remplacer_journalise_l_ecart(self):
        from django.contrib.contenttypes.models import ContentType

        from apps.records.models import Activity

        self._renvoyer_remesurer_revalider()
        self.api.post(self.url, {'remplacer': True}, format='json')
        lignes = Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(
                type(self.calepinage)),
            object_id=self.calepinage.pk,
            body__contains='Reprise mise à jour : pente_deg 10 vers 15')
        self.assertEqual(lignes.count(), 1)

    def test_sans_remplacer_rien_ne_change(self):
        self._renvoyer_remesurer_revalider()
        avant = list(self.releve.mesures)
        reponse = self.api.post(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.releve.refresh_from_db()
        self.assertEqual(self.releve.mesures, avant)
        self.assertFalse(reponse.data['a_jour'])

    def test_deja_repris_reste_vrai_visite_non_validee(self):
        from apps.visites.models import VisiteTerrain

        self.visite.statut = VisiteTerrain.Statut.TERMINEE
        self.visite.save(update_fields=['statut'])
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['deja_repris'])
        self.assertEqual(reponse.data['releve']['id'], self.releve.pk)
        self.assertFalse(reponse.data['a_jour'])
        self.assertEqual(reponse.data['ecart'], [])
