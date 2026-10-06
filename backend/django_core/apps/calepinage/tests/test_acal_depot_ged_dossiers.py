"""ACAL236 — UN dépôt GED des dossiers fusionnés, ancré sur les ENTRÉES.

Constat C-ACAL-134 : le dossier de fin de chantier était ancré sur
``layout_hash`` — une pose réelle saisie après coup (toit inchangé) retrouvait
la pièce figée à l'as-built vide — et chaque POST créait pourtant un NOUVEAU
document fusionné (11, 12, 13, 14…).

Désormais (``pack_technique.deposer_et_fusionner``, décision fondateur
D-ADOC-2 : un document client régénéré = nouvelle VERSION du même document
GED) : deux POST sans geste ⇒ le MÊME document, une seule version ; une
entrée changée (pose réelle, entrée électrique…) ⇒ une NOUVELLE VERSION du
même document, l'ancienne en historique ; total de pages incohérent ⇒ refus
nommé ; panne GED ⇒ 400 nommé, jamais un 500.

Chaîne RÉELLE : calepinage fabriqué par les vrais écrivains, client HTTP,
rendus réels (WeasyPrint/PyMuPDF), GED réelle en base de test + MinIO de la
CI. Seule la PANNE de la GED est simulée (dépendance externe).

Run :
    python manage.py test apps.calepinage.tests.test_acal_depot_ged_dossiers -v2
"""
import copy
import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.models import Calepinage, PoseReelle
from apps.calepinage.services.pack_technique import (
    PackRefuse, deposer_et_fusionner,
)
from apps.calepinage.services.resultat import modifier_resultat
from apps.crm.models import Lead
from apps.ged.services import find_document_by_source, selectors_latest_version
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from authentication.models import Company

from .acal_livrables_helpers import (
    calepinage_simule_reel, exiger_bibliotheques_pdf, patch_materiel,
)

User = get_user_model()

BASE = '/api/django/calepinage/calepinages/'


def _pdf(pages):
    import fitz

    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    octets = document.tobytes()
    document.close()
    return octets


def _texte(octets):
    import fitz

    document = fitz.open(stream=octets, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in document)
    finally:
        document.close()


class DepotGedDossiersTest(TestCase):
    def setUp(self):
        exiger_bibliotheques_pdf()
        self.societe = Company.objects.create(nom='ACAL236',
                                              slug='acal236')
        role = Role.objects.create(company=self.societe, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='acal236', password='x', company=self.societe,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        lead = Lead.objects.create(company=self.societe, nom='Toiture 236')
        pivot = calepinage_simule_reel()
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=lead.pk, titre='Remise 236',
            roof_layout=copy.deepcopy(pivot.roof_layout),
            resultat=copy.deepcopy(pivot.resultat),
            layout_hash=pivot.layout_hash or '',
            version_moteur=pivot.version_moteur or '')

    # ── outils ──────────────────────────────────────────────────────────
    def _composer(self):
        with patch_materiel():
            return self.api.post(
                f'{BASE}{self.calepinage.pk}/dossier-fin-chantier/')

    def _document(self):
        return find_document_by_source(
            self.societe, source_type='calepinage.dossier_fin_chantier.fusion',
            source_id='%s:dossier_fin_chantier' % self.calepinage.pk)

    def _versions(self, document):
        return list(document.versions.order_by('version'))

    def _octets_en_vigueur(self, document):
        from apps.records.storage import fetch_attachment

        octets, erreur = fetch_attachment(
            selectors_latest_version(document).file_key)
        self.assertIsNone(erreur)
        return octets

    def _saisir_la_pose(self):
        pan = self.calepinage.roof_layout['zones'][0].get('label') or 'a'
        PoseReelle.objects.create(
            company=self.societe, calepinage=self.calepinage, pan=pan,
            modules_poses=7, ecarts_position='Z236 rangee decalee',
            releve_le=datetime.date(2026, 10, 1))

    # ── essais ──────────────────────────────────────────────────────────
    def test_deux_post_identiques_un_seul_document_fusionne(self):
        premier = self._composer()
        self.assertEqual(premier.status_code, 201,
                         getattr(premier, 'data', premier.content[:300]))
        second = self._composer()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(premier.data['document'], second.data['document'])
        document = self._document()
        self.assertEqual(document.pk, premier.data['document'])
        self.assertEqual(len(self._versions(document)), 1)

    def test_dossier_fin_chantier_reflete_la_pose_saisie_apres_coup(self):
        premier = self._composer()
        self.assertEqual(premier.status_code, 201,
                         getattr(premier, 'data', premier.content[:300]))
        document = self._document()
        self.assertNotIn('Z236', _texte(self._octets_en_vigueur(document)))

        self._saisir_la_pose()  # conception INCHANGÉE : layout_hash aussi
        second = self._composer()
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.data['document'], premier.data['document'])
        versions = self._versions(document)
        self.assertEqual(len(versions), 2)
        self.assertNotEqual(versions[0].filename, versions[1].filename)
        self.assertIn('Z236', _texte(self._octets_en_vigueur(document)))

    def test_changement_d_entree_electrique_produit_un_dossier_neuf(self):
        self.assertEqual(self._composer().status_code, 201)
        entree = copy.deepcopy(
            self.calepinage.resultat.get('entree_electrique') or {})
        entree['dc_m'] = 37

        def saisir(resultat):
            resultat['entree_electrique'] = entree
        modifier_resultat(self.calepinage, saisir)
        self.assertEqual(self._composer().status_code, 201)
        self.assertEqual(len(self._versions(self._document())), 2)

    def test_pack_refuse_si_le_total_de_pages_ne_correspond_pas(self):
        # Une pièce qui ANNONCE 3 pages mais n'en porte que 2 : le fichier
        # fusionné (5 pages) ne fait pas la somme annoncée (6).
        pieces = [('planche', 'Planche', _pdf(3), 3),
                  ('note_calcul', 'Note de calcul', _pdf(2), 3)]
        with self.assertRaises(PackRefuse) as capture:
            deposer_et_fusionner(
                self.calepinage, pieces=pieces, famille='pack_technique',
                nom='Dossier technique', folder_nom='Dossiers techniques',
                company=self.societe, empreinte='f' * 64)
        self.assertEqual(capture.exception.piece, 'pieces')
        self.assertIsNone(find_document_by_source(
            self.societe, source_type='calepinage.pack_technique.fusion',
            source_id='%s:pack_technique' % self.calepinage.pk))

    def test_panne_de_lecture_ged_donne_400_nomme(self):
        # La GED est une dépendance EXTERNE : seule sa panne est simulée.
        with mock.patch('apps.ged.services.find_document_by_source',
                        side_effect=ValueError('lecture MinIO impossible')):
            reponse = self._composer()
        self.assertEqual(reponse.status_code, 400,
                         getattr(reponse, 'data', reponse.content[:300]))
        self.assertIn('ged', reponse.data)
        self.assertIn('lecture MinIO impossible', reponse.data['ged'])
