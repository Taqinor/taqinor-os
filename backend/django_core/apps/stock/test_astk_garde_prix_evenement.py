"""ASTK110 (C-ASTK-020, S2) — garde de CLASSE « un geste de prix = un événement ».

``Produit.prix_vente``, ``tva``, ``prix_fixe_ht`` et ``prix_par_panneau_ht``
chiffrent les lignes des devis : tout geste qui les écrit doit émettre
``core.events.produit_modifie`` (avec l'ancien et le nouveau), sinon l'abonné
ventes ne retarife jamais les brouillons.

DÉCOUVERTE par introspection (aucune liste de routes écrite à la main) : les
gestes d'écriture de ``ProduitViewSet`` sont ``update`` / ``partial_update`` +
chaque ``@action`` dont les méthodes incluent POST/PUT/PATCH
(``get_extra_actions()``). Chacun doit être :

* soit EXÉCUTÉ ici par un scénario (``SCENARIOS``) qui change réellement un
  champ de prix et affirme exactement un événement portant ce champ ;
* soit exempté par une règle NOMMÉE avec sa raison (``EXEMPTIONS``) — jamais
  par numéro de ligne.

Un nouveau geste d'écriture ni scénarisé ni exempté fait échouer la garde en le
NOMMANT ; un geste scénarisé qui n'émet plus fait échouer son scénario en le
nommant (ex. retirer l'émission d'ASTK88 ⇒ ``bulk`` rougit).

Bus réel : un récepteur de test s'abonne, rien n'est mocké.

Run :
    python manage.py test apps.stock.test_astk_garde_prix_evenement -v 2
"""
import itertools
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import Produit
from apps.stock.views.produit import (
    CHAMPS_PRODUIT_SUIVIS_DEVIS, ProduitViewSet,
)
from authentication.models import Company, CustomUser as User
from core.events import produit_modifie

BASE = '/api/django/stock/produits/'
METHODES_ECRITURE = {'post', 'put', 'patch'}
CHAMPS_PRIX = ('prix_vente', 'tva', 'prix_fixe_ht', 'prix_par_panneau_ht')

# Gestes d'écriture exemptés, avec LA RAISON (règle nommée, pas un n° de ligne).
EXEMPTIONS = {
    'inventaire': "pose des quantités (comptage), n'écrit aucun champ de prix",
    'export_xlsx': 'POST de lecture : produit un fichier, aucune écriture',
    'decoupes': 'découpe de stock (catch-weight) : mouvements, pas de prix',
    'photo': "pointe une pièce jointe, n'écrit aucun champ de prix",
    'generer_bcf_reappro': 'crée un BCF (achat) : ne modifie aucun produit',
    'rebuter': 'mouvement de rebut (quantité), pas de prix',
    'dupliquer': "CRÉE un nouveau produit : aucun devis ne le référence encore",
    'unarchive': "bascule is_archived, n'écrit aucun champ de prix",
}

_seq = itertools.count(1)


def gestes_ecriture():
    """Noms des gestes d'écriture de ProduitViewSet (introspection)."""
    noms = {'update', 'partial_update'}
    for action in ProduitViewSet.get_extra_actions():
        methodes = {m.lower() for m in (action.mapping or {})}
        if methodes & METHODES_ECRITURE:
            noms.add(action.__name__)
    return noms


class GardePrixEvenement(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            nom=f'ASTK110 {n}', slug=f'astk110-{n}')
        self.user = User.objects.create_superuser(
            username=f'astk110_admin_{n}', password='x',
            email=f'astk110-{n}@example.test')
        self.user.company = self.company
        self.user.save(update_fields=['company'])
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.produit = Produit.objects.create(
            company=self.company, nom='Forfait pose ASTK110', sku='ASTK110-1',
            prix_achat=Decimal('1000'), prix_vente=Decimal('2500'),
            prix_fixe_ht=Decimal('2000'), prix_par_panneau_ht=Decimal('250'),
            tva=Decimal('20'))
        self.evenements = []

        def recepteur(sender, **kwargs):
            self.evenements.append(kwargs)

        produit_modifie.connect(recepteur, weak=False)
        self.addCleanup(produit_modifie.disconnect, recepteur)

    # ── scénarios : chacun change UN champ de prix par UN geste ────────────
    def _url(self):
        return f'{BASE}{self.produit.pk}/'

    def _put(self, champ, valeur):
        corps = {'nom': self.produit.nom, 'sku': self.produit.sku,
                 'prix_achat': '1000', 'prix_vente': '2500',
                 'prix_fixe_ht': '2000', 'prix_par_panneau_ht': '250',
                 'tva': '20'}
        corps[champ] = valeur
        return self.api.put(self._url(), corps, format='json')

    def _patch(self, champ, valeur):
        return self.api.patch(self._url(), {champ: valeur}, format='json')

    def _bulk(self, champ, valeur):
        if champ != 'prix_vente':
            return None  # le geste ne sait écrire que prix_vente
        return self.api.post(
            f'{BASE}bulk/',
            {'ids': [self.produit.pk], 'action': 'set_price',
             'mode': 'percent', 'valeur': 10}, format='json')

    SCENARIOS = {
        'update': ('_put', {'prix_vente': '3000.00', 'tva': '10',
                            'prix_fixe_ht': '2200', 'prix_par_panneau_ht': '300'}),
        'partial_update': ('_patch', {'prix_vente': '3000.00', 'tva': '10',
                                      'prix_fixe_ht': '2200',
                                      'prix_par_panneau_ht': '300'}),
        'bulk': ('_bulk', {'prix_vente': None}),
    }

    def test_tout_geste_de_prix_emet(self):
        # 1) Découverte : chaque geste d'écriture est scénarisé OU exempté.
        gestes = gestes_ecriture()
        non_classes = sorted(
            g for g in gestes
            if g not in self.SCENARIOS and g not in EXEMPTIONS)
        self.assertEqual(
            non_classes, [],
            'Geste(s) d\'écriture de ProduitViewSet ni scénarisé(s) ni '
            f'exempté(s) : {non_classes}. Un geste qui écrit un champ de prix '
            f'({", ".join(CHAMPS_PRIX)}) doit émettre produit_modifie et '
            'avoir un scénario ici ; sinon, l\'exempter avec sa raison.')
        self.assertTrue(set(CHAMPS_PRODUIT_SUIVIS_DEVIS) >= set(CHAMPS_PRIX))

        # 2) Exécution : chaque geste scénarisé, chaque champ qu'il sait écrire.
        for geste, (methode, champs) in self.SCENARIOS.items():
            self.assertIn(geste, gestes, f'scénario orphelin : {geste}')
            for champ, valeur in champs.items():
                with self.subTest(geste=geste, champ=champ):
                    self.evenements.clear()
                    self.produit.refresh_from_db()
                    reponse = getattr(self, methode)(champ, valeur)
                    if reponse is None:
                        continue
                    self.assertEqual(
                        reponse.status_code, 200,
                        f'{geste}/{champ} : {reponse.content}')
                    self.assertEqual(
                        len(self.evenements), 1,
                        f'Le geste `{geste}` change `{champ}` mais émet '
                        f'{len(self.evenements)} événement(s) produit_modifie '
                        '(attendu : exactement 1).')
                    self.assertIn(champ, self.evenements[0]['champs'],
                                  f'`{geste}` : événement sans `{champ}`')
                    ancien, nouveau = self.evenements[0]['champs'][champ]
                    self.assertNotEqual(ancien, nouveau)
                    # remet le produit dans son état de départ pour la suite
                    Produit.objects.filter(pk=self.produit.pk).update(
                        prix_vente=Decimal('2500'), tva=Decimal('20'),
                        prix_fixe_ht=Decimal('2000'),
                        prix_par_panneau_ht=Decimal('250'))

    def test_exemptions_et_scenarios_sont_des_gestes_reels(self):
        """Pas d'exemption fantôme : chaque nom exempté existe encore (sinon
        la liste d'exemptions dérive silencieusement)."""
        gestes = gestes_ecriture()
        fantomes = sorted(g for g in EXEMPTIONS if g not in gestes)
        self.assertEqual(fantomes, [], fantomes)
