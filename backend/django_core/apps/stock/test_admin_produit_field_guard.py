"""Garde de CHAMP — `prix_achat`/`courbe_pompe` ne peuvent pas être vidés
depuis l'administration Django une fois renseignés.

Contexte : le garde de suppression de `ProduitAdmin` (voir
`test_admin_produit_delete_guard.py`) protège la LIGNE, mais un
superutilisateur pouvait toujours ouvrir la fiche produit et VIDER
`prix_achat` (prix fournisseur négocié) ou `courbe_pompe` (courbe
constructeur OSP) d'un simple « Enregistrer » — perte silencieuse d'une
donnée non reconstructible, sans le moindre avertissement.

Ces tests prouvent, sur `ProduitAdminForm` directement (pas de round-trip
HTTP complet : le formulaire admin de `Produit` porte ~30 champs, la plupart
optionnels — tester le formulaire isolément évite le bruit des champs sans
rapport avec ce garde) :
  * vider `prix_achat` déjà renseigné (→ 0) est refusé, avec le message
    dédié, et la valeur en base reste intacte ;
  * vider `courbe_pompe` déjà renseignée (→ vide) est refusé de même ;
  * le garde reste CIBLÉ : changer `prix_achat` vers une AUTRE valeur non
    vide (le fournisseur a baissé son prix) n'est PAS bloqué ;
  * une pompe déjà « prix à renseigner » (`prix_achat=0`) reste librement
    éditable — le garde ne s'accroche qu'à la transition renseigné → vide ;
  * un produit fraîchement créé peut légitimement rester sans prix.
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.admin import CHAMP_CATALOGUE_VIDE_INTERDIT, ProduitAdminForm
from apps.stock.models import Produit
from testkit.factories import CompanyFactory, ProduitFactory


class ProduitAdminFieldGuardTests(TestCase):
    def setUp(self):
        super().setUp()
        self.company = CompanyFactory(
            nom='Catalogue Champs Réels', slug='catalogue-champs-reels')
        self.produit = ProduitFactory(
            company=self.company, nom='Pompe OSP 30-15',
            prix_achat=Decimal('980.00'), prix_vente=Decimal('1350.00'),
            courbe_pompe={'debits_m3h': [0, 12, 18], 'hmt_m': [91, 85, 60]})

    def _data(self, **overrides):
        """Payload minimal — les champs requis SANS rapport avec ce garde
        (ex. `unite_stock`) peuvent manquer sans fausser les assertions : la
        validation par champ de Django continue jusqu'à `clean()` (le
        formulaire), qui s'exécute quels que soient les autres champs en
        échec (chaque erreur reste attachée à SON propre champ)."""
        data = {
            'nom': self.produit.nom,
            'prix_vente': str(self.produit.prix_vente),
            'prix_achat': str(self.produit.prix_achat),
            'quantite_stock': str(self.produit.quantite_stock),
            'seuil_alerte': str(self.produit.seuil_alerte),
            'courbe_pompe': self.produit.courbe_pompe,
        }
        data.update(overrides)
        return data

    def test_vidage_prix_achat_refuse(self):
        form = ProduitAdminForm(
            data=self._data(prix_achat='0'), instance=self.produit)
        form.is_valid()
        self.assertIn(CHAMP_CATALOGUE_VIDE_INTERDIT,
                      form.errors.get('prix_achat', []))
        produit = Produit.objects.get(pk=self.produit.pk)
        self.assertEqual(produit.prix_achat, Decimal('980.00'))

    def test_vidage_courbe_pompe_refuse(self):
        form = ProduitAdminForm(
            data=self._data(courbe_pompe=''), instance=self.produit)
        form.is_valid()
        self.assertIn(CHAMP_CATALOGUE_VIDE_INTERDIT,
                      form.errors.get('courbe_pompe', []))
        produit = Produit.objects.get(pk=self.produit.pk)
        self.assertEqual(produit.courbe_pompe['hmt_m'], [91, 85, 60])

    def test_changement_prix_vers_autre_valeur_non_bloque(self):
        """Le garde est CIBLÉ : le fournisseur baisse son prix, ce n'est PAS
        un vidage — pas d'erreur sur `prix_achat`."""
        form = ProduitAdminForm(
            data=self._data(prix_achat='850.00'), instance=self.produit)
        form.is_valid()
        self.assertNotIn('prix_achat', form.errors)

    def test_produit_sans_prix_reste_librement_editable(self):
        """Une pompe « prix à renseigner » (`prix_achat=0`) n'est PAS
        rattrapée par le garde : 0 -> une valeur, ou 0 -> 0, restent libres."""
        produit_nu = ProduitFactory(
            company=self.company, nom='Pompe OSP sans prix',
            prix_achat=Decimal('0'), prix_vente=Decimal('1500.00'))
        form = ProduitAdminForm(
            data={
                'nom': produit_nu.nom,
                'prix_vente': str(produit_nu.prix_vente),
                'prix_achat': '0',
                'quantite_stock': '0',
                'seuil_alerte': '0',
            },
            instance=produit_nu)
        form.is_valid()
        self.assertNotIn('prix_achat', form.errors)

    def test_creation_sans_prix_non_bloquee(self):
        """Un produit fraîchement créé part légitimement sans prix (pompe
        OSP « prix à renseigner ») — le garde ne s'applique qu'à l'ÉDITION
        d'un produit déjà existant (`self.instance.pk`)."""
        form = ProduitAdminForm(data={
            'nom': 'Pompe OSP toute neuve',
            'prix_vente': '0',
            'prix_achat': '0',
            'quantite_stock': '0',
            'seuil_alerte': '0',
        })
        form.is_valid()
        self.assertNotIn('prix_achat', form.errors)
        self.assertNotIn('courbe_pompe', form.errors)
