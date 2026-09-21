"""CAD62 — Zéro darija sur la marche après-devis : le repli en français
n'est plus silencieux.

Avant CAD62, `MESSAGE_TEMPLATE_DEFAULTS_DARIJA` ne couvrait que 16 des 27
clés de `CLES_RELANCE` — il manquait les 6 touches scriptées du suivi de
proposition (`j1_pdf`, `j4_preuve`, `j6_garanties`, `j9_validite`,
`j13_dernier`, `j14_pause`), les deux réveils dormants + saison
(`reveil_a1`, `reveil_a3`, `reveil_b`) et l'après-signature (`avis_google`,
`parrainage`). Un lead `langue_preferee='darija'` recevait donc tout le
suivi de proposition en français, silencieusement, exactement au moment où
l'argent se décide.

Ce fichier verrouille : (1) la garde du Done — aucune clé FR de
`CLES_RELANCE` n'est sans équivalent darija ; (2) les 11 clés comblées sont
bien présentes, non vides, et fidèles au fichier source
`docs/crm/messages_meryem.md` (même patron de re-dérivation que
`tests_mry12_messages_relance.py`) ; (3) aucune n'ajoute un placeholder ou
un prénom codé en dur hors de la doctrine ; (4) `get_corps` sert bien le
défaut darija pour ces 11 clés en l'absence de toute ligne enregistrée.

Ces 11 traductions n'ont PAS encore reçu la relecture native du 04/09/2026
(CADM1, comme `visite_proposition`/`visite_confirmation`) — ce fichier ne
prétend pas le contraire, il verrouille seulement la couverture et la
fidélité à la source.
"""
import pathlib
import re

from django.test import SimpleTestCase, TestCase

from authentication.models import Company

from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PLACEHOLDERS_RELANCE, MessageTemplate,
)

#: Les 11 clés que CAD62 comble (Done de la tâche).
CLES_CAD62 = [
    'j1_pdf', 'j4_preuve', 'j6_garanties', 'j9_validite', 'j13_dernier',
    'j14_pause', 'reveil_a1', 'reveil_a3', 'reveil_b', 'avis_google',
    'parrainage',
]

#: Même table de conversion crochet → placeholder que
#: `tests_mry12_messages_relance.py` (dictée par l'en-tête du fichier
#: source) — re-dérivée ici pour ne dépendre d'aucun import croisé entre
#: fichiers de test.
_CROCHETS = [
    (r'\[Prénom\]', '{prenom}'),
    (r'\[prénom\]', '{prenom}'),
    (r'\[الاسم\]', '{prenom}'),
    (r'\[date de la visite\]', '{date_visite}'),
    (r'\[تاريخ الزيارة\]', '{date_visite}'),
    (r'\[date\]', '{date_validite}'),
    (r'\[référence\]', '{reference}'),
    (r'\[المرجع\]', '{reference}'),
    (r'\[lien preuve\]', '{lien_preuve}'),
    (r'\[puissance preuve\]', '{puissance_preuve}'),
    # CAD71 (21/09/2026) — le lien de la fiche Google n'est PAS le lien du
    # devis : placeholder dédié {lien_google} (`CompanyProfile.lien_avis_google`).
    (r'\[lien de la fiche TAQINOR\]', '{lien_google}'),
    (r'\[lien de votre proposition\]', '{lien}'),
    (r'\[mois\]', '{mois_preuve}'),
    (r'\[ville\]', '{ville_preuve}'),
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


def _darija_valides():
    """`{cle: texte_darija}` re-dérivé de `docs/crm/messages_meryem.md`,
    uniquement pour les clés qui y portent une ligne ``DARIJA :``."""
    lignes = _fichier_source().read_text(
        encoding='utf-8').replace('\r\n', '\n').split('\n')
    textes, cle = {}, None
    for ligne in lignes:
        if ligne.startswith('### '):
            cle = ligne[4:].split(' ')[0].strip()
        elif cle and ligne.startswith('DARIJA : '):
            textes[cle] = _convertir(ligne[9:].strip())
    return textes


class CouvertureDarijaCompleteTests(SimpleTestCase):
    """LA garde du Done de CAD62 : plus aucune clé FR de `CLES_RELANCE` sans
    équivalent darija."""

    def test_aucune_cle_fr_nest_sans_equivalent_darija(self):
        manquantes = [c for c in CLES_RELANCE
                      if c not in MESSAGE_TEMPLATE_DEFAULTS_DARIJA]
        self.assertEqual(
            manquantes, [],
            f'clé(s) sans repli darija : {manquantes} — un lead '
            'langue_preferee=darija recevrait du français silencieusement.')

    def test_les_27_cles_de_relance_ont_un_defaut_darija_non_vide(self):
        for cle in CLES_RELANCE:
            with self.subTest(cle=cle):
                self.assertTrue(
                    (MESSAGE_TEMPLATE_DEFAULTS_DARIJA.get(cle) or '').strip())

    def test_les_11_cles_cad62_sont_bien_les_clés_qui_manquaient(self):
        """Anti-faux-vert : si CAD62 n'avait rien ajouté, ce test échouerait
        (ces clés ne préexistaient pas dans le dictionnaire darija)."""
        for cle in CLES_CAD62:
            self.assertIn(cle, CLES_RELANCE)
            self.assertIn(cle, MESSAGE_TEMPLATE_DEFAULTS_DARIJA)


class FideliteALaSourceTests(SimpleTestCase):
    """Les 11 nouvelles clés ne sont pas retapées : elles COPIENT
    `docs/crm/messages_meryem.md`, comme les 16 qui existaient déjà."""

    def setUp(self):
        self.source = _darija_valides()

    def test_la_source_porte_bien_les_11_lignes_darija(self):
        for cle in CLES_CAD62:
            with self.subTest(cle=cle):
                message = (
                    f'{cle} : aucune ligne DARIJA dans '
                    'docs/crm/messages_meryem.md'
                )
                self.assertIn(cle, self.source, message)

    def test_chaque_defaut_darija_cad62_est_le_texte_de_la_source(self):
        for cle in CLES_CAD62:
            with self.subTest(cle=cle):
                attendu = self.source[cle]
                obtenu = MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]
                self.assertEqual(obtenu, attendu)


class DoctrineTests(SimpleTestCase):
    """Les gardes du groupe CAD s'appliquent aux 11 nouvelles clés comme aux
    autres : aucun placeholder inconnu, aucun prénom codé en dur."""

    INTERDITS = ('Meryem', 'مريم', 'Reda', 'رضا')

    def test_aucun_placeholder_hors_liste_autorisee(self):
        autorises = set(PLACEHOLDERS_RELANCE)
        for cle in CLES_CAD62:
            with self.subTest(cle=cle):
                inconnus = [t for t in
                            _TOKEN_RE.findall(
                                MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle])
                            if t not in autorises]
                self.assertEqual(inconnus, [])

    def test_aucun_prenom_code_en_dur(self):
        for cle in CLES_CAD62:
            with self.subTest(cle=cle):
                texte = MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]
                for mot in self.INTERDITS:
                    self.assertNotIn(mot, texte)

    def test_les_defauts_fr_correspondants_sont_inchanges(self):
        """CAD62 ne touche QUE le darija : les 11 défauts FR restent ceux
        déjà validés (garde de non-régression, cf. tests_mry12)."""
        for cle in CLES_CAD62:
            with self.subTest(cle=cle):
                self.assertTrue(
                    (MESSAGE_TEMPLATE_DEFAULTS.get(cle) or '').strip())


class GetCorpsCad62Tests(TestCase):
    """`get_corps` sert le nouveau défaut darija sans aucune ligne
    enregistrée. Non exécutable sur cet hôte (pas de base) — écrit avec
    soin, la CI est le juge."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD62', slug='cad62')

    def test_defaut_darija_sort_pour_chaque_cle_cad62_sans_aucune_ligne(self):
        for cle in CLES_CAD62:
            with self.subTest(cle=cle):
                self.assertEqual(
                    MessageTemplate.get_corps(self.company, cle, 'darija'),
                    MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle])

    def test_darija_maison_prime_sur_le_defaut(self):
        MessageTemplate.objects.create(
            company=self.company, cle='j1_pdf',
            corps_fr='FR maison', corps_darija='DARIJA maison CAD62')
        self.assertEqual(
            MessageTemplate.get_corps(self.company, 'j1_pdf', 'darija'),
            'DARIJA maison CAD62')
