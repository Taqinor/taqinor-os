"""CAD153 — T9 : les tests qui FIGENT le script d'appel guidé.

Quatre gardes, et rien d'autre (Done de la tâche) :

  1. le panneau ne renvoie JAMAIS une question déjà répondue ni une valeur
     par défaut — prouvé sur CHAQUE colonne qu'il peut poser, pas sur un
     exemple choisi ;
  2. tout champ neuf du script guidé est déclaré à l'écran (``fieldLabels``)
     et la garde de provenance DC11 reste verte ;
  3. les cinq touches d'appel qui n'avaient aucun script (Appel 4, Appel 6,
     suivis J2/J7/J11) portent un ``template_cle`` non vide — et chaque
     touche d'appel des cadences par défaut aussi ;
  4. le contrat ``panneau_appel.json`` a EXACTEMENT la forme de la réponse
     réelle (racine, touche, script, question, équipement).

La moitié écran de ces gardes vit dans
``frontend/src/features/crm/relances/PanneauScriptAppel.test.jsx``.

Les classes ``SimpleTestCase`` travaillent sur un ``Lead`` NON ENREGISTRÉ
(l'assemblage du panneau ne lit que des attributs) ; seule la dernière classe
(l'endpoint HTTP) a besoin de l'ORM — écrite ici, exécutée par la CI.
"""
import datetime
import json
import re
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.db import models
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm import panneau_appel as panneau
from apps.crm import questionnaire, selectors
from apps.crm.models import Lead, RelanceEtape
from apps.crm.tests_cad149_vague1_champs import CHAMPS_VAGUE_1
from apps.crm.tests_cad154_vague2_champs import CHAMPS_VAGUE_2
from apps.parametres.models_messages import MESSAGE_TEMPLATE_DEFAULTS
from apps.parametres.models_relance import (
    CADENCE_APRES_DEVIS_DEFAUT, CADENCE_CONTACT_DEFAUT,
    CADENCE_DEUXIEME_AFFAIRE_DEFAUT, CADENCE_REVEIL_DEFAUT, CanalRelance,
)

RACINE = Path(__file__).resolve().parents[4]
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'panneau_appel.json').read_text(encoding='utf-8'))
FIELD_LABELS = (RACINE / 'frontend' / 'src' / 'features' / 'crm' / 'workspace'
                / 'fieldLabels.js').read_text(encoding='utf-8')


def _lead(**kwargs):
    return Lead(nom='Prospect', **kwargs)


def _univers(lead):
    """Toutes les colonnes que le panneau peut poser à CE lead."""
    champs = []
    for section in questionnaire.SECTIONS:
        champs.extend(questionnaire.CHAMPS_PAR_SECTION.get(section, ()))
    champs.extend(panneau.champs_oraux_du_segment(lead))
    return [c for c in dict.fromkeys(champs)
            if c not in panneau.CHAMPS_JAMAIS_DEMANDES]


def _valeur_reelle(champ):
    """Une RÉPONSE réelle, valide pour le type du champ (jamais son défaut)."""
    meta = Lead._meta.get_field(champ)
    if isinstance(meta, models.BooleanField):
        return True
    if meta.choices:
        return meta.choices[0][0]
    if isinstance(meta, models.DecimalField):
        return Decimal('2.50')
    if isinstance(meta, models.IntegerField):
        return 3
    if isinstance(meta, models.EmailField):
        return 'client@exemple.ma'
    return 'Réponse réelle'


def _champs(questions):
    return [q['champ'] for q in questions]


# ── Garde 1 — jamais une question répondue, jamais une valeur par défaut ────
class GardeUnJamaisReposeeJamaisParDefaut(SimpleTestCase):
    SEGMENTS = (None, Lead.TypeInstallation.RESIDENTIEL,
                Lead.TypeInstallation.AGRICOLE)

    def test_chaque_colonne_repondue_sort_des_questions_et_se_relit(self):
        for segment in self.SEGMENTS:
            for champ in _univers(_lead(type_installation=segment)):
                valeur = _valeur_reelle(champ)
                lead = _lead(type_installation=segment, **{champ: valeur})
                with self.subTest(segment=segment, champ=champ):
                    self.assertNotIn(
                        champ, _champs(panneau.questions_a_poser(lead)))
                    self.assertIn(champ, panneau.prefill_du_panneau(lead))

    def test_un_lead_vierge_n_a_aucun_prefill_quel_que_soit_le_segment(self):
        for segment in self.SEGMENTS:
            with self.subTest(segment=segment):
                self.assertEqual(
                    panneau.prefill_du_panneau(
                        _lead(type_installation=segment)), {})

    def test_une_colonne_a_defaut_ne_publie_jamais_ce_defaut(self):
        """Le défaut d'une colonne (ex. ``ete_differente = False`` dès la
        création) n'est pas une réponse du client : il reste une question."""
        vierge = _lead()
        prefill = panneau.prefill_du_panneau(vierge)
        questions = _champs(panneau.questions_a_poser(vierge))
        avec_defaut = [c for c in _univers(vierge)
                       if Lead._meta.get_field(c).has_default()]
        self.assertTrue(avec_defaut, 'aucune colonne à défaut : garde vide')
        for champ in avec_defaut:
            with self.subTest(champ=champ):
                self.assertNotIn(champ, prefill)
                self.assertIn(champ, questions)


# ── Garde 2 — tout champ neuf est déclaré à l'écran, DC11 reste verte ───────
class GardeDeuxFieldLabelsEtDc11(SimpleTestCase):
    def test_chaque_champ_des_vagues_1_et_2_a_son_entree_fieldlabels(self):
        for champ in (*CHAMPS_VAGUE_1, *CHAMPS_VAGUE_2):
            with self.subTest(champ=champ):
                self.assertRegex(
                    FIELD_LABELS, rf'(?m)^\s+{re.escape(champ)}: \{{',
                    f'« {champ} » absent de fieldLabels.js : une erreur '
                    'serveur sur ce champ afficherait sa clé brute.')

    def test_la_garde_de_provenance_dc11_ne_signale_aucune_omission(self):
        self.assertEqual(selectors.lead_provenance_omissions(), [])


# ── Garde 3 — les cinq touches d'appel ont un script ────────────────────────
class GardeTroisLesTouchesDAppelOntUnScript(SimpleTestCase):
    #: Les cinq touches d'appel qui n'avaient AUCUN script avant CAD67/CAD98,
    #: repérées par (cadence par défaut, ordre, clé attendue).
    CINQ = (
        (CADENCE_CONTACT_DEFAUT, 6, 'repondeur'),          # Appel 4
        (CADENCE_CONTACT_DEFAUT, 10, 'appel_dernier'),     # Appel 6
        (CADENCE_APRES_DEVIS_DEFAUT, 2, 'appel_suivi_j2'),
        (CADENCE_APRES_DEVIS_DEFAUT, 6, 'appel_suivi_j7'),
        (CADENCE_APRES_DEVIS_DEFAUT, 8, 'appel_suivi_j11'),
    )

    def test_les_cinq_touches_portent_leur_cle_non_vide(self):
        self.assertEqual(len(self.CINQ), 5)
        for cadence, ordre, cle in self.CINQ:
            etape = next(e for e in cadence if e['ordre'] == ordre)
            with self.subTest(cle=cle):
                self.assertEqual(etape['canal'], CanalRelance.APPEL)
                self.assertTrue(etape['template_cle'])
                self.assertEqual(etape['template_cle'], cle)
                self.assertTrue(MESSAGE_TEMPLATE_DEFAULTS.get(cle), cle)

    def test_toute_touche_d_appel_des_cadences_par_defaut_a_un_script(self):
        for cadence in (CADENCE_CONTACT_DEFAUT, CADENCE_APRES_DEVIS_DEFAUT,
                        CADENCE_REVEIL_DEFAUT,
                        CADENCE_DEUXIEME_AFFAIRE_DEFAUT):
            for etape in cadence:
                if etape['canal'] != CanalRelance.APPEL:
                    continue
                with self.subTest(libelle=etape['libelle']):
                    self.assertTrue(etape['template_cle'])
                    self.assertTrue(
                        MESSAGE_TEMPLATE_DEFAULTS.get(etape['template_cle']))


# ── Garde 4 — le contrat a la forme de la réponse réelle ────────────────────
def _touche_factice():
    return SimpleNamespace(
        pk=1287, ordre=3, template_cle='appel_suivi_j2', canal='appel',
        statut='a_faire', due_date=datetime.date(2026, 9, 23), due_at=None)


def _rendu_factice(*args, **kwargs):
    return {'message': 'Bonjour.', 'langue': 'fr',
            'placeholders_manquants': [], 'wa_url': 'https://wa.me/1'}


class GardeQuatreLeContratEstLaReponse(SimpleTestCase):
    def _panneau(self, lead, touche=None):
        # Le moteur d'horaires lit la base (profil société, jours ouvrés) :
        # il est simulé ici — sa forme est gardée par CAD155.
        with mock.patch.object(panneau, '_touche_en_cours',
                               return_value=touche), \
                mock.patch('apps.crm.services.message_pour_etape',
                           side_effect=_rendu_factice), \
                mock.patch('apps.crm.horaires.fenetre_du_jour',
                           return_value=None), \
                mock.patch('apps.crm.horaires.est_en_ramadan',
                           return_value=False):
            return panneau.panneau_appel(lead)

    def test_sans_touche_la_racine_est_celle_de_l_exemple_sans_cadence(self):
        data = self._panneau(_lead(type_installation='agricole'))
        self.assertEqual(set(data),
                         set(CONTRAT['exemple_sans_cadence_active']))
        self.assertIsNone(data['touche'])
        self.assertIsNone(data['script'])

    def test_avec_touche_racine_touche_et_script_ont_la_forme_de_l_exemple(self):
        data = self._panneau(_lead(type_installation='residentiel'),
                             touche=_touche_factice())
        exemple = CONTRAT['exemple']
        self.assertEqual(set(data), set(exemple))
        self.assertEqual(set(data['touche']), set(exemple['touche']))
        self.assertEqual(set(data['script']), set(exemple['script']))
        self.assertNotIn('wa_url', data['script'])

    def test_chaque_question_et_chaque_equipement_ont_la_forme_de_l_exemple(self):
        data = self._panneau(_lead(type_installation='residentiel'))
        cles_question = set(CONTRAT['exemple']['champs_a_poser'][0])
        cles_equipement = set(CONTRAT['exemple']['equipements'][0])
        self.assertTrue(data['champs_a_poser'])
        for question in data['champs_a_poser']:
            self.assertEqual(set(question), cles_question, question['champ'])
        self.assertEqual(
            [e['cle'] for e in data['equipements']],
            [e['cle'] for e in CONTRAT['exemple']['equipements']])
        for equipement in data['equipements']:
            self.assertEqual(set(equipement), cles_equipement)

    def test_tous_les_exemples_du_contrat_ont_la_meme_racine(self):
        """Une variante décrit un autre ÉTAT du serveur, jamais une autre
        forme (règle des échantillons PACT10)."""
        racines = {nom: set(valeur) for nom, valeur in CONTRAT.items()
                   if nom.startswith('exemple')}
        self.assertGreaterEqual(len(racines), 3)
        self.assertEqual(len({frozenset(r) for r in racines.values()}), 1,
                         racines)


class LEndpointReelSuitLeContrat(TestCase):
    """La réponse HTTP RÉELLE a la forme de l'exemple committé (CI)."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD153 Co',
                                              slug='cad153-co')
        self.lead = Lead.objects.create(
            company=self.company, nom='Prospect',
            type_installation=Lead.TypeInstallation.RESIDENTIEL,
            facture_hiver=Decimal('900.00'))
        RelanceEtape.objects.create(
            company=self.company, lead=self.lead, ordre=1,
            due_date='2026-09-23', canal=RelanceEtape.Canal.APPEL,
            template_cle='appel_suivi_j2', statut=RelanceEtape.Statut.A_FAIRE)
        from django.contrib.auth import get_user_model
        # Même utilisateur que la garde d'endpoint de CAD148.
        self.user = get_user_model().objects.create_user(
            username='cad153-co', password='x', company=self.company,
            is_staff=True, is_superuser=True)

    def test_la_reponse_http_a_la_forme_du_contrat(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        res = client.get(
            f'/api/django/crm/leads/{self.lead.pk}/panneau-appel/')
        self.assertEqual(res.status_code, 200, res.content)
        corps = res.json()
        exemple = CONTRAT['exemple']
        self.assertEqual(set(corps), set(exemple))
        self.assertEqual(set(corps['touche']), set(exemple['touche']))
        self.assertEqual(set(corps['script']), set(exemple['script']))
        for question in corps['champs_a_poser']:
            self.assertEqual(set(question),
                             set(exemple['champs_a_poser'][0]))
        # Garde 1, bout en bout : la facture répondue n'est pas reposée.
        self.assertNotIn('facture_hiver', _champs(corps['champs_a_poser']))
        self.assertEqual(corps['prefill']['facture_hiver'], 900.0)
