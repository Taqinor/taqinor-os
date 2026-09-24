"""CALX292 — le contrat des sections du rapport d'étude tient debout.

Le contrat ``contract_samples/rapport_etude.json`` est la liste de sections
que l'assembleur du rapport (CALX297), les rédacteurs de section, le choix de
la société (CALX307), l'inventaire des documents (CALX321) et les libellés
FR/EN (CALX296) lisent tous. Ce qui est prouvé ici :

* chaque ``entrees_exigees`` se RÉSOUT dans l'exemple committé de
  ``calepinage_resultat.json`` — un chemin inventé, ou renommé côté résultat,
  rougit en le NOMMANT ;
* l'``ordre`` est STRICTEMENT croissant, et aucun ``code`` n'apparaît deux
  fois ;
* les dix codes attendus sont tous là, et chaque section porte les six clés ;
* le résolveur n'est pas complaisant : un chemin absent, une liste vide ou une
  valeur ``null`` ne se résolvent PAS (preuve que la garde peut rougir) ;
* le document ne porte aucune clé ni aucun mot de montant (D5).

Essais PURS : ni base, ni Django, ni WeasyPrint.

Run :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx292_contrat_rapport.py -q
"""
import json
import pathlib
import unittest

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLONS = RACINE_APP / 'contract_samples'


def _charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


CONTRAT = _charger('rapport_etude.json')
RESULTAT = _charger('calepinage_resultat.json')['exemple']

#: Les dix codes que la tâche DÉCLARE — ni plus, ni moins.
CODES_ATTENDUS = ('garde', 'site_meteo', 'systeme', 'pertes', 'production',
                  'ombrage', 'electrique', 'nomenclature', 'hypotheses',
                  'preuve')

CLES_SECTION = ('code', 'titre', 'ordre', 'obligatoire', 'entrees_exigees',
                'motif_si_absent')


def resout(source, chemin):
    """Vrai si ``chemin`` désigne une valeur PRÉSENTE dans ``source``.

    Grammaire du contrat : ``a.b.c`` = clé imbriquée ; suffixe ``[]`` = une
    LISTE NON VIDE ; ``null`` et chaîne vide = ABSENT (jamais un zéro).
    """
    liste = chemin.endswith('[]')
    courant = source
    for cle in (chemin[:-2] if liste else chemin).split('.'):
        if not isinstance(courant, dict) or cle not in courant:
            return False
        courant = courant[cle]
    if liste:
        return isinstance(courant, list) and bool(courant)
    if courant is None:
        return False
    return not (isinstance(courant, str) and not courant.strip())


class FormeDuContratTest(unittest.TestCase):
    def test_l_enveloppe_pact10_est_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, CONTRAT, f"clé « {cle} » absente du contrat")
        self.assertTrue(CONTRAT['endpoint'].startswith(
            'GET /api/django/calepinage/calepinages/<int:pk>/'))
        self.assertIsInstance(CONTRAT['exemple']['sections'], list)

    def test_les_dix_codes_sont_declares(self):
        codes = [s['code'] for s in CONTRAT['exemple']['sections']]
        self.assertEqual(sorted(codes), sorted(CODES_ATTENDUS))

    def test_chaque_section_porte_ses_six_cles(self):
        for section in CONTRAT['exemple']['sections']:
            with self.subTest(section=section.get('code')):
                self.assertEqual(sorted(section), sorted(CLES_SECTION))
                self.assertIsInstance(section['ordre'], int)
                self.assertIsInstance(section['obligatoire'], bool)
                self.assertIsInstance(section['entrees_exigees'], list)
                self.assertTrue(section['titre'].strip())
                # Une section absente n'est jamais imprimée VIDE : sa phrase
                # de motif existe, toujours.
                self.assertTrue(section['motif_si_absent'].strip())


class OrdreTest(unittest.TestCase):
    def test_l_ordre_est_strictement_croissant(self):
        ordres = [s['ordre'] for s in CONTRAT['exemple']['sections']]
        for precedent, suivant in zip(ordres, ordres[1:]):
            self.assertLess(
                precedent, suivant,
                f"ordre {suivant} après {precedent} : l'ordre d'impression "
                "doit être STRICTEMENT croissant dans la liste.")

    def test_aucun_code_en_double(self):
        codes = [s['code'] for s in CONTRAT['exemple']['sections']]
        self.assertEqual(len(codes), len(set(codes)),
                         f'code(s) en double : {codes}')


class EntreesExigeesTest(unittest.TestCase):
    def test_chaque_entree_exigee_se_resout_dans_le_resultat_committe(self):
        for section in CONTRAT['exemple']['sections']:
            for chemin in section['entrees_exigees']:
                with self.subTest(section=section['code'], chemin=chemin):
                    self.assertTrue(
                        resout(RESULTAT, chemin),
                        f"section « {section['code']} » : le chemin "
                        f"« {chemin} » ne se résout pas dans l'exemple de "
                        "contract_samples/calepinage_resultat.json — un "
                        "chemin inventé ou renommé.")

    def test_le_resolveur_peut_rougir(self):
        """Preuve que la garde n'est pas complaisante."""
        self.assertFalse(resout(RESULTAT, 'production.inexistant'))
        self.assertFalse(resout({'a': []}, 'a[]'))          # liste vide
        self.assertFalse(resout({'a': None}, 'a'))          # null
        self.assertFalse(resout({'a': '  '}, 'a'))          # chaîne vide
        self.assertFalse(resout({'a': {'b': 1}}, 'a[]'))    # pas une liste
        self.assertTrue(resout({'a': 0}, 'a'))  # zéro PRÉSENT reste présent


class AucunMontantTest(unittest.TestCase):
    MOTS = ('prix', 'cout', 'coût', 'marge', 'montant', 'remise', 'mad',
            'ttc')

    def test_aucune_cle_ni_aucun_mot_de_montant(self):
        texte = json.dumps(CONTRAT['exemple'], ensure_ascii=False).lower()
        for mot in self.MOTS:
            with self.subTest(mot=mot):
                self.assertNotRegex(texte, r'\b%s\b' % mot)


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
