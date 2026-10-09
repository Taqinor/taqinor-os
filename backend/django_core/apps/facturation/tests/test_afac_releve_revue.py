"""AFAC6 (C-AFAC-009) — le dry-run renvoie TOUTES les lignes et le commit
accepte une ligne ambiguë RÉSOLUE `{ligne, facture_reference}` choisie parmi
ses candidates, avec un bilan par ligne.

Rejoue la sonde FENC-2 (12 lignes : `preview` tronqué à 10, la 12e ambiguë
jamais importable). Services et endpoints réels, aucun mock. Contrat :
`apps/facturation/contract_samples/releve_import_{dry_run,commit}.json`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_releve_revue"
"""
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]

DRY_URL = '/api/django/ventes/paiements/import-releve/dry-run/'
COMMIT_URL = '/api/django/ventes/paiements/import-releve/commit/'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


class ReleveRevueTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC6 Co', slug=f'afac6-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac6_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Revue', prenom='AFAC6',
            email=f'afac6-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _facture(self, ttc):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC6-{_nxt():04d}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)

    def _douze_lignes(self):
        """11 lignes rapprochées par référence + une 12e ambiguë."""
        self.factures = [self._facture(Decimal(1000 + k)) for k in range(11)]
        self.amb_a = self._facture(Decimal('7777'))
        self.amb_b = self._facture(Decimal('7777'))
        lignes = [f'2026-06-20;{f.reference};{f.montant_ttc}'
                  for f in self.factures]
        lignes.append('2026-06-21;;7777')
        texte = '\n'.join(['date;reference;montant'] + lignes) + '\n'
        return texte.encode('utf-8')

    def _dry(self, data):
        r = self.api.post(DRY_URL, {'file': io.BytesIO(data)},
                          format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_dry_run_renvoie_toutes_les_lignes(self):
        dry = self._dry(self._douze_lignes())
        self.assertEqual(dry['total_rows'], 12)
        self.assertEqual(len(dry['preview']), 12)
        derniere = dry['preview'][-1]
        self.assertEqual(derniere['ligne'], 13)
        self.assertEqual(derniere['statut'], 'ambigu')
        self.assertEqual(sorted(derniere['candidats']),
                         sorted([self.amb_a.reference, self.amb_b.reference]))
        self.assertEqual([d['ligne'] for d in dry['revue']], [13])

    def test_commit_resout_une_ambigue(self):
        from apps.ventes.models import Paiement, ReleveImportSession
        dry = self._dry(self._douze_lignes())
        lignes = list(range(2, 13)) + [
            {'ligne': 13, 'facture_reference': self.amb_a.reference}]
        r = self.api.post(COMMIT_URL, {'token': dry['token'], 'lignes': lignes},
                          format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['created'], 12, r.data)
        self.assertEqual(
            Paiement.objects.filter(facture=self.amb_a).count(), 1)
        self.assertEqual(
            Paiement.objects.filter(facture=self.amb_b).count(), 0)
        self.amb_a.refresh_from_db()
        self.amb_b.refresh_from_db()
        self.assertEqual(self.amb_a.montant_du, Decimal('0.00'))
        self.assertEqual(self.amb_b.montant_du, Decimal('7777.00'))
        session = ReleveImportSession.objects.get(token=dry['token'])
        d13 = [d for d in session.decisions if d['ligne'] == 13][0]
        self.assertEqual(d13['facture_id'], self.amb_a.id)
        self.assertEqual(d13['match_type'], 'manuel')

    def test_resolution_hors_candidats_refusee(self):
        from apps.ventes.models import Paiement, ReleveImportSession
        dry = self._dry(self._douze_lignes())
        autre = self.factures[0].reference
        r = self.api.post(
            COMMIT_URL,
            {'token': dry['token'],
             'lignes': [{'ligne': 13, 'facture_reference': autre}]},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('candidates', r.data['detail'])
        # Ligne NON ambiguë transmise sous forme objet : refusée aussi.
        r2 = self.api.post(
            COMMIT_URL,
            {'token': dry['token'],
             'lignes': [{'ligne': 2, 'facture_reference': autre}]},
            format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertEqual(Paiement.objects.filter(
            company=self.company).count(), 0)
        # Refus avant toute écriture : le jeton reste utilisable.
        session = ReleveImportSession.objects.get(token=dry['token'])
        self.assertIsNone(session.consomme_at)

    def test_bilan_par_ligne(self):
        from apps.ventes.models import Paiement
        dry = self._dry(self._douze_lignes())
        r = self.api.post(COMMIT_URL, {'token': dry['token']}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        par_ligne = {x['ligne']: x for x in r.data['results']}
        self.assertEqual(set(par_ligne), set(range(2, 14)))
        cree = par_ligne[2]
        self.assertEqual(cree['statut'], 'created')
        self.assertEqual(cree['facture_reference'], self.factures[0].reference)
        self.assertTrue(Paiement.objects.filter(
            pk=cree['paiement_id'], facture=self.factures[0]).exists())
        self.assertEqual(par_ligne[13]['statut'], 'ambigu')
