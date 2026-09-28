"""QAH2 — Machine d'états Hypothesis sur la chaîne documentaire ventes.

``RuleBasedStateMachine`` sur les transitions RÉELLES (jamais réimplémentées)
d'un même Devis → BonCommande → Facture : brouillon/envoye/accepte/refuse/
expire (rule #4), puis conversion en bon de commande, puis facturation — SOIT
par l'échéancier du devis (acompte/matériel/solde), SOIT par le bon de
commande — jamais les deux (AUD112, « les deux portes se voient enfin »).

Chaque transition passe par LE code de production réel :

* ``envoyer``/``accepter`` — les services canoniques documentés comme
  « LE chemin unique » (``apps.ventes.services.mark_devis_sent``/
  ``accept_devis``, partagés par le viewset ET la proposition web publique) ;
* ``expirer`` — ``apps.ventes.services.expire_stale_devis`` (le beat QJ5) ;
* ``refuser``, ``convertir_bc``, ``generer_facture_directe``, et les actions
  du bon de commande (``confirmer``/``marquer-livre``/``annuler``/
  ``creer-facture``) — les VRAIES routes DRF (``APIClient``), pas une
  réimplémentation de leurs gardes.

DEUX invariants d'ATTEIGNABILITÉ, vérifiés après CHAQUE étape :

1. Un ``BonCommande`` ou une ``Facture`` n'existe pour ce devis QUE si son
   statut est ``accepte`` (jamais une facture depuis un devis non accepté
   hors la voie explicitement prévue par le code — ``creer_facture_tranche``
   lève déjà ``ValueError`` sinon, ce test prouve qu'aucun autre chemin ne le
   contourne).
2. Les deux chaînes de facturation (échéancier devis vs bon de commande) ne
   coexistent JAMAIS pour le même devis (AUD112) — chaque porte se ferme dès
   que l'autre a déjà facturé.

Toute divergence trouvée devient une tâche ERR (jamais un test assoupli).
Base de données requise (Postgres) — CI SEULEMENT, ne tourne pas en local
sans docker.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import tag
from hypothesis import HealthCheck, settings as hyp_settings
from hypothesis.extra.django import TestCase as HypothesisDjangoTestCase
from hypothesis.stateful import (
    RuleBasedStateMachine, invariant, rule, run_state_machine_as_test,
)
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.facturation.models import Facture
from apps.ventes.models import BonCommande, Devis, LigneDevis
from apps.ventes.services import AcceptError, accept_devis, mark_devis_sent
from apps.ventes.domain.recouvrement import expire_stale_devis
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_produit,
)

User = get_user_model()

# DB-backed + plusieurs appels HTTP par étape : gate CI-only (le module ne
# tourne pas en local sans docker/Postgres) — voir la docstring du module.
DOC = hyp_settings(
    max_examples=12, stateful_step_count=10, deadline=None,
    derandomize=True, suppress_health_check=[HealthCheck.too_slow])


def _make_user(company):
    """Référence UNIQUE (jamais ``_quote_engine_common.make_user``, dont le
    ``username`` FIXE collisionne ici) : ``run_state_machine_as_test`` peut
    exécuter jusqu'à ``max_examples`` simulations complètes SANS rollback
    intermédiaire garanti entre elles (la méthode de test qui l'appelle
    n'est pas elle-même décorée ``@given`` — seul ce cas précis bénéficie du
    reset Hypothesis+Django par exemple). ``username`` est unique
    GLOBALEMENT (``AbstractUser``) : un identifiant fixe réutilisé par
    plusieurs simulations lèverait une collision d'intégrité."""
    return User.objects.create_user(
        username=f'qah2-{uuid.uuid4().hex[:16]}', password='x',
        role_legacy='responsable', company=company)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DocumentLifecycleMachine(RuleBasedStateMachine):
    """Un seul Devis, exploré par une SÉQUENCE aléatoire de transitions
    réelles — voir la docstring du module pour la liste et les deux
    invariants d'atteignabilité vérifiés après chaque étape."""

    def __init__(self):
        super().__init__()
        self.company = make_company()
        self.user = _make_user(self.company)
        self.api = _auth(self.user)
        self.client_obj = make_client(self.company)

        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-QAH2-LIFECYCLE',
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
            mode_installation='residentiel',
            # QJ5 — validité déjà dépassée : dès que le devis atteint
            # « envoyé », la règle ``expirer`` ci-dessous peut le faire
            # basculer sans avoir à retoucher la date en cours de route.
            date_validite=date.today() - timedelta(days=1))
        panneau = make_produit(
            self.company, 'Panneau PV QAH2', 'QAH2-PV', '1000')
        onduleur = make_produit(
            self.company, 'Onduleur QAH2', 'QAH2-OND', '5000')
        LigneDevis.objects.create(
            devis=self.devis, produit=panneau, designation='Panneau PV QAH2',
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'), taux_tva=Decimal('10'))
        LigneDevis.objects.create(
            devis=self.devis, produit=onduleur, designation='Onduleur QAH2',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            remise=Decimal('0'), taux_tva=Decimal('20'))

        self.bc = None

    # ── Devis : brouillon / envoye / accepte / refuse / expire (rule #4) ────

    @rule()
    def envoyer(self):
        """``mark_devis_sent`` — SEUL chemin brouillon → envoyé ; jamais une
        régression (un devis déjà accepté/refusé/expiré reste inchangé)."""
        self.devis.refresh_from_db()
        avant = self.devis.statut
        mark_devis_sent(devis=self.devis, user=self.user)
        self.devis.refresh_from_db()
        if avant == Devis.Statut.BROUILLON:
            self.assertEqualStatut(self.devis.statut, Devis.Statut.ENVOYE)
        else:
            self.assertEqualStatut(self.devis.statut, avant)

    @rule()
    def accepter(self):
        """``accept_devis`` (``idempotent_reaccept=False``, comme l'action
        du viewset) — succès UNIQUEMENT depuis brouillon/envoyé ; sinon
        ``AcceptError`` et le statut ne bouge pas."""
        self.devis.refresh_from_db()
        avant = self.devis.statut
        try:
            nouveau = accept_devis(
                devis=self.devis, user=self.user, nom='Client QAH2',
                date_acceptation=date.today(), option='',
                idempotent_reaccept=False)
        except AcceptError:
            self.devis.refresh_from_db()
            assert self.devis.statut == avant, (
                'AcceptError refusé mais le statut a quand même bougé '
                f'({avant} → {self.devis.statut}).')
            return
        assert avant in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE), (
            f'accept_devis a réussi depuis un statut non éligible : {avant}.')
        self.devis = nouveau
        assert self.devis.statut == Devis.Statut.ACCEPTE

    @rule()
    def refuser(self):
        """La VRAIE route ``/devis/<id>/refuser/`` — succès UNIQUEMENT depuis
        brouillon/envoyé (garde inline du viewset)."""
        self.devis.refresh_from_db()
        avant = self.devis.statut
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/refuser/', {},
            format='json')
        self.devis.refresh_from_db()
        if avant in (Devis.Statut.BROUILLON, Devis.Statut.ENVOYE):
            assert resp.status_code == 200, resp.data
            assert self.devis.statut == Devis.Statut.REFUSE
        else:
            assert resp.status_code == 409, (resp.status_code, resp.data)
            assert self.devis.statut == avant

    @rule()
    def expirer(self):
        """``expire_stale_devis`` (le beat QJ5) — bascule UNIQUEMENT un devis
        ``envoye`` dont la validité est dépassée (posée une fois pour toutes
        à la création) ; jamais accepté/refusé/déjà expiré/brouillon."""
        self.devis.refresh_from_db()
        avant = self.devis.statut
        expire_stale_devis()
        self.devis.refresh_from_db()
        if avant == Devis.Statut.ENVOYE:
            assert self.devis.statut == Devis.Statut.EXPIRE
        else:
            assert self.devis.statut == avant

    # ── Devis → BonCommande ──────────────────────────────────────────────────

    @rule()
    def convertir_bc(self):
        """``/devis/<id>/convertir-bc/`` — succès UNIQUEMENT si le devis est
        accepté ET qu'aucun BC n'existe déjà pour lui."""
        self.devis.refresh_from_db()
        devis_accepte = self.devis.statut == Devis.Statut.ACCEPTE
        bc_deja_present = BonCommande.objects.filter(
            devis=self.devis).exists()
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/convertir-bc/', {},
            format='json')
        if devis_accepte and not bc_deja_present:
            assert resp.status_code == 201, resp.data
            self.bc = BonCommande.objects.get(pk=resp.data['id'])
        else:
            assert resp.status_code == 400, (resp.status_code, resp.data)

    # ── BonCommande : en_attente / confirme / livre / annule ────────────────

    @rule()
    def confirmer_bc(self):
        if self.bc is None:
            return
        self.bc.refresh_from_db()
        avant = self.bc.statut
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/confirmer/', {},
            format='json')
        if avant == BonCommande.Statut.EN_ATTENTE:
            assert resp.status_code == 200, resp.data
            self.bc.refresh_from_db()
            assert self.bc.statut == BonCommande.Statut.CONFIRME
        else:
            assert resp.status_code == 400, (resp.status_code, resp.data)
            self.bc.refresh_from_db()
            assert self.bc.statut == avant

    @rule()
    def marquer_livre_bc(self):
        if self.bc is None:
            return
        self.bc.refresh_from_db()
        avant = self.bc.statut
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/marquer-livre/',
            {}, format='json')
        if avant == BonCommande.Statut.CONFIRME:
            assert resp.status_code == 200, resp.data
            self.bc.refresh_from_db()
            assert self.bc.statut == BonCommande.Statut.LIVRE
        else:
            assert resp.status_code == 400, (resp.status_code, resp.data)
            self.bc.refresh_from_db()
            assert self.bc.statut == avant

    @rule()
    def annuler_bc(self):
        if self.bc is None:
            return
        self.bc.refresh_from_db()
        avant = self.bc.statut
        facture_active = Facture.objects.filter(
            bon_commande=self.bc).exclude(
                statut=Facture.Statut.ANNULEE).exists()
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/annuler/', {},
            format='json')
        if avant != BonCommande.Statut.LIVRE and not facture_active:
            assert resp.status_code == 200, resp.data
            self.bc.refresh_from_db()
            assert self.bc.statut == BonCommande.Statut.ANNULE
        else:
            assert resp.status_code == 400, (resp.status_code, resp.data)
            self.bc.refresh_from_db()
            assert self.bc.statut == avant

    # ── Facturation : DEUX portes, JAMAIS les deux ensemble (AUD112) ────────

    @rule()
    def creer_facture_bc(self):
        """``/bons-commande/<id>/creer-facture/`` — succès UNIQUEMENT si le
        BC est confirmé/livré, qu'aucune facture ne lui est déjà attachée, ET
        qu'aucune facture d'échéancier n'existe déjà pour le devis
        (AUD112 : les deux portes se voient)."""
        if self.bc is None:
            return
        self.bc.refresh_from_db()
        bc_ok = self.bc.statut in (
            BonCommande.Statut.CONFIRME, BonCommande.Statut.LIVRE)
        facture_bc_deja = Facture.objects.filter(
            bon_commande=self.bc).exists()
        facture_devis_deja = Facture.objects.filter(
            devis=self.devis).exclude(bon_commande=self.bc).exists()
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/creer-facture/',
            {}, format='json')
        if bc_ok and not facture_bc_deja and not facture_devis_deja:
            assert resp.status_code == 201, resp.data
        else:
            assert resp.status_code == 400, (resp.status_code, resp.data)

    @rule()
    def generer_facture_directe(self):
        """``/devis/<id>/generer-facture/`` (échéancier) — succès UNIQUEMENT
        si le devis est accepté, qu'aucune facture BC n'existe déjà (AUD112),
        et qu'il reste une tranche à facturer."""
        self.devis.refresh_from_db()
        devis_accepte = self.devis.statut == Devis.Statut.ACCEPTE
        facture_bc_deja = Facture.objects.filter(
            devis=self.devis, bon_commande__isnull=False).exists()
        resp = self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/',
            {}, format='json')
        if not devis_accepte or facture_bc_deja:
            assert resp.status_code == 400, (resp.status_code, resp.data)
            return
        # Le devis est accepté et aucune facture BC ne le bloque : le seul
        # motif de refus restant est un échéancier déjà complet — l'ORACLE
        # est la fonction réelle qui décrit « la prochaine tranche »,
        # jamais un nombre de tranches réimplémenté ici.
        from apps.ventes.utils.echeancier import next_tranche
        self.devis.refresh_from_db()
        tranche = next_tranche(self.devis)
        if tranche is None:
            assert resp.status_code == 400, (resp.status_code, resp.data)
        else:
            assert resp.status_code == 201, resp.data

    # ── Invariants — vérifiés après CHAQUE étape ─────────────────────────────

    @invariant()
    def bon_de_commande_seulement_si_accepte(self):
        self.devis.refresh_from_db()
        if BonCommande.objects.filter(devis=self.devis).exists():
            assert self.devis.statut == Devis.Statut.ACCEPTE, (
                'Un bon de commande existe pour un devis '
                f'« {self.devis.statut} » — jamais accepté.')

    @invariant()
    def facture_seulement_si_accepte(self):
        self.devis.refresh_from_db()
        if Facture.objects.filter(devis=self.devis).exists():
            assert self.devis.statut == Devis.Statut.ACCEPTE, (
                'Une facture existe pour un devis '
                f'« {self.devis.statut} » — jamais accepté, hors toute '
                'voie explicitement prévue par le code.')

    @invariant()
    def une_seule_chaine_de_facturation(self):
        """AUD112 — jamais une facture-échéancier ET une facture-BC en même
        temps pour le même devis (« les deux portes se voient enfin »)."""
        self.devis.refresh_from_db()
        factures = list(Facture.objects.filter(devis=self.devis))
        via_bc = [f for f in factures if f.bon_commande_id is not None]
        via_echeancier = [f for f in factures if f.bon_commande_id is None]
        assert not (via_bc and via_echeancier), (
            'AUD112 violé : facture(s) via bon de commande ET via '
            f'échéancier coexistent pour {self.devis.reference}.')

    # ── Petit utilitaire (pas une règle) ─────────────────────────────────────
    def assertEqualStatut(self, obtenu, attendu):
        assert obtenu == attendu, f'{obtenu!r} != {attendu!r}'


@tag('slow')
class DocumentLifecycleInvariants(HypothesisDjangoTestCase):
    """Point d'entrée unittest — Postgres requis (CI seulement)."""

    def test_devis_bc_facture_lifecycle(self):
        run_state_machine_as_test(DocumentLifecycleMachine, settings=DOC)
