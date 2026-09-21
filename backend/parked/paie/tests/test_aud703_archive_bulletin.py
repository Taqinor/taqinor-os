"""AUD703 — le bulletin VALIDÉ est archivé en artefact immuable (doctrine D9).

ÉTAT AVANT LE FIX. Un grep exhaustif ``minio|default_storage|FileField|
upload_to|boto3|S3`` sur ``apps/paie/*.py`` ne renvoyait RIEN : les deux
endpoints ``pdf`` (gestionnaire et coffre-fort employé) appelaient
``render_bulletin_pdf`` à CHAQUE requête, rien n'était stocké. Or
``SNAPSHOT_FIELDS`` ne gèle que les MONTANTS : ``ProfilPaieSerializer`` laisse
``numero_cnss``/``rib``/``banque`` écrivables et ``PeriodePaieSerializer``
laisse ``date_paiement`` écrivable. Un PATCH banal après validation changeait
donc le contenu de TOUTE réimpression du même bulletin, sans trace ni
empreinte à comparer.

Ces tests n'ont besoin ni de WeasyPrint ni de MinIO : le rendu et l'entrepôt
sont remplacés par des doublures (le « PDF » est le HTML lui-même, ce qui rend
la divergence de contenu directement observable).
"""
from decimal import Decimal
from unittest import mock

from django.test import TestCase

from authentication.models import Company
from apps.paie import builders
from apps.paie.models import BulletinPaie, PeriodePaie, ProfilPaie
from apps.paie.services import (
    ensure_defaults,
    generer_bulletin,
    valider_bulletin,
)
from apps.rh.models import DossierEmploye


class ArchiveBulletinTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud703', nom='AUD703')
        ensure_defaults(self.co)
        self.dossier = DossierEmploye.objects.create(
            company=self.co, matricule='ARC1', nom='Archive', prenom='Test')
        self.profil = ProfilPaie.objects.create(
            company=self.co, employe=self.dossier,
            type_remuneration=ProfilPaie.TYPE_MENSUEL,
            salaire_base=Decimal('10000'),
            numero_cnss='11112222', affilie_cnss=True, affilie_amo=True)
        self.periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=6)
        self.bulletin = generer_bulletin(self.profil, self.periode)
        valider_bulletin(self.bulletin)
        self.bulletin.refresh_from_db()
        # Entrepôt en mémoire + « PDF » = le HTML rendu (contenu observable).
        self.entrepot = {}
        patches = [
            mock.patch.object(builders, '_html_to_pdf',
                              side_effect=lambda html: html.encode('utf-8')),
            mock.patch.object(builders, '_archive_put',
                              side_effect=self.entrepot.__setitem__),
            mock.patch.object(builders, '_archive_get',
                              side_effect=self.entrepot.__getitem__),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_premiere_emission_archive_et_empreinte(self):
        self.assertEqual(self.bulletin.pdf_archive_cle, '')
        pdf = builders.bulletin_pdf_a_servir(self.bulletin)
        self.bulletin.refresh_from_db()
        self.assertTrue(self.bulletin.pdf_archive_cle)
        self.assertEqual(len(self.bulletin.pdf_sha256), 64)
        self.assertIsNotNone(self.bulletin.pdf_archive_le)
        self.assertIn(self.bulletin.pdf_archive_cle, self.entrepot)
        self.assertEqual(self.entrepot[self.bulletin.pdf_archive_cle], pdf)

    def test_cle_prefixee_par_la_societe(self):
        cle = builders.cle_archive_bulletin(self.bulletin)
        self.assertEqual(
            cle,
            f'paie/{self.co.id}/bulletins/2026/06/{self.bulletin.id}.pdf')

    def test_reemission_apres_patch_identite_sert_larchive(self):
        """LE CŒUR DU CONSTAT : le n° CNSS change, le document remis NON."""
        remis = builders.bulletin_pdf_a_servir(self.bulletin)
        self.bulletin.refresh_from_db()
        empreinte = self.bulletin.pdf_sha256
        self.assertIn(b'11112222', remis)

        # Un PATCH banal, autorisé par le serializer, sur un bulletin VALIDÉ.
        self.profil.numero_cnss = '99998888'
        self.profil.save(update_fields=['numero_cnss'])
        self.bulletin.refresh_from_db()

        rejoue = builders.bulletin_pdf_a_servir(self.bulletin)
        self.bulletin.refresh_from_db()
        # Avant AUD703 : re-rendu → le NOUVEAU numéro, aucune empreinte.
        self.assertEqual(rejoue, remis)
        self.assertIn(b'11112222', rejoue)
        self.assertNotIn(b'99998888', rejoue)
        self.assertEqual(self.bulletin.pdf_sha256, empreinte)

    def test_brouillon_toujours_rendu_a_la_volee(self):
        periode = PeriodePaie.objects.create(
            company=self.co, annee=2026, mois=7)
        brouillon = generer_bulletin(self.profil, periode)
        self.assertEqual(brouillon.statut, BulletinPaie.STATUT_BROUILLON)
        builders.bulletin_pdf_a_servir(brouillon)
        brouillon.refresh_from_db()
        self.assertEqual(brouillon.pdf_archive_cle, '')
        self.assertEqual(self.entrepot, {})

    def test_archive_illisible_echoue_explicitement(self):
        """Mieux vaut un échec net qu'un document divergent."""
        builders.bulletin_pdf_a_servir(self.bulletin)
        self.bulletin.refresh_from_db()
        self.entrepot.clear()
        with self.assertRaises(builders.ArchiveBulletinIndisponible):
            builders.bulletin_pdf_a_servir(self.bulletin)

    def test_entrepot_indisponible_ne_pretend_pas_archiver(self):
        with mock.patch.object(builders, '_archive_put',
                               side_effect=OSError('entrepôt injoignable')):
            builders.bulletin_pdf_a_servir(self.bulletin)
        self.bulletin.refresh_from_db()
        # Empreinte posée (preuve de ce qui a été rendu), mais AUCUNE clé :
        # on n'annonce jamais une archive qui n'existe pas.
        self.assertEqual(self.bulletin.pdf_archive_cle, '')
        self.assertEqual(len(self.bulletin.pdf_sha256), 64)
