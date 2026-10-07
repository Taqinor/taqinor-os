"""ADOC62 — les dossiers d'un calepinage sont UN Document GED versionné.

D-ADOC-2 amende ACAL236 (fondateur 07/10/2026) : l'empreinte des entrées
décide toujours s'il faut re-rendre, mais la GED garde UN SEUL Document par
dossier — nouvelle VERSION quand le contenu change, aucune quand il est
identique, jamais de « Dossier technique — X » homonymes. L'ancienne version
reste en historique ; le Document (donc ``dossier.document_id``) est stable.

GED RÉELLE en base de test (+ MinIO de la CI) ; rendus = vrais PDF PyMuPDF
injectés par le seam ``rendus=``.

Run :
    python manage.py test apps.calepinage.tests.test_adoc_pack_version -v2
"""
from types import SimpleNamespace

from django.apps import apps as django_apps
from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.pack_technique import (
    construire_dossier_fin_chantier, construire_pack,
)
from apps.calepinage.services.reglementaire import construire_pack_dossier
from apps.crm.models import Lead
from authentication.models import Company

try:
    import fitz
except ImportError:  # pragma: no cover - dépend de l'environnement
    fitz = None


def _pdf(pages, marque=0):
    document = fitz.open()
    for _ in range(pages):
        page = document.new_page()
        page.insert_text((72, 72), 'ADOC62 %s' % marque)
    octets = document.tobytes()
    document.close()
    return octets


class _Base(TestCase):
    def setUp(self):
        if fitz is None:
            self.skipTest('PyMuPDF absent de cet environnement')
        self.societe = Company.objects.create(nom='ADOC62', slug='adoc62')
        lead = Lead.objects.create(company=self.societe, nom='Toiture 62')
        self.calepinage = Calepinage.objects.create(
            company=self.societe, lead_id=lead.pk, titre='Remise 62',
            roof_layout={})

    def _documents(self, prefixe):
        Document = django_apps.get_model('ged', 'Document')
        return list(Document.objects.filter(
            company=self.societe, nom__startswith=prefixe).order_by('id'))

    def _versions(self, document):
        return list(document.versions.order_by('version'))


class PackTechniqueVersionneTest(_Base):
    def _rendus(self, marque):
        return {'planche': lambda: _pdf(1, marque),
                'note_calcul': lambda: _pdf(2, marque)}

    def _construire(self, marque, empreinte):
        return construire_pack(self.calepinage, rendus=self._rendus(marque),
                               empreinte=empreinte)

    def test_pack_reconstruit_un_seul_document_versionne(self):
        premier = self._construire(1, 'a' * 16)
        second = self._construire(2, 'a' * 16)  # autre rendu, mêmes entrées
        # D-ADOC-2 amende ACAL236 (fondateur 07/10/2026) : entrées
        # inchangées => 1 Document, 1 version.
        self.assertEqual(premier['document'].pk, second['document'].pk)
        documents = self._documents('Dossier technique')
        self.assertEqual(len(documents), 1)
        self.assertEqual(len(self._versions(documents[0])), 1)

        # Entrées changées => toujours 1 Document, 2 versions.
        troisieme = self._construire(3, 'b' * 16)
        self.assertEqual(troisieme['document'].pk, premier['document'].pk)
        documents = self._documents('Dossier technique')
        self.assertEqual(len(documents), 1)
        versions = self._versions(documents[0])
        self.assertEqual([v.version for v in versions], [1, 2])
        self.assertNotEqual(versions[0].filename, versions[1].filename)
        self.assertTrue(versions[0].file_key)  # l'ancien rendu reste


class DossierFinChantierVersionneTest(_Base):
    def _construire(self, marque, empreinte):
        rendus = {'plan_pose': lambda: _pdf(1, marque),
                  'document_asbuilt': lambda: _pdf(1, marque)}
        return construire_dossier_fin_chantier(
            self.calepinage, rendus=rendus, empreinte=empreinte)

    def test_dossier_fin_chantier_versionne(self):
        premier = self._construire(1, 'a' * 16)
        self._construire(2, 'a' * 16)
        documents = self._documents('Dossier de fin de chantier')
        self.assertEqual(len(documents), 1)
        self.assertEqual(len(self._versions(documents[0])), 1)

        apres = self._construire(3, 'b' * 16)
        self.assertEqual(apres['document'].pk, premier['document'].pk)
        documents = self._documents('Dossier de fin de chantier')
        self.assertEqual(len(documents), 1)
        self.assertEqual(len(self._versions(documents[0])), 2)


class DossierReglementaireVersionneTest(_Base):
    def _dossier(self):
        gabarit = SimpleNamespace(pk=3, intitule='Dossier raccordement 62',
                                  fichier_present=True)
        return SimpleNamespace(pk=62, calepinage=self.calepinage,
                               company=self.societe, gabarit=gabarit)

    def _construire(self, marque, empreinte):
        rendus = {'planche': lambda: _pdf(1, marque),
                  'note_calcul': lambda: _pdf(1, marque)}
        return construire_pack_dossier(
            self._dossier(), rendus=rendus, empreinte=empreinte)

    def test_dossier_reglementaire_versionne(self):
        premier = self._construire(1, 'a' * 16)
        self._construire(2, 'a' * 16)
        documents = self._documents('Dossier raccordement 62')
        self.assertEqual(len(documents), 1)
        self.assertEqual(len(self._versions(documents[0])), 1)

        apres = self._construire(3, 'b' * 16)
        # dossier.document_id (posé par la vue depuis ce retour) est stable.
        self.assertEqual(apres['document'].pk, premier['document'].pk)
        documents = self._documents('Dossier raccordement 62')
        self.assertEqual(len(documents), 1)
        self.assertEqual(len(self._versions(documents[0])), 2)
