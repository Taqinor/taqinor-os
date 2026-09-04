"""AUD603 — la fabrique produit enfin les deux pièces BLOQUANTES d'un pli.

Constat : sur 10 producteurs déclarés, 3 seulement étaient montés. Le bordereau
des prix et l'acte d'engagement — les deux pièces sans lesquelles un pli est
déclaré IRRECEVABLE à l'ouverture au Maroc — portaient un
``motif_indisponible`` : ``producteurs_de_pack`` les marquait ``echouee`` et le
ZIP de dépôt partait amputé. La machinerie de rendu existait pourtant en entier
(``rendus/bordereau_pdf``, ``rendus/acte_engagement``) ; ce qui manquait était
le PONT entre un ``DossierAO`` en base et le contexte gelé AOF111, assemblé
nulle part hors des tests.

Run :
    python manage.py test apps.ao.tests.test_aud603_pieces_bloquantes -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.ao import services
from apps.ao.fabrique import producteurs as registre
from apps.ao.models import (
    AppelOffre, BordereauPrix, DossierAO, IdentiteAO, LigneBordereau,
    ModelePack, PieceConsultation, PieceDossierAO, PieceModele,
    SectionBordereau,
)
from authentication.models import Company

CLAUSE = ('Marché à prix unitaires : les quantités portées au présent '
          'bordereau sont prévisionnelles.')


class BaseDossierComplet(TestCase):
    """Un dossier RÉEL, avec tout ce qu'un pli recevable exige."""

    def setUp(self):
        self.company = Company.objects.create(nom='AUD603 Co',
                                              slug='aud603-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-603-1',
            reference_acheteur='AO 12/2026',
            objet='Fourniture et installation d\'une centrale photovoltaïque',
            acheteur='FRDISI', maitre_ouvrage='FRDISI',
            site_adresse='Route de Nouaceur, Casablanca',
            mode_passation='Appel d\'offres ouvert',
            delai_execution_jours=120, validite_offre_jours=75)
        IdentiteAO.objects.create(
            company=self.company, appel_offre=self.ao,
            role=IdentiteAO.Role.SOUMISSIONNAIRE,
            raison_sociale='TAQINOR SARL', ice='002345678000091',
            identifiant_fiscal='55667788', registre_commerce='123456',
            adresse='12 rue de l\'Énergie, Casablanca',
            signataire_nom='Reda Kasri', signataire_qualite='Gérant',
            rib='011 780 0000012345678901 23')
        self.bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao, clause_reserve=CLAUSE)
        section = SectionBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, numero=1,
            libelle='Bâtiment A')
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, section=section,
            numero=1, designation='Modules photovoltaïques 625 Wc', unite='U',
            quantite=Decimal('152.000'), prix_unitaire=Decimal('2950.00'))
        LigneBordereau.objects.create(
            company=self.company, bordereau=self.bordereau, section=section,
            numero=2, designation='Onduleurs 110 kW', unite='U',
            quantite=Decimal('3.000'), prix_unitaire=Decimal('78000.00'))
        self.dossier = DossierAO.objects.create(
            company=self.company, appel_offre=self.ao, reference='AODOS-603')
        self.piece_bordereau = PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, ordre=3,
            code='03', libelle='Bordereau des prix')
        self.piece_acte = PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, ordre=9,
            code='09', libelle="Acte d'engagement")

        # Le gabarit de pack : c'est LUI qui dit quel générateur produit quelle
        # pièce (AOF116). Sans lui, `_generateur_de_piece` retombe sur le code
        # numérique de la pièce, qui n'est déclaré à aucun registre.
        modele = ModelePack.objects.create(
            company=self.company, code='PACK-603', libelle='Pack AUD603')
        PieceModele.objects.create(
            company=self.company, modele=modele, code='03',
            libelle='Bordereau des prix', generateur='bordereau', ordre=3)
        PieceModele.objects.create(
            company=self.company, modele=modele, code='09',
            libelle="Acte d'engagement", generateur='acte_engagement',
            ordre=9)


class TestLesDeuxProducteursSontMontes(BaseDossierComplet):
    def test_le_registre_les_declare_montes(self):
        for code in ('bordereau', 'acte_engagement'):
            with self.subTest(producteur=code):
                self.assertTrue(
                    registre.REGISTRE[code].monte,
                    f'« {code} » reste déclaré sans monteur : la fabrique ne '
                    f'peut produire aucun pli déposable.')

    def test_plus_aucun_motif_indisponible_sur_ces_deux(self):
        for code in ('bordereau', 'acte_engagement'):
            with self.subTest(producteur=code):
                self.assertEqual(registre.REGISTRE[code].motif_indisponible,
                                 '')


class TestOctetsProduits(BaseDossierComplet):
    def test_le_bordereau_rend_un_pdf_non_vide(self):
        contenu = registre.REGISTRE['bordereau'].octets(
            self.dossier, self.piece_bordereau)
        self.assertTrue(contenu)
        self.assertTrue(contenu.startswith(b'%PDF'), contenu[:16])

    def test_l_acte_rend_un_pdf_non_vide(self):
        contenu = registre.REGISTRE['acte_engagement'].octets(
            self.dossier, self.piece_acte)
        self.assertTrue(contenu)
        self.assertTrue(contenu.startswith(b'%PDF'), contenu[:16])

    def test_producteurs_de_pack_leur_donne_un_producteur(self):
        pieces, _empreinte, _deja = services.producteurs_de_pack(
            self.dossier.pk)
        par_code = {p['code']: p for p in pieces}
        for code in ('03', '09'):
            with self.subTest(piece=code):
                self.assertIn('producteur', par_code[code])


class TestEchecsNOMMES(BaseDossierComplet):
    """La règle du module : un échec NOMME ce qui manque, jamais un vide."""

    def test_sans_bordereau_l_echec_nomme_le_bordereau(self):
        self.bordereau.delete()
        with self.assertRaises(registre.ProducteurIndisponible) as ctx:
            registre.REGISTRE['bordereau'].octets(
                self.dossier, self.piece_bordereau)
        self.assertIn('bordereau des prix', str(ctx.exception).lower())

    def test_bordereau_sans_ligne_refuse(self):
        self.bordereau.lignes.all().delete()
        with self.assertRaises(registre.ProducteurIndisponible):
            registre.REGISTRE['bordereau'].octets(
                self.dossier, self.piece_bordereau)

    def test_acte_aux_blancs_obligatoires_vides_refuse(self):
        """Un acte incomplet fait ÉCARTER le pli — il ne part pas."""
        IdentiteAO.objects.filter(appel_offre=self.ao).update(
            raison_sociale='', ice='', identifiant_fiscal='',
            registre_commerce='', adresse='', rib='', signataire_nom='',
            signataire_qualite='')
        with self.assertRaises(registre.ProducteurIndisponible) as ctx:
            registre.REGISTRE['acte_engagement'].octets(
                self.dossier, self.piece_acte)
        self.assertIn('INCOMPLET', str(ctx.exception))


class TestModeReport(BaseDossierComplet):
    """AOF132 — un modèle d'acte fourni par l'acheteur bascule en REPORT.

    Refabriquer le document de l'acheteur est un motif d'écartement : la
    présence de sa pièce doit suffire à changer de mode, sans réglage.
    """

    def test_le_modele_acheteur_bascule_le_mode(self):
        PieceConsultation.objects.create(
            company=self.company, appel_offre=self.ao,
            type_piece=PieceConsultation.TypePiece.MODELE_ACTE,
            reference='DCE-AE-01')
        modele = registre._modele_acte_de_l_acheteur(self.ao)
        self.assertEqual(modele['reference'], 'DCE-AE-01')

    def test_sans_modele_acheteur_le_mode_reste_autonome(self):
        self.assertIsNone(registre._modele_acte_de_l_acheteur(self.ao))


class TestRemiseGlobaleHonoree(BaseDossierComplet):
    """Une remise globale réelle doit descendre jusque dans les deux pièces.

    Sans ce report, le bordereau et l'acte auraient engagé le SOUS-TOTAL —
    c.-à-d. un montant supérieur à l'offre réellement consentie.
    """

    def test_les_montants_de_l_acte_suivent_la_remise(self):
        from apps.ao.fabrique.rendus import acte_engagement

        self.bordereau.remise_globale_pct = Decimal('5.00')
        self.bordereau.save(update_fields=['remise_globale_pct'])
        _b, lignes, gele = registre._entrees_de_bordereau(self.dossier)
        donnees = acte_engagement.contexte_gabarit(
            lignes, gele, taux_tva=self.bordereau.taux_tva_defaut,
            remise_globale=self.bordereau.montant_remise_globale)
        self.assertEqual(donnees['totaux'].total_ht,
                         self.bordereau.total_ht)
