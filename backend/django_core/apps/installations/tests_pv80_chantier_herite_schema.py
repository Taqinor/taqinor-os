"""PV80 — « Le chantier hérite du schéma ».

Deux garanties, sur le MÊME chemin (``create_installation_from_devis``,
partagé par l'endpoint ``creer-depuis-devis/`` et le récepteur
``devis_accepted``) :

  * un devis accepté qui porte une conception électrique (``electrical_design``,
    PV41) fait poser un document POINTEUR ``DocumentProjet
    (type_doc='schema_unifilaire')`` sur le chantier créé — la pièce que
    ``assemble_handover_pieces`` (CH4) cherchait déjà mais ne trouvait jamais
    (aucun code ne la créait) ; ``present`` bascule à ``True`` ;
  * un devis SANS conception électrique ne pose AUCUN document — dégradation
    propre, `present=False`, aucun plantage (comportement inchangé) ;
  * idempotence : ré-émettre ``devis_accepted`` (ré-acceptation) ne duplique
    jamais le document ;
  * le template de checklist « Défaut » porte la nouvelle étape système
    « Schéma électrique validé » (visible sur un chantier fraîchement créé).

Run :
    DB_NAME=erp_installations python manage.py test \
        apps.installations.tests_pv80_chantier_herite_schema -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Devis
from apps.installations.models import DocumentProjet, Installation
from apps.installations.services import (
    assemble_handover_pieces, create_installation_from_devis,
    ensure_checklist_items,
)
from core.events import devis_accepted

User = get_user_model()

_DESIGN_EXEMPLE = {
    'chaines': [{'pan': 1, 'mppt': 1, 'nb_modules': 16, 'conforme': True}],
    'conformite': True,
    'ratio_dc_ac': 1.15,
}


def _make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class PV80SchemaDocumentTests(TestCase):
    def setUp(self):
        self.company = _make_company('pv80-co', 'PV80 Co')
        self.user = User.objects.create_user(
            username='pv80_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.crm_client = Client.objects.create(
            company=self.company, nom='Client', prenom='PV80',
            email='pv80@example.com')

    def _devis(self, num, electrical_design=None):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-PV80-{num}',
            client=self.crm_client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel',
            electrical_design=electrical_design)

    def test_avec_conception_electrique_pose_document_pointeur(self):
        """Devis avec ``electrical_design`` → DocumentProjet pointeur posé,
        la pièce « as_built » du pack de remise bascule à `present=True`."""
        devis = self._devis(1, electrical_design=_DESIGN_EXEMPLE)
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)

        doc = DocumentProjet.objects.get(
            installation=inst, type_doc='schema_unifilaire')
        self.assertEqual(doc.company_id, self.company.id)
        self.assertIn(devis.reference, doc.titre)
        self.assertIn(f'/devis/{devis.pk}/schema-unifilaire/', doc.notes)

        resume = assemble_handover_pieces(inst)
        as_built = next(p for p in resume['pieces'] if p['type'] == 'as_built')
        self.assertTrue(as_built['present'])
        self.assertEqual(as_built['reference'], doc.titre)

    def test_sans_conception_electrique_aucun_document_ni_plantage(self):
        """Devis SANS ``electrical_design`` → aucun document créé, la pièce
        reste `present=False` (dégradation propre, comportement historique)."""
        devis = self._devis(2, electrical_design=None)
        inst, created = create_installation_from_devis(
            devis, self.user, self.company)
        self.assertTrue(created)

        self.assertFalse(
            DocumentProjet.objects.filter(
                installation=inst, type_doc='schema_unifilaire').exists())

        resume = assemble_handover_pieces(inst)
        as_built = next(p for p in resume['pieces'] if p['type'] == 'as_built')
        self.assertFalse(as_built['present'])
        self.assertFalse(resume['complet'])

    def test_conception_electrique_vide_ne_pose_rien(self):
        """Un dict vide ({}) n'est pas une conception électrique exploitable
        — comportement identique à `None` (jamais de document orphelin)."""
        devis = self._devis(3, electrical_design={})
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        self.assertFalse(
            DocumentProjet.objects.filter(
                installation=inst, type_doc='schema_unifilaire').exists())

    def test_idempotence_re_acceptation_ne_duplique_pas(self):
        """Ré-émettre ``devis_accepted`` (ré-acceptation) ne crée ni un second
        chantier, ni un second document pointeur."""
        devis = self._devis(4, electrical_design=_DESIGN_EXEMPLE)
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='envoye')
        devis_accepted.send(
            sender=None, devis=devis, user=self.user, ancien_statut='accepte')

        self.assertEqual(
            Installation.objects.filter(devis=devis).count(), 1)
        inst = Installation.objects.get(devis=devis)
        self.assertEqual(
            DocumentProjet.objects.filter(
                installation=inst, type_doc='schema_unifilaire').count(), 1)

    def test_appel_direct_re_seede_sans_dupliquer(self):
        """Un second appel direct au service (même chantier déjà créé, ex.
        étude électrique relancée) rafraîchit le pointeur SANS dupliquer la
        ligne — un seul DocumentProjet par (chantier, type_doc)."""
        from apps.installations.services import _seed_schema_unifilaire_document
        devis = self._devis(5, electrical_design=_DESIGN_EXEMPLE)
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        first = DocumentProjet.objects.get(
            installation=inst, type_doc='schema_unifilaire')

        _seed_schema_unifilaire_document(inst, devis)

        self.assertEqual(
            DocumentProjet.objects.filter(
                installation=inst, type_doc='schema_unifilaire').count(), 1)
        second = DocumentProjet.objects.get(
            installation=inst, type_doc='schema_unifilaire')
        self.assertEqual(first.id, second.id)


class PV80ChecklistStepTests(TestCase):
    def setUp(self):
        self.company = _make_company('pv80-checklist-co', 'PV80 Checklist Co')
        self.user = User.objects.create_user(
            username='pv80_checklist', password='x', role_legacy='responsable',
            company=self.company)
        self.crm_client = Client.objects.create(
            company=self.company, nom='Client', prenom='Checklist',
            email='pv80-checklist@example.com')

    def test_etape_schema_electrique_visible_sur_template_defaut(self):
        devis = Devis.objects.create(
            company=self.company, reference='DEV-PV80-CHK-1',
            client=self.crm_client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'), mode_installation='residentiel')
        inst, _ = create_installation_from_devis(devis, self.user, self.company)
        items = ensure_checklist_items(inst)
        cles = {it.cle for it in items}
        self.assertIn('schema_electrique_valide', cles)
        etape = next(it for it in items if it.cle == 'schema_electrique_valide')
        self.assertEqual(etape.libelle, 'Schéma électrique validé')
