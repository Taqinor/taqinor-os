"""AGR619 — modèle d'entretien « Pompage solaire » semé (idempotent), sans
intervalle ni chiffre.

Run :
    python manage.py test apps.sav.tests_agr619_entretien_pompage -v 2
"""
import re

from django.test import TestCase

from apps.sav.models import (
    MaintenanceChecklistItem, MaintenanceChecklistTemplate,
    TicketChecklistItem,
)
from apps.sav.services import (
    MODELE_ENTRETIEN_POMPAGE_ETAPES, MODELE_ENTRETIEN_POMPAGE_NOM,
    ensure_modele_entretien_pompage,
)
from apps.sav.tests_fg81_fg90 import (
    auth, make_company, make_installation, make_ticket, make_user,
)

URL = '/api/django/sav/checklist-templates/'


class EntretienPompageTests(TestCase):
    def setUp(self):
        self.co = make_company(slug='agr619-co', nom='AGR619 Co')
        self.user = make_user(self.co, username='agr619_admin')
        self.api = auth(self.user)

    def _modeles(self):
        return MaintenanceChecklistTemplate.objects.filter(company=self.co)

    def test_cree_une_seule_fois_a_l_affichage(self):
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200)
        noms = [x['nom'] for x in r.data['results']]
        self.assertEqual(noms.count(MODELE_ENTRETIEN_POMPAGE_NOM), 1)
        self.api.get(URL)
        self.assertEqual(self._modeles().count(), 1)
        modele = self._modeles().get()
        self.assertFalse(modele.protege)
        self.assertEqual(
            list(modele.items.order_by('ordre').values_list('cle', flat=True)),
            [cle for cle, _ in MODELE_ENTRETIEN_POMPAGE_ETAPES])
        self.assertIsNone(ensure_modele_entretien_pompage(self.co))

    def test_renomme_ou_desactive_jamais_recree(self):
        modele = ensure_modele_entretien_pompage(self.co)
        modele.nom = 'Visite forage'
        modele.save(update_fields=['nom'])
        self.assertIsNone(ensure_modele_entretien_pompage(self.co))
        self.assertEqual(self._modeles().count(), 1)
        modele.actif = False
        modele.save(update_fields=['actif'])
        r = self.api.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['results'], [])
        self.assertEqual(self._modeles().count(), 1)

    def test_ticket_preventif_recoit_les_10_etapes(self):
        modele = ensure_modele_entretien_pompage(self.co)
        inst, client = make_installation(self.co, ref='CHT-AGR619')
        ticket = make_ticket(self.co, self.user, client, inst)
        ticket.type = 'preventif'
        ticket.save(update_fields=['type'])
        r = self.api.post(f'/api/django/sav/tickets/{ticket.pk}/checklist/',
                          {'template_id': modele.pk}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(
            TicketChecklistItem.objects.filter(ticket=ticket).count(), 10)

    def test_aucune_valeur_numerique_dans_les_libelles(self):
        ensure_modele_entretien_pompage(self.co)
        libelles = MaintenanceChecklistItem.objects.filter(
            company=self.co).values_list('libelle', flat=True)
        self.assertEqual(len(libelles), 10)
        for libelle in libelles:
            self.assertIsNone(re.search(r'\d', libelle), libelle)
        self.assertIsNone(
            re.search(r'\d', MODELE_ENTRETIEN_POMPAGE_NOM))
