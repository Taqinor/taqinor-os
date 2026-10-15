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
  un jeu inconnu ⇒ 404 nommant ``preset_id`` (CI #993 api-fuzz : bien formé
  mais introuvable ; non-texte ⇒ 400), la réponse est le DÉTAIL
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
from apps.calepinage.tests._m0_en_attente import EN_ATTENTE_DETAIL, sans
from django.contrib.contenttypes.models import ContentType
from apps.calepinage.models import Calepinage
from apps.calepinage.services.modeles import marquer_modele
from apps.calepinage.services.parametres import (
    enregistrer_parametres,
)
from apps.crm.models import Client
from apps.records.models import Activity
from apps.ventes.models import Devis
from .test_api_liste import URL, BaseApiCalepinage

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
            with self.assertRaises(creation.JeuDeReglagesInconnu) as refus:
                creation._jeu_de_reglages(object(), 'tuile_romane')
        self.assertEqual(refus.exception.champ, 'preset_id')
        self.assertEqual(refus.exception.statut_http, 404)
        # CI #993 api-fuzz — la valeur reçue n'est jamais recopiée.
        self.assertNotIn('tuile_romane', str(refus.exception))

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


class CorpsPublieTest(SimpleTestCase):
    """ERR-ENF11-FUZZ-CALEPINAGE (w4) — le corps de ``depuis-modele`` : UN
    seul prédicat, publié au schéma ET appliqué par le serveur."""

    @staticmethod
    def _valider(corps):
        from apps.calepinage.views.bibliotheque import (
            CalepinageDepuisModeleCorpsSerializer,
        )

        champs = CalepinageDepuisModeleCorpsSerializer(data=corps)
        return champs.is_valid(), dict(champs.errors)

    def test_au_moins_un_rattachement_parmi_lead_client_devis(self):
        for corps in ({}, {'modele_id': 3}, {'titre': 'Nu'},
                      {'preset_id': None}, {'lead_id': 3, 'client_id': 0}):
            valide, erreurs = self._valider(corps)
            self.assertFalse(valide, corps)
            self.assertIn('client_id', erreurs)
        for corps in ({'lead_id': 1}, {'client_id': 1}, {'devis_id': 1},
                      {'modele_id': 2, 'lead_id': 1, 'titre': ' x ',
                       'preset_id': ''}):
            self.assertTrue(self._valider(corps)[0], corps)

    def test_formes_fautives_refusees_en_nommant_le_champ(self):
        base = {'lead_id': 1}
        fautifs = (('lead_id', 0), ('lead_id', -1), ('lead_id', 'AAA'),
                   ('lead_id', True), ('lead_id', None), ('lead_id', 2.5),
                   ('lead_id', 2 ** 31), ('modele_id', 0),
                   ('devis_id', [1]), ('client_id', {}), ('titre', 5),
                   ('titre', None), ('titre', 'x' * 201), ('titre', 'a\x00b'),
                   ('preset_id', 0), ('preset_id', {}), ('preset_id', 'a\x00b'))
        for champ, valeur in fautifs:
            valide, erreurs = self._valider({**base, champ: valeur})
            self.assertFalse(valide, (champ, valeur))
            self.assertIn(champ, erreurs)
        # La borne est atteignable, et le titre garde ses blancs saisis.
        valide, _ = self._valider({'lead_id': 2 ** 31 - 1,
                                   'titre': 'x' * 200})
        self.assertTrue(valide)

    def test_le_titre_garde_ses_blancs_et_le_corps_non_objet_est_refuse(self):
        from apps.calepinage.views.bibliotheque import (
            CalepinageDepuisModeleCorpsSerializer,
        )

        champs = CalepinageDepuisModeleCorpsSerializer(
            data={'lead_id': 1, 'titre': '  Villa  '})
        self.assertTrue(champs.is_valid())
        self.assertEqual(champs.validated_data['titre'], '  Villa  ')
        for corps in (None, [], 'AAA', 0):
            self.assertFalse(
                CalepinageDepuisModeleCorpsSerializer(data=corps).is_valid())

    def test_statuts_des_refus_de_rattachement(self):
        from apps.calepinage.services import creation, modeles

        for classe, code, parent in (
                (creation.RattachementIntrouvable, 404,
                 creation.CreationRefusee),
                (creation.RattachementEnConflit, 409,
                 creation.CreationRefusee),
                (modeles.RattachementDuModeleIntrouvable, 404,
                 modeles.ModeleInvalide),
                (modeles.ModeleEnConflit, 409, modeles.ModeleInvalide)):
            self.assertEqual(classe.statut_http, code)
            self.assertTrue(issubclass(classe, parent))
        # Les appelants qui ne lisent pas ``statut_http`` gardent leur 400.
        self.assertFalse(hasattr(creation.CreationRefusee, 'statut_http'))
        self.assertFalse(hasattr(modeles.ModeleInvalide, 'statut_http'))


# ── ORM — la CI est la gate de ces classes ─────────────────────────────────

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
        # ACAL117 (D-ACAL-15) — le lead cible d'un modèle porte un repère
        # toit : la conception y est translatée (épingle = ce repère).
        self.lead_2.roof_point = {'lat': 33.59, 'lng': -7.62}
        self.lead_2.save(update_fields=['roof_point'])

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
                         sorted(sans(CONTRAT_DETAIL['exemple'],
                                     EN_ATTENTE_DETAIL)))
        copie = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(copie.lead_id, self.lead_2.pk)
        self.assertEqual(copie.roof_layout['zones'][0]['pitchDeg'], 22)
        self.modele.refresh_from_db()
        self.assertEqual(self.modele.roof_layout, DOCUMENT)
        # Lot 2 critique #15 — la version « Conception d'origine » EST le
        # document courant (jeu appliqué), pas l'état d'avant réglage.
        origine = copie.versions.order_by('created_at', 'id').first()
        self.assertTrue(origine.libelle.startswith("Conception d'origine"))
        self.assertEqual(origine.roof_layout, copie.roof_layout)
        self.assertEqual(origine.roof_layout['zones'][0]['pitchDeg'], 22)

    def test_sans_jeu_identique_a_la_copie_d_aujourd_hui(self):
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        copie = Calepinage.objects.get(pk=reponse.data['id'])
        # ACAL117 — même conception, épinglée sur le repère du lead cible
        # (le modèle n'avait pas d'épingle : aucun vecteur, rien ne bouge).
        sans_pin = {cle: valeur for cle, valeur in copie.roof_layout.items()
                    if cle != 'pin'}
        self.assertEqual(sans_pin, self.modele.roof_layout)
        self.assertEqual(copie.roof_layout['pin'],
                         {'lat': 33.59, 'lng': -7.62})

    def test_modele_d_une_autre_societe_introuvable(self):
        reponse = self.api_autre.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead.pk},
            format='json')
        self.assertEqual(reponse.status_code, 404)

    def test_jeu_inconnu_404_nommant_le_champ(self):
        # CI #993 api-fuzz (cas v4QwmD) — un `preset_id` texte inconnu, même
        # `{}` envoyé en multipart, est INTROUVABLE (404) ; un non-texte JSON
        # est mal formé (400) ; rien n'est créé, la valeur n'est pas recopiée.
        avant = Calepinage.objects.count()
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk,
            'preset_id': 'hangar'}, format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)
        self.assertIn('preset_id', reponse.data)
        self.assertNotIn('hangar', str(reponse.data['preset_id']))
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk,
            'preset_id': '{}'}, format='multipart')
        self.assertEqual(reponse.status_code, 404, reponse.data)
        self.assertIn('preset_id', reponse.data)
        for brut in ({}, [], 0):
            reponse = self.api.post(URL_DEPUIS_MODELE, {
                'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk,
                'preset_id': brut}, format='json')
            self.assertEqual(reponse.status_code, 400, (brut, reponse.data))
            self.assertIn('preset_id', reponse.data)
        reponse = self.api.post(URL_DEPUIS_MODELE, {
            'modele_id': 999999, 'lead_id': self.lead_2.pk}, format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)
        self.assertIn('modele_id', reponse.data)
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
        # Le modèle seul, ou un corps qui n'a que titre / jeu, n'est pas un
        # rattachement non plus (le schéma publié l'exige : ``anyOf``).
        for corps in ({'modele_id': self.modele.pk}, {'titre': 'Nu'},
                      {'preset_id': 'villa'}):
            reponse = self.api.post(URL_DEPUIS_MODELE, corps, format='json')
            self.assertEqual(reponse.status_code, 400, corps)
            self.assertIn('client_id', reponse.data)

    def test_forme_fautive_400_avant_toute_ecriture(self):
        """ERR-ENF11-FUZZ-CALEPINAGE (w4) — les identifiants sont des entiers
        >= 1 (32 bits), le titre un texte de 200 signes au plus : une valeur
        ailleurs n'est plus ignorée ni coercée (un identifiant illisible
        laissait passer le reste du corps)."""
        avant = Calepinage.objects.count()
        base = {'modele_id': self.modele.pk, 'lead_id': self.lead_2.pk}
        fautifs = ({'lead_id': 0}, {'lead_id': -3}, {'lead_id': 'AAA'},
                   {'lead_id': True}, {'lead_id': None}, {'lead_id': 2.5},
                   {'client_id': 2 ** 31}, {'devis_id': 0},
                   {'modele_id': 0}, {'titre': 5}, {'titre': None},
                   {'titre': 'x' * 201}, {'titre': 'a\x00b'},
                   {'preset_id': 'a\x00b'})
        for surcharge in fautifs:
            reponse = self.api.post(URL_DEPUIS_MODELE, {**base, **surcharge},
                                    format='json')
            self.assertEqual(reponse.status_code, 400, (surcharge,
                                                        reponse.data))
            self.assertIn(next(iter(surcharge)), reponse.data)
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_rattachement_introuvable_404_jamais_400(self):
        """Un identifiant bien formé qui ne désigne rien (ou une ligne d'une
        autre société) est introuvable : 404 nommant le champ du corps."""
        avant = Calepinage.objects.count()
        for corps, champ in (({'lead_id': 987654}, 'lead_id'),
                             ({'client_id': 987654}, 'client_id'),
                             ({'devis_id': 987654}, 'devis_id'),
                             ({'modele_id': self.modele.pk,
                               'lead_id': 987654}, 'lead_id'),
                             ({'modele_id': self.modele.pk,
                               'client_id': 987654}, 'client_id'),
                             ({'modele_id': self.modele.pk,
                               'devis_id': 987654}, 'devis_id')):
            reponse = self.api.post(URL_DEPUIS_MODELE, corps, format='json')
            self.assertEqual(reponse.status_code, 404, (corps, reponse.data))
            self.assertIn(champ, reponse.data)
        self.assertEqual(Calepinage.objects.count(), avant)
