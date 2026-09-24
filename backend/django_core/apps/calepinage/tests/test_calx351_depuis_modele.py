"""CALX351 — démarrer un calepinage depuis un modèle et un jeu de réglages.

Ce qui est prouvé ici :

* ÉQUIVALENCE (D12) : ``preset_id`` absent ⇒ aucune lecture de réglage, les
  trois portes de ``services/creation.py`` créent exactement ce qu'elles
  créaient (même document, même empreinte, aucune note de jeu) ;
* un jeu de réglages inconnu est refusé en NOMMANT ``preset_id`` — et rien
  n'est créé ;
* le jeu est appliqué aux pans du document de DÉPART par
  ``services/gabarits.py::appliquer_gabarit`` (clés de pan seulement, jamais
  la géométrie), sur une COPIE — le document du devis ou du modèle reste
  intact, et l'empreinte du calepinage créé est recalculée ;
* ``POST calepinages/depuis-modele/`` : un modèle d'une autre société ⇒ 404,
  un jeu inconnu ⇒ 400 nommant ``preset_id``, la réponse est le DÉTAIL
  agrégé dont les clés sont celles de ``calepinage_detail.json`` ; sans
  modèle, la porte ordinaire du rattachement crée (lead/client/devis).

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx351_depuis_modele -v2
"""
import copy
import json
import pathlib
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.services import creation

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT_DETAIL = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_detail.json')
    .read_text(encoding='utf-8'))

JEU = {'id': 'villa', 'nom': 'Villa tuiles', 'roofType': 'tuiles',
       'pitchDeg': 22, 'marge_m': 0.3}

DOCUMENT = {
    'version': 2,
    'zones': [
        {'id': 'z1', 'label': 'Pan Sud', 'pitchDeg': 10,
         'vertices': [[-7.6, 33.5], [-7.5999, 33.5], [-7.5999, 33.5001]],
         'geometry': {'count': 2, 'panels': [{'cx': 1, 'cy': 1}]}},
        {'id': 'z2', 'label': 'Pan Nord', 'roofType': 'tuiles',
         'pitchDeg': 22, 'vertices': []},
    ],
}


#: Une section ``presets`` avec LES DEUX formes de jeux, les interrupteurs et
#: le catalogue de kits (qui ne sont pas des jeux).
PRESETS = {
    'jeux': [JEU],
    'hangar_bac_acier': {'orientation': 'paysage', 'source': 'Fiche pose'},
    'kits': [{'id': 3}],
    'feu_vert_bureau_etudes': True,
    'approbation_exigee': False,
}


def reglages(presets=PRESETS):
    return mock.patch('apps.calepinage.selectors.parametres_de_societe',
                      return_value={'presets': presets})


class JeuDeReglagesTest(SimpleTestCase):

    def test_absent_aucune_lecture_de_reglage(self):
        with mock.patch('apps.calepinage.selectors.parametres_de_societe',
                        side_effect=AssertionError('lecture interdite')):
            self.assertIsNone(creation._jeu_de_reglages(object(), None))
            self.assertIsNone(creation._jeu_de_reglages(object(), ''))

    def test_inconnu_refuse_en_nommant_preset_id(self):
        with reglages():
            with self.assertRaises(creation.CreationRefusee) as refus:
                creation._jeu_de_reglages(object(), 'tuile_romane')
        self.assertEqual(refus.exception.champ, 'preset_id')
        self.assertIn('tuile_romane', str(refus.exception))

    def test_les_deux_formes_de_jeux_sont_offertes(self):
        with reglages():
            self.assertEqual(creation._jeu_de_reglages(object(), 'villa'),
                             JEU)
            nomme = creation._jeu_de_reglages(object(), 'hangar_bac_acier')
            ids = [jeu['id'] for jeu in creation._jeux_disponibles(object())]
        self.assertEqual(nomme['orientation'], 'paysage')
        self.assertEqual(nomme['nom'], 'hangar_bac_acier')
        self.assertEqual(ids, ['villa', 'hangar_bac_acier'])

    def test_kits_et_interrupteurs_ne_sont_pas_des_jeux(self):
        with reglages():
            for cle in ('kits', 'jeux', 'feu_vert_bureau_etudes',
                        'approbation_exigee'):
                with self.subTest(cle=cle):
                    with self.assertRaises(creation.CreationRefusee):
                        creation._jeu_de_reglages(object(), cle)


class DocumentDeDepartTest(SimpleTestCase):

    def test_le_jeu_regle_les_pans_sur_une_copie(self):
        original = copy.deepcopy(DOCUMENT)
        document, regles = creation._layout_regle(DOCUMENT, JEU)
        self.assertEqual(DOCUMENT, original, 'le document source est intact')
        self.assertEqual(regles, 1, 'le pan déjà réglé ne compte pas')
        pan = document['zones'][0]
        self.assertEqual((pan['roofType'], pan['pitchDeg']), ('tuiles', 22))
        self.assertEqual(pan['vertices'], DOCUMENT['zones'][0]['vertices'])
        self.assertEqual(pan['geometry'], DOCUMENT['zones'][0]['geometry'])
        self.assertNotIn('marge_m', pan)

    def test_document_vide_ou_sans_pan(self):
        self.assertEqual(creation._layout_regle(None, JEU), (None, 0))
        self.assertEqual(creation._layout_regle({'zones': 'x'}, JEU)[1], 0)


class ChampsDuCorpsTest(SimpleTestCase):

    def test_un_refus_nomme_le_champ_du_corps(self):
        from apps.calepinage.views.bibliotheque import CHAMPS_DU_CORPS

        self.assertEqual(CHAMPS_DU_CORPS, {
            'modele': 'modele_id', 'lead': 'lead_id',
            'client': 'client_id', 'devis': 'devis_id'})


# ── ORM — la CI est la gate de ces classes ─────────────────────────────────

from django.contrib.contenttypes.models import ContentType  # noqa: E402

from apps.calepinage.models import Calepinage  # noqa: E402
from apps.calepinage.services.modeles import marquer_modele  # noqa: E402
from apps.calepinage.services.parametres import (  # noqa: E402
    enregistrer_parametres,
)
from apps.crm.models import Client  # noqa: E402
from apps.records.models import Activity  # noqa: E402
from apps.ventes.models import Devis  # noqa: E402

from .test_api_liste import URL, BaseApiCalepinage  # noqa: E402

URL_DEPUIS_MODELE = f'{URL}depuis-modele/'


class DepuisModeleEnBase(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        enregistrer_parametres(self.company,
                               {'presets': {'jeux': [dict(JEU)]}})
        self.modele = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Modèle villa',
            roof_layout=copy.deepcopy(DOCUMENT))
        marquer_modele(self.modele)

    def _notes(self, calepinage):
        return Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk)

    # ── Les trois portes de services/creation.py ───────────────────────
    def test_porte_lead_sans_jeu_identique_a_aujourd_hui(self):
        calepinage = creation.creer_pour_lead(self.lead_2.pk, self.company,
                                              user=self.user)
        self.assertIsNone(calepinage.roof_layout)
        self.assertFalse(any('Jeu de réglages' in (note.body or '')
                             for note in self._notes(calepinage)))

    def test_porte_lead_jeu_inconnu_rien_n_est_cree(self):
        avant = Calepinage.objects.count()
        with self.assertRaises(creation.CreationRefusee) as refus:
            creation.creer_pour_lead(self.lead_2.pk, self.company,
                                     preset_id='hangar')
        self.assertEqual(refus.exception.champ, 'preset_id')
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_porte_devis_applique_le_jeu_sur_une_copie(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-CALX351-1')
        Devis.objects.filter(pk=devis.pk).update(
            roof_layout=copy.deepcopy(DOCUMENT))
        calepinage, cree = creation.obtenir_ou_creer_pour_devis(
            devis.pk, self.company, user=self.user, preset_id='villa')
        self.assertTrue(cree)
        self.assertEqual(calepinage.roof_layout['zones'][0]['pitchDeg'], 22)
        devis.refresh_from_db()
        self.assertEqual(devis.roof_layout['zones'][0]['pitchDeg'], 10)
        self.assertTrue(calepinage.layout_hash)

    def test_porte_client_accepte_le_jeu(self):
        calepinage = creation.creer_pour_client(
            self.client_a.pk, self.company, preset_id='villa')
        self.assertTrue(any('Villa tuiles' in (note.body or '')
                            for note in self._notes(calepinage)))

    # ── La porte HTTP ─────────────────────────────────────────────────────
    def test_depuis_modele_rend_le_detail_du_contrat(self):
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk,
            'titre': 'Villa Maârif', 'preset_id': 'villa'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT_DETAIL['exemple']))
        copie = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(copie.lead_id, self.lead_2.pk)
        self.assertEqual(copie.roof_layout['zones'][0]['pitchDeg'], 22)
        self.modele.refresh_from_db()
        self.assertEqual(self.modele.roof_layout, DOCUMENT)

    def test_sans_jeu_identique_a_la_copie_d_aujourd_hui(self):
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        copie = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(copie.roof_layout, self.modele.roof_layout)
        self.assertEqual(copie.layout_hash, self.modele.layout_hash)

    def test_modele_d_une_autre_societe_introuvable(self):
        reponse = self.api_autre.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead.pk},
            format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_jeu_inconnu_400_nommant_le_champ(self):
        avant = Calepinage.objects.count()
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk,
            'preset_id': 'hangar'}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('preset_id', reponse.data)
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_sans_modele_la_porte_du_rattachement_cree(self):
        client = Client.objects.create(company=self.company,
                                       nom='Client CALX351')
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'client_id': client.pk, 'preset_id': 'villa'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(
            Calepinage.objects.get(pk=reponse.data['id']).client_id,
            client.pk)

    def test_sans_rattachement_refus_nomme(self):
        reponse = self.api.post(URL_DEPUIS_MODELE, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('client_id', reponse.data)
