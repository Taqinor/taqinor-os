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
    """Fonctions pures du gabarit (aucune base)."""

    def aller_retour(self, texte, ctx, prefere=()):
        g = K.gabarit(texte, ctx, prefere)
        self.assertEqual(K.rendre_gabarit(g, ctx), texte)
        return g

    def test_valeur_prefixe_d_une_autre(self):
        petit, grand = f'9{FINE}850,00{NB}DH', f'59{FINE}850,00{NB}DH'
        texte = f'Reste {petit}, soit sur {grand} au total.'
        g = self.aller_retour(texte, {'reste': petit, 'total': grand})
        self.assertEqual(g, 'Reste {reste}, soit sur {total} au total.')
        # La petite valeur seule ne mord jamais dans la grande.
        g = self.aller_retour(f'Sur {grand}.', {'reste': petit})
        self.assertEqual(g, f'Sur {grand}.')
        g = self.aller_retour(f'Sur 1{FINE}00{petit}.', {'reste': petit})
        self.assertNotIn('{reste}', g)

    def test_liste_des_tranches_sur_plusieurs_lignes(self):
        liste = (f'- **30{NB}%**, soit 29{FINE}550,00{NB}DH, à la signature ;\n'
                 f'- **70{NB}%**, soit 68{FINE}950,00{NB}DH, à la réception.')
        ctx = {'liste_tranches': liste, 'acompte': f'29{FINE}550,00{NB}DH'}
        g = self.aller_retour(f'Le prix est payé ainsi :\n{liste}\nMerci.',
                              ctx)
        self.assertEqual(g, 'Le prix est payé ainsi :\n{liste_tranches}\n'
                            'Merci.')

    def test_valeur_vide_jamais_remplacee_et_accolades_gardees(self):
        ctx = {'cndp': '', 'blanc': '  ', 'societe': 'TAQINOR'}
        g = self.aller_retour('TAQINOR garde la clause {spéciale} et {0}.',
                              ctx)
        self.assertEqual(g, '{societe} garde la clause {{spéciale}} et {{0}}.')

    def test_valeur_portee_par_deux_reperes(self):
        v = f'9{FINE}850,00{NB}DH'
        ctx = {'reste_a_regler': v, 'reste_apres_livraison': v}
        self.assertEqual(self.aller_retour(f'Reste {v}.', ctx), f'Reste {v}.')
        self.assertEqual(
            self.aller_retour(f'Reste {v}.', ctx, {'reste_a_regler'}),
            'Reste {reste_a_regler}.')

    def test_contexte_arabe(self):
        ctx = {'total_ttc': f'98{FINE}500,00{NB}درهم',
               'societe': 'تاقينور', 'date_limite': '23 يناير 2027'}
        texte = f'تلتزم تاقينور بثمن 98{FINE}500,00{NB}درهم قبل 23 يناير 2027.'
        g = self.aller_retour(texte, ctx)
        self.assertEqual(g, 'تلتزم {societe} بثمن {total_ttc} قبل '
                            '{date_limite}.')

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
        self.assertTrue(any('{liste_tranches}' in p
                            for p in stocke['paragraphes']), stocke)
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
        self.assertIn('{client}', acte.surcharges['quitus'][0])
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
