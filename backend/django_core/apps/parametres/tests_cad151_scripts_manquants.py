"""CAD151 — Le débrief après le retour du technicien n'avait aucun script.

`apps.crm.services.reprendre_plan_apres_retour_visite` reprend la cadence
après-devis là où elle en était, et `composer_note_retour_visite` écrit le
compte-rendu dans l'historique du lead — mais rien ne guidait l'appel que le
responsable passe au client dans les 24-48 h qui suivent. Fix : un script
court, ENVOI MANUEL comme `annonce_appel_reda`/`offre_reda` (CAD60) — aucun
barreau de cadence ne le porte, et il n'en aura pas (le retour de visite
reprend déjà le barreau après-devis suivant).

Zéro chiffre, aucun crochet (il partirait tel quel), aucun prénom ni graphie
de marque codés en dur : l'expéditeur est ``{conseiller}``, la société
``{marque}``. La fidélité au fichier source
(``docs/crm/messages_meryem.md``) est gardée par
``tests_mry12_messages_relance.py`` pour TOUTES les clés de ``CLES_RELANCE``,
``debrief_visite`` comprise.

Ce lot ajoute aussi deux réponses d'objection (générateur, subventions) au
panneau d'appel guidé (``frontend/.../appelGuidance.js``) et leur section
source dans ``docs/crm/messages_meryem.md`` — hors du périmètre de ce fichier
de test Python (aucun gabarit `MessageTemplate` ne les porte, elles ne
partent jamais par écrit) : leur re-dérivation est gardée côté JS
(``appelGuidance.test.mjs``, section CAD151).
"""
import re

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    CLES_ENVOI_MANUEL, CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS,
    MESSAGE_TEMPLATE_DEFAULTS_DARIJA, PLACEHOLDERS_RELANCE, MessageTemplate,
)
from apps.parametres.models_relance import (
    CADENCE_APRES_DEVIS_DEFAUT, CADENCE_CONTACT_DEFAUT, CADENCE_REVEIL_DEFAUT,
)

CLE = 'debrief_visite'

_TOKEN_RE = re.compile(r'\{[^{}]*\}')


def _textes():
    yield CLE, 'fr', MESSAGE_TEMPLATE_DEFAULTS[CLE]
    yield CLE, 'darija', MESSAGE_TEMPLATE_DEFAULTS_DARIJA[CLE]


class LeScriptExisteTests(SimpleTestCase):
    """LE Done : le débrief a un script, en FR et en darija."""

    def test_la_cle_est_un_choix_du_modele(self):
        choix = {c for c, _ in MessageTemplate.Cle.choices}
        self.assertIn(CLE, choix)

    def test_la_cle_est_dans_cles_relance(self):
        self.assertIn(CLE, CLES_RELANCE)

    def test_la_cle_est_en_envoi_manuel(self):
        """Même doctrine que `annonce_appel_reda`/`offre_reda` (CAD60) :
        aucun barreau de cadence ne le déclenche."""
        self.assertIn(CLE, CLES_ENVOI_MANUEL)

    def test_defauts_fr_et_darija_non_vides(self):
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertTrue(texte.strip())

    def test_la_darija_nest_pas_une_copie_du_francais(self):
        self.assertNotEqual(MESSAGE_TEMPLATE_DEFAULTS[CLE],
                            MESSAGE_TEMPLATE_DEFAULTS_DARIJA[CLE])
        self.assertRegex(MESSAGE_TEMPLATE_DEFAULTS_DARIJA[CLE], r'[؀-ۿ]')


class AucunBarreauNAjouteTests(SimpleTestCase):
    """Garde-fou : le débrief n'ouvre, ne retire ni ne déplace un barreau."""

    def test_aucun_barreau_ne_porte_la_cle_debrief(self):
        toutes = (list(CADENCE_CONTACT_DEFAUT)
                  + list(CADENCE_APRES_DEVIS_DEFAUT)
                  + list(CADENCE_REVEIL_DEFAUT))
        cles = {e.get('template_cle', '') for e in toutes}
        self.assertNotIn(CLE, cles)

    def test_les_trois_cadences_gardent_leur_nombre_de_barreaux(self):
        self.assertEqual(len(CADENCE_CONTACT_DEFAUT), 11)
        self.assertEqual(len(CADENCE_APRES_DEVIS_DEFAUT), 10)
        self.assertEqual(len(CADENCE_REVEIL_DEFAUT), 2)


class ReglesDeContenuTests(SimpleTestCase):
    """Zéro chiffre, aucun crochet, aucun nom codé en dur — même patron que
    `tests_cad98_scripts_appels_suivi.py`."""

    PRENOMS_INTERDITS = ('Meryem', 'مريم', 'Reda', 'رضا')
    GRAPHIES_MARQUE = ('TAQINOR', 'Taqinor')
    #: Chiffres latins, arabes et arabes orientaux.
    CHIFFRE_RE = re.compile(r'[0-9٠-٩۰-۹]')
    NOMBRES_EN_LETTRES = ('deux', 'trois', 'quatre', 'cinq', 'dix', 'vingt',
                          'trente', 'cent', 'mille', 'جوج', 'تلاتة', 'خمس',
                          'عشر')

    def test_aucun_chiffre(self):
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertIsNone(self.CHIFFRE_RE.search(texte))
                mots = set(re.findall(r'\w+', texte.lower()))
                self.assertEqual(mots & set(self.NOMBRES_EN_LETTRES), set())

    def test_aucun_crochet(self):
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertNotIn('[', texte)
                self.assertNotIn(']', texte)

    def test_placeholders_autorises_seulement(self):
        autorises = set(PLACEHOLDERS_RELANCE)
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                inconnus = [t for t in _TOKEN_RE.findall(texte)
                            if t not in autorises]
                self.assertEqual(inconnus, [])

    def test_lexpediteur_et_la_societe_sont_des_variables(self):
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertIn('{conseiller}', texte)
                self.assertIn('{marque}', texte)

    def test_aucun_prenom_ni_graphie_de_marque_en_dur(self):
        for cle, langue, texte in _textes():
            for mot in self.PRENOMS_INTERDITS + self.GRAPHIES_MARQUE:
                with self.subTest(cle=cle, langue=langue, mot=mot):
                    self.assertNotIn(mot, texte)

    def test_pas_de_porte_de_sortie_stop_sur_un_appel(self):
        """CAD110 a posé « Répondez STOP » sur des messages ÉCRITS précis ;
        un script d'appel se dit à voix haute, il n'en porte pas."""
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertNotIn('STOP', texte)
