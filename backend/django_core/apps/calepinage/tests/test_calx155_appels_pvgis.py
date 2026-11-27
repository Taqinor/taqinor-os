"""CALX155 — une requête météo par PLAN, jamais par module.

`services/production.py` demande aujourd'hui une série PAR PAN et met à
l'échelle côté client ; la simulation module par module (CALX182) en
demanderait une par MODULE. La mémoire installée par l'ordonnanceur est keyée
exactement comme le cache de `services/pvgis_serie.py` — c'est ce que ce
fichier garde, en COMPTANT les appels réels.

Aucun réseau : le fournisseur est un compteur.

Run :
    python manage.py test apps.calepinage.tests.test_calx155_appels_pvgis
"""
from __future__ import annotations

import unittest

from apps.calepinage.services.chaine_pertes import (
    CLE_FOURNISSEUR_METEO, CLE_METEO_PARTAGEE, ChaineInvalide,
    appliquer_chaine)

SERIE = {'pas_minutes': 60, 'points': [{'p_w': 1000.0}]}
SITE = {'lat': 33.5731, 'lon': -7.5898}


class Compteur:
    """Le fournisseur injecté par CALX5 — ici, un simple compteur d'appels."""

    def __init__(self):
        self.appels = []

    def __call__(self, plan):
        self.appels.append(plan.get('cle'))
        return {'pas_minutes': 60, 'points': [{'p_w': 1.0}],
                'pan': plan.get('cle')}


def contexte_de(plans, fournisseur):
    return {'site': dict(SITE), 'plans': list(plans),
            CLE_FOURNISSEUR_METEO: fournisseur}


class UneRequeteParPlanTest(unittest.TestCase):
    """Deux pans de mêmes angles = un seul appel."""

    def test_trois_pans_dont_deux_identiques_font_deux_appels(self):
        plans = [
            {'cle': 'A', 'inclinaison_deg': 20.0, 'azimut_pvgis_deg': 0.0},
            {'cle': 'B', 'inclinaison_deg': 20.0, 'azimut_pvgis_deg': 0.0},
            {'cle': 'C', 'inclinaison_deg': 35.0, 'azimut_pvgis_deg': -90.0},
        ]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)

        acces = contexte[CLE_METEO_PARTAGEE]
        for plan in plans:
            acces(plan)
        self.assertEqual(len(fournisseur.appels), 2,
                         'les pans A et B partagent inclinaison et azimut : '
                         'ils partagent la requête.')
        self.assertEqual(contexte['meteo']['appels_pvgis'], 2)

    def test_cinq_cents_modules_d_un_seul_plan_font_un_appel(self):
        plans = [{'cle': 'A', 'inclinaison_deg': 20.0,
                  'azimut_pvgis_deg': 0.0}]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)

        acces = contexte[CLE_METEO_PARTAGEE]
        for _ in range(500):
            acces('A')
        self.assertEqual(len(fournisseur.appels), 1,
                         'la météo se demande par PLAN : cinq cents modules '
                         'du même pan ne font pas cinq cents requêtes.')
        self.assertEqual(contexte['meteo']['appels_pvgis'], 1)

    def test_la_serie_rendue_est_bien_celle_du_pan(self):
        plans = [{'cle': 'A', 'inclinaison_deg': 20.0,
                  'azimut_pvgis_deg': 0.0}]
        contexte = contexte_de(plans, Compteur())
        appliquer_chaine(SERIE, contexte)
        self.assertEqual(contexte[CLE_METEO_PARTAGEE]('A')['pan'], 'A')


class CleDeCachePartageeTest(unittest.TestCase):
    """La clé est celle du cache existant : arrondie, pas exacte."""

    def test_deux_pans_au_dixieme_de_degre_pres_partagent_l_appel(self):
        plans = [
            {'cle': 'A', 'inclinaison_deg': 20.01, 'azimut_pvgis_deg': 0.02},
            {'cle': 'B', 'inclinaison_deg': 20.04, 'azimut_pvgis_deg': 0.01},
        ]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)
        for plan in plans:
            contexte[CLE_METEO_PARTAGEE](plan)
        self.assertEqual(len(fournisseur.appels), 1)

    def test_un_dixieme_de_degre_d_ecart_fait_bien_deux_appels(self):
        plans = [
            {'cle': 'A', 'inclinaison_deg': 20.0, 'azimut_pvgis_deg': 0.0},
            {'cle': 'B', 'inclinaison_deg': 20.4, 'azimut_pvgis_deg': 0.0},
        ]
        fournisseur = Compteur()
        contexte = contexte_de(plans, fournisseur)
        appliquer_chaine(SERIE, contexte)
        for plan in plans:
            contexte[CLE_METEO_PARTAGEE](plan)
        self.assertEqual(len(fournisseur.appels), 2)


class RefusTest(unittest.TestCase):
    """Un pan sans angle ne se partage pas en silence : il est NOMMÉ."""

    def test_un_pan_sans_inclinaison_est_refuse_en_nommant_le_champ(self):
        plans = [{'cle': 'A', 'azimut_pvgis_deg': 0.0}]
        contexte = contexte_de(plans, Compteur())
        appliquer_chaine(SERIE, contexte)
        with self.assertRaises(ChaineInvalide) as capture:
            contexte[CLE_METEO_PARTAGEE]('A')
        self.assertIn('inclinaison_deg', str(capture.exception))

    def test_un_site_sans_coordonnees_est_refuse_en_les_nommant(self):
        contexte = {'site': {}, 'plans': [], CLE_FOURNISSEUR_METEO: Compteur()}
        appliquer_chaine(SERIE, contexte)
        with self.assertRaises(ChaineInvalide) as capture:
            contexte[CLE_METEO_PARTAGEE](
                {'cle': 'A', 'inclinaison_deg': 20.0,
                 'azimut_pvgis_deg': 0.0})
        self.assertIn('site.lat', str(capture.exception))

    def test_un_pan_inconnu_du_document_est_refuse(self):
        contexte = contexte_de([], Compteur())
        appliquer_chaine(SERIE, contexte)
        with self.assertRaises(ChaineInvalide) as capture:
            contexte[CLE_METEO_PARTAGEE]('fantome')
        self.assertIn('fantome', str(capture.exception))


class SansFournisseurTest(unittest.TestCase):
    """Sans fournisseur, la chaîne tourne — elle n'invente pas de météo."""

    def test_aucun_acces_n_est_installe(self):
        contexte = {'site': dict(SITE)}
        _, cascade = appliquer_chaine(SERIE, contexte)
        self.assertNotIn(CLE_METEO_PARTAGEE, contexte)
        self.assertTrue(cascade['etapes'])

    def test_un_acces_deja_pose_n_est_pas_remplace(self):
        temoin = []

        def deja_la(pan):
            temoin.append(pan)
            return SERIE

        contexte = {'site': dict(SITE), CLE_METEO_PARTAGEE: deja_la,
                    CLE_FOURNISSEUR_METEO: Compteur()}
        appliquer_chaine(SERIE, contexte)
        contexte[CLE_METEO_PARTAGEE]('A')
        self.assertEqual(temoin, ['A'])


# ── ACAL468 — le balayage d'orientation : UN appel par couple distinct ──────
class _Limiteur0:
    def attendre_son_tour(self):
        pass


def _layout_champ_au_sol(**surface):
    base = {'id': 'sol-1', 'kind': 'sol', 'label': 'Champ', 'moduleWc': 500,
            'tiltDeg': 15, 'rowAzimuthDeg': 90, 'engine': {'modules': 10}}
    base.update(surface)
    return {'zones': [], 'poseSurfaces': [base]}


def _client_enregistre(cache=None):
    """Un ClientPvgis dont le transport COMPTE les appels réels."""
    from apps.calepinage.services.pvgis_serie import ClientPvgis, _Cache

    reseau = []

    def transport(url, timeout_s):
        reseau.append(url)
        return 200, '{"ok": 1}'

    client = ClientPvgis(transport=transport, limiteur=_Limiteur0(),
                         cache=cache if cache is not None else _Cache())
    return client, reseau


def _simuler_enregistre(cal, *, variante, client):
    """Une « simulation » qui ne fait que l'appel PVGIS du plan du point
    (angle = tiltDeg, aspect = azimut de face PVGIS) et rend un rendement
    maximal à 20° / Sud."""
    surface = variante.roof_layout['poseSurfaces'][0]
    angle = surface['tiltDeg']
    face = (surface['rowAzimuthDeg'] + 90.0) % 360.0
    client._appeler('seriescalc', {'lat': 33.57, 'lon': -7.59,
                                   'angle': angle, 'aspect': face - 180.0})
    rendement = 1500.0 - abs(angle - 20.0) * 10 - abs(face - 180.0)
    return {'blocs': {'production': {'total': {
        'p50_kwh': rendement * 5, 'specific_yield_kwh_kwc': rendement,
        'complete': True, 'socle_manquant': []}}}}


CORPS_3X3 = {'pan': 1, 'axes': [
    {'nom': 'inclinaison_deg', 'min': 10, 'max': 30, 'pas': 10},
    {'nom': 'azimut_deg', 'min': 150, 'max': 210, 'pas': 30}]}


#: ACAL812 — les clés que le seul ``critere`` ajoute au résultat.
CLES_CRITERE_RESULTAT = {'optimum_mois', 'ecart_mois_kwh'}


def _simuler_avec_mois(cal, *, variante, client):
    """``_simuler_enregistre`` + une production MENSUELLE connue : l'énergie
    de chaque mois vaut ``100 × mois`` kWh, plus un bonus de 10 kWh au mois 7
    quand l'inclinaison est 30° (c'est elle qui gagne en juillet)."""
    sortie = _simuler_enregistre(cal, variante=variante, client=client)
    angle = variante.roof_layout['poseSurfaces'][0]['tiltDeg']
    sortie['blocs']['production']['total']['kwc'] = 5.0
    sortie['blocs']['production']['mensuel'] = [
        {'mois': mois, 'p50_kwh': 100.0 * mois
         + (10.0 if mois == 7 and angle == 30 else 0.0)}
        for mois in range(1, 13)]
    return sortie


def _contrat_balayage(cle):
    import json
    import pathlib

    chemin = (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
              / 'calepinage_balayage.json')
    return json.loads(chemin.read_text(encoding='utf-8'))[cle]


class BalayageAppelsPvgisTest(unittest.TestCase):
    def _cal(self, layout=None):
        import types

        return types.SimpleNamespace(
            roof_layout=layout or _layout_champ_au_sol(), pk=1)

    def test_neuf_points_font_neuf_appels_et_le_rejeu_zero(self):
        from apps.calepinage.services.balayage import balayer

        client, reseau = _client_enregistre()
        premier = balayer(self._cal(), CORPS_3X3, client=client,
                          simuler=_simuler_enregistre)
        self.assertEqual(len(premier['grille']), 9)
        self.assertEqual(len(reseau), 9)
        self.assertEqual(premier['appels_pvgis'], 9)
        client2, _ = _client_enregistre(cache=client.cache)
        client2.transport = client.transport
        rejeu = balayer(self._cal(), CORPS_3X3, client=client2,
                        simuler=_simuler_enregistre)
        self.assertEqual(len(reseau), 9, 'le rejeu ne doit rien appeler')
        self.assertEqual(rejeu['appels_pvgis'], 0)
        self.assertEqual(rejeu['grille'], premier['grille'])

    def test_optimum_grille_et_forme_du_contrat(self):
        import json

        from apps.calepinage.services.balayage import balayer

        client, _ = _client_enregistre()
        cal = self._cal()
        avant = json.dumps(cal.roof_layout, sort_keys=True)
        sortie = balayer(cal, CORPS_3X3, client=client,
                         simuler=_simuler_enregistre)
        self.assertEqual(sortie['optimum']['inclinaison_deg'], 20.0)
        self.assertEqual(sortie['optimum']['azimut_deg'], 180.0)
        self.assertEqual(json.dumps(cal.roof_layout, sort_keys=True), avant,
                         'le document du calepinage ne doit pas bouger')
        # Sans ``critere`` : les clés du critère (ACAL812) ne sortent pas.
        self.assertEqual(sorted(sortie), sorted(
            set(_contrat_balayage('exemple_resultat')) - CLES_CRITERE_RESULTAT))
        for ligne in sortie['grille']:
            self.assertEqual(
                sorted(ligne),
                sorted(['inclinaison_deg', 'azimut_deg', 'p50_kwh',
                        'rendement_specifique_kwh_kwc']))

    def test_acal812_critere_mois_lit_l_index_du_mois_sans_appel_de_plus(self):
        from apps.calepinage.services.balayage import balayer

        client, reseau = _client_enregistre()
        sortie = balayer(self._cal(), dict(CORPS_3X3, critere={
            'nom': 'mois', 'mois': 7}), client=client,
            simuler=_simuler_avec_mois)
        self.assertEqual(len(sortie['grille']), 9)
        self.assertEqual(len(reseau), 9, 'aucun appel PVGIS de plus')
        self.assertEqual(sortie['appels_pvgis'], 9)
        for ligne in sortie['grille']:
            bonus = 10.0 if ligne['inclinaison_deg'] == 30 else 0.0
            # Juillet = index 6 de production.mensuel (700 kWh), jamais
            # l'index 7 (août, 800 kWh).
            self.assertEqual(ligne['p50_mois_kwh'], 700.0 + bonus)
            self.assertEqual(ligne['rendement_mois_kwh_kwc'],
                             (700.0 + bonus) / 5.0)
        # L'optimum de l'année reste celui du rendement ANNUEL (20°, Sud) ;
        # celui de juillet est à 30° (rendement du mois maximal).
        self.assertEqual(sortie['optimum']['inclinaison_deg'], 20.0)
        self.assertEqual(sortie['optimum_mois']['inclinaison_deg'], 30.0)
        # 710 (juillet à 30°) − 700 (juillet à l'optimum de l'année).
        self.assertEqual(sortie['ecart_mois_kwh'], 10.0)
        self.assertEqual(
            sorted(sortie),
            sorted(_contrat_balayage('exemple_resultat')))
        self.assertEqual(
            sorted(sortie['grille'][0]), sorted(
                ['inclinaison_deg', 'azimut_deg', 'p50_kwh',
                 'rendement_specifique_kwh_kwc', 'p50_mois_kwh',
                 'rendement_mois_kwh_kwc']))

    def test_acal812_sans_critere_aucune_cle_de_plus(self):
        from apps.calepinage.services.balayage import balayer

        client, _ = _client_enregistre()
        sortie = balayer(self._cal(), CORPS_3X3, client=client,
                         simuler=_simuler_avec_mois)
        self.assertEqual(CLES_CRITERE_RESULTAT & set(sortie), set())
        self.assertNotIn('p50_mois_kwh', sortie['grille'][0])

    def test_acal812_critere_mal_forme_nomme_critere_mois(self):
        from apps.calepinage.services.balayage import (
            BalayageInvalide, valider_demande)

        layout = _layout_champ_au_sol()
        for mois in (0, 13, 7.5, '7', True, None):
            with self.subTest(mois=mois):
                with self.assertRaises(BalayageInvalide) as capture:
                    valider_demande(layout, dict(CORPS_3X3, critere={
                        'nom': 'mois', 'mois': mois}))
                self.assertEqual(capture.exception.champ, 'critere.mois')
                self.assertTrue(capture.exception.forme)  # 400
        with self.assertRaises(BalayageInvalide) as capture:
            valider_demande(layout, dict(CORPS_3X3, critere={'nom': 'an'}))
        self.assertEqual(capture.exception.champ, 'critere')
        valider_demande(layout, dict(CORPS_3X3, critere={'nom': 'mois',
                                                         'mois': 12}))

    def test_acal812_le_corps_du_contrat_porte_le_critere(self):
        from apps.calepinage.services.balayage import valider_demande

        corps = _contrat_balayage('exemple_corps')
        self.assertEqual(corps['critere'], {'nom': 'mois', 'mois': 7})
        valider_demande(_layout_champ_au_sol(), corps)

    def test_un_client_neuf_par_point_est_detecte(self):
        """Mutant : sans le client partagé, le cache ne sert plus."""
        from apps.calepinage.services.balayage import balayer

        client, reseau = _client_enregistre()
        balayer(self._cal(), CORPS_3X3, client=client,
                simuler=_simuler_enregistre)

        def un_client_par_point(cal, *, variante, client):
            neuf, _ = _client_enregistre()
            neuf.transport = client.transport
            return _simuler_enregistre(cal, variante=variante, client=neuf)

        avant = len(reseau)
        balayer(self._cal(), CORPS_3X3, client=client,
                simuler=un_client_par_point)
        self.assertGreater(len(reseau), avant)

    def test_refus_nommes(self):
        from apps.calepinage.services.balayage import (
            BalayageInvalide, valider_demande)

        layout = _layout_champ_au_sol()
        axe = {'nom': 'inclinaison_deg', 'min': 10, 'max': 30, 'pas': 10}
        cas = [
            ({'pan': 1, 'axes': [dict(axe, pas=0)]}, 'axes[0].pas'),
            ({'pan': 1, 'axes': [dict(axe, pas=0.01, max=90)]},
             'axes[0].pas'),
            ({'pan': 9, 'axes': [axe]}, 'pan'),
            ({'pan': 1, 'axes': []}, 'axes'),
            ({'pan': 1, 'axes': [dict(axe, nom='ratio_dc_ac', min=0)]},
             'axes[0].min'),
            ({'pan': 1, 'axes': [
                {'nom': 'inclinaison_deg', 'min': 0, 'max': 90, 'pas': 1},
                {'nom': 'azimut_deg', 'min': 0, 'max': 360, 'pas': 5}]},
             'axes'),
        ]
        for corps, champ in cas:
            with self.assertRaises(BalayageInvalide) as capture:
                valider_demande(layout, corps)
            self.assertEqual(capture.exception.champ, champ, corps)
        valider_demande(layout, {'pan': 1, 'axes': [axe]})

    def test_pan_a_pente_imposee_par_le_toit_est_refuse(self):
        from apps.calepinage.services.balayage import (
            BalayageInvalide, valider_demande)

        toit = {'zones': [{'id': 'z1', 'label': 'Pan A',
                           'roofType': 'pitched', 'pitchDeg': 22,
                           'facingAzimuthDeg': 180,
                           'geometry': {'count': 8}}]}
        axes = [{'nom': 'inclinaison_deg', 'min': 10, 'max': 30, 'pas': 10}]
        with self.assertRaises(BalayageInvalide) as capture:
            valider_demande(toit, {'pan': 'z1', 'axes': axes})
        self.assertEqual(capture.exception.champ, 'pan')
        plat = {'zones': [dict(toit['zones'][0], roofType='flat')]}
        valider_demande(plat, {'pan': 'z1', 'axes': axes})

    def test_accuse_de_la_vue_a_les_cles_du_contrat(self):
        import types

        from apps.calepinage.views.balayage import accuse_de_balayage

        job = types.SimpleNamespace(pk=1, kind='calepinage',
                                    statut='en_attente', progress_pct=0,
                                    message_erreur='')
        self.assertEqual(accuse_de_balayage(job),
                         _contrat_balayage('exemple'))


class ClientHorizontal:
    """ACAL465 — un client double : compte les lectures d'irradiance."""

    def __init__(self, *, depuis_cache=False, erreur=None):
        self.demandes = []
        self.depuis_cache = depuis_cache
        self.erreur = erreur

    def serie_irradiance(self, **parametres):
        self.demandes.append(parametres)
        if self.erreur is not None:
            raise self.erreur
        return {'points': [{'annee': 2020, 'mois': 6, 'jour': 15,
                            'heure': 12, 'gi_w_m2': 900.0,
                            'gd_i_w_m2': 150.0}],
                'serie_horaire': {'pas_minutes': 60},
                'depuis_cache': self.depuis_cache}


class SerieHorizontaleBifacialeTest(unittest.TestCase):
    """ACAL465 — UN appel de plus par site, seulement si la fiche est
    bifaciale, et compté dans ``appels_pvgis``."""

    def _poser(self, fiche, client, *, fichier=None):
        from apps.calepinage.services.simulation import _poser_horizontale

        contexte = {'fiche_module': fiche, 'meteo': {'heure': {'base': 'utc'}},
                    'site': dict(SITE)}
        compteur = {'appels': 0}
        _poser_horizontale(
            contexte, client=client, decision={'fenetre_annees': (2020, 2020)},
            fichier=fichier, compteur=compteur,
            plan={'lat': 33.5, 'lon': -7.6})
        return contexte, compteur

    def test_fiche_bifaciale_un_appel_horizontal_compte(self):
        client = ClientHorizontal()
        contexte, compteur = self._poser({'bifacialite_pct': 70.0}, client)

        self.assertEqual(compteur['appels'], 1)
        demande = client.demandes[0]
        self.assertEqual(demande['inclinaison_deg'], 0.0)
        self.assertTrue(demande['composantes'])
        self.assertTrue(demande['masque_dans_la_geometrie'])
        self.assertEqual(
            len(contexte['serie_horizontale_legale']['points']), 1)

    def test_acal1959_le_module_pose_bifacial_declenche_l_appel(self):
        # Défaut monofacial, module POSÉ bifacial : l'étape bifaciale lit le posé, la série horizontale aussi.
        from apps.calepinage.services.simulation import _poser_horizontale

        client = ClientHorizontal()
        contexte = {'fiche_module': {'puissance_wc': 500.0},
                    'fiche_module_pose': {'bifacialite_pct': 70.0},
                    'meteo': {'heure': {'base': 'utc'}}, 'site': dict(SITE)}
        compteur = {'appels': 0}
        _poser_horizontale(
            contexte, client=client, decision={'fenetre_annees': (2020, 2020)},
            fichier=None, compteur=compteur, plan={'lat': 33.5, 'lon': -7.6})
        self.assertEqual(compteur['appels'], 1)
        # Posé == défaut (aucune fiche posée) : lecture inchangée.
        contexte.pop('fiche_module_pose')
        compteur['appels'] = 0
        _poser_horizontale(
            contexte, client=ClientHorizontal(), decision={'fenetre_annees': (2020, 2020)},
            fichier=None, compteur=compteur, plan={'lat': 33.5, 'lon': -7.6})
        self.assertEqual(compteur['appels'], 0)

    def test_fiche_monofaciale_ou_fichier_depose_aucun_appel(self):
        for fiche, fichier in (({'puissance_wc': 500.0}, None),
                               ({'bifacialite_pct': 70.0}, {'points': []})):
            with self.subTest(fiche=fiche):
                client = ClientHorizontal()
                contexte, compteur = self._poser(fiche, client,
                                                 fichier=fichier)
                self.assertEqual(client.demandes, [])
                self.assertEqual(compteur['appels'], 0)
                self.assertNotIn('serie_horizontale_legale', contexte)

    def test_reponse_du_cache_non_comptee_et_refus_replie(self):
        _, compteur = self._poser({'bifacialite_pct': 70.0},
                                  ClientHorizontal(depuis_cache=True))
        self.assertEqual(compteur['appels'], 0)

        from apps.calepinage.services.pvgis_serie import PvgisIndisponible

        contexte, compteur = self._poser(
            {'bifacialite_pct': 70.0},
            ClientHorizontal(erreur=PvgisIndisponible('hors ligne')))
        self.assertEqual(compteur['appels'], 0)
        self.assertNotIn('serie_horizontale_legale', contexte)


def _serie_deux_ans(gi_par_mois):
    """Une série « enregistrée » de DEUX années : un point de 1 h par mois."""
    return {'points': [{'annee': annee, 'mois': mois, 'jour': 15, 'heure': 12,
                        'gi_w_m2': gi_par_mois[mois - 1]}
                       for annee in (2019, 2020) for mois in range(1, 13)],
            'serie_horaire': {'pas_minutes': 60}}


class ClientDeuxSeries:
    """Rejoue la série à 0° (horizontale) ou celle du plan selon l'angle."""

    def __init__(self, horizontale, erreur=None):
        self.horizontale, self.erreur, self.demandes = horizontale, erreur, []

    def serie_irradiance(self, **parametres):
        self.demandes.append(parametres)
        if self.erreur is not None:
            raise self.erreur
        return dict(self.horizontale, depuis_cache=False)


class GainInclinaisonTest(unittest.TestCase):
    """ACAL706 — gain = rapport de DEUX irradiations servies, à l'année
    moyenne ; une requête impossible nomme son motif."""

    GHI = [600.0 + 50 * m for m in range(12)]
    PLAN = [700.0 + 50 * m for m in range(12)]

    def _irradiation_mensuelle(self):
        # Le plan à l'ANNÉE MOYENNE (deux années / 2), en kWh/m² (1 h).
        return [{'mois': m + 1, 'irradiation_plan_kwh_m2': self.PLAN[m] / 1000}
                for m in range(12)]

    def test_gain_egal_au_rapport_des_deux_irradiations(self):
        from apps.calepinage.services import gain_inclinaison as gi

        client = ClientDeuxSeries(_serie_deux_ans(self.GHI))
        compteur = {'appels': 0}
        bloc = gi.demander(client, {'lat': 33.5, 'lon': -7.6},
                           {'fenetre_annees': (2019, 2020)}, None, compteur,
                           {'irradiation_mensuelle':
                            self._irradiation_mensuelle()})
        # Référence calculée ICI : Σ sur deux ans ÷ 2 ans.
        ghi_annuel = sum(self.GHI) * 2 / 1000 / 2
        plan_annuel = sum(self.PLAN) / 1000
        self.assertAlmostEqual(bloc['ghi_annuel_kwh_m2'], ghi_annuel, places=3)
        self.assertAlmostEqual(bloc['plan_annuel_kwh_m2'], plan_annuel,
                               places=3)
        self.assertAlmostEqual(bloc['gain_pct'],
                               (plan_annuel / ghi_annuel - 1) * 100, places=2)
        self.assertGreater(bloc['gain_pct'], 0)
        self.assertEqual(len(bloc['ghi_mensuel']), 12)
        self.assertEqual(compteur['appels'], 1)
        self.assertEqual(client.demandes[0]['inclinaison_deg'], 0.0)
        self.assertEqual(client.demandes[0]['annee_debut'], 2019)

    def test_lire_le_plan_comme_horizontal_donnerait_un_gain_nul(self):
        from apps.calepinage.services import gain_inclinaison as gi

        bloc = gi.depuis_serie(_serie_deux_ans(self.PLAN),
                               self._irradiation_mensuelle())
        self.assertAlmostEqual(bloc['gain_pct'], 0.0, places=2)

    def test_mois_du_plan_inconnu_et_refus_nommes(self):
        from apps.calepinage.services import gain_inclinaison as gi
        from apps.calepinage.services.pvgis_serie import PvgisIndisponible

        irr = self._irradiation_mensuelle()
        irr[3]['irradiation_plan_kwh_m2'] = None
        bloc = gi.depuis_serie(_serie_deux_ans(self.GHI), irr)
        self.assertIsNone(bloc['plan_annuel_kwh_m2'])
        self.assertIsNone(bloc['gain_pct'])
        self.assertTrue(bloc['motif_omission'])
        compteur = {'appels': 0}
        refuse = gi.demander(
            ClientDeuxSeries({}, erreur=PvgisIndisponible('hors ligne')),
            {'lat': 33.5, 'lon': -7.6}, {'fenetre_annees': (2019, 2020)},
            None, compteur, {})
        self.assertIsNone(refuse['gain_pct'])
        self.assertIn('hors ligne', refuse['motif_omission'])
        self.assertEqual(compteur['appels'], 0)
        fichier = gi.demander(ClientDeuxSeries({}), {}, {}, {'points': []},
                              compteur, {})
        self.assertTrue(fichier['motif_omission'])


if __name__ == '__main__':
    unittest.main()
