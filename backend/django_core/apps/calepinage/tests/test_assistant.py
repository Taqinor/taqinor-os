"""Copilote vague 2 (lane CALA) — ce que l'assistant lit et écrit du calepinage.

Nouveau fichier car : aucune suite de l'assistant n'existe dans cette app
(modules neufs ``agent_actions.py``, ``views/assistant.py``,
``services/assistant.py``, ``services/contenance.py``,
``selectors_libelles.py``).

Les formes servies sont comparées aux échantillons COMMITTÉS
(``contrats_assistant.CONTRATS_ASSISTANT``) : un renommage côté vue rougit
ici, pas chez la carte.

Run :
    python manage.py test apps.calepinage.tests.test_assistant -v2
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth import get_user_model

from apps.calepinage.contrats_assistant import CONTRATS_ASSISTANT
from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.calepinage.permissions import CAL_GERER, CAL_VOIR
from apps.calepinage.services.parametres import enregistrer_parametres
from apps.roles.models import Role

from .test_api_liste import BaseApiCalepinage

User = get_user_model()

DOSSIER_CONTRATS = Path(__file__).resolve().parent.parent / 'contract_samples'


def echantillon(nom, cle='exemple'):
    """L'exemple ``cle`` du contrat ``nom`` (un des CONTRATS_ASSISTANT)."""
    assert nom in CONTRATS_ASSISTANT, nom
    return json.loads((DOSSIER_CONTRATS / nom).read_text(encoding='utf-8'))[cle]


class BaseAssistantCalepinage(BaseApiCalepinage):
    """Un calepinage sur le lead, une variante, un compte restreint « U »."""

    def setUp(self):
        super().setUp()
        self.lead.prenom = 'Karim'
        self.lead.nom = 'Alami'
        self.lead.save(update_fields=['prenom', 'nom'])
        self.cal = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toit Anfa',
            responsable=self.user, cree_par=self.user)
        self.variante = CalepinageVariante.objects.create(
            company=self.company, calepinage=self.cal, nom='Paysage')
        role = Role.objects.create(company=self.company, nom='ConcepteurCALA',
                                   permissions=[CAL_VOIR, CAL_GERER])
        self.u = User.objects.create_user(
            username='cala_u', password='x', company=self.company, role=role)
        self.api_u = self._client(self.u)

    def restreindre(self):
        enregistrer_parametres(self.company, {
            'presets': {'vue_restreinte_au_responsable': True}})


class LibellesTest(BaseAssistantCalepinage):
    """CALA1 — ``libelles_calepinage`` : la vue de l'utilisateur, rien d'autre."""

    def _libelles(self, user, **ids):
        from apps.calepinage.selectors_libelles import libelles_calepinage

        return libelles_calepinage(user, **ids)

    def test_reference_puis_nom_du_lead(self):
        sortie = self._libelles(self.user, calepinage=self.cal.pk,
                                variante=self.variante.pk)
        self.assertTrue(sortie['calepinage'].startswith('CAL-'))
        self.assertTrue(sortie['calepinage'].endswith('— Karim Alami'))
        self.assertTrue(sortie['variante'].startswith('« Paysage » (CAL-'))

    def test_autre_societe_ne_voit_rien(self):
        self.assertEqual(self._libelles(self.user_autre, calepinage=self.cal.pk,
                                        variante=self.variante.pk), {})

    def test_identifiant_inconnu_absent(self):
        self.assertEqual(self._libelles(self.user, calepinage=999999,
                                        variante=999999), {})

    def test_vue_restreinte_au_responsable(self):
        self.restreindre()
        self.assertEqual(self._libelles(self.u, calepinage=self.cal.pk,
                                        variante=self.variante.pk), {})
        self.assertIn('calepinage', self._libelles(self.user,
                                                   calepinage=self.cal.pk))

    def test_dispatch_de_l_agent(self):
        from apps.agent.libelles import libelles_objets

        sortie = libelles_objets(self.user, {'calepinage': self.cal.pk,
                                             'variante': self.variante.pk})
        self.assertEqual(set(sortie), {'calepinage', 'variante'})
