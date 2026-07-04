"""XGED21 — ACL automatiques pilotées par métadonnées.

Couvre :
  * poser le tag "Paie" restreint instantanément la visibilité au rôle RH ;
  * retirer le tag restaure l'accès par défaut (aucune ACL directe) ;
  * l'admin n'est jamais affecté (contournement GED19 inconditionnel) ;
  * non-régression GED19 (une ACL directe reste prioritaire au même scope) ;
  * isolation société.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.ged import selectors
from apps.ged.models import (
    Cabinet, Document, DocumentTag, Folder, RegleAclMetadonnee,
)
from apps.roles.models import Role

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_role(company, nom):
    return Role.objects.create(company=company, nom=nom)


def make_user(company, username, role=None, role_legacy='normal'):
    return User.objects.create_user(
        username=username, password='x', company=company, role=role,
        role_legacy=role_legacy)


class XGed21Base(TestCase):
    def setUp(self):
        self.co_a = make_company('xged21-a', 'Xged21 A')
        self.role_rh = make_role(self.co_a, 'RH')
        self.role_autre = make_role(self.co_a, 'Commercial')
        self.user_rh = make_user(
            self.co_a, 'xged21-rh', role=self.role_rh)
        self.user_autre = make_user(
            self.co_a, 'xged21-autre', role=self.role_autre)
        self.admin = make_user(
            self.co_a, 'xged21-admin', role=None, role_legacy='admin')
        self.cab_a = Cabinet.objects.create(company=self.co_a, nom='Admin')
        self.folder_a = Folder.objects.create(
            company=self.co_a, cabinet=self.cab_a, nom='RH')
        self.tag_paie = DocumentTag.objects.create(
            company=self.co_a, nom='Paie', slug='paie')
        self.doc = Document.objects.create(
            company=self.co_a, folder=self.folder_a, nom='bulletin-042.pdf')


class RegleAclMetadonneeTests(XGed21Base):
    def test_sans_regle_aucun_effet(self):
        """RÉTROCOMPATIBLE : sans règle, acl_effective renvoie None (GED19
        backward-compat inchangé)."""
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_autre))

    def test_tag_paie_restreint_a_role_rh(self):
        RegleAclMetadonnee.objects.create(
            company=self.co_a, nom='Paie → RH',
            condition_group={
                'op': 'and', 'conditions': [
                    {'field': 'tags', 'operator': 'contains', 'value': 'paie'},
                ],
            },
            role=self.role_rh, niveau='lecture')
        self.doc.tag_assignments.create(company=self.co_a, tag=self.tag_paie)

        # Le rôle RH obtient l'accès lecture immédiatement.
        self.assertEqual(
            selectors.acl_effective(self.doc, self.user_rh), 'lecture')
        # Un autre rôle n'est pas ciblé par la règle → non gouverné.
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_autre))

    def test_retirer_le_tag_restaure_comportement_par_defaut(self):
        RegleAclMetadonnee.objects.create(
            company=self.co_a, nom='Paie → RH',
            condition_group={
                'field': 'tags', 'operator': 'contains', 'value': 'paie',
            },
            role=self.role_rh, niveau='lecture')
        assignment = self.doc.tag_assignments.create(
            company=self.co_a, tag=self.tag_paie)
        self.assertEqual(
            selectors.acl_effective(self.doc, self.user_rh), 'lecture')

        assignment.delete()
        self.doc.refresh_from_db()
        # Recalcul immédiat sans tag : plus aucune règle ne matche → None.
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_rh))

    def test_admin_toujours_gestion_non_affecte(self):
        RegleAclMetadonnee.objects.create(
            company=self.co_a, nom='Paie → RH',
            condition_group={
                'field': 'tags', 'operator': 'contains', 'value': 'paie',
            },
            role=self.role_rh, niveau='lecture')
        self.doc.tag_assignments.create(company=self.co_a, tag=self.tag_paie)
        self.assertEqual(
            selectors.acl_effective(self.doc, self.admin), 'gestion')

    def test_acl_directe_reste_prioritaire_meme_scope(self):
        """Non-régression GED19 : une ACL directe (AclGed) au même scope (le
        document lui-même) l'emporte si son rang est plus permissif que la
        règle par métadonnée."""
        from apps.ged.models import AclGed
        RegleAclMetadonnee.objects.create(
            company=self.co_a, nom='Paie → RH (lecture)',
            condition_group={
                'field': 'tags', 'operator': 'contains', 'value': 'paie',
            },
            role=self.role_rh, niveau='lecture')
        self.doc.tag_assignments.create(company=self.co_a, tag=self.tag_paie)
        AclGed.objects.create(
            company=self.co_a, document=self.doc, role=self.role_rh,
            niveau='gestion', herite=False)
        self.assertEqual(
            selectors.acl_effective(self.doc, self.user_rh), 'gestion')

    def test_regle_inactive_non_appliquee(self):
        RegleAclMetadonnee.objects.create(
            company=self.co_a, nom='Paie → RH', actif=False,
            condition_group={
                'field': 'tags', 'operator': 'contains', 'value': 'paie',
            },
            role=self.role_rh, niveau='lecture')
        self.doc.tag_assignments.create(company=self.co_a, tag=self.tag_paie)
        self.assertIsNone(selectors.acl_effective(self.doc, self.user_rh))

    def test_isolation_societe(self):
        co_b = make_company('xged21-b', 'Xged21 B')
        role_rh_b = make_role(co_b, 'RH')
        user_rh_b = make_user(co_b, 'xged21-rh-b', role=role_rh_b)
        RegleAclMetadonnee.objects.create(
            company=self.co_a, nom='Paie → RH',
            condition_group={
                'field': 'tags', 'operator': 'contains', 'value': 'paie',
            },
            role=self.role_rh, niveau='lecture')
        self.doc.tag_assignments.create(company=self.co_a, tag=self.tag_paie)
        # Un utilisateur d'une AUTRE société n'est de toute façon jamais
        # gouverné par l'ACL d'une société différente (garde société de
        # acl_effective, avant même la résolution de règle).
        self.assertIsNone(selectors.acl_effective(self.doc, user_rh_b))
