"""AOF152 — le bon à tirer sort du MÊME manifeste que le sommaire.

Quatre promesses :
  1. l'ordre du PDF est exactement celui du manifeste (donc du sommaire) ;
  2. les pièces `interne`/`directeur` n'y entrent pas, et un intitulé de coût
     refuse l'assemblage (ratchet AOF129 étendu au bon à tirer) ;
  3. la fusion est DÉLÉGUÉE à `apps.ged.services.fusionner_pdf` — jamais un
     second usage de PyMuPDF recodé ici ;
  4. mémoire bornée : la séquence est un générateur et ne lit AUCUN octet de
     pièce (vérifié par une sentinelle qui explose si on la lit).

Run :
    python manage.py test apps.ao.tests.test_aof_pack_pdf -v2
"""
import types

from django.test import SimpleTestCase

from apps.ao.fabrique import pack_pdf
from apps.ao.fabrique.pack_pdf import (
    FORMAT_CORPS, FORMAT_PLANCHE, PackPdfRefuse, fusionner_pack,
    intercalaire_html, plan_pagination, sequence_impression,
)


class DocumentFactice:
    """Tient lieu de ``ged.Document`` : on ne vérifie que l'ORDRE."""

    def __init__(self, nom):
        self.nom = nom

    def __repr__(self):  # pragma: no cover - confort de diagnostic
        return 'Doc({})'.format(self.nom)


def manifeste():
    return [
        {'code': '00', 'libelle': 'Checklist partenaire', 'ordre': 0,
         'visibilite': 'interne', 'pages': 3, 'section': 'ADM',
         'document': DocumentFactice('00')},
        {'code': '01', 'libelle': 'Lettre de soumission', 'ordre': 1,
         'visibilite': 'client', 'pages': 1, 'section': 'ADM',
         'document': DocumentFactice('01')},
        {'code': '02', 'libelle': 'Mémoire technique', 'ordre': 2,
         'visibilite': 'client', 'pages': 24, 'section': 'TEC',
         'document': DocumentFactice('02')},
        {'code': '04', 'libelle': 'Bordereau des prix', 'ordre': 4,
         'visibilite': 'client', 'pages': 6, 'section': 'FIN',
         'document': DocumentFactice('04')},
        {'code': '06', 'libelle': 'Planches A3', 'ordre': 6,
         'visibilite': 'client', 'pages': 3, 'section': 'PLA',
         'format_page': 'A3', 'document': DocumentFactice('06')},
        {'code': '09', 'libelle': 'Rentabilité attendue (direction)',
         'ordre': 9, 'visibilite': 'directeur', 'pages': 2, 'section': 'DIR',
         'document': DocumentFactice('09')},
    ]


def avec_documents(elements):
    """Attache un document à chaque intercalaire (rôle de l'appelant)."""
    for element in elements:
        if element.get('document') is None:
            element['document'] = DocumentFactice(
                'inter-{}'.format(element.get('section')))
        yield element


class OrdreTest(SimpleTestCase):
    def test_l_ordre_suit_le_manifeste(self):
        pieces = [e for e in sequence_impression(manifeste())
                  if e['type'] == 'piece']
        self.assertEqual([e['code'] for e in pieces],
                         ['01', '02', '04', '06'])

    def test_les_pieces_non_client_n_entrent_pas(self):
        codes = [e.get('code') for e in sequence_impression(manifeste())]
        self.assertNotIn('00', codes)
        self.assertNotIn('09', codes)

    def test_un_intercalaire_precede_chaque_section(self):
        elements = list(sequence_impression(manifeste()))
        types = [e['type'] for e in elements]
        self.assertEqual(types, ['intercalaire', 'piece'] * 4)
        sections = [e['section'] for e in elements
                    if e['type'] == 'intercalaire']
        self.assertEqual(sections, ['ADM', 'TEC', 'FIN', 'PLA'])

    def test_les_intercalaires_peuvent_etre_desactives(self):
        elements = list(sequence_impression(manifeste(),
                                            avec_intercalaires=False))
        self.assertTrue(all(e['type'] == 'piece' for e in elements))

    def test_les_planches_sont_marquees_A3_dans_un_corps_A4(self):
        par_code = {e['code']: e for e in sequence_impression(manifeste())
                    if e['type'] == 'piece'}
        self.assertEqual(par_code['06']['format'], FORMAT_PLANCHE)
        self.assertEqual(par_code['02']['format'], FORMAT_CORPS)

    def test_un_manifeste_sans_piece_client_refuse(self):
        interne = [p for p in manifeste() if p['visibilite'] != 'client']
        with self.assertRaises(PackPdfRefuse):
            list(sequence_impression(interne))


class PaginationTest(SimpleTestCase):
    def test_les_plages_de_pages_sont_contigues(self):
        plan = plan_pagination(manifeste())
        self.assertEqual([(p['code'], p['premiere_page'], p['derniere_page'])
                          for p in plan],
                         [('01', 2, 2), ('02', 4, 27), ('04', 29, 34),
                          ('06', 36, 38)])

    def test_une_piece_sans_pages_interrompt_le_plan(self):
        entree = manifeste()
        entree[2].pop('pages')
        with self.assertRaises(PackPdfRefuse) as capture:
            plan_pagination(entree)
        self.assertIn('pagination annoncée', str(capture.exception))


class DelegationGedTest(SimpleTestCase):
    """La fusion est celle de GED — on vérifie ce qu'on lui passe."""

    def test_les_documents_sont_transmis_dans_l_ordre(self):
        recu = {}

        def _fausse_fusion(documents, *, cible=None, company=None, nom='',
                           created_by=None):
            recu['documents'] = list(documents)
            recu['nom'] = nom
            recu['company'] = company
            return 'document-fusionne'

        import apps.ged.services as ged_services
        original = ged_services.fusionner_pdf
        ged_services.fusionner_pdf = _fausse_fusion
        try:
            resultat = fusionner_pack(
                avec_documents(sequence_impression(manifeste())),
                company='SOCIETE', nom='Bon à tirer')
        finally:
            ged_services.fusionner_pdf = original

        self.assertEqual(resultat, 'document-fusionne')
        self.assertEqual(recu['nom'], 'Bon à tirer')
        self.assertEqual(
            [d.nom for d in recu['documents']],
            ['inter-ADM', '01', 'inter-TEC', '02', 'inter-FIN', '04',
             'inter-PLA', '06'])

    def test_un_element_sans_document_refuse_l_assemblage(self):
        with self.assertRaises(PackPdfRefuse) as capture:
            fusionner_pack(sequence_impression(manifeste()),
                           company='SOCIETE', nom='Bon à tirer')
        self.assertIn('sans document GED', str(capture.exception))

    def test_ce_module_n_importe_jamais_pymupdf(self):
        """Le seul assembleur PDF du dépôt reste celui de GED (XGED10)."""
        with open(pack_pdf.__file__, encoding='utf-8') as source:
            code = source.read()
        self.assertNotIn('import fitz', code)
        self.assertNotIn('from fitz', code)
        self.assertIn('from apps.ged.services import fusionner_pdf', code)


class EtancheiteBonATirerTest(SimpleTestCase):
    def test_un_intitule_de_cout_refuse_l_assemblage(self):
        for mot in ('marge', 'coût de revient', 'rentabilité'):
            entree = manifeste()
            entree[1]['libelle'] = 'Note de {}'.format(mot)
            with self.assertRaises(PackPdfRefuse, msg=mot) as capture:
                list(sequence_impression(entree))
            self.assertIn(mot, str(capture.exception))

    def test_aucun_intitule_interdit_dans_les_intercalaires(self):
        for element in sequence_impression(manifeste()):
            if element['type'] != 'intercalaire':
                continue
            html = intercalaire_html(element).lower()
            for mot in ('marge', 'rentabilité', "prix d'achat"):
                self.assertNotIn(mot, html)


class MemoireBorneeTest(SimpleTestCase):
    def test_la_sequence_est_un_generateur(self):
        self.assertIsInstance(sequence_impression(manifeste()),
                              types.GeneratorType)

    def test_aucun_octet_de_piece_n_est_lu(self):
        """Sentinelle : lire le contenu d'une pièce fait exploser le test."""

        class ContenuInterdit:
            def __getattr__(self, nom):
                raise AssertionError(
                    'le contenu de la pièce a été touché : {}'.format(nom))

        entree = manifeste()
        for piece in entree:
            piece['contenu'] = ContenuInterdit()
            piece['flux'] = ContenuInterdit()
        elements = list(sequence_impression(entree))
        self.assertTrue(elements)
        plan_pagination(entree)
