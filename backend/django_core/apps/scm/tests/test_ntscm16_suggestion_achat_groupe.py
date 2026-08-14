"""NTSCM16 — Suggestion d'achat groupée multi-fournisseurs avec MOQ/paliers.

Critère d'acceptation : un besoin de 8 unités avec MOQ 10 propose soit
« commander 10 (+2 surstock) » soit « attendre », jamais « commander 8 ».

``_decider_quantite_achat`` (le cœur de la décision MOQ/paliers) est testée
en UNITAIRE avec un objet ``PrixFournisseur`` FACTICE : le champ MOQ réel
(``PrixFournisseur.quantite_minimale_commande``, NTSCM17) n'existe pas
encore en base — hors périmètre de cette lane (``apps.achats``, pas
``apps.scm`` ; voir la docstring d'adaptation de
``services._decider_quantite_achat``). Le chemin d'intégration complet
(``suggerer_achats_groupes``, sans MOQ connu — comportement historique
préservé, ``getattr(..., None)``) est couvert séparément via un
``apps.achats.models.PrixFournisseur`` RÉEL (fixture DB, frontière
cross-app, CLAUDE.md — même justification que les tests NTSCM2/3/5/6/7)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.achats.models import PrixFournisseur
from apps.scm.services import (
    _decider_quantite_achat, recalculer_politiques_stock, suggerer_achats_groupes,
)
from apps.stock.models import Fournisseur, MouvementStock, Produit

from .helpers import make_company, make_user


class _FakePaliers:
    def __init__(self, paliers):
        self._paliers = paliers

    def all(self):
        return self._paliers


class _FakePalier:
    def __init__(self, qte_min, prix):
        self.qte_min = qte_min
        self.prix = Decimal(str(prix))


class _FakePrixFournisseur:
    """Objet minimal portant l'interface lue par ``_decider_quantite_achat``
    (``prix_achat``, ``quantite_minimale_commande``, ``paliers.all()``) —
    sans toucher la base, aucun modèle Django n'est nécessaire ici."""

    def __init__(self, prix_achat, *, moq=None, paliers=None):
        self.prix_achat = Decimal(str(prix_achat))
        self.quantite_minimale_commande = moq
        self.paliers = _FakePaliers(paliers or [])


class DeciderQuantiteAchatTests(TestCase):
    def test_besoin_sous_moq_ne_propose_jamais_la_quantite_brute(self):
        prix_fournisseur = _FakePrixFournisseur(10, moq=10)
        decision = _decider_quantite_achat(Decimal('8'), prix_fournisseur)

        self.assertEqual(decision['decision'], 'sous_moq')
        actions = {opt['action'] for opt in decision['options']}
        self.assertEqual(actions, {'attendre', 'commander_moq'})
        commander_moq = next(
            opt for opt in decision['options'] if opt['action'] == 'commander_moq')
        self.assertEqual(commander_moq['quantite'], 10)
        self.assertEqual(commander_moq['surstock'], '2')
        self.assertTrue(commander_moq['alerte_surstock'])

    def test_sans_moq_connu_comportement_historique_inchange(self):
        prix_fournisseur = _FakePrixFournisseur(10, moq=None)
        decision = _decider_quantite_achat(Decimal('8'), prix_fournisseur)
        self.assertEqual(decision['decision'], 'commander')
        self.assertEqual(decision['quantite'], '8')

    def test_palier_de_prix_reduit_le_cout_total(self):
        # base 10/u ; palier 10+ à 7/u -> commander 10 coûte 70 < 8x10=80.
        prix_fournisseur = _FakePrixFournisseur(10, paliers=[_FakePalier(10, 7)])
        decision = _decider_quantite_achat(Decimal('8'), prix_fournisseur)
        self.assertEqual(decision['decision'], 'commander')
        self.assertEqual(decision['quantite'], '10')
        self.assertEqual(decision['cout_total'], '70')

    def test_moq_atteint_ne_declenche_pas_sous_moq(self):
        prix_fournisseur = _FakePrixFournisseur(10, moq=10)
        decision = _decider_quantite_achat(Decimal('10'), prix_fournisseur)
        self.assertEqual(decision['decision'], 'commander')
        self.assertEqual(decision['quantite'], '10')


class SuggererAchatsGroupesTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-achats-groupes', 'Supply Achats Groupés')
        self.admin = make_user(self.company, 'scm-achats-groupes-admin', 'admin')
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Fournisseur Groupé SARL')
        self.produit = Produit.objects.create(
            company=self.company, nom='Connecteur MC4', prix_vente=8,
            quantite_stock=10, fournisseur=self.fournisseur)
        PrixFournisseur.objects.create(
            company=self.company, produit=self.produit,
            fournisseur=self.fournisseur, prix_achat=3)

        today = timezone.localdate()
        idx_dernier = today.year * 12 + (today.month - 1) - 1
        qty_restante = 100000
        for offset in range(5, -1, -1):
            idx = idx_dernier - offset
            y, m0 = divmod(idx, 12)
            mvt = MouvementStock.objects.create(
                company=self.company, produit=self.produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=300, quantite_avant=qty_restante,
                quantite_apres=qty_restante - 300)
            qty_restante -= 300
            mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
            mvt.save(update_fields=['date'])

        recalculer_politiques_stock(self.company)

    def test_groupe_par_fournisseur_sans_moq_connu(self):
        groupes = suggerer_achats_groupes(self.company)
        self.assertTrue(groupes)
        groupe = next(
            g for g in groupes if g['fournisseur_id'] == self.fournisseur.id)
        self.assertEqual(groupe['fournisseur_nom'], self.fournisseur.nom)
        self.assertEqual(len(groupe['lignes']), 1)
        ligne = groupe['lignes'][0]
        self.assertEqual(ligne['produit_id'], self.produit.id)
        self.assertEqual(ligne['decision'], 'commander')

    def test_endpoint_suggestions_achat_groupe(self):
        from .helpers import auth

        resp = auth(self.admin).get('/api/django/scm/suggestions-achat-groupe/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(any(
            g['fournisseur_id'] == self.fournisseur.id for g in resp.data))
