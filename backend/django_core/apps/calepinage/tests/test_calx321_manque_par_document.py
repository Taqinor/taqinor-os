"""CALX321 — nommer, donnée par donnée, ce qui manque à chaque document.

Ce qui est prouvé ici, sur le contrat POSÉ SEUL (PACT10, CALX291)
``contract_samples/calepinage_documents.json`` :

* un calepinage VIDE (aucune conception) sert EXACTEMENT l'``exemple_vide``
  committé — les neuf codes, chacun ``disponible: false`` avec le motif ET
  le ``manque`` MOT POUR MOT de l'exemple ;
* chaque ``champ`` publié dans un ``manque`` est celui RÉELLEMENT levé par
  le service concerné — jamais un texte inventé pour l'occasion (le test
  déclenche un vrai refus, via une clé de coût interdite, et compare) ;
* les pièces dont la disponibilité dépend d'une donnée SPÉCIFIQUE
  (``rapport_ombrage`` : accès solaire ; ``plan_cablage`` : chaînage
  électrique + cheminements) sont départagées CORRECTEMENT quand la base
  (conception + résultat) est acquise mais que cette donnée précise manque
  encore ;
* l'ancien endpoint ``sorties/`` (CAL175) n'a pas bougé ;
* en base (CI) : ``GET …/documents/`` sert l'inventaire, borné société,
  et son échantillon « plein » reprend la forme de l'exemple committé.

UN CHOIX FONDATEUR DE PORTÉE, EXPLICITEMENT NOTÉ ICI
-----------------------------------------------------
Le texte de la tâche CALX321 (``docs/PLAN2.md``) mentionne une entrée
``schema_unifilaire_dxf`` distincte. Le contrat déjà COMMITTÉ par CALX291
(``calepinage_documents.json``) — posé SEUL et EN PREMIER, PACT10 — ne
déclare QUE neuf codes, et la tâche frontend qui le consomme (CALX320)
affirme littéralement « 9 documents servis ⇒ 9 lignes ». Le besoin réel
derrière ``schema_unifilaire_dxf`` (le schéma unifilaire chaîné, CALX235)
est COUVERT ici par ``plan_cablage`` (``manque`` nommant
``electrique.chainage``, RÉELLEMENT levé sur le résultat) — jamais par un
dixième code qui romprait le contrat déjà partagé avec la lane frontend.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx321_manque_par_document.py -q
"""
from __future__ import annotations

import copy
import json
import pathlib
import unittest
from unittest import mock

from apps.calepinage.services.documents import inventaire_des_documents
from apps.calepinage.views.sorties import inventaire_des_sorties

from .test_cal171_planche import LAYOUT

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_documents.json')
    .read_text(encoding='utf-8'))

CODES_NEUF = tuple(d['code'] for d in CONTRAT['exemple']['documents'])


class FauxVide:
    """Un calepinage NU : aucune conception, aucun résultat, aucune base."""

    pk = 2
    devis_id = None
    roof_layout = None
    resultat = None
    company = None
    layout_hash = ''
    version_moteur = ''
    titre = 'Calepinage 2'

    def __str__(self):
        return self.titre


class FauxConceptionSansResultat:
    """Conception enregistrée, AUCUN résultat calculé (état intermédiaire)."""

    pk = 4
    devis_id = None
    roof_layout = {'zones': []}
    resultat = None
    company = None
    layout_hash = 'c' * 64
    version_moteur = 'calepinage-1.0.0'
    titre = 'Calepinage 4'

    def __str__(self):
        return self.titre


class FauxResultatCoute:
    """Conception + résultat PRÉSENTS, mais le résultat porte une clé de
    coût interdite — déclenche un vrai refus ``RapportRefuse`` PUR (aucune
    base, ``verifier_etancheite`` lève avant tout accès DB)."""

    pk = 3
    devis_id = None
    roof_layout = {'zones': [{'id': 1}]}
    resultat = {'prix_achat': 100}
    company = None
    layout_hash = 'b' * 64
    version_moteur = 'calepinage-1.0.0'
    titre = 'Calepinage 3'

    def __str__(self):
        return self.titre


class FauxCablageTrace:
    """Chaînage électrique ET cheminement mesuré PRÉSENTS — ``resultat
    ['troncons']`` est un DICT (contrat ``calepinage_resultat.json``),
    JAMAIS une liste : régression du bug où la grammaire ``[]`` le lisait
    comme toujours absent."""

    pk = 6
    devis_id = None
    roof_layout = {'zones': [{'id': 1}]}
    resultat = {
        'electrique': {'chainage': {'modules': 12, 'chaines': 2}},
        'troncons': {'troncons': [{'id': 't1'}], 'totaux': {},
                     'omissions': [], 'verdicts': []},
    }
    company = None
    layout_hash = 'd' * 64
    version_moteur = 'calepinage-1.0.0'
    titre = 'Calepinage 6'

    def __str__(self):
        return self.titre


class InventaireVideTest(unittest.TestCase):
    """Un calepinage nu sert EXACTEMENT ``exemple_vide`` (essai PUR)."""

    def test_neuf_codes_dans_l_ordre_du_contrat(self):
        servi = inventaire_des_documents(FauxVide())
        self.assertEqual([d['code'] for d in servi['documents']],
                         list(CODES_NEUF))

    def test_correspond_mot_pour_mot_a_l_exemple_vide_committe(self):
        servi = inventaire_des_documents(FauxVide())
        attendu = CONTRAT['exemple_vide']
        self.assertEqual(servi['calepinage'], attendu['calepinage'])
        self.assertEqual(servi['layout_hash'], attendu['layout_hash'])
        self.assertEqual(servi['version_moteur'], attendu['version_moteur'])
        self.assertEqual(servi['langue'], attendu['langue'])
        self.assertEqual(servi['images'], attendu['images'])
        self.assertEqual(len(servi['documents']), len(attendu['documents']))
        for servie, attendue in zip(servi['documents'], attendu['documents']):
            self.assertEqual(servie['code'], attendue['code'])
            self.assertEqual(servie['libelle'], attendue['libelle'])
            self.assertEqual(servie['format'], attendue['format'])
            self.assertEqual(servie['endpoint'], attendue['endpoint'])
            self.assertEqual(servie['produit_par'], attendue['produit_par'])
            self.assertEqual(servie['disponible'], attendue['disponible'])
            self.assertEqual(servie['motif_indisponible'],
                             attendue['motif_indisponible'])
            self.assertEqual(servie['manque'], attendue['manque'])
            self.assertEqual(servie['versions'], attendue['versions'])

    def test_champ_roof_layout_en_premier_jamais_resultat(self):
        """Sans AUCUNE conception, c'est ``roof_layout`` qui est nommé —
        jamais ``resultat`` (il n'y a même pas de conception à calculer)."""
        servi = inventaire_des_documents(FauxVide())
        for document in servi['documents']:
            self.assertEqual(document['manque'][0]['champ'], 'roof_layout')


class InventaireEtatIntermediaireTest(unittest.TestCase):
    """Conception seule, sans résultat : le champ nommé devient ``resultat``
    (essai PUR — ``company=None`` évite tout accès DB de résolution de
    langue)."""

    def test_champ_resultat_quand_la_conception_existe_seule(self):
        servi = inventaire_des_documents(FauxConceptionSansResultat())
        for document in servi['documents']:
            self.assertFalse(document['disponible'])
            self.assertEqual(document['manque'][0]['champ'], 'resultat')

    def test_langue_et_empreintes_publiees_meme_sans_resultat(self):
        """``layout_hash``/``version_moteur``/``langue`` ne dépendent QUE de
        la conception — jamais du résultat (même discipline du null que
        ``sorties/``)."""
        servi = inventaire_des_documents(FauxConceptionSansResultat())
        self.assertEqual(servi['layout_hash'], 'c' * 64)
        self.assertEqual(servi['version_moteur'], 'calepinage-1.0.0')
        self.assertEqual(servi['langue'], 'fr')


class ChampReellementLeveTest(unittest.TestCase):
    """Chaque ``champ`` publié correspond au champ RÉELLEMENT levé par le
    service — jamais un texte inventé (essai PUR, ``verifier_etancheite``
    lève avant tout accès base).

    Trois des neuf codes sortent ``disponible`` sur ce fixture : leur
    ``versions[]`` (CALX322) lit alors ``records.Attachment`` en BASE — hors
    du périmètre de CET essai (qui porte sur ``manque``, pas sur les
    versions). ``_versions_pour`` est donc doublé par ``[]``, sans quoi cet
    essai PUR échouerait au premier accès base."""

    def setUp(self):
        patcheur = mock.patch(
            'apps.calepinage.services.documents._versions_pour',
            return_value=[])
        patcheur.start()
        self.addCleanup(patcheur.stop)
        self.servi = inventaire_des_documents(FauxResultatCoute())
        self.par_code = {d['code']: d for d in self.servi['documents']}

    def test_rapport_etude_nomme_la_cle_de_cout_reellement_levee(self):
        document = self.par_code['rapport_etude']
        self.assertFalse(document['disponible'])
        self.assertEqual(document['manque'][0]['champ'], 'resultat.prix_achat')
        self.assertIn('prix_achat', document['motif_indisponible'])

    def test_rapport_ombrage_nomme_l_acces_solaire_manquant(self):
        document = self.par_code['rapport_ombrage']
        self.assertFalse(document['disponible'])
        self.assertEqual(
            document['manque'][0]['champ'],
            'roof_layout.zones[].geometry.solarAccess.values')

    def test_plan_cablage_nomme_chainage_et_troncons(self):
        document = self.par_code['plan_cablage']
        self.assertFalse(document['disponible'])
        champs = {ligne['champ'] for ligne in document['manque']}
        self.assertEqual(champs, {'electrique.chainage', 'troncons'})

    def test_plan_cablage_disponible_quand_troncons_est_un_dict_trace(self):
        """RÉGRESSION : ``resultat['troncons']`` est un DICT non vide quand
        un cheminement est tracé (jamais une liste) — la grammaire de
        présence ne doit PAS exiger ``[]``."""
        with mock.patch(
                'apps.calepinage.services.documents._versions_pour',
                return_value=[]):
            servi = inventaire_des_documents(FauxCablageTrace())
        document = next(d for d in servi['documents']
                        if d['code'] == 'plan_cablage')
        self.assertTrue(document['disponible'])
        self.assertEqual(document['manque'], [])

    def test_les_pieces_sans_service_dedie_restent_disponibles(self):
        """La BASE (conception+résultat) suffit pour ``export_projet_json``,
        ``manuel_proprietaire`` et ``presentation_compacte`` : aucune donnée
        supplémentaire n'est encore exigée pour elles."""
        for code in ('export_projet_json', 'manuel_proprietaire',
                     'presentation_compacte'):
            self.assertTrue(self.par_code[code]['disponible'], code)
            self.assertEqual(self.par_code[code]['manque'], [])

    def test_les_pieces_a_preuve_terrain_restent_indisponibles(self):
        """Aucune preuve terrain ne peut exister : la porte de dépôt
        d'image (CALX302) n'est pas encore posée dans ce dépôt."""
        for code in ('document_asbuilt', 'dossier_fin_chantier',
                     'diagramme_pertes'):
            self.assertFalse(self.par_code[code]['disponible'], code)
            self.assertEqual(self.par_code[code]['manque'][0]['champ'],
                             'images')


class SortiesInchangeTest(unittest.TestCase):
    """``sorties/`` (CAL175) continue de servir sa forme d'ORIGINE — cette
    tâche ne l'a pas touché."""

    def test_inventaire_des_sorties_sert_toujours_ses_douze_codes(self):
        class FauxSortie:
            pk = 9
            roof_layout = None
            resultat = None
            layout_hash = ''
            version_moteur = ''
            company = None
            titre = 'Sortie'
            roof_image = None

            def __str__(self):
                return self.titre

        servi = inventaire_des_sorties(FauxSortie())
        self.assertEqual(
            [s['code'] for s in servi['sorties']],
            ['planche_pdf', 'planche_svg', 'planche_png', 'plan_pose_pdf',
             'plan_toiture_pdf', 'plan_masse_pdf', 'note_calcul_pdf', 'dxf',
             'tableur_xlsx', 'tableur_csv', 'image_3d', 'pack_technique'])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()


# ═══════════════════════════════════════════════════════════════════════
# EN BASE (CI) — câblage réel, société, permission
# ═══════════════════════════════════════════════════════════════════════
#
# Écrit ici mais NON EXÉCUTÉ localement (pas de Postgres sur ce poste de
# lane) : la CI valide. Utilise le même patron que
# ``test_calx308_diagramme_pertes_svg.py::EndpointDiagrammeEnBaseTest``.

from apps.calepinage.models import Calepinage  # noqa: E402

from .test_api_liste import BaseApiCalepinage, url_detail  # noqa: E402


class EndpointDocumentsEnBaseTest(BaseApiCalepinage):
    """``GET …/documents/`` — câblage, société, forme de l'inventaire."""

    def setUp(self):
        super().setUp()
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=copy.deepcopy(LAYOUT), layout_hash='a' * 64,
            version_moteur='calepinage-1.0.0',
            resultat={'prix_achat_absent': True})
        self.etranger = Calepinage.objects.create(
            company=self.autre, lead_id=7, titre='Voisine',
            roof_layout=copy.deepcopy(LAYOUT), resultat={'ok': True})
        self.vide = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Vide')

    def test_neuf_documents_sont_servis(self):
        reponse = self.api.get(f'{url_detail(self.calepinage.pk)}documents/')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(len(reponse.data['documents']), len(CODES_NEUF))
        self.assertEqual([d['code'] for d in reponse.data['documents']],
                         list(CODES_NEUF))

    def test_calepinage_vide_sert_l_exemple_vide(self):
        reponse = self.api.get(f'{url_detail(self.vide.pk)}documents/')
        self.assertEqual(reponse.status_code, 200)
        for document in reponse.data['documents']:
            self.assertFalse(document['disponible'])
            self.assertEqual(document['manque'][0]['champ'], 'roof_layout')

    def test_une_autre_societe_est_introuvable(self):
        reponse = self.api.get(f'{url_detail(self.etranger.pk)}documents/')
        self.assertEqual(reponse.status_code, 404)

    def test_technicien_sans_droit_est_refuse_403(self):
        reponse = self.api_sans.get(
            f'{url_detail(self.calepinage.pk)}documents/')
        self.assertEqual(reponse.status_code, 403)
