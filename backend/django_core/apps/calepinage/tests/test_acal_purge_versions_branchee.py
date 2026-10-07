"""ACAL287 (C-ACAL-145) — la purge des versions est BRANCHÉE : chaque
version enregistrée (``enregistrer_layout``) ou restaurée
(``restaurer_version``) applique la borne SAISIE par la société
(``presets.versions_conservees``) ; absente ⇒ rien n'est retiré ; une borne
invalide est refusée à l'écriture en nommant ``presets.versions_conservees``.

ORM réel, services réels, HTTP réel pour les réglages ; rien n'est mocké.

Run :
    python manage.py test apps.calepinage.tests.test_acal_purge_versions_branchee -v2
"""
from apps.calepinage.models import Calepinage, CalepinageVersion
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.calepinage.services.versions import restaurer_version

from .test_api_liste import BaseApiCalepinage, url_detail

URL_PARAMETRES = '/api/django/calepinage/parametres/'


def _document(modules):
    return {'version': 2, 'zones': [{'id': 'z1', 'label': 'Pan Sud',
                                     'geometry': {'count': modules}}]}


class PurgeVersionsBrancheeTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL287')

    def _borne(self, valeur):
        enregistrer_parametres(self.company,
                               {'presets': {'versions_conservees': valeur}})

    def _versions(self):
        return list(CalepinageVersion.objects
                    .filter(calepinage=self.calepinage)
                    .order_by('-created_at', '-id'))

    def _enregistrer(self, modules):
        return enregistrer_layout(self.calepinage, _document(modules),
                                  user=self.user)

    def test_quatre_enregistrements_avec_borne_deux_laissent_deux_versions(self):
        self._borne(2)
        for modules in (4, 6, 8, 10):
            self._enregistrer(modules)
        versions = self._versions()
        self.assertEqual(len(versions), 2)
        # Les DEUX plus récentes survivent.
        self.assertEqual([v.roof_layout['zones'][0]['geometry']['count']
                          for v in versions], [10, 8])
        # Rouvrir : GET versions/ rend les N dernières.
        reponse = self.api.get(f'{url_detail(self.calepinage.pk)}versions/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = reponse.data.get('results', reponse.data) if isinstance(
            reponse.data, dict) else reponse.data
        self.assertEqual(len(lignes), 2)
        # Renvoi à l'identique : ni version neuve, ni purge de plus.
        resultat = self._enregistrer(10)
        self.assertTrue(resultat['inchange'])
        self.assertEqual([v.pk for v in self._versions()],
                         [v.pk for v in versions])

    def test_sans_borne_rien_n_est_purge(self):
        for modules in (4, 6, 8, 10):
            self._enregistrer(modules)
        self.assertEqual(len(self._versions()), 4)

    def test_restauration_purge_aussi(self):
        for modules in (4, 6, 8):
            self._enregistrer(modules)
        self.assertEqual(len(self._versions()), 3)
        self._borne(2)
        plus_ancienne = self._versions()[-1]
        self.calepinage.refresh_from_db()
        restaurer_version(plus_ancienne, user=self.user)
        versions = self._versions()
        self.assertEqual(len(versions), 2)
        self.calepinage.refresh_from_db()
        self.assertEqual(
            self.calepinage.roof_layout['zones'][0]['geometry']['count'], 4)

    def test_borne_invalide_refusee_en_nommant_le_champ(self):
        for valeur in (0, -1, 'deux', 2.5, True):
            with self.subTest(valeur=valeur):
                reponse = self.api.put(
                    URL_PARAMETRES,
                    {'presets': {'versions_conservees': valeur}},
                    format='json')
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn('presets', reponse.data)
                self.assertIn('versions_conservees', reponse.data['presets'])
        # Valides : un entier > 0, ou null (purge éteinte).
        for valeur in (3, None):
            with self.subTest(valeur=valeur):
                reponse = self.api.put(
                    URL_PARAMETRES,
                    {'presets': {'versions_conservees': valeur}},
                    format='json')
                self.assertEqual(reponse.status_code, 200, reponse.data)
