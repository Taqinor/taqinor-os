"""AGR609 — recette pompage : la mesure comparée au débit PROMIS du devis,
écart en %, commentaire obligatoire au-delà du seuil SAISI par la société.

Tests COMPORTEMENTAUX, sans mocker le sélecteur ``ventes.selectors.
promesse_pompage_devis`` : la promesse vient d'un vrai devis en base.

Run :
    python manage.py test apps.installations.tests_agr609_comparaison_recette
"""
import itertools
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.installations.models import Installation, RecettePompage
from apps.installations.services import comparer_recette_pompage
from apps.parametres.models import CompanyProfile
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.selectors import promesse_pompage_devis

User = get_user_model()
_seq = itertools.count(1)
BASE = '/api/django/installations'
CONTRAT = json.loads(
    (Path(__file__).resolve().parent / 'contract_samples'
     / 'recette_pompage.json').read_text(encoding='utf-8'))
COURBE = {'debits_m3h': [0, 12, 24, 30, 36, 39],
          'hmt_m': [91, 85, 70, 60, 43, 34]}


class ComparaisonRecetteTests(TestCase):
    def setUp(self):
        from authentication.models import Company
        n = next(_seq)
        self.company = Company.objects.get_or_create(
            slug=f'agr609-co-{n}', defaults={'nom': f'AGR609 Co {n}'})[0]
        self.user = User.objects.create_user(
            username=f'agr609-{n}', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Ferme', prenom='AGR609',
            email=f'agr609-{n}@example.invalid')
        self.pompe = Produit.objects.create(
            company=self.company, nom='Pompe immergée 5,5 kW 380V',
            role_pompage='pompe', type_pompe='immergee', alimentation='tri',
            pompe_kw=Decimal('5.5'), tension_v=380, courbe_pompe=COURBE,
            prix_vente=Decimal('15000'), prix_achat=Decimal('9000'))

    def _devis(self, etude):
        return Devis.objects.create(
            company=self.company, reference=f'DEV-AGR609-{next(_seq)}',
            client=self.client_obj, statut='accepte',
            taux_tva=Decimal('20'), mode_installation='agricole',
            etude_params=etude)

    def _chantier(self, devis, *, pompe=True):
        bom = ([{'produit_id': self.pompe.id, 'designation': self.pompe.nom,
                 'quantite': 1, 'marque': ''}] if pompe else [])
        return Installation.objects.create(
            company=self.company, reference=f'CHT-AGR609-{next(_seq)}',
            client=self.client_obj, devis=devis, bom=bom,
            type_installation='agricole')

    def _seuil(self, valeur):
        profil, _ = CompanyProfile.objects.get_or_create(company=self.company)
        CompanyProfile.objects.filter(pk=profil.pk).update(
            recette_pompage_ecart_max_pct=valeur)

    def _recette(self, chantier):
        r = self.api.post(f'{BASE}/chantiers/{chantier.id}/recette-pompage/',
                          {}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return RecettePompage.objects.get(installation=chantier)

    def _patch(self, recette, corps):
        return self.api.patch(f'{BASE}/recettes-pompage/{recette.id}/',
                              corps, format='json')

    # ── le sélecteur ventes, sans mock ──────────────────────────────────────
    def test_selecteur_promesse_scope_societe(self):
        devis = self._devis({'debit_hmt_m3h': 20, 'hmt_m': 60,
                             'm3_jour': 140.0, 'heures_pompage': 7.0})
        promesse = promesse_pompage_devis(devis.id, self.company)
        self.assertEqual(promesse['debit_hmt_m3h'], 20.0)
        self.assertEqual(promesse['devis_reference'], devis.reference)
        from authentication.models import Company
        autre = Company.objects.create(slug='agr609-autre', nom='Autre')
        self.assertIsNone(promesse_pompage_devis(devis.id, autre))

    # ── l'écart ─────────────────────────────────────────────────────────────
    def test_promis_20_mesure_17_ecart_moins_15(self):
        devis = self._devis({'debit_hmt_m3h': 20, 'hmt_m': 60})
        recette = self._recette(self._chantier(devis))
        r = self._patch(recette, {'debit_mesure_m3h': 17,
                                  'hmt_mesuree_m': 60})
        self.assertEqual(r.status_code, 200, r.data)
        comparaison = r.data['record']['comparaison']
        self.assertEqual(comparaison['ecart_debit_pct'], -15.0)
        self.assertEqual(comparaison['promesse']['debit_hmt_m3h'], 20.0)
        # Débit attendu lu sur la courbe de la pompe à la HMT MESURÉE.
        self.assertEqual(comparaison['debit_attendu_a_hmt_mesuree_m3h'], 30.0)
        self.assertIn('débit promis', comparaison['note_formule'])
        self.assertEqual(r.data['record']['vue_portail']['ecart_debit_pct'],
                         -15.0)

    def test_seuil_10_sans_commentaire_400_avec_commentaire_200(self):
        self._seuil(Decimal('10'))
        devis = self._devis({'debit_hmt_m3h': 20, 'hmt_m': 60})
        recette = self._recette(self._chantier(devis))
        r = self._patch(recette, {'debit_mesure_m3h': 17})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(
            str(r.data['commentaire_ecart'][0]),
            "Écart de -15,0 % au-delà du seuil de la société : commentaire "
            "requis")
        recette.refresh_from_db()
        self.assertIsNone(recette.debit_mesure_m3h)
        r = self._patch(recette, {'debit_mesure_m3h': 17,
                                  'commentaire_ecart': 'Forage colmaté.'})
        self.assertEqual(r.status_code, 200, r.data)
        comparaison = r.data['record']['comparaison']
        self.assertTrue(comparaison['hors_seuil'])
        self.assertTrue(comparaison['commentaire_requis'])
        self.assertEqual(comparaison['seuil_ecart_pct'], 10.0)

    def test_dans_le_seuil_aucun_commentaire_exige(self):
        self._seuil(Decimal('20'))
        devis = self._devis({'debit_hmt_m3h': 20, 'hmt_m': 60})
        recette = self._recette(self._chantier(devis))
        r = self._patch(recette, {'debit_mesure_m3h': 17})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data['record']['comparaison']['hors_seuil'])

    def test_seuil_non_saisi_hors_seuil_null(self):
        devis = self._devis({'debit_hmt_m3h': 20, 'hmt_m': 60})
        recette = self._recette(self._chantier(devis))
        r = self._patch(recette, {'debit_mesure_m3h': 10})
        self.assertEqual(r.status_code, 200, r.data)
        comparaison = r.data['record']['comparaison']
        self.assertEqual(comparaison['ecart_debit_pct'], -50.0)
        self.assertIsNone(comparaison['seuil_ecart_pct'])
        self.assertIsNone(comparaison['hors_seuil'])
        self.assertFalse(comparaison['commentaire_requis'])

    def test_promesse_absente_comparaison_omise_avec_motif(self):
        devis = self._devis({'mode_pompe': 'neuve'})
        recette = self._recette(self._chantier(devis))
        r = self._patch(recette, {'debit_mesure_m3h': 17})
        self.assertEqual(r.status_code, 200, r.data)
        comparaison = r.data['record']['comparaison']
        self.assertIsNone(comparaison['ecart_debit_pct'])
        self.assertIn({'cle': 'ecart_debit_pct',
                       'motif': 'le devis ne porte pas de débit promis'},
                      comparaison['omissions'])

    def test_pompe_sans_courbe_attendu_null_avec_motif(self):
        devis = self._devis({'debit_hmt_m3h': 20})
        recette = self._recette(self._chantier(devis, pompe=False))
        recette.hmt_mesuree_m = 60
        comparaison = comparer_recette_pompage(recette)
        self.assertIsNone(comparaison['debit_attendu_a_hmt_mesuree_m3h'])
        self.assertTrue(any(o['cle'] == 'debit_attendu_a_hmt_mesuree_m3h'
                            for o in comparaison['omissions']))

    def test_devis_revise_apres_la_recette_promesse_inchangee(self):
        devis = self._devis({'debit_hmt_m3h': 20, 'hmt_m': 60})
        recette = self._recette(self._chantier(devis))
        Devis.objects.filter(pk=devis.pk).update(
            etude_params={'debit_hmt_m3h': 35, 'hmt_m': 40})
        r = self._patch(recette, {'debit_mesure_m3h': 17})
        self.assertEqual(r.status_code, 200, r.data)
        promesse = r.data['record']['comparaison']['promesse']
        self.assertEqual(promesse['debit_hmt_m3h'], 20.0)
        self.assertEqual(promesse['hmt_m'], 60.0)
        self.assertEqual(r.data['record']['comparaison']['ecart_debit_pct'],
                         -15.0)

    def test_sortie_conforme_au_contrat_partage(self):
        devis = self._devis({'debit_hmt_m3h': 20, 'hmt_m': 60})
        recette = self._recette(self._chantier(devis))
        r = self._patch(recette, {'debit_mesure_m3h': 17})
        exemple = CONTRAT['exemple']['record']
        self.assertEqual(set(r.data['record']['comparaison']),
                         set(exemple['comparaison']))
        self.assertEqual(set(r.data['record']['comparaison']['promesse']),
                         set(exemple['comparaison']['promesse']))
        self.assertEqual(set(r.data['record']['vue_portail']),
                         set(exemple['vue_portail']))
        self.assertNotIn('prix_achat', json.dumps(r.data, default=str))
