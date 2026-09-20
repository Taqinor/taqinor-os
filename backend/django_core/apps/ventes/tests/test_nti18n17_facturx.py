"""NTI18N17 — Factur-X (XML EN16931 BASIC embarqué dans le PDF de facture).

Trois surfaces, aucune base de données :
  1. l'INTERRUPTEUR — fermé par défaut, il faut le pack FRANCE **et** une
     option cochée ;
  2. le XML — ce qu'il contient, et surtout ce qu'il REFUSE d'écrire ;
  3. l'EMBARQUEMENT — le PDF reste lisible et le XML en ressort identique.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_nti18n17_facturx -v 2
"""
import xml.etree.ElementTree as ET

from django.test import SimpleTestCase

from apps.ventes.quote_engine import facturx as FX


def facture_exemple():
    """Facture française minimale mais COMPLÈTE (tous les montants fournis).

    Une ligne porte volontairement un ``prix_achat`` : un test vérifie plus bas
    qu'il ne peut pas traverser jusqu'au document client.
    """
    return {
        'numero': 'FA-2026-000123',
        'date_emission': '2026-09-19',
        'date_echeance': '2026-10-19',
        'devise': 'EUR',
        'vendeur': {'nom': 'Taqinor SARL', 'pays': 'FR',
                    'tva_intracom': 'FR40303265045',
                    'adresse': '1 rue du Soleil', 'code_postal': '75001',
                    'ville': 'Paris'},
        'acheteur': {'nom': 'Client & Fils <SA>', 'pays': 'FR'},
        'lignes': [
            {'designation': 'Panneau mono 550W', 'quantite': '14',
             'prix_unitaire_ht': '110.00', 'montant_ht': '1540.00',
             'taux_tva': '20', 'prix_achat': '77777'},
            {'designation': 'Installation', 'quantite': '1',
             'prix_unitaire_ht': '400.00', 'montant_ht': '400.00',
             'taux_tva': '20'},
        ],
        'taux_tva': '20',
        'total_ht': '1940.00',
        'total_tva': '388.00',
        'total_ttc': '2328.00',
    }


class NTI18N17InterrupteurTests(SimpleTestCase):
    """La porte est fermée, et il faut DEUX clés pour l'ouvrir."""

    def test_par_defaut_rien_ne_s_active(self):
        self.assertFalse(FX.facturx_actif())

    def test_les_deux_conditions_sont_necessaires(self):
        self.assertTrue(
            FX.facturx_actif(pack_pays='FR', option_activee=True))
        self.assertFalse(
            FX.facturx_actif(pack_pays='FR', option_activee=False))
        self.assertFalse(
            FX.facturx_actif(pack_pays='MA', option_activee=True))
        self.assertFalse(
            FX.facturx_actif(pack_pays='', option_activee=True))

    def test_le_pack_pays_absent_ferme_la_porte_sans_lever(self):
        """``CompanyProfile.pack_pays`` n'existe pas encore (NTI18N16) : la
        lecture doit rendre '' au lieu d'exploser au milieu d'une facture."""
        self.assertEqual(FX.pack_pays_de(None), '')
        self.assertEqual(FX.pack_pays_de(object()), '')
        self.assertFalse(FX.facturx_actif(company=object(),
                                          option_activee=True))

    def test_porte_fermee_rend_les_octets_tels_quels(self):
        octets = b'%PDF-1.7\n% des octets de facture'
        rendus, rapport = FX.appliquer(octets, facture_exemple())
        self.assertIs(rendus, octets)
        self.assertFalse(rapport['embarque'])


class NTI18N17XmlTests(SimpleTestCase):
    """Le XML : profil déclaré, données fidèles, et refus d'écrire faux."""

    def setUp(self):
        self.xml = FX.construire_xml(facture_exemple())
        self.texte = self.xml.decode('utf-8')

    def test_le_profil_en16931_basic_est_declare(self):
        self.assertIn(FX.PROFIL_BASIC, self.texte)
        self.assertTrue(self.xml.startswith(b'<?xml'))

    def test_le_xml_est_bien_forme_et_porte_ses_lignes(self):
        racine = ET.fromstring(self.xml)
        self.assertTrue(racine.tag.endswith('}CrossIndustryInvoice'))
        lignes = racine.findall(
            './/{*}IncludedSupplyChainTradeLineItem')
        self.assertEqual(len(lignes), 2)

    def test_les_montants_sont_ceux_de_la_facture(self):
        for montant in ('1940.00', '388.00', '2328.00', '1540.00', '400.00'):
            with self.subTest(montant=montant):
                self.assertIn(f'>{montant}<', self.texte)

    def test_les_dates_sont_au_format_de_la_norme(self):
        self.assertIn('>20260919<', self.texte)
        self.assertIn('>20261019<', self.texte)

    def test_le_resume_suit_l_ordre_impose(self):
        ordre = ['LineTotalAmount', 'TaxBasisTotalAmount', 'TaxTotalAmount',
                 'GrandTotalAmount', 'DuePayableAmount']
        resume = self.texte.split(
            'SpecifiedTradeSettlementHeaderMonetarySummation')[1]
        positions = [resume.index(nom) for nom in ordre]
        self.assertEqual(positions, sorted(positions))

    def test_aucun_prix_d_achat_ne_traverse(self):
        """Règle #4 : ``Produit.prix_achat`` n'atteint aucune sortie client."""
        self.assertNotIn('77777', self.texte)
        self.assertNotIn('prix_achat', self.texte)
        self.assertNotIn('marge', self.texte.lower())

    def test_le_texte_client_est_echappe(self):
        self.assertIn('&lt;SA&gt;', self.texte)
        self.assertIn('&amp;', self.texte)
        self.assertNotIn('<SA>', self.texte)

    def test_une_facture_qui_se_contredit_est_refusee(self):
        facture = facture_exemple()
        facture['total_ttc'] = '9999.00'
        with self.assertRaises(FX.DonneesFacturxInvalides):
            FX.construire_xml(facture)

    def test_une_repartition_de_tva_qui_ne_tombe_pas_juste_est_refusee(self):
        facture = facture_exemple()
        facture['tva_par_taux'] = [
            {'taux': '20', 'base_ht': '1540.00', 'montant': '308.00'}]
        with self.assertRaises(FX.DonneesFacturxInvalides):
            FX.construire_xml(facture)

    def test_les_champs_requis_ne_sont_jamais_devines(self):
        for champ in FX.CHAMPS_REQUIS + ('lignes',):
            with self.subTest(champ=champ):
                facture = facture_exemple()
                facture.pop(champ)
                with self.assertRaises(FX.DonneesFacturxInvalides):
                    FX.construire_xml(facture)

    def test_une_date_illisible_est_refusee(self):
        facture = facture_exemple()
        facture['date_emission'] = 'le mois prochain'
        with self.assertRaises(FX.DonneesFacturxInvalides):
            FX.construire_xml(facture)

    def test_un_taux_nul_sans_categoire_declaree_est_refuse(self):
        """Une exonération engage : elle se déclare, elle ne se devine pas."""
        facture = facture_exemple()
        facture.update(taux_tva='0', total_tva='0.00', total_ttc='1940.00')
        with self.assertRaises(FX.DonneesFacturxInvalides):
            FX.construire_xml(facture)

    def test_une_exoneration_declaree_passe_avec_son_motif(self):
        facture = facture_exemple()
        facture.update(total_tva='0.00', total_ttc='1940.00')
        facture['tva_par_taux'] = [{
            'taux': '0', 'base_ht': '1940.00', 'montant': '0.00',
            'categorie': 'E',
            'motif_exoneration': 'Exonération art. 262 ter I du CGI',
        }]
        texte = FX.construire_xml(facture).decode('utf-8')
        self.assertIn('>E<', texte)
        self.assertIn('262 ter I du CGI', texte)

    def test_plusieurs_taux_donnent_plusieurs_tranches(self):
        facture = facture_exemple()
        facture['tva_par_taux'] = [
            {'taux': '20', 'base_ht': '1540.00', 'montant': '308.00'},
            {'taux': '10', 'base_ht': '400.00', 'montant': '80.00'},
        ]
        texte = FX.construire_xml(facture).decode('utf-8')
        self.assertIn('>10.00<', texte)
        self.assertIn('>80.00<', texte)
        self.assertIn('>308.00<', texte)


class NTI18N17EmbarquementTests(SimpleTestCase):
    """Le PDF reste un PDF, et le XML en ressort tel qu'il y est entré."""

    @staticmethod
    def _pdf_minimal():
        import fitz
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), 'Facture')
        octets = document.tobytes()
        document.close()
        return octets

    def test_des_octets_qui_ne_sont_pas_un_pdf_sont_refuses(self):
        with self.assertRaises(FX.DonneesFacturxInvalides):
            FX.embarquer_xml(b'ceci n est pas un PDF', b'<xml/>')

    def test_le_pdf_reste_lisible_et_rend_son_xml_a_l_identique(self):
        import fitz
        xml = FX.construire_xml(facture_exemple())
        octets, rapport = FX.embarquer_xml(self._pdf_minimal(), xml)

        self.assertTrue(octets.startswith(b'%PDF'))
        self.assertTrue(rapport['embarque'])
        self.assertEqual(rapport['nom_fichier'], FX.NOM_FICHIER_XML)
        self.assertEqual(rapport['profil'], FX.PROFIL_BASIC)

        document = fitz.open(stream=octets, filetype='pdf')
        try:
            self.assertEqual(document.page_count, 1)
            self.assertIn('Facture', document[0].get_text())
            self.assertIn(FX.NOM_FICHIER_XML, document.embfile_names())
            self.assertEqual(document.embfile_get(FX.NOM_FICHIER_XML), xml)
            metadonnees = document.get_xml_metadata() or ''
            self.assertIn('urn:factur-x', metadonnees)
            self.assertIn('BASIC', metadonnees)
            # Le rapport ne se contente pas de promettre : quand il annonce le
            # fichier associé, le catalogue le porte vraiment.
            if rapport['fichier_associe']:
                self.assertNotEqual(
                    document.xref_get_key(document.pdf_catalog(), 'AF')[0],
                    'null')
        finally:
            document.close()

    def test_le_rapport_n_annonce_pas_une_conformite_pdf_a3(self):
        """Attacher un XML ne rend pas le PDF conforme PDF/A-3 : le rapport
        doit le dire, pour que personne ne le croie en aval."""
        _, rapport = FX.embarquer_xml(
            self._pdf_minimal(), FX.construire_xml(facture_exemple()))
        self.assertFalse(rapport['pdf_a3'])

    def test_la_porte_ouverte_embarque_vraiment(self):
        import fitz
        octets, rapport = FX.appliquer(
            self._pdf_minimal(), facture_exemple(),
            pack_pays='FR', option_activee=True)
        self.assertTrue(rapport['embarque'])
        document = fitz.open(stream=octets, filetype='pdf')
        try:
            self.assertIn(FX.NOM_FICHIER_XML, document.embfile_names())
        finally:
            document.close()
