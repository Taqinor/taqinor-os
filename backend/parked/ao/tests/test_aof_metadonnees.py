"""AOF145 — un PDF sortant ne dit ni qui l'a fabriqué ni sur quel poste.

Les PDF témoins sont fabriqués ici avec la signature EXACTE du trou réel :
Creator « Matplotlib v3.9.2 », Producer « matplotlib pdf backend », et un
titre portant « C:\\Users\\…\\OneDrive - Atlencia\\… ». C'est ce que les trois
scripts de dépôt du 27/07 produisent aujourd'hui.

Trois promesses :
  1. aucune métadonnée d'outil ne subsiste (Creator/Producer vidés) ;
  2. aucun chemin local ne subsiste dans le binaire ;
  3. Author = SOUMISSIONNAIRE, y compris en marque blanche — jamais le bureau.

Run :
    python manage.py test apps.ao.tests.test_aof_metadonnees -v2
"""
from django.test import SimpleTestCase

from apps.ao.fabrique.metadonnees_pdf import (
    CheminLocalDetecte, assainir, chemins_locaux, forcer_metadonnees,
    lire_metadonnees, verifier_absence_chemins,
)

CHEMIN_REEL = ('C:\\Users\\kasri\\OneDrive - Atlencia\\TAQINOR\\AO\\'
               'planche_05H_bat_C_ecole.pdf')
SOUMISSIONNAIRE = 'ACCORDIA TECH'
BUREAU = 'TAQINOR'


def pdf_temoin(*, titre=CHEMIN_REEL, texte='', creator='Matplotlib v3.9.2',
               producer='matplotlib pdf backend'):
    """PDF portant la signature par défaut d'une planche matplotlib."""
    import fitz

    document = fitz.open()
    page = document.new_page()
    if texte:
        page.insert_text((72, 72), texte)
    document.set_metadata({
        'title': titre,
        'author': BUREAU,
        'subject': '',
        'keywords': 'solaire, AO',
        'creator': creator,
        'producer': producer,
    })
    contenu = document.tobytes()
    document.close()
    return contenu


class MetadonneesForceesTest(SimpleTestCase):
    def test_creator_et_producer_sont_neutralises(self):
        propre = forcer_metadonnees(pdf_temoin(), code_document='05H',
                                    soumissionnaire=SOUMISSIONNAIRE,
                                    objet_marche='Centrale PV')
        metadonnees = lire_metadonnees(propre)
        self.assertEqual(metadonnees.get('creator') or '', '')
        self.assertEqual(metadonnees.get('producer') or '', '')
        self.assertEqual(metadonnees.get('keywords') or '', '')

    def test_title_subject_et_author_sont_imposes(self):
        propre = forcer_metadonnees(pdf_temoin(), code_document='05H',
                                    soumissionnaire=SOUMISSIONNAIRE,
                                    objet_marche='Centrale PV FRDISI')
        metadonnees = lire_metadonnees(propre)
        self.assertEqual(metadonnees.get('title'), '05H')
        self.assertEqual(metadonnees.get('author'), SOUMISSIONNAIRE)
        self.assertEqual(metadonnees.get('subject'), 'Centrale PV FRDISI')

    def test_author_est_le_soumissionnaire_meme_en_marque_blanche(self):
        """Le PDF témoin porte le BUREAU en auteur : il doit disparaître."""
        self.assertEqual(lire_metadonnees(pdf_temoin()).get('author'), BUREAU)
        propre = forcer_metadonnees(pdf_temoin(), code_document='05H',
                                    soumissionnaire=SOUMISSIONNAIRE)
        self.assertEqual(lire_metadonnees(propre).get('author'),
                         SOUMISSIONNAIRE)
        self.assertEqual(chemins_locaux(propre, jetons_interdits=(BUREAU,)),
                         [])

    def test_un_soumissionnaire_vide_est_refuse(self):
        for valeur in ('', '   ', None):
            with self.assertRaises(ValueError, msg=repr(valeur)):
                forcer_metadonnees(pdf_temoin(), code_document='05H',
                                   soumissionnaire=valeur)

    def test_un_pdf_vide_est_refuse(self):
        with self.assertRaises(ValueError):
            forcer_metadonnees(b'', code_document='05H',
                               soumissionnaire=SOUMISSIONNAIRE)


class PurgeDesCheminsTest(SimpleTestCase):
    def test_le_chemin_reel_est_detecte_avant_traitement(self):
        trouves = chemins_locaux(pdf_temoin())
        self.assertTrue(trouves, "le chemin témoin doit être vu")
        self.assertTrue(any('OneDrive' in t or 'Users' in t for t in trouves))

    def test_aucun_chemin_ne_subsiste_apres_traitement(self):
        propre = forcer_metadonnees(pdf_temoin(), code_document='05H',
                                    soumissionnaire=SOUMISSIONNAIRE)
        self.assertEqual(chemins_locaux(propre), [])
        self.assertTrue(verifier_absence_chemins(propre))

    def test_un_jeton_interdit_est_detecte(self):
        propre = forcer_metadonnees(
            pdf_temoin(titre='planche 05H'), code_document='05H',
            soumissionnaire=SOUMISSIONNAIRE)
        # Rien à trouver…
        self.assertEqual(chemins_locaux(propre,
                                        jetons_interdits=('Atlencia',)), [])
        # …mais le soumissionnaire, lui, est bien inscrit et détectable :
        # le détecteur ne ment pas dans les deux sens.
        self.assertEqual(
            chemins_locaux(propre, jetons_interdits=(SOUMISSIONNAIRE,)),
            [SOUMISSIONNAIRE])

    def test_un_chemin_grave_dans_la_PAGE_fait_echouer_la_passe(self):
        """Ce qui est dans le flux de contenu ne se réécrit pas : on REFUSE."""
        temoin = pdf_temoin(titre='planche 05H', texte=CHEMIN_REEL)
        with self.assertRaises(CheminLocalDetecte) as capture:
            assainir(temoin, code_document='05H',
                     soumissionnaire=SOUMISSIONNAIRE)
        self.assertTrue(capture.exception.trouves)
        self.assertIn('corriger la SOURCE', str(capture.exception))

    def test_la_passe_complete_rend_un_pdf_propre(self):
        propre = assainir(pdf_temoin(), code_document='06I',
                          soumissionnaire=SOUMISSIONNAIRE,
                          objet_marche='Centrale PV',
                          jetons_interdits=(BUREAU, 'Atlencia'))
        metadonnees = lire_metadonnees(propre)
        self.assertEqual(metadonnees.get('title'), '06I')
        self.assertEqual(metadonnees.get('author'), SOUMISSIONNAIRE)
        self.assertEqual(metadonnees.get('creator') or '', '')
        self.assertTrue(propre.startswith(b'%PDF'))

    def test_le_bureau_en_marque_blanche_fait_echouer_la_passe(self):
        temoin = pdf_temoin(titre='planche 05H',
                            texte='Étude {} — bâtiment C'.format(BUREAU))
        with self.assertRaises(CheminLocalDetecte) as capture:
            assainir(temoin, code_document='05H',
                     soumissionnaire=SOUMISSIONNAIRE,
                     jetons_interdits=(BUREAU,))
        self.assertIn(BUREAU, capture.exception.trouves)
