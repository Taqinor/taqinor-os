"""AFAC96 (C-AFAC-008 + C-AFAC-016) — garde de CLASSE « import idempotent » :
TOUTES les entrées d'import d'argent J5 (relevé bancaire
``paiement_import.commit``, en-têtes de factures ``creer_facture_import`` via
``dataimport.services.commit``, lignes de factures
``ajouter_lignes_facture_import``) sont rejouées avec trois variantes
d'octets du même contenu logique (CRLF, ligne vide finale, relevé chevauchant)
: zéro paiement / facture / ligne créé au second passage. Une nouvelle
fonction d'import publique non enregistrée fait échouer le registre.

Rejoue les sondes FENC-1 / fenc_probe_hash (CRLF : paiement recréé,
`montant_du` 10 000 au lieu de 15 000). Services réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_imports_idempotents"
"""
import inspect
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()
_CTR = [0]

#: Registre des fonctions d'import PUBLIQUES des modules d'import ventes.
#: ``argent`` = rejouée par ce test ; sinon le motif d'exclusion.
REGISTRE = {
    'apps.ventes.paiement_import': {
        'commit': 'argent',
        'dry_run': 'lecture seule (aucune écriture, aperçu du commit)',
    },
    'apps.ventes.domain.imports': {
        'creer_facture_import': 'argent',
        'ajouter_lignes_facture_import': 'argent',
        'creer_devis_import': 'hors J5 (devis, aucun argent dû)',
        'ajouter_lignes_devis_import': 'hors J5 (devis, aucun argent dû)',
    },
}


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


def _octets(lignes, entete, eol='\n', ligne_vide_finale=False):
    texte = eol.join([entete] + lignes) + eol
    if ligne_vide_finale:
        texte += eol
    return texte.encode('utf-8')


VARIANTES = (dict(eol='\r\n'), dict(ligne_vide_finale=True))


class ImportsIdempotentsTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from authentication.models import Company
        n = _nxt()
        self.company = Company.objects.create(
            nom=f'AFAC96 {n}', slug=f'afac96-{n}')
        self.user = User.objects.create_user(
            username=f'afac96-{n}', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client Migre', prenom='',
            email=f'afac96-{n}@example.invalid')

    # ── relevé bancaire ────────────────────────────────────────────────
    def _facture(self):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC96-{_nxt():04d}',
            client=self.client_obj, statut='emise', taux_tva=Decimal('20'),
            montant_ht=Decimal('20000') / Decimal('1.2'),
            montant_tva=Decimal('20000') / Decimal('6'),
            montant_ttc=Decimal('20000'))

    def _releve(self, data):
        from apps.ventes.paiement_import import commit, dry_run
        dry = dry_run(data, 'releve.csv', self.company, user=self.user)
        res = commit(self.company, self.user, dry['token'])
        return dry, res

    def _ligne(self, fac, jour='2026-06-20', montant='5000'):
        return f'{jour};{fac.reference};{montant};virement'

    def _nb_paiements(self, fac):
        from apps.ventes.models import Paiement
        return Paiement.objects.filter(facture=fac).count()

    def _premier_releve(self, fac):
        _dry, res = self._releve(_octets(
            [self._ligne(fac)], 'date;reference;montant;mode'))
        self.assertEqual(res['created'], 1, res)

    def _rejouer_releve(self, fac, **variante):
        _dry, res = self._releve(_octets(
            [self._ligne(fac)], 'date;reference;montant;mode', **variante))
        self.assertEqual(res['created'], 0, (variante, res))
        self.assertEqual(self._nb_paiements(fac), 1)
        fac.refresh_from_db()
        self.assertEqual(fac.montant_du, Decimal('15000.00'))

    def test_releve_crlf_ne_double_pas(self):
        fac = self._facture()
        self._premier_releve(fac)
        self._rejouer_releve(fac, eol='\r\n')

    def test_releve_ligne_vide_finale_ne_double_pas(self):
        fac = self._facture()
        self._premier_releve(fac)
        self._rejouer_releve(fac, ligne_vide_finale=True)

    def test_releve_chevauchant_ne_double_pas(self):
        fac = self._facture()
        self._premier_releve(fac)
        _dry, res = self._releve(_octets(
            [self._ligne(fac),
             self._ligne(fac, jour='2026-06-21', montant='1000')],
            'date;reference;montant;mode'))
        self.assertEqual(res['created'], 1, res)
        self.assertEqual(self._nb_paiements(fac), 2)
        fac.refresh_from_db()
        self.assertEqual(fac.montant_du, Decimal('14000.00'))

    def test_date_non_reconnue_en_revue(self):
        fac = self._facture()
        dry, res = self._releve(_octets(
            [self._ligne(fac, jour='15.06.2026')],
            'date;reference;montant;mode'))
        self.assertEqual(dry['preview'][0]['statut'], 'date_invalide',
                         dry['preview'])
        self.assertEqual(res['created'], 0, res)
        self.assertEqual(self._nb_paiements(fac), 0)

    # ── en-têtes et lignes de factures (migration) ────────────────────
    def _importer_factures(self, data):
        from apps.dataimport.services import commit
        return commit(data, 'factures.csv', 'factures', self.company,
                      self.user)

    def test_factures_entetes_rejouees_sans_doublon(self):
        from apps.ventes.models import Facture
        contenu = ['F-SRC-1,Client Migre,EXT-F96']
        entete = 'reference,client_nom,external_id'
        premier = self._importer_factures(_octets(contenu, entete))
        self.assertEqual(premier['created'], 1, premier)
        for variante in VARIANTES:
            res = self._importer_factures(_octets(contenu, entete, **variante))
            self.assertEqual(res['created'], 0, (variante, res))
        self.assertEqual(
            Facture.objects.filter(company=self.company).count(), 1)

    def test_lignes_factures_rejouees_sans_doublon(self):
        from apps.stock.models import Produit
        from apps.ventes.domain.imports import ajouter_lignes_facture_import
        from apps.ventes.models import Facture, LigneFacture
        self._importer_factures(_octets(
            ['F-SRC-2,Client Migre,EXT-F97'],
            'reference,client_nom,external_id'))
        facture = Facture.objects.get(company=self.company)
        Produit.objects.create(
            company=self.company, nom='Onduleur', sku=f'AFAC96-{_nxt()}',
            prix_vente=Decimal('1000'))
        lignes = [
            {'document_external_id': 'EXT-F97', 'designation': 'Onduleur',
             'quantite': '1', 'prix_unitaire_ht': '1000', 'taux_tva': '20'},
            # Deux lignes identiques LÉGITIMES du même fichier.
            {'document_external_id': 'EXT-F97', 'designation': 'Onduleur',
             'quantite': '1', 'prix_unitaire_ht': '1000', 'taux_tva': '20'},
        ]
        crees, erreurs = ajouter_lignes_facture_import(
            self.company, 'import', lignes, user=self.user)
        self.assertEqual((crees, erreurs), (2, []))
        crees2, _err = ajouter_lignes_facture_import(
            self.company, 'import', lignes, user=self.user)
        self.assertEqual(crees2, 0)
        self.assertEqual(
            LigneFacture.objects.filter(facture=facture).count(), 2)

    # ── registre ──────────────────────────────────────────────────────
    def test_registre_couvre_tous_les_imports(self):
        import importlib
        for chemin, attendus in REGISTRE.items():
            module = importlib.import_module(chemin)
            publiques = {
                nom for nom, obj in inspect.getmembers(module,
                                                       inspect.isfunction)
                if obj.__module__ == module.__name__
                and not nom.startswith('_')
                and ('import' in nom or nom in ('commit', 'dry_run'))}
            self.assertEqual(publiques - set(attendus), set(),
                             f'{chemin} : fonction d\'import non enregistrée')
