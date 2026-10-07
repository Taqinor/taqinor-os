"""ACAL112 (D-ACAL-17, C-ACAL-086) — simuler UNE variante.

Ce qui est prouvé ici :

* ``POST simuler/ {variante_id, forcer}`` accuse 202 et transmet la variante
  au travail de fond ; le service écrit ``variante.resultat`` (simulation +
  production calculées sur ``variante.roof_layout``) ;
* ``Calepinage.resultat`` reste INCHANGÉ ;
* le comparatif lit modules / kWc de la CONCEPTION d'une variante non
  simulée (``source_mesures: 'conception'``) ;
* modifier la conception d'une variante remet son résultat à ``None`` ;
* une variante d'un autre calepinage ou inexistante ⇒ 404, même message.

Le fournisseur PVGIS est injecté au niveau RÉSEAU seulement (client rejoué) ;
la file de travaux est hors sujet (elle lancerait PVGIS) et n'est doublée que
dans le test de la porte HTTP.

Run :
    python manage.py test apps.calepinage.tests.test_acal_simuler_variante -v2
"""
import copy
from unittest import mock

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.services.simulation import simuler_calepinage
from apps.calepinage.services.variantes import (
    creer_variante, modifier_variante,
)

from .acal_livrables_helpers import patch_materiel
from .test_acal_multi_pans import _ClientParOrientation, _layout, _zone
from .test_api_liste import BaseApiCalepinage, url_detail
from .test_calx5_simulation import MATERIEL


class SimulerVarianteTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='ACAL112',
            roof_layout=_layout(_zone(1, 16, 90.0), _zone(2, 8, 270.0)),
            resultat={'entree_electrique': {'dc_m': 30}})
        self.a = creer_variante(self.calepinage, nom='A',
                                roof_layout=_layout(_zone(1, 14, 180.0)))
        self.b = creer_variante(self.calepinage, nom='B',
                                roof_layout=_layout(_zone(1, 10, 180.0)))
        self.base = url_detail(self.calepinage.pk)

    def _simuler_service(self, variante):
        with patch_materiel():
            return simuler_calepinage(
                self.calepinage, client=_ClientParOrientation(),
                materiel=MATERIEL, enregistrer=True, forcer=True,
                variante=variante)

    def _poster(self, corps):
        with patch_materiel(), mock.patch('core.jobs.submit') as soumettre:
            soumettre.return_value = mock.Mock(
                pk=1, statut='pending', kind='calepinage', progress_pct=0,
                message_erreur='')
            reponse = self.api.post(f'{self.base}simuler/', corps,
                                    format='json')
        return reponse, soumettre

    def test_simuler_une_variante_ecrit_son_resultat(self):
        reponse, soumettre = self._poster(
            {'variante_id': self.a.pk, 'forcer': True})
        self.assertEqual(reponse.status_code, 202, reponse.data)
        self.assertEqual(reponse.data['variante_id'], self.a.pk)
        self.assertEqual(soumettre.call_args.kwargs['variante_id'], self.a.pk)

        self._simuler_service(self.a)
        self.a.refresh_from_db()
        self.assertIn('simulation', self.a.resultat)
        self.assertIn('production', self.a.resultat)
        self.assertIsNotNone(
            (self.a.resultat['production'].get('total') or {})
            .get('p50_kwh'))

    def test_get_resultat_variante_sert_sa_simulation(self):
        """Lot 2 critique #17 — ``GET resultat/?variante=`` sert la
        simulation de LA variante (``variante.resultat``) ; une variante sans
        conception ⇒ 400 ``variante``, jamais le calepinage sous son nom."""
        self._simuler_service(self.a)
        self.a.refresh_from_db()
        with patch_materiel():
            reponse = self.api.get(f'{self.base}resultat/',
                                   {'variante': self.a.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['simulation_perimee'],
                         reponse.data.get('motif'))
        self.assertEqual(reponse.data['production'],
                         self.a.resultat['production'])
        # Le calepinage, lui, n'a jamais été simulé.
        with patch_materiel():
            courant = self.api.get(f'{self.base}resultat/')
        self.assertNotEqual(courant.data['production'],
                            self.a.resultat['production'])
        vide = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='Vide',
            roof_layout=None)
        reponse = self.api.get(f'{self.base}resultat/', {'variante': vide.pk})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('variante', reponse.data)

    def test_simuler_variante_sans_conception_400_avant_la_file(self):
        """Lot 2 critique #18 — refus nommé ``variante``, rien n'est mis en
        file."""
        vide = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.calepinage, nom='Vide',
            roof_layout=None)
        reponse, soumettre = self._poster({'variante_id': vide.pk})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('variante', reponse.data)
        soumettre.assert_not_called()

    def test_resultat_du_calepinage_intact(self):
        avant = copy.deepcopy(Calepinage.objects.get(
            pk=self.calepinage.pk).resultat)
        self._simuler_service(self.a)
        self.assertEqual(Calepinage.objects.get(
            pk=self.calepinage.pk).resultat, avant)

    def test_mesures_de_conception_sans_simulation(self):
        self._simuler_service(self.a)
        with patch_materiel():
            reponse = self.api.get(f'{self.base}comparer/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = {ligne['nom']: ligne for ligne in reponse.data['lignes']}
        self.assertTrue(lignes['A']['simulee'])
        self.assertEqual(lignes['A']['source_mesures'], 'simulation')
        # Lot 2 critique #30 — SIMULÉE, la variante garde ses modules / kWc
        # (lus dans sa conception, les blocs de simulation n'en portent pas).
        self.assertEqual(lignes['A']['total_modules'], 14)
        self.assertIsNotNone(lignes['A']['kwc'])
        self.assertFalse(lignes['B']['simulee'])
        self.assertEqual(lignes['B']['source_mesures'], 'conception')
        self.assertEqual(lignes['B']['total_modules'], 10)

    def test_modifier_variante_invalide(self):
        self._simuler_service(self.a)
        self.a.refresh_from_db()
        self.assertIsNotNone(self.a.resultat)
        modifier_variante(self.a, roof_layout=_layout(_zone(1, 12, 180.0)))
        self.assertIsNone(CalepinageVariante.objects.get(
            pk=self.a.pk).resultat)

    def test_variante_etrangere_404(self):
        autre = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk, titre='Autre',
            roof_layout=_layout(_zone(1, 6, 180.0)))
        etrangere = creer_variante(autre, nom='X',
                                   roof_layout=_layout(_zone(1, 6, 180.0)))
        absente, _ = self._poster({'variante_id': 999999})
        ailleurs, soumettre = self._poster({'variante_id': etrangere.pk})
        self.assertEqual(absente.status_code, 404)
        self.assertEqual(ailleurs.status_code, 404)
        self.assertEqual(ailleurs.data, absente.data)
        soumettre.assert_not_called()
