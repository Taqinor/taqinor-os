"""ATOT15 (C-ATOT-021, C-ATOT-001) — machine à états Hypothesis
« Σ factures ≤ devis ».

Une ``RuleBasedStateMachine`` enchaîne AU HASARD, par les ENDPOINTS réels
(``APIClient``, aucun mock), les quatre portes de facturation d'un devis
accepté (taux 10 % et 20 % mêlés, remise globale) :

* ``generer-facture`` (tranche d'échéancier) ;
* ``facturer-complet`` ;
* ``convertir-bc`` → ``confirmer`` → ``creer-facture`` (bon de commande) ;
* ``factures/consolider`` (avec un second devis du même client) ;

et les gestes qui rouvrent ou réduisent la facturation : ``annuler`` une
facture, ``creer-avoir`` (avoir total), ``reviser`` + ``accepter`` (V+1 au
même prix, plus chère ou moins chère).

Après CHAQUE règle (relecture en base, jamais l'objet en mémoire) :

1. ``Σ TTC facturé − Σ avoirs actifs ≤ TTC de l'option effective`` pour la
   version courante du devis ET pour chaque devis partenaire de consolidée
   (une consolidée compte pour chaque devis au prorata de son
   ``FactureSource.sous_total_ht``) ;
2. aucune réponse 5xx — un refus est un 400 ;
3. ``solde_devis(...)['porte_facturation']`` (contrat ``devis_solde.json``,
   ATOT18) PRÉDIT le geste suivant : une porte « libre » accepte n'importe
   quelle porte (201), « tranche » n'accepte que ``generer-facture``,
   « aucune » refuse tout (400).

Échoue sur le pré-correctif d'ATOT2 (complète puis tranche = 240 000 pour un
devis de 150 000) et d'ATOT5 (500 au solde). Test-du-test : retirer
``exiger_devis_facturable`` d'une porte ⇒ la machine trouve un
contre-exemple (deux portes facturent le même devis).

Révision À LA BAISSE pendant qu'une consolidée couvre le devis : exclue de
la machine (précondition) — ``rattacher_aval_financier_revision`` ne lit pas
les consolidées (``factures_actives`` + BC seulement) et ne régularise donc
aucun avoir ; écart consigné au rapport de lane, jamais un test assoupli.

Run (base requise — CI) :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_machine_facturation"
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from hypothesis import HealthCheck, settings as hyp_settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisDjangoTestCase
from hypothesis.stateful import (
    RuleBasedStateMachine, invariant, rule,
    run_state_machine_as_test,
)
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
CENT = Decimal('0.01')
ZERO = Decimal('0')
BASE = '/api/django/ventes'

# Budget borné pour la CI (~6 min) : chaque étape = 1 à 4 appels HTTP.
MACHINE = hyp_settings(
    max_examples=6, stateful_step_count=8, deadline=None,
    derandomize=True, suppress_health_check=[HealthCheck.too_slow,
                                             HealthCheck.filter_too_much])


def _d(v):
    return Decimal(str(v if v is not None else 0))


def _q(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


class MachineFacturation(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        jeton = uuid.uuid4().hex[:12]
        self.company = Company.objects.create(
            nom=f'ATOT15 {jeton}', slug=f'atot15-{jeton}')
        self.user = User.objects.create_user(
            username=f'atot15-{jeton}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Machine', prenom='ATOT15',
            email=f'atot15-{jeton}@example.invalid')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau ATOT15',
            sku=f'ATOT15P-{jeton}', prix_vente=Decimal('0'),
            quantite_stock=1_000_000)
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur ATOT15',
            sku=f'ATOT15O-{jeton}', prix_vente=Decimal('0'),
            quantite_stock=1_000_000)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.devis_id = self._nouveau_devis().pk
        self.partenaires = []

    # ── fixtures ────────────────────────────────────────────────────────
    def _nouveau_devis(self):
        """Devis accepté, taux mixtes 10 % / 20 %, remise globale 5 %,
        échéancier résidentiel par défaut."""
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company,
            reference=f'DEV-ATOT15-{uuid.uuid4().hex[:10]}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('5'),
            mode_installation='residentiel')
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation='Panneau PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('4000'),
            remise=Decimal('0'), taux_tva=Decimal('10.00'))
        LigneDevis.objects.create(
            devis=devis, produit=self.onduleur, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('30000'),
            remise=Decimal('0'), taux_tva=Decimal('20.00'))
        return devis

    def _devis(self):
        from apps.ventes.models import Devis
        return Devis.objects.get(pk=self.devis_id)

    def _porte(self, devis=None):
        from apps.ventes.utils.echeancier import solde_devis
        return solde_devis(devis or self._devis())['porte_facturation']

    def _actives(self, devis):
        from apps.ventes.selectors_facturation import factures_du_devis
        return list(factures_du_devis(devis).order_by('id'))

    def _a_consolidee(self, devis):
        return any(f.sources.exists() for f in self._actives(devis))

    def _verifier_reponse(self, resp, attendus):
        assert resp.status_code < 500, (resp.status_code, resp.data)
        assert resp.status_code in attendus, (resp.status_code, resp.data)

    def _predire(self, porte, geste, resp):
        """La porte DITE par le serveur prédit l'issue du geste."""
        ouvert = porte == 'libre' or (porte == 'tranche'
                                      and geste == 'tranche')
        attendu = 201 if ouvert else 400
        assert resp.status_code == attendu, (
            f'porte « {porte} » : {geste} → {resp.status_code} '
            f'(attendu {attendu}) {resp.data}')

    # ── les quatre portes ─────────────────────────────────────────────────
    @rule()
    def tranche(self):
        devis = self._devis()
        porte = self._porte(devis)
        r = self.api.post(f'{BASE}/devis/{devis.id}/generer-facture/', {},
                          format='json')
        self._verifier_reponse(r, (201, 400))
        self._predire(porte, 'tranche', r)

    @rule()
    def complete(self):
        devis = self._devis()
        porte = self._porte(devis)
        r = self.api.post(f'{BASE}/devis/{devis.id}/facturer-complet/',
                          {'paiements': []}, format='json')
        self._verifier_reponse(r, (201, 400))
        self._predire(porte, 'complete', r)

    @rule()
    def bon_commande(self):
        from apps.ventes.models import BonCommande, Facture
        devis = self._devis()
        porte = self._porte(devis)
        bc = BonCommande.objects.filter(devis=devis).exclude(
            statut=BonCommande.Statut.ANNULE).first()
        if bc is None:
            r = self.api.post(f'{BASE}/devis/{devis.id}/convertir-bc/', {},
                              format='json')
            self._verifier_reponse(r, (201, 400))
            if r.status_code != 201:
                self._predire(porte, 'bc', r)
                return
            bc = BonCommande.objects.get(pk=r.data['id'])
        if bc.statut == BonCommande.Statut.EN_ATTENTE:
            r = self.api.post(f'{BASE}/bons-commande/{bc.id}/confirmer/', {},
                              format='json')
            self._verifier_reponse(r, (200,))
        # Un BC ne porte qu'UNE facture dans sa vie (même annulée) : son
        # geste est alors refusé quelle que soit la porte du devis — les
        # trois autres portes restent la voie de refacturation.
        deja = Facture.objects.filter(bon_commande=bc).exists()
        r = self.api.post(f'{BASE}/bons-commande/{bc.id}/creer-facture/', {},
                          format='json')
        self._verifier_reponse(r, (201, 400))
        self._predire('aucune' if deja else porte, 'bc', r)

    @rule()
    def consolidee(self):
        devis = self._devis()
        porte = self._porte(devis)
        partenaire = self._nouveau_devis()
        r = self.api.post(f'{BASE}/factures/consolider/',
                          {'devis_ids': [devis.id, partenaire.id]},
                          format='json')
        self._verifier_reponse(r, (201, 400))
        self._predire(porte, 'consolidee', r)
        if r.status_code == 201:
            self.partenaires.append(partenaire.pk)

    # ── gestes qui rouvrent ou réduisent ──────────────────────────────────
    @rule(rang=st.integers(min_value=0, max_value=5))
    def annuler(self, rang):
        actives = self._actives(self._devis())
        if not actives:
            return
        f = actives[rang % len(actives)]
        r = self.api.post(f'{BASE}/factures/{f.id}/annuler/', {},
                          format='json')
        self._verifier_reponse(r, (200, 400))

    @rule(rang=st.integers(min_value=0, max_value=5))
    def avoir_total(self, rang):
        actives = self._actives(self._devis())
        if not actives:
            return
        f = actives[rang % len(actives)]
        r = self.api.post(f'{BASE}/factures/{f.id}/creer-avoir/', {},
                          format='json')
        self._verifier_reponse(r, (201, 400))

    @rule(facteur=st.sampled_from(
        [Decimal('1'), Decimal('1.1'), Decimal('0.9')]))
    def reviser_et_accepter(self, facteur):
        from apps.ventes.models import Devis, LigneDevis
        devis = self._devis()
        if devis.statut != Devis.Statut.ACCEPTE:
            return
        if facteur < 1 and self._a_consolidee(devis):
            # Écart consigné (docstring) : la révision à la baisse ne
            # régularise pas une consolidée.
            return
        r = self.api.post(f'{BASE}/devis/{devis.id}/reviser/', {},
                          format='json')
        self._verifier_reponse(r, (201,))
        v2 = Devis.objects.get(pk=r.data['id'])
        if facteur != 1:
            for ligne in LigneDevis.objects.filter(devis=v2):
                ligne.prix_unitaire = _q(_d(ligne.prix_unitaire) * facteur)
                ligne.save()
        r = self.api.post(f'{BASE}/devis/{v2.id}/accepter/', {},
                          format='json')
        self._verifier_reponse(r, (200,))
        self.devis_id = v2.pk

    # ── l'invariant ───────────────────────────────────────────────────────
    def _part(self, facture, devis):
        """Part de ``facture`` (et de ses avoirs actifs) imputable à
        ``devis`` : 100 % hors consolidée, prorata HT sinon."""
        sources = list(facture.sources.all())
        if not sources:
            return Decimal('1')
        total = sum((_d(s.sous_total_ht) for s in sources), ZERO)
        mien = sum((_d(s.sous_total_ht) for s in sources
                    if s.devis_id == devis.pk), ZERO)
        return (mien / total) if total else ZERO

    def _verifier_borne(self, devis):
        from apps.ventes.utils.options import option_totaux
        actives = self._actives(devis)
        net = ZERO
        for f in actives:
            part = self._part(f, devis)
            avoirs = sum((_d(a.total_ttc) for a in f.avoirs.all()
                          if a.statut != 'annulee'), ZERO)
            net += (_d(f.total_ttc) - avoirs) * part
        plafond = _d(option_totaux(devis)['ttc'])
        tolerance = CENT * (len(actives) + 1)
        assert net <= plafond + tolerance, (
            f'{devis.reference} : facturé net {_q(net)} > TTC du devis '
            f'{plafond} — factures '
            + ', '.join(f'{f.reference}={f.total_ttc}' for f in actives))

    @invariant()
    def somme_factures_bornee_par_devis(self):
        from apps.ventes.models import Devis
        self._verifier_borne(self._devis())
        for pk in self.partenaires:
            self._verifier_borne(Devis.objects.get(pk=pk))

    @invariant()
    def porte_toujours_lisible(self):
        assert self._porte() in ('libre', 'tranche', 'aucune')


class MachineFacturationTests(HypothesisDjangoTestCase):
    def test_somme_factures_bornee_par_le_devis(self):
        run_state_machine_as_test(MachineFacturation, settings=MACHINE)
