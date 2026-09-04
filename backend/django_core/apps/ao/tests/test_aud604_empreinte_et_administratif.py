"""AUD604 — le pack ne réutilise plus une pièce périmée, et le dossier
administratif est enfin produit.

Deux défauts d'un même bloc :

1. ``empreinte_dossier()`` ne reflétait NI le contenu des textes normalisés du
   mémoire (``SectionMemoire``, lus en LIVE par ``assembler_memoire``) NI
   l'état de la checklist partenaire. Corriger une phrase du mémoire laissait
   donc l'empreinte identique : la branche REPRISE de ``producteurs_de_pack``
   reprenait la pièce ARCHIVÉE, et c'est l'ancien texte qui partait à
   l'acheteur — sans que rien ne l'indique.
2. Le producteur ``administratif`` (3e pièce bloquante d'un pli marocain)
   restait déclaré sans monteur.

Run :
    python manage.py test apps.ao.tests.test_aud604_empreinte_et_administratif -v2
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.ao.fabrique import producteurs as registre
from apps.ao.fabrique.coherence import empreinte_dossier
from apps.ao.models import (
    AppelOffre, DossierAO, LigneChecklistPartenaire, PieceAdministrative,
    PieceDossierAO, SectionMemoire,
)
from apps.records.models import Attachment
from authentication.models import Company


def pdf_d_une_page():
    """Un PDF RÉEL d'une page — produit par la même bibliothèque qui fusionne.

    Un littéral d'octets « à peu près PDF » passerait ou non selon la tolérance
    de la version de PyMuPDF installée : le test ne prouverait alors plus la
    fusion, il prouverait la tolérance du parseur.
    """
    import fitz

    document = fitz.open()
    try:
        document.new_page()
        return document.tobytes()
    finally:
        document.close()


class BaseDossier(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AUD604 Co',
                                              slug='aud604-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-604-1', objet='Empreinte',
            date_limite=date.today() + timedelta(days=30))
        self.dossier = DossierAO.objects.create(
            company=self.company, appel_offre=self.ao, reference='AODOS-604')


class TestEmpreinteSuitLeMemoire(BaseDossier):
    def setUp(self):
        super().setUp()
        self.section = SectionMemoire.objects.create(
            company=self.company, code='SEC1', titre='Méthodologie',
            corps='Nous procéderons en trois phases.', ordre=1)

    def test_modifier_le_corps_du_memoire_change_l_empreinte(self):
        avant = empreinte_dossier(self.dossier)
        self.section.corps = 'Nous procéderons en QUATRE phases.'
        self.section.save(update_fields=['corps'])
        self.assertNotEqual(
            empreinte_dossier(self.dossier), avant,
            "Le contenu du mémoire ne périme pas le pack : une pièce archivée "
            "au texte ANCIEN serait reprise et déposée.")

    def test_desactiver_une_section_change_l_empreinte(self):
        avant = empreinte_dossier(self.dossier)
        self.section.actif = False
        self.section.save(update_fields=['actif'])
        self.assertNotEqual(empreinte_dossier(self.dossier), avant)

    def test_un_simple_recalcul_ne_bouge_pas(self):
        """L'empreinte reste STABLE sans changement — sinon tout se refait."""
        self.assertEqual(empreinte_dossier(self.dossier),
                         empreinte_dossier(self.dossier))

    def test_la_section_d_une_autre_societe_ne_perime_rien(self):
        voisine = Company.objects.create(nom='AUD604 Voisine',
                                         slug='aud604-voisine')
        avant = empreinte_dossier(self.dossier)
        SectionMemoire.objects.create(
            company=voisine, code='SEC1', titre='Autre', corps='Autre texte.')
        self.assertEqual(empreinte_dossier(self.dossier), avant)


class TestEmpreinteSuitLaChecklist(BaseDossier):
    def test_cocher_un_point_change_l_empreinte(self):
        ligne = LigneChecklistPartenaire.objects.create(
            company=self.company, dossier=self.dossier, bloc='administratif',
            code='ADM1', libelle='Attestation CNSS à jour')
        avant = empreinte_dossier(self.dossier)
        ligne.faite = True
        ligne.save(update_fields=['faite'])
        self.assertNotEqual(
            empreinte_dossier(self.dossier), avant,
            "L'état de la checklist ne périme pas le pack : la checklist "
            "archivée continuerait d'annoncer un point non traité.")


class TestProducteurAdministratif(BaseDossier):
    def setUp(self):
        super().setUp()
        self.piece_pack = PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, ordre=8,
            code='08', libelle='Dossier administratif')

    def _piece_admin(self, libelle, *, avec_scan=True, expire=False):
        attachment = None
        if avec_scan:
            attachment = Attachment.objects.create(
                company=self.company,
                content_type=ContentType.objects.get_for_model(AppelOffre),
                object_id=self.ao.pk, file_key=f'k-{libelle}',
                filename=f'{libelle}.pdf')
        piece = PieceAdministrative.objects.create(
            company=self.company, type_piece='attestation_fiscale',
            libelle=libelle, attachment=attachment,
            date_emission=date.today() - timedelta(days=400 if expire else 10),
            duree_validite_jours=90)
        piece.dossiers.add(self.dossier)
        return piece

    def test_le_producteur_est_monte(self):
        self.assertTrue(registre.REGISTRE['administratif'].monte)
        self.assertEqual(
            registre.REGISTRE['administratif'].motif_indisponible, '')

    def test_la_fusion_rend_un_pdf_non_vide(self):
        self._piece_admin('RC')
        self._piece_admin('CNSS')
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(pdf_d_une_page(), None)):
            contenu = registre.REGISTRE['administratif'].octets(
                self.dossier, self.piece_pack)
        self.assertTrue(contenu)
        self.assertTrue(contenu.startswith(b'%PDF'), contenu[:16])

    def test_sans_piece_administrative_l_echec_est_nomme(self):
        with self.assertRaises(registre.ProducteurIndisponible) as ctx:
            registre.REGISTRE['administratif'].octets(
                self.dossier, self.piece_pack)
        self.assertIn('administrative', str(ctx.exception).lower())

    def test_une_piece_sans_scan_refuse_en_la_nommant(self):
        self._piece_admin('Patente', avec_scan=False)
        with self.assertRaises(registre.ProducteurIndisponible) as ctx:
            registre.REGISTRE['administratif'].octets(
                self.dossier, self.piece_pack)
        self.assertIn('Patente', str(ctx.exception))

    def test_un_scan_illisible_refuse_en_le_nommant(self):
        self._piece_admin('RC')
        with patch('apps.records.storage.fetch_attachment',
                   return_value=(None, 'objet introuvable')):
            with self.assertRaises(registre.ProducteurIndisponible) as ctx:
                registre.REGISTRE['administratif'].octets(
                    self.dossier, self.piece_pack)
        self.assertIn('RC', str(ctx.exception))

    def test_une_piece_expiree_n_entre_pas_dans_la_fusion(self):
        """Sa porte est AOF137 (BLOQUANTE) ; elle n'est pas COLLÉE ici."""
        self._piece_admin('RC périmé', expire=True)
        with self.assertRaises(registre.ProducteurIndisponible):
            registre.REGISTRE['administratif'].octets(
                self.dossier, self.piece_pack)
