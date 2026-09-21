"""Tests CONTRAT19 — Dépôt en GED des versions & PDF signés.

Couvre :
- La création/finalisation d'une version de contrat (``creer_version``) dépose
  automatiquement un document GED dans la société du contrat.
- La bascule « signé » (qui fige un instantané immuable) fait, elle aussi,
  atterrir le contrat signé dans la GED.
- Le dépôt est IDEMPOTENT : redéposer la MÊME version ne crée pas de doublon GED.
- Isolation multi-tenant : le document GED est dans la société du contrat ; un
  contrat d'une autre société dépose dans SA propre société (jamais de fuite).
- Le dépôt est BEST-EFFORT : un échec côté GED ne casse jamais la création de la
  version (la version est tout de même créée).

Le chemin de dépôt testé ici n'utilise QUE ``file_key`` / pointeur de version
(jamais d'octets bruts), donc aucun appel MinIO n'est nécessaire — les tests
restent focalisés sur l'orchestration cross-app contrats → ged.services.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.contrats import services
from apps.contrats.models import Contrat, PartieContrat, VersionContrat
from apps.ged.models import Document
from apps.ged.services import SOURCE_ID_KEY, SOURCE_TYPE_KEY

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={"nom": nom})
    return company


def make_user(company, username, role="admin"):
    return User.objects.create_user(
        username=username, password="x", company=company, role_legacy=role)


def make_contrat(company, statut="en_approbation", objet="Contrat test",
                 reference="CT-001", avec_parties=True):
    contrat = Contrat.objects.create(
        company=company, objet=objet, reference=reference,
        montant=Decimal("80000"), type_contrat="vente", statut=statut,
        date_debut=timezone.localdate() + timedelta(days=30))
    if avec_parties:
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="client", nom="Client SARL", ordre=0)
        PartieContrat.objects.create(
            company=company, contrat=contrat,
            type_partie="prestataire", nom="Taqinor", ordre=1)
    return contrat


def _ged_docs(company):
    return Document.objects.filter(company=company)


class DepotVersionGedTests(TestCase):
    def setUp(self):
        self.co = make_company("ged-dep", "GedDep")
        self.user = make_user(self.co, "ged-dep-admin", role="admin")
        self.contrat = make_contrat(
            self.co, objet="Contrat solaire 12 kWc", reference="CT-2026-001")

    def test_creer_version_depose_un_document_ged(self):
        v = services.creer_version(self.contrat, cree_par=self.user)
        docs = _ged_docs(self.co)
        self.assertEqual(docs.count(), 1)
        doc = docs.first()
        # Société posée côté serveur (celle du contrat).
        self.assertEqual(doc.company_id, self.co.id)
        # La trace de l'objet source pointe vers cette version (idempotence).
        self.assertEqual(doc.custom_data.get(SOURCE_TYPE_KEY),
                         'contrats.versioncontrat')
        self.assertEqual(doc.custom_data.get(SOURCE_ID_KEY), v.pk)
        # Le nom du document référence le contrat + le numéro de version.
        self.assertIn('CT-2026-001', doc.nom)
        self.assertIn('version 1', doc.nom)
        # Le document a bien une première version GED.
        self.assertEqual(doc.versions.count(), 1)

    def test_depot_idempotent_pas_de_doublon(self):
        v = services.creer_version(self.contrat, cree_par=self.user)
        # Redéposer la MÊME version ne crée pas un second document GED.
        doc1, created1 = services.deposer_version_en_ged(v)
        self.assertFalse(created1)
        doc2, created2 = services.deposer_version_en_ged(v)
        self.assertFalse(created2)
        self.assertEqual(doc1.pk, doc2.pk)
        self.assertEqual(_ged_docs(self.co).count(), 1)

    def test_versions_distinctes_deposent_des_documents_distincts(self):
        services.creer_version(self.contrat, cree_par=self.user)
        services.creer_version(self.contrat, cree_par=self.user)
        # Deux versions distinctes → deux documents GED distincts.
        self.assertEqual(_ged_docs(self.co).count(), 2)

    def test_fichier_key_pdf_depose_la_cle(self):
        v = services.creer_version(
            self.contrat, fichier_key="contrats/2026/signe.pdf",
            motif="Signature", cree_par=self.user)
        doc = _ged_docs(self.co).get(
            custom_data__contains={SOURCE_ID_KEY: v.pk})
        gv = doc.versions.first()
        self.assertEqual(gv.file_key, "contrats/2026/signe.pdf")
        self.assertEqual(gv.mime, "application/pdf")


class DepotIsolationTests(TestCase):
    def test_isolation_societe(self):
        co_a = make_company("ged-iso-a", "IsoA")
        co_b = make_company("ged-iso-b", "IsoB")
        ua = make_user(co_a, "iso-a-admin", role="admin")
        ub = make_user(co_b, "iso-b-admin", role="admin")
        ca = make_contrat(co_a, reference="A-1")
        cb = make_contrat(co_b, reference="B-1")
        services.creer_version(ca, cree_par=ua)
        services.creer_version(cb, cree_par=ub)
        # Chaque dépôt atterrit dans SA société — jamais de fuite cross-société.
        self.assertEqual(Document.objects.filter(company=co_a).count(), 1)
        self.assertEqual(Document.objects.filter(company=co_b).count(), 1)
        self.assertEqual(
            Document.objects.filter(company=co_a).first().company_id, co_a.id)


class DepotSignatureTests(TestCase):
    def setUp(self):
        self.co = make_company("ged-sig", "GedSig")
        self.user = make_user(self.co, "ged-sig-admin", role="admin")
        self.contrat = make_contrat(self.co, reference="SIG-1")

    def test_bascule_signe_depose_le_contrat_signe_en_ged(self):
        # Client signe (partiel — pas de bascule, pas de version, pas de dépôt).
        services.signer_contrat(
            self.contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        self.assertEqual(_ged_docs(self.co).count(), 0)
        # Prestataire signe → bascule « signé » → instantané figé → dépôt GED.
        res = services.signer_contrat(
            self.contrat, signataire_nom="Taqinor",
            role_signataire="prestataire", auteur=self.user)
        self.assertTrue(res["contrat_signe"])
        # La version figée à la signature a atterri dans la GED.
        self.assertEqual(_ged_docs(self.co).count(), 1)
        v = VersionContrat.objects.filter(contrat=self.contrat).first()
        doc = _ged_docs(self.co).first()
        self.assertEqual(doc.custom_data.get(SOURCE_ID_KEY), v.pk)

    def test_deposer_contrat_signe_explicite_idempotent(self):
        services.signer_contrat(
            self.contrat, signataire_nom="Client", role_signataire="client",
            auteur=self.user)
        services.signer_contrat(
            self.contrat, signataire_nom="Taqinor",
            role_signataire="prestataire", auteur=self.user)
        sig = self.contrat.signatures.first()
        # Re-déposer le contrat signé explicitement ne crée pas de doublon.
        doc, created = services.deposer_contrat_signe_en_ged(sig)
        self.assertFalse(created)
        self.assertEqual(_ged_docs(self.co).count(), 1)


class DepotBestEffortTests(TestCase):
    def setUp(self):
        self.co = make_company("ged-be", "GedBE")
        self.user = make_user(self.co, "ged-be-admin", role="admin")
        self.contrat = make_contrat(self.co, reference="BE-1")

    def test_echec_ged_ne_casse_pas_la_creation_de_version(self):
        # Si le dépôt GED lève, la version doit tout de même être créée.
        with mock.patch.object(
            services, "deposer_version_en_ged",
            side_effect=RuntimeError("ged indisponible"),
        ):
            v = services.creer_version(self.contrat, cree_par=self.user)
        self.assertIsNotNone(v.pk)
        self.assertEqual(
            VersionContrat.objects.filter(contrat=self.contrat).count(), 1)
        # Aucun document GED n'a été déposé (le dépôt a échoué silencieusement).
        self.assertEqual(_ged_docs(self.co).count(), 0)
