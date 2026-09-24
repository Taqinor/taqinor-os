"""CALX312 — l'export JSON versionné du projet et de ses résultats.

Ce qui est prouvé ici :

* le document servi a EXACTEMENT la forme de l'exemple committé
  ``contract_samples/export_projet.json`` (toutes ses clés, blocs imbriqués), sur
  ``exemple`` (calepinage simulé) ET sur ``exemple_vide`` (jamais posé) —
  l'exemple est AFFIRMÉ, pas recopié ;
* ``format_version`` est l'ENTIER 2 (CALX370 : ``postes_pertes`` et
  ``variantes`` rejoignent le fichier) ; ``produit_le`` l'instant de
  production, en UTC ;
* un calepinage NON SIMULÉ exporte ``resultat: null`` (jamais ``{}``),
  ``pertes: []`` et les grandeurs de simulation à ``null`` AVEC leur motif en
  tête des avertissements — aucune clé absente ;
* aucune clé ni valeur du document ne contient un mot de
  ``note_calcul.CLES_INTERDITES`` ; une clé de coût injectée fait REFUSER
  l'export en la nommant ; les jeux géométriques du moteur passent ;
* l'empreinte publiée dans l'export (``hash_entree``, ``version_moteur``)
  égale celle du résultat servi ;
* le fichier se relit en JSON STRICT ; une valeur non finie est refusée,
  chemin nommé ;
* en base (CI) : ``GET …/export-projet.json/`` sert le téléchargement nommé,
  borné société (404) et permission (403).

Run :
    python manage.py test apps.calepinage.tests.test_calx312_export_projet -v2
"""
import copy
import datetime
import json
import pathlib
import re
import unittest
from types import SimpleNamespace
from unittest import mock

from apps.calepinage.models import Calepinage
from apps.calepinage.services.export_projet import (
    CLES_DOCUMENT, FORMAT_VERSION, MOTIF_NON_SIMULE, MOTIF_SANS_CONCEPTION,
    ExportProjetRefuse, document_de_projet, octets_de_projet,
)
from apps.calepinage.services.note_calcul import CLES_INTERDITES

from .test_api_liste import BaseApiCalepinage, url_detail

ECHANTILLONS = pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CONTRAT = charger('export_projet.json')
RESULTAT = charger('calepinage_resultat.json')
EQUIPEMENTS = charger('calepinage_equipements.json')
MOMENT = datetime.datetime(2026, 9, 23, 11, 30, tzinfo=datetime.timezone.utc)

#: Le repère servi par ``selectors.contexte_geographique`` (ses cinq clés).
SITE = {'adresse': "12 rue d'essai", 'ville': 'Casablanca',
        'pin': {'lat': 33.5731, 'lng': -7.5898}, 'outline': None,
        'source': 'lead_roof_point'}
SITE_VIDE = {'adresse': None, 'ville': None, 'pin': None, 'outline': None,
             'source': None}


def calepinage(**champs):
    """Un calepinage NON ENREGISTRÉ, sans société : aucune lecture en base."""
    valeurs = dict(pk=1, company=None, client_id=None, lead_id=None,
                   devis_id=None, titre='Toiture atelier — Bouskoura',
                   roof_layout=copy.deepcopy(CONTRAT['exemple']['roof_layout']),
                   layout_hash='ab' * 32, version_moteur='calepinage-1.0.0',
                   resultat=None)
    valeurs.update(champs)
    return SimpleNamespace(**valeurs)


def resultat(cle='exemple'):
    return copy.deepcopy(RESULTAT[cle])


def exporte(objet=None, **options):
    options.setdefault('moment', MOMENT)
    options.setdefault('resultat', resultat())
    options.setdefault('site', SITE)
    options.setdefault('equipements', copy.deepcopy(EQUIPEMENTS['exemple']))
    return document_de_projet(objet or calepinage(), **options)


def vide():
    return document_de_projet(
        calepinage(pk=2, titre='', roof_layout=None, layout_hash='',
                   version_moteur=''),
        moment=MOMENT, site=SITE_VIDE,
        equipements=copy.deepcopy(EQUIPEMENTS['exemple_vide']))


class FormeDuContratTest(unittest.TestCase):
    """L'exemple committé est AFFIRMÉ contre le document réellement servi."""

    def comparer(self, attendu, obtenu, chemin='<racine>'):
        self.assertEqual(sorted(attendu), sorted(obtenu),
                         'clés divergentes en %s' % chemin)

    def test_les_cles_du_contrat_simule(self):
        document = exporte()
        exemple = CONTRAT['exemple']
        self.comparer(exemple, document)
        self.assertEqual(tuple(document), CLES_DOCUMENT)
        for bloc in ('calepinage', 'site', 'equipements'):
            self.comparer(exemple[bloc], document[bloc], bloc)
        for famille in ('panneau', 'onduleur'):
            self.assertLessEqual(set(exemple['equipements'][famille]),
                                 set(document['equipements'][famille]))
        self.assertLessEqual(set(exemple['resultat']),
                             set(document['resultat']))
        for poste in document['pertes']:
            self.comparer(exemple['pertes'][0], poste, 'pertes[]')

    def test_l_exemple_vide_est_rendu_a_l_identique(self):
        document = vide()
        exemple = copy.deepcopy(CONTRAT['exemple_vide'])
        self.assertEqual(document.pop('produit_le'), '2026-09-23T11:30:00Z')
        exemple.pop('produit_le')
        self.assertEqual(document, exemple)

    def test_format_version_est_l_entier_2(self):
        for document in (exporte(), vide()):
            self.assertEqual(document['format_version'], 2)
            self.assertIs(type(document['format_version']), int)
        self.assertEqual(FORMAT_VERSION, CONTRAT['exemple']['format_version'])

    def test_produit_le_est_l_instant_de_production_en_utc(self):
        self.assertEqual(exporte()['produit_le'], '2026-09-23T11:30:00Z')
        casablanca = datetime.timezone(datetime.timedelta(hours=1))
        self.assertEqual(
            exporte(moment=MOMENT.astimezone(casablanca))['produit_le'],
            '2026-09-23T11:30:00Z')

    def test_les_blocs_sont_lus_tels_quels(self):
        document = exporte()
        servi = resultat()
        self.assertEqual(document['resultat'], servi)
        self.assertEqual(document['pertes'], servi['pertes'])
        self.assertEqual(document['site']['altitude_m'],
                         servi['meteo']['point']['altitude_m'])
        self.assertEqual(document['site']['fuseau'],
                         servi['meteo']['heure']['fuseau_site'])
        self.assertEqual(document['site']['source_repere'], 'lead_roof_point')
        self.assertEqual(document['equipements']['panneau'],
                         EQUIPEMENTS['exemple']['panneau'])
        self.assertEqual(document['roof_layout'],
                         CONTRAT['exemple']['roof_layout'])
        self.assertEqual(document['layout_hash'], 'ab' * 32)
        self.assertEqual(document['version_moteur'], 'calepinage-1.0.0')
        self.assertEqual(document['avertissements'],
                         servi['avertissements'])


class NonSimuleTest(unittest.TestCase):
    def test_un_calepinage_non_simule_exporte_resultat_null(self):
        servi = resultat('exemple_vide')
        document = exporte(resultat=servi)
        self.assertEqual(tuple(document), CLES_DOCUMENT)
        self.assertIn('resultat', document)
        self.assertIsNone(document['resultat'])
        self.assertEqual(document['pertes'], [])
        self.assertIn('altitude_m', document['site'])
        self.assertIsNone(document['site']['altitude_m'])
        self.assertIsNone(document['site']['fuseau'])
        self.assertEqual(document['avertissements'][0], MOTIF_NON_SIMULE)
        self.assertEqual(document['avertissements'][1:],
                         servi['avertissements'])

    def test_une_simulation_perimee_n_est_pas_exportee(self):
        servi = resultat('exemple_perime')
        document = exporte(resultat=servi)
        self.assertIsNone(document['resultat'])
        self.assertEqual(document['avertissements'][0], MOTIF_NON_SIMULE)
        self.assertIn(servi['motif'], document['avertissements'])

    def test_aucun_resultat_servi(self):
        document = exporte(resultat=None)
        self.assertIsNone(document['resultat'])
        self.assertEqual(document['avertissements'], [MOTIF_NON_SIMULE])

    def test_jamais_pose_ne_calcule_rien(self):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage'
        ) as calcul:
            document = vide()
        calcul.assert_not_called()
        self.assertEqual(document['avertissements'], [MOTIF_SANS_CONCEPTION])
        self.assertEqual(MOTIF_SANS_CONCEPTION,
                         CONTRAT['exemple_vide']['avertissements'][0])


def _cles_et_textes(noeud):
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            yield str(cle)
            yield from _cles_et_textes(valeur)
    elif isinstance(noeud, (list, tuple)):
        for valeur in noeud:
            yield from _cles_et_textes(valeur)
    elif isinstance(noeud, str):
        yield noeud


class AucunMontantTest(unittest.TestCase):
    def test_aucune_cle_ni_valeur_ne_porte_un_mot_interdit(self):
        motif = re.compile(r'(?<![a-z])(%s)(?![a-z])'
                           % '|'.join(CLES_INTERDITES), re.IGNORECASE)
        for document in (exporte(), vide(),
                         exporte(resultat=resultat('exemple_vide'))):
            for texte in _cles_et_textes(document):
                self.assertIsNone(motif.search(texte.replace(' ', '_')),
                                  texte)

    def test_une_cle_de_cout_injectee_est_refusee_en_la_nommant(self):
        servi = resultat()
        servi['pose']['prix_achat_total'] = 1
        with self.assertRaises(ExportProjetRefuse) as capture:
            exporte(resultat=servi)
        self.assertIn('prix_achat_total', capture.exception.champ)
        self.assertIn('resultat.pose.prix_achat_total', str(capture.exception))

    def test_la_famille_du_contrat_est_refusee(self):
        for cle in ('cout_unitaire', 'marge_pct', 'prix'):
            equipements = copy.deepcopy(EQUIPEMENTS['exemple'])
            equipements['panneau']['specs'][cle] = 1
            with self.subTest(cle=cle):
                with self.assertRaises(ExportProjetRefuse) as capture:
                    exporte(equipements=equipements)
                self.assertTrue(capture.exception.champ.endswith(cle))

    def test_les_jeux_geometriques_du_moteur_passent(self):
        servi = resultat()
        servi['marges'] = {'troncon_min_cm': 12}
        servi['marge_troncon_min'] = 12
        exporte(resultat=servi)  # ne lève pas


class EmpreinteTest(unittest.TestCase):
    def test_l_empreinte_publiee_egale_celle_du_resultat(self):
        servi = resultat()
        document = exporte(resultat=servi)
        self.assertEqual(document['resultat']['hash_entree'],
                         servi['hash_entree'])
        self.assertEqual(document['resultat']['version_moteur'],
                         servi['version_moteur'])


def _refuser_constante(nom):
    raise ValueError('constante JSON non stricte : %s' % nom)


class JsonStrictTest(unittest.TestCase):
    def test_le_fichier_se_relit_en_json_strict(self):
        for document in (exporte(), vide()):
            relu = json.loads(octets_de_projet(document).decode('utf-8'),
                              parse_constant=_refuser_constante)
            self.assertEqual(relu, document)

    def test_une_valeur_non_finie_est_refusee_en_nommant_son_chemin(self):
        servi = resultat()
        servi['production']['total']['p50_kwh'] = float('nan')
        with self.assertRaises(ExportProjetRefuse) as capture:
            exporte(resultat=servi)
        self.assertEqual(capture.exception.champ,
                         'resultat.production.total.p50_kwh')


class EndpointExportProjetEnBaseTest(BaseApiCalepinage):
    """``GET …/export-projet.json/`` — câblage, société, permission (CI)."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=CONTRAT['exemple']['roof_layout'],
            layout_hash='a' * 64)
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Chez la voisine',
            roof_layout=CONTRAT['exemple']['roof_layout'])

    def _get(self, objet, *, api=None, servi=None):
        with mock.patch(
                'apps.calepinage.services.electrique.resultat_calepinage',
                return_value=resultat() if servi is None else servi):
            return (api or self.api).get(
                '%sexport-projet.json/' % url_detail(objet.pk))

    def test_le_json_se_telecharge_nomme_et_strict(self):
        reponse = self._get(self.calepinage)
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse['Content-Type'].startswith('application/json'))
        self.assertTrue(reponse['Content-Disposition'].startswith(
            'attachment; filename="calepinage-'))
        self.assertTrue(reponse['Content-Disposition'].endswith(
            'export-projet.json"'))
        document = json.loads(reponse.content.decode('utf-8'),
                              parse_constant=_refuser_constante)
        self.assertEqual(tuple(document), CLES_DOCUMENT)
        self.assertEqual(document['format_version'], FORMAT_VERSION)
        self.assertEqual(document['calepinage']['id'], self.calepinage.pk)
        self.assertEqual(document['resultat']['hash_entree'],
                         resultat()['hash_entree'])

    def test_non_simule_resultat_null(self):
        reponse = self._get(self.calepinage, servi=resultat('exemple_vide'))
        self.assertEqual(reponse.status_code, 200)
        self.assertIsNone(reponse.data['resultat'])
        self.assertEqual(reponse.data['pertes'], [])

    def test_une_cle_de_cout_400_en_la_nommant(self):
        servi = resultat()
        servi['pose']['prix_achat_total'] = 1
        reponse = self._get(self.calepinage, servi=servi)
        self.assertEqual(reponse.status_code, 400)
        self.assertTrue(any('prix_achat' in cle for cle in reponse.data))

    def test_une_autre_societe_est_introuvable(self):
        self.assertEqual(self._get(self.etranger).status_code, 404)

    def test_sans_permission_de_lecture_c_est_403(self):
        self.assertEqual(
            self._get(self.calepinage, api=self.api_sans).status_code, 403)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
