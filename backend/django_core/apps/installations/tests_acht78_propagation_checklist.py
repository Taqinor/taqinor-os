"""ACHT78 (C-ACHT-073) — règle de propagation du modèle de checklist (D-ACHT-2,
ACHT95 option a) : la checklist d'un chantier est figée à sa première
matérialisation ; un chantier réceptionné/clôturé n'est jamais modifié ; un
chantier jamais ouvert reçoit le modèle courant ; la relecture est idempotente.

Rejoue COUT-9 : clôturé `items apres relecture 9 (avant 8)`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht78_propagation_checklist"
"""
from django.test import TestCase

from authentication.models import Company

from apps.installations.models import (
    ChantierChecklistItem, ChecklistEtapeModele, ChecklistTemplate,
    Installation,
)
from apps.installations.services import ensure_checklist_items


class PropagationChecklistTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ACHT78', slug='acht78-co')
        self.tpl = ChecklistTemplate.objects.create(
            company=self.co, nom='Défaut')
        for i in range(8):
            ChecklistEtapeModele.objects.create(
                company=self.co, template=self.tpl, cle=f'e{i}',
                libelle=f'Étape {i}', ordre=i)
        self.cloture = Installation.objects.create(
            company=self.co, reference='CH-CLOS',
            statut=Installation.Statut.CLOTURE)
        self.en_cours = Installation.objects.create(
            company=self.co, reference='CH-COURS',
            statut=Installation.Statut.EN_COURS)
        self.jamais_ouvert = Installation.objects.create(
            company=self.co, reference='CH-NEUF',
            statut=Installation.Statut.EN_COURS)
        # Le clôturé et l'en-cours ont déjà leurs 8 étapes matérialisées
        # (avant la clôture pour le premier).
        for inst in (self.cloture, self.en_cours):
            Installation.objects.filter(pk=inst.pk).update(
                statut=Installation.Statut.EN_COURS)
            inst.refresh_from_db()
            self.assertEqual(len(ensure_checklist_items(inst)), 8)
        Installation.objects.filter(pk=self.cloture.pk).update(
            statut=Installation.Statut.CLOTURE)
        self.cloture.refresh_from_db()

    def _modifier_le_modele(self):
        ChecklistEtapeModele.objects.create(
            company=self.co, template=self.tpl, cle='nouvelle',
            libelle='Nouvelle étape', ordre=9)
        ChecklistEtapeModele.objects.filter(
            template=self.tpl, cle='e0').update(libelle='RENOMME')

    def _lire(self, inst):
        return [(i.cle, i.libelle) for i in ensure_checklist_items(inst)]

    def test_cloture_et_en_cours_figes_puis_neuf_recoit_le_modele(self):
        avant_clos = self._lire(self.cloture)
        avant_cours = self._lire(self.en_cours)
        self._modifier_le_modele()
        for _ in range(2):           # relecture idempotente
            self.assertEqual(self._lire(self.cloture), avant_clos)
            self.assertEqual(self._lire(self.en_cours), avant_cours)
        self.assertEqual(len(avant_clos), 8)
        neuf = self._lire(self.jamais_ouvert)
        self.assertEqual(len(neuf), 9)
        self.assertIn(('e0', 'RENOMME'), neuf)
        self.assertEqual(self._lire(self.jamais_ouvert), neuf)

    def test_cloture_jamais_ouvert_reste_vide(self):
        vide = Installation.objects.create(
            company=self.co, reference='CH-CLOS-VIDE',
            statut=Installation.Statut.CLOTURE)
        self.assertEqual(ensure_checklist_items(vide), [])
        self.assertEqual(ChantierChecklistItem.objects.filter(
            installation=vide).count(), 0)
