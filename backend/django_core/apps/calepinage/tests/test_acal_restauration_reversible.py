"""ACAL45 (C-ACAL-091) — toute restauration est réversible.

Ce qui est prouvé ici, par ``POST versions/<id>/restaurer/`` réel :

* une version « Avant restauration de #<v1> » porte l'état d'avant (roof_layout
  d'avant) ; restaurer CETTE version rend l'état initial à l'identique ;
* seul le DESSIN est restauré : ``Calepinage.resultat`` (entrée électrique,
  raccordement, schéma, dérogations, simulation) est octet-identique ;
* restaurer la version déjà courante : ``inchange``, aucun instantané ;
* une version de GÉOMÉTRIE ne gèle plus le résultat (``resultat`` None) ;
* le rendu 3D (``roof_image``) est vidé.

Run :
    python manage.py test apps.calepinage.tests.test_acal_restauration_reversible -v2
"""
import copy

from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.resultat import modifier_resultat

from .test_api_liste import BaseApiCalepinage, url_detail

L1 = {'schema_version': 2, 'result': {'panels': 10}}
L2 = {'schema_version': 2, 'result': {'panels': 12}}
L2_PLUS = {'schema_version': 2, 'result': {'panels': 12},
           'horizonProfile': [{'azimut': 180, 'hauteur': 5}],
           'setbacksM': 0.5}


def url_restaurer(pk, version_id):
    return f'{url_detail(pk)}versions/{version_id}/restaurer/'


class RestaurationReversibleTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL45')
        for document in (L1, L2, L2_PLUS):
            enregistrer_layout(self.calepinage, copy.deepcopy(document),
                               user=self.user)
        self.v1 = (CalepinageVersion.objects
                   .filter(calepinage=self.calepinage)
                   .order_by('created_at', 'id').first())

        def _saisies(resultat):
            resultat['entree_electrique'] = {'dc_m': 55, 'ac_m': 40}
            resultat['raccordement_saisie'] = {'type': 'monophase'}
            resultat['journal_derogations'] = [{'code': 'X', 'motif': 'm'}]
            resultat['simulation'] = {'hash_entree': 'ab' * 8}
        modifier_resultat(self.calepinage, _saisies)
        Calepinage.objects.filter(pk=self.calepinage.pk).update(
            roof_image='roofs/1/calepinage-rendu.png')
        self.calepinage.refresh_from_db()

    def _etat(self):
        cal = Calepinage.objects.get(pk=self.calepinage.pk)
        return copy.deepcopy(cal.roof_layout), copy.deepcopy(cal.resultat)

    def _restaurer(self, version):
        reponse = self.api.post(url_restaurer(self.calepinage.pk, version.pk),
                                {}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def test_avant_restauration_depose_l_etat_courant(self):
        initial = self._etat()
        self._restaurer(self.v1)
        avant = CalepinageVersion.objects.get(
            calepinage=self.calepinage,
            libelle=f'Avant restauration de #{self.v1.pk}')
        self.assertEqual(avant.roof_layout, initial[0])
        self.assertIsNone(avant.resultat)
        # Restaurer l'instantané « Avant restauration » ⇒ état initial.
        self._restaurer(avant)
        self.assertEqual(self._etat(), initial)

    def test_restaurer_conserve_les_saisies(self):
        _layout, resultat_initial = self._etat()
        self._restaurer(self.v1)
        roof_layout, resultat = self._etat()
        self.assertEqual(roof_layout, L1)
        self.assertEqual(resultat, resultat_initial)
        self.assertEqual(resultat['entree_electrique'],
                         {'dc_m': 55, 'ac_m': 40})
        self.assertEqual(resultat['raccordement_saisie'],
                         {'type': 'monophase'})

    def test_restaurer_version_courante_sans_effet(self):
        courante = (CalepinageVersion.objects
                    .filter(calepinage=self.calepinage)
                    .order_by('-created_at', '-id').first())
        avant = CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count()
        initial = self._etat()
        donnees = self._restaurer(courante)
        self.assertTrue(donnees['inchange'])
        self.assertEqual(CalepinageVersion.objects.filter(
            calepinage=self.calepinage).count(), avant)
        self.assertEqual(self._etat(), initial)
        self.assertEqual(Calepinage.objects.get(
            pk=self.calepinage.pk).roof_image,
            'roofs/1/calepinage-rendu.png')

    def test_version_de_geometrie_sans_resultat(self):
        enregistrer_layout(self.calepinage, {'schema_version': 2,
                                             'result': {'panels': 16}},
                           user=self.user)
        derniere = (CalepinageVersion.objects
                    .filter(calepinage=self.calepinage)
                    .order_by('-created_at', '-id').first())
        self.assertIsNone(derniere.resultat)

    def test_roof_image_videe(self):
        self._restaurer(self.v1)
        self.assertEqual(Calepinage.objects.get(
            pk=self.calepinage.pk).roof_image, '')
