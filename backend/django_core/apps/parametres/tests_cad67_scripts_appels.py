"""CAD67 — Le script « répondeur » partait deux fois en ~20 h, et deux
appels de la cadence contact n'avaient aucune phrase d'ouverture.

Avant CAD67 : ``template_cle='repondeur'`` était posé sur l'« Appel 2
(répondeur) » (ordre 3, J0+150 min) ET sur l'« Appel 3 (répondeur) »
(ordre 4, J1 10:30) — alors que le document source (``docs/crm/
messages_meryem.md``) réserve ``repondeur`` aux appels 2 et 4. L'« Appel 4 »
(ordre 6) et l'« Appel 6 (dernier) » (ordre 10) portaient ``template_cle``
vide : Meryem n'avait aucune phrase d'ouverture pour le DERNIER appel,
celui qui décide du classement du lead.

Fix : ``repondeur`` reste sur l'ordre 3, se déplace de l'ordre 4 vers
l'ordre 6 (espace les deux répondeurs de ~2 jours au lieu de ~20 h) ;
l'ordre 4 reçoit son propre script (``appel_relance``) et l'ordre 10 le
sien (``appel_dernier``), sur le patron des scripts d'appel existants
(``appel_ouverture``, ``vocal_j3``, ``appel_dimanche``).

Garde-fou : aucun barreau ajouté, retiré ou déplacé — mêmes ``ordre``,
mêmes ``delai_jours``/``delai_minutes``/``heure_cible``, même ``canal``.
"""
import datetime

from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PLACEHOLDERS_RELANCE, MessageTemplate,
)
from apps.parametres.models_relance import (
    CADENCE_CONTACT_DEFAUT, CanalRelance,
)

#: Barreaux d'ordre 3/4/6/10 AVANT CAD67 (référence figée pour prouver que
#: seules les clés de gabarit ont changé — jamais l'ordre, le jour ou le
#: canal).
_ORDRES_AVANT = {
    3: {'delai_jours': 0, 'delai_minutes': 150, 'heure_cible': None,
        'canal': CanalRelance.APPEL},
    4: {'delai_jours': 1, 'delai_minutes': 0,
        'heure_cible': datetime.time(10, 30), 'canal': CanalRelance.APPEL},
    6: {'delai_jours': 2, 'delai_minutes': 0,
        'heure_cible': datetime.time(18, 0), 'canal': CanalRelance.APPEL},
    10: {'delai_jours': 10, 'delai_minutes': 0,
         'heure_cible': datetime.time(15, 0), 'canal': CanalRelance.APPEL},
}


def _par_ordre():
    return {e['ordre']: e for e in CADENCE_CONTACT_DEFAUT}


class BarreauxInchangesTests(SimpleTestCase):
    """Aucun barreau ajouté/retiré/déplacé — seules les clés de gabarit
    changent (garde-fou explicite de la tâche)."""

    def test_meme_nombre_de_barreaux(self):
        self.assertEqual(len(CADENCE_CONTACT_DEFAUT), 11)

    def test_ordre_jour_canal_inchanges_pour_les_barreaux_touches(self):
        par_ordre = _par_ordre()
        for ordre, attendu in _ORDRES_AVANT.items():
            with self.subTest(ordre=ordre):
                entree = par_ordre[ordre]
                jours, minutes = attendu['delai_jours'], attendu['delai_minutes']
                self.assertEqual(entree['delai_jours'], jours)
                self.assertEqual(entree['delai_minutes'], minutes)
                self.assertEqual(entree['heure_cible'], attendu['heure_cible'])
                self.assertEqual(entree['canal'], attendu['canal'])


class AucunAppelSansScriptTests(SimpleTestCase):
    """LE Done de CAD67 : aucune touche d'appel de la cadence contact n'a de
    ``template_cle`` vide."""

    def test_aucune_touche_appel_nest_sans_script(self):
        for entree in CADENCE_CONTACT_DEFAUT:
            if entree['canal'] != CanalRelance.APPEL:
                continue
            ordre, libelle = entree['ordre'], entree['libelle']
            with self.subTest(ordre=ordre, libelle=libelle):
                message = f"ordre {ordre} ({libelle}) n'a aucun script d'ouverture."
                self.assertTrue(entree['template_cle'].strip(), message)


class RepondeurBienEspaceTests(SimpleTestCase):
    """LE Done de CAD67 : ``repondeur`` n'apparaît pas deux fois en moins de
    24 h — et suit le document (appels 2 et 4, pas 2 et 3)."""

    def _minutes_depuis_depart(self, entree):
        heure = entree['heure_cible']
        minutes_du_jour = (heure.hour * 60 + heure.minute) if heure else \
            entree['delai_minutes']
        return entree['delai_jours'] * 24 * 60 + minutes_du_jour

    def test_repondeur_sur_exactement_deux_barreaux(self):
        repondeurs = [e for e in CADENCE_CONTACT_DEFAUT
                      if e['template_cle'] == 'repondeur']
        self.assertEqual(len(repondeurs), 2)

    def test_repondeur_est_sur_les_ordres_3_et_6(self):
        """Les libellés le disent : « Appel 2 » (ordre 3) et « Appel 4 »
        (ordre 6) — le document réserve `repondeur` à ces deux-là."""
        repondeurs = [e for e in CADENCE_CONTACT_DEFAUT
                      if e['template_cle'] == 'repondeur']
        ordres = sorted(e['ordre'] for e in repondeurs)
        self.assertEqual(ordres, [3, 6])

    def test_repondeur_najamais_moins_de_24h_decart(self):
        repondeurs = [e for e in CADENCE_CONTACT_DEFAUT
                      if e['template_cle'] == 'repondeur']
        instants = sorted(self._minutes_depuis_depart(e) for e in repondeurs)
        for avant, apres in zip(instants, instants[1:]):
            self.assertGreaterEqual(
                apres - avant, 24 * 60,
                'deux messages repondeur a moins de 24h l\'un de l\'autre.')

    def test_ordre_4_ne_porte_plus_repondeur(self):
        """Anti-faux-vert : avant CAD67, l'ordre 4 portait `repondeur` — ce
        test échouerait sur le code d'avant le correctif."""
        par_ordre = _par_ordre()
        self.assertNotEqual(par_ordre[4]['template_cle'], 'repondeur')
        self.assertNotEqual(par_ordre[10]['template_cle'], '')


class NouvellesClesTests(SimpleTestCase):
    """`appel_relance` et `appel_dernier` existent, sont non vides, dans les
    deux langues, avec des placeholders autorisés et sans prénom en dur."""

    NOUVELLES_CLES = ['appel_relance', 'appel_dernier']
    INTERDITS = ('Meryem', 'مريم', 'Reda', 'رضا')

    def test_les_deux_cles_sont_dans_cles_relance(self):
        for cle in self.NOUVELLES_CLES:
            self.assertIn(cle, CLES_RELANCE)

    def test_les_deux_cles_sont_des_choix_du_modele(self):
        choix = {c for c, _ in MessageTemplate.Cle.choices}
        for cle in self.NOUVELLES_CLES:
            self.assertIn(cle, choix)

    def test_defauts_fr_et_darija_non_vides(self):
        for cle in self.NOUVELLES_CLES:
            with self.subTest(cle=cle):
                self.assertTrue(
                    (MESSAGE_TEMPLATE_DEFAULTS.get(cle) or '').strip())
                self.assertTrue(
                    (MESSAGE_TEMPLATE_DEFAULTS_DARIJA.get(cle) or '').strip())

    def test_les_cles_sont_bien_celles_posees_sur_les_barreaux(self):
        par_ordre = _par_ordre()
        self.assertEqual(par_ordre[4]['template_cle'], 'appel_relance')
        self.assertEqual(par_ordre[10]['template_cle'], 'appel_dernier')

    def test_aucun_prenom_code_en_dur(self):
        for cle in self.NOUVELLES_CLES:
            for texte in (MESSAGE_TEMPLATE_DEFAULTS[cle],
                          MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]):
                for mot in self.INTERDITS:
                    self.assertNotIn(mot, texte)

    def test_placeholders_autorises_seulement(self):
        import re
        token_re = re.compile(r'\{[^{}]*\}')
        autorises = set(PLACEHOLDERS_RELANCE)
        for cle in self.NOUVELLES_CLES:
            for texte in (MESSAGE_TEMPLATE_DEFAULTS[cle],
                          MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle]):
                inconnus = [t for t in token_re.findall(texte)
                            if t not in autorises]
                self.assertEqual(inconnus, [])
