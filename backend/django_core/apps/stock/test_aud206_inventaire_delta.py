"""AUD206 — `valider_inventaire_session` applique un DELTA, jamais un
remplacement brut.

Défaut d'origine (`stock/services.py`) : la validation posait
``produit.quantite_stock = ligne.quantite_comptee``. Entre le snapshot
(``quantite_theorique``, figé à la génération de la session — jusqu'à 30/90/180
jours plus tôt pour un comptage tournant ``generer_comptages_tournants``) et la
validation, tout mouvement légitime (réception, vente, transfert) était
silencieusement effacé.

Le comptage physique constate un ÉCART ; c'est cet écart qu'il faut appliquer à
la quantité LIVE verrouillée, pas le niveau absolu compté.

INTERNE — admin uniquement.

Run :
    python manage.py test apps.stock.test_aud206_inventaire_delta -v 2
"""
from decimal import Decimal

from django.test import TestCase

from apps.stock.models import (
    InventaireSession, LigneInventaire, MouvementStock, Produit,
)
from apps.stock.services import valider_inventaire_session


def make_company(slug='aud206-co', nom='AUD206 Co'):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class TestValidationInventaireDelta(TestCase):
    def setUp(self):
        self.company = make_company()
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau 550W', sku='AUD206-1',
            prix_achat=Decimal('1000'), prix_vente=Decimal('1500'),
            quantite_stock=100)
        # Session générée comme le fait `generer_comptages_tournants` :
        # quantité théorique = stock au moment de la GÉNÉRATION.
        self.session = InventaireSession.objects.create(
            company=self.company, reference='INV-AUD206-1',
            motif='Comptage tournant — classe A')

    def _ligne(self, comptee, theorique=100):
        return LigneInventaire.objects.create(
            session=self.session, produit=self.produit,
            quantite_theorique=theorique, quantite_comptee=comptee)

    def _bouger_stock(self, delta):
        """Mouvement légitime survenu APRÈS la génération de la session."""
        self.produit.quantite_stock += delta
        self.produit.save(update_fields=['quantite_stock'])

    def test_mouvement_entre_snapshot_et_validation_est_preserve(self):
        # Comptage : 95 constatés pour 100 théoriques => écart de -5.
        self._ligne(comptee=95)
        # Puis une réception légitime de +10 arrive avant la validation.
        self._bouger_stock(+10)

        res = valider_inventaire_session(self.session, None)

        self.produit.refresh_from_db()
        # 110 (live) + (-5) (écart constaté) = 105.
        # Avant AUD206 : 95 — les 10 unités reçues étaient effacées.
        self.assertEqual(self.produit.quantite_stock, 105)
        self.assertEqual(res, {'ajustes': 1, 'inchanges': 0})

    def test_mouvement_sortant_entre_snapshot_et_validation_est_preserve(self):
        # Comptage : 103 constatés pour 100 théoriques => écart de +3.
        self._ligne(comptee=103)
        # Une vente légitime de 20 unités passe avant la validation.
        self._bouger_stock(-20)

        valider_inventaire_session(self.session, None)

        self.produit.refresh_from_db()
        # 80 (live) + 3 = 83. Avant AUD206 : 103.
        self.assertEqual(self.produit.quantite_stock, 83)

    def test_mouvement_trace_les_quantites_live(self):
        self._ligne(comptee=95)
        self._bouger_stock(+10)

        valider_inventaire_session(self.session, None)

        mvt = MouvementStock.objects.get(reference=self.session.reference)
        self.assertEqual(mvt.type_mouvement,
                         MouvementStock.TypeMouvement.AJUSTEMENT)
        self.assertEqual(mvt.quantite, 5)          # |écart|
        self.assertEqual(mvt.quantite_avant, 110)  # live, pas le snapshot
        self.assertEqual(mvt.quantite_apres, 105)

    def test_sans_mouvement_intermediaire_le_compte_fait_foi(self):
        """Cas nominal : sans mouvement entre-temps, le résultat est identique
        au comportement historique (le niveau compté)."""
        self._ligne(comptee=95)

        valider_inventaire_session(self.session, None)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 95)

    def test_ligne_sans_ecart_ne_touche_rien(self):
        self._ligne(comptee=100)
        self._bouger_stock(+10)

        res = valider_inventaire_session(self.session, None)

        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 110)
        self.assertEqual(res, {'ajustes': 0, 'inchanges': 1})
        self.assertFalse(
            MouvementStock.objects.filter(
                reference=self.session.reference).exists())
