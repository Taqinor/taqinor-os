"""Dossier contractuel d'un chantier — cycle de vie, montants, contenu.

Rejoue le parcours réel par le bus d'événements (``core.events``) : une
acceptation de devis crée le chantier (``installations``) puis, APRÈS le
commit, les cinq brouillons ; la dés-acceptation les annule ; la
ré-acceptation les rétablit ; un acte signé reste signé. Chaque montant d'un
contenu égale ``plan_facturation`` / ``solde_devis`` au centime (deux
variantes de livraison) ; aucun prix d'achat ni marge ne sort ; les clés
servies égalent celles du contrat d'API (contract_samples/*.json) ; la
traduction arabe a le même schéma et les mêmes montants.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.documents.tests.test_contrats_dossier"
"""
import itertools
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import fitz
from django.contrib.auth import get_user_model
from django.test import TestCase, tag

from apps.crm.models import Client
from apps.documents.contrats import contenu as K
from apps.documents.contrats import services as S
from apps.documents.contrats import types as T
from apps.documents.models import ActeContractuel
from apps.installations.models import Installation
from apps.stock.models import Produit
from apps.ventes.models import Devis, Facture, LigneDevis, Paiement
from authentication.models import Company
from core.events import devis_acceptation_annulee, devis_accepted

User = get_user_model()
_seq = itertools.count(1)
SAMPLES = Path(__file__).resolve().parents[1] / 'contract_samples'
PRIX_ACHAT = Decimal('7777.77')
SIG = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAf'
       'FcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==')


def charger_echantillon(nom):
    return json.loads((SAMPLES / nom).read_text(encoding='utf-8'))


def texte_pdf(octets):
    doc = fitz.open(stream=octets, filetype='pdf')
    try:
        return '\n'.join(page.get_text() for page in doc)
    finally:
        doc.close()


def cles(valeur, prefixe=''):
    """Ensemble récursif des chemins de clés (dict : chaque clé ; liste : le
    premier élément) — la forme, jamais les valeurs."""
    sortie = set()
    if isinstance(valeur, dict):
        for k, v in valeur.items():
            chemin = f'{prefixe}.{k}' if prefixe else k
            sortie.add(chemin)
            sortie |= cles(v, chemin)
    elif isinstance(valeur, list) and valeur and isinstance(
            valeur[0], (dict, list)):
        sortie |= cles(valeur[0], prefixe + '[]')
    return sortie


def toutes_les_cles(valeur):
    if isinstance(valeur, dict):
        for k, v in valeur.items():
            yield k
            yield from toutes_les_cles(v)
    elif isinstance(valeur, list):
        for v in valeur:
            yield from toutes_les_cles(v)


class Vente:
    """Une vente résidentielle 30 / 60 / 10, acceptée par le bus."""

    def __init__(self, test, *, slug=None, entreprise=False):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=slug or f'ctr-co-{n}', nom=f'Contrats Co {n}')
        self.user = User.objects.create_user(
            username=f'ctr-resp-{n}', password='x', company=self.company,
            role_legacy='responsable')
        self.client = Client.objects.create(
            company=self.company, nom='EXEMPLE', prenom='Youssef',
            telephone='+212611223344', email=f'client{n}@exemple.ma',
            adresse='Villa 7, lotissement Exemple, Bouskoura', cin='BK000000',
            type_client='entreprise' if entreprise else 'particulier')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-CTR-{n}',
            client=self.client, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
            created_by=self.user, mode_installation='residentiel',
            date_acceptation=date(2026, 11, 20),
            echeancier=[
                {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 30},
                {'libelle': 'Livraison du matériel', 'type': 'materiel',
                 'pct_or_montant': 60},
                {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10},
            ])
        for desig, qte, pu in (('Onduleur hybride Deye 6 kW', '1', '14000'),
                               ('Panneau Canadian Solar 590 W', '10', '1400'),
                               ('Batterie lithium Dyness 5 kWh', '2', '9000')):
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'CTR{n}-{desig[:8]}',
                prix_vente=Decimal(pu), prix_achat=PRIX_ACHAT,
                quantite_stock=50)
            LigneDevis.objects.create(
                devis=self.devis, produit=produit, designation=desig,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu))
        self.test = test
        self.accepter()
        self.chantier = Installation.objects.get(devis=self.devis)

    def accepter(self):
        with self.test.captureOnCommitCallbacks(execute=True):
            devis_accepted.send(sender=None, devis=self.devis, user=self.user,
                                ancien_statut='envoye')

    def desaccepter(self):
        with self.test.captureOnCommitCallbacks(execute=True):
            devis_acceptation_annulee.send(
                sender=None, devis=self.devis, user=self.user,
                option_acceptee='', date_acceptation=None, motif='essai')

    def payer(self, montant, jour=date(2026, 12, 2)):
        """Une facture émise + un paiement encaissé de ``montant``."""
        n = next(_seq)
        montant = Decimal(montant)
        ht = (montant / Decimal('1.2')).quantize(Decimal('0.01'))
        facture = Facture.objects.create(
            company=self.company, reference=f'FAC-CTR-{n}', devis=self.devis,
            client=self.client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=ht, montant_tva=montant - ht,
            montant_ttc=montant)
        Paiement.objects.create(
            company=self.company, facture=facture, montant=montant,
            date_paiement=jour, mode='virement')
        return facture

    def actes(self):
        return ActeContractuel.objects.filter(
            company=self.company, chantier=self.chantier)

    def acte(self, type_acte, variante=''):
        return self.actes().get(type=type_acte, variante=variante)

    def plan(self):
        from apps.ventes.vente_facturation import plan_facturation
        return plan_facturation(self.devis)

    def solde(self):
        from apps.ventes.utils.echeancier import solde_devis
        return solde_devis(self.devis)


class CycleDeVieTests(TestCase):

    def test_acceptation_cree_cinq_brouillons_idempotent(self):
        v = Vente(self)
        self.assertEqual(v.actes().count(), 5)
        self.assertEqual(set(v.actes().values_list('statut', flat=True)),
                         {T.BROUILLON})
        self.assertEqual(
            sorted(v.actes().values_list('type', 'variante')),
            sorted((t, var) for t, var, _r in T.LIGNES_DOSSIER))
        ids = set(v.actes().values_list('pk', flat=True))
        v.accepter()  # rejeu de l'événement
        self.assertEqual(set(v.actes().values_list('pk', flat=True)), ids)
        ref = v.chantier.reference.partition('-')[2] or v.chantier.reference
        self.assertEqual(v.acte(T.CONTRAT).reference, f'CTR-{ref}')
        self.assertEqual(v.acte(T.CLOTURE).reference, f'CLO-{ref}')

    def test_desacceptation_annule_reacceptation_retablit_signe_reste(self):
        v = Vente(self)
        ActeContractuel.objects.filter(pk=v.acte(T.CONTRAT).pk).update(
            statut=T.SIGNE, signataire_nom='Youssef EXEMPLE')
        ActeContractuel.objects.filter(
            pk=v.acte(T.RECEPTION).pk).update(statut=T.EMIS)
        v.desaccepter()
        statuts = dict(v.actes().values_list('type', 'statut'))
        self.assertEqual(statuts[T.CONTRAT], T.SIGNE)
        self.assertEqual(statuts[T.CLOTURE], T.ANNULE)
        recep = v.acte(T.RECEPTION)
        self.assertEqual(recep.statut, T.ANNULE)
        self.assertEqual(recep.statut_avant_annulation, T.EMIS)
        self.assertEqual(v.actes().count(), 5)  # jamais supprimés
        v.accepter()
        self.assertEqual(v.acte(T.CONTRAT).statut, T.SIGNE)
        self.assertEqual(v.acte(T.RECEPTION).statut, T.EMIS)
        self.assertEqual(v.acte(T.CLOTURE).statut, T.BROUILLON)
        self.assertEqual(v.acte(T.LIVRAISON, T.RESTE_A_REGLER).statut,
                         T.BROUILLON)

    def test_chantier_sans_devis_contenu_valide(self):
        n = next(_seq)
        company = Company.objects.create(slug=f'ctr-sd-{n}', nom=f'SD {n}')
        chantier = Installation.objects.create(
            company=company, reference=f'CHT-2026-11-{n:04d}')
        actes = S.preparer_dossier(chantier)
        self.assertEqual(len(actes), 5)
        for acte in actes:
            with self.subTest(acte=acte.type):
                contenu = K.construire_contenu(acte)
                self.assertIsNone(contenu['prix']['total_ttc'])
                self.assertEqual(contenu.get('echeancier', []), [])
                self.assertTrue(any('devis accepté' in a for a in
                                    K.avertissements(acte, contenu)))
                self.assertIsNotNone(S.motif_refus_emission(
                    acte, K.Lecture(chantier)))


class MontantsTests(TestCase):
    """Chaque montant d'un contenu égale la vente au centime."""

    def _verifier(self, v, paye):
        plan, solde = v.plan(), v.solde()
        self.assertEqual(solde['paye'], paye)
        prix = plan['prix_convenu_ttc']
        cibles = [t['cible_cumul_ttc'] for t in plan['tranches']]
        attendus = {
            (T.CONTRAT, ''): cibles[0],
            (T.LIVRAISON, T.RESTE_A_REGLER): cibles[1],
            (T.LIVRAISON, T.TRANCHE_REGLEE): cibles[1],
            (T.RECEPTION, ''): prix,
            (T.CLOTURE, ''): prix,
        }
        for (type_acte, variante), cible in attendus.items():
            acte = v.acte(type_acte, variante)
            for langue in T.LANGUES:
                with self.subTest(acte=type_acte, variante=variante,
                                  langue=langue):
                    c = K.construire_contenu(acte, langue)
                    self.assertEqual(c['prix']['total_ttc'], f'{prix:.2f}')
                    self.assertEqual(c['prix']['total_ht'],
                                     f'{plan["prix_convenu_ht"]:.2f}')
                    self.assertEqual(c['prix']['tva'],
                                     f'{plan["prix_convenu_tva"]:.2f}')
                    self.assertEqual(
                        [t['montant_ttc'] for t in c['echeancier']],
                        [f'{t["montant_ttc"]:.2f}' for t in plan['tranches']])
                    if type_acte == T.CONTRAT:
                        continue
                    effectif = paye
                    if variante == T.TRANCHE_REGLEE:
                        effectif = max(paye, cibles[1])
                    p = c['paiement']
                    self.assertEqual(p['total_regle'], f'{effectif:.2f}')
                    self.assertEqual(p['reste_a_regler'],
                                     f'{max(Decimal(0), prix - effectif):.2f}')
                    self.assertEqual(
                        p['exigible_maintenant'],
                        f'{max(Decimal(0), cible - effectif):.2f}')
                    if 'restera_ensuite' in p:
                        self.assertEqual(p['restera_ensuite'],
                                         f'{max(Decimal(0), prix - cible):.2f}')

    def test_montants_sans_paiement(self):
        v = Vente(self)
        self._verifier(v, Decimal('0.00'))

    def test_montants_acompte_regle(self):
        v = Vente(self)
        acompte = v.plan()['tranches'][0]['montant_ttc']
        v.payer(acompte)
        self._verifier(v, acompte)
        c = K.construire_contenu(v.acte(T.LIVRAISON, T.RESTE_A_REGLER))
        self.assertEqual([t['statut'] for t in c['echeancier']],
                         ['regle', 'exigible', 'a_venir'])
        self.assertEqual(c['echeancier'][0]['regle_le'], '2026-12-02')
        c = K.construire_contenu(v.acte(T.LIVRAISON, T.TRANCHE_REGLEE))
        self.assertEqual([t['statut'] for t in c['echeancier']],
                         ['regle', 'regle', 'a_venir'])
        self.assertEqual(c['paiement']['exigible_maintenant'], '0.00')
        avert = K.avertissements(v.acte(T.LIVRAISON, T.TRANCHE_REGLEE))
        self.assertTrue(any("L'ERP n'a enregistré que" in a for a in avert))


class SansPrixAchatTests(TestCase):

    def test_aucun_prix_achat_ni_marge(self):
        v = Vente(self)
        for acte in v.actes():
            for langue in T.LANGUES:
                with self.subTest(acte=acte.type, variante=acte.variante,
                                  langue=langue):
                    c = K.construire_contenu(acte, langue)
                    brut = json.dumps(c, ensure_ascii=False)
                    self.assertNotIn('prix_achat', brut)
                    self.assertNotIn('7777', brut)
                    self.assertFalse(any('marge' in k.lower()
                                         for k in toutes_les_cles(c)))


@tag('pdf')
class SansPrixAchatPdfTests(TestCase):
    """Le texte du PDF rendu (WeasyPrint réel : palier « pdf »)."""

    def test_pdf_sans_prix_achat_ni_marge(self):
        v = Vente(self)
        texte = texte_pdf(S.pdf_de_l_acte(v.acte(T.CONTRAT)))
        self.assertNotIn('7 777', texte)
        self.assertNotIn('7777', texte)
        self.assertNotIn('prix_achat', texte)
        self.assertNotIn('marge', texte.lower())


class FormeEtLanguesTests(TestCase):

    def test_arabe_meme_schema_memes_montants(self):
        v = Vente(self)
        v.payer(v.plan()['tranches'][0]['montant_ttc'])
        for acte in v.actes():
            with self.subTest(acte=acte.type, variante=acte.variante):
                fr = K.construire_contenu(acte, 'fr')
                ar = K.construire_contenu(acte, 'ar')
                self.assertEqual(ar['langue'], 'ar')
                self.assertEqual(cles(fr), cles(ar))
                self.assertEqual(fr['prix']['total_ttc'],
                                 ar['prix']['total_ttc'])
                self.assertEqual(
                    [t['montant_ttc'] for t in fr.get('echeancier', [])],
                    [t['montant_ttc'] for t in ar.get('echeancier', [])])
                for k, val in (fr.get('paiement') or {}).items():
                    if k not in T.CLES_PAIEMENT_TEXTE and k != \
                            'exigible_en_lettres':
                        self.assertEqual(val, ar['paiement'][k], k)
                self.assertEqual(ar['prix']['total_en_lettres'], '')

    def test_options_par_defaut(self):
        v = Vente(self)
        c = K.construire_contenu(v.acte(T.CONTRAT))
        self.assertEqual(c['options'], {
            'consommateur': True, 'reserve_propriete': True,
            'raccorde_reseau': True, 'penalite_retard_pct': None,
            'delai_execution_jours': 30})
        self.assertIsNotNone(c['delais']['date_limite'])
        self.assertNotIn('retractation', c)
        self.assertNotIn('conclusion', c)
        self.assertEqual(c['echeancier'][0]['exigibilite'], 'À la signature')
        pro = Vente(self, entreprise=True)
        self.assertFalse(K.construire_contenu(
            pro.acte(T.CONTRAT))['options']['consommateur'])

    def test_garantie_installation_24_mois_par_defaut(self):
        v = Vente(self)
        c = K.construire_contenu(v.acte(T.CONTRAT))
        pose = [g for g in c['garanties'] if g['cle'] == 'installation']
        self.assertEqual(len(pose), 1)
        self.assertEqual(pose[0]['duree_mois'], 24)
        Installation.objects.filter(pk=v.chantier.pk).update(
            garantie_installation_mois=36, date_reception=date(2026, 12, 21))
        acte = v.acte(T.CLOTURE)
        acte.chantier.refresh_from_db()
        c = K.construire_contenu(acte)
        pose = [g for g in c['garanties'] if g['cle'] == 'installation'][0]
        self.assertEqual(pose['duree_mois'], 36)
        self.assertEqual(pose['fin'], '2029-12-21')


@tag('pdf')
class EmissionTests(TestCase):
    """Émission et signature réelles : rendu WeasyPrint, GED et MinIO de
    test (aucun mock de la source) — palier « pdf »."""

    def test_emission_depose_deux_documents_et_signature(self):
        from apps.ged import services as ged_services
        v = Vente(self)
        acte, avert = S.emettre(v.acte(T.CONTRAT), v.user)
        self.assertEqual(acte.statut, T.EMIS)
        self.assertEqual(avert, [])
        self.assertEqual(acte.contenu['langue'], 'fr')
        self.assertEqual(acte.contenu_ar['langue'], 'ar')
        for source in ('documents.acte_contrat_installation',
                       'documents.acte_contrat_installation_ar'):
            with self.subTest(source=source):
                self.assertIsNotNone(ged_services.find_document_by_source(
                    v.company, source_type=source, source_id=acte.pk))
        acte, avert = S.signer_sur_place(
            acte, signature_client=SIG, signataire_nom='Youssef EXEMPLE',
            user=v.user, ip='10.0.0.1', agent='essai')
        self.assertEqual(acte.statut, T.SIGNE)
        self.assertEqual(len(acte.preuve['empreinte_sha256']), 64)
        self.assertTrue(acte.preuve['empreinte_sha256_ar'])
        self.assertEqual(acte.contenu['signatures']['client']['nom'],
                         'Youssef EXEMPLE')
        self.assertEqual(acte.contenu_ar['signatures']['client']['nom'],
                         'Youssef EXEMPLE')
        texte = texte_pdf(S.pdf_de_l_acte(acte))
        self.assertIn('Youssef EXEMPLE', texte)
        with self.assertRaises(S.ErreurActe) as ctx:
            S.rouvrir(acte)
        self.assertEqual(ctx.exception.code, T.CODE_DEJA_SIGNE)

    def test_rouvrir_puis_reemettre_version_plus_un(self):
        v = Vente(self)
        acte, _ = S.emettre(v.acte(T.RECEPTION), v.user)
        acte = S.rouvrir(acte, v.user)
        self.assertEqual(acte.statut, T.BROUILLON)
        self.assertIsNone(acte.contenu)
        acte, _ = S.emettre(acte, v.user)
        self.assertEqual(acte.version, 2)
        self.assertEqual(acte.contenu['version'], 2)

    def test_variante_jumelle_ecartee(self):
        from apps.documents.contrats.selectors import dossier_du_chantier
        v = Vente(self)
        S.emettre(v.acte(T.LIVRAISON, T.TRANCHE_REGLEE), v.user)
        dossier = dossier_du_chantier(v.chantier)
        livraisons = {a['variante']: a for a in dossier['actes']
                      if a['type'] == T.LIVRAISON}
        self.assertTrue(livraisons[T.RESTE_A_REGLER]['ecarte'])
        self.assertFalse(livraisons[T.RESTE_A_REGLER]['peut_emettre'])
        self.assertFalse(livraisons[T.TRANCHE_REGLEE]['ecarte'])

    def test_quitus_refuse_tant_que_solde_non_regle(self):
        v = Vente(self)
        with self.assertRaises(S.ErreurActe) as ctx:
            S.emettre(v.acte(T.CLOTURE), v.user)
        self.assertEqual(ctx.exception.code, T.CODE_SOLDE_NON_REGLE)
        v.payer(v.plan()['prix_convenu_ttc'], jour=date(2026, 12, 22))
        acte, _ = S.emettre(v.acte(T.CLOTURE), v.user)
        self.assertEqual(acte.statut, T.EMIS)
        self.assertEqual(acte.contenu['paiement']['reste_a_regler'], '0.00')
        self.assertEqual(len(acte.contenu['paiements']), 1)
