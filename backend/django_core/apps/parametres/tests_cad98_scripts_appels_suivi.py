"""CAD98 — Les trois « Appel de suivi » du suivi après devis n'avaient aucun
script.

Avant CAD98 : les barreaux d'ordre 2 (J2), 6 (J7) et 8 (J11) de
``CADENCE_APRES_DEVIS_DEFAUT`` portaient ``template_cle=''`` — 30 % des
touches après devis ne donnaient à la commerciale ni question ni phrase
d'ouverture, alors que chaque appel de la cadence contact a son script
(``appel_ouverture``, ``appel_relance``, ``appel_dimanche``,
``appel_dernier``…).

Fix : trois scripts courts (``appel_suivi_j2``/``_j7``/``_j11``), FR et
darija, sur le patron de CAD67. Garde-fou : aucun barreau ajouté, retiré ni
déplacé — seules les trois clés de gabarit changent. Zéro chiffre, aucun
crochet (il partirait tel quel), aucun prénom ni graphie de marque codés en
dur : l'expéditeur est ``{conseiller}``, la société ``{marque}``.

La fidélité au fichier source (``docs/crm/messages_meryem.md``) est gardée
par ``tests_mry12_messages_relance.py`` pour TOUTES les clés de
``CLES_RELANCE``, ces trois-là comprises.
"""
import re

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PLACEHOLDERS_RELANCE, MessageTemplate,
)
from apps.parametres.models_relance import (
    CADENCE_APRES_DEVIS_DEFAUT, CRENEAU_APPEL, CanalRelance,
)

#: Barreau → clé attendue (le Done de la tâche).
CLES_PAR_ORDRE = {2: 'appel_suivi_j2', 6: 'appel_suivi_j7',
                  8: 'appel_suivi_j11'}
NOUVELLES_CLES = list(CLES_PAR_ORDRE.values())

#: Les trois barreaux AVANT CAD98 (référence figée) : seul `template_cle`
#: a le droit de changer.
_AVANT = {
    2: {'delai_jours': 2, 'delai_minutes': 0, 'heure_cible': CRENEAU_APPEL,
        'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi'},
    6: {'delai_jours': 7, 'delai_minutes': 0, 'heure_cible': CRENEAU_APPEL,
        'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi'},
    8: {'delai_jours': 11, 'delai_minutes': 0, 'heure_cible': CRENEAU_APPEL,
        'canal': CanalRelance.APPEL, 'libelle': 'Appel de suivi'},
}

_TOKEN_RE = re.compile(r'\{[^{}]*\}')


def _par_ordre():
    return {e['ordre']: e for e in CADENCE_APRES_DEVIS_DEFAUT}


def _textes():
    for cle in NOUVELLES_CLES:
        yield cle, 'fr', MESSAGE_TEMPLATE_DEFAULTS[cle]
        yield cle, 'darija', MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]


class LesTroisBarreauxPortentUneCleTests(SimpleTestCase):
    """LE Done : les trois barreaux portent une clé de gabarit."""

    def test_chaque_appel_de_suivi_porte_sa_cle(self):
        par_ordre = _par_ordre()
        for ordre, cle in CLES_PAR_ORDRE.items():
            with self.subTest(ordre=ordre):
                self.assertEqual(par_ordre[ordre]['template_cle'], cle)

    def test_aucun_appel_apres_devis_nest_sans_script(self):
        """Anti-faux-vert : ce test échoue sur le code d'avant CAD98 (trois
        appels à `template_cle` vide)."""
        for entree in CADENCE_APRES_DEVIS_DEFAUT:
            if entree['canal'] != CanalRelance.APPEL:
                continue
            with self.subTest(ordre=entree['ordre']):
                self.assertTrue(
                    entree['template_cle'].strip(),
                    f"ordre {entree['ordre']} ({entree['libelle']}) n'a "
                    "aucun script d'appel.")

    def test_trois_cles_distinctes(self):
        self.assertEqual(len(set(NOUVELLES_CLES)), 3)


class AucunBarreauNeBougeTests(SimpleTestCase):
    """Règle du groupe CAD : ni le nombre, ni l'ordre, ni le jour J+N."""

    def test_toujours_dix_barreaux(self):
        self.assertEqual(len(CADENCE_APRES_DEVIS_DEFAUT), 10)
        self.assertEqual(sorted(_par_ordre()), list(range(1, 11)))

    def test_jour_heure_canal_libelle_inchanges(self):
        par_ordre = _par_ordre()
        for ordre, attendu in _AVANT.items():
            for champ, valeur in attendu.items():
                with self.subTest(ordre=ordre, champ=champ):
                    self.assertEqual(par_ordre[ordre][champ], valeur)


class LesTextesExistentTests(SimpleTestCase):
    """LE Done : les textes existent en FR et en darija."""

    def test_les_cles_sont_dans_cles_relance(self):
        for cle in NOUVELLES_CLES:
            self.assertIn(cle, CLES_RELANCE)

    def test_les_cles_sont_des_choix_du_modele(self):
        choix = {c for c, _ in MessageTemplate.Cle.choices}
        for cle in NOUVELLES_CLES:
            self.assertIn(cle, choix)

    def test_defauts_fr_et_darija_non_vides(self):
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertTrue(texte.strip())

    def test_la_darija_nest_pas_une_copie_du_francais(self):
        for cle in NOUVELLES_CLES:
            with self.subTest(cle=cle):
                self.assertNotEqual(MESSAGE_TEMPLATE_DEFAULTS[cle],
                                    MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle])
                self.assertRegex(MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle],
                                 r'[؀-ۿ]')


class ReglesDeContenuTests(SimpleTestCase):
    """Zéro chiffre, aucun crochet, aucun nom codé en dur."""

    PRENOMS_INTERDITS = ('Meryem', 'مريم', 'Reda', 'رضا')
    GRAPHIES_MARQUE = ('TAQINOR', 'Taqinor')
    #: Chiffres latins, arabes et arabes orientaux.
    CHIFFRE_RE = re.compile(r'[0-9٠-٩۰-۹]')
    #: Nombres écrits en toutes lettres (un script d'appel ne promet aucun
    #: délai ni aucune durée chiffrée).
    NOMBRES_EN_LETTRES = ('deux', 'trois', 'quatre', 'cinq', 'dix', 'vingt',
                          'trente', 'cent', 'mille', 'جوج', 'تلاتة', 'خمس',
                          'عشر')

    def test_aucun_chiffre(self):
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertIsNone(self.CHIFFRE_RE.search(texte))
                mots = set(re.findall(r'\w+', texte.lower()))
                self.assertEqual(
                    mots & set(self.NOMBRES_EN_LETTRES), set())

    def test_aucun_crochet(self):
        """Un crochet partirait tel quel : rien n'est à remplir à la main."""
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
        """CAD110 a posé « Répondez STOP » sur huit messages ÉCRITS précis ;
        un script d'appel se dit à voix haute, il n'en porte pas."""
        for cle, langue, texte in _textes():
            with self.subTest(cle=cle, langue=langue):
                self.assertNotIn('STOP', texte)
