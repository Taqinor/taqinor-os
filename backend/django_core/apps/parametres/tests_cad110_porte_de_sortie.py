"""CAD110 — Aucun message ne disait au client comment faire cesser les
relances.

Le seul « stop » du catalogue était la clé `stop_contact` — une RÉPONSE
envoyée APRÈS que le client a demandé l'arrêt, jamais une porte de sortie
OFFERTE. L'art. 10 al. 5 de la loi 09-08 conditionne l'exception de
prospection à une opposition possible « chaque fois qu'un courrier […] lui
est adressé » et à des coordonnées valables pour faire cesser — et l'envoi
manuel ne protège de rien : l'article vise le MOYEN employé et le
consentement, pas la main humaine.

Fix : une phrase courte et non commerciale (« Répondez STOP et je
n'insiste plus. ») dans les QUATRE familles de textes qui portent le plus
loin dans le suivi — J7 (`je_classe_j7`), J14 (`cloture_j14`), fin
d'après-devis (`j13_dernier`, `j14_pause`), et tous les réveils
(`reveil_a1`, `reveil_a2`, `reveil_a3`, `reveil_b`) — jamais les trois
premiers messages (garde-fou explicite de la tâche : ne pas alourdir le
début, c'est le suivi long qui expose).
"""
import pathlib
import re

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PLACEHOLDERS_RELANCE,
)

#: Les 4 familles / 8 clés que CAD110 complète.
CLES_PORTE_DE_SORTIE = [
    'je_classe_j7', 'cloture_j14',           # J7, J14
    'j13_dernier', 'j14_pause',              # fin d'après-devis
    'reveil_a1', 'reveil_a2', 'reveil_a3', 'reveil_b',  # tous les réveils
]

#: Les trois PREMIERS messages de la cadence contact — le garde-fou dit
#: explicitement de ne PAS les alourdir.
CLES_TROIS_PREMIERS = ['identite', 'appel_ouverture', 'repondeur']

_CROCHETS = [
    (r'\[Prénom\]', '{prenom}'),
    (r'\[prénom\]', '{prenom}'),
    (r'\[الاسم\]', '{prenom}'),
    (r'\[date\]', '{date_validite}'),
    (r'\[Conseiller\]', '{conseiller}'),
    (r'\[المستشار\]', '{conseiller}'),
]

_TOKEN_RE = re.compile(r'\{[^{}]*\}')


def _fichier_source():
    ici = pathlib.Path(__file__).resolve()
    for parent in ici.parents:
        candidat = parent / 'docs' / 'crm' / 'messages_meryem.md'
        if candidat.exists():
            return candidat
    raise AssertionError(
        'docs/crm/messages_meryem.md introuvable — source de vérité des '
        'textes de relance.')


def _convertir(texte):
    for motif, remplacement in _CROCHETS:
        texte = re.sub(motif, remplacement, texte)
    return texte


def _textes_source():
    lignes = _fichier_source().read_text(
        encoding='utf-8').replace('\r\n', '\n').split('\n')
    textes, cle = {}, None
    for ligne in lignes:
        if ligne.startswith('### '):
            cle = ligne[4:].split(' ')[0].strip()
            if cle in CLES_PORTE_DE_SORTIE:
                textes[cle] = {'fr': '', 'darija': ''}
            else:
                cle = None
        elif cle and ligne.startswith('FR : '):
            textes[cle]['fr'] = _convertir(ligne[5:].strip())
        elif cle and ligne.startswith('DARIJA : '):
            textes[cle]['darija'] = _convertir(ligne[9:].strip())
    return textes


class QuatreFamillesPortentLaMentionTests(SimpleTestCase):
    """LE Done : « les quatre familles de textes portent la mention en FR
    et en darija »."""

    MENTION_FR = 'STOP'

    def test_les_huit_cles_portent_stop_en_fr(self):
        for cle in CLES_PORTE_DE_SORTIE:
            with self.subTest(cle=cle):
                self.assertIn(self.MENTION_FR, MESSAGE_TEMPLATE_DEFAULTS[cle])

    def test_les_huit_cles_portent_stop_en_darija(self):
        for cle in CLES_PORTE_DE_SORTIE:
            with self.subTest(cle=cle):
                self.assertIn(
                    self.MENTION_FR, MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle])

    def test_toutes_les_cles_de_relance_sont_couvertes(self):
        for cle in CLES_PORTE_DE_SORTIE:
            self.assertIn(cle, CLES_RELANCE)


class TroisPremiersMessagesNonAlourdisTests(SimpleTestCase):
    """Garde-fou explicite : ne pas alourdir les trois premiers messages —
    c'est le suivi long qui expose."""

    def test_les_trois_premiers_ne_portent_pas_stop(self):
        for cle in CLES_TROIS_PREMIERS:
            with self.subTest(cle=cle):
                self.assertNotIn('STOP', MESSAGE_TEMPLATE_DEFAULTS[cle])

    def test_aucun_chevauchement_entre_les_deux_listes(self):
        self.assertEqual(
            set(CLES_PORTE_DE_SORTIE) & set(CLES_TROIS_PREMIERS), set())


class FideliteALaSourceTests(SimpleTestCase):
    """Les huit textes complétés COPIENT `docs/crm/messages_meryem.md`,
    jamais retapés — même discipline que `tests_mry12`."""

    def setUp(self):
        self.source = _textes_source()

    def test_la_source_porte_bien_les_huit_cles(self):
        self.assertEqual(sorted(self.source), sorted(CLES_PORTE_DE_SORTIE))

    def test_chaque_defaut_fr_est_le_texte_de_la_source(self):
        for cle in CLES_PORTE_DE_SORTIE:
            with self.subTest(cle=cle):
                attendu = self.source[cle]['fr']
                self.assertEqual(MESSAGE_TEMPLATE_DEFAULTS[cle], attendu)

    def test_chaque_defaut_darija_est_le_texte_de_la_source(self):
        for cle in CLES_PORTE_DE_SORTIE:
            with self.subTest(cle=cle):
                attendu = self.source[cle]['darija']
                obtenu = MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]
                self.assertEqual(obtenu, attendu)


class PlaceholdersEtDoctrineTests(SimpleTestCase):
    INTERDITS = ('Meryem', 'مريم', 'Reda', 'رضا')

    def test_aucun_placeholder_hors_liste_autorisee(self):
        autorises = set(PLACEHOLDERS_RELANCE)
        for cle in CLES_PORTE_DE_SORTIE:
            for texte in (MESSAGE_TEMPLATE_DEFAULTS[cle],
                          MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]):
                inconnus = [t for t in _TOKEN_RE.findall(texte)
                            if t not in autorises]
                self.assertEqual(inconnus, [])

    def test_aucun_prenom_code_en_dur(self):
        for cle in CLES_PORTE_DE_SORTIE:
            for texte in (MESSAGE_TEMPLATE_DEFAULTS[cle],
                          MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]):
                for mot in self.INTERDITS:
                    self.assertNotIn(mot, texte)
