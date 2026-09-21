"""CAD109 — Le script d'appel ne disait ni que l'appel est commercial, ni
d'où viennent les données.

`appel_ouverture` donnait l'identité du conseiller et de la société, et
rien d'autre. Deux textes primaires (extraits mot pour mot au round 2)
demandent davantage :
  * loi 31-08 art. 51 — un démarchage téléphonique doit indiquer
    explicitement l'identité ET le caractère commercial de l'intervention
    (sanctionné par l'art. 180) ;
  * loi 09-08 art. 5 §3 + décret 2-09-165 art. 34 — pour des données NON
    collectées auprès de la personne (Meta, Odoo), l'information sur leur
    origine peut être donnée « par tous moyens », donc oralement.

Fix : une phrase courte ajoutée aux DEUX scripts d'appel EN DIRECT
(`appel_ouverture`, `appel_dimanche` — `repondeur`/`vocal_j3` restent des
scripts de répondeur/vocal, pas des ouvertures de conversation), re-dérivée
depuis `docs/crm/messages_meryem.md` (même discipline que
`tests_mry12_messages_relance.py`).
"""
import pathlib
import re

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PLACEHOLDERS_RELANCE,
)

#: Les deux scripts d'appel EN DIRECT que CAD109 complète.
CLES_APPEL_DIRECT = ['appel_ouverture', 'appel_dimanche']

_CROCHETS = [
    (r'\[Prénom\]', '{prenom}'),
    (r'\[prénom\]', '{prenom}'),
    (r'\[الاسم\]', '{prenom}'),
    (r'\[Conseiller\]', '{conseiller}'),
    (r'\[المستشار\]', '{conseiller}'),
    # CAD96 (fold post-merge, 21/09/2026) — le nom de marque, résolu côté
    # serveur (jamais une graphie codée en dur).
    (r'\[Marque\]', '{marque}'),
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
    """`{cle: {fr, darija}}` re-dérivé du fichier validé, pour les deux
    clés de ce test SEULEMENT (les autres crochets — dates, liens — ne sont
    pas convertis ici : hors de portée de CAD109)."""
    lignes = _fichier_source().read_text(
        encoding='utf-8').replace('\r\n', '\n').split('\n')
    textes, cle = {}, None
    for ligne in lignes:
        if ligne.startswith('### '):
            cle = ligne[4:].split(' ')[0].strip()
            if cle in CLES_APPEL_DIRECT:
                textes[cle] = {'fr': '', 'darija': ''}
            else:
                cle = None
        elif cle and ligne.startswith('FR : '):
            textes[cle]['fr'] = _convertir(ligne[5:].strip())
        elif cle and ligne.startswith('DARIJA : '):
            textes[cle]['darija'] = _convertir(ligne[9:].strip())
    return textes


class MentionAppelCommercialTests(SimpleTestCase):
    """LE Done : « les deux scripts d'appel portent la mention »."""

    MENTION = 'appel commercial'

    def test_les_deux_scripts_portent_la_mention_fr(self):
        for cle in CLES_APPEL_DIRECT:
            with self.subTest(cle=cle):
                self.assertIn(self.MENTION, MESSAGE_TEMPLATE_DEFAULTS[cle])

    def test_les_deux_scripts_portent_lorigine_des_coordonnees_fr(self):
        """loi 09-08 art. 5 §3 : où exercer le droit de savoir d'où
        viennent des données non collectées auprès de la personne."""
        for cle in CLES_APPEL_DIRECT:
            with self.subTest(cle=cle):
                self.assertIn("d'où viennent vos coordonnées",
                              MESSAGE_TEMPLATE_DEFAULTS[cle])

    def test_les_scripts_hors_perimetre_ne_sont_pas_touches(self):
        """`repondeur` (voicemail) et `vocal_j3` (note vocale WhatsApp) ne
        sont PAS des ouvertures de conversation en direct — hors Done."""
        for cle in ('repondeur', 'vocal_j3'):
            with self.subTest(cle=cle):
                self.assertNotIn(self.MENTION, MESSAGE_TEMPLATE_DEFAULTS[cle])


class FideliteALaSourceTests(SimpleTestCase):
    """Les deux scripts complétés COPIENT `docs/crm/messages_meryem.md`,
    jamais retapés."""

    def setUp(self):
        self.source = _textes_source()

    def test_la_source_porte_bien_les_deux_cles(self):
        self.assertEqual(sorted(self.source), sorted(CLES_APPEL_DIRECT))

    def test_chaque_defaut_fr_est_le_texte_de_la_source(self):
        for cle in CLES_APPEL_DIRECT:
            with self.subTest(cle=cle):
                attendu = self.source[cle]['fr']
                self.assertEqual(MESSAGE_TEMPLATE_DEFAULTS[cle], attendu)

    def test_chaque_defaut_darija_est_le_texte_de_la_source(self):
        for cle in CLES_APPEL_DIRECT:
            with self.subTest(cle=cle):
                attendu = self.source[cle]['darija']
                obtenu = MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]
                self.assertEqual(obtenu, attendu)


class PlaceholdersEtDoctrineTests(SimpleTestCase):
    INTERDITS = ('Meryem', 'مريم', 'Reda', 'رضا')

    def test_aucun_placeholder_hors_liste_autorisee(self):
        autorises = set(PLACEHOLDERS_RELANCE)
        for cle in CLES_APPEL_DIRECT:
            for texte in (MESSAGE_TEMPLATE_DEFAULTS[cle],
                          MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]):
                inconnus = [t for t in _TOKEN_RE.findall(texte)
                            if t not in autorises]
                self.assertEqual(inconnus, [])

    def test_aucun_prenom_code_en_dur(self):
        for cle in CLES_APPEL_DIRECT:
            for texte in (MESSAGE_TEMPLATE_DEFAULTS[cle],
                          MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]):
                for mot in self.INTERDITS:
                    self.assertNotIn(mot, texte)
