"""CALX62 — la série météo DÉPOSÉE par la société : lue, ou refusée en nommant.

CE QUI EST PROUVÉ ICI
---------------------
1. **La forme rendue est celle de PVGIS** — ``lire_serie_meteo`` rend le même
   document que ``ClientPvgis.serie_irradiance`` (CALX150) : mêmes clés, mêmes
   colonnes de point, même bloc ``serie_horaire`` (CALX142). La chaîne de
   pertes ne voit donc aucune différence entre les deux sources.
2. **La PROPRIÉTÉ qui compte** : un fichier de 8 760 lignes en irradiance de
   PLAN produit la MÊME cascade qu'une réponse PVGIS portant les mêmes
   valeurs — points identiques, série persistée identique, cascade identique.
   C'est ce qui autorise à substituer une source à l'autre.
3. **Les refus NOMMENT** : la colonne horizontale quand seule la GHI est là,
   la ligne quand un horodatage n'a pas de fuseau, la ligne quand le
   calendrier est troué, en doublon ou désordonné.
4. **σ ne se fabrique pas** : un fichier d'UNE année ne donne aucun σ mesuré
   (``services/p50p90.py::variabilite_interannuelle`` rend ``absente``), quel
   que soit le mode choisi par la société.
5. **La route existe** et elle est gardée : ``meteo-fichier``, POST seul,
   ``PeutGererCalepinage``, multipart.

LES FICHIERS D'ESSAI SONT SYNTHÉTIQUES, ET ASSUMÉS (D-CALX 7) : irradiances et
températures sont une courbe en cloche d'essai, elles ne décrivent aucune
station ni aucune installation réelle. La réponse PVGIS de la propriété est
fabriquée à partir des MÊMES valeurs, pour que la comparaison porte sur la
mécanique et non sur un jeu de chiffres.

Aucune base de données, aucun réseau : ``SimpleTestCase`` partout, transport
PVGIS injecté.

Run :
    python manage.py test apps.calepinage.tests.test_calx62_meteo_fichier -v2
"""
from __future__ import annotations

import datetime
import json
import math
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.meteo_fichier import (
    COLONNE_HORODATAGE,
    COLONNE_IRRADIANCE_PLAN,
    LIGNES_MAX,
    MeteoFichierRefuse,
    lire_serie_meteo,
)
from apps.calepinage.services.p50p90 import variabilite_interannuelle
from apps.calepinage.services.pvgis_serie import (
    COLONNES_COMPOSANTES, MOTIF_COMPOSANTES_ABSENTES, ClientPvgis, _Cache,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads((ECHANTILLONS / 'calepinage_meteo_fichier.json')
                     .read_text(encoding='utf-8'))

#: Horodatage FIGÉ : un test ne dépend jamais de l'horloge murale.
OBTENUE_LE = '2026-09-21T09:00:00+00:00'

EN_TETE = ('horodatage;gi_w_m2;gb_i_w_m2;gd_i_w_m2;gr_i_w_m2;t2m_c;ws10m')


def _valeurs_essai(heure):
    """Une courbe en cloche d'ESSAI — aucune mesure, aucune station."""
    arche = max(0.0, math.sin(math.pi * (heure - 6) / 12.0))
    globale = round(900.0 * arche, 2)
    return {
        'gi_w_m2': globale,
        'gb_i_w_m2': round(globale * 0.75, 2),
        'gd_i_w_m2': round(globale * 0.2, 2),
        'gr_i_w_m2': round(globale * 0.05, 2),
        't2m_c': round(12.0 + 10.0 * arche, 2),
        'ws10m': 2.5,
    }


def _instants(nombre, *, depart=None, decalage_minutes=0, pas_minutes=60):
    """``nombre`` instants consécutifs, fuseau EXPLICITE."""
    fuseau = datetime.timezone(datetime.timedelta(minutes=decalage_minutes))
    debut = depart or datetime.datetime(2021, 1, 1, 0, 0, tzinfo=fuseau)
    return [debut + datetime.timedelta(minutes=pas_minutes * rang)
            for rang in range(nombre)]


def _csv(moments):
    """Le CSV d'essai : en-tête nommé, décimale « . », séparateur « ; »."""
    lignes = [EN_TETE]
    for moment in moments:
        valeurs = _valeurs_essai(moment.hour)
        lignes.append(';'.join([
            moment.isoformat(),
            str(valeurs['gi_w_m2']), str(valeurs['gb_i_w_m2']),
            str(valeurs['gd_i_w_m2']), str(valeurs['gr_i_w_m2']),
            str(valeurs['t2m_c']), str(valeurs['ws10m']),
        ]))
    return '\r\n'.join(lignes) + '\r\n'


def _lire(texte, **extra):
    parametres = {'fournisseur': 'Station d essai', 'nom_fichier': 'essai.csv',
                  'obtenue_le': OBTENUE_LE}
    parametres.update(extra)
    return lire_serie_meteo(texte.encode('utf-8'), **parametres)


class FormeRendueTest(SimpleTestCase):
    """Ce que la chaîne reçoit : la forme de ``serie_irradiance``."""

    def setUp(self):
        self.serie = _lire(_csv(_instants(24, decalage_minutes=60)))

    def test_les_cles_du_document_sont_celles_du_client_pvgis(self):
        for cle in ('service', 'points', 'composantes_disponibles',
                    'motif_composantes', 'serie_horaire', 'meteo', 'annees',
                    'url', 'depuis_cache'):
            self.assertIn(cle, self.serie, cle)
        self.assertEqual(self.serie['service'], 'fichier')
        self.assertIsNone(self.serie['url'])
        self.assertFalse(self.serie['depuis_cache'])

    def test_chaque_point_porte_les_colonnes_du_contrat(self):
        point = self.serie['points'][12]
        for colonne in ('annee', 'mois', 'jour', 'heure', 'gi_w_m2', 't2m_c',
                        'ws10m', 'h_sun_deg') + COLONNES_COMPOSANTES:
            self.assertIn(colonne, point, colonne)
        # Un fichier ne porte pas la hauteur du soleil : elle reste NULLE
        # plutôt que d'être calculée ici.
        self.assertIsNone(point['h_sun_deg'])
        self.assertEqual(point['gi_w_m2'], _valeurs_essai(12)['gi_w_m2'])

    def test_le_bloc_serie_horaire_est_celui_de_calx142(self):
        bloc = self.serie['serie_horaire']
        for cle in ('pas_minutes', 'tronquee', 'colonnes', 'points'):
            self.assertIn(cle, bloc, cle)
        self.assertEqual(bloc['pas_minutes'], 60)
        self.assertFalse(bloc['tronquee'])
        self.assertEqual(bloc['colonnes'],
                         CONTRAT['exemple']['serie']['colonnes'])

    def test_la_provenance_est_publiee_et_saisie(self):
        meteo = self.serie['meteo']
        self.assertEqual(meteo['service'], 'fichier')
        self.assertEqual(meteo['fournisseur'], 'Station d essai')
        self.assertEqual(meteo['fichier']['nom'], 'essai.csv')
        self.assertEqual(meteo['fichier']['lignes'], 24)
        self.assertEqual(len(meteo['fichier']['empreinte_sha256']), 64)
        self.assertEqual(meteo['obtenue_le'], OBTENUE_LE)
        # Les décalages sont ceux RÉELLEMENT lus dans le fichier.
        self.assertEqual(meteo['heure']['decalage_minutes'], [60])
        # Heure locale : la base reste NULLE — choisir entre heure standard et
        # heure légale à la place de la société serait une supposition.
        self.assertIsNone(meteo['heure']['base'])

    def test_aucune_cle_pvgis_nest_remplie_dune_valeur_plausible(self):
        meteo = self.serie['meteo']
        for cle in ('base_rayonnement', 'base_demandee', 'base_meteo', 'mode',
                    'url'):
            self.assertIsNone(meteo[cle], cle)
        for cle in ('lat', 'lon', 'altitude_m'):
            self.assertIsNone(meteo['point'][cle], cle)
        self.assertEqual(meteo['horizon']['origine'], 'aucun')

    def test_un_fichier_en_utc_declare_sa_base(self):
        serie = _lire(_csv(_instants(24, decalage_minutes=0)))
        self.assertEqual(serie['meteo']['heure']['decalage_minutes'], [0])
        self.assertEqual(serie['meteo']['heure']['base'], 'utc')


class ComposantesTest(SimpleTestCase):
    """Sans les trois composantes, le motif UNIQUE du module est publié."""

    def test_sans_composantes_le_motif_est_celui_de_calx152(self):
        lignes = ['horodatage;gi_w_m2;t2m_c']
        for moment in _instants(3):
            lignes.append('{0};{1};{2}'.format(
                moment.isoformat(), _valeurs_essai(moment.hour)['gi_w_m2'],
                _valeurs_essai(moment.hour)['t2m_c']))
        serie = _lire('\r\n'.join(lignes))

        self.assertFalse(serie['composantes_disponibles'])
        self.assertEqual(serie['motif_composantes'],
                         MOTIF_COMPOSANTES_ABSENTES)
        for colonne in COLONNES_COMPOSANTES:
            self.assertIsNone(serie['points'][0][colonne])

    def test_avec_les_trois_composantes_elles_sont_disponibles(self):
        serie = _lire(_csv(_instants(3)))
        self.assertTrue(serie['composantes_disponibles'])
        self.assertIsNone(serie['motif_composantes'])


class RefusQuiNommentTest(SimpleTestCase):
    """Chaque refus pointe SA colonne — et sa ligne quand elle est connue."""

    def test_un_fichier_seulement_horizontal_est_refuse_en_nommant_la_colonne(self):
        lignes = ['horodatage;ghi_w_m2;t2m_c',
                  '2021-01-15T13:00:00+01:00;780.0;19.8']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertEqual(leve.exception.champ, 'ghi_w_m2')
        self.assertIn('CALX198', leve.exception.motif)
        self.assertIn('gi_w_m2', leve.exception.motif)

    def test_sans_aucune_irradiance_de_plan_le_refus_nomme_la_colonne_attendue(self):
        lignes = ['horodatage;t2m_c', '2021-01-15T13:00:00+01:00;19.8']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertEqual(leve.exception.champ, COLONNE_IRRADIANCE_PLAN)

    def test_un_horodatage_sans_fuseau_est_refuse_en_nommant_la_ligne(self):
        lignes = ['horodatage;gi_w_m2', '2021-01-15T13:00:00;780.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertEqual(leve.exception.champ, COLONNE_HORODATAGE)
        self.assertEqual(leve.exception.ligne, 2)
        self.assertIn('fuseau', leve.exception.motif)

    def test_un_horodatage_illisible_est_refuse_en_nommant_la_ligne(self):
        lignes = ['horodatage;gi_w_m2', '15/01/2021 13h;780.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertEqual(leve.exception.champ, COLONNE_HORODATAGE)
        self.assertEqual(leve.exception.ligne, 2)

    def test_un_doublon_dheure_est_refuse_en_nommant_la_ligne(self):
        lignes = ['horodatage;gi_w_m2',
                  '2021-01-15T13:00:00+01:00;780.0',
                  '2021-01-15T13:00:00+01:00;790.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertEqual(leve.exception.ligne, 3)
        self.assertIn('répète', leve.exception.motif)

    def test_un_trou_dans_le_calendrier_est_refuse(self):
        lignes = ['horodatage;gi_w_m2',
                  '2021-01-15T13:00:00+01:00;780.0',
                  '2021-01-15T15:00:00+01:00;700.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertEqual(leve.exception.champ, COLONNE_HORODATAGE)
        self.assertIn('120 minutes', leve.exception.motif)

    def test_un_fichier_desordonne_est_refuse(self):
        lignes = ['horodatage;gi_w_m2',
                  '2021-01-15T14:00:00+01:00;700.0',
                  '2021-01-15T13:00:00+01:00;780.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertIn('croissant', leve.exception.motif)

    def test_une_irradiance_manquante_est_refusee_en_nommant_la_ligne(self):
        lignes = ['horodatage;gi_w_m2',
                  '2021-01-15T13:00:00+01:00;',
                  '2021-01-15T14:00:00+01:00;700.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))

        self.assertEqual(leve.exception.champ, COLONNE_IRRADIANCE_PLAN)
        self.assertEqual(leve.exception.ligne, 2)

    def test_un_fichier_vide_est_refuse(self):
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('')
        self.assertEqual(leve.exception.champ, 'fichier')

    def test_un_entete_seul_est_refuse(self):
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire(EN_TETE)
        self.assertEqual(leve.exception.champ, 'fichier')

    def test_la_borne_de_lignes_vient_du_calendrier(self):
        # Dix années bissextiles au pas horaire — la borne n'est pas un
        # chiffre choisi ici, elle est dérivée.
        self.assertEqual(LIGNES_MAX, 366 * 24 * 10)


class FormatsAdmisTest(SimpleTestCase):
    """Les deux séparateurs, et la décimale française."""

    def test_le_point_virgule_accepte_la_decimale_francaise(self):
        lignes = ['horodatage;gi_w_m2;t2m_c',
                  '2021-01-15T13:00:00+01:00;780,5;19,8']
        serie = _lire('\r\n'.join(lignes))
        self.assertEqual(serie['points'][0]['gi_w_m2'], 780.5)
        self.assertEqual(serie['points'][0]['t2m_c'], 19.8)

    def test_la_virgule_separatrice_est_admise(self):
        lignes = ['horodatage,gi_w_m2,t2m_c',
                  '2021-01-15T13:00:00+01:00,780.5,19.8']
        serie = _lire('\r\n'.join(lignes))
        self.assertEqual(serie['points'][0]['gi_w_m2'], 780.5)

    def test_un_cartouche_de_provenance_avant_lentete_est_traverse(self):
        lignes = ['Provenance;Station d essai',
                  '',
                  'horodatage;gi_w_m2',
                  '2021-01-15T13:00:00+01:00;780.0']
        serie = _lire('\r\n'.join(lignes))
        self.assertEqual(len(serie['points']), 1)


class _Transport:
    """Transport INJECTÉ : rejoue une charge fabriquée, jamais le réseau."""

    def __init__(self, charge):
        self.charge = charge
        self.appels = []

    def __call__(self, url, timeout_s):
        self.appels.append(url)
        return 200, json.dumps(self.charge)


def _reponse_pvgis(moments):
    """La réponse ``seriescalc`` qui porte EXACTEMENT les mêmes valeurs.

    ``H_sun`` est volontairement ABSENT : un fichier ne porte pas la hauteur
    du soleil, et la comparaison doit se faire sur ce que les DEUX sources
    peuvent publier.
    """
    horaire = []
    for moment in moments:
        valeurs = _valeurs_essai(moment.hour)
        horaire.append({
            'time': '{0:04d}{1:02d}{2:02d}:{3:02d}10'.format(
                moment.year, moment.month, moment.day, moment.hour),
            'G(i)': valeurs['gi_w_m2'],
            'Gb(i)': valeurs['gb_i_w_m2'],
            'Gd(i)': valeurs['gd_i_w_m2'],
            'Gr(i)': valeurs['gr_i_w_m2'],
            'T2m': valeurs['t2m_c'],
            'WS10m': valeurs['ws10m'],
        })
    return {
        'inputs': {
            'location': {'latitude': 33.5, 'longitude': -7.6,
                         'elevation': 50.0},
            'meteo_data': {'radiation_db': 'PVGIS-SARAH3',
                           'meteo_db': 'ERA5', 'year_min': 2021,
                           'year_max': 2021, 'use_horizon': True,
                           'horizon_db': 'DEM-calculated'},
        },
        'outputs': {'hourly': horaire},
    }


class ProprieteMemeCascadeTest(SimpleTestCase):
    """8 760 lignes en POA = la MÊME cascade qu'une réponse PVGIS jumelle."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.moments = _instants(8760, decalage_minutes=0)
        cls.fichier = _lire(_csv(cls.moments))
        client = ClientPvgis(
            _Transport(_reponse_pvgis(cls.moments)),
            cache=_Cache(), dormir=lambda _s: None)
        cls.pvgis = client.serie_irradiance(
            lat=33.5, lon=-7.6, inclinaison_deg=15.0, aspect_deg=0.0,
            annee_debut=2021, annee_fin=2021, composantes=True,
            obtenue_le=OBTENUE_LE)

    def test_les_deux_sources_portent_le_meme_nombre_de_points(self):
        self.assertEqual(len(self.fichier['points']), 8760)
        self.assertEqual(len(self.pvgis['points']),
                         len(self.fichier['points']))

    def test_point_par_point_les_deux_series_sont_identiques(self):
        for rang, (du_fichier, de_pvgis) in enumerate(
                zip(self.fichier['points'], self.pvgis['points'])):
            self.assertEqual(sorted(du_fichier), sorted(de_pvgis), rang)
            for colonne in sorted(de_pvgis):
                self.assertEqual(du_fichier[colonne], de_pvgis[colonne],
                                 'point {0}, colonne {1}'.format(rang,
                                                                 colonne))

    def test_la_serie_persistee_est_la_meme_des_deux_cotes(self):
        gauche = self.fichier['serie_horaire']
        droite = self.pvgis['serie_horaire']
        self.assertEqual(gauche['colonnes'], droite['colonnes'])
        self.assertEqual(gauche['pas_minutes'], droite['pas_minutes'])
        self.assertEqual(gauche['tronquee'], droite['tronquee'])
        self.assertEqual(len(gauche['points']), len(droite['points']))

    def test_la_cascade_calculee_sur_lune_vaut_celle_de_lautre(self):
        from apps.calepinage.services.chaine_pertes import appliquer_chaine

        _serie_g, cascade_g = appliquer_chaine(self.fichier['serie_horaire'])
        _serie_d, cascade_d = appliquer_chaine(self.pvgis['serie_horaire'])
        self.assertEqual(cascade_g['total_pct'], cascade_d['total_pct'])
        self.assertEqual(cascade_g['ordre'], cascade_d['ordre'])
        self.assertEqual(
            [(etape['etape'], etape['kwh_avant'], etape['kwh_apres'])
             for etape in cascade_g['etapes']],
            [(etape['etape'], etape['kwh_avant'], etape['kwh_apres'])
             for etape in cascade_d['etapes']])


class SigmaNonMesurableTest(SimpleTestCase):
    """Une seule année de fichier ⇒ AUCUN σ mesuré, quel que soit le mode."""

    def test_un_fichier_dune_annee_ne_donne_aucun_sigma_mesure(self):
        serie = _lire(_csv(_instants(48)))
        self.assertEqual(serie['annees'], [2021])

        # Le total annuel d'ESSAI : une seule année, donc une seule valeur.
        sigma, origine, annees = variabilite_interannuelle({2021: 12345.0})
        self.assertIsNone(
            sigma, "Un écart-type sur une seule année n'existe pas : le mode "
                   'pluriannuel doit refuser σ plutôt que d\'en fabriquer un.')
        self.assertEqual(origine, 'absente')
        self.assertEqual(annees, 1)

    def test_deux_annees_dans_le_fichier_sont_bien_enumerees(self):
        depart = datetime.datetime(2021, 12, 31, 22, 0,
                                   tzinfo=datetime.timezone.utc)
        serie = _lire(_csv(_instants(6, depart=depart)))
        self.assertEqual(serie['annees'], [2021, 2022])


class RouteEnregistreeTest(SimpleTestCase):
    """La porte existe, et elle est gardée."""

    def test_laction_meteo_fichier_est_routee_en_post_multipart(self):
        from apps.calepinage import urls  # noqa: F401
        from apps.calepinage.views.calepinages import CalepinageViewSet

        actions = {methode.__name__: methode
                   for methode in CalepinageViewSet.get_extra_actions()}
        self.assertIn('meteo_fichier', actions)
        action = actions['meteo_fichier']
        self.assertEqual(action.url_path, 'meteo-fichier')
        self.assertEqual(set(action.mapping), {'post'})
        self.assertEqual(
            [garde.__name__ for garde in action.kwargs['permission_classes']],
            ['PeutGererCalepinage'])
        self.assertEqual(
            [parseur.__name__
             for parseur in action.kwargs['parser_classes']],
            ['MultiPartParser', 'FormParser'])


class ContratCommitteTest(SimpleTestCase):
    """L'échantillon committé décrit bien ce que le service rend."""

    def test_lendpoint_est_celui_de_la_porte(self):
        self.assertTrue(CONTRAT['endpoint'].startswith('POST '))
        self.assertTrue(
            CONTRAT['endpoint'].rstrip('/').endswith('meteo-fichier'))

    def test_le_bloc_meteo_de_lexemple_porte_les_memes_cles_que_le_service(self):
        attendu = _lire(_csv(_instants(3, decalage_minutes=60)))['meteo']
        self.assertEqual(sorted(CONTRAT['exemple']['meteo']), sorted(attendu))
        self.assertEqual(sorted(CONTRAT['exemple']['meteo']['fichier']),
                         sorted(attendu['fichier']))
        self.assertEqual(sorted(CONTRAT['exemple']['meteo']['heure']),
                         sorted(attendu['heure']))

    def test_le_resume_de_serie_de_lexemple_porte_les_memes_cles(self):
        exemple = CONTRAT['exemple']['serie']
        for cle in ('points', 'annees', 'pas_minutes', 'tronquee', 'colonnes',
                    'composantes_disponibles', 'motif_composantes'):
            self.assertIn(cle, exemple, cle)
        # Le nombre de points, jamais les points eux-mêmes.
        self.assertIsInstance(exemple['points'], int)

    def test_le_refus_horizontal_committe_est_celui_que_le_service_leve(self):
        lignes = ['horodatage;ghi_w_m2', '2021-01-15T13:00:00+01:00;780.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))
        self.assertEqual(CONTRAT['exemple_refus_horizontal']['ghi_w_m2'][0],
                         leve.exception.motif)

    def test_le_refus_sans_fuseau_committe_est_celui_que_le_service_leve(self):
        lignes = ['horodatage;gi_w_m2', '2021-01-15T13:00:00;780.0']
        with self.assertRaises(MeteoFichierRefuse) as leve:
            _lire('\r\n'.join(lignes))
        self.assertEqual(CONTRAT['exemple_refus_sans_fuseau']['horodatage'][0],
                         leve.exception.motif)
        self.assertEqual(CONTRAT['exemple_refus_sans_fuseau']['ligne'],
                         leve.exception.ligne)

    def test_le_refus_sans_fournisseur_committe_est_celui_de_la_vue(self):
        from apps.calepinage.views.meteo_fichier import SANS_FOURNISSEUR

        self.assertEqual(
            CONTRAT['exemple_refus_sans_fournisseur']['fournisseur'][0],
            SANS_FOURNISSEUR)

    def test_le_message_committe_est_celui_de_la_vue(self):
        from apps.calepinage.views.meteo_fichier import MESSAGE_DEPOSE

        self.assertEqual(CONTRAT['exemple']['message'], MESSAGE_DEPOSE)
