"""Tests FG42 — import relevé bancaire (dry-run + commit)."""
import csv
import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def make_company(slug='ri-co', nom='RI Co'):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _make_csv(rows, headers=None):
    """Crée un CSV minimal en mémoire."""
    if headers is None:
        headers = ['date', 'reference', 'montant', 'mode']
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, delimiter=';')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode('utf-8')


class _ReleveImportBase(TestCase):
    """Fixture partagée (société, opérateur, client, factures) + les deux
    gestes de l'import. Aucune assertion ici : les classes de test en
    héritent sans réexécuter les tests des autres."""

    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='ri_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='RI', prenom='Client',
            email='ri@example.com', telephone='+212600000080')

    def _facture(self, ref=None, ttc=Decimal('12000'), statut='emise'):
        n = _nxt()
        ref = ref or f'FAC-{MONTH}-RI{n:04d}'
        f = Facture.objects.create(
            company=self.company, reference=ref,
            client=self.client_obj, statut=statut,
            taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'),
            montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc,
        )
        return f

    DRY_URL = '/api/django/ventes/paiements/import-releve/dry-run/'
    COMMIT_URL = '/api/django/ventes/paiements/import-releve/commit/'

    def _dry(self, csv_bytes):
        """AUD121 — aperçu ; renvoie la réponse (qui porte le jeton)."""
        return self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')

    def _commit(self, csv_bytes, lignes=None):
        """AUD121 — le commit ne prend plus de fichier : dry-run d'abord,
        puis on rejoue le jeton. Renvoie (reponse_dry, reponse_commit)."""
        dry = self._dry(csv_bytes)
        if dry.status_code != 200:
            return dry, dry
        body = {'token': dry.data['token']}
        if lignes is not None:
            body['lignes'] = lignes
        return dry, self.api.post(self.COMMIT_URL, body, format='json')


class TestReleveImport(_ReleveImportBase):
    # ── Validation ────────────────────────────────────────────────────────────

    def test_no_file_returns_400(self):
        r = self.api.post(self.DRY_URL)
        self.assertEqual(r.status_code, 400)

    # ── Dry-run ───────────────────────────────────────────────────────────────

    def test_dry_run_match_by_reference(self):
        """Dry-run : ligne avec référence exacte → statut a_importer."""
        fac = self._facture(ref=f'FAC-{MONTH}-RI0099', ttc=Decimal('15000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20',
            'reference': fac.reference,
            'montant': '15000',
            'mode': 'virement',
        }])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)},
            format='multipart')
        r.accepted_renderer = None
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['matched'], 1)
        self.assertEqual(r.data['preview'][0]['statut'], 'a_importer')
        self.assertEqual(r.data['preview'][0]['facture_reference'], fac.reference)

    def test_dry_run_no_match(self):
        """Dry-run : ligne sans facture correspondante → statut non_trouve."""
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': 'FAC-INCONNU', 'montant': '5000',
        }])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['matched'], 0)
        self.assertEqual(r.data['preview'][0]['statut'], 'non_trouve')

    def test_dry_run_invalid_montant(self):
        """Ligne sans montant valide → statut montant_invalide."""
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': 'X', 'montant': 'abc',
        }])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['preview'][0]['statut'], 'montant_invalide')

    def test_dry_run_exposes_columns(self):
        """Dry-run renvoie le mapping colonnes reconnues + non reconnues."""
        csv_bytes = _make_csv([{'date': '2026-06-20', 'reference': 'X',
                                'montant': '100', 'unknown_col': 'x'}],
                              headers=['date', 'reference', 'montant', 'unknown_col'])
        r = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertIn('date', r.data['columns'].values())
        self.assertIn('unknown_col', r.data['unmapped'])

    def test_dry_run_no_write(self):
        """Dry-run ne crée aucun Paiement."""
        fac = self._facture(ttc=Decimal('10000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference, 'montant': '10000',
        }])
        before = Paiement.objects.filter(company=self.company).count()
        self.api.post(
            self.DRY_URL, {'file': io.BytesIO(csv_bytes)}, format='multipart')
        after = Paiement.objects.filter(company=self.company).count()
        self.assertEqual(before, after)

    # ── Commit ────────────────────────────────────────────────────────────────

    def test_commit_creates_paiement(self):
        """Commit : ligne matchée → Paiement créé, facture passée payée."""
        fac = self._facture(ttc=Decimal('9000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '9000', 'mode': 'virement',
        }])
        _, r = self._commit(csv_bytes)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['created'], 1)
        self.assertEqual(r.data['skipped'], 0)
        fac.refresh_from_db()
        self.assertEqual(fac.statut, 'payee')
        p = Paiement.objects.filter(company=self.company, facture=fac).first()
        self.assertIsNotNone(p)
        self.assertEqual(p.montant, Decimal('9000'))

    def test_commit_surpaiement_skipped(self):
        """Un montant supérieur au reste dû est refusé (garde sur-paiement)."""
        fac = self._facture(ttc=Decimal('5000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '6000', 'mode': 'virement',
        }])
        _, r = self._commit(csv_bytes)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['skipped'], 1)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 0)

    def test_commit_already_paid_skipped(self):
        """Une facture déjà payée est ignorée (jamais rapprochée)."""
        fac = self._facture(ttc=Decimal('8000'), statut='payee')
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '8000',
        }])
        _, r = self._commit(csv_bytes)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['skipped'], 1)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 0)

    def test_commit_montant_seul_sans_donneur_dordre_part_en_revue(self):
        """AUD121 — le fallback montant-seul AUTONOME n'existe plus.

        Sans référence ET sans donneur d'ordre identifiable, la ligne ne
        s'affecte plus toute seule : elle part en file de revue."""
        fac = self._facture(ttc=Decimal('7777'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': '',
            'montant': '7777',
        }])
        dry, r = self._commit(csv_bytes)
        self.assertEqual(dry.data['preview'][0]['statut'],
                         'client_non_identifie')
        self.assertEqual(len(dry.data['revue']), 1)
        self.assertEqual(r.data['created'], 0)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 0)

    def test_commit_montant_avec_donneur_dordre_identifie(self):
        """AUD121 — avec le nom du donneur d'ordre dans le libellé, le
        rapprochement par montant redevient légitime (un seul candidat)."""
        payeur = Client.objects.create(
            company=self.company, nom='Bouskoura Energie', prenom='',
            email='bouskoura@ri.com', telephone='+212600000090')
        fac = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-RIB001',
            client=payeur, statut='emise', taux_tva=Decimal('20'),
            montant_ht=Decimal('6378.33'), montant_tva=Decimal('1275.67'),
            montant_ttc=Decimal('7654'))
        csv_bytes = _make_csv(
            [{'date': '2026-06-20',
              'libelle': 'VIR SEPA BOUSKOURA ENERGIE CPTE 123',
              'montant': '7654'}],
            headers=['date', 'libelle', 'montant'])
        dry, r = self._commit(csv_bytes)
        self.assertEqual(dry.data['preview'][0]['statut'], 'a_importer')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['created'], 1)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 1)

    def test_commit_no_match_skipped(self):
        """Ligne sans facture correspondante → skipped."""
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': 'FAC-INCONNU', 'montant': '1234',
        }])
        _, r = self._commit(csv_bytes)
        self.assertIn(r.status_code, (200, 201))
        self.assertEqual(r.data['skipped'], 1)

    def test_commit_company_scoped(self):
        """Les factures d'une autre société ne sont jamais matchées."""
        other_co, _ = Company.objects.get_or_create(
            slug='other-ri-co', defaults={'nom': 'Other RI Co'})
        other_client = Client.objects.create(
            company=other_co, nom='Other', email='other@ri.com',
            telephone='+212600000081')
        other_fac = Facture.objects.create(
            company=other_co, reference=f'FAC-{MONTH}-ORI001',
            client=other_client, statut='emise',
            taux_tva=Decimal('20'),
            montant_ht=Decimal('5000'), montant_tva=Decimal('1000'),
            montant_ttc=Decimal('6000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': other_fac.reference, 'montant': '6000',
        }])
        _, r = self._commit(csv_bytes)
        self.assertIn(r.status_code, (200, 201))
        self.assertEqual(r.data['created'], 0)
        self.assertEqual(Paiement.objects.filter(facture=other_fac).count(), 0)


class TestAUD121FileDeRevueEtJeton(_ReleveImportBase):
    """AUD121 — les trois cas ROUGES avant le correctif.

      1. un montant partagé par deux factures ouvertes de CLIENTS
         DIFFÉRENTS créditait la première venue ; il doit désormais
         partir en `ambigu`, sans aucune affectation ;
      2. `commit` sans jeton de dry-run écrivait quand même ; il doit
         répondre 400 ;
      3. le même fichier importé deux fois créait deux jeux de Paiement.
    """

    def test_montant_partage_par_deux_clients_part_en_ambigu(self):
        autre_client = Client.objects.create(
            company=self.company, nom='Bernoussi', prenom='Autre',
            email='autre@ri.com', telephone='+212600000082')
        f1 = self._facture(ttc=Decimal('12000'))
        f2 = Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-RIX999',
            client=autre_client, statut='emise', taux_tva=Decimal('20'),
            montant_ht=Decimal('10000'), montant_tva=Decimal('2000'),
            montant_ttc=Decimal('12000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': '', 'montant': '12000',
        }])
        dry, r = self._commit(csv_bytes)
        self.assertEqual(dry.data['preview'][0]['statut'], 'ambigu')
        self.assertEqual(dry.data['ambigus'], 1)
        self.assertTrue(dry.data['revue'], 'file de revue vide')
        self.assertEqual(r.data['created'], 0)
        self.assertEqual(
            Paiement.objects.filter(facture__in=[f1, f2]).count(), 0)

    def test_commit_sans_jeton_refuse(self):
        fac = self._facture(ttc=Decimal('4000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '4000',
        }])
        self._dry(csv_bytes)  # le jeton existe, mais on ne le fournit pas
        r = self.api.post(self.COMMIT_URL, {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 0)

    def test_commit_jeton_inconnu_refuse(self):
        r = self.api.post(
            self.COMMIT_URL, {'token': 'jeton-fabrique'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_meme_fichier_importe_deux_fois_ne_double_pas(self):
        """Facture de 20 000 réglée PARTIELLEMENT par le relevé (5 000) :
        elle reste ouverte, donc le second import passerait sans la garde
        de contenu."""
        fac = self._facture(ttc=Decimal('20000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '5000',
        }])
        _, r1 = self._commit(csv_bytes)
        self.assertEqual(r1.data['created'], 1)
        _, r2 = self._commit(csv_bytes)
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 1)

    def test_jeton_a_usage_unique(self):
        fac = self._facture(ttc=Decimal('6000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '6000',
        }])
        dry = self._dry(csv_bytes)
        token = dry.data['token']
        r1 = self.api.post(self.COMMIT_URL, {'token': token}, format='json')
        self.assertEqual(r1.status_code, 201, r1.data)
        r2 = self.api.post(self.COMMIT_URL, {'token': token}, format='json')
        self.assertEqual(r2.status_code, 400, r2.data)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 1)

    def test_commit_n_ecrit_que_les_lignes_selectionnees(self):
        f1 = self._facture(ttc=Decimal('1100'))
        f2 = self._facture(ttc=Decimal('2200'))
        csv_bytes = _make_csv([
            {'date': '2026-06-20', 'reference': f1.reference,
             'montant': '1100'},
            {'date': '2026-06-20', 'reference': f2.reference,
             'montant': '2200'},
        ])
        dry = self._dry(csv_bytes)
        lignes = [d['ligne'] for d in dry.data['preview']
                  if d['facture_reference'] == f1.reference]
        r = self.api.post(
            self.COMMIT_URL, {'token': dry.data['token'], 'lignes': lignes},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['created'], 1)
        self.assertEqual(Paiement.objects.filter(facture=f1).count(), 1)
        self.assertEqual(Paiement.objects.filter(facture=f2).count(), 0)

    def test_jeton_d_une_autre_societe_introuvable(self):
        """Multi-tenant : un jeton n'est jamais lisible d'une autre société."""
        fac = self._facture(ttc=Decimal('3000'))
        csv_bytes = _make_csv([{
            'date': '2026-06-20', 'reference': fac.reference,
            'montant': '3000',
        }])
        dry = self._dry(csv_bytes)
        other_co, _ = Company.objects.get_or_create(
            slug='ri-tenant-co', defaults={'nom': 'RI Tenant Co'})
        other_user = User.objects.create_user(
            username='ri_other_resp', password='x', role_legacy='responsable',
            company=other_co)
        r = auth(other_user).post(
            self.COMMIT_URL, {'token': dry.data['token']}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Paiement.objects.filter(facture=fac).count(), 0)
