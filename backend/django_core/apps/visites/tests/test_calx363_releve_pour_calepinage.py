"""CALX363 — la porte visite technique → calepinage, côté ``apps.visites``.

Ce qui est prouvé ici, et pourquoi :

* **Le contrat partagé est tenu** (PACT10) — la lecture rend EXACTEMENT les
  clés que ``apps/calepinage/contract_samples/calepinage_releve_visite.json``
  attribue au côté visites, et l'exemple committé se REJOUE : ses mesures,
  réinjectées comme saisie, ressortent à l'identique (libellés, unités,
  ordre) ; ses photos aussi.
* **Une mesure vide est OMISE**, jamais servie à ``None`` ; ``False`` et
  ``0`` sont des saisies ; aucune valeur n'est convertie (l'orientation reste
  le choix saisi).
* **Rien ne sort tant que la visite n'est pas VALIDÉE**, et l'absence NOMME
  ce qui manque — sans jamais changer la forme de la réponse.
* **Une visite d'une autre société ne peut pas sortir** (le bornage vient du
  lead) et **la lecture n'écrit rien**.

Les classes ``*EnBase`` exigent la base (``TestCase``) : elles tournent en
CI. Les autres sont PURES (``SimpleTestCase``) et tournent partout.

Aucune horloge : ``validee_le`` est affirmé ``None`` (aucun horodatage de
validation n'est stocké par ``VisiteTerrain``), jamais une date « du jour ».
"""
from __future__ import annotations

import json
import pathlib

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext

from apps.visites import selectors, visite_checklist

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[2] / 'calepinage'
     / 'contract_samples' / 'calepinage_releve_visite.json')
    .read_text(encoding='utf-8'))

#: Les clés que le CALEPINAGE ajoute (CALX364) : lui seul sait si CE
#: calepinage a déjà repris la visite, et quel relevé il a écrit.
CLES_COTE_CALEPINAGE = {'deja_repris', 'releve'}

#: Les clés que CETTE lecture sert — dérivées du contrat, jamais retapées.
CLES_COTE_VISITES = set(CONTRAT['exemple']) - CLES_COTE_CALEPINAGE


def _categorie_de(code):
    for cat in visite_checklist.categories():
        if any(champ['code'] == code for champ in cat['mesures']):
            return cat['categorie']
    raise AssertionError('mesure « %s » absente de la checklist' % code)


def _saisie_depuis_le_contrat(mesures):
    """Le JSON stocké (``{categorie: {code: valeur}}``) qui rend ``mesures``."""
    saisie = {}
    for mesure in mesures:
        saisie.setdefault(_categorie_de(mesure['code']), {})[
            mesure['code']] = mesure['valeur']
    return saisie


class _Media:
    """Un ``VisiteMedia`` lu — seulement ce que la porte consulte."""

    def __init__(self, slot_code, attachment_id, a_refaire=False):
        self.slot_code = slot_code
        self.attachment_id = attachment_id
        self.a_refaire = a_refaire


# ═══════════════════════════════════════════════════════════════════════════
# 1. LE CONTRAT PARTAGÉ — pur
# ═══════════════════════════════════════════════════════════════════════════

class ContratReleveVisiteTest(SimpleTestCase):
    """L'exemple committé est la forme que cette porte sert."""

    def test_l_echantillon_porte_les_trois_cles_de_pact10(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CONTRAT)
        self.assertEqual(
            CONTRAT['endpoint'],
            'GET /api/django/calepinage/calepinages/<int:pk>/releve-visite/')

    def test_la_porte_sert_exactement_les_cles_du_cote_visites(self):
        self.assertEqual(
            CLES_COTE_VISITES,
            {'visite_id', 'validee_le', 'mesures', 'photos',
             'motif_absence'})
        self.assertEqual(set(selectors.releve_pour_calepinage(None)),
                         CLES_COTE_VISITES)

    def test_les_etats_du_contrat_ont_tous_la_meme_forme(self):
        for etat in ('exemple_avant_reprise', 'exemple_vide'):
            with self.subTest(etat=etat):
                self.assertEqual(sorted(CONTRAT[etat]),
                                 sorted(CONTRAT['exemple']))

    def test_sans_visite_validee_les_cles_de_donnees_sont_nulles(self):
        vide = CONTRAT['exemple_vide']

        for cle in ('visite_id', 'validee_le', 'mesures', 'photos'):
            self.assertIsNone(vide[cle], cle)
        self.assertEqual(vide['motif_absence'],
                         selectors.MOTIF_VISITE_NON_VALIDEE)

    def test_les_mesures_de_l_exemple_se_rejouent_a_l_identique(self):
        attendues = CONTRAT['exemple']['mesures']

        rendues = selectors._releve_mesures_saisies(
            _saisie_depuis_le_contrat(attendues))

        self.assertEqual(rendues, attendues)

    def test_les_photos_de_l_exemple_se_rejouent_a_l_identique(self):
        attendues = CONTRAT['exemple']['photos']
        medias = [_Media(photo['slot_code'], photo['attachment_id'])
                  for photo in attendues]

        self.assertEqual(selectors._releve_photos_retenues(medias),
                         attendues)

    def test_aucune_valeur_de_l_exemple_n_est_nulle(self):
        for mesure in CONTRAT['exemple']['mesures']:
            self.assertIsNotNone(mesure['valeur'], mesure['code'])

    def test_la_provenance_ecrite_cote_calepinage_est_nommee(self):
        releve = CONTRAT['exemple']['releve']

        self.assertEqual(releve['provenance'], 'visite')
        for photo in releve['photos']:
            self.assertEqual(photo['provenance'], 'visite')


# ═══════════════════════════════════════════════════════════════════════════
# 2. LES MESURES ET LES PHOTOS — pur
# ═══════════════════════════════════════════════════════════════════════════

class MesuresSaisiesTest(SimpleTestCase):
    """Une mesure non saisie est OMISE ; rien n'est converti ni complété."""

    def test_une_mesure_vide_est_omise_jamais_servie_a_null(self):
        rendues = selectors._releve_mesures_saisies({
            'toiture': {'longueur_m': 12.5, 'largeur_m': None,
                        'orientation': '', 'obstacles_notes': '   '},
        })

        self.assertEqual([m['code'] for m in rendues], ['longueur_m'])
        for mesure in rendues:
            self.assertIsNotNone(mesure['valeur'])

    def test_faux_et_zero_sont_des_saisies(self):
        rendues = selectors._releve_mesures_saisies({
            'toiture': {'toit_plat': False},
            'tableau': {'emplacements_libres': 0},
        })

        par_code = {m['code']: m['valeur'] for m in rendues}
        self.assertIs(par_code['toit_plat'], False)
        self.assertEqual(par_code['emplacements_libres'], 0)

    def test_l_unite_est_celle_du_libelle_de_la_checklist(self):
        rendues = selectors._releve_mesures_saisies({
            'toiture': {'longueur_m': 12.5, 'pente_deg': 15,
                        'orientation': 'sud'},
            'tableau': {'calibre_disjoncteur_a': 63,
                        'emplacements_libres': 4},
            'local_onduleur': {'largeur_mur_cm': 200},
        })

        unites = {m['code']: m['unite'] for m in rendues}
        self.assertEqual(unites, {
            'longueur_m': 'm', 'pente_deg': '°', 'orientation': None,
            'calibre_disjoncteur_a': 'A', 'emplacements_libres': None,
            'largeur_mur_cm': 'cm',
        })

    def test_aucune_valeur_n_est_convertie(self):
        rendues = selectors._releve_mesures_saisies({
            'toiture': {'orientation': 'sud_est', 'pente_deg': '15'},
        })

        par_code = {m['code']: m['valeur'] for m in rendues}
        # L'orientation reste le CHOIX saisi (jamais un azimut) et une
        # valeur saisie en texte n'est pas « corrigée » en nombre.
        self.assertEqual(par_code, {'pente_deg': '15',
                                    'orientation': 'sud_est'})

    def test_l_ordre_est_celui_de_la_checklist(self):
        rendues = selectors._releve_mesures_saisies({
            'tableau': {'type_alimentation': 'tri'},
            'toiture': {'type_couverture': 'tole', 'longueur_m': 9},
        })

        self.assertEqual([m['code'] for m in rendues],
                         ['longueur_m', 'type_couverture',
                          'type_alimentation'])

    def test_une_cle_inconnue_de_la_checklist_ne_sort_pas(self):
        rendues = selectors._releve_mesures_saisies({
            'toiture': {'longueur_m': 9, 'hauteur_faitage_m': 7},
            'inconnue': {'x': 1},
        })

        self.assertEqual([m['code'] for m in rendues], ['longueur_m'])

    def test_un_json_illisible_ne_rend_aucune_mesure(self):
        for brut in (None, [], 'texte', {'toiture': 'pas un dict'}):
            with self.subTest(brut=brut):
                self.assertEqual(selectors._releve_mesures_saisies(brut),
                                 [])


class PhotosRetenuesTest(SimpleTestCase):
    """Les photos sortent par identifiant de pièce jointe, jamais copiées."""

    def test_une_photo_a_refaire_ne_sort_pas(self):
        photos = selectors._releve_photos_retenues([
            _Media('toiture_vue_generale', 41),
            _Media('toiture_vue_generale', 42, a_refaire=True),
        ])

        self.assertEqual([p['attachment_id'] for p in photos], [41])

    def test_un_slot_inconnu_garde_son_code(self):
        photos = selectors._releve_photos_retenues([
            _Media('ancien_slot', 9)])

        self.assertEqual(photos, [{'slot_code': 'ancien_slot',
                                   'libelle': 'ancien_slot',
                                   'attachment_id': 9}])


class SansLeadTest(SimpleTestCase):
    """Un lead absent rend la forme vide, sans lever — et sans requête."""

    def test_lead_absent(self):
        rendu = selectors.releve_pour_calepinage(None)

        self.assertEqual(rendu, {
            'visite_id': None, 'validee_le': None, 'mesures': None,
            'photos': None, 'motif_absence': selectors.MOTIF_AUCUNE_VISITE,
        })


# ═══════════════════════════════════════════════════════════════════════════
# 3. EN BASE — exécuté en CI
# ═══════════════════════════════════════════════════════════════════════════

class ReleveEnBaseTest(TestCase):
    """La porte réelle, sur deux vraies sociétés."""

    @classmethod
    def setUpTestData(cls):
        from apps.crm.models import Lead
        from authentication.models import Company

        cls.company = Company.objects.create(nom='CALX363 Solaire',
                                             slug='calx363-a')
        cls.autre = Company.objects.create(nom='CALX363 Concurrent',
                                           slug='calx363-b')
        cls.lead = Lead.objects.create(company=cls.company, nom='Bennani',
                                       prenom='Karim')
        cls.lead_sans_visite = Lead.objects.create(company=cls.company,
                                                   nom='Sans visite')

    def _visite(self, statut, mesures=None, company=None, lead=None):
        from apps.visites.models import VisiteTerrain

        return VisiteTerrain.objects.create(
            company=company or self.company, lead=lead or self.lead,
            statut=statut, mesures=mesures or {})

    def _photo(self, visite, slot_code, a_refaire=False):
        from apps.crm.models import Lead
        from apps.records.models import Attachment
        from apps.visites.models import VisiteMedia

        piece = Attachment.objects.create(
            company=visite.company,
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=visite.lead_id,
            file_key='visites/%s.png' % slot_code,
            filename='%s.png' % slot_code, size=1, mime='image/png')
        VisiteMedia.objects.create(
            company=visite.company, visite=visite, attachment=piece,
            slot_code=slot_code, a_refaire=a_refaire)
        return piece

    def test_sans_aucune_visite_les_cles_sont_nulles_et_nommees(self):
        rendu = selectors.releve_pour_calepinage(self.lead_sans_visite)

        self.assertEqual(set(rendu), CLES_COTE_VISITES)
        for cle in ('visite_id', 'validee_le', 'mesures', 'photos'):
            self.assertIsNone(rendu[cle], cle)
        self.assertEqual(rendu['motif_absence'],
                         selectors.MOTIF_AUCUNE_VISITE)

    def test_une_visite_non_validee_ne_sort_pas(self):
        from apps.visites.models import VisiteTerrain

        for statut in (VisiteTerrain.Statut.BROUILLON,
                       VisiteTerrain.Statut.EN_COURS,
                       VisiteTerrain.Statut.TERMINEE,
                       VisiteTerrain.Statut.A_REFAIRE):
            with self.subTest(statut=statut):
                visite = self._visite(statut,
                                      mesures={'toiture': {'longueur_m': 9}})

                rendu = selectors.releve_pour_calepinage(self.lead)

                self.assertEqual(set(rendu), CLES_COTE_VISITES)
                self.assertIsNone(rendu['visite_id'])
                self.assertIsNone(rendu['mesures'])
                self.assertEqual(rendu['motif_absence'],
                                 selectors.MOTIF_VISITE_NON_VALIDEE)
                visite.delete()

    def test_la_derniere_visite_validee_sort_avec_ses_saisies(self):
        from apps.visites.models import VisiteTerrain

        ancienne = self._visite(VisiteTerrain.Statut.VALIDEE,
                                mesures={'toiture': {'longueur_m': 7}})
        self._photo(ancienne, 'toiture_vue_generale')
        visite = self._visite(
            VisiteTerrain.Statut.VALIDEE,
            mesures=_saisie_depuis_le_contrat(
                CONTRAT['exemple']['mesures']))
        retenue = self._photo(visite, 'toiture_vue_generale')
        self._photo(visite, 'toiture_obstacles', a_refaire=True)

        rendu = selectors.releve_pour_calepinage(self.lead)

        self.assertEqual(set(rendu), CLES_COTE_VISITES)
        self.assertEqual(rendu['visite_id'], visite.id)
        self.assertEqual(rendu['mesures'], CONTRAT['exemple']['mesures'])
        self.assertEqual(rendu['photos'], [{
            'slot_code': 'toiture_vue_generale',
            'libelle': 'Vue générale du toit',
            'attachment_id': retenue.id,
        }])
        self.assertIsNone(rendu['motif_absence'])
        # Aucun horodatage de validation n'est stocké : jamais une autre
        # date à sa place.
        self.assertIsNone(rendu['validee_le'])

    def test_une_visite_d_une_autre_societe_ne_sort_pas(self):
        from apps.visites.models import VisiteTerrain

        # Une ligne CORROMPUE : visite d'une autre société posée sur NOTRE
        # lead. Le bornage vient du lead — elle ne peut pas sortir.
        self._visite(VisiteTerrain.Statut.VALIDEE, company=self.autre,
                     mesures={'toiture': {'longueur_m': 99}})

        rendu = selectors.releve_pour_calepinage(self.lead)

        self.assertIsNone(rendu['visite_id'])
        self.assertEqual(rendu['motif_absence'],
                         selectors.MOTIF_AUCUNE_VISITE)

    def test_la_lecture_n_ecrit_rien(self):
        from apps.visites.models import VisiteTerrain

        visite = self._visite(VisiteTerrain.Statut.VALIDEE,
                              mesures={'toiture': {'longueur_m': 9}})
        self._photo(visite, 'general_facade')

        with CaptureQueriesContext(connection) as requetes:
            selectors.releve_pour_calepinage(self.lead)

        ecritures = [requete['sql'] for requete in requetes.captured_queries
                     if not requete['sql'].lstrip().upper().startswith(
                         'SELECT')]
        self.assertEqual(ecritures, [])
