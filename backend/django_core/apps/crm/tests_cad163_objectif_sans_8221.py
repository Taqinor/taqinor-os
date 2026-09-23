"""CAD163 — conformité de la fiche : la loi 82-21 n'est jamais abordée
spontanément (décision fondateur du 21/09/2026, Q9).

La phrase autorisée vit UNIQUEMENT parmi les objections du script d'appel
(`appelGuidance.js`, liste `OBJECTIONS`) — elle n'est pas dupliquée ici. Ce
qui restait, c'est la fiche du lead : le texte d'aide d'`objectif_projet` (la
question posée À L'APPEL) faisait proposer « injecter le surplus ? », et le
libellé du choix nommait « (loi 82-21) ».

Verrouillé ici :

  * la VALEUR `injection_8221` est inchangée (données, webhooks, questionnaire) ;
  * ni le libellé ni la question ne nomment la loi ;
  * la question posée à l'appel ne propose plus le surplus ;
  * les deux textes sont documentés, marqués ✎, dans `docs/crm/messages_meryem.md`.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.crm.models import Lead

MESSAGES = (Path(__file__).resolve().parents[4] / 'docs' / 'crm'
            / 'messages_meryem.md').read_text(encoding='utf-8')


def _champ():
    return Lead._meta.get_field('objectif_projet')


def _question(help_text):
    """La question orale, entre « … », au début du texte d'aide."""
    trouve = re.search(r'«(.*?)»', help_text)
    return trouve.group(1) if trouve else ''


class ObjectifSansLoiSpontaneeTests(SimpleTestCase):

    def test_la_valeur_est_inchangee(self):
        valeurs = [v for v, _ in _champ().choices]
        self.assertIn('injection_8221', valeurs)
        self.assertEqual(Lead.ObjectifProjet.INJECTION_8221.value,
                         'injection_8221')

    def test_le_libelle_ne_nomme_plus_la_loi(self):
        libelle = Lead.ObjectifProjet.INJECTION_8221.label
        self.assertNotIn('82-21', libelle)
        self.assertNotIn('loi', libelle.lower())
        self.assertIn('si le client en parle', libelle)

    def test_la_question_de_l_appel_ne_propose_plus_le_surplus(self):
        texte = _champ().help_text
        self.assertTrue(texte.startswith("Question à l'appel"))
        question = _question(texte)
        self.assertTrue(question, 'question introuvable dans le texte d’aide')
        self.assertNotIn('surplus', question.lower())
        self.assertNotIn('82-21', texte)
        self.assertNotIn('loi', texte.lower())

    def test_la_regle_est_dite_a_la_commerciale(self):
        self.assertIn('ne se coche QUE si le client en parle',
                      _champ().help_text)

    def test_les_textes_sont_documentes_et_marques_a_valider(self):
        debut = MESSAGES.index('#### objectif_projet — ')
        section = MESSAGES[debut:].split('\n## ', 1)[0]
        self.assertIn('✎', section)
        self.assertIn(Lead.ObjectifProjet.INJECTION_8221.label, section)
        self.assertIn(_question(_champ().help_text).strip(), section)
