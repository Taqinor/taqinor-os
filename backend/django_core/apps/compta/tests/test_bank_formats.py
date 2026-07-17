"""Tests NTTRE1-3 — parseurs de relevés bancaires normalisés (CFONB120 / MT940 /
camt.053) + endpoint d'import ``import-releve``.

Couvre : chaque parseur produit le bon nombre de lignes avec montants SIGNÉS
corrects ; l'endpoint matérialise autant de ``LigneReleve`` que de lignes
parsées (réutilise ``ajouter_ligne_releve``, aucun nouveau modèle) ; une entrée
mal formée est rejetée avec un message clair.
"""
from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.bank_formats import (
    parser_camt053, parser_cfonb120, parser_mt940)
from apps.compta.models import CompteTresorerie, LigneReleve

User = get_user_model()

_OVER_POS = {'0': '{', '1': 'A', '2': 'B', '3': 'C', '4': 'D',
             '5': 'E', '6': 'F', '7': 'G', '8': 'H', '9': 'I'}
_OVER_NEG = {'0': '}', '1': 'J', '2': 'K', '3': 'L', '4': 'M',
             '5': 'N', '6': 'O', '7': 'P', '8': 'Q', '9': 'R'}


def _zone_montant(montant):
    cents = int((abs(montant) * 100).to_integral_value())
    z = str(cents).zfill(14)
    corps, dernier = z[:13], z[13]
    table = _OVER_NEG if montant < 0 else _OVER_POS
    return corps + table[dernier]


def _ligne_cfonb(*, code='04', jjmmaa='150626', libelle='VIREMENT',
                 ref='REF00001', montant=Decimal('600.00')):
    ligne = [' '] * 120

    def place(txt, start):
        for i, ch in enumerate(txt):
            ligne[start + i] = ch
    place(code, 0)
    place(jjmmaa, 34)
    place(libelle[:31], 48)
    place(ref[:8], 80)
    place(_zone_montant(montant), 90)
    return ''.join(ligne)


class CfonbParserTests(TestCase):
    def test_dix_lignes_montants_signes(self):
        lignes = []
        for i in range(10):
            montant = Decimal('600.00') if i % 2 == 0 else Decimal('-100.00')
            lignes.append(_ligne_cfonb(
                libelle='OP%02d' % i, ref='R%07d' % i, montant=montant))
        contenu = ('\n'.join(lignes)).encode('latin-1')
        res = parser_cfonb120(contenu)
        self.assertEqual(len(res), 10)
        self.assertEqual(res[0]['montant'], Decimal('600.00'))
        self.assertEqual(res[1]['montant'], Decimal('-100.00'))
        self.assertEqual(res[0]['date_operation'], date(2026, 6, 15))
        self.assertEqual(res[0]['libelle'], 'OP00')
        self.assertEqual(res[0]['reference'], 'R0000000')

    def test_soldes_01_07_ignores(self):
        contenu = '\n'.join([
            _ligne_cfonb(code='01'),
            _ligne_cfonb(montant=Decimal('250.00')),
            _ligne_cfonb(code='07'),
        ])
        res = parser_cfonb120(contenu)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['montant'], Decimal('250.00'))

    def test_ligne_mauvaise_longueur_rejetee(self):
        with self.assertRaises(ValueError):
            parser_cfonb120(b'04 trop court')


class Mt940ParserTests(TestCase):
    FICHIER = (
        ':20:RELEVE-001\n'
        ':25:007780000123456789\n'
        ':28C:00001/001\n'
        ':60F:C260601MAD1000,00\n'
        ':61:2606050605C600,00NTRFNONREF//BK1\n'
        ':86:VIREMENT RECU CLIENT ALPHA\n'
        ':61:2606100610D100,00NCHGFRAIS//BK2\n'
        ':86:FRAIS BANCAIRES MENSUELS\n'
        ':61:2606200620C250,50NTRFNONREF//BK3\n'
        ':86:REGLEMENT FACTURE 42\n'
        ':62F:C260630MAD1750,50\n'
        '-\n'
    )

    def test_lignes_et_somme_egale_delta_solde(self):
        res = parser_mt940(self.FICHIER)
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]['montant'], Decimal('600.00'))
        self.assertEqual(res[1]['montant'], Decimal('-100.00'))
        self.assertEqual(res[2]['montant'], Decimal('250.50'))
        self.assertEqual(res[0]['libelle'], 'VIREMENT RECU CLIENT ALPHA')
        self.assertEqual(res[0]['date_operation'], date(2026, 6, 5))
        # Somme des montants signés == solde clôture (:62F:) − ouverture (:60F:).
        somme = sum(mvt['montant'] for mvt in res)
        self.assertEqual(somme, Decimal('1750.50') - Decimal('1000.00'))

    def test_ligne_61_illisible_rejetee(self):
        with self.assertRaises(ValueError):
            parser_mt940(':61:PASUNEDATE\n')


class Camt053ParserTests(TestCase):
    def _fichier(self):
        entrees = [
            ('CRDT', '600.00', '2026-06-05', 'E1', 'VIREMENT ALPHA'),
            ('DBIT', '100.00', '2026-06-10', 'E2', 'FRAIS'),
            ('CRDT', '250.50', '2026-06-15', 'E3', 'REGLEMENT'),
            ('DBIT', '75.25', '2026-06-20', 'E4', 'PRELEVEMENT'),
            ('CRDT', '10.00', '2026-06-25', 'E5', 'INTERETS'),
        ]
        ntrys = ''
        for sens, montant, dt, ref, lib in entrees:
            ntrys += (
                '<Ntry>'
                f'<Amt Ccy="MAD">{montant}</Amt>'
                f'<CdtDbtInd>{sens}</CdtDbtInd>'
                f'<BookgDt><Dt>{dt}</Dt></BookgDt>'
                f'<NtryRef>{ref}</NtryRef>'
                f'<NtryDtls><TxDtls><RmtInf><Ustrd>{lib}</Ustrd>'
                '</RmtInf></TxDtls></NtryDtls>'
                '</Ntry>')
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">'
            f'<BkToCstmrStmt><Stmt>{ntrys}</Stmt></BkToCstmrStmt></Document>'
        ).encode('utf-8')

    def test_cinq_entrees_sens_signe(self):
        res = parser_camt053(self._fichier())
        self.assertEqual(len(res), 5)
        self.assertEqual(res[0]['montant'], Decimal('600.00'))
        self.assertEqual(res[1]['montant'], Decimal('-100.00'))
        self.assertEqual(res[3]['montant'], Decimal('-75.25'))
        self.assertEqual(res[0]['date_operation'], date(2026, 6, 5))
        self.assertEqual(res[0]['libelle'], 'VIREMENT ALPHA')
        self.assertEqual(res[0]['reference'], 'E1')

    def test_xml_malforme_rejete(self):
        with self.assertRaises(ValueError):
            parser_camt053(b'<Document><Ntry></Document>')


class ImportReleveEndpointTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='nttre-import', defaults={'nom': 'NTTRE Import'})
        self.user = User.objects.create_user(
            username='nttre-import-user', password='x', company=self.co,
            role_legacy='responsable')
        services.seed_plan_comptable(self.co)
        self.treso = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Banque import', solde_initial=Decimal('1000'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.rap = services.creer_rapprochement(
            self.co, self.treso,
            date_debut=date(2026, 6, 1), date_fin=date(2026, 6, 30),
            solde_releve=Decimal('1500'), created_by=self.user)
        self.base = (
            f'/api/django/compta/rapprochements/{self.rap.id}/import-releve/')

    def _api(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        return api

    def _upload(self, contenu, nom):
        f = BytesIO(contenu if isinstance(contenu, bytes) else contenu.encode())
        f.name = nom
        return f

    def test_import_cfonb_cree_10_lignes(self):
        lignes = [_ligne_cfonb(libelle='OP%02d' % i) for i in range(10)]
        f = self._upload('\n'.join(lignes).encode('latin-1'), 'releve.cfonb')
        resp = self._api().post(
            self.base + '?format=cfonb120', {'releve': f}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['nombre'], 10)
        self.assertEqual(
            LigneReleve.objects.filter(rapprochement=self.rap).count(), 10)

    def test_import_camt_cree_5_lignes(self):
        f = self._upload(Camt053ParserTests()._fichier(), 'releve.xml')
        resp = self._api().post(
            self.base + '?format=camt053', {'releve': f}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data['nombre'], 5)

    def test_format_inconnu_400(self):
        f = self._upload(b'x', 'releve.txt')
        resp = self._api().post(
            self.base + '?format=xxx', {'releve': f}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_fichier_mal_forme_400(self):
        f = self._upload(b'04 trop court', 'releve.cfonb')
        resp = self._api().post(
            self.base + '?format=cfonb120', {'releve': f}, format='multipart')
        self.assertEqual(resp.status_code, 400)
