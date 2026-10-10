"""ATOT14 (C-ATOT-021) — propriétés « avoir » et « échéancier » sur des
documents PERSISTÉS (oracle `oracles_argent`, ATOT13).

* Avoir : Σ avoirs actifs ≤ TTC facture ; un avoir qui dépasserait le reste
  créditable répond 400 ; l'avoir TOTAL == TTC de la facture (remise et
  arrondi compris) ; un avoir de tranche à taux mixtes porte ≥ 2 paniers et
  Σ TVA = TVA de la facture.
* Échéancier : pour tout jalonnement (1-5 jalons), remise, taux 10/20 mêlés et
  retenue 0-10 % : Σ tranches HT/TVA/TTC == `option_totaux(devis)` au centime,
  chaque tranche HT + TVA = TTC, et annuler la tranche k puis régénérer
  reconstitue l'échéancier (une seule facture active par clé). Aucun 500.

Échoue sur le pré-correctif d'ATOT5 (annulation de l'acompte → matériel ×2)
et d'ATOT6 (panier unique). Endpoints et services réels, aucun mock.

Run (base requise — CI) :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_proprietes_avoir_echeancier"
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from hypothesis import HealthCheck, assume, given, settings as hyp_settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisDjangoTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.facturation.tests.oracles_argent import (
    facture_strategie, fraction_strategie, relire, verifier_chaine_document,
    verifier_reste_a_payer,
)

User = get_user_model()
CENT = Decimal('0.01')
ZERO = Decimal('0')

PROPRIETES = hyp_settings(
    max_examples=8, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow,
                           HealthCheck.filter_too_much])


def _q(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


@st.composite
def echeancier_strategie(draw):
    """1 à 5 jalons en pourcentage, chacun ≥ 1, de somme 100."""
    n = draw(st.integers(min_value=1, max_value=5))
    coupes = sorted(draw(st.lists(st.integers(min_value=1, max_value=99),
                                  min_size=n - 1, max_size=n - 1,
                                  unique=True)))
    bornes = [0] + coupes + [100]
    return [{'pct_or_montant': bornes[i + 1] - bornes[i]} for i in range(n)]


devis_strategie = st.fixed_dictionaries({
    'echeancier': echeancier_strategie(),
    'remise_globale': st.decimals(min_value=Decimal('0'),
                                  max_value=Decimal('99.99'), places=2,
                                  allow_nan=False, allow_infinity=False),
    'retenue': st.sampled_from([0, 5, 10]),
    'base10': st.integers(min_value=1000, max_value=90000),
    'base20': st.integers(min_value=1000, max_value=90000),
})


class _Base(HypothesisDjangoTestCase):
    def _contexte(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        jeton = uuid.uuid4().hex[:12]
        self.company = Company.objects.create(nom=f'ATOT14 {jeton}',
                                              slug=f'atot14-{jeton}')
        self.admin = User.objects.create_user(
            username=f'atot14-{jeton}', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Oracle', prenom='ATOT14',
            email=f'atot14-{jeton}@example.invalid')
        self.produit = Produit.objects.create(
            company=self.company, nom='Avoir ATOT14', sku=f'ATOT14-{jeton}',
            prix_vente=Decimal('0'), quantite_stock=0)
        # Produit des lignes du devis : facturer-complet décompte le stock.
        self.kit = Produit.objects.create(
            company=self.company, nom='Kit ATOT14', sku=f'ATOT14K-{jeton}',
            prix_vente=Decimal('0'), quantite_stock=1_000_000)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _devis(self, lignes, **extra):
        from apps.ventes.models import Devis, LigneDevis
        devis = Devis.objects.create(
            company=self.company,
            reference=f'DEV-ATOT14-{uuid.uuid4().hex[:8]}',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel',
            **extra)
        for i, li in enumerate(lignes):
            # Une ligne produit porte son produit du catalogue
            # (`LigneFacture.produit` est NOT NULL : sans lui → IntegrityError).
            LigneDevis.objects.create(devis=devis, produit=self.kit,
                                      designation=f'L{i}', **li)
        return Devis.objects.get(pk=devis.pk)

    def _generer(self, devis):
        return self.api.post(
            f'/api/django/ventes/devis/{devis.id}/generer-facture/',
            {}, format='json')


class ProprietesAvoirEcheancierTests(_Base):
    @PROPRIETES
    @given(donnees=facture_strategie,
           fractions=st.lists(fraction_strategie, min_size=1, max_size=4))
    def test_avoirs_bornes_et_avoir_total(self, donnees, fractions):
        from apps.ventes.domain.facturation_ops import facturer_devis_complet
        from apps.ventes.models import Avoir
        self._contexte()
        devis = self._devis(donnees['lignes'],
                            remise_globale=donnees['remise_globale'])
        facture, _ = facturer_devis_complet(
            devis=devis, user=self.admin, company=self.company, paiements=[])
        ttc = Decimal(str(relire(facture).total_ttc))

        # Avoir TOTAL d'abord (aucun avoir actif) : == TTC de la facture.
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/', {},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        total = Avoir.objects.get(pk=r.data['id'])
        self.assertEqual(Decimal(str(total.total_ttc)), ttc)
        verifier_chaine_document(total)
        # Plus rien à créditer : tout avoir supplémentaire = 400.
        r = self.api.post(
            f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
            {'lignes': [{'designation': 'Trop', 'quantite': '1',
                         'prix_unitaire': '10', 'taux_tva': '20',
                         'produit': self.produit.id}]}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.api.post(f'/api/django/ventes/avoirs/{total.id}/annuler/', {},
                      format='json')

        # Avoirs partiels successifs : Σ actifs ≤ TTC, refus en 400 au-delà.
        for fraction in fractions:
            ht = max(_q(Decimal(str(relire(facture).total_ht))
                        * fraction / 100), CENT)
            r = self.api.post(
                f'/api/django/ventes/factures/{facture.id}/creer-avoir/',
                {'lignes': [{'designation': 'Partiel', 'quantite': '1',
                             'prix_unitaire': str(ht), 'taux_tva': '20',
                             'produit': self.produit.id}]}, format='json')
            self.assertIn(r.status_code, (201, 400), r.data)
            actifs = sum((Decimal(str(a.total_ttc)) for a in
                          Avoir.objects.filter(facture=facture).exclude(
                              statut=Avoir.Statut.ANNULEE)), ZERO)
            self.assertLessEqual(actifs, ttc + CENT)
            verifier_reste_a_payer(facture)

    @PROPRIETES
    @given(donnees=devis_strategie, k=st.integers(min_value=0, max_value=4))
    def test_echeancier_somme_et_reconstitution(self, donnees, k):
        from apps.ventes.models import Avoir, Facture
        from apps.ventes.utils.options import option_totaux
        self._contexte()
        extra = {'echeancier': donnees['echeancier'],
                 'remise_globale': donnees['remise_globale']}
        if donnees['retenue']:
            extra['retenue_garantie'] = {'taux_pct': donnees['retenue']}
        devis = self._devis([
            {'quantite': Decimal('1'),
             'prix_unitaire': Decimal(donnees['base10']),
             'remise': ZERO, 'taux_tva': Decimal('10')},
            {'quantite': Decimal('1'),
             'prix_unitaire': Decimal(donnees['base20']),
             'remise': ZERO, 'taux_tva': Decimal('20')},
        ], **extra)
        opt = option_totaux(devis)
        n = len(donnees['echeancier'])

        def _actives():
            return list(Facture.objects.filter(devis=devis).exclude(
                statut=Facture.Statut.ANNULEE).order_by('id'))

        def _tout_facturer():
            while True:
                r = self._generer(devis)
                self.assertIn(r.status_code, (201, 400), r.data)
                if r.status_code != 201:
                    break

        def _verifier_sommes():
            actives = _actives()
            self.assertEqual(len({f.cle_tranche for f in actives}),
                             len(actives))
            for f in actives:
                self.assertEqual(
                    Decimal(str(f.total_ht)) + Decimal(str(f.total_tva)),
                    Decimal(str(f.total_ttc)))
            for cle in ('ht', 'tva', 'ttc'):
                attr = {'ht': 'total_ht', 'tva': 'total_tva',
                        'ttc': 'total_ttc'}[cle]
                self.assertEqual(
                    sum((Decimal(str(getattr(f, attr))) for f in actives),
                        ZERO), Decimal(str(opt[cle])), cle)

        # Un devis remisé à ~100 % n'a plus d'échéancier significatif.
        assume(Decimal(str(opt['ttc'])) >= Decimal('1000'))
        _tout_facturer()
        _verifier_sommes()

        # Ventilation : chaque tranche à taux mixtes porte ≥ 2 paniers dont
        # la TVA somme celle de la facture ; un avoir total la reproduit.
        premiere = _actives()[0]
        if premiere.ventilation_tva:
            self.assertGreaterEqual(len(premiere.ventilation_tva), 2)
            r = self.api.post(
                f'/api/django/ventes/factures/{premiere.id}/creer-avoir/',
                {}, format='json')
            self.assertEqual(r.status_code, 201, r.data)
            avoir = Avoir.objects.get(pk=r.data['id'])
            self.assertGreaterEqual(len(avoir.tva_par_taux), 2)
            self.assertEqual(
                sum((Decimal(str(b['montant'])) for b in avoir.tva_par_taux),
                    ZERO), Decimal(str(premiere.total_tva)))
            self.api.post(f'/api/django/ventes/avoirs/{avoir.id}/annuler/',
                          {}, format='json')

        # Annuler la tranche k puis régénérer : l'échéancier se reconstitue.
        cible = _actives()[min(k, n - 1)]
        Facture.objects.filter(pk=cible.pk).update(
            statut=Facture.Statut.ANNULEE)
        _tout_facturer()
        _verifier_sommes()
        self.assertIn(cible.cle_tranche,
                      {f.cle_tranche for f in _actives()})

    def _reglage_societe(self, acompte, materiel, solde):
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.get(company=self.company)
        profil.payment_terms = {'residentiel': {
            'acompte': acompte, 'materiel': materiel, 'solde': solde}}
        profil.save()

    def test_echeancier_fige_insensible_aux_reglages(self):
        """AMET1 (C-AMET-003, D-ECH-FIGE) — un devis accepté figé garde
        30/60/10 quand la société passe à 30/40/30 ; un devis non figé suit
        toujours la société ; second appel idempotent ; forme = contrat."""
        import json
        from pathlib import Path
        from apps.ventes.models import Devis
        from apps.ventes.utils.echeancier import (
            figer_echeancier, tranches_normalisees,
        )
        self._contexte()
        self._reglage_societe(30, 60, 10)
        ligne = [{'quantite': Decimal('1'),
                  'prix_unitaire': Decimal('53166.67'), 'remise': ZERO,
                  'taux_tva': Decimal('20')}]
        devis = self._devis(ligne)
        brouillon = self._devis(ligne)
        Devis.objects.filter(pk=brouillon.pk).update(
            statut=Devis.Statut.BROUILLON)
        self.assertFalse(devis.echeancier)

        rendu = figer_echeancier(devis)
        self.assertFalse(rendu['deja_fige'])
        contrat = json.loads((Path(__file__).resolve().parents[1]
                              / 'contract_samples' / 'echeancier_fige.json')
                             .read_text(encoding='utf-8'))
        self.assertEqual(set(rendu), set(contrat['exemple_figer']))
        self.assertEqual(set(rendu['jalons'][0]),
                         set(contrat['exemple_figer']['jalons'][0]))

        self._reglage_societe(30, 40, 30)
        relu = Devis.objects.get(pk=devis.pk)
        self.assertEqual(
            [(t['key'], t['valeur']) for t in tranches_normalisees(relu)],
            [('acompte', 30), ('materiel', 60), ('solde', 10)])
        self.assertEqual(
            [t['libelle'] for t in tranches_normalisees(relu)],
            ['Acompte', 'Livraison du matériel', 'Solde'])
        # Non figé : suit la société (comportement inchangé).
        self.assertEqual(
            [t['valeur'] for t in tranches_normalisees(
                Devis.objects.get(pk=brouillon.pk))], [30, 40, 30])
        # Idempotent : aucun changement au second appel.
        stocke = relu.echeancier
        second = figer_echeancier(relu)
        self.assertTrue(second['deja_fige'])
        self.assertEqual(Devis.objects.get(pk=devis.pk).echeancier, stocke)
