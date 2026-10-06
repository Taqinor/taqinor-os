"""ADOC128 — un document obsolète (ou archivé, côté partenaire) sort du portail.

Rejoue la sonde #101 de l'audit documents (2026-10-05) : approuvé, obsolète
et archivé étaient tous listés et téléchargés (200) dans les ressources
partenaires. Les deux sélecteurs (client, partenaire) sont la seule source
des listes, détails, téléchargements, exports et recherches du portail.
"""
from django.test import TestCase

from apps.crm.models import Client
from apps.ged import selectors
from apps.ged.models import AclGed, Cabinet, Document, Folder
from apps.roles.models import Role
from apps.roles.permissions_registre import ROLE_PORTAIL_PARTENAIRE
from authentication.models import Company


class PortailCycleVieTests(TestCase):
    def setUp(self):
        self.co = Company.objects.get_or_create(
            slug='adoc128', defaults={'nom': 'ADOC128'})[0]
        cab = Cabinet.objects.create(company=self.co, nom='Cab')
        self.folder = Folder.objects.create(
            company=self.co, cabinet=cab, nom='R')
        self.role, _ = Role.objects.get_or_create(
            company=self.co, nom=ROLE_PORTAIL_PARTENAIRE)
        self.docs = {}
        for statut in ('approuve', 'obsolete', 'archive'):
            doc = Document.objects.create(
                company=self.co, folder=self.folder, nom=f'res-{statut}')
            Document.objects.filter(pk=doc.pk).update(statut=statut)
            AclGed.objects.create(company=self.co, document=doc,
                                  role=self.role, niveau='lecture')
            self.docs[statut] = doc
        self.client_c1 = Client.objects.create(
            company=self.co, nom='C1', email='c1@example.com')

    def _partage_client(self, statut):
        doc = Document.objects.create(
            company=self.co, folder=self.folder, nom=f'client-{statut}')
        Document.objects.filter(pk=doc.pk).update(statut=statut)
        AclGed.objects.create(company=self.co, document=doc,
                              client=self.client_c1, niveau='lecture')
        return doc

    def test_ressource_obsolete_absente(self):
        liste = list(selectors.ressources_partenaire_portail(self.co))
        self.assertIn(self.docs['approuve'], liste)
        self.assertNotIn(self.docs['obsolete'], liste)
        self.assertIsNone(selectors.ressource_partenaire_portail(
            self.co, self.docs['obsolete'].pk))
        self.assertIsNotNone(selectors.ressource_partenaire_portail(
            self.co, self.docs['approuve'].pk))

    def test_ressource_archivee_absente(self):
        self.assertNotIn(self.docs['archive'],
                         list(selectors.ressources_partenaire_portail(self.co)))
        self.assertIsNone(selectors.ressource_partenaire_portail(
            self.co, self.docs['archive'].pk))
        # Repassée en « approuve », la ressource réapparaît.
        Document.objects.filter(pk=self.docs['archive'].pk).update(
            statut='approuve')
        self.assertIsNotNone(selectors.ressource_partenaire_portail(
            self.co, self.docs['archive'].pk))

    def test_document_client_obsolete_absent(self):
        obsolete = self._partage_client('obsolete')
        archive = self._partage_client('archive')
        approuve = self._partage_client('approuve')
        liste = list(selectors.documents_partages_client_portail(
            self.co, self.client_c1.pk))
        self.assertNotIn(obsolete, liste)
        self.assertIn(archive, liste)
        self.assertIn(approuve, liste)
        self.assertIsNone(selectors.document_partage_client_portail(
            self.co, self.client_c1.pk, obsolete.pk))
