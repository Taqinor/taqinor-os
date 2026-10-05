"""Tests de ``publier_documents_meryem`` (GED) — publication versionnée des
documents internes de Meryem (Guide, Protocole de rappel, Carte one-page) :
cabinet/dossier/ACL idempotents, versionnage par SHA-256, notification des
destinataires (responsable des leads + admins/directeurs), ``--dry-run``,
``--force``, et la résolution de société ambiguë.

Destination par entrée (30/09/2026) : une entrée du manifeste peut porter
``cabinet`` + ``dossier`` (dossier RACINE du cabinet, ex. « Documentation » ->
« Guides » où vit déjà le guide de la visite) ; sans eux, le comportement
historique (« Documents internes » -> « Commercial » -> « Guides de Meryem »)
est inchangé. Les classes ``DestinationPersonnaliseeTests`` (base de données,
jouées par la CI) et ``DestinationDeLEntreeTests`` (sans base) la couvrent.

Aucun mock de stockage : comme le reste de la suite GED (``test_ged.py``,
``test_xged12_photos_assemblees.py``…), le fichier passe par le VRAI pipeline
``records.storage.store_attachment`` contre le service MinIO de test (CI)."""
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.ged import services
from apps.ged.management.commands import publier_documents_meryem as cmd
from apps.ged.models import AclGed, Cabinet, Document, DocumentVersion, Folder
from apps.notifications.models import Notification
from apps.parametres.models_company import CompanyProfile
from apps.roles.models import Role
from apps.roles.permissions_registre import ROLE_PORTAIL_CLIENT

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
        # Rôle système du portail (compte EXTERNE, palier « normal » par
        # construction) : ne doit recevoir AUCUNE ACL de lecture.
        self.role_portail = Role.objects.create(
            company=self.company, nom=ROLE_PORTAIL_CLIENT, est_systeme=True,
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
        # Le rôle portail (externe) n'a aucune entrée ACL, à aucun niveau.
        self.assertFalse(AclGed.objects.filter(
            folder=dossier, role=self.role_portail).exists())

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


DOC_SUIVI = {
    'fichier': 'suivi.pdf',
    'titre': 'Guide — Le suivi commercial : étapes, réponses et suites',
    'version': '1.0',
    'description': 'Les étapes du suivi, leurs réponses et ce qui suit.',
    'cabinet': 'Documentation', 'dossier': 'Guides',
}
# Le guide de la visite existe déjà en production dans Documentation/Guides
# (déposé par ``seed_guide_visite``) : son titre est EXACTEMENT le nom du
# document, pour que la publication lui ajoute une version au lieu d'un doublon.
DOC_VISITE = {
    'fichier': 'visite.pdf',
    'titre': services.GUIDE_VISITE_NOM,
    'version': '2.0',
    'description': 'La visite technique dans le suivi commercial.',
    'cabinet': services.GUIDE_VISITE_CABINET,
    'dossier': services.GUIDE_VISITE_DOSSIER,
}


class DestinationDeLEntreeTests(SimpleTestCase):
    """``_destination`` : la règle pure qui choisit le dossier d'une entrée."""

    def test_sans_cabinet_ni_dossier_c_est_la_destination_historique(self):
        self.assertIsNone(cmd._destination({'fichier': 'a.pdf', 'titre': 'A'}))
        self.assertIsNone(cmd._destination({'cabinet': '', 'dossier': '  '}))
        self.assertIsNone(cmd._destination(None))

    def test_cabinet_et_dossier_donnent_la_destination(self):
        self.assertEqual(
            cmd._destination({'cabinet': ' Documentation ', 'dossier': 'Guides'}),
            ('Documentation', 'Guides'))

    def test_un_seul_des_deux_champs_est_refuse(self):
        for entree in ({'cabinet': 'Documentation'}, {'dossier': 'Guides'}):
            with self.assertRaises(ValueError) as ctx:
                cmd._destination(entree)
            self.assertIn('cabinet', str(ctx.exception))
            self.assertIn('dossier', str(ctx.exception))


class DestinationPersonnaliseeTests(PublicationMeryemTestsBase):
    """Entrées à ``cabinet`` + ``dossier`` : dépôt dans le dossier racine du
    cabinet, ACL et notification comme pour « Guides de Meryem »."""

    def _guides(self):
        return Folder.objects.get(
            company=self.company, cabinet__nom='Documentation', nom='Guides',
            parent__isnull=True)

    def _deposer_guide_visite_existant(self, contenu):
        """Reproduit l'état de production : le guide de la visite déjà
        déposé par ``seed_guide_visite`` (v1) dans Documentation/Guides."""
        document, _created = services.deposit_document(
            company=self.company, nom=DOC_VISITE['titre'],
            source_type=services.GUIDE_VISITE_SOURCE_TYPE,
            source_id=services.GUIDE_VISITE_SOURCE_ID,
            file_key='attachments/guide-visite-existant.pdf',
            filename='guide-visite-existant.pdf', size=len(contenu),
            mime='application/pdf', checksum=services.compute_checksum(contenu),
            cabinet_nom=services.GUIDE_VISITE_CABINET,
            folder_nom=services.GUIDE_VISITE_DOSSIER)
        return document

    def test_depose_dans_le_dossier_racine_du_cabinet_indique(self):
        self._ecrire_manifeste([DOC_SUIVI], {'suivi.pdf': b'%PDF-1.4 suivi v1'})

        call_command('publier_documents_meryem', company=self.company.slug)

        cabinet = Cabinet.objects.get(company=self.company, nom='Documentation')
        guides = self._guides()
        self.assertEqual(guides.cabinet_id, cabinet.pk)
        document = Document.objects.get(folder=guides, nom=DOC_SUIVI['titre'])
        self.assertEqual(document.description, DOC_SUIVI['description'])
        self.assertEqual(document.versions.count(), 1)
        # Aucune entrée ne va dans l'ancienne destination : elle n'est pas créée.
        self.assertFalse(Cabinet.objects.filter(
            company=self.company, nom=cmd.CABINET_NOM).exists())

    def test_acl_de_lecture_et_notification_valent_pour_ce_dossier(self):
        self._ecrire_manifeste([DOC_SUIVI], {'suivi.pdf': b'%PDF-1.4 suivi v1'})

        call_command('publier_documents_meryem', company=self.company.slug)

        guides = self._guides()
        self.assertTrue(AclGed.objects.filter(
            folder=guides, role=self.role_commercial, niveau='lecture',
            herite=True).exists())
        self.assertFalse(AclGed.objects.filter(
            folder=guides, role=self.role_directeur).exists())
        self.assertFalse(AclGed.objects.filter(
            folder=guides, role=self.role_portail).exists())
        notifs = Notification.objects.filter(company=self.company)
        self.assertEqual(notifs.count(), 2)
        self.assertEqual(
            {n.recipient_id for n in notifs},
            {self.sales_rep.pk, self.admin.pk})
        self.assertTrue(all(n.link == '/ged' for n in notifs))
        self.assertTrue(all(
            n.title.startswith('Nouveau document : ') and DOC_SUIVI['titre'] in n.title
            for n in notifs))

    def test_nouvelle_version_d_un_document_deja_present_par_nom(self):
        ancien = b'%PDF-1.4 ancienne version du guide de la visite'
        existant = self._deposer_guide_visite_existant(ancien)
        notifs_avant = Notification.objects.count()
        self._ecrire_manifeste([DOC_VISITE], {'visite.pdf': b'%PDF-1.4 visite v2'})

        call_command('publier_documents_meryem', company=self.company.slug)

        documents = Document.objects.filter(
            company=self.company, nom=DOC_VISITE['titre'])
        self.assertEqual(documents.count(), 1)  # jamais de doublon
        self.assertEqual(documents.get().pk, existant.pk)
        self.assertEqual(
            sorted(existant.versions.values_list('version', flat=True)), [1, 2])
        self.assertEqual(Notification.objects.count(), notifs_avant + 2)

    def test_meme_contenu_que_la_version_existante_ne_cree_rien(self):
        # Installation neuve : la fixture déposée par ``seed_guide_visite`` et
        # le PDF de ``docs/meryem/`` sont le même fichier.
        contenu = b'%PDF-1.4 visite identique'
        existant = self._deposer_guide_visite_existant(contenu)
        notifs_avant = Notification.objects.count()
        self._ecrire_manifeste([DOC_VISITE], {'visite.pdf': contenu})

        call_command('publier_documents_meryem', company=self.company.slug)

        self.assertEqual(existant.versions.count(), 1)
        self.assertEqual(Notification.objects.count(), notifs_avant)

    def test_deuxieme_run_ne_republie_rien(self):
        self._ecrire_manifeste([DOC_SUIVI], {'suivi.pdf': b'%PDF-1.4 suivi v1'})
        call_command('publier_documents_meryem', company=self.company.slug)
        versions_avant = DocumentVersion.objects.count()
        notifs_avant = Notification.objects.count()
        acl_avant = AclGed.objects.count()
        dossiers_avant = Folder.objects.count()

        call_command('publier_documents_meryem', company=self.company.slug)

        self.assertEqual(DocumentVersion.objects.count(), versions_avant)
        self.assertEqual(Notification.objects.count(), notifs_avant)
        self.assertEqual(AclGed.objects.count(), acl_avant)
        self.assertEqual(Folder.objects.count(), dossiers_avant)

    def test_entree_sans_cabinet_reste_dans_guides_de_meryem(self):
        # Un manifeste mixte : l'entrée historique ne bouge pas, l'autre va
        # dans Documentation/Guides.
        self._ecrire_manifeste(
            [MANIFEST[0], DOC_SUIVI],
            {'guide.pdf': _CONTENUS_V1['guide.pdf'], 'suivi.pdf': b'%PDF-1.4 suivi v1'})

        call_command('publier_documents_meryem', company=self.company.slug)

        historique = self._dossier()
        guides = self._guides()
        self.assertNotEqual(historique.pk, guides.pk)
        self.assertTrue(Document.objects.filter(
            folder=historique, nom='Guide de Meryem').exists())
        self.assertFalse(Document.objects.filter(
            folder=historique, nom=DOC_SUIVI['titre']).exists())
        self.assertTrue(Document.objects.filter(
            folder=guides, nom=DOC_SUIVI['titre']).exists())
        self.assertFalse(Document.objects.filter(
            folder=guides, nom='Guide de Meryem').exists())
        # Deux documents x deux destinataires.
        self.assertEqual(Notification.objects.filter(company=self.company).count(), 4)

    def test_cabinet_sans_dossier_fait_echouer_cette_entree_seulement(self):
        incomplete = {k: v for k, v in DOC_SUIVI.items() if k != 'dossier'}
        self._ecrire_manifeste(
            [incomplete, MANIFEST[0]],
            {'guide.pdf': _CONTENUS_V1['guide.pdf'], 'suivi.pdf': b'%PDF-1.4 suivi v1'})

        with self.assertRaises(SystemExit) as ctx:
            call_command('publier_documents_meryem', company=self.company.slug)
        self.assertEqual(ctx.exception.code, 1)

        self.assertFalse(Document.objects.filter(nom=DOC_SUIVI['titre']).exists())
        self.assertFalse(Cabinet.objects.filter(
            company=self.company, nom='Documentation').exists())
        self.assertTrue(Document.objects.filter(
            folder=self._dossier(), nom='Guide de Meryem').exists())

    def test_dry_run_annonce_sans_rien_ecrire(self):
        existant = self._deposer_guide_visite_existant(b'%PDF-1.4 ancienne version')
        self._ecrire_manifeste(
            [DOC_SUIVI, DOC_VISITE],
            {'suivi.pdf': b'%PDF-1.4 suivi v1', 'visite.pdf': b'%PDF-1.4 visite v2'})
        avant = (Document.objects.count(), DocumentVersion.objects.count(),
                 Folder.objects.count(), Cabinet.objects.count(),
                 AclGed.objects.count(), Notification.objects.count())
        sortie = StringIO()

        call_command('publier_documents_meryem', company=self.company.slug,
                     dry_run=True, stdout=sortie)

        apres = (Document.objects.count(), DocumentVersion.objects.count(),
                 Folder.objects.count(), Cabinet.objects.count(),
                 AclGed.objects.count(), Notification.objects.count())
        self.assertEqual(apres, avant)
        self.assertEqual(existant.versions.count(), 1)
        texte = sortie.getvalue()
        self.assertIn('nouveau document', texte)  # le guide du suivi
        self.assertIn('nouvelle version', texte)  # le guide de la visite


class SocieteAmbigueTests(TestCase):
    def test_plusieurs_societes_sans_option_leve_command_error(self):
        make_company('meryem-amb-a', 'Meryem Amb A')
        make_company('meryem-amb-b', 'Meryem Amb B')

        with self.assertRaises(CommandError):
            call_command('publier_documents_meryem')
