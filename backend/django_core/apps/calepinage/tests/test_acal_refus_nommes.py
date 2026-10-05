"""ACAL277 — valeur non finie, hors bornes ou du mauvais type ⇒ 400 nommé.

Constat C-ACAL-142 (audit 2026-10-04) : ``nan`` / ``inf`` / ``1e400`` dans un
relevé, un champ de dossier ou un montant de « Générer le devis », et un nom
de variante qui n'est pas un texte, finissaient en 500 ; un identifiant de
chemin non numérique (``variantes/abc/``) aussi (SIT-G2-12).

Tenu ici sur les routes et services RÉELS (APIClient, aucun mock) : chaque
refus nomme le champ, rien n'est écrit (comptage avant / après), et un
identifiant non numérique répond le MÊME 404 qu'un identifiant absent.

Run :
    python manage.py test apps.calepinage.tests.test_acal_refus_nommes -v2
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.calepinage.models import (
    Calepinage, CalepinageVariante, ReleveTerrain,
)
from apps.calepinage.services.reglementaire import (
    ChampsDossierInvalides, _valider_champs_saisis,
)
from apps.calepinage.services.valeurs import ValeurRefusee, nombre_fini

from .test_api_liste import BaseApiCalepinage, url_detail

DOCUMENT = {'version': 2, 'zones': [{'id': 'z1', 'pitchDeg': 30}]}


def _chaine(cotes, **champs):
    return dict({'nom': 'Long pan', 'cotes': cotes}, **champs)


class NombreFiniTest(SimpleTestCase):
    """La règle unique — ``services/valeurs.py``."""

    def test_non_fini_et_mauvais_type_refuses(self):
        for valeur in ('nan', 'inf', '-inf', '1e400', float('nan'), True,
                       [1], 'abc'):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ValeurRefusee) as refus:
                    nombre_fini(valeur, 'champ_x')
                self.assertEqual(refus.exception.champ, 'champ_x')

    def test_bornes_et_decimales(self):
        self.assertEqual(nombre_fini('20', 'tva', mini=0, maxi=100), 20.0)
        for valeur in (150, -5, 12.345):
            with self.subTest(valeur=valeur):
                with self.assertRaises(ValeurRefusee):
                    nombre_fini(valeur, 'tva', mini=0, maxi=100, decimales=2)
        with self.assertRaises(ValeurRefusee):
            nombre_fini(0, 'cote', mini=0, mini_exclu=True)
        self.assertIsNone(nombre_fini(None, 'absent'))


class RefusNommesTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=DOCUMENT)
        self.url = url_detail(self.calepinage.pk)

    def test_releve_nan_inf_negatif(self):
        cas = (
            [_chaine([{'nom': 'a', 'valeur': 'nan'}])],
            [_chaine([{'nom': 'a', 'valeur': 'inf'}])],
            [_chaine([{'nom': 'a', 'valeur': '1e400'}])],
            [_chaine([{'nom': 'a', 'valeur': 5}], tolerance_m='nan')],
            [_chaine([{'nom': 'a', 'valeur': -3}, {'nom': 'b', 'valeur': 2}])],
            [_chaine([{'nom': 'a', 'valeur': 3}, {'nom': 'b'}],
                     total_mesure=-1)],
        )
        avant = ReleveTerrain.objects.count()
        for chaines in cas:
            with self.subTest(chaines=chaines):
                reponse = self.api.post(
                    f'{self.url}releve/',
                    {'releve_le': '2026-10-01', 'chaines': chaines},
                    format='json')
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn('chaines[0]', reponse.data)
        self.assertEqual(ReleveTerrain.objects.count(), avant)

    def test_champs_dossier_non_fini(self):
        gabarit = [{'code': 'puissance_kwc', 'libelle': 'Puissance',
                    'type': 'nombre'},
                   {'code': 'commentaire', 'libelle': 'Commentaire'}]
        for code, valeur in (('puissance_kwc', 'nan'),
                             ('puissance_kwc', 'inf'),
                             ('puissance_kwc', '1e400'),
                             ('commentaire', float('nan'))):
            with self.subTest(code=code, valeur=valeur):
                with self.assertRaises(ChampsDossierInvalides) as refus:
                    _valider_champs_saisis(gabarit, {code: valeur})
                self.assertEqual(refus.exception.champ, code)
        self.assertEqual(
            _valider_champs_saisis(gabarit, {'puissance_kwc': '6,5'}),
            {'puissance_kwc': 6.5})

    def test_generer_devis_montants_hors_bornes(self):
        from apps.ventes.models import Devis

        avant = Devis.objects.count()
        for corps, champ in (({'remise_globale': '150'}, 'remise_globale'),
                             ({'remise_globale': '-5'}, 'remise_globale'),
                             ({'taux_tva': 'NaN'}, 'taux_tva'),
                             ({'taux_tva': '123456'}, 'taux_tva')):
            with self.subTest(corps=corps):
                reponse = self.api.post(f'{self.url}generer-devis/', corps,
                                        format='json')
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn(champ, reponse.data)
        self.assertEqual(Devis.objects.count(), avant)
        self.calepinage.refresh_from_db()
        self.assertIsNone(self.calepinage.devis_id)

    def test_variante_nom_non_textuel(self):
        avant = CalepinageVariante.objects.count()
        for nom in (5, ['a']):
            with self.subTest(nom=nom):
                reponse = self.api.post(f'{self.url}variantes/',
                                        {'nom': nom}, format='json')
                self.assertEqual(reponse.status_code, 400, reponse.data)
                self.assertIn('nom', reponse.data)
        self.assertEqual(CalepinageVariante.objects.count(), avant)

        variante = self.api.post(f'{self.url}variantes/', {'nom': 'A'},
                                 format='json')
        self.assertEqual(variante.status_code, 201, variante.data)
        reponse = self.api.patch(
            f'{self.url}variantes/{variante.data["id"]}/', {'nom': 5},
            format='json')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('nom', reponse.data)

    def test_identifiant_non_numerique_404(self):
        routes = (
            ('get', 'variantes/{}/'),
            ('post', 'variantes/{}/retenir/'),
            ('post', 'versions/{}/restaurer/'),
            ('get', 'versions/{}/diff/'),
            ('patch', 'photos/{}/calage/'),
        )
        for methode, gabarit in routes:
            with self.subTest(route=gabarit):
                absent = getattr(self.api, methode)(
                    self.url + gabarit.format(999999), {}, format='json')
                self.assertEqual(absent.status_code, 404, absent.data)
                for brut in ('abc', '9' * 30):
                    reponse = getattr(self.api, methode)(
                        self.url + gabarit.format(brut), {}, format='json')
                    self.assertEqual(reponse.status_code, 404, reponse.data)
                    self.assertEqual(reponse.data, absent.data)
