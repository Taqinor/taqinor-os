# -*- coding: utf-8 -*-
"""PVSYNC — modifier une RÉFÉRENCE du stock recale les devis qui l'utilisent.

Ce que ces tests verrouillent, et pourquoi chaque borne compte :

1. **Un devis VIVANT suit le catalogue.** Corriger un prix ou renommer une
   référence laissait jusqu'ici les brouillons parler de l'ancien monde ; ils
   suivent désormais, sans que personne n'ait à rouvrir quoi que ce soit.
2. **Un devis CONTRACTUEL ne bouge JAMAIS.** Accepté, refusé ou expiré : le
   client a vu (ou signé) ces montants. Aucune correction de catalogue n'a le
   droit de les réécrire — et le statut n'est jamais touché nulle part.
3. **Une ligne NÉGOCIÉE est sacrée.** Le prix ne suit que si la ligne portait
   EXACTEMENT l'ancien prix catalogue, sans remise ; la désignation ne suit que
   si elle n'avait jamais été retouchée. C'est pour cela que l'événement
   transporte l'AVANT.
4. **Un autre tenant n'existe pas.** La resynchronisation est cantonnée à la
   société de l'événement.
5. **Aucune boucle.** Le chemin n'écrit jamais un ``Produit``, donc il ne peut
   pas ré-émettre l'événement ; et le rejouer ne change plus rien (la livraison
   Celery est at-least-once).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pvsync_produit_modifie -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes import services
from apps.ventes.models import Devis, DevisActivity, LigneDevis
from authentication.models import Company
from core import events

User = get_user_model()

ANCIEN_PRIX = Decimal('1000.00')
NOUVEAU_PRIX = Decimal('1200.00')
ANCIEN_NOM = 'Panneau Jinko 550W'
NOUVEAU_NOM = 'Panneau Jinko 555W'


def _champs(prix=True, nom=False):
    """Payload d'événement tel que le viewset stock l'émet (chaînes)."""
    champs = {}
    if prix:
        champs['prix_vente'] = [str(ANCIEN_PRIX), str(NOUVEAU_PRIX)]
    if nom:
        champs['nom'] = [ANCIEN_NOM, NOUVEAU_NOM]
    return champs


class PvSyncBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Taqinor PVSYNC')
        self.user = User.objects.create_user(
            username='pvsync_admin', password='x', role_legacy='admin',
            company=self.company)
        self.produit = Produit.objects.create(
            company=self.company, nom=ANCIEN_NOM, sku='PVSYNC-PAN',
            prix_achat=Decimal('700.00'), prix_vente=ANCIEN_PRIX,
            quantite_stock=10)
        # Produit DISTINCT pour la ligne onduleur de fixture : lie au meme
        # produit que le panneau, elle entrait dans le queryset de resync
        # (filter(produit=...)) et gonflait lignes_conservees (CI round 3).
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur hybride 5kW',
            sku='PVSYNC-OND', prix_achat=Decimal('6000.00'),
            prix_vente=Decimal('9000.00'), quantite_stock=5)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Bennani', prenom='Karim',
            email='pvsync@example.com', telephone='+212600000009')
        self._compteur_reference = 0

    def _client_de(self, company):
        if company is None or company == self.company:
            return self.client_obj
        return Client.objects.create(
            company=company, nom='Client', prenom='Autre',
            email=f'client{company.id}@example.com',
            telephone='+212600000010')

    def _devis(self, statut, *, prix=ANCIEN_PRIX, remise=Decimal('0'),
               designation=ANCIEN_NOM, company=None, produit=None):
        self._compteur_reference += 1
        devis = Devis.objects.create(
            company=company or self.company, statut=statut,
            client=self._client_de(company),
            reference=f'DEV-PVSYNC-{self._compteur_reference:04d}',
            taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=produit or self.produit,
            designation=designation, quantite=Decimal('10'),
            prix_unitaire=prix, remise=remise)
        # Le moteur de proposition refuse un devis sans onduleur (garde-fou
        # PV86) : chaque devis de fixture porte une ligne onduleur stable,
        # sur son PROPRE produit — donc reellement hors du queryset de resync
        # (filter(produit=...)), contrairement a la premiere version.
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur,
            designation='Onduleur hybride 5kW (fixture)',
            quantite=Decimal('1'), prix_unitaire=Decimal('9000'),
            remise=Decimal('0'))
        return devis

    def _ligne(self, devis):
        return devis.lignes.first()

    def _notes(self, devis):
        return DevisActivity.objects.filter(
            devis=devis, field='produit_resynchronise')

    def _resync(self, champs=None, produit=None, company=None):
        return services.resynchroniser_devis_pour_produit(
            produit=produit or self.produit,
            company=company or self.company,
            champs=champs if champs is not None else _champs(),
            user=self.user)


class BrouillonEtEnvoyeSuiventTests(PvSyncBase):
    def test_brouillon_recale_au_prix_catalogue_et_note_le_chatter(self):
        devis = self._devis(Devis.Statut.BROUILLON)

        resultat = self._resync()

        self.assertEqual(resultat['devis_touches'], 1)
        self.assertEqual(resultat['lignes_modifiees'], 1)
        self.assertEqual(self._ligne(devis).prix_unitaire, NOUVEAU_PRIX)
        # Le chatter DIT ce qui s'est passé — sinon la ligne aurait bougé
        # sous les yeux du commercial sans la moindre trace.
        note = self._notes(devis).first()
        self.assertIsNotNone(note)
        self.assertIn('Resynchronisé automatiquement', note.body)
        self.assertIn(ANCIEN_NOM, note.body)
        self.assertIn('prix', note.body)
        # Le STATUT n'a pas bougé d'un iota (règle #4).
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_envoye_est_recale_aussi(self):
        devis = self._devis(Devis.Statut.ENVOYE)

        self._resync()

        self.assertEqual(self._ligne(devis).prix_unitaire, NOUVEAU_PRIX)
        self.assertEqual(self._notes(devis).count(), 1)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)


class TransparenceApresEnvoiTests(PvSyncBase):
    """Le périmètre reste brouillon + envoyé, mais un devis DÉJÀ ENVOYÉ qui
    bouge le DIT : le client tient un PDF figé pendant que sa page est
    re-rendue en direct. Sans marqueur, il pouvait signer un montant différent
    de sa pièce jointe sans jamais l'avoir su."""

    def test_un_devis_envoye_modifie_porte_l_horodatage(self):
        devis = self._devis(Devis.Statut.ENVOYE)

        self._resync()

        devis.refresh_from_db()
        marqueur = (devis.etude_params or {}).get('resync_apres_envoi')
        self.assertIsNotNone(marqueur)
        self.assertIn('date', marqueur)
        # Une date ISO lisible, pas un booléen muet.
        self.assertRegex(marqueur['date'], r'^\d{4}-\d{2}-\d{2}T')
        # Et le statut n'a pas bougé (règle #4).
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)

    def test_un_brouillon_ne_porte_aucun_marqueur(self):
        """Rien n'est parti chez le client : il n'y a rien à lui signaler."""
        devis = self._devis(Devis.Statut.BROUILLON)

        self._resync()

        devis.refresh_from_db()
        self.assertIsNone((devis.etude_params or {}).get('resync_apres_envoi'))

    def test_un_envoye_NON_modifie_ne_porte_aucun_marqueur(self):
        """Ligne négociée : rien n'a été recalé, donc rien à signaler."""
        devis = self._devis(Devis.Statut.ENVOYE, prix=Decimal('850.00'))

        self._resync()

        devis.refresh_from_db()
        self.assertIsNone((devis.etude_params or {}).get('resync_apres_envoi'))

    def test_le_marqueur_est_ECRASE_a_chaque_resynchro(self):
        """C'est un « depuis quand », pas un journal qui gonfle."""
        devis = self._devis(Devis.Statut.ENVOYE)
        devis.etude_params = {'resync_apres_envoi': {'date': '2020-01-01T00:00:00'}}
        devis.save(update_fields=['etude_params'])

        self._resync()

        devis.refresh_from_db()
        marqueur = devis.etude_params['resync_apres_envoi']
        self.assertNotEqual(marqueur['date'], '2020-01-01T00:00:00')
        self.assertEqual(len(devis.etude_params['resync_apres_envoi']), 1)

    def test_le_payload_public_expose_la_cle_resync_apres_envoi(self):
        """Le nom de la clé est un CONTRAT : la page proposition la lit."""
        from apps.ventes.models import ShareLink

        devis = self._devis(Devis.Statut.ENVOYE)
        self._resync()
        lien = ShareLink.for_devis(devis)

        reponse = APIClient().get(
            f'/api/django/ventes/proposal/{lien.token}/')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNotNone(reponse.data.get('resync_apres_envoi'))
        self.assertIn('date', reponse.data['resync_apres_envoi'])

    def test_le_payload_public_reste_nul_sans_resynchro(self):
        from apps.ventes.models import ShareLink

        devis = self._devis(Devis.Statut.ENVOYE)
        lien = ShareLink.for_devis(devis)

        reponse = APIClient().get(
            f'/api/django/ventes/proposal/{lien.token}/')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertIsNone(reponse.data.get('resync_apres_envoi'))

    def test_la_designation_suit_le_renommage(self):
        devis = self._devis(Devis.Statut.BROUILLON)

        self._resync(champs=_champs(prix=False, nom=True))

        self.assertEqual(self._ligne(devis).designation, NOUVEAU_NOM)
        self.assertIn('désignation', self._notes(devis).first().body)


class DocumentsClosIntactsTests(PvSyncBase):
    def test_accepte_refuse_expire_ne_bougent_jamais(self):
        clos = [self._devis(statut) for statut in (
            Devis.Statut.ACCEPTE, Devis.Statut.REFUSE, Devis.Statut.EXPIRE)]

        resultat = self._resync()

        self.assertEqual(resultat['devis_touches'], 0)
        self.assertEqual(resultat['lignes_modifiees'], 0)
        for devis in clos:
            self.assertEqual(self._ligne(devis).prix_unitaire, ANCIEN_PRIX,
                             'un document contractuel a été réécrit')
            self.assertEqual(self._notes(devis).count(), 0)


class LignesNegocieesPreserveesTests(PvSyncBase):
    def test_un_prix_negocie_est_conserve_et_annonce(self):
        devis = self._devis(Devis.Statut.BROUILLON, prix=Decimal('850.00'))

        resultat = self._resync()

        self.assertEqual(self._ligne(devis).prix_unitaire, Decimal('850.00'))
        self.assertEqual(resultat['lignes_modifiees'], 0)
        self.assertEqual(resultat['lignes_conservees'], 1)
        self.assertTrue(resultat['avertissements'])
        # Rien n'a bougé ⇒ le chatter reste muet.
        self.assertEqual(self._notes(devis).count(), 0)

    def test_une_remise_de_ligne_vaut_prix_negocie(self):
        devis = self._devis(Devis.Statut.BROUILLON, remise=Decimal('10'))

        self._resync()

        self.assertEqual(self._ligne(devis).prix_unitaire, ANCIEN_PRIX)

    def test_une_designation_retouchee_est_conservee(self):
        devis = self._devis(Devis.Statut.BROUILLON,
                            designation='Panneau (remisé chantier Bouskoura)')

        self._resync(champs=_champs(prix=False, nom=True))

        self.assertEqual(self._ligne(devis).designation,
                         'Panneau (remisé chantier Bouskoura)')


class IsolationTenantTests(PvSyncBase):
    def test_le_devis_d_une_autre_societe_n_est_jamais_touche(self):
        autre = Company.objects.create(nom='Concurrent SARL')
        produit_autre = Produit.objects.create(
            company=autre, nom=ANCIEN_NOM, sku='PVSYNC-PAN-AUTRE',
            prix_achat=Decimal('700.00'), prix_vente=ANCIEN_PRIX,
            quantite_stock=5)
        devis_autre = self._devis(Devis.Statut.BROUILLON, company=autre,
                                  produit=produit_autre)
        devis_maison = self._devis(Devis.Statut.BROUILLON)

        resultat = self._resync()

        self.assertEqual(resultat['devis_touches'], 1)
        self.assertEqual(self._ligne(devis_maison).prix_unitaire, NOUVEAU_PRIX)
        self.assertEqual(self._ligne(devis_autre).prix_unitaire, ANCIEN_PRIX)


class AucuneBoucleTests(PvSyncBase):
    def test_la_resynchronisation_ne_reemet_jamais_l_evenement(self):
        """La garde anti-cascade est STRUCTURELLE : ce chemin n'écrit que des
        lignes de devis, jamais un produit — il ne peut donc pas se rappeler
        lui-même."""
        self._devis(Devis.Statut.BROUILLON)
        emissions = []

        def _compter(sender, **kwargs):
            emissions.append(kwargs)

        events.produit_modifie.connect(_compter, dispatch_uid='pvsync_test')
        try:
            self._resync()
        finally:
            events.produit_modifie.disconnect(dispatch_uid='pvsync_test')

        self.assertEqual(emissions, [])
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.prix_vente, ANCIEN_PRIX,
                         'la resynchronisation a réécrit le produit source')

    def test_rejouer_le_meme_evenement_ne_change_plus_rien(self):
        devis = self._devis(Devis.Statut.BROUILLON)

        premier = self._resync()
        second = self._resync()

        self.assertEqual(premier['lignes_modifiees'], 1)
        self.assertEqual(second['lignes_modifiees'], 0)
        self.assertEqual(second['devis_touches'], 0)
        # Une seule note, pas une par rejeu.
        self.assertEqual(self._notes(devis).count(), 1)

    def test_un_evenement_sans_changement_utile_est_un_no_op(self):
        devis = self._devis(Devis.Statut.BROUILLON)

        resultat = self._resync(champs={})

        self.assertEqual(resultat['lignes_modifiees'], 0)
        self.assertEqual(self._ligne(devis).prix_unitaire, ANCIEN_PRIX)


class CablageBoutEnBoutTests(PvSyncBase):
    """Le chemin RÉEL : PATCH du produit → émission → abonné ventes → Celery.

    On bouchonne la mise en file (pas de courtier en test) mais on vérifie que
    la tâche est bien planifiée APRÈS commit, avec des PK et l'avant/après.
    """

    def test_patch_produit_planifie_la_resynchronisation(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        url = f'/api/django/stock/produits/{self.produit.id}/'

        with patch('apps.ventes.tasks.'
                   'task_resync_devis_apres_produit_modifie') as tache:
            with self.captureOnCommitCallbacks(execute=True):
                reponse = api.patch(url, {'prix_vente': str(NOUVEAU_PRIX)},
                                    format='json')

        self.assertEqual(reponse.status_code, 200)
        tache.delay.assert_called_once()
        args = tache.delay.call_args.args
        self.assertEqual(args[0], self.produit.id)
        self.assertEqual(args[1], self.company.id)
        self.assertIn('prix_vente', args[2])
        self.assertEqual(args[2]['prix_vente'][0], str(ANCIEN_PRIX))
        self.assertEqual(args[3], self.user.id)

    def test_un_champ_sans_effet_sur_les_devis_n_emet_rien(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        url = f'/api/django/stock/produits/{self.produit.id}/'

        with patch('apps.ventes.tasks.'
                   'task_resync_devis_apres_produit_modifie') as tache:
            with self.captureOnCommitCallbacks(execute=True):
                reponse = api.patch(url, {'seuil_alerte': 7}, format='json')

        self.assertEqual(reponse.status_code, 200)
        tache.delay.assert_not_called()
