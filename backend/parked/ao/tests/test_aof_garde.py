"""AOF139 — le sommaire est une PROJECTION du manifeste, pas une liste tapée.

Quatre promesses :
  1. ajouter une pièce au manifeste la fait apparaître au sommaire, renumérotée,
     sans qu'on touche au gabarit ;
  2. aucune pièce `interne` ou `directeur` ne peut entrer au sommaire ni au
     bordereau des pièces — même fournie explicitement ;
  3. en marque blanche, la page de garde porte le SOUMISSIONNAIRE et le bureau
     d'exécution n'apparaît nulle part ;
  4. ratchet d'étanchéité (AOF129) sur la pièce rendue.

Run :
    python manage.py test apps.ao.tests.test_aof_garde -v2
"""
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.ao.fabrique.rendus.garde_sommaire import (
    MOTS_INTERDITS, construire_bordereau_pieces, construire_sommaire,
    identite_de_garde, rendre_page_garde_html,
)

GABARIT = Path(settings.BASE_DIR) / 'templates' / 'ao' / 'page_garde.html'

BUREAU = {'raison_sociale': 'TAQINOR', 'ice': '000111222', 'rc': 'RC-1'}
PARTENAIRE = {'raison_sociale': 'ACCORDIA TECH', 'ice': '999888777',
              'identifiant_fiscal': 'IF-42', 'rc': 'RC-9',
              'adresse': 'Casablanca', 'telephone': '05 22 00 00 00'}


def manifeste_reel():
    return [
        {'code': '00', 'libelle': 'Checklist partenaire', 'ordre': 0,
         'visibilite': 'interne', 'format': 'docx', 'obligatoire': True,
         'presente': True, 'empreinte': 'f' * 64},
        {'code': '01', 'libelle': 'Lettre de soumission', 'ordre': 1,
         'visibilite': 'client', 'format': 'pdf', 'obligatoire': True,
         'presente': True, 'empreinte': '1' * 64, 'pages': 1},
        {'code': '02', 'libelle': 'Mémoire technique', 'ordre': 2,
         'visibilite': 'client', 'format': 'pdf', 'obligatoire': True,
         'presente': True, 'empreinte': '2' * 64, 'pages': 24},
        {'code': '04', 'libelle': 'Bordereau des prix', 'ordre': 4,
         'visibilite': 'client', 'format': 'pdf', 'obligatoire': True,
         'presente': True, 'empreinte': '4' * 64, 'pages': 6},
        {'code': '09', 'libelle': 'Rentabilité attendue (direction)',
         'ordre': 9, 'visibilite': 'directeur', 'format': 'xlsx',
         'obligatoire': False, 'presente': True, 'empreinte': '9' * 64},
    ]


def contexte(marque_blanche=True):
    return {
        'empreinte': 'c' * 64,
        'identite': {
            'marque_blanche': marque_blanche,
            'soumissionnaire': dict(PARTENAIRE),
            'bureau_execution': dict(BUREAU),
        },
        'marche': {'reference': 'AO-FRDISI-01', 'objet': 'Centrale PV',
                   'maitre_ouvrage': 'FRDISI',
                   'date_remise_plis': '2026-09-15'},
        'dates': {'generation': '2026-08-01'},
    }


class SommaireDeriveTest(SimpleTestCase):
    def test_la_numerotation_suit_l_ordre_du_manifeste(self):
        entrees, _ = construire_sommaire(manifeste_reel())
        self.assertEqual([e['numero'] for e in entrees], [1, 2, 3])
        self.assertEqual([e['code'] for e in entrees], ['01', '02', '04'])

    def test_une_piece_ajoutee_apparait_sans_intervention(self):
        manifeste = manifeste_reel()
        avant, _ = construire_sommaire(manifeste)
        manifeste.append({'code': '03', 'libelle': 'Note de calcul',
                          'ordre': 3, 'visibilite': 'client', 'format': 'pdf',
                          'obligatoire': True, 'presente': True,
                          'empreinte': '3' * 64, 'pages': 8})
        apres, _ = construire_sommaire(manifeste)
        self.assertEqual(len(apres), len(avant) + 1)
        self.assertEqual([e['code'] for e in apres],
                         ['01', '02', '03', '04'])
        # La renumérotation est recalculée, jamais héritée.
        self.assertEqual([e['numero'] for e in apres], [1, 2, 3, 4])
        html = rendre_page_garde_html(contexte(), manifeste)
        self.assertIn('Note de calcul', html)

    def test_l_etat_manquante_est_reserve_aux_pieces_obligatoires(self):
        manifeste = manifeste_reel()
        manifeste[1]['presente'] = False
        manifeste.append({'code': '07', 'libelle': 'Annexe facultative',
                          'ordre': 7, 'visibilite': 'client', 'format': 'pdf',
                          'obligatoire': False, 'presente': False,
                          'empreinte': ''})
        lignes = {ligne['code']: ligne
                  for ligne in construire_bordereau_pieces(manifeste)}
        self.assertEqual(lignes['01']['etat'], 'MANQUANTE')
        self.assertEqual(lignes['07']['etat'], 'non fournie')

    def test_l_empreinte_courte_identifie_la_version(self):
        lignes = {ligne['code']: ligne
                  for ligne in construire_bordereau_pieces(manifeste_reel())}
        self.assertEqual(lignes['02']['empreinte_courte'], '2' * 8)


class ExclusionStructurelleTest(SimpleTestCase):
    def test_aucune_piece_interne_ou_directeur_au_sommaire(self):
        entrees, exclues = construire_sommaire(manifeste_reel())
        codes = [e['code'] for e in entrees]
        self.assertNotIn('00', codes)
        self.assertNotIn('09', codes)
        self.assertEqual(sorted(e['visibilite'] for e in exclues),
                         ['directeur', 'interne'])

    def test_les_pieces_exclues_ne_sont_pas_nommees_dans_le_rendu(self):
        html = rendre_page_garde_html(contexte(), manifeste_reel())
        self.assertNotIn('Rentabilité attendue', html)
        self.assertNotIn('Checklist partenaire', html)

    def test_le_bordereau_des_pieces_applique_le_meme_filtre(self):
        codes = [ligne['code']
                 for ligne in construire_bordereau_pieces(manifeste_reel())]
        self.assertNotIn('09', codes)
        self.assertNotIn('00', codes)


class MarqueBlancheTest(SimpleTestCase):
    def test_la_garde_porte_le_partenaire_et_jamais_le_bureau(self):
        html = rendre_page_garde_html(contexte(marque_blanche=True),
                                      manifeste_reel())
        self.assertIn('ACCORDIA TECH', html)
        self.assertNotIn('TAQINOR', html)
        self.assertNotIn(BUREAU['ice'], html)
        self.assertNotIn(BUREAU['rc'], html)

    def test_hors_marque_blanche_l_identite_reste_celle_du_soumissionnaire(self):
        identite = identite_de_garde(contexte(marque_blanche=False))
        self.assertEqual(identite['raison_sociale'], 'ACCORDIA TECH')

    def test_marque_blanche_sans_soumissionnaire_refuse_de_se_rabattre(self):
        ctx = contexte(marque_blanche=True)
        ctx['identite']['soumissionnaire'] = {}
        with self.assertRaises(ValueError) as capture:
            identite_de_garde(ctx)
        self.assertIn('marque blanche', str(capture.exception).lower())


class GabaritEtEtancheiteTest(SimpleTestCase):
    def test_le_gabarit_ne_liste_aucune_piece_en_dur(self):
        source = GABARIT.read_text(encoding='utf-8')
        corps = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '',
                       source, flags=re.S)
        for grave in ('Lettre de soumission', 'Mémoire technique',
                      'Bordereau des prix', 'Note de calcul'):
            self.assertNotIn(grave, corps)

    def test_aucun_nombre_de_quatre_chiffres_hors_style(self):
        source = GABARIT.read_text(encoding='utf-8')
        corps = re.sub(r'<style>.*?</style>', '', source, flags=re.S)
        corps = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '',
                       corps, flags=re.S)
        self.assertEqual(
            re.findall(r'(?<![\w.-])\d{4,}(?![\w-])', corps), [])

    def test_un_libelle_de_cout_fait_refuser_le_rendu(self):
        manifeste = manifeste_reel()
        manifeste[1]['libelle'] = 'Lettre de soumission (marge incluse)'
        with self.assertRaises(ValueError) as capture:
            rendre_page_garde_html(contexte(), manifeste)
        self.assertIn('marge', str(capture.exception))

    def test_aucun_mot_interdit_dans_le_rendu(self):
        html = rendre_page_garde_html(contexte(), manifeste_reel()).lower()
        for mot in MOTS_INTERDITS:
            self.assertNotIn(mot, html)
