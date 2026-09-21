"""CAD96 — une seule graphie de marque, et elle n'est JAMAIS codée en dur.

Avant : « TAQINOR Solutions » (identite, appel_ouverture), « TAQINOR » (neuf
autres touches) et « Taqinor Solutions » (les trois réveils) coexistaient dans
le même catalogue de messages — incohérence déjà présente dans le document
source validé (`docs/crm/messages_meryem.md`), pas une dérive du code.

Plutôt que de figer UNE de ces trois graphies dans le code (une future
société white-label hériterait du nom de TAQINOR — garde SCA29), la marque
est désormais `{marque}`, résolue côté serveur depuis
`parametres.CompanyProfile.nom` (`apps.crm.services._nom_affiche_marque`).
Ce module vérifie le CATALOGUE (aucune graphie littérale ne doit y
réapparaître) ; `tests_mry12_messages_relance.py` vérifie déjà la fidélité au
fichier source (re-dérivation) pour tous les textes, `{marque}` inclus.
"""
from django.test import SimpleTestCase

from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PLACEHOLDERS_RELANCE,
)

#: Les trois graphies qui coexistaient avant CAD96 — plus aucune ne doit
#: réapparaître dans un texte de la cadence (`CLES_RELANCE`).
GRAPHIES_INTERDITES = ('TAQINOR Solutions', 'Taqinor Solutions', 'TAQINOR',
                       'Taqinor')

#: Clés qui portaient effectivement une graphie avant la correction — sert de
#: garde anti-faux-vert (si cette liste devenait vide, le test ci-dessous
#: passerait à vide et ne prouverait plus rien).
CLES_AVEC_MARQUE_AVANT = (
    'identite', 'appel_ouverture', 'repondeur', 'vocal_j3', 'appel_dimanche',
    'je_classe_j7', 'cloture_j14', 'reveil_a2', 'dimanche_famille',
    'annonce_appel_reda', 'offre_reda', 'reveil_a1', 'reveil_a3', 'reveil_b',
)


class AucuneGraphieCodeeEnDurTests(SimpleTestCase):

    def test_les_cles_attendues_sont_bien_dans_cles_relance(self):
        """Anti-faux-vert : si cette liste divergeait de CLES_RELANCE, les
        tests ci-dessous ne couvriraient plus rien."""
        for cle in CLES_AVEC_MARQUE_AVANT:
            self.assertIn(cle, CLES_RELANCE)

    def test_aucun_defaut_fr_ne_code_une_graphie_de_marque_en_dur(self):
        for cle in CLES_RELANCE:
            texte = MESSAGE_TEMPLATE_DEFAULTS[cle]
            with self.subTest(cle=cle):
                for graphie in GRAPHIES_INTERDITES:
                    self.assertNotIn(
                        graphie, texte,
                        f'{cle} (FR) contient « {graphie} » en dur — '
                        'utiliser {marque}.')

    def test_aucun_defaut_darija_ne_code_une_graphie_de_marque_en_dur(self):
        for cle, texte in MESSAGE_TEMPLATE_DEFAULTS_DARIJA.items():
            with self.subTest(cle=cle):
                for graphie in GRAPHIES_INTERDITES:
                    self.assertNotIn(
                        graphie, texte,
                        f'{cle} (darija) contient « {graphie} » en dur — '
                        'utiliser {marque}.')

    def test_les_cles_qui_portaient_une_marque_utilisent_desormais_marque(self):
        for cle in CLES_AVEC_MARQUE_AVANT:
            with self.subTest(cle=cle):
                self.assertIn('{marque}', MESSAGE_TEMPLATE_DEFAULTS[cle])

    def test_marque_est_dans_la_liste_autorisee(self):
        self.assertIn('{marque}', PLACEHOLDERS_RELANCE)
