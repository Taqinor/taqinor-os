"""CIQ641 — modèle d'entretien « Site professionnel » semé (idempotent),
sans intervalle ni chiffre (la fréquence vient du contrat O&M, CIQ640).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.sav.tests_ciq641_entretien_ci"
"""
import re

from django.test import TestCase

from apps.sav.models import (
    MaintenanceChecklistItem, MaintenanceChecklistTemplate,
    TicketChecklistItem,
)
from apps.sav.services import (
    MODELE_ENTRETIEN_CI_ETAPES, MODELE_ENTRETIEN_CI_NOM,
    ensure_modele_entretien_ci,
)
from apps.sav.tests_fg81_fg90 import (
    auth, make_company, make_installation, make_ticket, make_user,
)

URL = '/api/django/sav/checklist-templates/'


class EntretienSiteProTests(TestCase):
    def setUp(self):
        self.co = make_company(slug='ciq641-co', nom='CIQ641 Co')
        self.user = make_user(self.co, username='ciq641_admin')
        self.api = auth(self.user)

    def _modeles_ci(self):
        marqueur = MODELE_ENTRETIEN_CI_ETAPES[0][0]
        return MaintenanceChecklistTemplate.objects.filter(
            company=self.co, items__cle=marqueur)

    def test_cree_une_seule_fois_a_l_affichage(self):
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200)
        noms = [x['nom'] for x in r.data['results']]
        self.assertEqual(noms.count(MODELE_ENTRETIEN_CI_NOM), 1)
        self.api.get(URL)
        self.assertEqual(self._modeles_ci().count(), 1)
        modele = self._modeles_ci().get()
        self.assertFalse(modele.protege)
        self.assertEqual(
            list(modele.items.order_by('ordre').values_list('cle', flat=True)),
            [cle for cle, _ in MODELE_ENTRETIEN_CI_ETAPES])
        self.assertIsNone(ensure_modele_entretien_ci(self.co))

    def test_renomme_ou_desactive_jamais_recree(self):
        modele = ensure_modele_entretien_ci(self.co)
        modele.nom = 'Visite toiture usine'
        modele.save(update_fields=['nom'])
        self.assertIsNone(ensure_modele_entretien_ci(self.co))
        self.assertEqual(self._modeles_ci().count(), 1)
        modele.actif = False
        modele.save(update_fields=['actif'])
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200)
        noms = [x['nom'] for x in r.data['results']]
        self.assertNotIn('Visite toiture usine', noms)
        self.assertNotIn(MODELE_ENTRETIEN_CI_NOM, noms)
        self.assertEqual(self._modeles_ci().count(), 1)

    def test_ticket_preventif_l_instancie(self):
        modele = ensure_modele_entretien_ci(self.co)
        inst, client = make_installation(self.co, ref='CHT-CIQ641')
        ticket = make_ticket(self.co, self.user, client, inst)
        ticket.type = 'preventif'
        ticket.save(update_fields=['type'])
        r = self.api.post(f'/api/django/sav/tickets/{ticket.pk}/checklist/',
                          {'template_id': modele.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            TicketChecklistItem.objects.filter(ticket=ticket).count(),
            len(MODELE_ENTRETIEN_CI_ETAPES))

    def test_aucune_valeur_numerique_dans_les_libelles(self):
        ensure_modele_entretien_ci(self.co)
        cles = [cle for cle, _ in MODELE_ENTRETIEN_CI_ETAPES]
        libelles = MaintenanceChecklistItem.objects.filter(
            company=self.co, cle__in=cles).values_list('libelle', flat=True)
        self.assertEqual(len(libelles), len(MODELE_ENTRETIEN_CI_ETAPES))
        for libelle in libelles:
            self.assertIsNone(re.search(r'\d', libelle), libelle)
        self.assertIsNone(re.search(r'\d', MODELE_ENTRETIEN_CI_NOM))
