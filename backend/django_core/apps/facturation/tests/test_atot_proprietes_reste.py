"""ATOT13 (C-ATOT-021) — propriété « reste à payer » sur des factures
PERSISTÉES, par l'oracle réutilisable `oracles_argent`.

Des factures générées par Hypothesis (lignes à taux 0/10/20, remise de ligne
et globale, palier 100 hérité du devis) sont créées par le service réel
(`facturer_devis_complet`) ; des gestes tirés au hasard (paiement, rejet,
avoir, annulation d'avoir) passent par les services et endpoints réels. Après
chaque geste : `montant_du == TTC − payés valides − avoirs actifs …`,
`0 ≤ montant_du ≤ TTC`, payée ⇔ dû ≤ 0 ; métamorphiques : rejeter un paiement
augmente le reste exactement de son montant, annuler un avoir de son TTC ;
chaque document tient `ht_brut − remise − arrondi = ht_net` et
`ht_net + Σ TVA = TTC`. Échoue sur le pré-correctif d'ATOT8 (facture payée
avec 30 000 dus après l'annulation d'un avoir). Aucun mock.

Run (base requise — CI) :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_atot_proprietes_reste"
"""
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from hypothesis import HealthCheck, given, settings as hyp_settings
from hypothesis.extra.django import TestCase as HypothesisDjangoTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.facturation.tests.oracles_argent import (
    facture_strategie, gestes_strategie, relire, reste_brut,
    verifier_chaine_document, verifier_reste_a_payer,
)

User = get_user_model()
CENT = Decimal('0.01')

PROPRIETES = hyp_settings(
    max_examples=10, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow])


def _q(x):
    return Decimal(x).quantize(CENT, rounding=ROUND_HALF_UP)


class ProprietesResteTests(HypothesisDjangoTestCase):
    def _contexte(self):
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from authentication.models import Company
        jeton = uuid.uuid4().hex[:12]
        company = Company.objects.create(nom=f'ATOT13 {jeton}',
                                         slug=f'atot13-{jeton}')
        admin = User.objects.create_user(
            username=f'atot13-{jeton}', password='x', role_legacy='admin',
            company=company)
        client = Client.objects.create(
            company=company, nom='Oracle', prenom='ATOT13',
            email=f'atot13-{jeton}@example.invalid')
        produit = Produit.objects.create(
            company=company, nom='Avoir ATOT13', sku=f'ATOT13-{jeton}',
            prix_vente=Decimal('0'), quantite_stock=0)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(admin)}')
        return company, admin, client, produit, api

    def _facture(self, donnees, company, admin, client):
        from apps.ventes.domain.facturation_ops import facturer_devis_complet
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        # Produit des lignes du devis : `LigneFacture.produit` est NOT NULL et
        # facturer_devis_complet décompte le stock.
        kit = Produit.objects.create(
            company=company, nom='Kit ATOT13',
            sku=f'ATOT13K-{uuid.uuid4().hex[:8]}',
            prix_vente=Decimal('0'), quantite_stock=1_000_000)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-ATOT13-{uuid.uuid4().hex[:8]}',
            client=client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), mode_installation='residentiel',
            remise_globale=donnees['remise_globale'])
        for i, li in enumerate(donnees['lignes']):
            LigneDevis.objects.create(
                devis=devis, produit=kit, designation=f'Ligne {i}', **li)
        facture, _ = facturer_devis_complet(
            devis=devis, user=admin, company=company, paiements=[])
        return facture

    @PROPRIETES
    @given(donnees=facture_strategie, gestes=gestes_strategie)
    def test_reste_a_payer_apres_chaque_geste(self, donnees, gestes):
        from apps.ventes.domain.encaissements import (
            EncaissementRefuse, encaisser_sur_facture,
        )
        from apps.ventes.domain.recouvrement import rejeter_paiement
        from apps.ventes.models import Avoir, Paiement

        company, admin, client, produit, api = self._contexte()
        facture = self._facture(donnees, company, admin, client)
        verifier_chaine_document(relire(facture))
        verifier_reste_a_payer(facture)

        for geste, fraction in gestes:
            f = relire(facture)
            if geste == 'paiement':
                du = Decimal(str(f.montant_du))
                montant = max(_q(du * fraction / 100), CENT)
                if du <= 0:
                    continue
                try:
                    encaisser_sur_facture(
                        facture=f, user=admin, donnees={
                            'montant': montant, 'date_paiement': date.today(),
                            'mode': 'virement', 'reference': ''})
                except EncaissementRefuse:
                    pass
            elif geste == 'rejet':
                paiement = (Paiement.objects.filter(facture=f)
                            .exclude(statut=Paiement.Statut.REJETE)
                            .order_by('-id').first())
                if paiement is None:
                    continue
                avant = reste_brut(f)
                rejeter_paiement(paiement=paiement, motif='Chèque impayé',
                                 user=admin)
                self.assertEqual(
                    reste_brut(f),
                    avant + Decimal(str(paiement.montant))
                    + Decimal(str(paiement.escompte_montant or 0)))
            elif geste == 'avoir':
                ht = max(_q(Decimal(str(f.total_ht)) * fraction / 200), CENT)
                r = api.post(
                    f'/api/django/ventes/factures/{f.id}/creer-avoir/',
                    {'lignes': [{'designation': 'Avoir', 'quantite': '1',
                                 'prix_unitaire': str(ht), 'taux_tva': '20',
                                 'produit': produit.id}]}, format='json')
                self.assertIn(r.status_code, (201, 400), r.data)
                if r.status_code == 201:
                    verifier_chaine_document(Avoir.objects.get(pk=r.data['id']))
            else:
                avoir = (Avoir.objects.filter(facture=f)
                         .exclude(statut=Avoir.Statut.ANNULEE)
                         .order_by('-id').first())
                if avoir is None:
                    continue
                avant = reste_brut(f)
                r = api.post(f'/api/django/ventes/avoirs/{avoir.id}/annuler/',
                             {}, format='json')
                self.assertEqual(r.status_code, 200, r.data)
                self.assertEqual(reste_brut(f),
                                 avant + Decimal(str(avoir.total_ttc)))
            verifier_reste_a_payer(facture)
