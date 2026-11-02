"""AUD112 — un devis ne peut plus être facturé DEUX FOIS, jusqu'à 200 %.

Les deux voies de facturation étaient totalement aveugles l'une à l'autre :

  * ``bon_commande.creer_facture`` créait la Facture avec ``bon_commande=bc``
    mais SANS ``devis=bc.devis``, et sa seule garde était
    ``Facture.objects.filter(bon_commande=bc).exists()`` ;
  * ``creer_facture_tranche`` compte les tranches déjà émises via
    ``factures_actives(devis)`` = ``devis.factures.all()``, qui ne voit donc
    AUCUNE facture de la chaîne BC ;
  * ``convertir_en_bc`` ne vérifie que l'absence de BC.

Que ``Facture.devis`` soit réservé à l'échéancier est assumé — ce qui ne
l'était pas, c'est l'absence de tout garde-fou croisé qui en découle : un devis
converti en BC puis facturé, puis facturé une seconde fois par l'échéancier,
et le client recevait deux fois la même vente.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import BonCommande, Devis, Facture, LigneDevis
from authentication.models import Company

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class TestDoubleFacturationDevis(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='AUD112 Co', slug=f'aud112-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'aud112_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='AUD112', prenom='Client',
            telephone='+212600000113')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit PV', sku=f'AUD112-{_nxt()}',
            prix_vente=Decimal('10000'), quantite_stock=500)
        self.devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD112-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=self.devis, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        self.bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD112-{_nxt()}',
            devis=self.devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)

    def _facturer_bc(self):
        return self.api.post(
            f'/api/django/ventes/bons-commande/{self.bc.id}/creer-facture/',
            {}, format='json')

    def _facturer_tranche(self):
        return self.api.post(
            f'/api/django/ventes/devis/{self.devis.id}/generer-facture/',
            {}, format='json')

    # ── Sens 1 : BC facturé, puis l'échéancier ────────────────────────────

    def _emettre(self, facture_id):
        return self.api.post(
            f'/api/django/ventes/factures/{facture_id}/emettre/', {},
            format='json')

    def test_bc_facture_puis_echeancier_refuse(self):
        resp = self._facturer_bc()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Facture.objects.count(), 1)
        # VNT20 — la facture de BC naît BROUILLON et ne ferme aucune porte
        # tant qu'elle n'est pas ÉMISE : c'est la facture émise qui bloque.
        self.assertEqual(self._emettre(resp.data['id']).status_code, 200)

        resp2 = self._facturer_tranche()
        self.assertEqual(resp2.status_code, 409, resp2.data)  # CI #997 fuzz : refus d'état, 409
        self.assertEqual(Facture.objects.count(), 1)

    # ── Sens 2 : acompte d'échéancier, puis le BC ─────────────────────────

    def test_tranche_dacompte_puis_bc_refuse(self):
        resp = self._facturer_tranche()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Facture.objects.count(), 1)

        resp2 = self._facturer_bc()
        self.assertEqual(resp2.status_code, 409, resp2.data)  # CI #997 fuzz : refus d'état, 409
        self.assertEqual(Facture.objects.count(), 1)

    # ── ERR-FACT-ACOMPTE-PLUS-BC-DOUBLE (APDF99 P8) ───────────────────────

    def test_brouillon_acompte_auto_puis_facture_bc_jamais_au_dela(self):
        """Acompte automatique de l'acceptation (VNT62, brouillon) PUIS
        facture de BC (complète) : comme ``facturer-complet`` (VNT65), le
        brouillon d'acompte est ANNULÉ — le prévu de la vente reste le prix
        du devis et ``DOC_FACTURATION_DEPASSE_DEVIS`` reste muette."""
        from apps.ventes.coherence.moteur import _Ctx
        from apps.ventes.coherence.registre import REGISTRE, charger_regles
        from apps.ventes.domain.facturation_vente import (
            acompte_a_l_acceptation)

        acompte = acompte_a_l_acceptation(self.devis, self.user)
        self.assertIsNotNone(acompte)
        self.assertEqual(acompte.statut, Facture.Statut.BROUILLON)

        resp = self._facturer_bc()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self._emettre(resp.data['id']).status_code, 200)

        acompte.refresh_from_db()
        self.assertEqual(acompte.statut, Facture.Statut.ANNULEE)
        actives = Facture.objects.filter(devis=self.devis).exclude(
            statut=Facture.Statut.ANNULEE)
        self.assertEqual([f.pk for f in actives], [resp.data['id']])
        charger_regles()
        regle = REGISTRE['DOC_FACTURATION_DEPASSE_DEVIS']
        devis = Devis.objects.get(pk=self.devis.pk)
        self.assertEqual(regle.check(regle, devis, _Ctx(self.company)), [])

    # ── Corollaire : la facture BC porte enfin son devis ──────────────────

    def test_la_facture_bc_porte_son_devis(self):
        resp = self._facturer_bc()
        self.assertEqual(resp.status_code, 201, resp.data)
        facture = Facture.objects.get(pk=resp.data['id'])
        self.assertEqual(facture.devis_id, self.bc.devis_id)
        self.assertEqual(facture.bon_commande_id, self.bc.id)

    def test_le_solde_devis_voit_la_facture_du_bon_de_commande(self):
        from apps.ventes.utils.echeancier import solde_devis

        resp = self._facturer_bc()
        # VNT19/VNT20 — un brouillon est PRÉVU, jamais facturé : le solde
        # voit la facture de BC une fois ÉMISE.
        self.assertEqual(self._emettre(resp.data['id']).status_code, 200)
        self.devis.refresh_from_db()
        solde = solde_devis(self.devis)
        # ATOT2 — comportement INVERSÉ par la tâche : `tranches_facturees` ne
        # compte plus que les factures de TRANCHE ; la facture de BC reste
        # vue par le solde (`facture`) et ferme la porte (`aucune`).
        self.assertEqual(solde['tranches_facturees'], 0)
        self.assertEqual(solde['porte_facturation'], 'aucune')
        self.assertIs(solde['facturation_terminee'], True)  # AMET9
        self.assertEqual(solde['facture'], Decimal('12000.00'))

    # ── Le prédicat partagé lui-même ──────────────────────────────────────

    def test_predicat_partage(self):
        from apps.ventes.selectors import (
            devis_deja_facture, factures_du_devis, factures_via_bon_commande,
        )

        self.assertFalse(devis_deja_facture(self.devis))
        self._facturer_bc()
        self.assertTrue(devis_deja_facture(self.devis))
        self.assertEqual(factures_du_devis(self.devis).count(), 1)
        self.assertEqual(factures_via_bon_commande(self.devis).count(), 1)

    def test_une_facture_annulee_ne_bloque_plus_rien(self):
        from apps.ventes.selectors import devis_deja_facture

        resp = self._facturer_bc()
        facture = Facture.objects.get(pk=resp.data['id'])
        facture.statut = Facture.Statut.ANNULEE
        facture.save(update_fields=['statut'])
        self.assertFalse(devis_deja_facture(self.devis))

    # ── Le cas normal reste ouvert ────────────────────────────────────────

    def test_bc_et_facture_annules_ne_bloquent_plus(self):
        """AARG30 (C-AARG-032) — BC annulé : nouveau BC sur le devis ; facture
        annulée du BC : nouvelle facture ; les vivants bloquent toujours."""
        from apps.ventes.domain.annulation_facture import annuler_facture
        from apps.ventes.models import FactureActivity
        url_bc = f'/api/django/ventes/devis/{self.devis.id}/convertir-bc/'
        self.assertEqual(self.api.post(url_bc).status_code, 409)  # BC vivant
        BonCommande.objects.filter(pk=self.bc.pk).update(
            statut=BonCommande.Statut.ANNULE)
        r = self.api.post(url_bc)
        self.assertEqual(r.status_code, 201, r.data)
        bc2 = BonCommande.objects.get(pk=r.data['id'])
        ancien = BonCommande.objects.get(pk=self.bc.pk)
        self.assertIsNone(ancien.devis_id)
        self.assertEqual(ancien.reference, self.bc.reference)
        self.assertEqual(bc2.devis_id, self.devis.id)
        self.assertTrue(self.devis.activites.filter(
            body__contains='détaché à la recréation').exists())
        BonCommande.objects.filter(pk=bc2.pk).update(
            statut=BonCommande.Statut.CONFIRME)
        url_f = f'/api/django/ventes/bons-commande/{bc2.id}/creer-facture/'
        r = self.api.post(url_f, {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        f1 = Facture.objects.get(bon_commande=bc2)
        # Facture vivante : second essai refusé.
        self.assertEqual(
            self.api.post(url_f, {}, format='json').status_code, 409)
        annuler_facture(f1, user=self.user)
        r = self.api.post(url_f, {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        reference = f1.reference
        f1 = Facture.objects.get(pk=f1.pk)
        self.assertEqual(f1.statut, Facture.Statut.ANNULEE)
        self.assertIsNone(f1.bon_commande_id)
        self.assertEqual(f1.reference, reference)
        self.assertTrue(FactureActivity.objects.filter(
            facture=f1, body__contains='à la recréation').exists())
        self.assertEqual(Facture.objects.get(bon_commande=bc2).pk,
                         r.data['id'])

    def test_un_devis_vierge_reste_facturable_par_les_deux_portes(self):
        autre_devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD112-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=autre_devis, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        resp = self.api.post(
            f'/api/django/ventes/devis/{autre_devis.id}/generer-facture/',
            {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

    # ── ATOT49 — la porte `facturable` servie sur chaque BC ───────────────

    def _devis_et_bc(self):
        devis = Devis.objects.create(
            company=self.company, created_by=self.user,
            client=self.client_obj, reference=f'DEV-AUD112-{_nxt()}',
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation='Kit PV',
            quantite=Decimal('1'), prix_unitaire=Decimal('10000'),
            taux_tva=Decimal('20'))
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-AUD112-{_nxt()}',
            devis=devis, client=self.client_obj,
            statut=BonCommande.Statut.CONFIRME)
        return devis, bc

    def _facturable(self, bc):
        resp = self.api.get('/api/django/ventes/bons-commande/')
        self.assertEqual(resp.status_code, 200)
        rows = (resp.data['results'] if isinstance(resp.data, dict)
                else resp.data)
        return next(r for r in rows if r['id'] == bc.id)['facturable']

    def test_bc_facturable_suit_la_porte(self):
        import json
        from pathlib import Path

        _d2, b2 = self._devis_et_bc()
        # B2 : le devis a déjà une facture COMPLÈTE émise (autre porte).
        Facture.objects.create(
            company=self.company, reference=f'FAC-ATOT49-{_nxt()}',
            devis=b2.devis, client=self.client_obj,
            statut=Facture.Statut.EMISE,
            type_facture=Facture.TypeFacture.COMPLETE)
        # B3 : déjà facturé par ce BC.
        self.assertEqual(self._facturer_bc().status_code, 201)

        _d1, b1 = self._devis_et_bc()
        self.assertEqual(self._facturable(b1), {'ok': True, 'motif': ''})
        f2 = self._facturable(b2)
        self.assertFalse(f2['ok'])
        self.assertIn('déjà facturé', f2['motif'])
        self.assertEqual(
            self._facturable(self.bc),
            {'ok': False, 'motif': 'Une facture existe déjà pour ce BC.'})
        # Le refus de creer-facture porte le MÊME motif.
        resp = self.api.post(
            f'/api/django/ventes/bons-commande/{b2.id}/creer-facture/',
            {}, format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.data['detail'], f2['motif'])
        # Contrat partagé : mêmes clés que l'exemple du fichier.
        ech = json.loads((Path(__file__).resolve().parents[2]
                          / 'facturation' / 'contract_samples'
                          / 'bon_commande_facturable.json').read_text())
        for cle in ('exemple', 'exemple_devis_facture',
                    'exemple_deja_facture'):
            self.assertEqual(set(ech[cle]['facturable']), {'ok', 'motif'})
        self.assertEqual(ech['exemple']['facturable'],
                         self._facturable(b1))
