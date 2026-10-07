"""ACAL114 (D-ACAL-11, D-ACAL-19, C-ACAL-093/094) — l'approbation est liée à
l'empreinte IMPRIMÉE, une conception vide ne s'approuve pas, et le statut du
calepinage est DÉRIVÉ (lecture seule).

HTTP réels ; le réglage société ``approbation_exigee`` est ÉCRIT EN BASE
(``enregistrer_parametres``), jamais un patch de ``parametres_de_societe``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_approbation_empreinte -v2
"""
import copy

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.layout import (
    empreinte_document, enregistrer_layout,
)
from apps.calepinage.services.parametres import enregistrer_parametres

from .test_api_liste import URL, BaseApiCalepinage, url_detail


def _dessin(largeur=10):
    return {'zones': [{'id': 'z1', 'label': 'Pan Sud',
                       'vertices': [[0, 0], [largeur, 0], [largeur, 6]],
                       'geometry': {'count': largeur, 'azimuthDeg': 180,
                                    'tiltDeg': 15}}]}


class ApprobationEmpreinteTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        enregistrer_parametres(self.company,
                               {'presets': {'approbation_exigee': True}})
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL114')
        # ACAL303 — la conception est d'un AUTRE compte que le relecteur.
        enregistrer_layout(self.calepinage, _dessin(10), user=self.user_sans)
        self.base = url_detail(self.calepinage.pk)

    def _approuver(self):
        reponse = self.api.post(f'{self.base}approbation/',
                                {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse

    def _etat(self):
        reponse = self.api.get(f'{self.base}approbation/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return reponse.data

    def _modifier_le_dessin(self, largeur=12):
        cal = Calepinage.objects.get(pk=self.calepinage.pk)
        jeton = empreinte_document(cal.roof_layout) or ''
        reponse = self.api.post(f'{self.base}layout/', _dessin(largeur),
                                format='json', HTTP_IF_MATCH=f'"{jeton}"')
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def _variante(self, dessin, nom='V'):
        return CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom=nom,
            roof_layout=copy.deepcopy(dessin))

    def _retenir(self, variante):
        return self.api.post(
            f'{self.base}variantes/{variante.pk}/retenir/', {},
            format='json')

    def test_modifier_apres_approbation_perime(self):
        self._approuver()
        etat = self._etat()
        self.assertEqual(etat['etat'], 'approuve')
        self.assertFalse(etat['perimee'])
        self._modifier_le_dessin()
        etat = self._etat()
        self.assertEqual(etat['etat'], 'approuve')
        self.assertTrue(etat['perimee'])
        detail = self.api.get(self.base).data
        self.assertEqual(detail['statut'], 'perime')

    def _publier(self, geste='devis'):
        """La SEULE porte de l'approbation : la publication (ACAL116)."""
        from apps.calepinage.services.feu_vert import (
            verifier_avant_publication,
        )

        cal = Calepinage.objects.get(pk=self.calepinage.pk)
        return verifier_avant_publication(cal, geste=geste)

    def test_retenir_approbation_perimee_passe_puis_publication_refusee(self):
        # Décision fondateur 07/10/2026 : retenir -> approuver -> publier.
        from rest_framework.exceptions import ValidationError

        self._approuver()
        self._modifier_le_dessin()
        variante = self._variante(_dessin(12))
        reponse = self._retenir(variante)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        variante.refresh_from_db()
        self.assertTrue(variante.retenue)
        with self.assertRaises(ValidationError) as refus:
            self._publier()
        self.assertIn('approbation', refus.exception.detail)
        self._approuver()
        self.assertIsNone(self._publier())

    def test_retenir_autre_variante_perime_l_accord_jusqu_a_reapprobation(
            self):
        from rest_framework.exceptions import ValidationError

        self._approuver()
        self.assertIsNone(self._publier())
        autre = self._variante(_dessin(14), nom='Autre')
        reponse = self._retenir(autre)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        # La variante retenue est la conception courante : accord périmé.
        self.assertTrue(self._etat()['perimee'])
        for geste in ('devis', 'execution'):
            with self.subTest(geste=geste):
                with self.assertRaises(ValidationError) as refus:
                    self._publier(geste)
                self.assertIn('approbation', refus.exception.detail)
        self._approuver()
        self.assertIsNone(self._publier('devis'))
        self.assertIsNone(self._publier('execution'))

    def test_approuver_conception_vide_refuse(self):
        vide = Calepinage.objects.create(company=self.company,
                                         lead_id=self.lead_2.pk, titre='Vide')
        reponse = self.api.post(f'{url_detail(vide.pk)}approbation/',
                                {'decision': 'approuve'}, format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(reponse.data['roof_layout'],
                         'Rien à approuver : dessinez la toiture')
        vide.refresh_from_db()
        self.assertIsNone(vide.approbation)

    def test_statut_derive_et_filtre(self):
        def ids(statut):
            reponse = self.api.get(URL, {'statut': statut})
            self.assertEqual(reponse.status_code, 200, reponse.data)
            lignes = reponse.data.get('results', reponse.data)
            return {ligne['id'] for ligne in lignes}

        self.assertIn(self.calepinage.pk, ids('brouillon'))
        self._approuver()
        self.assertIn(self.calepinage.pk, ids('valide'))
        self.assertNotIn(self.calepinage.pk, ids('brouillon'))
        self._modifier_le_dessin()
        self.assertIn(self.calepinage.pk, ids('perime'))
        self.assertNotIn(self.calepinage.pk, ids('valide'))
        reponse = self.api.get(URL, {'ordering': 'statut'})
        self.assertEqual(reponse.status_code, 200, reponse.data)

    def test_patch_statut_sans_effet(self):
        reponse = self.api.patch(self.base, {'statut': 'valide'},
                                 format='json')
        self.assertIn(reponse.status_code, (200, 400), reponse.data)
        detail = self.api.get(self.base).data
        self.assertEqual(detail['statut'], 'brouillon')
        self.assertEqual(detail['statut_libelle'], 'Brouillon')
