"""CIQ502 — la forme e-mail (objet + corps) des touches après devis et réveil.

Un acheteur B2B transmet un e-mail et sa pièce jointe à sa direction ou à sa
banque : les sept touches WhatsApp du suivi après devis et ``reveil_a2`` /
``reveil_a3`` ont donc une forme e-mail, NEUTRE de segment (un particulier
sur fixe avec e-mail la reçoit aussi), re-dérivée de
``docs/crm/messages_meryem.md`` (lignes ``E-MAIL OBJET : `` / ``E-MAIL : ``).
"""
import re

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_FORMES_EMAIL,
    PLACEHOLDERS_RELANCE, forme_email,
)
from apps.parametres.tests_cad126_variantes_segment import _guide
from apps.parametres.tests_mry12_messages_relance import _convertir

CLES_EMAIL = ('j1_pdf', 'dimanche_famille', 'j4_preuve', 'j6_garanties',
              'j9_validite', 'j13_dernier', 'j14_pause', 'reveil_a2',
              'reveil_a3')

#: Ce qu'une forme e-mail ne dit jamais : le canal WhatsApp et ses gestes,
#: le résidentiel (« famille », « toit », « chez vous »), et les mots interdits
#: aux textes B2B par CIQ501 — ces formes partent aussi aux pros sur fixe.
INTERDITS = ('WhatsApp', 'STOP', 'ici', 'famille', 'toit', 'chez vous',
             'comparable', '3D', 'une photo suffit', 'voisin', 'frère',
             'récompense')

_PLACEHOLDER = re.compile(r'\{\w+\}')


def _formes_du_guide():
    lignes = _guide().read_text(
        encoding='utf-8').replace('\r\n', '\n').split('\n')
    formes, cle = {}, None
    for ligne in lignes:
        if ligne.startswith('### '):
            cle = ligne[4:].split(' ')[0].strip()
            continue
        if not cle:
            continue
        if ligne.startswith('E-MAIL OBJET : '):
            formes.setdefault(cle, {})['objet'] = _convertir(
                ligne[len('E-MAIL OBJET : '):].strip())
        elif ligne.startswith('E-MAIL : '):
            formes.setdefault(cle, {})['corps'] = _convertir(
                ligne[len('E-MAIL : '):].strip())
    return formes


class FormesEmailTests(SimpleTestCase):
    def test_a_chaque_cle_a_un_objet_et_un_corps(self):
        self.assertEqual(set(MESSAGE_TEMPLATE_FORMES_EMAIL), set(CLES_EMAIL))
        for cle in CLES_EMAIL:
            forme = forme_email(cle)
            with self.subTest(cle=cle):
                self.assertIsNotNone(forme)
                self.assertTrue(forme['objet'].strip())
                self.assertTrue(forme['corps'].strip())
                self.assertIn(cle, MESSAGE_TEMPLATE_DEFAULTS)

    def test_b_aucun_mot_interdit_ni_chiffre_hors_placeholder(self):
        for cle, forme in MESSAGE_TEMPLATE_FORMES_EMAIL.items():
            for champ in ('objet', 'corps'):
                texte = _PLACEHOLDER.sub('', forme[champ])
                for mot in INTERDITS:
                    with self.subTest(cle=cle, champ=champ, mot=mot):
                        self.assertNotIn(mot.lower(), texte.lower())
                with self.subTest(cle=cle, champ=champ, chiffre=True):
                    self.assertIsNone(re.search(r'\d', texte))

    def test_placeholders_autorises_seulement(self):
        autorises = set(PLACEHOLDERS_RELANCE)
        for cle, forme in MESSAGE_TEMPLATE_FORMES_EMAIL.items():
            for champ in ('objet', 'corps'):
                with self.subTest(cle=cle, champ=champ):
                    self.assertEqual(
                        [t for t in _PLACEHOLDER.findall(forme[champ])
                         if t not in autorises], [])

    def test_sortie_cad110_par_e_mail(self):
        for cle in ('j13_dernier', 'j14_pause', 'reveil_a2', 'reveil_a3'):
            with self.subTest(cle=cle):
                self.assertIn(
                    'si vous préférez ne plus être recontacté, répondez-le '
                    'simplement à cet e-mail',
                    forme_email(cle)['corps'].lower())

    def test_la_proposition_est_jointe(self):
        for cle in ('j1_pdf', 'j9_validite'):
            with self.subTest(cle=cle):
                self.assertIn('joint', forme_email(cle)['corps'])

    def test_objet_de_la_proposition(self):
        self.assertEqual(forme_email('j1_pdf')['objet'],
                         'Votre proposition {reference} — {marque}')

    def test_c_egalite_guide_dict(self):
        guide = _formes_du_guide()
        self.assertTrue(guide)  # anti-faux-vert : le parseur lit bien
        self.assertEqual(guide, MESSAGE_TEMPLATE_FORMES_EMAIL)

    def test_d_pas_de_forme_pour_le_vocal_ni_la_cadence_contact(self):
        for cle in ('vocal_j3', 'identite', 'valeur_j1', 'cle_inconnue'):
            with self.subTest(cle=cle):
                self.assertIsNone(forme_email(cle))

    def test_forme_email_rend_une_copie(self):
        forme = forme_email('j1_pdf')
        forme['objet'] = 'modifié'
        self.assertNotEqual(forme_email('j1_pdf')['objet'], 'modifié')
