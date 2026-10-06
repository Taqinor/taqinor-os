"""ADOC113 — « Mes devis » du portail expose `deux_options` et `options`.

Constat (C-ADOC-043, sondes #83/#104) : la liste portail ne disait jamais
qu'un devis portait deux options ; l'acceptation sans option répondait 400
(le client ne pouvait pas savoir quoi choisir) et l'écran ne pouvait offrir
aucun choix. Le contrat ``mes_devis_liste.json`` (ADOC110) fixait la forme.

Run :
    python manage.py test apps.portail.tests.test_adoc_devis_deux_options -v2
"""
import itertools
import json
import pathlib
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    PORTAIL_CLIENT_PERMISSIONS,
    ROLE_PORTAIL_CLIENT,
)
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from authentication.models import Company, CustomUser

_seq = itertools.count(1)

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1]
     / 'contract_samples' / 'mes_devis_liste.json')
    .read_text(encoding='utf-8'))

LISTE = '/api/django/portail/mes-devis/'


class DevisDeuxOptionsPortailTests(TestCase):
    def setUp(self):
        n = next(_seq)
        self.co, _ = Company.objects.get_or_create(
            slug=f'adoc113-{n}', defaults={'nom': f'ADOC113 {n}'})
        self.client_a = Client.objects.create(
            company=self.co, nom='Alpha', prenom=f'ADOC113-{n}',
            email=f'adoc113-{n}@example.invalid')
        self.deux = self._devis_deux_options(n)
        self.mono = Devis.objects.create(
            company=self.co, reference=f'DEV-ADOC113-M{n}',
            client=self.client_a, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        role, _ = Role.objects.get_or_create(
            company=self.co, nom=ROLE_PORTAIL_CLIENT,
            defaults={'permissions': list(PORTAIL_CLIENT_PERMISSIONS),
                      'est_systeme': True})
        user = CustomUser.objects.create_user(
            username=f'adoc113-portail-{n}', password='motdepasse-test-1234',
            company=self.co, role=role)
        user.portee = CustomUser.PORTEE_PORTAIL_CLIENT
        user.portail_client_id = self.client_a.id
        user.save()
        self.api = APIClient()
        self.api.force_authenticate(user=user)

    def _devis_deux_options(self, n):
        """Même patron que ventes/tests/test_acceptation.py `_devis_deux_options`
        (scénario déclaré + réseau ET hybride avec batterie)."""
        devis = Devis.objects.create(
            company=self.co, reference=f'DEV-ADOC113-D{n}',
            client=self.client_a, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'),
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        for desig, qty, pu in [
                ('Onduleur réseau', '1', '11700'),
                ('Onduleur hybride', '1', '24000'),
                ('Panneau mono 550W', '14', '1100'),
                ('Batterie 5 kWh', '1', '14000'),
                ('Installation', '1', '4000')]:
            produit = Produit.objects.create(
                company=self.co, nom=desig, sku=f'A113-{n}-{desig[:12]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _lignes(self):
        res = self.api.get(LISTE)
        self.assertEqual(res.status_code, 200, res.content)
        return {ligne['id']: ligne for ligne in res.json()['results']}

    def _accepter(self, **extra):
        return self.api.post(
            f'{LISTE}{self.deux.id}/accepter/',
            {'nom': 'Karim Alaoui', 'consent_esign': True, **extra},
            format='json')

    def test_liste_conforme_au_contrat_deux_options(self):
        self.assertEqual(CONTRAT['forme_serveur'], 'complete')
        lignes = self._lignes()
        attendu_deux = CONTRAT['exemple_deux_options']['results'][0]
        attendu_mono = CONTRAT['exemple_deux_options']['results'][1]
        # Clés émises == clés du contrat (exemple principal).
        for ligne in lignes.values():
            self.assertEqual(set(ligne),
                             set(CONTRAT['exemple']['results'][0]))
        self.assertIs(lignes[self.deux.id]['deux_options'], True)
        self.assertEqual(lignes[self.deux.id]['options'],
                         attendu_deux['options'])
        self.assertIs(lignes[self.mono.id]['deux_options'], False)
        self.assertIsNone(lignes[self.mono.id]['options'])
        self.assertEqual(attendu_mono['options'], None)
        # Jamais de montant par option ni de prix d'achat.
        self.assertNotIn('prix_achat', json.dumps(lignes[self.deux.id]))

    def test_accepter_sans_option_400_inchange(self):
        res = self._accepter()
        self.assertEqual(res.status_code, 400, res.content)
        self.assertTrue(res.json()['detail'].startswith(
            'Ce devis comporte deux options'))
        self.deux.refresh_from_db()
        self.assertEqual(self.deux.statut, Devis.Statut.ENVOYE)

    def test_accepter_avec_option_200(self):
        res = self._accepter(option='avec_batterie')
        self.assertEqual(res.status_code, 200, res.content)
        self.deux.refresh_from_db()
        self.assertEqual(self.deux.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(self.deux.option_acceptee,
                         Devis.OptionAcceptee.AVEC_BATTERIE)
        # Persistance : la liste relue garde deux_options et le statut.
        ligne = self._lignes()[self.deux.id]
        self.assertEqual(ligne['statut'], 'accepte')
        self.assertIs(ligne['deux_options'], True)
