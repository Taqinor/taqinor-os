"""AFAC5 (C-AFAC-008 + C-AFAC-016) — l'import de relevé est idempotent PAR
LIGNE et n'invente jamais une date.

Rejoue les sondes FENC-1 (relevé ré-encodé CRLF/BOM/ligne vide : 2 paiements),
L2-C-AFAC-008 (ré-export FR : 2 paiements, `idempotency_key` None) et FENC-9
(« 15.06.2026 » importé daté du jour). Services réels `dry_run`/`commit`,
parseur réel, contrainte réelle — aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_releve_idempotent"
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()
_CTR = [0]


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _csv(lignes, entete='date;reference;montant;mode', eol='\n', bom=False,
         ligne_vide_finale=False):
    texte = eol.join([entete] + lignes) + eol
    if ligne_vide_finale:
        texte += eol
    data = texte.encode('utf-8')
    return (b'\xef\xbb\xbf' + data) if bom else data


class ReleveIdempotentTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        self.company = Company.objects.create(
            nom='AFAC5 Co', slug=f'afac5-co-{_nxt()}')
        self.user = User.objects.create_user(
            username=f'afac5_resp_{_nxt()}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Releve', prenom='AFAC5',
            email=f'afac5-{_nxt()}@example.invalid')

    def _facture(self, ttc=Decimal('20000')):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC5-{_nxt():04d}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)

    def _importer(self, data, nom='releve.csv', lignes=None):
        from apps.ventes.paiement_import import commit, dry_run
        dry = dry_run(data, nom, self.company, user=self.user)
        res = commit(self.company, self.user, dry['token'], lignes=lignes)
        return dry, res

    def _paiements(self, facture):
        from apps.ventes.models import Paiement
        return list(Paiement.objects.filter(facture=facture).order_by('id'))

    def _premier_import(self, fac):
        dry, res = self._importer(_csv([f'2026-06-20;{fac.reference};5000;virement']))
        self.assertEqual(res['created'], 1, res)
        return dry, res

    def test_reencodage_ne_double_pas(self):
        fac = self._facture()
        self._premier_import(fac)
        for variante in (
                dict(eol='\r\n'), dict(bom=True), dict(ligne_vide_finale=True)):
            data = _csv([f'2026-06-20;{fac.reference};5000;virement'], **variante)
            dry, res = self._importer(data)
            self.assertEqual(dry['preview'][0]['statut'], 'doublon_import',
                             (variante, dry['preview']))
            self.assertEqual(res['created'], 0, (variante, res))
        paiements = self._paiements(fac)
        self.assertEqual(len(paiements), 1)
        self.assertTrue(paiements[0].idempotency_key)
        fac.refresh_from_db()
        self.assertEqual(fac.montant_du, Decimal('15000.00'))

    def test_reexport_format_fr_ne_double_pas(self):
        fac = self._facture()
        self._premier_import(fac)
        data = _csv([f'virement;5 000,00;{fac.reference};20/06/2026'],
                    entete='mode;montant;reference;date')
        dry, res = self._importer(data)
        self.assertEqual(dry['preview'][0]['statut'], 'doublon_import')
        self.assertEqual(res['created'], 0, res)
        self.assertEqual(len(self._paiements(fac)), 1)
        fac.refresh_from_db()
        self.assertEqual(fac.montant_du, Decimal('15000.00'))

    def test_chevauchant_importe_seulement_la_nouvelle(self):
        fac = self._facture()
        self._premier_import(fac)
        data = _csv([f'2026-06-20;{fac.reference};5000;virement',
                     f'2026-06-25;{fac.reference};2000;virement'])
        dry, res = self._importer(data)
        statuts = [d['statut'] for d in dry['preview']]
        self.assertEqual(statuts, ['doublon_import', 'a_importer'])
        self.assertEqual(res['created'], 1, res)
        self.assertEqual(
            sorted(p.montant for p in self._paiements(fac)),
            [Decimal('2000.00'), Decimal('5000.00')])

    def test_lignes_identiques_du_meme_fichier(self):
        fac = self._facture()
        data = _csv([f'2026-06-20;{fac.reference};3000;virement',
                     f'2026-06-20;{fac.reference};3000;virement'])
        _, res = self._importer(data)
        self.assertEqual(res['created'], 2, res)
        paiements = self._paiements(fac)
        self.assertEqual(len(paiements), 2)
        self.assertNotEqual(paiements[0].idempotency_key,
                            paiements[1].idempotency_key)
        # Le même relevé ré-encodé : les DEUX lignes sont des doublons.
        dry, res2 = self._importer(_csv(
            [f'2026-06-20;{fac.reference};3000;virement',
             f'2026-06-20;{fac.reference};3000;virement'], eol='\r\n'))
        self.assertEqual([d['statut'] for d in dry['preview']],
                         ['doublon_import', 'doublon_import'])
        self.assertEqual(res2['created'], 0, res2)

    def test_date_non_reconnue_en_revue(self):
        fac = self._facture()
        data = _csv([f'15.06.2026;{fac.reference};5000;virement',
                     f';{fac.reference};4000;virement'])
        dry, res = self._importer(data)
        self.assertEqual([d['statut'] for d in dry['preview']],
                         ['date_invalide', 'date_invalide'])
        self.assertEqual({d['ligne'] for d in dry['revue']}, {2, 3})
        self.assertEqual(res['created'], 0, res)
        self.assertEqual(self._paiements(fac), [])
        from apps.ventes.models import Paiement
        self.assertFalse(Paiement.objects.filter(
            company=self.company,
            date_paiement=timezone.localdate()).exists())

    def test_second_commit_meme_jeton_refuse(self):
        from apps.ventes.paiement_import import commit, dry_run
        from apps.ventes.models import ReleveImportSession
        fac = self._facture()
        dry = dry_run(_csv([f'2026-06-20;{fac.reference};5000;virement']),
                      'r.csv', self.company, user=self.user)
        commit(self.company, self.user, dry['token'])
        with self.assertRaises(ValueError):
            commit(self.company, self.user, dry['token'])
        self.assertEqual(len(self._paiements(fac)), 1)
        session = ReleveImportSession.objects.get(token=dry['token'])
        self.assertIsNotNone(session.consomme_at)
