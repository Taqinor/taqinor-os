"""CAD60 — les deux textes de l'appel du fondateur partent À LA MAIN.

Constat de l'audit L3 du 21/09/2026 : ``annonce_appel_reda`` et ``offre_reda``
sont écrits, validés en FR et en darija, décrits dans le guide — et aucun des
10 barreaux après-devis ne les porte. Le grep du dépôt ne les trouve que dans
le catalogue et un test de texte. Personne ne sait qu'ils partent à la main.

Le remède RETENU n'est PAS un bouton conditionnel (sur-ingénierie :
``offre_reda`` contient trois blancs non calculables) : c'est de le DIRE, à
côté du texte, dans le catalogue et dans le guide. Ce module assert que la
mention y est — et que le câblage reste absent, volontairement.
"""
import pathlib
import re

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    CLES_ENVOI_MANUEL, CLES_RELANCE, MENTION_ENVOI_MANUEL,
    MESSAGE_TEMPLATE_DEFAULTS,
)
from apps.parametres.models_relance import CADENCES_DEFAUT

SOURCE_MESSAGES = (pathlib.Path(__file__).resolve().parent
                   / 'models_messages.py')


def _guide():
    """``docs/crm/messages_meryem.md``, remonté depuis ce fichier de test —
    même patron que ``tests_mry12_messages_relance`` (la profondeur du
    chemin ne se compte pas à la main : elle bouge)."""
    ici = pathlib.Path(__file__).resolve()
    for parent in ici.parents:
        candidat = parent / 'docs' / 'crm' / 'messages_meryem.md'
        if candidat.exists():
            return candidat
    raise AssertionError(
        "docs/crm/messages_meryem.md introuvable — c'est la SOURCE DE VÉRITÉ "
        'des textes de relance, elle ne peut pas disparaître.')


class LaMentionExisteTests(SimpleTestCase):
    def test_les_deux_cles_sont_declarees_a_envoi_manuel(self):
        # CAD151 (23/09/2026) a rejoint cette doctrine avec `debrief_visite`
        # (même raison : aucun barreau de cadence ne le porte) — verrouillé
        # par ailleurs par tests_cad151_scripts_manquants.py.
        self.assertEqual(CLES_ENVOI_MANUEL,
                         frozenset({'annonce_appel_reda', 'offre_reda',
                                   'debrief_visite'}))

    def test_elles_restent_des_cles_de_relance_a_part_entiere(self):
        """« Manuel » ne veut pas dire « absent du catalogue » : la
        commerciale doit pouvoir les copier."""
        for cle in CLES_ENVOI_MANUEL:
            with self.subTest(cle=cle):
                self.assertIn(cle, CLES_RELANCE)
                self.assertIn(cle, MESSAGE_TEMPLATE_DEFAULTS)

    def test_la_mention_dit_les_trois_choses_qui_comptent(self):
        mention = MENTION_ENVOI_MANUEL.lower()
        self.assertIn('manuel', mention)
        self.assertIn('hors cadence', mention)
        self.assertIn('fondateur', mention)

    def test_le_catalogue_porte_la_mention_A_COTE_du_texte(self):
        source = SOURCE_MESSAGES.read_text(encoding='utf-8')
        avant = source.split("'annonce_appel_reda':")[0]
        self.assertIn('CAD60', avant[-1200:])
        self.assertIn('hors cadence', avant[-1200:].lower())

    def test_le_guide_porte_la_mention_A_COTE_du_texte(self):
        guide = _guide().read_text(encoding='utf-8')
        avant = guide.split('### annonce_appel_reda')[0]
        self.assertIn('CAD60', avant[-1400:])
        self.assertIn('à la main', avant[-1400:].lower())


class AucunCablageTests(SimpleTestCase):
    def test_aucun_barreau_de_cadence_ne_porte_ces_cles(self):
        """Le constat de l'audit, verrouillé : si un futur run câblait une
        touche dessus, ce test le dirait."""
        for cadence, barreaux in CADENCES_DEFAUT.items():
            for barreau in barreaux:
                cle = barreau.get('template_cle', '')
                with self.subTest(cadence=cadence, ordre=barreau['ordre']):
                    self.assertNotIn(cle, CLES_ENVOI_MANUEL)

    def test_offre_reda_garde_ses_trois_blancs_NON_calculables(self):
        """La raison pour laquelle on ne câble pas : rien ne peut les
        remplir automatiquement, et un blanc envoyé au client est interdit."""
        texte = MESSAGE_TEMPLATE_DEFAULTS['offre_reda']
        blancs = re.findall(r'\[[^\]]+\]', texte)
        self.assertEqual(len(blancs), 3, blancs)
