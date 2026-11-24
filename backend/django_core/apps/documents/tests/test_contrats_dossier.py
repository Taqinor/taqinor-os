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
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import fitz
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, tag

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


class SuppressionChantierTests(TestCase):
    """S7 : brouillons et actes annulés partent avec le chantier ; un acte
    émis ou signé l'empêche."""

    def _chantier(self):
        n = next(_seq)
        company = Company.objects.create(slug=f'ctr-del-{n}', nom=f'Del {n}')
        chantier = Installation.objects.create(
            company=company, reference=f'CHT-2026-11-{n:04d}')
        S.preparer_dossier(chantier)
        return chantier

    def test_brouillons_et_annules_supprimes_avec_le_chantier(self):
        chantier = self._chantier()
        ActeContractuel.objects.filter(chantier=chantier,
                                       type=T.CLOTURE).update(statut=T.ANNULE)
        pk = chantier.pk
        chantier.delete()
        self.assertFalse(ActeContractuel.objects.filter(
            chantier_id=pk).exists())

    def test_acte_emis_ou_signe_protege_le_chantier(self):
        from django.db.models import ProtectedError
        for statut in (T.EMIS, T.SIGNE):
            with self.subTest(statut=statut):
                chantier = self._chantier()
                ActeContractuel.objects.filter(
                    chantier=chantier, type=T.CONTRAT).update(statut=statut)
                with self.assertRaises(ProtectedError):
                    chantier.delete()
                self.assertEqual(ActeContractuel.objects.filter(
                    chantier=chantier).count(), 5)


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

    def test_facture_d_acompte_emise_d_un_autre_montant(self):
        """C1 (recette sur écran réel) : une facture d'acompte émise d'un
        montant un peu différent (96 DH de moins) ne réduit jamais la
        tranche imprimée à « ce qu'il reste à facturer » : les montants des
        tranches somment au prix et leurs cumuls égalent les cibles."""
        v = Vente(self)
        cible0 = v.plan()['tranches'][0]['cible_cumul_ttc']
        acompte = cible0 - Decimal('96')
        ht = (acompte / Decimal('1.2')).quantize(Decimal('0.01'))
        Facture.objects.create(
            company=v.company, reference=f'FAC-CTR-AC-{next(_seq)}',
            devis=v.devis, client=v.client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ht=ht, montant_tva=acompte - ht,
            montant_ttc=acompte)
        plan = v.plan()
        prix = plan['prix_convenu_ttc']
        cibles = [t['cible_cumul_ttc'] for t in plan['tranches']]
        for acte in v.actes():
            for langue in T.LANGUES:
                with self.subTest(acte=acte.type, variante=acte.variante,
                                  langue=langue):
                    c = K.construire_contenu(acte, langue)
                    montants = [Decimal(t['montant_ttc'])
                                for t in c['echeancier']]
                    self.assertEqual(sum(montants), prix)
                    cumuls = list(itertools.accumulate(montants))
                    self.assertEqual(cumuls[:-1], cibles[:-1])
                    self.assertGreater(montants[0], Decimal('1000'))

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


class GarantiesDuContratTests(TestCase):

    def test_cloture_suit_le_contrat_et_la_reception_signee(self):
        """C3 par la base : la clôture prend les garanties du CONTRAT
        (brouillon, puis contenu figé une fois signé) et part du jour où la
        réception a été signée."""
        v = Vente(self)
        contrat = v.acte(T.CONTRAT)
        garanties = [dict(g, duree_mois=36) if g['cle'] == 'installation'
                     else g for g in K.construire_contenu(contrat)['garanties']]
        S.modifier(contrat, {'garanties': garanties}, v.user)
        ActeContractuel.objects.filter(pk=v.acte(T.RECEPTION).pk).update(
            statut=T.SIGNE,
            contenu={'signatures': {'client': {'signe_le': '2026-12-18'}}})

        def pose(langue='fr'):
            c = K.construire_contenu(v.acte(T.CLOTURE), langue)
            return next(g for g in c['garanties']
                        if g['cle'] == 'installation'), c
        for langue in T.LANGUES:
            ligne, c = pose(langue)
            self.assertEqual((ligne['duree_mois'], ligne['fin']),
                             (36, '2029-12-18'))
            self.assertEqual(c['reception']['date'], '2026-12-18')
        contrat = v.acte(T.CONTRAT)
        ActeContractuel.objects.filter(pk=contrat.pk).update(
            statut=T.SIGNE, contenu=K.construire_contenu(contrat),
            contenu_ar=K.construire_contenu(contrat, 'ar'), surcharges={})
        self.assertEqual(pose()[0]['duree_mois'], 36)


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
        # S3 : la version « tranche réglée » ne s'émet qu'une fois les
        # paiements qu'elle affirme enregistrés.
        v.payer(v.plan()['tranches'][1]['cible_cumul_ttc'])
        S.emettre(v.acte(T.LIVRAISON, T.TRANCHE_REGLEE), v.user)
        dossier = dossier_du_chantier(v.chantier)
        livraisons = {a['variante']: a for a in dossier['actes']
                      if a['type'] == T.LIVRAISON}
        self.assertTrue(livraisons[T.RESTE_A_REGLER]['ecarte'])
        self.assertFalse(livraisons[T.RESTE_A_REGLER]['peut_emettre'])
        self.assertFalse(livraisons[T.TRANCHE_REGLEE]['ecarte'])

    def test_pdf_servi_toujours_celui_du_contenu_fige(self):
        """S6 : un dépôt GED raté ne fait jamais servir l'ancienne version."""
        from unittest import mock

        from apps.ged import services as ged_services
        v = Vente(self)
        acte, _ = S.emettre(v.acte(T.CONTRAT), v.user)
        acte = S.rouvrir(acte, v.user)
        S.modifier(acte, {'conditions_particulieres':
                          'Accès par le portail nord.'}, v.user)
        with mock.patch.object(ged_services, 'deposit_document',
                               side_effect=RuntimeError('stockage muet')):
            acte, avert = S.emettre(v.acte(T.CONTRAT), v.user)
        self.assertEqual(acte.version, 2)
        self.assertTrue(any('rangé' in a for a in avert))
        document = S.document_ged(acte)
        self.assertFalse(S.document_a_jour(document, acte, acte.contenu))
        self.assertIn('portail nord', texte_pdf(S.pdf_de_l_acte(acte)))
        # Le dépôt a été retenté : la GED porte désormais la version 2.
        document = S.document_ged(acte)
        self.assertTrue(S.document_a_jour(document, acte, acte.contenu))
        self.assertIn('portail nord', texte_pdf(S.pdf_de_l_acte(acte)))

    def test_portail_ne_montre_ni_acte_rouvert_ni_acte_annule(self):
        """S8 : rouvrir ou annuler retire le partage portail ; ré-émettre ou
        rétablir le remet."""
        from apps.ged.models import AclGed

        v = Vente(self)

        def partages(acte):
            return {langue: AclGed.objects.filter(
                document=S.document_ged(acte, langue),
                client_id=v.client.pk).count() for langue in T.LANGUES}

        acte, _ = S.emettre(v.acte(T.CONTRAT), v.user)
        self.assertEqual(partages(acte), {'fr': 1, 'ar': 1})
        acte = S.rouvrir(acte, v.user)
        self.assertEqual(partages(acte), {'fr': 0, 'ar': 0})
        acte, _ = S.emettre(acte, v.user)
        self.assertEqual(partages(acte), {'fr': 1, 'ar': 1})
        v.desaccepter()
        self.assertEqual(v.acte(T.CONTRAT).statut, T.ANNULE)
        self.assertEqual(partages(acte), {'fr': 0, 'ar': 0})
        v.accepter()
        self.assertEqual(v.acte(T.CONTRAT).statut, T.EMIS)
        self.assertEqual(partages(acte), {'fr': 1, 'ar': 1})

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


# ── S1 : un texte personnalisé ne fige jamais une valeur ────────────────────

NB, FINE = ' ', ' '


class GabaritTests(SimpleTestCase):
    """Fonctions pures du gabarit et de l'alignement (aucune base)."""

    def aligner_un(self, jetons, saisi, ctx):
        return K.ecrire_gabarit(K.aligner([K.lire_gabarit(jetons)], [saisi],
                                          ctx)[0])

    def test_lecture_stricte_et_accolades(self):
        """Défaut attrapé : le rendu par ``str.format`` évaluait tout texte
        stocké ; les accolades tapées doivent survivre au rendu."""
        ctx = {'societe': 'TAQINOR'}
        self.assertEqual(K.rendre_gabarit('{societe} {{x}} {inconnu} {0}',
                                          ctx), 'TAQINOR {x} {inconnu} {0}')
        self.assertEqual(K.rendre_gabarit('{penalite_retard}', ctx),
                         'à préciser')
        texte = 'clause {spéciale} {societe} {{ }}'
        self.assertEqual(K.rendre_gabarit(
            K.ecrire_gabarit([('t', texte)]), ctx), texte)

    def test_reperes_lus_dans_les_textes(self):
        noms = K.noms_reperes()
        for nom in ('liste_tranches', 'ecart_regle', 'contrat_du',
                    'penalite_retard', 'total_regle', 'reste_a_regler'):
            self.assertIn(nom, noms)

    def test_textes_par_defaut_en_jetons_rendus_a_l_identique(self):
        """Les jetons des textes par défaut, rendus avec le contexte, sont
        mot pour mot les textes de ``textes`` / ``textes_ar`` (toutes les
        options)."""
        from apps.documents.contrats import textes, textes_ar
        ctx = dict(textes_ar.FORMES_CTX)
        for module in (textes, textes_ar):
            for type_acte, variante in CINQ_ACTES:
                for opts in ({}, {'consommateur': False,
                                  'reserve_propriete': False,
                                  'raccorde_reseau': False,
                                  'penalite_retard_pct': '2'}):
                    with self.subTest(module=module.__name__,
                                      acte=type_acte, opts=opts):
                        attendu = module.articles_par_defaut(
                            type_acte, variante, ctx, opts)
                        jetons = K.articles_en_jetons(
                            module, type_acte, variante, opts, ctx)
                        self.assertEqual(
                            [{'cle': a['cle'],
                              'titre': K.rendre_jetons(a['titre'], ctx),
                              'paragraphes': [K.rendre_jetons(p, ctx)
                                              for p in a['paragraphes']]}
                             for a in jetons], attendu)

    def test_aligner_valeurs_intactes_modifiees_vides(self):
        """L'alignement : valeur intacte → repère ; valeur modifiée en son
        milieu → texte ; repère vide ancré à son voisin."""
        ctx = {'a': f'29{FINE}550,00{NB}DH', 'b': f'29{FINE}550,00{NB}DH',
               'vide': ''}
        g = '{a} puis {b}.{vide}'
        self.assertEqual(self.aligner_un(g, f'29{FINE}550,00{NB}DH puis '
                                         f'29{FINE}550,00{NB}DH. Merci.', ctx),
                         '{a} puis {b}.{vide} Merci.')
        # Valeur modifiée en son milieu : reprise en texte.
        self.assertEqual(self.aligner_un(g, f'29{FINE}551,00{NB}DH puis '
                                         f'29{FINE}550,00{NB}DH.', ctx),
                         f'29{FINE}551,00{NB}DH puis {{b}}.{{vide}}')
        # Phrase supprimée avec sa valeur.
        self.assertEqual(self.aligner_un('Total {a}. Fin.', 'Fin.', ctx),
                         'Fin.')

    def test_espaces_normales_du_navigateur(self):
        """Défaut attrapé par la recette sur écran réel : le navigateur
        renvoie des espaces normales là où les montants portent des espaces
        insécables et fines ; chaque montant non touché paraissait modifié
        et devenait du texte figé."""
        ctx = {'a': f'29{FINE}550,00{NB}DH', 'b': f'68{FINE}950,00{NB}DH'}
        g = f'Payé{NB}: {{a}}, reste {{b}}.'
        saisi = 'Payé : 29 550,00 DH, reste 68 950,00 DH. Merci.'
        self.assertEqual(self.aligner_un(g, saisi, ctx),
                         f'Payé{NB}: {{a}}, reste {{b}}. Merci.')

    def test_acces_indexe_stocke_jamais_une_erreur(self):
        """m5 : un texte stocké « {societe[x]} » levait TypeError dans
        ``rendre_gabarit`` (erreur 500 à chaque lecture du brouillon)."""
        ctx = {'societe': 'TAQINOR', 'client': 'M. EXEMPLE'}
        for texte in ('{societe[x]}', '{societe[0][1]}', '{client.nom}',
                      '{0}', 'accolade { seule'):
            with self.subTest(texte=texte):
                self.assertIsInstance(K.rendre_gabarit(texte, ctx), str)

    def test_montants_du_texte(self):
        self.assertEqual(
            K.montants_du_texte(f'29{FINE}550,00{NB}DH, 1 234 DH, 12,5 dirhams'
                                f' et 59{FINE}100,00{NB}درهم ; 10 % ; 2026'),
            [Decimal('29550.00'), Decimal('1234.00'), Decimal('12.50'),
             Decimal('59100.00')])


def texte_article(contenu, cle):
    a = next(a for a in contenu['articles'] if a['cle'] == cle)
    return '\n'.join([a['titre']] + a['paragraphes'])


def corriger(articles, cle, ajout=' Texte ajouté par le commercial.'):
    """La liste servie, avec l'article ``cle`` corrigé (un mot ajouté au
    premier paragraphe)."""
    sortie = json.loads(json.dumps(articles))
    for a in sortie:
        if a['cle'] == cle:
            a['paragraphes'][0] += ajout
    return sortie


class ArticlesGabaritsTests(TestCase):
    """Un article corrigé suit la vente, les options et les dates."""

    def test_aller_retour_identique_dans_chaque_acte_et_langue(self):
        v = Vente(self)
        v.payer(v.plan()['tranches'][0]['montant_ttc'])
        for acte in v.actes():
            for langue in T.LANGUES:
                with self.subTest(acte=acte.type, variante=acte.variante,
                                  langue=langue):
                    acte.refresh_from_db()
                    avant = K.construire_contenu(acte, langue)['articles']
                    envoye = corriger(avant, avant[-1]['cle'])
                    S.modifier(acte, {'articles': envoye}, v.user, langue)
                    acte.refresh_from_db()
                    self.assertEqual(
                        K.construire_contenu(acte, langue)['articles'], envoye)

    def test_paiement_corrige_suit_l_echeancier_de_la_vente(self):
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        envoye = corriger(K.construire_contenu(acte)['articles'], 'paiement')
        S.modifier(acte, {'articles': envoye}, v.user)
        acte.refresh_from_db()
        stocke = next(a for a in acte.surcharges['articles']
                      if a['cle'] == 'paiement')
        # Le paragraphe de la liste, non touché, reste un renvoi vivant.
        self.assertIn({'defaut': 1}, stocke['paragraphes'])
        Devis.objects.filter(pk=v.devis.pk).update(echeancier=[
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 40},
            {'libelle': 'Livraison du matériel', 'type': 'materiel',
             'pct_or_montant': 50},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 10}])
        acte = v.acte(T.CONTRAT)
        contenu, ctx = K._construire(acte, avec_ctx=True)
        apres = texte_article(contenu, 'paiement')
        self.assertIn('Texte ajouté par le commercial.', apres)
        self.assertIn(ctx['liste_tranches'], apres)
        self.assertIn(f'40{NB}%', ctx['liste_tranches'])

    def test_penalite_reglee_puis_retiree_apres_correction(self):
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        S.modifier(acte, {'options': {'penalite_retard_pct': '10'}}, v.user)
        acte.refresh_from_db()
        self.assertIn('indemnité', texte_article(
            K.construire_contenu(acte), 'retard'))
        envoye = corriger(K.construire_contenu(acte)['articles'], 'objet')
        S.modifier(acte, {'articles': envoye}, v.user)
        acte.refresh_from_db()
        S.modifier(acte, {'options': {'penalite_retard_pct': None}}, v.user)
        acte.refresh_from_db()
        contenu = K.construire_contenu(acte)
        self.assertNotIn('indemnité', texte_article(contenu, 'retard'))
        self.assertIn('Texte ajouté par le commercial.',
                      texte_article(contenu, 'objet'))

    def test_reserve_propriete_decochee_puis_recochee(self):
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        ordre = [a['cle'] for a in K.construire_contenu(acte)['articles']]
        S.modifier(acte, {'options': {'reserve_propriete': False}}, v.user)
        acte.refresh_from_db()
        sans = K.construire_contenu(acte)['articles']
        self.assertNotIn('propriete', [a['cle'] for a in sans])
        S.modifier(acte, {'articles': corriger(sans, 'objet')}, v.user)
        acte.refresh_from_db()
        S.modifier(acte, {'options': {'reserve_propriete': True}}, v.user)
        acte.refresh_from_db()
        contenu = K.construire_contenu(acte)
        self.assertEqual([a['cle'] for a in contenu['articles']], ordre)
        self.assertIn('Texte ajouté par le commercial.',
                      texte_article(contenu, 'objet'))

    def test_options_et_articles_dans_le_meme_corps(self):
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        sans = [a for a in K.construire_contenu(acte)['articles']
                if a['cle'] != 'propriete']
        S.modifier(acte, {'options': {'reserve_propriete': False},
                          'articles': corriger(sans, 'objet')}, v.user)
        acte.refresh_from_db()
        self.assertFalse(any(e.get('retire')
                             for e in acte.surcharges['articles']))
        S.modifier(acte, {'options': {'reserve_propriete': True}}, v.user)
        acte.refresh_from_db()
        self.assertIn('propriete', [a['cle'] for a in K.construire_contenu(
            acte)['articles']])

    def test_service_options_et_liste_affichee_meme_corps(self):
        """B1 par le service réel : le corps de l'écran (options + liste
        ENTIÈRE affichée, un article corrigé) ne fige plus l'article
        « Retard » avec sa pénalité retirée."""
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        S.modifier(acte, {'options': {'penalite_retard_pct': '10'}}, v.user)
        acte.refresh_from_db()
        affiches = K.construire_contenu(acte)['articles']
        S.modifier(acte, {'options': {'reserve_propriete': True,
                                      'delai_execution_jours': 30,
                                      'penalite_retard_pct': None},
                          'articles': corriger(affiches, 'objet')}, v.user)
        acte.refresh_from_db()
        contenu = K.construire_contenu(acte)
        self.assertNotIn('indemnité', texte_article(contenu, 'retard'))
        self.assertIn('Texte ajouté par le commercial.',
                      texte_article(contenu, 'objet'))
        self.assertEqual([e for e in acte.surcharges['articles']
                          if len(e) > 1][0]['cle'], 'objet')

    def test_article_supprime_reste_supprime(self):
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        avant = K.construire_contenu(acte)['articles']
        envoye = [a for a in corriger(avant, 'objet')
                  if a['cle'] != 'estimations']
        S.modifier(acte, {'articles': envoye}, v.user)
        acte.refresh_from_db()
        S.modifier(acte, {'options': {'penalite_retard_pct': '5'}}, v.user)
        acte.refresh_from_db()
        apres = K.construire_contenu(acte)['articles']
        self.assertNotIn('estimations', [a['cle'] for a in apres])
        self.assertEqual(len(apres), len(avant) - 1)

    def test_arabe_corrige_suit_la_vente(self):
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        envoye = corriger(K.construire_contenu(acte, 'ar')['articles'],
                          'paiement', ' نص أضافه المستشار.')
        S.modifier(acte, {'articles': envoye}, v.user, 'ar')
        acte.refresh_from_db()
        self.assertEqual(acte.surcharges, {})
        self.assertEqual(K.construire_contenu(acte, 'ar')['articles'], envoye)
        Devis.objects.filter(pk=v.devis.pk).update(echeancier=[
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 50},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 50}])
        contenu, ctx = K._construire(v.acte(T.CONTRAT), 'ar', avec_ctx=True)
        apres = texte_article(contenu, 'paiement')
        self.assertIn('نص أضافه المستشار.', apres)
        self.assertIn(ctx['liste_tranches'], apres)
        self.assertNotIn(f'60{NB}%', apres)

    def test_quitus_corrige_en_gabarit(self):
        v = Vente(self)
        acte = v.acte(T.CLOTURE)
        quitus = K.construire_contenu(acte)['quitus']
        envoye = [quitus[0] + ' Merci de votre confiance.'] + quitus[1:]
        S.modifier(acte, {'quitus': envoye}, v.user)
        acte.refresh_from_db()
        self.assertEqual(acte.surcharges['quitus'][0]['defaut'], 0)
        self.assertIn('{client}', acte.surcharges['quitus'][0]['texte'])
        self.assertEqual(acte.surcharges['quitus'][1], {'defaut': 1})
        self.assertEqual(K.construire_contenu(acte)['quitus'], envoye)
        S.modifier(acte, {'quitus': quitus}, v.user)  # retour au défaut
        acte.refresh_from_db()
        self.assertNotIn('quitus', acte.surcharges)

    def test_montant_ecrit_en_clair_refuse_a_l_emission(self):
        v = Vente(self)
        acte = v.acte(T.CONTRAT)
        envoye = corriger(K.construire_contenu(acte)['articles'], 'objet',
                          f' Frais de dossier : 12{FINE}345,67{NB}DH.')
        S.modifier(acte, {'articles': envoye}, v.user)
        acte.refresh_from_db()
        self.assertEqual(len(K.montants_figes(acte)), 1)
        self.assertTrue(any('Objet du contrat' in a
                            for a in K.avertissements(acte)))
        with self.assertRaises(S.ErreurActe) as ctx:
            S.emettre(acte, v.user)
        self.assertEqual(ctx.exception.code, T.CODE_MONTANT_FIGE)
        self.assertIn('« Objet du contrat »', ctx.exception.detail)
        self.assertEqual(v.acte(T.CONTRAT).statut, T.BROUILLON)


# ── S2 : le quitus dit ce qui a été réellement réglé ────────────────────────

class ReglementsPursTests(SimpleTestCase):

    def test_lignes_somment_au_paye_ecart_nomme(self):
        rows = [{'date': '2026-12-02', 'libelle': 'Acompte', 'mode': 'Virement',
                 'montant': '29550.00', '_key': 'acompte'}]
        lignes = K.reglements(rows, Decimal('29650.00'))
        self.assertEqual(len(lignes), 2)
        self.assertEqual(lignes[1]['libelle'], 'Escompte ou avance ventilée')
        self.assertEqual(sum(Decimal(x['montant']) for x in lignes),
                         Decimal('29650.00'))
        lignes = K.reglements(rows, Decimal('29000.00'))
        self.assertEqual(sum(Decimal(x['montant']) for x in lignes),
                         Decimal('29000.00'))
        self.assertEqual(len(K.reglements(rows, Decimal('29550.00'))), 1)

    def test_phrase_de_l_ecart(self):
        self.assertEqual(K.ecart_regle(Decimal('100'), Decimal('100'),
                                       Decimal('0'), 'fr'), '')
        fr = K.ecart_regle(Decimal('1000'), Decimal('500'), Decimal('500'),
                           'fr')
        self.assertIn('500,00', fr)
        self.assertIn('avoir', fr)
        self.assertIn('إشعار دائن', K.ecart_regle(
            Decimal('1000'), Decimal('500'), Decimal('500'), 'ar'))
        self.assertIn('retenue à la source', K.ecart_regle(
            Decimal('1000'), Decimal('500'), Decimal('0'), 'fr'))


class QuitusRegleTests(TestCase):

    def test_tableau_et_total_d_une_meme_source_avec_escompte(self):
        v = Vente(self)
        prix = v.plan()['prix_convenu_ttc']
        facture = v.payer(prix, jour=date(2026, 12, 22))
        Paiement.objects.filter(facture=facture).update(
            montant=prix - Decimal('100'), escompte_montant=Decimal('100'))
        acte = v.acte(T.CLOTURE)
        for langue in T.LANGUES:
            with self.subTest(langue=langue):
                contenu, ctx = K._construire(acte, langue, avec_ctx=True)
                total = Decimal(contenu['paiement']['total_regle'])
                self.assertEqual(total, prix)
                self.assertEqual(
                    sum(Decimal(p['montant']) for p in contenu['paiements']),
                    total)
                self.assertEqual(len(contenu['paiements']), 2)
                self.assertEqual(set(contenu['paiements'][1]),
                                 {'date', 'libelle', 'mode', 'montant'})
                self.assertEqual(ctx['total_regle'],
                                 K.C.montant(total, langue=langue))
                self.assertEqual(ctx['ecart_regle'], '')
        self.assertIsNone(S.motif_refus_emission(acte, K.Lecture(v.chantier)))


# ── S5 : les garanties sont les mêmes dans les deux langues ─────────────────

class GarantiesArabesPursTests(SimpleTestCase):

    def test_lignes_et_durees_du_francais_textes_arabes(self):
        def ligne(cle, designation, mois):
            return {'cle': cle, 'designation': designation, 'duree_mois': mois,
                    'duree_libelle': '', 'garant': 'g', 'detail': 'd',
                    'fin': None}
        defauts_ar = [ligne('onduleur', 'العاكس', 120),
                      ligne('installation', 'التركيب', 24)]
        fr = [ligne('installation', 'Installation', 36),
              ligne('perso_1', 'Toiture', 120)]
        trad = [{'cle': 'perso_1', 'designation': 'السقف'},
                {'cle': 'inconnue', 'designation': 'زائد'}]
        sortie = K._garanties_ar(defauts_ar, fr, trad)
        self.assertEqual([(g['cle'], g['designation'], g['duree_mois'])
                          for g in sortie],
                         [('installation', 'التركيب', 36),
                          ('perso_1', 'السقف', 120)])
        self.assertEqual(K._garanties_ar(defauts_ar, None, trad), defauts_ar)


# ── S12 : repères du contexte ───────────────────────────────────────────────

class ReperesContexteTests(TestCase):

    def test_contrat_du_adresse_reste_et_vrai_nom_en_arabe(self):
        from apps.documents.contrats import textes_ar
        from apps.parametres.models import CompanyProfile
        v = Vente(self)
        profil = CompanyProfile.get(company=v.company)
        profil.nom = 'Solaire Réelle SARL'
        profil.adresse = '3, rue Réelle, Casablanca'
        profil.save()
        acompte = v.plan()['tranches'][0]['montant_ttc']
        v.payer(acompte)
        prix = v.plan()['prix_convenu_ttc']
        recep = v.acte(T.RECEPTION)
        for langue in T.LANGUES:
            with self.subTest(langue=langue):
                ctx = K.contexte_de(recep, langue)
                self.assertEqual(ctx['contrat_du'], '')
                self.assertEqual(ctx['adresse_societe'],
                                 '3, rue Réelle, Casablanca')
                self.assertEqual(ctx['reste_a_regler'], K.C.montant(
                    prix - acompte, langue=langue))
                self.assertEqual(ctx['societe'], 'Solaire Réelle SARL')
                self.assertNotEqual(ctx['societe'],
                                    textes_ar.FORMES_CTX['societe'])
        ActeContractuel.objects.filter(pk=v.acte(T.CONTRAT).pk).update(
            statut=T.EMIS, contenu={'date_document': '2026-11-24'})
        self.assertEqual(K.contexte_de(v.acte(T.RECEPTION))['contrat_du'],
                         ' du 24 novembre 2026')
        # Même forme que l'exemple des textes (même date : 24 novembre 2026).
        self.assertEqual(K.contexte_de(v.acte(T.RECEPTION), 'ar')[
            'contrat_du'], textes_ar.FORMES_CTX['contrat_du'])


# ── S13 : arabe de contenu.py ───────────────────────────────────────────────

#: Formes écartées : « الرصيد » pour le solde, « تسلّم » sans damma.
RASEED, TASALLUM_SANS_DAMMA = 'الرصيد', \
    'تسلّم'


class ArabeTranchesPursTests(SimpleTestCase):

    def test_chaque_cle_de_tranche_a_ses_mots_dans_les_deux_langues(self):
        from apps.ventes.utils.echeancier import TRANCHE_LABELS
        for cle in TRANCHE_LABELS:
            with self.subTest(cle=cle):
                self.assertIn(cle, K._LIBELLES_AR)
                for table in (K._EXIGIBILITE, K._MOMENT):
                    self.assertIn(cle, table['fr'])
                    self.assertIn(cle, table['ar'])
        self.assertEqual(K._LIBELLES_AR['solde'], 'باقي الثمن')
        brut = json.dumps([K._EXIGIBILITE, K._MOMENT, K._LIBELLES_AR],
                          ensure_ascii=False)
        self.assertNotIn(RASEED, brut)
        self.assertNotIn(TASALLUM_SANS_DAMMA, brut)


class ArabeContenuTests(TestCase):

    def test_solde_et_reception_ecrits_d_une_seule_facon(self):
        v = Vente(self)
        for acte in v.actes():
            with self.subTest(acte=acte.type, variante=acte.variante):
                c = K.construire_contenu(acte, 'ar')
                brut = json.dumps({k: c.get(k) for k in (
                    'echeancier', 'paiement')}, ensure_ascii=False)
                self.assertNotIn(RASEED, brut)
                self.assertNotIn(TASALLUM_SANS_DAMMA, brut)
        c = K.construire_contenu(v.acte(T.RECEPTION), 'ar')
        self.assertIn('باقي الثمن', c['paiement']['engagement'])
        self.assertEqual(c['echeancier'][2]['libelle'], 'باقي الثمن')


# ── S4 : la livraison sans tranche « livraison » ────────────────────────────

def _tr(*cles_):
    return [{'key': c, 'cible': Decimal(i + 1)} for i, c in enumerate(cles_)]


class IndexLivraisonTests(SimpleTestCase):

    def test_derniere_tranche_commande_ou_livraison_sinon_la_premiere(self):
        self.assertEqual(K.index_livraison(_tr('acompte', 'materiel', 'solde')),
                         1)
        self.assertEqual(K.index_livraison(_tr(
            'commande', 'livraison_materiel', 'mise_en_service',
            'reception_definitive')), 1)
        self.assertEqual(K.index_livraison(_tr(
            'commande', 'mise_en_service', 'reception_definitive')), 0)
        # 50 / 50 : ni commande ni livraison → la seule première tranche,
        # jamais « l'avant-dernière ».
        self.assertEqual(K.index_livraison(_tr('acompte', 'solde')), 0)
        self.assertTrue(K.livraison_sans_etape(_tr('acompte', 'solde')))
        self.assertEqual(K.index_livraison(_tr(
            'acompte', 'acompte', 'acompte', 'solde')), 0)
        self.assertFalse(K.livraison_sans_etape(_tr('acompte', 'materiel')))
        self.assertFalse(K.livraison_sans_etape([]))


class LivraisonSansEtapeTests(TestCase):

    def test_cinquante_cinquante(self):
        v = Vente(self)
        Devis.objects.filter(pk=v.devis.pk).update(echeancier=[
            {'libelle': 'Acompte', 'type': 'acompte', 'pct_or_montant': 50},
            {'libelle': 'Solde', 'type': 'solde', 'pct_or_montant': 50}])
        acte = v.acte(T.LIVRAISON, T.RESTE_A_REGLER)
        premiere = v.plan()['tranches'][0]['cible_cumul_ttc']
        c = K.construire_contenu(acte)
        self.assertEqual(c['paiement']['exigible_maintenant'],
                         f'{premiere:.2f}')
        self.assertEqual([t['statut'] for t in c['echeancier']],
                         ['exigible', 'a_venir'])
        self.assertTrue(any('ne correspond à la commande' in a
                            for a in K.avertissements(acte)))


# ── S3 : la version « tranche réglée » ne s'émet pas sur une supposition ────

class TrancheRegleeTests(TestCase):

    def _drapeaux(self, v, variante):
        from apps.documents.contrats.selectors import dossier_du_chantier
        return next(a for a in dossier_du_chantier(v.chantier)['actes']
                    if a['type'] == T.LIVRAISON and a['variante'] == variante)

    def test_refusee_tant_que_les_paiements_ne_couvrent_pas_la_cible(self):
        v = Vente(self)
        acompte = v.plan()['tranches'][0]['montant_ttc']
        cible = v.plan()['tranches'][1]['cible_cumul_ttc']
        v.payer(acompte)
        acte = v.acte(T.LIVRAISON, T.TRANCHE_REGLEE)
        # Le brouillon reste prêt et se prévisualise.
        c = K.construire_contenu(acte)
        self.assertEqual(c['paiement']['total_regle'], f'{cible:.2f}')
        self.assertFalse(self._drapeaux(v, T.TRANCHE_REGLEE)['peut_emettre'])
        self.assertTrue(self._drapeaux(v, T.RESTE_A_REGLER)['peut_emettre'])
        self.assertTrue(any('ne pourra être émise' in a
                            for a in K.avertissements(acte)))
        with self.assertRaises(S.ErreurActe) as ctx:
            S.emettre(acte, v.user)
        self.assertEqual(ctx.exception.code, T.CODE_PAIEMENT_NON_ENREGISTRE)
        self.assertEqual(ctx.exception.statut_http, 409)
        self.assertIn('reste à régler', ctx.exception.detail)
        self.assertEqual(v.acte(T.LIVRAISON, T.TRANCHE_REGLEE).statut,
                         T.BROUILLON)
        v.payer(cible - acompte)
        self.assertTrue(self._drapeaux(v, T.TRANCHE_REGLEE)['peut_emettre'])
        self.assertIsNone(S.motif_refus_emission(
            v.acte(T.LIVRAISON, T.TRANCHE_REGLEE), K.Lecture(v.chantier)))
        self.assertFalse(any('ne pourra être émise' in a for a in
                             K.avertissements(v.acte(T.LIVRAISON,
                                                     T.TRANCHE_REGLEE))))

    def test_emission_verrouille_les_deux_variantes(self):
        """S9 : toutes les lignes de livraison du chantier sont verrouillées
        avant le contrôle de la jumelle."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        v = Vente(self)
        with CaptureQueriesContext(connection) as requetes:
            with self.assertRaises(S.ErreurActe):
                S.emettre(v.acte(T.LIVRAISON, T.TRANCHE_REGLEE), v.user)
        verrous = [q['sql'] for q in requetes.captured_queries
                   if 'FOR UPDATE' in q['sql'] and 'pv_livraison' in q['sql']]
        self.assertTrue(verrous, [q['sql'] for q in requetes.captured_queries
                                  if 'FOR UPDATE' in q['sql']])


# ── Harnais pur : le contenu d'un acte sans base de données ─────────────────
# Les lectures vivantes (société, vente, modèles) sont servies par
# ``LecturePure`` ; l'acte et le chantier sont de simples objets. Tout ce qui
# suit tourne dans un conteneur sans base (``SimpleTestCase``).

def vente_pure(prix='100000', pcts=(30, 60, 10),
               cles_=('acompte', 'materiel', 'solde'), paiements=(),
               avoirs='0'):
    """Une vente comme ``Lecture.vente`` la rend (montants Decimal)."""
    from apps.ventes.utils.echeancier import TRANCHE_LABELS
    prix, cumul, tranches = Decimal(prix), Decimal(0), []
    for i, (pct, key) in enumerate(zip(pcts, cles_)):
        montant = (prix * Decimal(pct) / 100).quantize(Decimal('0.01'))
        if i == len(pcts) - 1:
            montant = prix - cumul
        cumul += montant
        tranches.append({'cle': f't{i + 1}', 'key': key,
                         'libelle': TRANCHE_LABELS[key], 'montant': montant,
                         'cible': cumul, 'pourcentage': Decimal(pct)})
    lignes = [{'date': jour, 'libelle': 'Paiement', 'mode': 'Virement',
               'montant': f'{Decimal(m):.2f}', '_key': ''}
              for jour, m in paiements]
    paye = sum((Decimal(m) for _j, m in paiements), Decimal('0.00'))
    avoirs = Decimal(avoirs)
    ht = (prix / Decimal('1.2')).quantize(Decimal('0.01'))
    return {'prix_ttc': prix, 'prix_ht': ht, 'tva': prix - ht, 'paye': paye,
            'reste': max(Decimal('0.00'), prix - paye - avoirs),
            'avoirs': avoirs, 'tranches': tranches, 'paiements': lignes,
            'reglements': K.reglements(lignes, paye)}


class LecturePure(K.Lecture):
    """Les lectures vivantes d'un chantier, servies sans base."""

    def __init__(self, chantier, vente, *, modeles=None, date_contrat=None,
                 garanties=None, societe='Solaire Exemple SARL',
                 garanties_contrat=None, reception_signee=None):
        super().__init__(chantier)
        self._societe = societe
        self._garanties_contrat = garanties_contrat or {}
        self._reception_signee = reception_signee
        self._vente = vente
        self._modeles = modeles or {}
        self._date_contrat = date_contrat
        self._garanties = garanties if garanties is not None else [
            {'designation': 'Onduleur', 'duree': '10 ans', 'detail': ''},
            {'designation': 'Panneaux', 'duree': '12 ans', 'detail': ''}]

    def profil(self):
        from types import SimpleNamespace
        return SimpleNamespace(
            nom=self._societe, adresse='12, rue des Exemples, '
            'Casablanca', telephone='+212522000000',
            email='contact@exemple.ma', instructions_paiement='', rib='',
            banque='')

    def logo_uri(self):
        return ''

    def modele(self, type_acte):
        return self._modeles.get(type_acte)

    def date_du_contrat(self):
        return self._date_contrat

    def composants(self):
        return [{'designation': 'Panneau Canadian Solar 590 W',
                 'marque': 'Canadian Solar', 'quantite': 10},
                {'designation': 'Onduleur hybride Deye 6 kW',
                 'marque': 'Deye', 'quantite': 1}]

    def garanties_vente(self, langue):
        return self._garanties

    def garanties_du_contrat(self, langue):
        return self._garanties_contrat.get(langue)

    def date_reception_signee(self):
        return self._reception_signee

    def vente(self):
        return self._vente


def chantier_pur(**champs):
    from types import SimpleNamespace
    client = SimpleNamespace(
        nom='EXEMPLE', prenom='Youssef', email='client@exemple.ma',
        telephone='+212611223344', adresse='Villa 7, Bouskoura',
        type_client='particulier', cin='BK000000', ice='', rc='',
        if_fiscal='', contact_nom='', adresse_siege='')
    devis = SimpleNamespace(reference='DEV-202611-0042',
                            date_acceptation=date(2026, 11, 20),
                            mode_installation='residentiel')
    valeurs = dict(
        pk=7, company_id=1, reference='CHT-2026-11-0007', client=client,
        client_id=3, devis=devis, type_installation='residentiel',
        site_adresse='Villa 7, Bouskoura', site_ville='Bouskoura',
        puissance_installee_kwc=Decimal('5.90'),
        date_pose_prevue=date(2026, 12, 10), duree_pose_jours=2,
        date_mise_en_service=None, date_reception=date(2026, 12, 21),
        garantie_installation_mois=None, garantie_installation_perimetre='',
        annule=False)
    valeurs.update(champs)
    return SimpleNamespace(**valeurs)


def acte_pur(type_acte, variante='', *, chantier=None, surcharges=None,
             surcharges_ar=None):
    from types import SimpleNamespace
    return SimpleNamespace(type=type_acte, variante=variante, version=1,
                           statut=T.BROUILLON,
                           chantier=chantier or chantier_pur(),
                           surcharges=surcharges or {},
                           surcharges_ar=surcharges_ar or {})


#: Les cinq actes du dossier : (type, variante).
CINQ_ACTES = tuple((t, var) for t, var, _r in T.LIGNES_DOSSIER)


# ── Avoirs : ce qui est dû ne dépasse jamais ce que la vente doit ───────────

class AvoirsPursTests(SimpleTestCase):

    def test_avoir_borne_le_du_dans_chaque_acte_et_langue(self):
        """Défaut attrapé : ``situation`` ignorait les avoirs — la réception
        disait « devoir 70 000,00 DH » quand la vente n'en devait plus que
        50 000 (30 000 payés, avoir de 20 000)."""
        vente = vente_pure(paiements=[('2026-12-02', '30000')],
                           avoirs='20000')
        self.assertEqual(vente['reste'], Decimal('50000.00'))
        for type_acte, variante in CINQ_ACTES:
            acte = acte_pur(type_acte, variante)
            for langue in T.LANGUES:
                with self.subTest(acte=type_acte, variante=variante,
                                  langue=langue):
                    c = K.construire_contenu(acte, langue,
                                             LecturePure(acte.chantier, vente))
                    p = c['paiement']
                    for cle in ('exigible_maintenant', 'reste_a_regler'):
                        if p.get(cle) is not None:
                            self.assertLessEqual(Decimal(p[cle]),
                                                 vente['reste'], cle)
                    if 'restera_ensuite' in p:
                        self.assertEqual(
                            Decimal(p['exigible_maintenant'])
                            + Decimal(p['restera_ensuite']),
                            Decimal(p['reste_a_regler']))
        recep = acte_pur(T.RECEPTION)
        for langue in T.LANGUES:
            c = K.construire_contenu(recep, langue,
                                     LecturePure(recep.chantier, vente))
            self.assertEqual(c['paiement']['exigible_maintenant'], '50000.00')
            self.assertEqual(c['paiement']['reste_a_regler'], '50000.00')
            solde = next(a for a in c['articles'] if a['cle'] == 'solde')
            texte = '\n'.join(solde['paragraphes'])
            self.assertIn(K.C.montant('50000', langue=langue), texte)
            self.assertNotIn(K.C.montant('70000', langue=langue), texte)

    def test_livraison_reste_a_regler_et_tranche_reglee(self):
        """Défaut attrapé : la livraison « reste à régler » réclamait la
        tranche entière (60 000) malgré un avoir qui ne laisse que 50 000
        dus ; la variante « tranche réglée » annonçait un reste qui ignorait
        l'avoir."""
        vente = vente_pure(paiements=[('2026-12-02', '30000')],
                           avoirs='20000')
        acte = acte_pur(T.LIVRAISON, T.RESTE_A_REGLER)
        p = K.construire_contenu(acte, 'fr', LecturePure(
            acte.chantier, vente))['paiement']
        self.assertEqual((p['exigible_maintenant'], p['restera_ensuite'],
                          p['reste_a_regler']),
                         ('50000.00', '0.00', '50000.00'))
        acte = acte_pur(T.LIVRAISON, T.TRANCHE_REGLEE)
        p = K.construire_contenu(acte, 'fr', LecturePure(
            acte.chantier, vente))['paiement']
        self.assertEqual(p['reste_a_regler'], '0.00')
        # Sans avoir, rien ne change (30 / 60 / 10, acompte payé).
        sans = vente_pure(paiements=[('2026-12-02', '30000')])
        acte = acte_pur(T.LIVRAISON, T.RESTE_A_REGLER)
        p = K.construire_contenu(acte, 'fr', LecturePure(
            acte.chantier, sans))['paiement']
        self.assertEqual((p['exigible_maintenant'], p['restera_ensuite'],
                          p['reste_a_regler']),
                         ('60000.00', '10000.00', '70000.00'))


# ── L'écran réel : corps envoyés comme l'éditeur les envoie ─────────────────
# frontend/src/pages/installations/contrats/sections.js : un enregistrement
# qui touche une option ET un article envoie ``options`` et la liste ENTIÈRE
# des articles telle que l'écran l'affichait (anciennes options, ancien
# contexte), paragraphes coupés par ``texteVersParagraphes``.

def texte_vers_paragraphes(texte):
    """outils.js ``texteVersParagraphes``."""
    sortie = []
    for p in re.split(r'\n[ \t]*\n', texte):
        p = re.sub(r'^\s*\n', '', re.sub(r'\s+$', '', p), count=1)
        if p.strip():
            sortie.append(p)
    return sortie


def articles_ecran(contenu, corrections=None):
    """``SECTIONS.articles.lire`` puis ``ecrire`` ; ``corrections`` :
    ``{cle: f(titre, texte) -> (titre, texte)}`` (ce que tape l'utilisateur
    dans la zone de l'article)."""
    sortie = []
    for a in contenu['articles']:
        titre, texte = a['titre'], '\n\n'.join(a['paragraphes'])
        if corrections and a['cle'] in corrections:
            titre, texte = corrections[a['cle']](titre, texte)
        sortie.append({'cle': a['cle'], 'titre': titre,
                       'paragraphes': texte_vers_paragraphes(texte)})
    return sortie


def options_ecran(contenu, **changements):
    """``SECTIONS.options.lire`` puis ``ecrire``."""
    o = contenu['options']
    d = {'reserve_propriete': bool(o.get('reserve_propriete')),
         'penalite_retard_pct': o.get('penalite_retard_pct')}
    if contenu['type'] == T.CONTRAT and 'delai_execution_jours' in o:
        d['delai_execution_jours'] = o['delai_execution_jours']
    d.update(changements)
    return d


def ajouter(fin):
    return lambda titre, texte: (titre, texte + fin)


def remplacer(avant, apres):
    return lambda titre, texte: (titre, texte.replace(avant, apres, 1))


def article(contenu, cle):
    a = next((a for a in contenu['articles'] if a['cle'] == cle), None)
    return None if a is None else '\n'.join([a['titre']] + a['paragraphes'])


class Ecran:
    """Un brouillon pur, lu et enregistré comme l'écran le fait (même
    chemin que ``services.modifier`` : validation puis ``personnaliser``)."""

    def __init__(self, type_acte, variante='', vente=None, **lecture):
        self.acte = acte_pur(type_acte, variante)
        self.vente = vente or vente_pure()
        self.lecture_kw = lecture

    def lecture(self):
        return LecturePure(self.acte.chantier, self.vente, **self.lecture_kw)

    def lire(self, langue='fr'):
        return K.construire_contenu(self.acte, langue, self.lecture())

    def enregistrer(self, corps, langue='fr'):
        propre = K.valider_surcharges(self.acte.type, corps, langue)
        champ = 'surcharges_ar' if langue == 'ar' else 'surcharges'
        setattr(self.acte, champ, K.personnaliser(self.acte, propre, langue,
                                                  self.lecture()))
        return getattr(self.acte, champ)

    def figes(self):
        return K.montants_figes(self.acte, self.lecture())


class EcranOptionsEtArticlesTests(SimpleTestCase):
    """B1 : options et articles dans le même corps."""

    def test_penalite_retiree_et_autre_article_corrige(self):
        """Défaut attrapé : l'article « Retard » (non touché) était comparé à
        une base SANS pénalité, paraissait modifié et restait figé avec son
        paragraphe de pénalité."""
        e = Ecran(T.CONTRAT)
        e.enregistrer({'options': options_ecran(e.lire(),
                                                penalite_retard_pct=10)})
        c = e.lire()
        self.assertIn('indemnité', article(c, 'retard'))
        e.enregistrer({'options': options_ecran(c, penalite_retard_pct=None),
                       'articles': articles_ecran(c, {'objet': ajouter(
                           ' Accès par le portail nord.')})})
        c = e.lire()
        self.assertNotIn('indemnité', article(c, 'retard'))
        self.assertIn('portail nord', article(c, 'objet'))
        self.assertEqual(e.figes(), [])

    def test_reserve_de_propriete_decochee_puis_recochee(self):
        """Défaut attrapé : réserve de propriété décochée + un article
        corrigé dans le même corps → l'article « Propriété » restait
        imprimé."""
        e = Ecran(T.CONTRAT)
        c = e.lire()
        ordre = [a['cle'] for a in c['articles']]
        e.enregistrer({'options': options_ecran(c, reserve_propriete=False),
                       'articles': articles_ecran(c, {'objet': ajouter(
                           ' Accès nord.')})})
        c = e.lire()
        self.assertIsNone(article(c, 'propriete'))
        self.assertFalse(any(x.get('retire')
                             for x in e.acte.surcharges['articles']))
        e.enregistrer({'options': options_ecran(c, reserve_propriete=True)})
        c = e.lire()
        self.assertEqual([a['cle'] for a in c['articles']], ordre)
        self.assertIn('Accès nord.', article(c, 'objet'))

    def test_penalite_changee_retard_intact_puis_corrige(self):
        """Défaut attrapé : pénalité 0,5 → 2 avec l'article « Retard » non
        touché : le texte gardait « 0,5 % » ; corrigé, il doit suivre aussi."""
        pct = K.C.pourcent
        e = Ecran(T.CONTRAT)
        e.enregistrer({'options': options_ecran(e.lire(),
                                                penalite_retard_pct=0.5)})
        c = e.lire()
        self.assertIn(pct('0.5'), article(c, 'retard'))
        e.enregistrer({'options': options_ecran(c, penalite_retard_pct=2),
                       'articles': articles_ecran(c, {'objet': ajouter(
                           ' Accès nord.')})})
        c = e.lire()
        self.assertIn(pct('2'), article(c, 'retard'))
        self.assertNotIn(pct('0.5'), article(c, 'retard'))
        e.enregistrer({'options': options_ecran(c, penalite_retard_pct=3),
                       'articles': articles_ecran(c, {'retard': remplacer(
                           'mise en demeure écrite',
                           'mise en demeure écrite et datée')})})
        texte = article(e.lire(), 'retard')
        self.assertIn('et datée', texte)
        self.assertIn(pct('3'), texte)
        self.assertNotIn(pct('2'), texte)
        self.assertEqual(e.figes(), [])

    def test_article_corrige_masque_par_l_option_puis_rendu(self):
        """Un article corrigé qu'une option retire n'est plus imprimé, un
        avertissement le dit, et il revient avec l'option — même après un
        autre enregistrement de la liste (qui ne le montrait pas)."""
        e = Ecran(T.CONTRAT)
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'propriete': ajouter(' Clause convenue.')})})
        e.enregistrer({'options': options_ecran(e.lire(),
                                                reserve_propriete=False)})
        c = e.lire()
        self.assertIsNone(article(c, 'propriete'))
        avert = K.avertissements(e.acte, None, e.lecture())
        self.assertTrue(any('Propriété du matériel' in a
                            and "n'est pas imprimé" in a for a in avert),
                        avert)
        e.enregistrer({'articles': articles_ecran(c, {'objet': ajouter(
            ' Accès nord.')})})
        e.enregistrer({'options': options_ecran(e.lire(),
                                                reserve_propriete=True)})
        c = e.lire()
        self.assertIn('Clause convenue.', article(c, 'propriete'))
        self.assertIn('Accès nord.', article(c, 'objet'))


class EcranMontantsTests(SimpleTestCase):
    """M2 : une même valeur portée par deux repères ; le filet à
    l'émission."""

    def test_cinquante_cinquante_tranche_reglee_suit_les_paiements(self):
        """Défaut attrapé : 50 / 50, article « Paiement » de la livraison
        « tranche réglée » corrigé avant tout paiement — total réglé et reste
        valent tous deux 50 000 : la valeur restait écrite en clair, et le
        contrôle d'émission la laissait passer (égale à une tranche)."""
        e = Ecran(T.LIVRAISON, T.TRANCHE_REGLEE,
                  vente=vente_pure(pcts=(50, 50), cles_=('acompte', 'solde')))
        c = e.lire()
        cinquante = K.C.montant('50000')
        self.assertEqual(article(c, 'paiement').count(cinquante), 2)
        e.enregistrer({'articles': articles_ecran(c, {
            'paiement': lambda t, x: (t, x.replace('Rien', 'Ainsi, rien', 1)
                                      + ' Merci.')})})
        e.vente = vente_pure(pcts=(50, 50), cles_=('acompte', 'solde'),
                             paiements=[('2026-12-02', '60000')])
        texte = article(e.lire(), 'paiement')
        self.assertIn('Ainsi, rien', texte)
        self.assertIn(K.C.montant('60000'), texte)
        self.assertIn(K.C.montant('40000'), texte)
        self.assertNotIn(cinquante, texte)
        self.assertEqual(e.figes(), [])

    def test_montant_modifie_en_son_milieu_refuse_meme_egal(self):
        """Défaut attrapé : un montant repris à la main qui égale une autre
        valeur vivante (une tranche) passait le contrôle d'émission."""
        e = Ecran(T.LIVRAISON, T.TRANCHE_REGLEE,
                  vente=vente_pure(pcts=(50, 50), cles_=('acompte', 'solde'),
                                   paiements=[('2026-12-02', '50000')]))
        cinquante = K.C.montant('50000')
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'paiement': remplacer(cinquante, cinquante.replace(',00', ''))})})
        figes = e.figes()
        self.assertEqual(len(figes), 1, figes)
        self.assertIn('« Paiement »', figes[0][0])
        self.assertEqual(figes[0][1], [Decimal('50000.00')])
        refus = S.motif_refus_emission(e.acte, e.lecture(), jumelle=False)
        self.assertEqual(refus[0], T.CODE_MONTANT_FIGE)
        self.assertIn('écrit à la main', refus[1])

    def test_espaces_normales_un_mot_change(self):
        """Défaut attrapé par la recette sur écran réel : le texte revenu du
        navigateur porte des espaces normales partout ; un seul mot changé,
        aucun montant ne doit devenir du texte figé."""
        e = Ecran(T.CONTRAT)

        def respacer(titre, texte):
            return titre, texte.replace(NB, ' ').replace(FINE, ' ')
        corrections = {a['cle']: respacer for a in e.lire()['articles']}
        corrections['prix'] = lambda t, x: respacer(t, x.replace(
            'définitif', 'non révisable', 1))
        e.enregistrer({'articles': articles_ecran(e.lire(), corrections)})
        stockes = [x for x in e.acte.surcharges['articles'] if len(x) > 1]
        self.assertEqual([x['cle'] for x in stockes], ['prix'])
        p0 = stockes[0]['paragraphes'][0]
        self.assertEqual(p0['defaut'], 0)
        self.assertIn('{total_ttc}', p0['texte'])
        self.assertEqual(e.figes(), [])
        # Le montant garde ses espaces insécables (valeur vivante).
        self.assertIn(f'**ferme et non révisable** : '
                      f'{K.C.montant("100000")}', article(e.lire(), 'prix'))


class EcranValeursVidesTests(SimpleTestCase):
    """M3 : un repère dont la valeur était VIDE à l'enregistrement."""

    def test_quitus_personnalise_avant_l_avoir(self):
        """Défaut attrapé : quitus corrigé sans avoir (``ecart_regle`` vide)
        puis un avoir : la phrase qui le nomme ne revenait jamais."""
        payee = vente_pure(paiements=[('2026-12-20', '100000')])
        e = Ecran(T.CLOTURE, vente=payee)
        quitus = texte_vers_paragraphes('\n\n'.join(e.lire()['quitus']))
        envoye = [quitus[0] + ' Merci de votre confiance.'] + quitus[1:]
        e.enregistrer({'quitus': envoye})
        self.assertEqual(e.lire()['quitus'], envoye)
        e.vente = vente_pure(paiements=[('2026-12-20', '90000')],
                             avoirs='10000')
        premier = e.lire()['quitus'][0]
        ecart = K.ecart_regle(Decimal('100000'), Decimal('90000'),
                              Decimal('10000'), 'fr')
        self.assertTrue(ecart)
        self.assertIn(ecart + ' Merci de votre confiance.', premier)
        e.vente = payee
        e.enregistrer({'quitus': quitus})  # retour au défaut
        self.assertNotIn('quitus', e.acte.surcharges)

    def test_date_du_contrat_apparait_une_fois_emis(self):
        """Défaut attrapé : article « Ce que vaut la réception » corrigé
        avant l'émission du contrat (``contrat_du`` vide) : la date du
        contrat n'était jamais imprimée ensuite."""
        e = Ecran(T.RECEPTION)
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'portee': remplacer('En signant,', 'En signant ce document,')})})
        e.lecture_kw['date_contrat'] = date(2026, 11, 24)
        texte = article(e.lire(), 'portee')
        self.assertIn('En signant ce document,', texte)
        self.assertIn('CTR-2026-11-0007 du 24 novembre 2026', texte)


class EcranTextesTests(SimpleTestCase):

    def test_phrase_supprimee_avec_ses_reperes(self):
        """Une phrase supprimée emporte ses repères ; le reste du paragraphe
        suit toujours la société."""
        e = Ecran(T.CONTRAT)
        phrase = (' Si elle reste sans effet pendant huit jours, Solaire '
                  'Exemple SARL peut suspendre')
        texte = article(e.lire(), 'retard')
        self.assertIn(phrase, texte)
        fin = texte.index('propriété.', texte.index(phrase)) + len('propriété.')
        coupe = texte[texte.index(phrase):fin]
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'retard': remplacer(coupe, '')})})
        e.lecture_kw['societe'] = 'Nouveau Nom SARL'
        texte = article(e.lire(), 'retard')
        self.assertNotIn('sans effet', texte)
        self.assertIn('date prévue, Nouveau Nom SARL adresse', texte)

    def test_paragraphe_ajoute(self):
        """Un paragraphe ajouté est du texte ; les autres restent des
        renvois vivants."""
        e = Ecran(T.CONTRAT)
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'objet': ajouter('\n\nUn paragraphe ajouté par le commercial.')})})
        stocke = next(x for x in e.acte.surcharges['articles']
                      if x['cle'] == 'objet')
        self.assertEqual(stocke['paragraphes'],
                         [{'defaut': 0}, {'defaut': 1}, {'defaut': 2},
                          'Un paragraphe ajouté par le commercial.'])
        e.lecture_kw['societe'] = 'Nouveau Nom SARL'
        self.assertIn('Nouveau Nom SARL fournit', article(e.lire(), 'objet'))

    def test_retablir_un_article_puis_tout_retablir(self):
        """Corps de l'éditeur pour « Rétablir » : la liste ENTIÈRE, l'article
        rétabli réduit à ``{cle}`` (= retour au texte par défaut, jamais une
        suppression) ; « Tout rétablir » envoie ``articles: null``."""
        e = Ecran(T.CONTRAT)
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'objet': ajouter(' Ajout A.'), 'prix': ajouter(' Ajout B.')})})
        self.assertEqual(K.articles_personnalises(e.acte), ['objet', 'prix'])
        corps = [{'cle': a['cle']} if a['cle'] == 'objet' else a
                 for a in articles_ecran(e.lire())]
        e.enregistrer({'articles': corps})
        c = e.lire()
        self.assertIn('objet', [a['cle'] for a in c['articles']])
        self.assertNotIn('Ajout A.', article(c, 'objet'))
        self.assertIn('Ajout B.', article(c, 'prix'))
        self.assertEqual(K.articles_personnalises(e.acte), ['prix'])
        e.enregistrer({'articles': None})
        self.assertNotIn('articles', e.acte.surcharges)
        self.assertEqual(K.articles_personnalises(e.acte), [])
        self.assertNotIn('Ajout B.', article(e.lire(), 'prix'))

    def test_modele_de_la_societe_garde_les_reperes(self):
        """Un article corrigé devenu modèle garde ses repères : un autre
        chantier imprime SA société et la correction."""
        from types import SimpleNamespace
        e = Ecran(T.CONTRAT)
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'objet': remplacer('fournit, pose', 'fournit, livre, pose')})})
        modele = K.textes_pour_modele(e.acte, 'fr', e.lecture())
        objet = next(x for x in modele['articles'] if x['cle'] == 'objet')
        self.assertNotIn('Solaire Exemple', K.texte_litteral(
            [objet['titre']] + objet['paragraphes']))
        autre = Ecran(T.CONTRAT, societe='Autre Société SARL', modeles={
            T.CONTRAT: SimpleNamespace(surcharges={'articles': modele[
                'articles']}, surcharges_ar={})})
        self.assertIn('Autre Société SARL fournit, livre, pose',
                      article(autre.lire(), 'objet'))

    def test_accolades_tapees(self):
        """Des accolades tapées s'impriment telles quelles, jamais
        substituées (même « {societe} »)."""
        e = Ecran(T.CONTRAT)
        e.enregistrer({'articles': articles_ecran(e.lire(), {
            'objet': ajouter(' Clause {spéciale} et {societe}.')})})
        self.assertIn(' Clause {spéciale} et {societe}.',
                      article(e.lire(), 'objet'))

    def test_ancienne_forme_stockee_lue_sans_erreur(self):
        """Une entrée de l'ancienne forme (gabarit par valeurs) se lit,
        rendue telle qu'elle est."""
        e = Ecran(T.CONTRAT)
        e.acte.surcharges = {'articles': [
            {'cle': 'objet', 'titre': 'Objet du contrat', 'base': True,
             'paragraphes': ['{societe} fournit tout. {{x}} {societe[x]}']}]}
        self.assertIn('Solaire Exemple SARL fournit tout. {x} {societe[x]}',
                      article(e.lire(), 'objet'))


class EcranReperesApresPersonnalisationTests(SimpleTestCase):
    """M4 : les repères lus APRÈS les personnalisations de l'acte."""

    def test_modalites_de_paiement_personnalisees(self):
        """Défaut attrapé : ``{modalites_paiement}`` était calculé avant la
        personnalisation « paiement » : l'article Paiement contredisait
        l'encadré du même contrat."""
        e = Ecran(T.CONTRAT)
        e.enregistrer({'paiement': {'modalites': 'Paiement par virement '
                                                 'sur le compte convenu.'}})
        c = e.lire()
        self.assertEqual(c['paiement']['modalites'],
                         'Paiement par virement sur le compte convenu.')
        self.assertIn('Paiement par virement sur le compte convenu.',
                      article(c, 'paiement'))

    def test_garantie_d_installation_personnalisee_deux_langues(self):
        """Défaut attrapé : ``{garantie_installation}`` était calculé avant
        la personnalisation des garanties : l'article disait « 2 ans » quand
        le tableau du même contrat disait 36 mois."""
        e = Ecran(T.CONTRAT)
        garanties = [dict(g, duree_mois=36) if g['cle'] == 'installation'
                     else g for g in e.lire()['garanties']]
        e.enregistrer({'garanties': garanties})
        for langue in T.LANGUES:
            with self.subTest(langue=langue):
                c = e.lire(langue)
                pose = next(g for g in c['garanties']
                            if g['cle'] == 'installation')
                self.assertEqual(pose['duree_mois'], 36)
                texte = article(c, 'garanties')
                self.assertIn(K.C.duree_mois(36, langue=langue), texte)
                self.assertNotIn(K.C.duree_mois(24, langue=langue), texte)


class EcheancierConvenuPursTests(SimpleTestCase):
    """C1 (recette sur écran réel) : l'échéancier imprimé est celui CONVENU."""

    def test_facture_d_acompte_d_un_montant_un_peu_different(self):
        """Défaut attrapé : avec une facture d'acompte émise de 33 024 DH
        (30 % de 110 400 = 33 120), chaque acte imprimait « Acompte
        96,00 DH · 0,1 % » (ce qu'il restait à facturer), somme 77 376."""
        plan = [  # forme de plan_facturation : montant_ttc = reste à faire
            {'cle': 't1', 'key': 'acompte', 'libelle': 'Acompte',
             'montant_ttc': Decimal('96.00'),
             'cible_cumul_ttc': Decimal('33120.00')},
            {'cle': 't2', 'key': 'materiel',
             'libelle': 'Livraison du matériel',
             'montant_ttc': Decimal('66240.00'),
             'cible_cumul_ttc': Decimal('99360.00')},
            {'cle': 't3', 'key': 'solde', 'libelle': 'Solde',
             'montant_ttc': Decimal('11040.00'),
             'cible_cumul_ttc': Decimal('110400.00')}]
        tranches = K.tranches_convenues(plan, Decimal('110400'))
        self.assertEqual([t['montant'] for t in tranches],
                         [Decimal('33120.00'), Decimal('66240.00'),
                          Decimal('11040.00')])
        self.assertEqual(sum(t['montant'] for t in tranches),
                         Decimal('110400.00'))
        self.assertEqual([t['pourcentage'] for t in tranches],
                         [Decimal('30.00'), Decimal('60.00'),
                          Decimal('10.00')])
        # La dernière prend le reste au centime, même si sa cible s'arrête
        # avant le prix (facture d'acompte re-pointée).
        plan[0]['cible_cumul_ttc'] = Decimal('33024.00')
        plan[1]['cible_cumul_ttc'] = Decimal('99264.00')
        plan[2]['cible_cumul_ttc'] = Decimal('110304.00')
        tranches = K.tranches_convenues(plan, Decimal('110400'))
        self.assertEqual(sum(t['montant'] for t in tranches),
                         Decimal('110400.00'))
        self.assertEqual(tranches[-1]['cible'], Decimal('110400.00'))

    def test_frise_et_liste_des_tranches_deux_langues(self):
        """La frise (``echeancier``) et la liste de l'article Paiement
        portent les montants convenus, dans les deux langues."""
        vente = vente_pure(prix='110400')
        acte = acte_pur(T.CONTRAT)
        for langue in T.LANGUES:
            c = K.construire_contenu(acte, langue, LecturePure(
                acte.chantier, vente))
            self.assertEqual([t['montant_ttc'] for t in c['echeancier']],
                             ['33120.00', '66240.00', '11040.00'])
            texte = article(c, 'paiement')
            for m in ('33120', '66240', '11040'):
                self.assertIn(K.C.montant(m, langue=langue), texte)


class ClotureNonSoldeePursTests(SimpleTestCase):
    """C2 (recette sur écran réel)."""

    def test_ecart_jamais_nomme_pour_une_somme_impayee(self):
        """Défaut attrapé : 110 400 DH dus, le quitus disait « le reste,
        110 400,00 DH, a été soldé par avoir, retenue à la source ou abandon
        de créance »."""
        self.assertEqual(K.ecart_regle(Decimal('110400'), Decimal('0'),
                                       Decimal('0'), 'fr',
                                       reste=Decimal('110400')), '')
        self.assertTrue(K.ecart_regle(Decimal('100000'), Decimal('90000'),
                                      Decimal('10000'), 'fr',
                                      reste=Decimal('0')))
        e = Ecran(T.CLOTURE, vente=vente_pure(prix='110400'))
        for langue in T.LANGUES:
            quitus = ' '.join(e.lire(langue)['quitus'])
            self.assertNotIn('abandon de créance', quitus)
            self.assertNotIn('بالتنازل عن الدين', quitus)

    def test_drapeau_brouillon(self):
        """Le contenu servi d'un brouillon porte ``brouillon: True`` (le PDF
        se marque « PROJET ») ; le contenu que l'émission fige, False."""
        acte = acte_pur(T.CLOTURE)
        lecture = LecturePure(acte.chantier, vente_pure())
        self.assertIs(K.contenu_de(acte, 'fr', lecture)['brouillon'], True)
        self.assertIs(K.construire_contenu(acte, 'ar', lecture)['brouillon'],
                      False)
        acte.statut, acte.contenu = T.EMIS, {'brouillon': False}
        self.assertIs(K.contenu_de(acte, 'fr', lecture)['brouillon'], False)


class GarantiesDuContratPursTests(SimpleTestCase):
    """C3 (recette sur écran réel) : une garantie par chantier."""

    def test_cloture_reprend_les_garanties_du_contrat(self):
        """Défaut attrapé : garantie d'installation portée à 36 mois sur le
        contrat (signé), le certificat de la clôture imprimait « 2 ans » ;
        sa date de départ restait « … » alors que la réception était
        signée."""
        contrat = Ecran(T.CONTRAT)
        garanties = [dict(g, duree_mois=36) if g['cle'] == 'installation'
                     else g for g in contrat.lire()['garanties']]
        contrat.enregistrer({'garanties': garanties})
        du_contrat = {langue: contrat.lire(langue)['garanties']
                      for langue in T.LANGUES}
        cloture = Ecran(T.CLOTURE, vente=vente_pure(
            paiements=[('2026-12-21', '100000')]),
            garanties_contrat=du_contrat,
            reception_signee=date(2026, 12, 18))
        # La clôture corrige un texte et tente une durée : seul le texte
        # passe (les durées sont celles du contrat).
        perso = [dict(g, detail='Pose et câblage.', duree_mois=6)
                 if g['cle'] == 'installation' else g
                 for g in cloture.lire()['garanties']]
        cloture.enregistrer({'garanties': perso})
        for langue in T.LANGUES:
            with self.subTest(langue=langue):
                c = cloture.lire(langue)
                self.assertEqual(c['reception']['date'], '2026-12-18')
                self.assertEqual([g['cle'] for g in c['garanties']],
                                 [g['cle'] for g in du_contrat[langue]])
                pose = next(g for g in c['garanties']
                            if g['cle'] == 'installation')
                self.assertEqual(pose['duree_mois'], 36)
                self.assertEqual(pose['fin'], '2029-12-18')
                if langue == 'fr':
                    self.assertEqual(pose['detail'], 'Pose et câblage.')

    def test_sans_reception_signee_la_date_du_chantier(self):
        cloture = Ecran(T.CLOTURE)
        self.assertEqual(cloture.lire()['reception']['date'], '2026-12-21')


class FaitsFrancaisEnArabePursTests(SimpleTestCase):
    """C4 (recette sur écran réel) : le document arabe n'omet aucun fait."""

    def test_cases_reserves_et_conditions_saisies_en_francais(self):
        """Défaut attrapé : les cases cochées en français, les réserves et
        les conditions particulières tapées en français n'apparaissaient
        pas dans le PDF arabe."""
        e = Ecran(T.LIVRAISON, T.RESTE_A_REGLER)
        constats = [dict(k, cochee=True) for k in e.lire()['constats']]
        constats[1]['cochee'] = False
        constats.append({'texte': 'Un carton abîmé, contenu intact.',
                         'cochee': True})
        e.enregistrer({'constats': constats,
                       'reserves': ['Rayure sur le coffret onduleur.'],
                       'conditions_particulieres': 'Accès par le portail.'})
        defauts_ar = e.lire('ar')
        self.assertEqual([k['cochee'] for k in defauts_ar['constats']],
                         [True, False, True, True])
        self.assertNotEqual(defauts_ar['constats'][0]['texte'],
                            constats[0]['texte'])  # texte arabe gardé
        self.assertEqual(defauts_ar['constats'][-1]['texte'],
                         'Un carton abîmé, contenu intact.')
        self.assertEqual(defauts_ar['reserves'],
                         ['Rayure sur le coffret onduleur.'])
        self.assertEqual(defauts_ar['conditions_particulieres'],
                         'Accès par le portail.')
        # Traduits à la main : la traduction l'emporte, les cases restent
        # celles du français.
        e.enregistrer({'reserves': ['خدش على علبة العاكس.'],
                       'constats': [{'texte': f'نص {i}', 'cochee': False}
                                    for i in range(4)]}, 'ar')
        ar = e.lire('ar')
        self.assertEqual(ar['reserves'], ['خدش على علبة العاكس.'])
        self.assertEqual([k['cochee'] for k in ar['constats']],
                         [True, False, True, True])
        self.assertEqual(ar['constats'][0]['texte'], 'نص 0')


class EcranAllerRetourTests(SimpleTestCase):

    def test_rien_change_rien_stocke_cinq_actes_deux_langues(self):
        """Renvoyer ce qui est affiché ne stocke rien et ne change rien."""
        vente = vente_pure(paiements=[('2026-12-02', '30000')])
        for type_acte, variante in CINQ_ACTES:
            for langue in T.LANGUES:
                with self.subTest(acte=type_acte, variante=variante,
                                  langue=langue):
                    e = Ecran(type_acte, variante, vente=vente)
                    c = e.lire(langue)
                    corps = {'articles': articles_ecran(c)}
                    if 'quitus' in c:
                        corps['quitus'] = texte_vers_paragraphes(
                            '\n\n'.join(c['quitus']))
                    s = e.enregistrer(corps, langue)
                    self.assertTrue(all(set(x) == {'cle'}
                                        for x in s['articles']), s)
                    self.assertNotIn('quitus', s)
                    self.assertEqual(e.lire(langue), c)

    def test_un_mot_change_aller_retour_et_idempotence(self):
        """Un mot ajouté : le texte servi est celui envoyé ; enregistrer
        deux fois le même texte stocke la même chose."""
        vente = vente_pure(paiements=[('2026-12-02', '30000')])
        mots = {'fr': ' Texte ajouté.', 'ar': ' نص أضافه المستشار.'}
        for type_acte, variante in CINQ_ACTES:
            for langue in T.LANGUES:
                with self.subTest(acte=type_acte, variante=variante,
                                  langue=langue):
                    e = Ecran(type_acte, variante, vente=vente)
                    c = e.lire(langue)
                    cles_ = [a['cle'] for a in c['articles']]
                    envoye = articles_ecran(c, {
                        cle: ajouter(mots[langue]) for cle in cles_})
                    premier = e.enregistrer({'articles': envoye}, langue)
                    self.assertEqual(e.lire(langue)['articles'], envoye)
                    premier = json.loads(json.dumps(premier))
                    second = e.enregistrer(
                        {'articles': articles_ecran(e.lire(langue))}, langue)
                    self.assertEqual(second, premier)
                    self.assertEqual(e.figes(), [])
