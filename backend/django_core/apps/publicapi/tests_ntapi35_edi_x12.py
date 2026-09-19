"""NTAPI35 — EDI ANSI X12 : 810 sortant (facture) et 850 entrant (commande).

Critère d'acceptation, les trois volets :
  * un 810 généré est VALIDE — enveloppes ISA/GS/ST … SE/GE/IEA présentes et
    appariées, segments requis (BIG, IT1, TDS, CTT), compte SE01 exact ;
  * un 850 d'exemple crée un devis BROUILLON ;
  * INERTE drapeau OFF — aucun message, aucun devis, aucune exception.

Vérifie en plus les garanties transverses : la traduction des codes articles
passe par le registre NTAPI36 (jamais une seconde table), un code non mappé est
un avertissement et non un refus, et AUCUN prix d'achat n'entre dans un message.
"""
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, override_settings

from authentication.models import Company
from apps.crm.models import Client, Lead
from apps.stock.models import Categorie, Produit
from apps.ventes.models import Facture, LigneFacture

from .edi import x12
from .models import PartenaireEdi

# Horloge GELÉE : sans elle, l'ISA porterait la date du jour et un test
# comparant l'enveloppe deviendrait flaky à minuit.
MAINTENANT = datetime(2026, 9, 19, 14, 30, tzinfo=dt_timezone.utc)
EMISSION = date(2026, 9, 19)


def _company(slug, nom):
    co, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return co


def _facture(company, client, reference, **montants):
    """`Facture.date_emission` est `auto_now_add` : la seule façon de la figer
    est un `update()` après création (sinon le test prend la date du jour et
    devient flaky à minuit)."""
    facture = Facture.objects.create(
        company=company, client=client, reference=reference, **montants)
    Facture.objects.filter(pk=facture.pk).update(date_emission=EMISSION)
    facture.refresh_from_db()
    return facture


def _segments(message):
    """Tags de segments dans l'ordre, pour vérifier la structure."""
    return [s.split(x12.SEP_ELEMENT)[0]
            for s in message.split(x12.SEP_SEGMENT) if s.strip()]


def _segment(message, tag):
    for brut in message.split(x12.SEP_SEGMENT):
        elements = brut.split(x12.SEP_ELEMENT)
        if elements and elements[0] == tag:
            return elements
    return None


class Ntapi35GatedTests(SimpleTestCase):
    """Le drapeau : OFF par défaut, tout est inerte."""

    def test_le_drapeau_est_off_par_defaut(self):
        self.assertFalse(x12.edi_actif())

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_le_drapeau_sallume_explicitement(self):
        self.assertTrue(x12.edi_actif())


class Ntapi35Genere810Tests(TestCase):
    def setUp(self):
        self.co = _company('ntapi35', 'NTAPI35')
        categorie = Categorie.objects.create(company=self.co, nom='Panneaux')
        self.produit = Produit.objects.create(
            company=self.co, nom='Panneau 550 Wc', sku='PV-550',
            categorie=categorie, prix_vente=Decimal('1250.00'),
            # Prix d'ACHAT interne : il ne doit apparaître dans AUCUN message.
            prix_achat=Decimal('830.00'))
        self.client_obj = Client.objects.create(
            company=self.co, nom='Centrale US')
        self.facture = _facture(
            self.co, self.client_obj, 'FA-202609-0007',
            montant_ht=Decimal('12500.00'), montant_tva=Decimal('1250.00'),
            montant_ttc=Decimal('13750.00'))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit,
            designation='Panneau 550 Wc', quantite=Decimal('10'),
            prix_unitaire=Decimal('1250.00'))
        self.partenaire = PartenaireEdi.objects.create(
            company=self.co, nom='Centrale US', type_identifiant='duns',
            identifiant='123456789', format=PartenaireEdi.FORMAT_X12,
            mapping_sku={'PV-550': 'ACME-PANEL-550'})

    # ── Le cœur du critère ────────────────────────────────────────────────
    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_le_810_porte_toutes_ses_enveloppes_et_segments_requis(self):
        message, _avertissements = x12.generer_810(
            self.co, self.facture.id,
            identifiant_partenaire='123456789', maintenant=MAINTENANT)
        self.assertEqual(
            _segments(message),
            ['ISA', 'GS', 'ST', 'BIG', 'N1', 'IT1', 'TDS', 'CTT',
             'SE', 'GE', 'IEA'])
        # N1*ST = le tiers destinataire, sans adresse inventée.
        self.assertEqual(_segment(message, 'N1')[1:], ['ST', 'Centrale US'])

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_le_compte_de_segments_se01_est_exact(self):
        """SE01 compte ST → SE INCLUS. Un compte faux est le rejet le plus
        fréquent d'un 810, et il est silencieux côté VAN."""
        message, _ = x12.generer_810(
            self.co, self.facture.id, maintenant=MAINTENANT)
        tags = _segments(message)
        attendu = tags.index('SE') - tags.index('ST') + 1
        self.assertEqual(_segment(message, 'SE')[1], str(attendu))

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_les_numeros_de_controle_isa_ge_iea_sappairent(self):
        message, _ = x12.generer_810(
            self.co, self.facture.id, maintenant=MAINTENANT, controle=7)
        isa = message.split(x12.SEP_SEGMENT)[0].split(x12.SEP_ELEMENT)
        self.assertEqual(isa[13], '000000007')
        self.assertEqual(_segment(message, 'IEA')[2], '000000007')
        self.assertEqual(_segment(message, 'GE')[2], '7')
        self.assertEqual(_segment(message, 'GS')[6], '7')

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_isa_est_a_largeur_fixe_et_en_usage_test(self):
        message, _ = x12.generer_810(
            self.co, self.facture.id,
            identifiant_partenaire='123456789', maintenant=MAINTENANT)
        isa = message.split(x12.SEP_SEGMENT)[0].split(x12.SEP_ELEMENT)
        self.assertEqual(len(isa[2]), 10)      # ISA02 — 10 caractères
        self.assertEqual(len(isa[6]), 15)      # ISA06 — 15 caractères
        self.assertEqual(len(isa[8]), 15)      # ISA08 — 15 caractères
        self.assertEqual(isa[7].strip(), '01')  # DUNS → qualifiant '01'
        self.assertEqual(isa[8].strip(), '123456789')
        self.assertEqual(isa[12], x12.VERSION_ISA)
        # Gated → jamais 'P' par défaut : un essai ne doit pas passer pour une
        # facture réelle chez le partenaire.
        self.assertEqual(isa[15], x12.USAGE_TEST)

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_big_et_tds_portent_la_facture_reelle(self):
        message, _ = x12.generer_810(
            self.co, self.facture.id, maintenant=MAINTENANT)
        big = _segment(message, 'BIG')
        self.assertEqual(big[1], '20260919')
        self.assertEqual(big[2], 'FA-202609-0007')
        # TDS = total TTC en centièmes, sans point décimal (implied decimal).
        self.assertEqual(_segment(message, 'TDS')[1], '1375000')
        self.assertEqual(_segment(message, 'CTT')[1], '1')

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_it1_utilise_le_code_partenaire_du_registre(self):
        message, avertissements = x12.generer_810(
            self.co, self.facture.id,
            identifiant_partenaire='123456789', maintenant=MAINTENANT)
        it1 = _segment(message, 'IT1')
        self.assertEqual(it1[2], '10')                  # quantité
        self.assertEqual(it1[3], x12.UNITE_DEFAUT)
        self.assertEqual(it1[4], '1250.00')             # prix de VENTE facturé
        self.assertEqual(it1[6], x12.QUALIFIANT_ARTICLE)
        self.assertEqual(it1[7], 'ACME-PANEL-550')      # traduit (NTAPI36)
        self.assertEqual(avertissements, [])

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_un_sku_non_mappe_passe_brut_avec_un_avertissement(self):
        self.partenaire.mapping_sku = {}
        self.partenaire.save(update_fields=['mapping_sku'])
        message, avertissements = x12.generer_810(
            self.co, self.facture.id,
            identifiant_partenaire='123456789', maintenant=MAINTENANT)
        self.assertEqual(_segment(message, 'IT1')[7], 'PV-550')
        self.assertEqual(len(avertissements), 1)
        self.assertIn('PV-550', avertissements[0])

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_aucun_prix_dachat_dans_le_message(self):
        message, _ = x12.generer_810(
            self.co, self.facture.id, maintenant=MAINTENANT)
        self.assertNotIn('830.00', message)
        self.assertNotIn('83000', message)

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_une_facture_dune_autre_societe_ne_sexporte_pas(self):
        autre = _company('ntapi35-autre', 'NTAPI35 autre')
        client_autre = Client.objects.create(company=autre, nom='Pas à moi')
        facture_autre = _facture(
            autre, client_autre, 'FA-X',
            montant_ht=Decimal('1'), montant_tva=Decimal('0'),
            montant_ttc=Decimal('1'))
        self.assertIsNone(
            x12.generer_810(self.co, facture_autre.id, maintenant=MAINTENANT))

    def test_inerte_drapeau_off(self):
        self.assertIsNone(
            x12.generer_810(self.co, self.facture.id, maintenant=MAINTENANT))


EXEMPLE_850 = (
    'ISA*00*          *00*          *ZZ*ACMEUS         *ZZ*TAQINOR        '
    '*260919*1430*U*00401*000000012*0*T*>~'
    'GS*PO*ACMEUS*TAQINOR*20260919*1430*12*X*004010~'
    'ST*850*0001~'
    'BEG*00*SA*PO-88421**20260919~'
    'PO1*1*24*EA*1250.00**VP*ACME-PANEL-550~'
    'PO1*2*4*EA*3900.00**VP*ACME-INV-5K~'
    'CTT*2~'
    'SE*6*0001~'
    'GE*1*12~'
    'IEA*1*000000012~'
)


class Ntapi35Parse850Tests(SimpleTestCase):
    """Le parseur est pur : aucun accès base, testable seul."""

    def test_lit_le_numero_la_date_et_les_lignes(self):
        commande = x12.parser_850(EXEMPLE_850)
        self.assertEqual(commande['numero'], 'PO-88421')
        self.assertEqual(commande['date'], '20260919')
        self.assertEqual(len(commande['lignes']), 2)
        premiere = commande['lignes'][0]
        self.assertEqual(premiere['code_partenaire'], 'ACME-PANEL-550')
        self.assertEqual(premiere['quantite'], '24')
        self.assertEqual(premiere['prix_unitaire'], '1250.00')

    def test_un_po1_sans_prix_laisse_le_prix_a_none(self):
        """Jamais un zéro inventé, qui se lirait « gratuit »."""
        message = EXEMPLE_850.replace('*1250.00**VP*', '***VP*')
        commande = x12.parser_850(message)
        self.assertIsNone(commande['lignes'][0]['prix_unitaire'])

    def test_les_sauts_de_ligne_decoratifs_sont_toleres(self):
        commande = x12.parser_850(EXEMPLE_850.replace('~', '~\n'))
        self.assertEqual(commande['numero'], 'PO-88421')

    def test_une_autre_transaction_est_refusee_proprement(self):
        with self.assertRaises(x12.X12Error):
            x12.parser_850(EXEMPLE_850.replace('ST*850*', 'ST*810*'))

    def test_un_message_vide_est_refuse_proprement(self):
        with self.assertRaises(x12.X12Error):
            x12.parser_850('   ')

    def test_une_commande_sans_numero_est_avertie_pas_refusee(self):
        commande = x12.parser_850(
            EXEMPLE_850.replace('BEG*00*SA*PO-88421**', 'BEG*00*SA***'))
        self.assertEqual(commande['numero'], '')
        self.assertTrue(commande['avertissements'])


class Ntapi35Importe850Tests(TestCase):
    def setUp(self):
        self.co = _company('ntapi35-imp', 'NTAPI35 import')
        categorie = Categorie.objects.create(company=self.co, nom='Panneaux')
        Produit.objects.create(
            company=self.co, nom='Panneau 550 Wc', sku='PV-550',
            categorie=categorie, prix_vente=Decimal('1250.00'))
        self.lead = Lead.objects.create(
            company=self.co, nom='Centrale ACME',
            email='achats@acme.test')
        self.partenaire = PartenaireEdi.objects.create(
            company=self.co, nom='Centrale US', type_identifiant='duns',
            identifiant='123456789', format=PartenaireEdi.FORMAT_X12,
            mapping_sku={'PV-550': 'ACME-PANEL-550'})

    # ── Le cœur du second volet ───────────────────────────────────────────
    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_un_850_dexemple_cree_un_devis_brouillon(self):
        from apps.ventes.models import Devis

        resultat = x12.importer_850(
            self.co, EXEMPLE_850, lead=self.lead,
            identifiant_partenaire='123456789')
        devis = resultat['devis']
        self.assertEqual(devis.company_id, self.co.id)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.lead_id, self.lead.id)
        # Le client est résolu SERVEUR depuis le lead, jamais depuis l'ISA.
        self.assertIsNotNone(devis.client_id)
        # Aucune ligne créée : l'écrivain unique de lignes vit dans ventes.
        self.assertEqual(devis.lignes.count(), 0)

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_les_lignes_appariees_et_non_appariees_sont_listees(self):
        resultat = x12.importer_850(
            self.co, EXEMPLE_850, lead=self.lead,
            identifiant_partenaire='123456789')
        self.assertEqual([lig['sku'] for lig in resultat['lignes_appariees']],
                         ['PV-550'])
        # `ACME-INV-5K` n'est ni mappé ni au catalogue : listé, jamais devine.
        self.assertEqual(
            [lig['code_partenaire']
             for lig in resultat['lignes_non_appariees']],
            ['ACME-INV-5K'])
        self.assertTrue(resultat['avertissements'])

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_la_note_du_brouillon_resume_lorigine_edi(self):
        resultat = x12.importer_850(
            self.co, EXEMPLE_850, lead=self.lead,
            identifiant_partenaire='123456789')
        note = resultat['devis'].note or ''
        self.assertIn('850', note)
        self.assertIn('PO-88421', note)

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_sans_lead_limport_refuse_proprement(self):
        with self.assertRaises(x12.X12Error):
            x12.importer_850(self.co, EXEMPLE_850, lead=None)

    @override_settings(PUBLICAPI_EDI_ACTIF=True)
    def test_un_produit_dune_autre_societe_nest_jamais_apparie(self):
        autre = _company('ntapi35-imp-autre', 'NTAPI35 import autre')
        cat_autre = Categorie.objects.create(company=autre, nom='Onduleurs')
        Produit.objects.create(
            company=autre, nom='Onduleur 5 kW', sku='ACME-INV-5K',
            categorie=cat_autre, prix_vente=Decimal('3900.00'))
        resultat = x12.importer_850(
            self.co, EXEMPLE_850, lead=self.lead,
            identifiant_partenaire='123456789')
        self.assertEqual(
            [lig['code_partenaire']
             for lig in resultat['lignes_non_appariees']],
            ['ACME-INV-5K'])

    def test_inerte_drapeau_off(self):
        from apps.ventes.models import Devis

        self.assertIsNone(
            x12.importer_850(self.co, EXEMPLE_850, lead=self.lead))
        self.assertEqual(Devis.objects.count(), 0)
