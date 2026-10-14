# -*- coding: utf-8 -*-
"""ADEV18 (C-ADEV-011) — l'instantané restaurable porte la note client et
TOUS les champs d'en-tête visibles, et la restauration les ré-applique.

Rejoue la sonde VA p6 : sur un devis ENVOYÉ, PATCH ``note`` créait UN
instantané SANS ``note``, puis PATCH ``acompte_pct`` n'en créait AUCUN (le
contenu était identique au précédent) alors que le chatter disait « corrigé
après envoi — en-tête ». « Revenir à cette version » ne pouvait donc rien
rétablir de l'en-tête.

La restauration rejoue l'appel de l'écran : ``POST replace-lines`` avec les
lignes de l'instantané et ``entete`` = ``contenu.entete`` + ``note``
(contrat QJR504 ``devis_replace_lines_entete.json``).

Test-du-test : retirer ``note`` de ``configuration_devis_contenu`` ⇒
``test_note_dans_instantane`` échoue ; retirer un champ de l'en-tête ⇒
``test_garde_tout_champ_entete_visible_dans_instantane`` le nomme.
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.domain import modifiabilite
from apps.ventes.domain.historique_config import (
    cle_entete, configuration_devis_contenu)
from apps.ventes.models import ConfigurationDevisSnapshot, Devis, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class InstantaneEnteteNoteTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ADEV18 Co', slug='adev18-co')
        self.user = User.objects.create_user(
            username='adev18_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV18',
            email='adev18@example.test', telephone='+212600000018')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='ADEV18-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau Huawei 5kW',
            sku='ADEV18-OND', prix_vente=Decimal('3000'),
            prix_achat=Decimal('2000'), quantite_stock=100)
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-0018',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'), created_by=self.user,
            note='Pose prévue en mars.', acompte_pct=Decimal('30'),
            date_validite=timezone.localdate() + datetime.timedelta(days=30))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal('10'),
            prix_unitaire=Decimal('1000'), remise=Decimal('0'), ordre=0)
        LigneDevis.objects.create(
            devis=self.devis, produit=self.onduleur,
            designation=self.onduleur.nom, quantite=Decimal('1'),
            prix_unitaire=Decimal('3000'), remise=Decimal('0'), ordre=1)

    def _snaps(self):
        return list(ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).order_by('date_creation', 'id'))

    def _patch(self, **corps):
        r = self.api.patch(f'/api/django/ventes/devis/{self.devis.id}/',
                           corps, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        return r

    def test_note_dans_instantane(self):
        self._patch(note='Pose reportée en avril.')
        snaps = self._snaps()
        self.assertGreaterEqual(len(snaps), 2)
        # L'état vu par le client (avant) ET l'état corrigé portent la note.
        self.assertEqual(snaps[-2].contenu['note'], 'Pose prévue en mars.')
        self.assertEqual(snaps[-1].contenu['note'], 'Pose reportée en avril.')
        for snap in snaps[-2:]:
            self.assertIn('entete', snap.contenu)

    def test_acompte_cree_instantane(self):
        self._patch(note='Pose reportée en avril.')
        n1 = len(self._snaps())
        self._patch(acompte_pct='40')
        snaps = self._snaps()
        self.assertEqual(len(snaps), n1 + 1)
        self.assertEqual(
            Decimal(snaps[-1].contenu['entete']['acompte_pct']),
            Decimal('40'))
        self.assertEqual(
            Decimal(snaps[-2].contenu['entete']['acompte_pct']),
            Decimal('30'))

    def test_restauration_reapplique_entete(self):
        nouvelle_validite = timezone.localdate() + datetime.timedelta(days=60)
        self._patch(note='Pose reportée en avril.')
        self._patch(acompte_pct='40',
                    date_validite=nouvelle_validite.isoformat())
        origine = self._snaps()[0].contenu
        self.assertEqual(origine['note'], 'Pose prévue en mars.')
        # Rejoue « Revenir à cette version » (écran) : lignes + entete + note.
        lignes = []
        for ligne in origine['lignes']:
            copie = dict(ligne)
            copie.pop('lot', None)
            lignes.append(copie)
        entete = dict(origine['entete'])
        entete['note'] = origine['note']
        r = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/replace-lines/',
            {'lignes': lignes, 'entete': entete}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        # CLAUSE PERSISTANCE : relire en base.
        frais = Devis.objects.get(pk=self.devis.pk)
        self.assertEqual(frais.note, 'Pose prévue en mars.')
        self.assertEqual(frais.acompte_pct, Decimal('30'))
        self.assertEqual(frais.date_validite.isoformat(),
                         origine['entete']['date_validite'])
        self.assertEqual(frais.taux_tva, Decimal('20'))
        self.assertEqual(frais.client_id, self.client_obj.pk)
        self.assertEqual(frais.statut, Devis.Statut.ENVOYE)
        # Le contenu restauré = l'en-tête et la note de l'instantané.
        apres = configuration_devis_contenu(frais)
        self.assertEqual(apres['note'], origine['note'])
        self.assertEqual(apres['entete'], origine['entete'])

    def test_rien_change_aucun_instantane(self):
        self._patch(note='Pose reportée en avril.')
        n = len(self._snaps())
        self._patch(note='Pose reportée en avril.')
        self.assertEqual(len(self._snaps()), n)

    def test_garde_tout_champ_entete_visible_dans_instantane(self):
        """Garde de classe : tout champ que ``empreinte_visible`` compare
        (en-tête + note) figure dans l'instantané restaurable."""
        contenu = configuration_devis_contenu(self.devis)
        self.assertIn('note', contenu)
        for champ in modifiabilite._CHAMPS_ENTETE_VISIBLES:
            self.assertIn(
                cle_entete(champ), contenu['entete'],
                f"champ d'en-tête visible « {champ} » absent de l'instantané")
        empreinte = modifiabilite.empreinte_visible(self.devis)
        self.assertEqual(len(empreinte['entete']), len(contenu['entete']))
