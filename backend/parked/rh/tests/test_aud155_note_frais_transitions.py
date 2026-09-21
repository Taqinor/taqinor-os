"""AUD155 — le cycle de vie d'une `rh.NoteDeFrais` est ORDONNÉ.

Défaut prouvé : `NoteDeFraisViewSet._set_statut` (apps/rh/views.py:5081-5087
avant ce correctif) faisait uniquement
``if note.statut != nouveau: note.statut = nouveau; note.save(...)`` — aucune
vérification de l'état courant. Or :

* le cycle documenté (docs/module-map.md §ODX15) est
  « soumise → approuvee → remboursee / refusee » ;
* le jumeau `frais.NoteFrais` vérifie STRICTEMENT l'état précédent à chaque
  étape (`apps/compta/services.py:4841` « Seule une note soumise peut être
  validée », `:4898` pour le rejet, `:4921` « Seule une note validée peut
  être remboursée »).

Scénario : une note de frais REFUSÉE est marquée « remboursée » d'un appel
direct, sans avoir jamais été approuvée — et l'argent sort.
"""
from decimal import Decimal

from django.test import TestCase

from apps.rh.models import NoteDeFrais

from .test_portail_self_service import (
    FRAIS, auth, make_company, make_employe, make_user,
)


class NoteDeFraisTransitionsTests(TestCase):
    def setUp(self):
        self.company = make_company('aud155-nf', 'AUD155 NF')
        self.responsable = make_user(
            self.company, 'aud155-resp', role='responsable')
        self.employe = make_employe(self.company, 'AUD155-1')
        self.api = auth(self.responsable)

    def _note(self, libelle, statut=NoteDeFrais.Statut.SOUMISE):
        return NoteDeFrais.objects.create(
            company=self.company, employe=self.employe, libelle=libelle,
            montant=Decimal('750.00'), statut=statut)

    # ── (1) le scénario : une note REFUSÉE devient « remboursée » ──────────
    def test_note_refusee_ne_peut_pas_etre_remboursee(self):
        note = self._note('Refusée', statut=NoteDeFrais.Statut.REFUSEE)
        reponse = self.api.post(f'{FRAIS}{note.id}/marquer-remboursee/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteDeFrais.Statut.REFUSEE)

    # ── (2) une note SOUMISE non approuvée ne se rembourse pas non plus ────
    def test_note_soumise_non_approuvee_ne_peut_pas_etre_remboursee(self):
        note = self._note('Soumise')
        reponse = self.api.post(f'{FRAIS}{note.id}/marquer-remboursee/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteDeFrais.Statut.SOUMISE)

    # ── (3) le chemin nominal reste intact ─────────────────────────────────
    def test_chemin_nominal_soumise_approuvee_remboursee(self):
        note = self._note('Nominale')
        reponse = self.api.post(f'{FRAIS}{note.id}/approuver/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'],
                         NoteDeFrais.Statut.APPROUVEE)

        reponse = self.api.post(f'{FRAIS}{note.id}/marquer-remboursee/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'],
                         NoteDeFrais.Statut.REMBOURSEE)

    def test_chemin_nominal_soumise_refusee(self):
        note = self._note('Refus direct')
        reponse = self.api.post(f'{FRAIS}{note.id}/refuser/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'], NoteDeFrais.Statut.REFUSEE)

    # ── les autres transitions hors cycle ──────────────────────────────────
    def test_note_remboursee_ne_peut_plus_etre_refusee(self):
        note = self._note('Déjà payée',
                          statut=NoteDeFrais.Statut.REMBOURSEE)
        reponse = self.api.post(f'{FRAIS}{note.id}/refuser/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteDeFrais.Statut.REMBOURSEE)

    def test_note_refusee_ne_peut_pas_etre_approuvee(self):
        note = self._note('Refusée bis', statut=NoteDeFrais.Statut.REFUSEE)
        reponse = self.api.post(f'{FRAIS}{note.id}/approuver/')
        self.assertEqual(reponse.status_code, 400, reponse.data)
        note.refresh_from_db()
        self.assertEqual(note.statut, NoteDeFrais.Statut.REFUSEE)

    # ── l'idempotence annoncée par les trois actions est préservée ─────────
    def test_idempotence_preservee_sur_les_trois_actions(self):
        for statut, url in (
            (NoteDeFrais.Statut.APPROUVEE, 'approuver'),
            (NoteDeFrais.Statut.REFUSEE, 'refuser'),
            (NoteDeFrais.Statut.REMBOURSEE, 'marquer-remboursee'),
        ):
            note = self._note(f'Idem {url}', statut=statut)
            reponse = self.api.post(f'{FRAIS}{note.id}/{url}/')
            self.assertEqual(reponse.status_code, 200, reponse.data)
            self.assertEqual(reponse.data['statut'], statut)

    def test_message_de_refus_nomme_le_cycle(self):
        note = self._note('Message', statut=NoteDeFrais.Statut.REFUSEE)
        reponse = self.api.post(f'{FRAIS}{note.id}/marquer-remboursee/')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('approuvée', reponse.data['detail'])
