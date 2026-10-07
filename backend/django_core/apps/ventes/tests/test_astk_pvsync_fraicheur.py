# -*- coding: utf-8 -*-
"""ASTK140 — PVSYNC ignore un événement ``produit_modifie`` PÉRIMÉ.

Deux corrections de prix rapprochées (1 000 → 10 000 puis 10 000 → 1 000)
peuvent être traitées dans le désordre par la file Celery. Sans garde, la plus
ancienne, jouée en dernier, ré-imposait 10 000 à un brouillon alors que le
catalogue vaut 1 000. La resynchronisation relit donc le produit en base et
ignore tout « après » qui n'est plus la valeur courante.

Source réelle : ``resynchroniser_devis_pour_produit`` et la tâche
``task_resync_devis_apres_produit_modifie`` (appelée en ligne = mode eager),
aucun mock du domaine.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain.catalogue_events import (
    resynchroniser_devis_pour_produit)
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.tasks import task_resync_devis_apres_produit_modifie
from authentication.models import Company

User = get_user_model()

# Événement A : 1 000 → 10 000 ; événement B : 10 000 → 1 000 (catalogue final).
EVT_A = {'prix_vente': ['1000.00', '10000.00']}
EVT_B = {'prix_vente': ['10000.00', '1000.00']}


class FraicheurPvsyncTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor ASTK140')
        self.user = User.objects.create_user(
            username='astk140_admin', password='x', role_legacy='admin',
            company=self.company)
        # Le catalogue FINAL (saisies 1 000 → 10 000 → 1 000) vaut 1 000.
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='ASTK140-PAN',
            prix_achat=Decimal('700.00'), prix_vente=Decimal('1000.00'),
            quantite_stock=10)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Sara',
            email='astk140@example.com', telephone='+212600000140')
        self.devis = Devis.objects.create(
            company=self.company, statut=Devis.Statut.BROUILLON,
            client=self.client_obj, reference='DEV-ASTK140-0001',
            taux_tva=Decimal('20'))
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation='Panneau Jinko 550W', quantite=Decimal('10'),
            prix_unitaire=Decimal('1000.00'), remise=Decimal('0'))

    def _resync(self, champs):
        return resynchroniser_devis_pour_produit(
            produit=self.produit, company=self.company, champs=champs,
            user=self.user)

    def _tache(self, champs):
        return task_resync_devis_apres_produit_modifie(
            self.produit.id, self.company.id, champs, self.user.id)

    def _prix_relu(self):
        return LigneDevis.objects.get(pk=self.ligne.pk).prix_unitaire

    def test_ordre_inverse_reste_au_catalogue(self):
        # B d'abord (direct), puis A (via la tâche Celery réelle).
        self._resync(EVT_B)
        with self.assertLogs('apps.ventes.services', level='INFO') as logs:
            resultat_a = self._tache(EVT_A)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.prix_vente, Decimal('1000.00'))
        self.assertEqual(self._prix_relu(), Decimal('1000.00'))
        self.assertEqual(self._prix_relu(), self.produit.prix_vente)
        self.assertEqual(resultat_a['lignes_modifiees'], 0)
        self.assertTrue(any('périmé' in ligne for ligne in logs.output),
                        logs.output)

    def test_ordre_normal(self):
        self._tache(EVT_A)
        self._resync(EVT_B)

        self.assertEqual(self._prix_relu(), Decimal('1000.00'))

    def test_nom_perime_ignore(self):
        # Renommages X → Y puis Y → X ; catalogue final = X. L'événement
        # X → Y joué en dernier est périmé : la désignation reste X.
        resultat = self._resync(
            {'nom': ['Panneau Jinko 550W', 'Panneau Jinko 555W']})

        self.assertEqual(resultat['lignes_modifiees'], 0)
        self.assertEqual(
            LigneDevis.objects.get(pk=self.ligne.pk).designation,
            'Panneau Jinko 550W')

    def test_evenement_courant_toujours_applique(self):
        # Garde-fou : un événement dont l'« après » EST le catalogue courant
        # continue de recaler la ligne au prix catalogue.
        Produit.objects.filter(pk=self.produit.pk).update(
            prix_vente=Decimal('1100.00'))
        self._resync({'prix_vente': ['1000.00', '1100.00']})

        self.assertEqual(self._prix_relu(), Decimal('1100.00'))


class PerimetreDAstk1Tests(TestCase):
    """ASTK141 (D-ASTK-1, fondateur 06/10/2026) — une correction catalogue
    recale les BROUILLONS seulement. Un devis ENVOYÉ reste figé et reçoit une
    note persistée ; une ligne négociée conservée dans un brouillon aussi."""

    EVT = {'prix_vente': ['1000.00', '1100.00']}

    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor ASTK141')
        self.user = User.objects.create_user(
            username='astk141_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='ASTK141-PAN',
            prix_achat=Decimal('700.00'), prix_vente=Decimal('1000.00'),
            quantite_stock=10)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur hybride 5kW',
            sku='ASTK141-OND', prix_achat=Decimal('6000.00'),
            prix_vente=Decimal('9000.00'), quantite_stock=5)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Idrissi', prenom='Omar',
            email='astk141@example.com', telephone='+212600000141')
        self._n = 0
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _devis(self, statut, *, prix=Decimal('1000.00'), prix_manuel=False):
        self._n += 1
        devis = Devis.objects.create(
            company=self.company, statut=statut, client=self.client_obj,
            reference=f'DEV-ASTK141-{self._n:04d}', taux_tva=Decimal('20'))
        ligne = LigneDevis.objects.create(
            devis=devis, produit=self.produit,
            designation='Panneau Jinko 550W', quantite=Decimal('10'),
            prix_unitaire=prix, remise=Decimal('0'), prix_manuel=prix_manuel)
        # Le moteur de proposition exige un onduleur (garde PV86).
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur,
            designation='Onduleur hybride 5kW', quantite=Decimal('1'),
            prix_unitaire=Decimal('9000'), remise=Decimal('0'))
        return devis, ligne

    def _corriger_catalogue(self):
        # Le flux réel : le stock écrit le produit, PUIS l'événement part.
        Produit.objects.filter(pk=self.produit.pk).update(
            prix_vente=Decimal('1100.00'))
        return resynchroniser_devis_pour_produit(
            produit=self.produit, company=self.company, champs=self.EVT,
            user=self.user)

    def _historique(self, devis):
        reponse = self.api.get(
            f'/api/django/ventes/devis/{devis.id}/historique/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return [a.get('body') or '' for a in reponse.json()]

    def _public(self, devis):
        from apps.ventes.models import ShareLink
        lien = ShareLink.for_devis(devis)
        reponse = APIClient().get(
            f'/api/django/ventes/proposal/{lien.token}/')
        self.assertEqual(reponse.status_code, 200, reponse.content)
        return reponse.data

    def test_brouillon_suit_le_catalogue(self):
        devis, ligne = self._devis(Devis.Statut.BROUILLON)

        self._corriger_catalogue()

        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_unitaire, Decimal('1100.00'))
        self.assertTrue(any('Resynchronisé automatiquement' in b
                            for b in self._historique(devis)))

    def test_envoye_reste_fige_avec_note(self):
        devis, ligne = self._devis(Devis.Statut.ENVOYE)
        total_avant = Devis.objects.get(pk=devis.pk).total_ttc
        public_avant = self._public(devis)

        self._corriger_catalogue()

        ligne.refresh_from_db()
        devis.refresh_from_db()
        self.assertEqual(ligne.prix_unitaire, Decimal('1000.00'))
        self.assertEqual(devis.total_ttc, total_avant)
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertIsNone(
            (devis.etude_params or {}).get('resync_apres_envoi'))
        # Persistance : relue via l'historique HTTP, UNE note.
        corps = [b for b in self._historique(devis)
                 if 'devis envoyé conservé' in b]
        self.assertEqual(len(corps), 1, corps)
        self.assertIn('Prix catalogue passé de 1 000,00 à 1 100,00', corps[0])
        self.assertIn("réviser pour l'appliquer", corps[0])
        # Client : la page publique est identique à celle d'avant correction.
        public_apres = self._public(devis)
        self.assertIsNone(public_apres.get('resync_apres_envoi'))
        for cle in ('option_totals', 'lignes_structure'):
            self.assertEqual(public_apres.get(cle), public_avant.get(cle), cle)

    def test_negocie_conserve_avec_note_persistee(self):
        devis, ligne = self._devis(Devis.Statut.BROUILLON,
                                   prix=Decimal('900.00'), prix_manuel=True)

        self._corriger_catalogue()

        ligne.refresh_from_db()
        self.assertEqual(ligne.prix_unitaire, Decimal('900.00'))
        corps = [b for b in self._historique(devis)
                 if 'conservé (catalogue' in b]
        self.assertEqual(len(corps), 1, corps)
        self.assertIn('900,00 conservé (catalogue 1 000,00 → 1 100,00)',
                      corps[0])

    def test_rejeu_sans_doublon(self):
        envoye, _ = self._devis(Devis.Statut.ENVOYE)
        negocie, _ = self._devis(Devis.Statut.BROUILLON,
                                 prix=Decimal('900.00'), prix_manuel=True)

        self._corriger_catalogue()
        nb_envoye = len(self._historique(envoye))
        nb_negocie = len(self._historique(negocie))
        self._corriger_catalogue()

        self.assertEqual(len(self._historique(envoye)), nb_envoye)
        self.assertEqual(len(self._historique(negocie)), nb_negocie)
