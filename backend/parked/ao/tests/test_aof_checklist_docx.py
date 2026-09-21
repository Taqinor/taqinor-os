"""AOF138 — la checklist partenaire se rend en .docx éditable, ou dégrade.

Trois promesses :
  1. quand ``python-docx`` est là, un .docx VRAIMENT éditable sort (cases,
     colonnes vides à remplir, mention manuscrite) ;
  2. quand la bibliothèque est absente — le cas NORMAL tant que la ligne de
     dépendance n'est pas inscrite dans ``requirements.txt`` — le rendu ne
     casse pas : il dégrade en PDF marqué « pièce à fournir », donc la pièce
     est comptée NON produite plutôt que verte à tort ;
  3. le ratchet d'étanchéité (AOF129) couvre AUSSI le format DOCX : le texte
     réellement écrit dans le paquet OOXML est relu, pas seulement l'entrée.

Run :
    python manage.py test apps.ao.tests.test_aof_checklist_docx -v2
"""
from django.test import SimpleTestCase

from apps.ao.fabrique.rendus import checklist_docx as module
from apps.ao.fabrique.rendus.checklist_docx import (
    CASE_COCHEE, CASE_VIDE, FORMAT_DOCX, FORMAT_PDF_DEGRADE,
    MENTION_A_FOURNIR, docx_disponible, html_degrade, rendre_checklist,
    texte_du_docx,
)

IDENTITE = {'raison_sociale': 'ACCORDIA TECH'}
MARCHE = {'reference': 'AO-FRDISI-01', 'objet': 'Centrale PV',
          'date_remise_plis': '2026-09-15'}


def blocs_reels():
    """Les 7 blocs de la checklist réelle, en forme de lignes d'état."""
    return [
        {'code': 'CPS', 'titre': 'CPS', 'lignes': [
            {'libelle': 'Remplir les blancs du CPS', 'obligatoire': True,
             'cochee': False, 'responsable': '', 'commentaire': ''},
            {'libelle': 'Parapher chaque page', 'obligatoire': True,
             'cochee': False, 'responsable': '', 'commentaire': ''},
            {'libelle': "Mention manuscrite « lu et accepté »",
             'obligatoire': True, 'cochee': False, 'responsable': '',
             'commentaire': ''},
        ]},
        {'code': 'ACTE', 'titre': "Acte d'engagement", 'lignes': [
            {'libelle': 'Montants en chiffres et en lettres',
             'obligatoire': True, 'cochee': True, 'responsable': 'M. B.',
             'commentaire': ''},
            {'libelle': 'RIB et durée de validité', 'obligatoire': True,
             'cochee': False, 'responsable': '', 'commentaire': ''},
        ]},
        {'code': 'BORD', 'titre': 'Bordereau des prix', 'lignes': [
            {'libelle': "NE MODIFIER AUCUN PRIX NI AUCUNE QUANTITÉ",
             'obligatoire': True, 'cochee': False, 'responsable': '',
             'commentaire': ''},
        ]},
        {'code': 'LETTRE', 'titre': 'Lettre de soumission', 'lignes': [
            {'libelle': 'Report de la clause de réserve', 'obligatoire': True,
             'cochee': False, 'responsable': '', 'commentaire': ''},
        ]},
        {'code': 'MEM', 'titre': 'Mémoire technique', 'lignes': [
            {'libelle': 'Bloc signature et attestations de bonne exécution',
             'obligatoire': True, 'cochee': False, 'responsable': '',
             'commentaire': ''},
        ]},
        {'code': 'ADM', 'titre': 'Dossier administratif', 'lignes': [
            {'libelle': 'Attestation fiscale de moins d’un an',
             'obligatoire': True, 'cochee': False, 'responsable': '',
             'commentaire': ''},
            {'libelle': 'CNSS de moins de trois mois', 'obligatoire': True,
             'cochee': False, 'responsable': '', 'commentaire': ''},
            {'libelle': 'Caution provisoire', 'obligatoire': True,
             'cochee': False, 'responsable': '', 'commentaire': ''},
        ]},
        {'code': 'TEL', 'titre': 'Vérifications avant dépôt', 'lignes': [
            {'libelle': 'Prorogation écrite', 'obligatoire': False,
             'cochee': False, 'responsable': '', 'commentaire': ''},
            {'libelle': 'Plis séparés ou pli unique', 'obligatoire': True,
             'cochee': False, 'responsable': '', 'commentaire': ''},
        ]},
    ]


class DegradationTest(SimpleTestCase):
    """La voie qui s'exécute tant que la dépendance n'est pas inscrite."""

    def test_sans_la_bibliotheque_le_rendu_degrade_et_se_declare(self):
        html = html_degrade(blocs_reels(), IDENTITE, MARCHE)
        self.assertIn(MENTION_A_FOURNIR, html)
        # La pièce ne se fait JAMAIS passer pour la version définitive.
        self.assertIn('à fournir', MENTION_A_FOURNIR.lower())

    def test_le_repli_porte_toutes_les_lignes_et_leurs_cases(self):
        html = html_degrade(blocs_reels(), IDENTITE, MARCHE)
        for bloc in blocs_reels():
            self.assertIn(bloc['titre'], html)
            for ligne in bloc['lignes']:
                self.assertIn(ligne['libelle'].split('«')[0].strip()[:20],
                              html)
        self.assertIn(CASE_VIDE, html)
        self.assertIn(CASE_COCHEE, html)

    def test_forcer_degrade_simule_l_absence_de_la_lib(self):
        """Le drapeau permet de tester la voie dégradée même lib présente."""
        appels = {}

        def _faux_render_pdf(html=None, **kwargs):
            appels['html'] = html
            return b'%PDF-1.7 faux'

        import core.pdf as core_pdf
        original = core_pdf.render_pdf
        core_pdf.render_pdf = _faux_render_pdf
        try:
            contenu, format_, a_fournir = rendre_checklist(
                blocs_reels(), identite=IDENTITE, marche=MARCHE,
                forcer_degrade=True)
        finally:
            core_pdf.render_pdf = original
        self.assertEqual(format_, FORMAT_PDF_DEGRADE)
        self.assertTrue(a_fournir)
        self.assertTrue(contenu.startswith(b'%PDF'))
        self.assertIn(MENTION_A_FOURNIR, appels['html'])

    def test_docx_disponible_ne_leve_jamais(self):
        self.assertIn(docx_disponible(), (True, False))


class DocxEditableTest(SimpleTestCase):
    """Ne s'exécute que là où la dépendance optionnelle est installée."""

    def setUp(self):
        if not docx_disponible():
            self.skipTest("python-docx absent — voie dégradée testée ailleurs")

    def test_un_docx_editable_est_produit(self):
        contenu, format_, a_fournir = rendre_checklist(
            blocs_reels(), identite=IDENTITE, marche=MARCHE)
        self.assertEqual(format_, FORMAT_DOCX)
        self.assertFalse(a_fournir)
        # Un .docx est un ZIP OOXML : la signature « PK » le prouve.
        self.assertTrue(contenu.startswith(b'PK'))
        texte = texte_du_docx(contenu)
        self.assertIn('ACCORDIA TECH', texte)
        self.assertIn('AO-FRDISI-01', texte)
        self.assertIn('lu et accepté', texte)

    def test_les_cases_sont_vides_donc_remplissables(self):
        contenu, _, _ = rendre_checklist(blocs_reels(), identite=IDENTITE,
                                         marche=MARCHE)
        texte = texte_du_docx(contenu)
        self.assertIn(CASE_VIDE, texte)
        self.assertIn(CASE_COCHEE, texte)

    def test_les_sept_blocs_sont_presents(self):
        contenu, _, _ = rendre_checklist(blocs_reels(), identite=IDENTITE,
                                         marche=MARCHE)
        texte = texte_du_docx(contenu)
        for bloc in blocs_reels():
            self.assertIn(bloc['titre'], texte)


class EtancheiteDocxTest(SimpleTestCase):
    """Ratchet AOF129 étendu au format DOCX."""

    def test_un_libelle_de_cout_fait_refuser_le_rendu(self):
        for mot in ("prix d'achat", 'coût de revient', 'marge', 'bénéfice',
                    'maximum posable'):
            blocs = blocs_reels()
            blocs[0]['lignes'][0]['commentaire'] = 'vérifier la {}'.format(mot)
            with self.assertRaises(ValueError, msg=mot) as capture:
                rendre_checklist(blocs, identite=IDENTITE, marche=MARCHE,
                                 forcer_degrade=True)
            self.assertIn(mot, str(capture.exception))

    def test_le_texte_reellement_ecrit_dans_le_docx_est_relu(self):
        if not docx_disponible():
            self.skipTest("python-docx absent")
        contenu, _, _ = rendre_checklist(blocs_reels(), identite=IDENTITE,
                                         marche=MARCHE)
        texte = texte_du_docx(contenu).lower()
        for interdit in module.MOTS_INTERDITS:
            self.assertNotIn(interdit, texte)

    def test_le_repli_pdf_ne_porte_aucun_mot_interdit(self):
        html = html_degrade(blocs_reels(), IDENTITE, MARCHE).lower()
        for interdit in module.MOTS_INTERDITS:
            self.assertNotIn(interdit, html)
