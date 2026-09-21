"""NTMFG39 — Entrées `audit.AuditLog` sur les actions sensibles du module
MRP.

Critère : les actions sensibles génèrent chacune une entrée AuditLog
consultable par un admin, aucune autre action mineure du module n'est
auditée (pas de bruit).

NOTE DE PÉRIMÈTRE — le plan liste 3 actions (forçage QC bloquant NTMFG13,
approbation ECO NTMFG15, modification coût standard figé NTMFG11). NTMFG13
(blocage QC bloquant) n'est PAS construit dans ce dépôt (round 1/2 :
« NTMFG13 hors périmètre de ce lot », voir `apps/mrp/selectors.py`) — il n'y
a donc aucune action de forçage QC à auditer. Ce lot audite les 2 actions
RÉELLEMENT construites : approbation ECO et coût standard figé."""
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.audit.models import AuditLog
from apps.mrp.models import (
    CoutStandard, Gamme, OperationGamme, OrdreFabrication, OrdreModification,
    PosteDeCharge,
)
from apps.mrp.services import approuver_eco, confirmer_of, figer_cout_standard
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class AuditFigerCoutStandardTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg39-1', 'MRP NTMFG39 1')
        self.admin = make_user(self.company, 'mrp-ntmfg39-admin', role='admin')
        self.produit = make_produit(self.company)
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-39', nom='Poste 39')
        self.gamme = Gamme.objects.create(
            company=self.company, nom='Gamme 39', produit=self.produit)
        OperationGamme.objects.create(
            gamme=self.gamme, ordre=1, poste_charge=self.poste, libelle='Op',
            temps_prepa_min=Decimal('1'), temps_unitaire_min=Decimal('1'))

    def test_figer_cout_standard_cree_une_entree_audit(self):
        standard = figer_cout_standard(
            self.company, self.produit, self.gamme, user=self.admin)
        ct = ContentType.objects.get_for_model(CoutStandard)
        logs = AuditLog.objects.filter(
            company=self.company, content_type=ct, object_id=str(standard.id))
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action, AuditLog.Action.CREATE)
        self.assertEqual(logs.first().user_id, self.admin.id)

    def test_deuxieme_version_cree_une_entree_distincte(self):
        figer_cout_standard(self.company, self.produit, self.gamme, user=self.admin)
        deuxieme = figer_cout_standard(
            self.company, self.produit, self.gamme, user=self.admin)
        ct = ContentType.objects.get_for_model(CoutStandard)
        self.assertEqual(
            AuditLog.objects.filter(company=self.company, content_type=ct).count(), 2)
        self.assertIn('v1', AuditLog.objects.get(
            content_type=ct, object_id=str(deuxieme.id)).detail)


class AuditApprouverEcoTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ntmfg39-eco-1', 'MRP NTMFG39 ECO 1')
        self.admin = make_user(self.company, 'mrp-ntmfg39-eco-admin', role='admin')
        self.produit = make_produit(self.company)

    def test_approuver_eco_cree_une_entree_audit(self):
        eco = OrdreModification.objects.create(
            company=self.company, produit=self.produit,
            type_eco=OrdreModification.TypeEco.GAMME, changements={})
        approuver_eco(eco, user=self.admin)
        ct = ContentType.objects.get_for_model(OrdreModification)
        logs = AuditLog.objects.filter(
            company=self.company, content_type=ct, object_id=str(eco.id))
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs.first().action, AuditLog.Action.STATUS)
        self.assertEqual(
            logs.first().changes,
            [{'field': 'statut', 'old': 'brouillon', 'new': 'approuve'}])


class AuditPasDeBruitTests(TestCase):
    """Une action MINEURE du module (confirmer un OF, NTMFG3) ne doit
    JAMAIS générer d'entrée AuditLog — seules les 2 actions sensibles ci-
    dessus le font (chatter ARC8 est le canal des transitions routine,
    NTMFG38 — jamais l'audit)."""

    def setUp(self):
        self.company = make_company('mrp-ntmfg39-bruit-1', 'MRP NTMFG39 BRUIT 1')
        self.user = make_user(self.company, 'mrp-ntmfg39-bruit-user')
        self.produit = make_produit(self.company)

    def test_confirmer_of_n_est_pas_audite(self):
        of = OrdreFabrication.objects.create(
            company=self.company, produit=self.produit, quantite=1)
        confirmer_of(of, user=self.user)
        ct = ContentType.objects.get_for_model(OrdreFabrication)
        self.assertEqual(
            AuditLog.objects.filter(
                company=self.company, content_type=ct, object_id=str(of.id)).count(),
            0)
