"""Tests de ``publier_documents_meryem`` (GED) — publication versionnée des
documents internes de Meryem (Guide, Protocole de rappel, Carte one-page) :
cabinet/dossier/ACL idempotents, versionnage par SHA-256, notification des
destinataires (responsable des leads + admins/directeurs), ``--dry-run``,
``--force``, et la résolution de société ambiguë.

Aucun mock de stockage : comme le reste de la suite GED (``test_ged.py``,
``test_xged12_photos_assemblees.py``…), le fichier passe par le VRAI pipeline
``records.storage.store_attachment`` contre le service MinIO de test (CI)."""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from authentication.models import Company
from apps.ged.management.commands import publier_documents_meryem as cmd
from apps.ged.models import AclGed, Cabinet, Document, DocumentVersion, Folder
from apps.notifications.models import Notification
from apps.parametres.models_company import CompanyProfile
from apps.roles.models import Role

User = get_user_model()

MANIFEST = [
    {'fichier': 'guide.pdf', 'titre': 'Guide de Meryem', 'version': '2.1',
     'description': 'Guide de vente et de suivi des leads.'},
    {'fichier': 'protocole.pdf', 'titre': 'Protocole de rappel',
     'version': '3.0', 'description': 'Cadence des relances.'},
    {'fichier': 'carte.pdf', 'titre': 'Carte de Meryem', 'version': '1.0',
     'description': 'Repères en une page.'},
]

_CONTENUS_V1 = {
    'guide.pdf': b'%PDF-1.4 guide v1',
    'protocole.pdf': b'%PDF-1.4 protocole v1',
    'carte.pdf': b'%PDF-1.4 carte v1',
}


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PublicationMeryemTestsBase(TestCase):
    def setUp(self):
        self.company = make_company('meryem-pub', 'Meryem Pub')

        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.docs_dir = Path(self._tmpdir.name)
        patcher = mock.patch.object(cmd, 'MERYEM_DOCS_DIR', self.docs_dir)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._ecrire_manifeste(MANIFEST, _CONTENUS_V1)

        self.sales_rep = User.objects.create_user(
            username='meryem', password='x', company=self.company,
            role_legacy='normal', is_active=True)
        self.admin = User.objects.create_user(
            username='admin-meryem', password='x', company=self.company,
            role_legacy='admin', is_active=True)
        CompanyProfile.objects.create(
            company=self.company, responsable_defaut_leads=self.sales_rep)

        # Un rôle « normal/responsable » (doit recevoir l'ACL) et un rôle
        # admin (Directeur — ne doit RECEVOIR aucune entrée ACL, il a déjà
        # l'accès implicite `is_admin_role`).
        self.role_commercial = Role.objects.create(
            company=self.company, nom='Commercial', est_systeme=True,
            permissions=[])
        self.role_directeur = Role.objects.create(
            company=self.company, nom='Directeur', est_systeme=True,
            permissions=[])

    def _ecrire_manifeste(self, manifest, contenus):
        (self.docs_dir / cmd.MANIFEST_NOM).write_text(
            json.dumps(manifest), encoding='utf-8')
        for fichier, contenu in contenus.items():
            (self.docs_dir / fichier).write_bytes(contenu)

    def _dossier(self):
        return Folder.objects.get(
            company=self.company, cabinet__nom=cmd.CABINET_NOM,
            nom=cmd.DOSSIER_MERYEM_NOM)


class PremierRunTests(PublicationMeryemTestsBase):
    def test_cree_cabinet_dossier_acl_documents_versions_et_notifie(self):
        call_command('publier_documents_meryem', company=self.company.slug)

        cabinet = Cabinet.objects.get(company=self.company, nom=cmd.CABINET_NOM)
        racine = Folder.objects.get(
            company=self.company, cabinet=cabinet, parent__isnull=True,
            nom=cmd.DOSSIER_RACINE_NOM)
        dossier = Folder.objects.get(
            company=self.company, cabinet=cabinet, parent=racine,
            nom=cmd.DOSSIER_MERYEM_NOM)

        self.assertEqual(Document.objects.filter(folder=dossier).count(), 3)
        self.assertEqual(
            DocumentVersion.objects.filter(document__folder=dossier).count(), 3)

        # ACL : le rôle Commercial (normal) reçoit la lecture, Directeur (admin) non.
        self.assertTrue(AclGed.objects.filter(
            folder=dossier, role=self.role_commercial, niveau='lecture',
            herite=True).exists())
        self.assertFalse(AclGed.objects.filter(
            folder=dossier, role=self.role_directeur).exists())

        # Notifications : 3 documents x 2 destinataires (sales rep + admin).
        notifs = Notification.objects.filter(company=self.company)
        self.assertEqual(notifs.count(), 6)
        self.assertEqual(
            notifs.filter(recipient=self.sales_rep).count(), 3)
        self.assertEqual(notifs.filter(recipient=self.admin).count(), 3)
        titres_admin = list(
            notifs.filter(recipient=self.admin).values_list('title', flat=True))
        self.assertTrue(any('Guide de Meryem' in t for t in titres_admin))
        self.assertTrue(
            all(t.startswith('Nouveau document : ') for t in titres_admin))
        self.assertTrue(all(n.link == '/ged' for n in notifs))

    def test_deuxieme_run_ne_cree_rien_et_ne_notifie_personne(self):
        call_command('publier_documents_meryem', company=self.company.slug)
        docs_avant = Document.objects.count()
        versions_avant = DocumentVersion.objects.count()
        acl_avant = AclGed.objects.count()
        notifs_avant = Notification.objects.count()
        cabinets_avant = Cabinet.objects.count()
        dossiers_avant = Folder.objects.count()

        call_command('publier_documents_meryem', company=self.company.slug)

        self.assertEqual(Document.objects.count(), docs_avant)
        self.assertEqual(DocumentVersion.objects.count(), versions_avant)
        self.assertEqual(AclGed.objects.count(), acl_avant)
        self.assertEqual(Notification.objects.count(), notifs_avant)
        self.assertEqual(Cabinet.objects.count(), cabinets_avant)
        self.assertEqual(Folder.objects.count(), dossiers_avant)

    def test_fichier_modifie_cree_une_nouvelle_version_et_notifie(self):
        call_command('publier_documents_meryem', company=self.company.slug)
        notifs_avant = Notification.objects.count()

        # Contenu du Guide change ; les deux autres restent identiques.
        (self.docs_dir / 'guide.pdf').write_bytes(b'%PDF-1.4 guide v2 (edite)')

        call_command('publier_documents_meryem', company=self.company.slug)

        guide = Document.objects.get(folder=self._dossier(), nom='Guide de Meryem')
        self.assertEqual(guide.versions.count(), 2)
        autre = Document.objects.get(
            folder=self._dossier(), nom='Protocole de rappel')
        self.assertEqual(autre.versions.count(), 1)
        # Seul le document changé renotifie (2 destinataires).
        self.assertEqual(Notification.objects.count(), notifs_avant + 2)

    def test_force_republie_et_renotifie_meme_sans_changement(self):
        call_command('publier_documents_meryem', company=self.company.slug)
        notifs_avant = Notification.objects.count()

        call_command(
            'publier_documents_meryem', company=self.company.slug, force=True)

        dossier = self._dossier()
        for titre in ('Guide de Meryem', 'Protocole de rappel', 'Carte de Meryem'):
            doc = Document.objects.get(folder=dossier, nom=titre)
            self.assertEqual(doc.versions.count(), 2)
        self.assertEqual(Notification.objects.count(), notifs_avant + 6)

    def test_dry_run_necrit_rien(self):
        call_command(
            'publier_documents_meryem', company=self.company.slug, dry_run=True)

        self.assertEqual(Cabinet.objects.filter(company=self.company).count(), 0)
        self.assertEqual(Folder.objects.filter(company=self.company).count(), 0)
        self.assertEqual(Document.objects.filter(company=self.company).count(), 0)
        self.assertEqual(
            DocumentVersion.objects.filter(company=self.company).count(), 0)
        self.assertEqual(AclGed.objects.filter(company=self.company).count(), 0)
        self.assertEqual(Notification.objects.filter(company=self.company).count(), 0)

    def test_destinataires_dedupliques_quand_responsable_est_admin(self):
        # Le responsable des leads EST l'admin : un seul destinataire, jamais deux.
        profile = CompanyProfile.objects.get(company=self.company)
        profile.responsable_defaut_leads = self.admin
        profile.save(update_fields=['responsable_defaut_leads'])

        call_command('publier_documents_meryem', company=self.company.slug)

        notifs = Notification.objects.filter(company=self.company)
        self.assertEqual(notifs.count(), 3)
        self.assertEqual(notifs.filter(recipient=self.admin).count(), 3)

    def test_entree_avec_fichier_manquant_est_best_effort(self):
        # Le fichier du Protocole disparaît : les 2 autres doivent quand même
        # être publiés, et le processus sort en erreur (SystemExit 1).
        (self.docs_dir / 'protocole.pdf').unlink()

        with self.assertRaises(SystemExit) as ctx:
            call_command('publier_documents_meryem', company=self.company.slug)
        self.assertEqual(ctx.exception.code, 1)

        dossier = self._dossier()
        self.assertTrue(
            Document.objects.filter(folder=dossier, nom='Guide de Meryem').exists())
        self.assertTrue(
            Document.objects.filter(folder=dossier, nom='Carte de Meryem').exists())
        self.assertFalse(
            Document.objects.filter(
                folder=dossier, nom='Protocole de rappel').exists())


class SocieteAmbigueTests(TestCase):
    def test_plusieurs_societes_sans_option_leve_command_error(self):
        make_company('meryem-amb-a', 'Meryem Amb A')
        make_company('meryem-amb-b', 'Meryem Amb B')

        with self.assertRaises(CommandError):
            call_command('publier_documents_meryem')
