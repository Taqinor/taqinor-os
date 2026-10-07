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
