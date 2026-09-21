"""CALX70 — ``GET resultat/`` SERT la simulation, ou dit pourquoi il refuse.

L'incident que ce fichier ferme : une simulation écrite dans
``Calepinage.resultat`` et JAMAIS servie. ``services/electrique.py`` publiait
``production`` et ``pertes`` par littéral (``None`` / ``[]``) — l'écran
affichait donc « non simulé » alors que le calcul avait tourné.

Trois garanties, et elles comptent autant l'une que l'autre :

1. **fraîche, la simulation est SERVIE telle quelle** — ``production``,
   ``cascade`` et les dix autres blocs déclarés par CALX4
   (``contract_samples/calepinage_simulation.json``) ressortent à l'identique,
   et ``simule`` devient vrai parce que ``production.total.p50_kwh`` est un
   NOMBRE ;
2. **périmée, elle est REFUSÉE en le disant** — le document a changé depuis le
   calcul, donc chaque bloc vaut ``null``, ``simulation_perimee`` vaut vrai et
   le motif NOMME la péremption avec la date du calcul. Une production
   calculée sur un autre toit ne s'affiche jamais comme si elle décrivait
   celui-ci. SEULE EXCEPTION de type : ``pertes`` reste une LISTE (vide) —
   quatre lecteurs l'itèrent déjà comme telle (D-CALX 11) ;
3. **``enregistrer_entree`` n'efface AUCUN bloc de simulation** — les trois
   écritures persistantes du module fusionnent une clé dans le dictionnaire
   existant, et ce test l'exige (non-régression sur la fusion de clés).

Aucune base de données : le matériel est injecté (``materiel=``) et la
simulation est écrite À LA MAIN dans ``resultat`` (aucun service de simulation
n'existe encore — il arrive avec CALX5).

Run :
    python manage.py test \
        apps.calepinage.tests.test_calx70_resultat_sert_la_simulation -v2
"""
import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.electrique import (
    BLOCS_SIMULATION, CLE_SIMULATION, enregistrer_entree, resultat_calepinage,
)

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads(
    (ECHANTILLONS / 'calepinage_resultat.json').read_text(encoding='utf-8'))
SIMULATION = json.loads(
    (ECHANTILLONS / 'calepinage_simulation.json').read_text(encoding='utf-8'))

MODULE = {
    'vmp_v': 41.5, 'voc_v': 49.6, 'isc_a': 18.4, 'imp_a': 17.1,
    'pmax_wc': 710.0, 'temp_coeff_voc_pct_c': -0.27,
    'temp_coeff_pmax_pct_c': -0.35,
}
ONDULEUR = {
    'n_mppt': 2, 'mppt_v_min': 150.0, 'mppt_v_max': 800.0,
    'v_max_abs': 1000.0, 'i_max_mppt_a': 26.0, 'ac_kw': 10.0, 'phases': 3,
}
MATERIEL = {
    'module': MODULE, 'onduleur': ONDULEUR, 'optimiseur': None,
    'designations': {'module': 'Module d essai',
                     'onduleur': 'Onduleur d essai', 'optimiseur': ''},
    'absents': (),
}
LAYOUT = {
    'version': 2,
    'pin': {'lat': 33.5731, 'lng': -7.5898},
    'zones': [
        {'id': 'a', 'label': 'PAN-A',
         'geometry': {'count': 12, 'azimuthDeg': 180.0, 'tiltDeg': 15.0}},
        {'id': 'b', 'label': 'PAN-B',
         'geometry': {'count': 7, 'azimuthDeg': 90.0, 'tiltDeg': 15.0}},
    ],
}
#: LE MÊME toit, avec un module de plus sur le premier pan : l'empreinte des
#: entrées change, donc la simulation enregistrée ne décrit plus ce document.
LAYOUT_MODIFIE = copy.deepcopy(LAYOUT)
LAYOUT_MODIFIE['zones'][0]['geometry']['count'] = 13


class _Calepinage:
    """Le strict minimum que le service lit sur un pivot — aucun ORM."""

    def __init__(self, layout, resultat=None, pk=1):
        self.pk = pk
        self.roof_layout = layout
        self.resultat = resultat
        self.company = None
        self.enregistrements = []

    def save(self, update_fields=None):
        # Le service borne toujours son écriture ; on le CONSTATE ici plutôt
        # que de le supposer (règle #4 : aucun statut n'est touché).
        self.enregistrements.append(tuple(update_fields or ()))


def _document_simule(empreinte, *, calcule_le='2026-09-19T11:30:00Z'):
    """Le document qu'une simulation DÉPOSE dans ``Calepinage.resultat``.

    Les blocs viennent de l'échantillon committé par CALX4 : le test affirme
    LE CONTRAT, jamais des valeurs réinventées pour l'occasion.
    """
    depose = {CLE_SIMULATION: {
        'hash_entree': empreinte,
        'version_moteur': 'essai',
        'calcule_le': calcule_le,
        'duree_s': 12.4,
    }}
    for cle in BLOCS_SIMULATION:
        depose[cle] = copy.deepcopy(SIMULATION['exemple'][cle])
    # La série horaire est bien DANS le document (CALX4) : c'est justement ce
    # que ``GET resultat/`` ne recopie pas (D-CALX 14 — volume).
    depose['serie_horaire'] = copy.deepcopy(
        SIMULATION['exemple']['serie_horaire'])
    return depose


def _empreinte_du_document(layout):
    """L'empreinte que le serveur publie AUJOURD'HUI pour ce document."""
    return resultat_calepinage(_Calepinage(layout),
                               materiel=MATERIEL)['hash_entree']


class SimulationFraicheTest(SimpleTestCase):
    """Le calcul a tourné et le document n'a pas bougé : il est SERVI."""

    def setUp(self):
        self.empreinte = _empreinte_du_document(LAYOUT)
        self.calepinage = _Calepinage(
            LAYOUT, resultat=_document_simule(self.empreinte))
        self.resultat = resultat_calepinage(self.calepinage,
                                            materiel=MATERIEL)

    def test_la_production_annuelle_est_servie_et_non_nulle(self):
        attendu = SIMULATION['exemple']['production']['total']['p50_kwh']

        self.assertIsNotNone(self.resultat['production']['total']['p50_kwh'])
        self.assertEqual(self.resultat['production']['total']['p50_kwh'],
                         attendu)

    def test_la_cascade_de_pertes_est_servie_telle_quelle(self):
        self.assertEqual(self.resultat['cascade'],
                         SIMULATION['exemple']['cascade'])

    def test_les_douze_blocs_declares_par_calx4_sont_servis(self):
        for cle in BLOCS_SIMULATION:
            self.assertEqual(self.resultat[cle],
                             SIMULATION['exemple'][cle],
                             f'le bloc « {cle} » n est pas servi tel quel.')

    def test_la_serie_horaire_n_est_pas_recopiee(self):
        # D-CALX 14 : elle reste servie par ``export-csv`` et le panneau
        # Séries — la recopier ici ferait voyager des milliers de points à
        # chaque ouverture d'écran.
        self.assertNotIn('serie_horaire', self.resultat)

    def test_simule_est_vrai_et_la_date_du_calcul_est_publiee(self):
        self.assertTrue(self.resultat['simule'])
        self.assertEqual(self.resultat['calcule_le'], '2026-09-19T11:30:00Z')
        self.assertFalse(self.resultat['simulation_perimee'])
        self.assertEqual(self.resultat['motif'], '')

    def test_aucun_avertissement_de_non_simulation(self):
        for message in self.resultat['avertissements']:
            self.assertNotIn('Production non simulée', message)

    def test_la_reponse_est_detachee_du_document_stocke(self):
        # Remanier la réponse ne doit JAMAIS remanier la base.
        self.resultat['production']['total']['p50_kwh'] = 1.0

        self.assertEqual(
            self.calepinage.resultat['production']['total']['p50_kwh'],
            SIMULATION['exemple']['production']['total']['p50_kwh'])

    def test_aucun_prix_dans_le_resultat_servi(self):
        rendu = json.dumps(self.resultat, ensure_ascii=False)

        for interdit in ('prix_achat', 'prix_vente', 'marge'):
            self.assertNotIn(interdit, rendu)


class SimulationPerimeeTest(SimpleTestCase):
    """Le document a changé depuis le calcul : les blocs sont REFUSÉS."""

    def setUp(self):
        # La simulation a été calculée sur LAYOUT ; le document d'aujourd'hui
        # porte un module de plus.
        self.calepinage = _Calepinage(
            LAYOUT_MODIFIE,
            resultat=_document_simule(_empreinte_du_document(LAYOUT)))
        self.resultat = resultat_calepinage(self.calepinage,
                                            materiel=MATERIEL)

    def test_chaque_bloc_vaut_null_sauf_la_liste_de_pertes(self):
        for cle in BLOCS_SIMULATION:
            if cle == 'pertes':
                continue
            self.assertIsNone(self.resultat[cle],
                              f'le bloc « {cle} » devrait être null.')

    def test_les_pertes_restent_une_liste_plate_vide(self):
        # D-CALX 11 : quatre lecteurs itèrent ``pertes`` — son TYPE ne change
        # pas avec sa fraîcheur (``note_calcul``, ``comparaison``,
        # ``export_csv``, ``DiagrammePertes``).
        self.assertIsInstance(self.resultat['pertes'], list)
        self.assertEqual(self.resultat['pertes'], [])

    def test_le_drapeau_et_le_motif_nomment_la_peremption(self):
        self.assertTrue(self.resultat['simulation_perimee'])
        self.assertEqual(
            self.resultat['motif'],
            'simulation périmée : le document a changé depuis le calcul '
            'du 19/09/2026')

    def test_le_motif_ouvre_les_avertissements(self):
        self.assertEqual(self.resultat['avertissements'][0],
                         self.resultat['motif'])

    def test_le_resultat_n_est_pas_declare_simule(self):
        self.assertFalse(self.resultat['simule'])
        self.assertIsNone(self.resultat['calcule_le'])

    def test_sans_date_enregistree_aucune_date_n_est_inventee(self):
        depose = _document_simule(_empreinte_du_document(LAYOUT),
                                  calcule_le=None)

        resultat = resultat_calepinage(
            _Calepinage(LAYOUT_MODIFIE, resultat=depose), materiel=MATERIEL)

        self.assertTrue(resultat['simulation_perimee'])
        self.assertEqual(
            resultat['motif'],
            'simulation périmée : le document a changé depuis le calcul '
            "précédent, dont la date n'a pas été enregistrée")


class AucuneSimulationTest(SimpleTestCase):
    """Rien n'a jamais été calculé : le comportement d'hier est intact."""

    def setUp(self):
        self.resultat = resultat_calepinage(_Calepinage(LAYOUT),
                                            materiel=MATERIEL)

    def test_la_pose_reste_chiffree_et_la_production_nulle(self):
        # La POSE est un fait : kWc et modules restent des nombres. La
        # production, elle, n'a pas été lancée — jamais un 0.
        self.assertEqual(self.resultat['pose']['total_modules'], 19)
        self.assertIsNotNone(self.resultat['production']['total']['kwc'])
        self.assertIsNone(self.resultat['production']['total']['p50_kwh'])
        self.assertEqual(self.resultat['production']['mensuel'], [])
        self.assertEqual(self.resultat['pertes'], [])

    def test_les_blocs_neufs_sont_presents_et_nuls(self):
        for cle in BLOCS_SIMULATION:
            self.assertIn(cle, self.resultat)
            if cle in ('production', 'pertes'):
                continue
            self.assertIsNone(self.resultat[cle])

    def test_rien_n_est_declare_perime(self):
        self.assertFalse(self.resultat['simule'])
        self.assertFalse(self.resultat['simulation_perimee'])
        self.assertEqual(self.resultat['motif'], '')
        self.assertIsNone(self.resultat['calcule_le'])
        self.assertTrue(any('Production non simulée' in message
                            for message in self.resultat['avertissements']))

    def test_une_simulation_sans_empreinte_ne_compte_pas(self):
        # Un en-tête de simulation sans ``hash_entree`` ne prouve RIEN : on ne
        # peut pas dire si le document a bougé, donc on ne sert pas ses blocs.
        depose = _document_simule('')

        resultat = resultat_calepinage(
            _Calepinage(LAYOUT, resultat=depose), materiel=MATERIEL)

        self.assertFalse(resultat['simule'])
        self.assertFalse(resultat['simulation_perimee'])
        self.assertIsNone(resultat['production']['total']['p50_kwh'])


class EnregistrerEntreeNEffaceRienTest(SimpleTestCase):
    """Non-régression : la fusion de clés préserve la simulation."""

    def test_aucun_bloc_de_simulation_n_est_efface(self):
        empreinte = _empreinte_du_document(LAYOUT)
        calepinage = _Calepinage(LAYOUT, resultat=_document_simule(empreinte))
        avant = copy.deepcopy(calepinage.resultat)

        enregistrer_entree(calepinage, {'dc_m': 42.0})

        for cle in list(BLOCS_SIMULATION) + [CLE_SIMULATION, 'serie_horaire']:
            self.assertEqual(calepinage.resultat[cle], avant[cle],
                             f'« {cle} » a été effacé par enregistrer_entree.')
        self.assertEqual(calepinage.resultat['entree_electrique']['dc_m'],
                         42.0)
        self.assertEqual(calepinage.enregistrements,
                         [('resultat', 'updated_at')])

    def test_la_simulation_reste_servie_apres_une_saisie_neutre(self):
        # ``cheminement`` DÉCRIT le passage des câbles : il n'entre pas dans
        # l'empreinte (``_options_entree``), donc il ne périme rien.
        empreinte = _empreinte_du_document(LAYOUT)
        calepinage = _Calepinage(LAYOUT, resultat=_document_simule(empreinte))

        enregistrer_entree(calepinage, {'cheminement': 'chemin de câbles'})
        resultat = resultat_calepinage(calepinage, materiel=MATERIEL)

        self.assertTrue(resultat['simule'])
        self.assertFalse(resultat['simulation_perimee'])
        self.assertEqual(resultat['production'],
                         SIMULATION['exemple']['production'])

    def test_une_saisie_qui_entre_dans_l_empreinte_perime_la_simulation(self):
        # ``dc_m``, elle, EST une entrée du calcul (``_options_entree``) :
        # allonger la liaison change les pertes, donc la simulation d'avant ne
        # décrit plus ce dossier. Les blocs sont CONSERVÉS en base — seule
        # leur publication est refusée, avec son motif.
        empreinte = _empreinte_du_document(LAYOUT)
        calepinage = _Calepinage(LAYOUT, resultat=_document_simule(empreinte))

        enregistrer_entree(calepinage, {'dc_m': 42.0})
        resultat = resultat_calepinage(calepinage, materiel=MATERIEL)

        self.assertTrue(resultat['simulation_perimee'])
        self.assertIsNone(resultat['production'])
        self.assertEqual(calepinage.resultat['production'],
                         SIMULATION['exemple']['production'])


class ContratPartageTest(SimpleTestCase):
    """L'échantillon committé décrit bien ce que le serveur sert.

    Le contrôle est à SENS UNIQUE (« toute clé promise est servie ») : ce
    `resultat` sert DÉJÀ des clés que l'échantillon n'énumère pas (les blocs
    électriques CAL127-134), un écart antérieur à CALX70 que cette tâche ne
    referme pas.
    """

    def _servi(self, calepinage):
        return set(resultat_calepinage(calepinage, materiel=MATERIEL))

    def test_les_cles_promises_par_chaque_etat_sont_servies(self):
        etats = {
            'exemple': _Calepinage(
                LAYOUT, resultat=_document_simule(
                    _empreinte_du_document(LAYOUT))),
            'exemple_perime': _Calepinage(
                LAYOUT_MODIFIE, resultat=_document_simule(
                    _empreinte_du_document(LAYOUT))),
            'exemple_vide': _Calepinage(LAYOUT),
        }
        for etat, calepinage in etats.items():
            manquantes = sorted(set(CONTRAT[etat]) - self._servi(calepinage))
            self.assertEqual(
                manquantes, [],
                f'{etat} : le serveur ne sert PAS la ou les clés '
                f'{manquantes} que l échantillon promet.')

    def test_l_echantillon_declare_les_douze_blocs_et_leurs_drapeaux(self):
        for etat in ('exemple', 'exemple_perime', 'exemple_vide'):
            for cle in list(BLOCS_SIMULATION) + ['simulation_perimee',
                                                 'motif']:
                self.assertIn(cle, CONTRAT[etat],
                              f'{etat} : « {cle} » absent de l échantillon.')

    def test_l_etat_perime_de_l_echantillon_est_coherent(self):
        perime = CONTRAT['exemple_perime']

        self.assertTrue(perime['simulation_perimee'])
        self.assertFalse(perime['simule'])
        self.assertIsNone(perime['production'])
        self.assertEqual(perime['pertes'], [])
        self.assertIn('simulation périmée', perime['motif'])

    def test_l_echantillon_ne_promet_pas_la_serie_horaire(self):
        for etat in ('exemple', 'exemple_perime', 'exemple_vide'):
            self.assertNotIn('serie_horaire', CONTRAT[etat])
