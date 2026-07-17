"""Sélecteurs LECTURE SEULE de la Comptabilité générale (états & restitutions).

Grand livre (FG110), balance générale (FG111), lettrage (FG112), CPC (FG113) et
bilan (FG114) se déduisent tous des ``LigneEcriture`` du grand livre. Aucune
écriture n'est modifiée ici. Toutes les fonctions sont scopées par société.
"""
import re
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, Sum
from django.utils import timezone

from .models import (
    Budget, BudgetLigne, Caisse, CautionBancaire, CessionImmobilisation,
    ChargeConstateeAvance,
    CompteComptable,
    CompteTresorerie, EcheanceEmprunt,
    Effet, Emprunt,
    EntiteConsolidation, Immobilisation, IndemniteChantier, LigneEcriture,
    LignePrevisionnelTresorerie,
    MouvementCaisse, Rapprochement, RetenueGarantie, RetenueSource,
    TauxDevise, TimbreFiscal,
    ClotureCaisse, DotationAmortissement, EcritureComptable,
    NoteFrais, Provision, RapprochementBancaire,
)


def _as_date(value):
    """Normalise une date (str ISO ou ``date``) en ``date``, ou None."""
    if value is None or value == '':
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _lignes_qs(company, *, date_debut=None, date_fin=None, validees_seulement=False):
    qs = LigneEcriture.objects.filter(company=company).select_related(
        'compte', 'ecriture')
    if date_debut:
        qs = qs.filter(ecriture__date_ecriture__gte=date_debut)
    if date_fin:
        qs = qs.filter(ecriture__date_ecriture__lte=date_fin)
    if validees_seulement:
        qs = qs.filter(ecriture__statut='validee')
    return qs


# ── FG110 / COMPTA19 — Grand livre ─────────────────────────────────────────

def grand_livre(company, *, compte=None, date_debut=None, date_fin=None,
                validees_seulement=False):
    """Détail des mouvements par compte avec solde courant cumulé.

    Renvoie une liste de dicts par compte :
    ``{'compte', 'numero', 'intitule', 'lignes': [...], 'total_debit',
    'total_credit', 'solde'}`` où chaque ligne porte un ``solde_courant`` cumulé.
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement).order_by(
        'compte__numero', 'ecriture__date_ecriture', 'id')
    if compte is not None:
        qs = qs.filter(compte=compte)
    resultat = {}
    soldes = {}
    for ligne in qs:
        num = ligne.compte.numero
        bucket = resultat.setdefault(num, {
            'compte_id': ligne.compte_id,
            'numero': num,
            'intitule': ligne.compte.intitule,
            'lignes': [],
            'total_debit': Decimal('0'),
            'total_credit': Decimal('0'),
        })
        solde = soldes.get(num, Decimal('0')) + ligne.debit - ligne.credit
        soldes[num] = solde
        bucket['total_debit'] += ligne.debit
        bucket['total_credit'] += ligne.credit
        bucket['lignes'].append({
            'date': ligne.ecriture.date_ecriture,
            'journal': ligne.ecriture.journal.code,
            'reference': ligne.ecriture.reference,
            'libelle': ligne.libelle or ligne.ecriture.libelle,
            'debit': ligne.debit,
            'credit': ligne.credit,
            'lettrage': ligne.lettrage,
            'solde_courant': solde,
        })
    for bucket in resultat.values():
        bucket['solde'] = bucket['total_debit'] - bucket['total_credit']
    return sorted(resultat.values(), key=lambda b: b['numero'])


# ── ZACC4 — Journal Items : ledger PLAT ligne-à-ligne (toutes écritures) ────

def journal_items(company, *, journal=None, compte=None, tiers_type=None,
                  tiers_id=None, date_debut=None, date_fin=None,
                  lettrage=None, validees=None):
    """Vue plate de CHAQUE ``LigneEcriture`` (débit/crédit), toutes écritures
    confondues, filtrable par journal/compte/tiers/période/lettrage/statut —
    le « Journal Items » d'Odoo (indispensable pour l'audit et le pointage
    transversal, complète ``grand_livre`` qui GROUPE par compte).

    ``journal`` : code du journal (ex. 'BNK', 'VTE') ou instance ``Journal``.
    ``lettrage`` : ``'lettrees'`` (lettrage non vide), ``'non_lettrees'``
    (lettrage vide), ou ``None`` (toutes).
    ``validees`` : ``True``/``False``/``None`` (toutes, défaut).

    Renvoie une liste de dicts triée par date pièce puis id : ``{'id',
    'date_ecriture', 'journal_code', 'ecriture_reference', 'compte_numero',
    'compte_intitule', 'libelle', 'tiers_type', 'tiers_id', 'debit',
    'credit', 'lettrage', 'statut'}``. Lecture seule, company-scopée."""
    qs = (LigneEcriture.objects
          .filter(company=company)
          .select_related('compte', 'ecriture', 'ecriture__journal')
          .order_by('ecriture__date_ecriture', 'id'))
    if date_debut:
        qs = qs.filter(ecriture__date_ecriture__gte=_as_date(date_debut))
    if date_fin:
        qs = qs.filter(ecriture__date_ecriture__lte=_as_date(date_fin))
    if journal:
        code = getattr(journal, 'code', journal)
        qs = qs.filter(ecriture__journal__code=code)
    if compte:
        numero = getattr(compte, 'numero', compte)
        qs = qs.filter(compte__numero=numero)
    if tiers_type:
        qs = qs.filter(tiers_type=tiers_type)
    if tiers_id:
        qs = qs.filter(tiers_id=tiers_id)
    if lettrage == 'lettrees':
        qs = qs.exclude(lettrage='')
    elif lettrage == 'non_lettrees':
        qs = qs.filter(lettrage='')
    if validees is True:
        qs = qs.filter(ecriture__statut=EcritureComptable.Statut.VALIDEE)
    elif validees is False:
        qs = qs.exclude(ecriture__statut=EcritureComptable.Statut.VALIDEE)

    out = []
    for ligne in qs:
        ecriture = ligne.ecriture
        out.append({
            'id': ligne.id,
            'date_ecriture': ecriture.date_ecriture,
            'journal_code': ecriture.journal.code if ecriture.journal else '',
            'ecriture_reference': ecriture.reference,
            'compte_numero': ligne.compte.numero,
            'compte_intitule': ligne.compte.intitule,
            'libelle': ligne.libelle or ecriture.libelle,
            'tiers_type': ligne.tiers_type,
            'tiers_id': ligne.tiers_id,
            'debit': ligne.debit,
            'credit': ligne.credit,
            'lettrage': ligne.lettrage,
            'statut': ecriture.statut,
        })
    return out


# ── ZACC2 — Colonne comparative N-1 sur les états STANDARD (bilan/CPC/
# balance/ESG). L'existant (XACC19) porte le N-1 sur les états PERSONNALISÉS
# uniquement ; les états CGNC natifs ne comparaient rien. On ajoute un mode
# comparatif OPTIONNEL : sans paramètre, chaque selector renvoie EXACTEMENT
# son dict actuel (aucune régression) ; ``comparer=True`` (vue) enrichit
# chaque ligne par clé (``numero`` pour bilan/balance, ``code`` pour l'ESG)
# avec la valeur N-1, l'écart absolu et l'écart % — un exercice sans N-1
# renvoie 0 (jamais d'erreur).

def _decalage_un_an(valeur):
    """Décale une date d'exactement un an en arrière (29 fév -> 28 fév)."""
    d = _as_date(valeur)
    if d is None:
        return None
    try:
        return d.replace(year=d.year - 1)
    except ValueError:  # 29 février d'une année bissextile.
        return d.replace(year=d.year - 1, day=28)


def _periode_n1(date_debut, date_fin, date_debut_n1=None, date_fin_n1=None):
    """Résout la période N-1 : les bornes explicites priment, sinon la même
    période décalée d'un an (jamais d'erreur si aucune période N-1 n'existe —
    l'appelant reçoit simplement des soldes nuls)."""
    deb_n1 = date_debut_n1 or _decalage_un_an(date_debut)
    fin_n1 = date_fin_n1 or _decalage_un_an(date_fin)
    return deb_n1, fin_n1


def _ecart_pct(valeur_n, valeur_n1):
    """Écart % = (N − N-1) / |N-1| × 100, ``None`` si N-1 = 0 (indéterminé)."""
    if not valeur_n1:
        return None
    return ((valeur_n - valeur_n1) / abs(valeur_n1) * Decimal('100')
            ).quantize(Decimal('0.01'))


def _fusionner_comparatif(lignes_n, lignes_n1, cle):
    """Fusionne deux listes de lignes (dicts) par ``cle`` : ajoute
    ``montant_n1``/``ecart``/``ecart_pct`` sur chaque ligne de ``lignes_n``
    (une ligne présente seulement en N-1 n'est pas ajoutée — l'état N reste le
    référentiel de lignes affichées, comme le veut le menu « Comparison »)."""
    par_cle = {ligne[cle]: ligne for ligne in lignes_n1}
    out = []
    for ligne in lignes_n:
        ligne = dict(ligne)
        n1 = par_cle.get(ligne[cle])
        montant_n1 = (n1['montant'] if n1 is not None
                      else Decimal('0'))
        ligne['montant_n1'] = montant_n1
        ligne['ecart'] = ligne['montant'] - montant_n1
        ligne['ecart_pct'] = _ecart_pct(ligne['montant'], montant_n1)
        out.append(ligne)
    return out


# ── FG111 / COMPTA20 — Balance générale (trial balance) ────────────────────

def balance_generale(company, *, date_debut=None, date_fin=None,
                     validees_seulement=False, comparer=False,
                     date_debut_n1=None, date_fin_n1=None):
    """Débit/crédit/solde par compte sur une période (≠ balance âgée clients).

    Renvoie une liste de dicts triée par numéro + des totaux globaux. La somme
    des débits doit égaler la somme des crédits (le grand livre est équilibré).

    ZACC2 — ``comparer=True`` ajoute, par ligne, le solde débiteur N-1
    (``solde_debiteur_n1``) et l'écart (``ecart_solde_debiteur``,
    ``ecart_solde_debiteur_pct``), calculés sur ``date_debut_n1``/
    ``date_fin_n1`` (défaut : même intervalle décalé d'un an). Défaut
    (``comparer`` omis) = réponse actuelle byte-identique.
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement)
    agg = qs.values(
        'compte__numero', 'compte__intitule', 'compte__classe',
    ).annotate(
        debit=Sum('debit'), credit=Sum('credit'),
    ).order_by('compte__numero')
    lignes = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for row in agg:
        debit = row['debit'] or Decimal('0')
        credit = row['credit'] or Decimal('0')
        solde = debit - credit
        total_debit += debit
        total_credit += credit
        lignes.append({
            'numero': row['compte__numero'],
            'intitule': row['compte__intitule'],
            'classe': row['compte__classe'],
            'debit': debit,
            'credit': credit,
            'solde_debiteur': solde if solde > 0 else Decimal('0'),
            'solde_crediteur': -solde if solde < 0 else Decimal('0'),
        })
    resultat = {
        'lignes': lignes,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'equilibree': total_debit == total_credit,
    }
    if comparer:
        deb_n1, fin_n1 = _periode_n1(date_debut, date_fin, date_debut_n1,
                                     date_fin_n1)
        n1 = balance_generale(
            company, date_debut=deb_n1, date_fin=fin_n1,
            validees_seulement=validees_seulement)
        lignes_n1 = [
            {'numero': li['numero'], 'montant': li['solde_debiteur']}
            for li in n1['lignes']]
        fusion = _fusionner_comparatif(
            [{'numero': li['numero'], 'montant': li['solde_debiteur'],
              **li} for li in lignes],
            lignes_n1, 'numero')
        for li, f in zip(lignes, fusion):
            li['solde_debiteur_n1'] = f['montant_n1']
            li['ecart_solde_debiteur'] = f['ecart']
            li['ecart_solde_debiteur_pct'] = f['ecart_pct']
        resultat['date_debut_n1'] = deb_n1
        resultat['date_fin_n1'] = fin_n1
    return resultat


# ── FG141 — Export FEC (Fichier des Écritures Comptables, format DGI) ───────

# Colonnes normalisées du FEC (ordre figé, exigé par l'administration fiscale).
# Adapté du standard FEC français (audit DGI) : une ligne par ligne d'écriture,
# ordonnée par date puis numéro de pièce. Aucun prix d'achat / aucune marge.
FEC_COLUMNS = [
    'JournalCode', 'JournalLib', 'EcritureNum', 'EcritureDate', 'CompteNum',
    'CompteLib', 'CompAuxNum', 'CompAuxLib', 'PieceRef', 'PieceDate',
    'EcritureLib', 'Debit', 'Credit', 'EcritureLet', 'DateLet',
    'ValidDate', 'Montantdevise', 'Idevise',
]


def _fec_date(valeur):
    """Formate une date au format FEC ``AAAAMMJJ`` (vide si absente)."""
    if not valeur:
        return ''
    return valeur.strftime('%Y%m%d')


def _fec_montant(valeur):
    """Formate un montant FEC : décimale à virgule, deux décimales, jamais vide."""
    return f'{(valeur or Decimal("0")):.2f}'.replace('.', ',')


def _fec_to_decimal(valeur):
    """Relit un montant FEC (« 1234,56 ») en ``Decimal`` (COMPTA37)."""
    if not valeur:
        return Decimal('0')
    return Decimal(str(valeur).replace(',', '.'))


def export_fec(company, exercice, *, validees_seulement=False):
    """Lignes du FEC d'un exercice, ordonnées et prêtes pour l'export DGI (FG141).

    Produit UNE ligne par ``LigneEcriture`` de l'exercice (bornée par
    ``exercice.date_debut``/``date_fin``), triée par date d'écriture puis numéro
    de pièce (``EcritureNum``) puis ordre de saisie — l'ordre auditable exigé.
    Chaque ligne porte les colonnes normalisées ``FEC_COLUMNS``. Tout est déduit
    du grand livre (``LigneEcriture``) ; aucune écriture n'est modifiée et la
    fonction est scopée société.

    Renvoie ``{'exercice', 'date_debut', 'date_fin', 'columns', 'lignes',
    'total_debit', 'total_credit', 'equilibre', 'nb_lignes'}`` où ``lignes`` est
    une liste de dicts (clés = ``FEC_COLUMNS``).
    """
    qs = LigneEcriture.objects.filter(
        company=company,
        ecriture__date_ecriture__gte=exercice.date_debut,
        ecriture__date_ecriture__lte=exercice.date_fin,
    ).select_related('compte', 'ecriture', 'ecriture__journal')
    if validees_seulement:
        qs = qs.filter(ecriture__statut='validee')
    # Ordre auditable : date d'écriture, puis pièce (numéro d'écriture stable =
    # l'id de la pièce), puis ordre de saisie de la ligne.
    qs = qs.order_by(
        'ecriture__date_ecriture', 'ecriture_id', 'id')

    lignes = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    for ligne in qs:
        ecriture = ligne.ecriture
        compte = ligne.compte
        # Auxiliaire (tiers) : renseigné seulement pour un compte de tiers porté
        # par une ligne pointant un tiers (CompAux* sinon vides, comme le veut le
        # standard FEC).
        comp_aux_num = ''
        comp_aux_lib = ''
        if compte.est_tiers and ligne.tiers_id:
            comp_aux_num = f'{ligne.tiers_type or "TIERS"}{ligne.tiers_id}'
            comp_aux_lib = ligne.libelle or ecriture.libelle
        total_debit += ligne.debit
        total_credit += ligne.credit
        lignes.append({
            'JournalCode': ecriture.journal.code,
            'JournalLib': ecriture.journal.libelle,
            'EcritureNum': str(ecriture.pk),
            'EcritureDate': _fec_date(ecriture.date_ecriture),
            'CompteNum': compte.numero,
            'CompteLib': compte.intitule,
            'CompAuxNum': comp_aux_num,
            'CompAuxLib': comp_aux_lib,
            'PieceRef': ecriture.reference or str(ecriture.pk),
            'PieceDate': _fec_date(ecriture.date_ecriture),
            'EcritureLib': ligne.libelle or ecriture.libelle,
            'Debit': _fec_montant(ligne.debit),
            'Credit': _fec_montant(ligne.credit),
            'EcritureLet': ligne.lettrage or '',
            'DateLet': '',
            'ValidDate': (
                _fec_date(ecriture.date_creation.date())
                if ecriture.statut == 'validee' and ecriture.date_creation
                else ''),
            'Montantdevise': '',
            'Idevise': '',
        })
    return {
        'exercice': exercice.libelle or str(exercice.pk),
        'date_debut': exercice.date_debut.isoformat(),
        'date_fin': exercice.date_fin.isoformat(),
        'columns': list(FEC_COLUMNS),
        'lignes': lignes,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'equilibre': total_debit == total_credit,
        'nb_lignes': len(lignes),
    }


# ── FG112 / COMPTA22 — Lettrage / encours par tiers ────────────────────────

def lignes_non_lettrees(company, compte):
    """Lignes non lettrées d'un compte lettrable (factures/règlements ouverts).

    Sert au lettrage manuel et au calcul de l'encours exact d'un tiers.
    """
    return list(
        LigneEcriture.objects.filter(
            company=company, compte=compte, lettrage='',
        ).select_related('ecriture').order_by('ecriture__date_ecriture', 'id'))


def encours_tiers(company, compte):
    """Encours (solde non lettré) d'un compte de tiers lettrable.

    Σ(débit) − Σ(crédit) des seules lignes NON lettrées : ce qui reste dû/à
    régler après appariement.
    """
    agg = LigneEcriture.objects.filter(
        company=company, compte=compte, lettrage='',
    ).aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


def lettrer(company, ligne_ids, code):
    """Pose un code de lettrage sur un lot de lignes SSI elles s'équilibrent.

    Renvoie le nombre de lignes lettrées, ou lève ``ValueError`` si le lot ne
    solde pas (Σ débit ≠ Σ crédit) — on ne lettre jamais un appariement bancal.
    """
    qs = LigneEcriture.objects.filter(company=company, id__in=ligne_ids)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    debit = agg['debit'] or Decimal('0')
    credit = agg['credit'] or Decimal('0')
    if debit != credit:
        raise ValueError(
            f"Lettrage impossible : Σ débit ({debit}) ≠ Σ crédit ({credit}).")
    return qs.update(lettrage=code)


def prochain_code_lettrage(company, compte):
    """YLEDG6 — code de lettrage séquentiel A, B, …, Z, AA, AB… pour un
    compte lettrable donné (jamais réutilisé, même après délettrage — le
    prochain code repart toujours après le plus haut déjà vu)."""
    codes = (LigneEcriture.objects
             .filter(company=company, compte=compte)
             .exclude(lettrage='')
             .values_list('lettrage', flat=True).distinct())

    def _rang(code):
        rang = 0
        for ch in code:
            rang = rang * 26 + (ord(ch) - ord('A') + 1)
        return rang

    def _code(rang):
        lettres = ''
        while rang > 0:
            rang, reste = divmod(rang - 1, 26)
            lettres = chr(ord('A') + reste) + lettres
        return lettres

    valides = [c for c in codes if c and c.isalpha() and c.isupper()]
    dernier_rang = max((_rang(c) for c in valides), default=0)
    return _code(dernier_rang + 1)


def delettrer(company, code):
    """YLEDG6 — retire le code de lettrage ``code`` d'un lot de lignes (rouvre
    le lot : la balance âgée / l'encours ré-incluent les lignes). Renvoie le
    nombre de lignes délettrées. Journalisé côté appelant (jamais silencieux)
    — cette fonction, LECTURE-ÉCRITURE ciblée, ne touche jamais aux montants
    ni aux écritures elles-mêmes (COMPTA11 : jamais de suppression/altération
    d'une écriture validée)."""
    qs = LigneEcriture.objects.filter(company=company, lettrage=code)
    return qs.update(lettrage='')


# ── FG113 / COMPTA27 — CPC (Compte de Produits et Charges) ─────────────────

def cpc(company, *, date_debut=None, date_fin=None, validees_seulement=False,
        comparer=False, date_debut_n1=None, date_fin_n1=None):
    """État de résultat (CPC) : produits (classe 7) − charges (classe 6).

    Renvoie ``{'produits', 'total_produits', 'charges', 'total_charges',
    'resultat'}``. Le résultat positif = bénéfice, négatif = perte.

    ZACC2 — ``comparer=True`` ajoute ``montant_n1``/``ecart``/``ecart_pct``
    sur chaque poste (produit et charge) + ``resultat_n1``/``resultat_ecart``
    de tête, calculés sur ``date_debut_n1``/``date_fin_n1`` (défaut : même
    intervalle décalé d'un an). Défaut = réponse actuelle byte-identique.
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__classe__in=[6, 7])
    agg = qs.values(
        'compte__numero', 'compte__intitule', 'compte__classe',
    ).annotate(debit=Sum('debit'), credit=Sum('credit')).order_by(
        'compte__numero')
    produits, charges = [], []
    total_produits = Decimal('0')
    total_charges = Decimal('0')
    for row in agg:
        debit = row['debit'] or Decimal('0')
        credit = row['credit'] or Decimal('0')
        item = {
            'numero': row['compte__numero'],
            'intitule': row['compte__intitule'],
        }
        if row['compte__classe'] == 7:
            # Produit : solde créditeur.
            montant = credit - debit
            item['montant'] = montant
            total_produits += montant
            produits.append(item)
        else:
            # Charge : solde débiteur.
            montant = debit - credit
            item['montant'] = montant
            total_charges += montant
            charges.append(item)
    resultat = {
        'produits': produits,
        'total_produits': total_produits,
        'charges': charges,
        'total_charges': total_charges,
        'resultat': total_produits - total_charges,
    }
    if comparer:
        deb_n1, fin_n1 = _periode_n1(date_debut, date_fin, date_debut_n1,
                                     date_fin_n1)
        n1 = cpc(company, date_debut=deb_n1, date_fin=fin_n1,
                 validees_seulement=validees_seulement)
        n1_produits = {li['numero']: li['montant'] for li in n1['produits']}
        n1_charges = {li['numero']: li['montant'] for li in n1['charges']}
        for item in produits:
            montant_n1 = n1_produits.get(item['numero'], Decimal('0'))
            item['montant_n1'] = montant_n1
            item['ecart'] = item['montant'] - montant_n1
            item['ecart_pct'] = _ecart_pct(item['montant'], montant_n1)
        for item in charges:
            montant_n1 = n1_charges.get(item['numero'], Decimal('0'))
            item['montant_n1'] = montant_n1
            item['ecart'] = item['montant'] - montant_n1
            item['ecart_pct'] = _ecart_pct(item['montant'], montant_n1)
        resultat['resultat_n1'] = n1['resultat']
        resultat['resultat_ecart'] = resultat['resultat'] - n1['resultat']
        resultat['date_debut_n1'] = deb_n1
        resultat['date_fin_n1'] = fin_n1
    return resultat


# ── FG114 / COMPTA28 — Bilan (format CGNC) ─────────────────────────────────

def bilan(company, *, date_fin=None, validees_seulement=False,
          comparer=False, date_fin_n1=None):
    """Bilan : actif (classes 2,3,5) / passif (classes 1,4) depuis les soldes.

    Le résultat de l'exercice (CPC) est porté au passif pour équilibrer
    (équation comptable : Actif = Passif + Résultat). Renvoie
    ``{'actif', 'total_actif', 'passif', 'total_passif', 'resultat',
    'equilibre'}``.

    ZACC2 — ``comparer=True`` ajoute ``montant_n1``/``ecart``/``ecart_pct``
    sur chaque poste d'actif/passif, calculés à ``date_fin_n1`` (défaut :
    ``date_fin`` décalée d'un an). Défaut = réponse actuelle byte-identique.
    """
    qs = _lignes_qs(company, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__classe__in=[1, 2, 3, 4, 5])
    agg = qs.values(
        'compte__numero', 'compte__intitule', 'compte__classe',
    ).annotate(debit=Sum('debit'), credit=Sum('credit')).order_by(
        'compte__numero')
    actif, passif = [], []
    total_actif = Decimal('0')
    total_passif = Decimal('0')
    for row in agg:
        debit = row['debit'] or Decimal('0')
        credit = row['credit'] or Decimal('0')
        solde = debit - credit
        item = {
            'numero': row['compte__numero'],
            'intitule': row['compte__intitule'],
        }
        if row['compte__classe'] in (2, 3, 5):
            item['montant'] = solde
            total_actif += solde
            actif.append(item)
        else:
            item['montant'] = -solde
            total_passif += -solde
            passif.append(item)
    resultat_exercice = cpc(
        company, date_fin=date_fin,
        validees_seulement=validees_seulement)['resultat']
    out = {
        'actif': actif,
        'total_actif': total_actif,
        'passif': passif,
        'total_passif': total_passif,
        'resultat': resultat_exercice,
        'equilibre': total_actif == (total_passif + resultat_exercice),
    }
    if comparer:
        _, fin_n1 = _periode_n1(None, date_fin, None, date_fin_n1)
        n1 = bilan(company, date_fin=fin_n1,
                   validees_seulement=validees_seulement)
        n1_actif = {li['numero']: li['montant'] for li in n1['actif']}
        n1_passif = {li['numero']: li['montant'] for li in n1['passif']}
        for item in actif:
            montant_n1 = n1_actif.get(item['numero'], Decimal('0'))
            item['montant_n1'] = montant_n1
            item['ecart'] = item['montant'] - montant_n1
            item['ecart_pct'] = _ecart_pct(item['montant'], montant_n1)
        for item in passif:
            montant_n1 = n1_passif.get(item['numero'], Decimal('0'))
            item['montant_n1'] = montant_n1
            item['ecart'] = item['montant'] - montant_n1
            item['ecart_pct'] = _ecart_pct(item['montant'], montant_n1)
        out['resultat_n1'] = n1['resultat']
        out['date_fin_n1'] = fin_n1
    return out


# ── COMPTA29 — ESG (état des soldes de gestion) + ETIC ─────────────────────
# Les états de synthèse CGNC ne se limitent pas au bilan + CPC : la liasse exige
# aussi l'ESG (état des soldes de gestion — la cascade des soldes intermédiaires
# marge → valeur ajoutée → EBE → résultat courant → résultat net) et l'ETIC
# (état des informations complémentaires — le paquet de tableaux annexes). On les
# DÉRIVE du grand livre lui-même : aucun recalcul métier ad hoc, aucun import
# cross-app. L'ESG se lit sur les seuls comptes de gestion (classes 6 & 7),
# regroupés par préfixe CGNC ; l'ETIC assemble les tableaux annexes déjà produits
# par les sélecteurs existants (immobilisations/provisions/cautions/engagements),
# bornés au même intervalle — d'où une cohérence 1:1 avec les états standalone.

def _somme_prefixes(company, prefixes, *, sens, date_debut=None,
                    date_fin=None, validees_seulement=False):
    """Solde net d'un ensemble de comptes dont le numéro commence par un préfixe.

    ``prefixes`` : itérable de préfixes de numéros (ex. ``('711', '712')``).
    ``sens`` = ``'produit'`` (crédit − débit) ou ``'charge'`` (débit − crédit).
    Lecture seule, scopée société, bornée à l'intervalle demandé. Renvoie un
    ``Decimal`` (0 si aucun compte concerné).
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement)
    filtre = Q()
    for prefixe in prefixes:
        filtre |= Q(compte__numero__startswith=prefixe)
    agg = qs.filter(filtre).aggregate(debit=Sum('debit'), credit=Sum('credit'))
    debit = agg['debit'] or Decimal('0')
    credit = agg['credit'] or Decimal('0')
    return (credit - debit) if sens == 'produit' else (debit - credit)


def esg(company, *, date_debut=None, date_fin=None, validees_seulement=False,
        comparer=False, date_debut_n1=None, date_fin_n1=None):
    """État des soldes de gestion (ESG / SIG) au format CGNC marocain.

    Cascade des soldes intermédiaires de gestion, chacun déduit des soldes de
    comptes de gestion (classes 6 & 7) regroupés par préfixe CGNC :

      * marge brute sur ventes en l'état = ventes de marchandises (711) −
        achats revendus de marchandises (611) ;
      * production de l'exercice = ventes de biens & services produits (712) ;
      * valeur ajoutée = marge brute + production − consommations (612/613/614) ;
      * excédent brut d'exploitation (EBE) = valeur ajoutée − charges de
        personnel (617) − impôts & taxes (616) ;
      * résultat d'exploitation = EBE + autres produits d'expl. (718) − autres
        charges d'expl. (618) − dotations d'exploitation (619) ;
      * résultat financier = produits financiers (73) − charges financières (63) ;
      * résultat courant = résultat d'exploitation + résultat financier ;
      * résultat non courant = produits non courants (75) − charges non
        courantes (65) ;
      * résultat avant impôts = résultat courant + résultat non courant ;
      * résultat net = résultat avant impôts − impôts sur les résultats (67).

    Renvoie ``{'soldes': [{'code', 'libelle', 'montant'} …], 'resultat_net'}``.
    Lecture seule ; aucun état n'est persisté.

    ZACC2 — ``comparer=True`` ajoute ``montant_n1``/``ecart``/``ecart_pct``
    sur chaque solde + ``resultat_net_n1``, calculés sur ``date_debut_n1``/
    ``date_fin_n1`` (défaut : même intervalle décalé d'un an). Défaut =
    réponse actuelle byte-identique.
    """
    def prod(*prefixes):
        return _somme_prefixes(
            company, prefixes, sens='produit', date_debut=date_debut,
            date_fin=date_fin, validees_seulement=validees_seulement)

    def charge(*prefixes):
        return _somme_prefixes(
            company, prefixes, sens='charge', date_debut=date_debut,
            date_fin=date_fin, validees_seulement=validees_seulement)

    ventes_marchandises = prod('711')
    achats_revendus = charge('611')
    marge_brute = ventes_marchandises - achats_revendus
    production = prod('712')
    consommations = charge('612', '613', '614')
    valeur_ajoutee = marge_brute + production - consommations
    charges_personnel = charge('617')
    impots_taxes = charge('616')
    ebe = valeur_ajoutee - charges_personnel - impots_taxes
    autres_prod_expl = prod('718')
    autres_charges_expl = charge('618')
    dotations_expl = charge('619')
    resultat_exploitation = (
        ebe + autres_prod_expl - autres_charges_expl - dotations_expl)
    resultat_financier = prod('73') - charge('63')
    resultat_courant = resultat_exploitation + resultat_financier
    resultat_non_courant = prod('75') - charge('65')
    resultat_avant_impots = resultat_courant + resultat_non_courant
    impots_resultats = charge('67')
    resultat_net = resultat_avant_impots - impots_resultats
    soldes = [
        {'code': 'MARGE', 'libelle': 'Marge brute sur ventes en l’état',
         'montant': marge_brute},
        {'code': 'PROD', 'libelle': 'Production de l’exercice',
         'montant': production},
        {'code': 'VA', 'libelle': 'Valeur ajoutée', 'montant': valeur_ajoutee},
        {'code': 'EBE', 'libelle': 'Excédent brut d’exploitation',
         'montant': ebe},
        {'code': 'REXPL', 'libelle': 'Résultat d’exploitation',
         'montant': resultat_exploitation},
        {'code': 'RFIN', 'libelle': 'Résultat financier',
         'montant': resultat_financier},
        {'code': 'RCOUR', 'libelle': 'Résultat courant',
         'montant': resultat_courant},
        {'code': 'RNC', 'libelle': 'Résultat non courant',
         'montant': resultat_non_courant},
        {'code': 'RAI', 'libelle': 'Résultat avant impôts',
         'montant': resultat_avant_impots},
        {'code': 'RN', 'libelle': 'Résultat net de l’exercice',
         'montant': resultat_net},
    ]
    out = {'soldes': soldes, 'resultat_net': resultat_net}
    if comparer:
        deb_n1, fin_n1 = _periode_n1(date_debut, date_fin, date_debut_n1,
                                     date_fin_n1)
        n1 = esg(company, date_debut=deb_n1, date_fin=fin_n1,
                 validees_seulement=validees_seulement)
        n1_soldes = {s['code']: s['montant'] for s in n1['soldes']}
        for solde in soldes:
            montant_n1 = n1_soldes.get(solde['code'], Decimal('0'))
            solde['montant_n1'] = montant_n1
            solde['ecart'] = solde['montant'] - montant_n1
            solde['ecart_pct'] = _ecart_pct(solde['montant'], montant_n1)
        out['resultat_net_n1'] = n1['resultat_net']
        out['date_debut_n1'] = deb_n1
        out['date_fin_n1'] = fin_n1
    return out


# Sections normalisées de l'ETIC (ordre figé du paquet d'informations
# complémentaires destiné au fiduciaire / à la DGI).
ETIC_SECTIONS = (
    'principes_methodes',
    'immobilisations',
    'provisions',
    'engagements_hors_bilan',
    'resultat',
)


def etic(company, exercice, *, validees_seulement=False):
    """ETIC — état des informations complémentaires (paquet annexe CGNC).

    Assemble — SANS rien recalculer — les tableaux annexes déjà produits par les
    sélecteurs existants, tous bornés à l'exercice :

      * ``immobilisations`` — soldes des comptes de classe 2 (immobilisations
        brutes) via ``comptes_par_classe`` + leur solde ;
      * ``provisions`` — provisions pour créances douteuses ouvertes ;
      * ``engagements_hors_bilan`` — cautions bancaires & retenues de garantie
        non encore libérées (engagements donnés) ;
      * ``resultat`` — CPC de l'exercice (rappel de tête) ;
      * ``principes_methodes`` — mention normalisée (méthode CGNC, coût
        historique) ; texte fixe, aucune donnée société recopiée.

    Lecture seule, scopée société ; aucune écriture n'est créée. Renvoie
    ``{'exercice', 'date_debut', 'date_fin', 'sections', 'principes_methodes',
    'immobilisations', 'provisions', 'engagements_hors_bilan', 'resultat'}``.
    """
    from .models import ProvisionCreance, CautionBancaire, RetenueGarantie
    date_debut = exercice.date_debut
    date_fin = exercice.date_fin
    # Immobilisations brutes : soldes des comptes de classe 2 à la clôture.
    immos = []
    for compte in comptes_par_classe(company, 2):
        solde = solde_compte(
            company, compte, date_fin=date_fin,
            validees_seulement=validees_seulement)
        if solde:
            immos.append({
                'numero': compte.numero, 'intitule': compte.intitule,
                'valeur_brute': solde})
    provisions = [
        {'tiers_type': p.tiers_type, 'tiers_id': p.tiers_id,
         'base': p.base, 'dotation': p.dotation, 'taux': p.taux,
         'statut': p.statut}
        for p in ProvisionCreance.objects.filter(company=company)
    ]
    cautions = [
        {'reference': c.reference, 'montant': c.montant, 'statut': c.statut}
        for c in CautionBancaire.objects.filter(company=company)
    ]
    retenues = [
        {'reference': r.reference, 'montant': r.montant, 'statut': r.statut}
        for r in RetenueGarantie.objects.filter(company=company)
    ]
    etat_cpc = cpc(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement)
    return {
        'exercice': exercice.libelle or str(exercice.pk),
        'date_debut': date_debut.isoformat(),
        'date_fin': date_fin.isoformat(),
        'sections': list(ETIC_SECTIONS),
        'principes_methodes': (
            'États établis selon le CGNC (coût historique). Continuité '
            'd’exploitation, permanence des méthodes, clarté et spécialisation '
            'des exercices.'),
        'immobilisations': immos,
        'provisions': provisions,
        'engagements_hors_bilan': {
            'cautions_bancaires': cautions,
            'retenues_garantie': retenues,
        },
        'resultat': etat_cpc,
    }


# ── FG121 — Position de trésorerie depuis le grand livre ───────────────────

def solde_compte(company, compte, *, date_fin=None, validees_seulement=False):
    """Solde (débit − crédit) d'un compte à une date donnée."""
    qs = _lignes_qs(company, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(compte=compte)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


def comptes_par_classe(company, classe):
    """Comptes d'une classe donnée (lecture seule, scopé société)."""
    return list(CompteComptable.objects.filter(
        company=company, classe=classe).order_by('numero'))


# ── ZACC3 — Tableau de financement / des flux de trésorerie CGNC (méthode
# indirecte) ─────────────────────────────────────────────────────────────
# 5e état CGNC (standard Odoo « Cash Flow Statement »), jamais couvert avant :
# la position (FG122) donne un solde instantané, le prévisionnel (FG126) une
# projection roulante éditable — ni l'un ni l'autre ne réconcilie le résultat
# de l'exercice à la variation RÉELLE de trésorerie sur la période. On dérive
# tout du grand livre (AUCUN import cross-app, AUCUN recalcul hors GL) :
#
#   * capacité d'autofinancement (CAF) = résultat net (ESG) + dotations aux
#     amortissements/provisions (charges 619/659 — non décaissées) − reprises
#     (produits 719/759 — non encaissées) ;
#   * variation du BFR = variation NETTE des soldes des comptes de tiers/stock
#     d'exploitation (classes 3 hors trésorerie 51/54, et 4 hors emprunts
#     1481/1671) entre l'ouverture et la clôture — une hausse de créances/
#     stock CONSOMME de la trésorerie (flux négatif), une hausse de dettes en
#     LIBÈRE (flux positif) ;
#   * flux d'investissement = variation NETTE des comptes d'immobilisations
#     (classe 2) entre ouverture et clôture, signe inversé (une acquisition
#     consomme de la trésorerie) ;
#   * flux de financement = variation NETTE des comptes d'emprunts (1481,
#     1671) + capital (111x) entre ouverture et clôture.
#
# Somme des 3 flux = variation nette de trésorerie, réconciliée avec la
# position FG122 ouverture → clôture (comptes 51xx/54xx).

_COMPTES_FINANCEMENT = ('1481', '1671', '1111', '1117')


def _solde_classe(company, classe, *, date_fin=None, validees_seulement=False,
                  exclure_prefixes=()):
    """Solde net (débit − crédit) de TOUS les comptes d'une classe à une date,
    en excluant les comptes dont le numéro commence par un préfixe exclu."""
    qs = _lignes_qs(company, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__classe=classe)
    for prefixe in exclure_prefixes:
        qs = qs.exclude(compte__numero__startswith=prefixe)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


def tableau_flux_tresorerie(company, exercice, *, validees_seulement=False):
    """Tableau de financement / des flux de trésorerie CGNC — méthode
    indirecte (ZACC3).

    Trois sections (exploitation / investissement / financement) dont la
    somme réconcilie EXACTEMENT la variation nette de trésorerie de
    l'exercice (position FG122 ouverture → clôture). Lecture seule, scopée
    société ; aucune écriture n'est créée. Renvoie ``{'exercice',
    'date_debut', 'date_fin', 'exploitation': {...}, 'investissement': {...},
    'financement': {...}, 'variation_nette_tresorerie',
    'tresorerie_ouverture', 'tresorerie_cloture', 'reconciliee'}``.
    """
    date_debut = exercice.date_debut
    date_fin = exercice.date_fin
    date_ouverture = date_debut - timedelta(days=1)

    # ── Exploitation : CAF ± variation du BFR ──
    resultat_exercice = cpc(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement)['resultat']
    dotations = _somme_prefixes(
        company, ('619', '659'), sens='charge', date_debut=date_debut,
        date_fin=date_fin, validees_seulement=validees_seulement)
    reprises = _somme_prefixes(
        company, ('719', '759'), sens='produit', date_debut=date_debut,
        date_fin=date_fin, validees_seulement=validees_seulement)
    caf = resultat_exercice + dotations - reprises

    # Classe 3 (actif circulant) est déjà HORS trésorerie dans le plan CGNC
    # (la trésorerie est en classe 5) ; classe 4 (passif circulant) exclut
    # par précaution les comptes de financement (au cas où un compte 1481/
    # 1671 serait mal classé) — sans effet dans le plan seedé standard.
    bfr_ouverture = (
        _solde_classe(company, 3, date_fin=date_ouverture,
                      validees_seulement=validees_seulement)
        - _solde_classe(company, 4, date_fin=date_ouverture,
                        validees_seulement=validees_seulement,
                        exclure_prefixes=_COMPTES_FINANCEMENT))
    bfr_cloture = (
        _solde_classe(company, 3, date_fin=date_fin,
                      validees_seulement=validees_seulement)
        - _solde_classe(company, 4, date_fin=date_fin,
                        validees_seulement=validees_seulement,
                        exclure_prefixes=_COMPTES_FINANCEMENT))
    variation_bfr = bfr_cloture - bfr_ouverture
    # Une hausse du BFR (plus de créances/stock net des dettes) CONSOME de la
    # trésorerie : flux négatif.
    flux_exploitation = caf - variation_bfr

    # ── Investissement : variation des immobilisations (classe 2) ──
    immo_ouverture = _solde_classe(
        company, 2, date_fin=date_ouverture,
        validees_seulement=validees_seulement)
    immo_cloture = _solde_classe(
        company, 2, date_fin=date_fin,
        validees_seulement=validees_seulement)
    # Une hausse du solde des immobilisations (acquisition nette) CONSOMME de
    # la trésorerie : flux négatif (signe inversé de la variation).
    flux_investissement = -(immo_cloture - immo_ouverture)

    # ── Financement : variation des emprunts + capital ──
    fin_ouverture = _solde_groupe(
        company, _COMPTES_FINANCEMENT, date_fin=date_ouverture,
        validees_seulement=validees_seulement)
    fin_cloture = _solde_groupe(
        company, _COMPTES_FINANCEMENT, date_fin=date_fin,
        validees_seulement=validees_seulement)
    # Ces comptes sont au PASSIF (soldes créditeurs négatifs en débit-crédit) :
    # une hausse de l'encours (nouvel emprunt/apport) LIBÈRE de la trésorerie,
    # d'où le signe inversé (même convention que le bilan : passif = -solde).
    flux_financement = -(fin_cloture - fin_ouverture)

    variation_nette = (
        flux_exploitation + flux_investissement + flux_financement)

    tresorerie_ouverture = _solde_classe(
        company, 5, date_fin=date_ouverture,
        validees_seulement=validees_seulement)
    tresorerie_cloture = _solde_classe(
        company, 5, date_fin=date_fin, validees_seulement=validees_seulement)

    return {
        'exercice': exercice.libelle or str(exercice.pk),
        'date_debut': date_debut.isoformat(),
        'date_fin': date_fin.isoformat(),
        'exploitation': {
            'resultat_net': resultat_exercice,
            'dotations': dotations,
            'reprises': reprises,
            'capacite_autofinancement': caf,
            'variation_bfr': variation_bfr,
            'flux_net': flux_exploitation,
        },
        'investissement': {
            'immobilisations_ouverture': immo_ouverture,
            'immobilisations_cloture': immo_cloture,
            'flux_net': flux_investissement,
        },
        'financement': {
            'financement_ouverture': fin_ouverture,
            'financement_cloture': fin_cloture,
            'flux_net': flux_financement,
        },
        'variation_nette_tresorerie': variation_nette,
        'tresorerie_ouverture': tresorerie_ouverture,
        'tresorerie_cloture': tresorerie_cloture,
        'reconciliee': (
            tresorerie_ouverture + variation_nette == tresorerie_cloture),
    }


# ── ZACC12 — Rapport des immobilisations (tableau CGNC B2/B2bis) ──────────
# Aucun sélecteur d'ÉTAT récapitulatif des immobilisations n'existait (seul un
# registre `Immobilisation` + un plan d'amortissement par immo). Ce sélecteur
# assemble, PAR IMMOBILISATION, le tableau CGNC B2 (immobilisations : valeur
# brute ouverture/acquisitions/cessions/clôture) et B2bis (amortissements :
# cumul ouverture/dotations de l'exercice/reprises sur cessions/cumul
# clôture) + la VNC — sans rien recalculer (relit `Immobilisation`,
# `DotationAmortissement`, `CessionImmobilisation` déjà postés).

def tableau_immobilisations(company, exercice, *, validees_seulement=False):
    """Tableau des immobilisations & amortissements pour la liasse/l'annexe
    (ZACC12 — tableaux CGNC B2/B2bis).

    Par immobilisation : valeur brute à l'ouverture (coût si acquise avant
    l'exercice, sinon 0), acquisitions de l'exercice, cessions de l'exercice
    (valeur brute sortie), valeur brute à la clôture, cumul d'amortissement à
    l'ouverture, dotations de l'exercice (postées), reprises sur cessions de
    l'exercice, cumul à la clôture, VNC. Une immobilisation cédée AVANT
    l'exercice n'apparaît pas (déjà sortie du patrimoine). Lecture seule,
    scopée société ; aucune écriture n'est créée. Renvoie ``{'exercice',
    'date_debut', 'date_fin', 'lignes': [...], 'totaux': {...}}``.
    """
    date_debut = exercice.date_debut
    date_fin = exercice.date_fin
    lignes = []
    total_brut_ouverture = Decimal('0')
    total_acquisitions = Decimal('0')
    total_cessions_brut = Decimal('0')
    total_brut_cloture = Decimal('0')
    total_amort_ouverture = Decimal('0')
    total_dotations = Decimal('0')
    total_reprises = Decimal('0')
    total_amort_cloture = Decimal('0')
    total_vnc = Decimal('0')

    immos = (Immobilisation.objects.filter(company=company)
             .filter(Q(date_acquisition__lte=date_fin))
             .order_by('date_acquisition', 'id'))
    for immo in immos:
        cession = CessionImmobilisation.objects.filter(
            company=company, immobilisation=immo,
            date_cession__lt=date_debut).first()
        if cession is not None:
            continue  # sortie du patrimoine AVANT l'exercice : omise.

        cout = immo.cout or Decimal('0')
        cession_exercice = CessionImmobilisation.objects.filter(
            company=company, immobilisation=immo,
            date_cession__gte=date_debut,
            date_cession__lte=date_fin).first()

        acquis_avant = immo.date_acquisition < date_debut
        brut_ouverture = cout if acquis_avant else Decimal('0')
        acquisitions = Decimal('0') if acquis_avant else cout
        cessions_brut = cout if cession_exercice is not None else Decimal('0')
        brut_cloture = brut_ouverture + acquisitions - cessions_brut

        plan = getattr(immo, 'plan_amortissement', None)
        dotations_qs = (
            DotationAmortissement.objects.filter(
                company=company, plan=plan, posted=True)
            if plan is not None else DotationAmortissement.objects.none())
        if validees_seulement:
            dotations_qs = dotations_qs.filter(
                ecriture__statut=EcritureComptable.Statut.VALIDEE)
        amort_ouverture = Decimal('0')
        if plan is not None:
            cumul_avant = (
                dotations_qs.filter(date_dotation__lt=date_debut)
                .order_by('-date_dotation', '-id').values_list(
                    'cumul', flat=True).first())
            amort_ouverture = cumul_avant or Decimal('0')
        dotations_exercice = (
            dotations_qs.filter(
                date_dotation__gte=date_debut, date_dotation__lte=date_fin,
            ).aggregate(total=Sum('montant'))['total'] or Decimal('0'))
        reprises = (
            cession_exercice.amortissements_cumules
            if cession_exercice is not None else Decimal('0'))
        amort_cloture = amort_ouverture + dotations_exercice - reprises
        vnc = brut_cloture - amort_cloture

        lignes.append({
            'immobilisation_id': immo.id,
            'reference': immo.reference,
            'libelle': immo.libelle,
            'categorie': immo.categorie,
            'brut_ouverture': brut_ouverture,
            'acquisitions': acquisitions,
            'cessions': cessions_brut,
            'brut_cloture': brut_cloture,
            'amort_ouverture': amort_ouverture,
            'dotations': dotations_exercice,
            'reprises': reprises,
            'amort_cloture': amort_cloture,
            'valeur_nette_comptable': vnc,
        })
        total_brut_ouverture += brut_ouverture
        total_acquisitions += acquisitions
        total_cessions_brut += cessions_brut
        total_brut_cloture += brut_cloture
        total_amort_ouverture += amort_ouverture
        total_dotations += dotations_exercice
        total_reprises += reprises
        total_amort_cloture += amort_cloture
        total_vnc += vnc

    return {
        'exercice': exercice.libelle or str(exercice.pk),
        'date_debut': date_debut.isoformat(),
        'date_fin': date_fin.isoformat(),
        'lignes': lignes,
        'totaux': {
            'brut_ouverture': total_brut_ouverture,
            'acquisitions': total_acquisitions,
            'cessions': total_cessions_brut,
            'brut_cloture': total_brut_cloture,
            'amort_ouverture': total_amort_ouverture,
            'dotations': total_dotations,
            'reprises': total_reprises,
            'amort_cloture': total_amort_cloture,
            'valeur_nette_comptable': total_vnc,
        },
    }


# ── FG122 — Position de trésorerie consolidée + projection nette ───────────

# Comptes CGNC dont les soldes alimentent la projection nette. Tout se déduit du
# grand livre de la compta elle-même (AUCUN import cross-app) : la facturation
# client/fournisseur, la paie et les impôts laissent leur trace sur ces comptes.
_COMPTE_CLIENTS = '3421'        # Clients — créances (AR), solde débiteur.
_COMPTE_FOURNISSEURS = '4411'   # Fournisseurs — dettes (AP), solde créditeur.
_COMPTES_TVA_DUE = ('4455', '44552')          # TVA collectée à reverser (passif).
_COMPTES_TVA_RECUP = ('3455', '34552')        # TVA récupérable (actif).
_COMPTES_PAIE = ('4432', '4441', '4443')      # Rémunérations/organismes/État dus.


def _solde_numero(company, numero, *, date_fin=None, validees_seulement=False):
    """Solde (débit − crédit) d'un compte par son numéro, 0 si compte absent."""
    compte = CompteComptable.objects.filter(
        company=company, numero=numero).first()
    if compte is None:
        return Decimal('0')
    return solde_compte(
        company, compte, date_fin=date_fin,
        validees_seulement=validees_seulement)


def _solde_groupe(company, numeros, *, date_fin=None, validees_seulement=False):
    """Solde net (Σ débit − Σ crédit) d'un groupe de comptes (par numéros)."""
    qs = _lignes_qs(company, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__numero__in=numeros)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0')) - (agg['credit'] or Decimal('0'))


def position_tresorerie(company, *, date_fin=None, validees_seulement=False):
    """Position de trésorerie consolidée : solde par compte/caisse + total.

    Pour chaque ``CompteTresorerie`` actif de la société, le solde courant =
    ``solde_initial`` + mouvements du grand livre sur son compte comptable
    (classe 5). Renvoie ``{'comptes': [...], 'total': Decimal,
    'encours_emprunts': Decimal}`` où chaque entrée de ``comptes`` porte
    ``{'id', 'libelle', 'type_compte', 'banque', 'devise', 'solde_initial',
    'mouvements', 'solde'}``. ``encours_emprunts`` (XACC14) est le capital
    restant dû cumulé de TOUS les emprunts/leasings de la société — ajouté en
    lecture seule, n'affecte pas ``total``. Lecture seule, scopée société.
    """
    comptes = []
    total = Decimal('0')
    treso_qs = CompteTresorerie.objects.filter(
        company=company, actif=True).select_related('compte_comptable').order_by(
        'type_compte', 'libelle')
    for treso in treso_qs:
        mouvements = solde_compte(
            company, treso.compte_comptable, date_fin=date_fin,
            validees_seulement=validees_seulement)
        solde = (treso.solde_initial or Decimal('0')) + mouvements
        total += solde
        comptes.append({
            'id': treso.id,
            'libelle': treso.libelle,
            'type_compte': treso.type_compte,
            'banque': treso.banque,
            'devise': treso.devise,
            'solde_initial': treso.solde_initial or Decimal('0'),
            'mouvements': mouvements,
            'solde': solde,
        })
    encours_emprunts = sum(
        (e.encours_restant_du for e in Emprunt.objects.filter(company=company)),
        Decimal('0'))
    return {'comptes': comptes, 'total': total, 'encours_emprunts': encours_emprunts}


def comptes_sous_seuil(company, *, date_fin=None):
    """NTTRE8 — Comptes de trésorerie dont le solde courant est sous un seuil.

    Pour chaque ``CompteTresorerie`` actif portant un ``seuil_alerte_bas`` ou un
    ``seuil_alerte_decouvert``, compare le solde courant (solde_initial +
    mouvements GL, comme ``position_tresorerie``). Renvoie la liste des comptes
    en alerte : ``[{'id', 'libelle', 'solde', 'seuil_alerte_bas',
    'seuil_alerte_decouvert', 'sous_bas', 'sous_decouvert'}]``. Lecture seule,
    scopée société.
    """
    resultat = []
    treso_qs = CompteTresorerie.objects.filter(
        company=company, actif=True).select_related('compte_comptable')
    for treso in treso_qs:
        seuil_bas = treso.seuil_alerte_bas
        seuil_dec = treso.seuil_alerte_decouvert
        if seuil_bas is None and seuil_dec is None:
            continue
        solde = (treso.solde_initial or Decimal('0')) + solde_compte(
            company, treso.compte_comptable, date_fin=date_fin)
        sous_bas = seuil_bas is not None and solde < seuil_bas
        sous_dec = seuil_dec is not None and solde < seuil_dec
        if sous_bas or sous_dec:
            resultat.append({
                'id': treso.id,
                'libelle': treso.libelle,
                'solde': solde,
                'seuil_alerte_bas': seuil_bas,
                'seuil_alerte_decouvert': seuil_dec,
                'sous_bas': sous_bas,
                'sous_decouvert': sous_dec,
            })
    return resultat


def projection_tresorerie(company, *, date_fin=None, validees_seulement=False):
    """Projection nette de trésorerie : position actuelle ± AR/AP/paie/impôts.

    Estimation pragmatique tirée des seuls soldes du grand livre de la compta
    (aucun import cross-app) : la trésorerie consolidée actuelle, augmentée des
    créances clients ouvertes (3421, débit) à encaisser, diminuée des dettes
    fournisseurs (4411, crédit), des dettes de paie & organismes sociaux/fiscaux
    (44xx) et de la TVA nette due (TVA collectée − TVA récupérable). Renvoie
    ``{'tresorerie_actuelle', 'creances_clients', 'dettes_fournisseurs',
    'dettes_paie', 'tva_nette', 'projection_nette'}``. Lecture seule, scopée
    société. C'est une PROJECTION indicative, pas une écriture.
    """
    position = position_tresorerie(
        company, date_fin=date_fin, validees_seulement=validees_seulement)
    tresorerie = position['total']

    # AR : solde débiteur du compte clients (positif = à encaisser).
    solde_clients = _solde_numero(
        company, _COMPTE_CLIENTS, date_fin=date_fin,
        validees_seulement=validees_seulement)
    creances = solde_clients if solde_clients > 0 else Decimal('0')

    # AP : solde créditeur du compte fournisseurs (positif = à payer).
    solde_fournisseurs = _solde_groupe(
        company, [_COMPTE_FOURNISSEURS], date_fin=date_fin,
        validees_seulement=validees_seulement)
    dettes_fourn = -solde_fournisseurs if solde_fournisseurs < 0 else Decimal('0')

    # Paie & organismes : soldes créditeurs (dettes) sur les comptes 44xx.
    solde_paie = _solde_groupe(
        company, _COMPTES_PAIE, date_fin=date_fin,
        validees_seulement=validees_seulement)
    dettes_paie = -solde_paie if solde_paie < 0 else Decimal('0')

    # TVA nette due = TVA collectée (passif) − TVA récupérable (actif).
    tva_due = _solde_groupe(
        company, _COMPTES_TVA_DUE, date_fin=date_fin,
        validees_seulement=validees_seulement)
    tva_recup = _solde_groupe(
        company, _COMPTES_TVA_RECUP, date_fin=date_fin,
        validees_seulement=validees_seulement)
    # TVA due : passif → solde créditeur (négatif) ; on prend sa valeur absolue.
    tva_collectee = -tva_due if tva_due < 0 else Decimal('0')
    # TVA récupérable : actif → solde débiteur (positif).
    tva_recuperable = tva_recup if tva_recup > 0 else Decimal('0')
    tva_nette = tva_collectee - tva_recuperable
    if tva_nette < 0:
        tva_nette = Decimal('0')

    projection = tresorerie + creances - dettes_fourn - dettes_paie - tva_nette
    return {
        'tresorerie_actuelle': tresorerie,
        'creances_clients': creances,
        'dettes_fournisseurs': dettes_fourn,
        'dettes_paie': dettes_paie,
        'tva_nette': tva_nette,
        'projection_nette': projection,
    }


# ── FG123 — Rapprochement bancaire (relevé ↔ écritures) ────────────────────

def solde_gl_compte_tresorerie(rapprochement):
    """Solde GL d'un compte de trésorerie à la fin de la période rapprochée.

    ``solde_initial`` du ``CompteTresorerie`` + mouvements du grand livre sur son
    compte comptable (classe 5) jusqu'à ``date_fin`` du rapprochement. Lecture
    seule, scopée société.
    """
    treso = rapprochement.compte_tresorerie
    mouvements = solde_compte(
        rapprochement.company, treso.compte_comptable,
        date_fin=rapprochement.date_fin)
    return (treso.solde_initial or Decimal('0')) + mouvements


def lignes_gl_pointables(rapprochement):
    """Lignes du grand livre du compte de trésorerie sur la période (FG123).

    Restitue les ``LigneEcriture`` du compte comptable (classe 5) du compte de
    trésorerie dont l'écriture tombe dans ``[date_debut ; date_fin]``, avec un
    drapeau ``pointee`` indiquant si la ligne est déjà appariée dans CE
    rapprochement. Sert à présenter le côté GL face au relevé. Lecture seule.
    """
    from .models import LigneReleve

    treso = rapprochement.compte_tresorerie
    qs = LigneEcriture.objects.filter(
        company=rapprochement.company,
        compte=treso.compte_comptable,
        ecriture__date_ecriture__gte=rapprochement.date_debut,
        ecriture__date_ecriture__lte=rapprochement.date_fin,
    ).select_related('ecriture', 'ecriture__journal').order_by(
        'ecriture__date_ecriture', 'id')
    # IDs des lignes GL déjà pointées dans ce rapprochement.
    pointees = set(
        LigneReleve.objects.filter(rapprochement=rapprochement).values_list(
            'lignes_gl__id', flat=True))
    resultat = []
    for ligne in qs:
        resultat.append({
            'id': ligne.id,
            'date': ligne.ecriture.date_ecriture,
            'journal': ligne.ecriture.journal.code,
            'reference': ligne.ecriture.reference,
            'libelle': ligne.libelle or ligne.ecriture.libelle,
            'debit': ligne.debit,
            'credit': ligne.credit,
            'montant': (ligne.debit or Decimal('0')) - (
                ligne.credit or Decimal('0')),
            'pointee': ligne.id in pointees,
        })
    return resultat


# ── XACC3 — Auto-suggestion de rapprochement bancaire ──────────────────────

# Fenêtre de date par défaut pour un candidat « date proche » (± N jours).
SUGGESTION_FENETRE_JOURS = 5


def _score_candidat(ligne_releve, ligne_gl):
    """Score de confiance d'un appariement candidat (0-100, plus haut = mieux).

    Cumule des indices INDÉPENDANTS (chacun additionne des points) : montant
    exact (poids fort), date proche (± ``SUGGESTION_FENETRE_JOURS`` jours),
    référence/numéro de pièce présent dans le libellé du relevé, tiers déjà
    renseigné sur la ligne GL. Lecture seule, ne modifie rien.
    """
    score = 0
    montant_gl = (ligne_gl.debit or Decimal('0')) - (ligne_gl.credit or Decimal('0'))
    if montant_gl == ligne_releve.montant:
        score += 60
    ecart_jours = abs((ligne_releve.date_operation
                       - ligne_gl.ecriture.date_ecriture).days)
    if ecart_jours == 0:
        score += 20
    elif ecart_jours <= SUGGESTION_FENETRE_JOURS:
        score += 10
    ref_piece = (ligne_gl.ecriture.reference or '').strip()
    libelle_releve = (ligne_releve.libelle or '') + ' ' + (
        ligne_releve.reference or '')
    if ref_piece and ref_piece.lower() in libelle_releve.lower():
        score += 15
    if ligne_gl.tiers_id:
        score += 5
    return score


def suggestions_rapprochement(rapprochement):
    """Suggère les appariements ligne de relevé ↔ ligne GL les plus probables.

    Pour chaque ligne de relevé NON encore pointée dans CE rapprochement,
    cherche les lignes GL pointables (même compte de trésorerie, période)
    candidates : montant exact, date à ± ``SUGGESTION_FENETRE_JOURS`` jours,
    référence dans le libellé, tiers connu — chacune notée par
    ``_score_candidat``. Renvoie une liste ``[{'ligne_releve_id', 'candidats':
    [{'ligne_gl_id', 'score', ...}, ...], 'ambigue'}]`` triée par
    ``ligne_releve.date_operation``. ``candidats`` est trié par score
    décroissant (la meilleure suggestion en tête). ``ambigue`` est vrai quand ≥2
    candidats partagent le MEILLEUR score (montant identique, p. ex. deux
    factures au même montant) — CES lignes ne doivent jamais être
    auto-acceptées. Lecture seule, ne pointe rien.
    """
    from .models import LigneReleve

    treso = rapprochement.compte_tresorerie
    lignes_gl = list(LigneEcriture.objects.filter(
        company=rapprochement.company,
        compte=treso.compte_comptable,
        ecriture__date_ecriture__gte=rapprochement.date_debut
        - timedelta(days=SUGGESTION_FENETRE_JOURS),
        ecriture__date_ecriture__lte=rapprochement.date_fin
        + timedelta(days=SUGGESTION_FENETRE_JOURS),
    ).select_related('ecriture', 'ecriture__journal'))
    deja_pointees = set(
        LigneReleve.objects.filter(rapprochement=rapprochement).values_list(
            'lignes_gl__id', flat=True))
    lignes_releve = rapprochement.lignes_releve.filter(
        statut=LigneReleve.Statut.NON_POINTEE).order_by('date_operation', 'id')
    resultat = []
    for lr in lignes_releve:
        candidats = []
        for gl in lignes_gl:
            if gl.id in deja_pointees:
                continue
            montant_gl = (gl.debit or Decimal('0')) - (gl.credit or Decimal('0'))
            ecart_jours = abs((lr.date_operation - gl.ecriture.date_ecriture).days)
            if montant_gl != lr.montant and ecart_jours > SUGGESTION_FENETRE_JOURS:
                continue  # ni le montant ni la date ne concordent : pas candidat.
            score = _score_candidat(lr, gl)
            if score <= 0:
                continue
            candidats.append({
                'ligne_gl_id': gl.id,
                'score': score,
                'montant': montant_gl,
                'date': gl.ecriture.date_ecriture,
                'reference': gl.ecriture.reference,
                'libelle': gl.libelle or gl.ecriture.libelle,
            })
        candidats.sort(key=lambda c: c['score'], reverse=True)
        ambigue = (len(candidats) >= 2
                   and candidats[0]['score'] == candidats[1]['score'])
        resultat.append({
            'ligne_releve_id': lr.id,
            'date_operation': lr.date_operation,
            'libelle': lr.libelle,
            'montant': lr.montant,
            'candidats': candidats,
            'ambigue': ambigue,
        })
    return resultat


def resume_rapprochement(rapprochement):
    """Synthèse d'un rapprochement : solde relevé vs solde GL vs écart (FG123).

    Renvoie ``{'solde_releve', 'solde_gl', 'ecart', 'lignes_total',
    'lignes_pointees', 'lignes_non_pointees', 'montant_pointe',
    'montant_non_pointe', 'statut', 'rapproche'}``. Le ``solde_gl`` se déduit du
    grand livre, l'``ecart`` global = solde relevé − solde GL ; ``rapproche`` est
    vrai quand chaque ligne de relevé est concordante (écart nul) et que l'écart
    global est nul. Lecture seule, scopée société.
    """
    lignes = list(
        rapprochement.lignes_releve.all().prefetch_related('lignes_gl'))
    solde_gl = solde_gl_compte_tresorerie(rapprochement)
    solde_releve = rapprochement.solde_releve or Decimal('0')
    montant_pointe = Decimal('0')
    montant_non_pointe = Decimal('0')
    lignes_pointees = 0
    lignes_non_pointees = 0
    toutes_concordantes = True
    for ligne in lignes:
        if ligne.est_concordante:
            lignes_pointees += 1
            montant_pointe += ligne.montant or Decimal('0')
        else:
            lignes_non_pointees += 1
            montant_non_pointe += ligne.montant or Decimal('0')
            toutes_concordantes = False
    ecart = solde_releve - solde_gl
    # Rapproché quand toutes les lignes de relevé (s'il y en a) sont
    # concordantes ET que l'écart global est nul. Une période SANS ligne de
    # relevé (aucun mouvement bancaire ce mois-ci) reste rapprochable si le
    # solde relevé saisi égale déjà le solde GL — rien à pointer, mais pas
    # un blocage dur (XACC10 : jamais de blocage dur sur une étape sans
    # activité réelle).
    rapproche = toutes_concordantes and ecart == Decimal('0')
    return {
        'solde_releve': solde_releve,
        'solde_gl': solde_gl,
        'ecart': ecart,
        'lignes_total': len(lignes),
        'lignes_pointees': lignes_pointees,
        'lignes_non_pointees': lignes_non_pointees,
        'montant_pointe': montant_pointe,
        'montant_non_pointe': montant_non_pointe,
        'statut': rapprochement.statut,
        'rapproche': rapproche,
    }


# ── XACC10 — Checklist de clôture de période ────────────────────────────────

def checklist_cloture_periode(periode):
    """Checklist de clôture calculée depuis les DONNÉES réelles (XACC10).

    ``cloturer_periode`` verrouille mais sans guidage : cette checklist
    calcule automatiquement l'état « fait / à faire / non applicable » de
    chaque étape type, à partir des données déjà en base — jamais une case à
    cocher manuelle. Renvoie ``{'etapes': [{'code', 'libelle', 'statut',
    'detail'}], 'toutes_faites': bool}`` ; ``statut`` ∈ {'fait', 'a_faire',
    'non_applicable'}. Une étape ``non_applicable`` compte comme faite pour
    ``toutes_faites`` (jamais un blocage dur sur une fonctionnalité absente,
    ex. écarts de change tant qu'aucun module multi-devise n'existe).
    """
    company = periode.company
    debut, fin = periode.date_debut, periode.date_fin
    etapes = []

    # 1. Dotations d'amortissement postées (pertinent en fin d'exercice : le
    # mois de décembre de l'exercice, où la dotation annuelle est passée).
    if fin.month == 12:
        dotations_annee = DotationAmortissement.objects.filter(
            company=company, annee=fin.year)
        if not dotations_annee.exists():
            etapes.append({
                'code': 'dotations', 'libelle': 'Dotations aux amortissements',
                'statut': 'non_applicable',
                'detail': "Aucun plan d'amortissement actif cette année."})
        else:
            non_postees = dotations_annee.filter(posted=False).count()
            etapes.append({
                'code': 'dotations', 'libelle': 'Dotations aux amortissements',
                'statut': 'fait' if non_postees == 0 else 'a_faire',
                'detail': f'{non_postees} dotation(s) non postée(s).'
                if non_postees else 'Toutes les dotations sont postées.'})
    else:
        etapes.append({
            'code': 'dotations', 'libelle': 'Dotations aux amortissements',
            'statut': 'non_applicable',
            'detail': "Postées en fin d'exercice (décembre) uniquement."})

    # 2. FNP/FAE de la période (XACC7) — au moins vérifié si une provision a
    # été postée OU s'il n'y a aucune écriture d'achat/vente non rapprochée
    # à provisionner ; par défaut « à faire » tant qu'aucune provision n'a
    # été générée pour cette période (rappel actif, jamais un blocage).
    provisions = EcritureComptable.objects.filter(
        company=company, source_type__in=['fnp', 'fae'],
        date_ecriture__gte=debut, date_ecriture__lte=fin).exists()
    etapes.append({
        'code': 'fnp_fae', 'libelle': 'Provisions FNP/FAE',
        'statut': 'fait' if provisions else 'a_faire',
        'detail': 'Provisions postées sur la période.' if provisions
        else 'Aucune provision FNP/FAE postée sur la période — à vérifier.'})

    # 3. Rapprochements bancaires soldés sur la période.
    rapprochements = RapprochementBancaire.objects.filter(
        company=company, date_fin__gte=debut, date_fin__lte=fin)
    if not rapprochements.exists():
        etapes.append({
            'code': 'rapprochements', 'libelle': 'Rapprochements bancaires',
            'statut': 'non_applicable',
            'detail': 'Aucun rapprochement ouvert sur la période.'})
    else:
        non_soldes = rapprochements.exclude(
            statut=RapprochementBancaire.Statut.RAPPROCHE).count()
        etapes.append({
            'code': 'rapprochements', 'libelle': 'Rapprochements bancaires',
            'statut': 'fait' if non_soldes == 0 else 'a_faire',
            'detail': f'{non_soldes} rapprochement(s) non soldé(s).'
            if non_soldes else 'Tous les rapprochements sont soldés.'})

    # 4. Caisses clôturées sur la période.
    caisses = Caisse.objects.filter(company=company)
    if not caisses.exists():
        etapes.append({
            'code': 'caisses', 'libelle': 'Caisses clôturées',
            'statut': 'non_applicable', 'detail': 'Aucune caisse configurée.'})
    else:
        cloturees = ClotureCaisse.objects.filter(
            company=company, date_cloture__gte=debut,
            date_cloture__lte=fin).values_list('caisse_id', flat=True).distinct()
        manquantes = caisses.exclude(id__in=list(cloturees)).count()
        etapes.append({
            'code': 'caisses', 'libelle': 'Caisses clôturées',
            'statut': 'fait' if manquantes == 0 else 'a_faire',
            'detail': f'{manquantes} caisse(s) sans clôture sur la période.'
            if manquantes else 'Toutes les caisses sont clôturées.'})

    # 5. Écarts de change — AUCUN module multi-devise n'existe encore dans
    # apps.compta (XACC17/18 planifiés) : toujours non applicable, jamais
    # faussement « fait » ou « à faire ».
    etapes.append({
        'code': 'ecarts_change', 'libelle': 'Écarts de change',
        'statut': 'non_applicable',
        'detail': 'Module multi-devise non encore disponible.'})

    # 6. TVA soldée (XACC10 — solder_tva_periode).
    tva_soldee = EcritureComptable.objects.filter(
        company=company, source_type='solde_tva',
        date_ecriture__gte=debut, date_ecriture__lte=fin).exists()
    etapes.append({
        'code': 'tva_soldee', 'libelle': 'TVA soldée',
        'statut': 'fait' if tva_soldee else 'a_faire',
        'detail': 'Écriture de solde TVA postée.' if tva_soldee
        else 'Aucune écriture de solde TVA postée sur la période.'})

    toutes_faites = all(
        e['statut'] in ('fait', 'non_applicable') for e in etapes)
    return {'etapes': etapes, 'toutes_faites': toutes_faites}


# ── FG124 — Caisse / petty cash (journal d'espèces) ────────────────────────

def solde_caisse_a(caisse, *, date_fin=None):
    """Solde théorique d'une caisse (solde initial + entrées − sorties).

    = ``solde_initial`` + Σ(entrées) − Σ(sorties) jusqu'à ``date_fin`` (incluse)
    si fournie. Lecture seule, identique au calcul du service ``solde_caisse``.
    """
    qs = MouvementCaisse.objects.filter(caisse=caisse)
    if date_fin is not None:
        qs = qs.filter(date_mouvement__lte=date_fin)
    entrees = qs.filter(sens=MouvementCaisse.Sens.ENTREE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    sorties = qs.filter(sens=MouvementCaisse.Sens.SORTIE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    return (caisse.solde_initial or Decimal('0')) + entrees - sorties


def journal_caisse(caisse, *, date_debut=None, date_fin=None):
    """Journal d'espèces d'une caisse : mouvements + solde courant cumulé (FG124).

    Renvoie une liste de dicts ordonnée par date puis id, chaque entrée portant
    ``{'id', 'date', 'sens', 'montant', 'montant_signe', 'motif',
    'justificatif', 'piece', 'posted', 'solde_courant'}`` où ``solde_courant``
    est le solde cumulé APRÈS le mouvement (en partant du solde initial). Lecture
    seule, scopée à la caisse.
    """
    qs = MouvementCaisse.objects.filter(caisse=caisse).order_by(
        'date_mouvement', 'id')
    if date_debut is not None:
        qs = qs.filter(date_mouvement__gte=date_debut)
    if date_fin is not None:
        qs = qs.filter(date_mouvement__lte=date_fin)
    solde = caisse.solde_initial or Decimal('0')
    lignes = []
    for mvt in qs:
        solde += mvt.montant_signe
        lignes.append({
            'id': mvt.id,
            'date': mvt.date_mouvement,
            'sens': mvt.sens,
            'montant': mvt.montant,
            'montant_signe': mvt.montant_signe,
            'motif': mvt.motif,
            'justificatif': mvt.justificatif,
            'piece': mvt.piece,
            'posted': mvt.posted,
            'solde_courant': solde,
        })
    return lignes


def resume_caisse(caisse, *, date_fin=None):
    """Synthèse d'une caisse : solde initial, entrées, sorties, solde courant.

    Renvoie ``{'solde_initial', 'total_entrees', 'total_sorties',
    'nb_mouvements', 'solde_courant', 'derniere_cloture'}`` jusqu'à ``date_fin``
    (incluse) si fournie. ``derniere_cloture`` porte la date et l'écart de la
    dernière clôture (ou None). Lecture seule.
    """
    qs = MouvementCaisse.objects.filter(caisse=caisse)
    if date_fin is not None:
        qs = qs.filter(date_mouvement__lte=date_fin)
    total_entrees = qs.filter(sens=MouvementCaisse.Sens.ENTREE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    total_sorties = qs.filter(sens=MouvementCaisse.Sens.SORTIE).aggregate(
        s=Sum('montant'))['s'] or Decimal('0')
    solde_initial = caisse.solde_initial or Decimal('0')
    derniere = caisse.clotures.order_by('-date_cloture', '-id').first()
    return {
        'solde_initial': solde_initial,
        'total_entrees': total_entrees,
        'total_sorties': total_sorties,
        'nb_mouvements': qs.count(),
        'solde_courant': solde_initial + total_entrees - total_sorties,
        'derniere_cloture': (
            {'date_cloture': derniere.date_cloture, 'ecart': derniere.ecart}
            if derniere is not None else None),
    }


def caisses_de(company):
    """Caisses actives d'une société (lecture seule, scopée société)."""
    return list(Caisse.objects.filter(company=company).select_related(
        'compte_tresorerie').order_by('libelle'))


# ── FG126 — Prévisionnel de trésorerie roulant 13 semaines ─────────────────

def previsionnel_tresorerie(company, *, date_debut=None, nb_semaines=13):
    """Prévisionnel de trésorerie roulant sur ``nb_semaines`` semaines (FG126).

    Construit une projection SEMAINE PAR SEMAINE en partant de la position de
    trésorerie consolidée actuelle (selon le grand livre) et en y empilant, pour
    chaque semaine, les ``LignePrevisionnelTresorerie`` prévues qui y tombent
    (montant signé : + encaissement, − décaissement) PLUS les effets ouverts
    (FG127/FG128) dont l'échéance tombe dans la semaine (effets à recevoir → +,
    à payer → −). Renvoie ``{'solde_initial', 'date_debut', 'semaines': [...]}``
    où chaque semaine porte ``{'index', 'date_debut', 'date_fin', 'entrees',
    'sorties', 'flux_net', 'solde_fin', 'lignes': [...]}``. Lecture seule.
    """
    debut = date_debut or timezone.localdate()
    # Cale le début sur le lundi de la semaine de ``debut``.
    debut = debut - timedelta(days=debut.weekday())
    position = position_tresorerie(company)
    solde = position['total']
    solde_initial = solde

    fin_horizon = debut + timedelta(weeks=nb_semaines)
    lignes_prev = list(LignePrevisionnelTresorerie.objects.filter(
        company=company, date_prevue__gte=debut,
        date_prevue__lt=fin_horizon).order_by('date_prevue', 'id'))
    effets = list(Effet.objects.filter(
        company=company, date_echeance__gte=debut,
        date_echeance__lt=fin_horizon,
        statut__in=[Effet.Statut.PORTEFEUILLE, Effet.Statut.REMIS]
    ).order_by('date_echeance', 'id'))
    # XACC14 — échéances d'emprunt FUTURES non postées : décaissement prévu.
    echeances_emprunt = list(EcheanceEmprunt.objects.filter(
        company=company, date_echeance__gte=debut,
        date_echeance__lt=fin_horizon, posted=False,
    ).select_related('emprunt').order_by('date_echeance', 'id'))

    semaines = []
    for i in range(nb_semaines):
        s_debut = debut + timedelta(weeks=i)
        s_fin = s_debut + timedelta(days=6)
        entrees = Decimal('0')
        sorties = Decimal('0')
        lignes = []
        for lp in lignes_prev:
            if s_debut <= lp.date_prevue <= s_fin:
                montant = lp.montant or Decimal('0')
                if montant >= 0:
                    entrees += montant
                else:
                    sorties += -montant
                lignes.append({
                    'type': 'prevu',
                    'libelle': lp.libelle,
                    'categorie': lp.categorie,
                    'date': lp.date_prevue,
                    'montant': montant,
                })
        for ef in effets:
            if s_debut <= ef.date_echeance <= s_fin:
                montant = ef.montant or Decimal('0')
                if ef.sens == Effet.Sens.RECEVOIR:
                    entrees += montant
                    signe = montant
                else:
                    sorties += montant
                    signe = -montant
                lignes.append({
                    'type': 'effet',
                    'libelle': (ef.numero or ef.tireur
                                or ef.get_type_effet_display()),
                    'categorie': ef.sens,
                    'date': ef.date_echeance,
                    'montant': signe,
                })
        for ee in echeances_emprunt:
            if s_debut <= ee.date_echeance <= s_fin:
                montant = ee.mensualite or Decimal('0')
                sorties += montant
                lignes.append({
                    'type': 'echeance_emprunt',
                    'libelle': (
                        f'Échéance emprunt {ee.emprunt.banque or ee.emprunt.reference}'),
                    'categorie': 'decaissement',
                    'date': ee.date_echeance,
                    'montant': -montant,
                })
        flux_net = entrees - sorties
        solde += flux_net
        semaines.append({
            'index': i + 1,
            'date_debut': s_debut,
            'date_fin': s_fin,
            'entrees': entrees,
            'sorties': sorties,
            'flux_net': flux_net,
            'solde_fin': solde,
            'lignes': lignes,
        })
    return {
        'solde_initial': solde_initial,
        'date_debut': debut,
        'nb_semaines': nb_semaines,
        'semaines': semaines,
    }


# ── FG127 / FG128 — Portefeuille d'effets (échéancier) ─────────────────────

def echeancier_effets(company, *, sens=None, statut=None):
    """Échéancier des effets (chèques/traites) de la société (FG127/FG128).

    Liste les ``Effet`` filtrés par ``sens`` (recevoir/payer) et/ou ``statut``,
    ordonnés par échéance. Renvoie une liste de dicts ; les effets OUVERTS (non
    soldés/rejetés) alimentent la trésorerie prévisionnelle. Lecture seule.
    """
    qs = Effet.objects.filter(company=company)
    if sens:
        qs = qs.filter(sens=sens)
    if statut:
        qs = qs.filter(statut=statut)
    qs = qs.order_by('date_echeance', 'id')
    resultats = []
    for ef in qs:
        resultats.append({
            'id': ef.id,
            'sens': ef.sens,
            'type_effet': ef.type_effet,
            'numero': ef.numero,
            'montant': ef.montant,
            'date_emission': ef.date_emission,
            'date_echeance': ef.date_echeance,
            'banque': ef.banque,
            'tireur': ef.tireur,
            'statut': ef.statut,
            'frais_rejet': ef.frais_rejet,
            'bordereau_id': ef.bordereau_id,
        })
    return resultats


def total_effets_ouverts(company, *, sens):
    """Total des montants des effets OUVERTS d'un sens (portefeuille+remis)."""
    total = Effet.objects.filter(
        company=company, sens=sens,
        statut__in=[Effet.Statut.PORTEFEUILLE, Effet.Statut.REMIS]
    ).aggregate(s=Sum('montant'))['s']
    return total or Decimal('0')


# ── FG131 — Rapprochement 3 voies (BC ↔ réception ↔ facture fournisseur) ────

def rapprochements_en_ecart(company):
    """Rapprochements 3 voies de la société présentant un écart bloquant
    (statut ``ecart``), ordonnés du plus récemment évalué au plus ancien.
    Sert d'alerte « à corriger avant paiement ». Lecture seule."""
    return list(
        Rapprochement.objects.filter(
            company=company, statut=Rapprochement.Statut.ECART)
        .order_by('-date_evaluation', '-id'))


def rapprochement_ecart_pct(company, bon_commande_id):
    """XPUR10 — écart en % (facturé vs reçu) du rapprochement 3 voies d'un
    BCF, pour que ``apps.stock`` puisse comparer aux tolérances société sans
    jamais importer ``apps.compta.models``. Renvoie ``None`` si aucun
    rapprochement n'existe encore pour ce BCF (pas encore évalué — no-op,
    comportement historique). Lecture seule, scopée société."""
    rapp = Rapprochement.objects.filter(
        company=company, bon_commande_id=bon_commande_id).first()
    if rapp is None:
        return None
    if not rapp.montant_recu:
        return None
    return abs(rapp.ecart) / rapp.montant_recu * Decimal('100')


# ── FG132 — Échéancier & relevé fournisseur (balance âgée AP + relevé) ──────
# Miroir fournisseur de la balance âgée clients (apps.ventes.recouvrement). Tout
# se déduit du grand livre de la compta elle-même (lignes du compte 4411
# Fournisseurs, auxiliarisées par ``tiers_type``/``tiers_id``) — AUCUN import
# cross-app de modèle. Lecture seule, scopée société. Le côté fournisseur est un
# compte de PASSIF : son solde naturel est CRÉDITEUR ; ce qui reste DÛ à un
# fournisseur = Σ(crédit) − Σ(débit) de ses lignes (positif = à payer).

# Comptes de tiers fournisseurs dont les lignes alimentent la balance âgée AP.
_COMPTES_FOURNISSEURS_AP = ('4411', '4417')   # Fournisseurs + retenues garantie.


def _nom_fournisseur(company, tiers_type, tiers_id):
    """Résout le nom d'un fournisseur via le sélecteur de stock (cross-app READ).

    N'importe JAMAIS ``apps.stock.models`` : passe par
    ``apps.stock.selectors.get_fournisseur_by_id`` (import local pour éviter les
    cycles). Renvoie ``''`` si le tiers est inconnu / non fournisseur.
    """
    if tiers_id is None or (tiers_type or '') != 'fournisseur':
        return ''
    try:
        from apps.stock.selectors import get_fournisseur_by_id
    except Exception:  # pragma: no cover - défensif si l'app stock manque
        return ''
    fournisseur = get_fournisseur_by_id(company, tiers_id)
    return getattr(fournisseur, 'nom', '') or ''


def _lignes_ap_qs(company, *, date_debut=None, date_fin=None,
                  validees_seulement=False):
    """Lignes du grand livre sur les comptes fournisseurs (auxiliaire tiers)."""
    return _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                      validees_seulement=validees_seulement).filter(
        compte__numero__in=_COMPTES_FOURNISSEURS_AP)


def balance_agee_fournisseurs(company, *, date_reference=None,
                              validees_seulement=False):
    """Balance âgée fournisseurs : encours dû par fournisseur, bucketé par âge.

    Miroir AP de la balance âgée clients. Pour chaque fournisseur (auxiliaire
    ``tiers_id`` des lignes du compte 4411), on cumule le montant restant DÛ
    (Σ crédit − Σ débit) en quatre tranches d'ancienneté calculées à partir de la
    DATE D'ÉCRITURE par rapport à ``date_reference`` (défaut : aujourd'hui) :
    0–30 / 31–60 / 61–90 / 90+ jours. Les lignes lettrées (appariées/soldées)
    sont EXCLUES — seul l'encours ouvert reste dû. Un fournisseur dont l'encours
    net est nul ou débiteur (avance/avoir) est omis. Renvoie une liste de dicts
    ``{'tiers_id', 'fournisseur_nom', 'b0_30', 'b31_60', 'b61_90', 'b90_plus',
    'total'}`` triés par total décroissant. Lecture seule, scopée société.
    """
    ref = date_reference or timezone.localdate()
    qs = _lignes_ap_qs(
        company, date_fin=date_reference,
        validees_seulement=validees_seulement).filter(
        lettrage='', tiers_id__isnull=False, tiers_type='fournisseur')
    par_tiers = {}
    for ligne in qs:
        tid = ligne.tiers_id
        entry = par_tiers.setdefault(tid, {
            'tiers_id': tid,
            'tiers_type': ligne.tiers_type,
            'b0_30': Decimal('0'), 'b31_60': Decimal('0'),
            'b61_90': Decimal('0'), 'b90_plus': Decimal('0'),
            'total': Decimal('0'),
        })
        # Dette fournisseur (passif) : crédit − débit (positif = à payer).
        montant = (ligne.credit or Decimal('0')) - (ligne.debit or Decimal('0'))
        jours = (ref - ligne.ecriture.date_ecriture).days
        if jours <= 30:
            entry['b0_30'] += montant
        elif jours <= 60:
            entry['b31_60'] += montant
        elif jours <= 90:
            entry['b61_90'] += montant
        else:
            entry['b90_plus'] += montant
        entry['total'] += montant
    out = []
    for entry in par_tiers.values():
        if entry['total'] <= 0:
            continue  # solde nul ou débiteur (avance/avoir) : pas une dette.
        entry['fournisseur_nom'] = _nom_fournisseur(
            company, entry['tiers_type'], entry['tiers_id'])
        out.append(entry)
    out.sort(key=lambda e: e['total'], reverse=True)
    return out


def releve_fournisseur(company, tiers_id, *, tiers_type='fournisseur',
                       date_debut=None, date_fin=None,
                       validees_seulement=False):
    """Relevé de compte d'un fournisseur : toutes ses lignes 4411 + soldes.

    Miroir AP du relevé client. Liste chronologiquement les mouvements du compte
    fournisseur pour l'auxiliaire ``tiers_id`` (factures au crédit, règlements au
    débit) avec un solde courant cumulé (côté passif : crédit − débit), et les
    totaux ``{credit, debit, solde_du}``. ``solde_du`` positif = reste à payer.
    Renvoie ``{'fournisseur': {...}, 'lignes': [...], 'totaux': {...}}``.
    Lecture seule, scopée société.
    """
    qs = _lignes_ap_qs(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement).filter(
        tiers_id=tiers_id, tiers_type=tiers_type).order_by(
        'ecriture__date_ecriture', 'id')
    lignes = []
    total_credit = total_debit = Decimal('0')
    solde = Decimal('0')
    for ligne in qs:
        credit = ligne.credit or Decimal('0')
        debit = ligne.debit or Decimal('0')
        solde += credit - debit
        total_credit += credit
        total_debit += debit
        lignes.append({
            'date': ligne.ecriture.date_ecriture,
            'journal': ligne.ecriture.journal.code,
            'reference': ligne.ecriture.reference,
            'libelle': ligne.libelle or ligne.ecriture.libelle,
            'credit': credit,   # facture / dette engagée.
            'debit': debit,     # règlement / avoir.
            'lettrage': ligne.lettrage,
            'solde_courant': solde,
        })
    return {
        'fournisseur': {
            'tiers_id': tiers_id,
            'tiers_type': tiers_type,
            'nom': _nom_fournisseur(company, tiers_type, tiers_id),
        },
        'lignes': lignes,
        'totaux': {
            'credit': total_credit,
            'debit': total_debit,
            'solde_du': solde,
        },
    }


# ── FG137 — Préparation de la déclaration de TVA ────────────────────────────

# Comptes CGNC de TVA. La TVA collectée (facturée aux clients) est un PASSIF
# (classe 4455…) : elle naît au CRÉDIT. La TVA déductible/récupérable (payée
# aux fournisseurs) est un ACTIF (classe 3455…) : elle naît au DÉBIT.
_COMPTES_TVA_COLLECTEE = ('4455', '44552')      # TVA facturée / due (passif).
_COMPTES_TVA_DEDUCTIBLE = ('3455', '34552')     # TVA récupérable (actif).


def _mouvements_groupe(company, numeros, *, date_debut=None, date_fin=None,
                       validees_seulement=False):
    """Σ débit et Σ crédit d'un groupe de comptes (par numéros) sur une période.

    À la différence de ``_solde_groupe`` (solde cumulé à une date), on agrège
    les MOUVEMENTS de la période ``[date_debut ; date_fin]`` — c'est ce qu'exige
    une déclaration périodique de TVA (la TVA du mois/trimestre, pas le cumul).
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__numero__in=numeros)
    agg = qs.aggregate(debit=Sum('debit'), credit=Sum('credit'))
    return (agg['debit'] or Decimal('0'), agg['credit'] or Decimal('0'))


def preparer_declaration_tva(company, *, date_debut, date_fin, regime='mensuel',
                             methode='debit', credit_anterieur=Decimal('0'),
                             validees_seulement=False, comparer=False,
                             date_debut_m1=None, date_fin_m1=None):
    """Calcule la TVA à déclarer sur une période depuis le grand livre (FG137).

    TVA collectée = Σ crédit − Σ débit des comptes 4455… (passif : un avoir
    annulant une vente DÉBITE 4455, on le déduit). TVA déductible = Σ débit − Σ
    crédit des comptes 3455… (actif : un avoir fournisseur CRÉDITE 3455). La TVA
    nette à déclarer = max(0, collectée − déductible − crédit antérieur) ;
    l'excédent éventuel devient un crédit reportable. ``regime`` (mensuel /
    trimestriel) et ``methode`` (débit / encaissement) qualifient le dépôt mais
    n'altèrent pas l'agrégation GL (la période en porte la portée). Lecture
    seule, scopée société. Renvoie un dict prêt à figer sur une ``DeclarationTVA``.

    ZACC10 — ``comparer=True`` ajoute ``tva_collectee_m1``/
    ``tva_deductible_m1``/``tva_a_declarer_m1`` + les écarts % correspondants,
    calculés sur ``date_debut_m1``/``date_fin_m1`` (défaut : la période
    immédiatement précédente, de même durée). Défaut = réponse actuelle
    byte-identique — détection d'anomalie de collecte/déduction M-1.
    """
    debit_coll, credit_coll = _mouvements_groupe(
        company, _COMPTES_TVA_COLLECTEE, date_debut=date_debut,
        date_fin=date_fin, validees_seulement=validees_seulement)
    collectee = credit_coll - debit_coll
    if collectee < 0:
        collectee = Decimal('0')

    debit_ded, credit_ded = _mouvements_groupe(
        company, _COMPTES_TVA_DEDUCTIBLE, date_debut=date_debut,
        date_fin=date_fin, validees_seulement=validees_seulement)
    deductible = debit_ded - credit_ded
    if deductible < 0:
        deductible = Decimal('0')

    anterieur = credit_anterieur or Decimal('0')
    net = collectee - deductible - anterieur
    a_declarer = net if net >= 0 else Decimal('0')
    reportable = -net if net < 0 else Decimal('0')
    resultat = {
        'date_debut': date_debut,
        'date_fin': date_fin,
        'regime': regime,
        'methode': methode,
        'tva_collectee': collectee,
        'tva_deductible': deductible,
        'credit_anterieur': anterieur,
        'tva_a_declarer': a_declarer,
        'credit_reportable': reportable,
    }
    if comparer:
        deb_m1, fin_m1 = _periode_m1(date_debut, date_fin, date_debut_m1,
                                     date_fin_m1)
        m1 = preparer_declaration_tva(
            company, date_debut=deb_m1, date_fin=fin_m1, regime=regime,
            methode=methode, validees_seulement=validees_seulement)
        resultat['date_debut_m1'] = deb_m1
        resultat['date_fin_m1'] = fin_m1
        resultat['tva_collectee_m1'] = m1['tva_collectee']
        resultat['tva_collectee_ecart_pct'] = _ecart_pct(
            collectee, m1['tva_collectee'])
        resultat['tva_deductible_m1'] = m1['tva_deductible']
        resultat['tva_deductible_ecart_pct'] = _ecart_pct(
            deductible, m1['tva_deductible'])
        resultat['tva_a_declarer_m1'] = m1['tva_a_declarer']
        resultat['tva_a_declarer_ecart_pct'] = _ecart_pct(
            a_declarer, m1['tva_a_declarer'])
    return resultat


def _periode_m1(date_debut, date_fin, date_debut_m1=None, date_fin_m1=None):
    """Résout la période M-1 (précédente) : bornes explicites priment, sinon
    la période immédiatement AVANT ``date_debut`` de la MÊME durée en jours
    (jamais d'erreur si aucune donnée M-1 n'existe — soldes nuls)."""
    if date_debut_m1 or date_fin_m1:
        return date_debut_m1, date_fin_m1
    deb = _as_date(date_debut)
    fin = _as_date(date_fin)
    if deb is None or fin is None:
        return None, None
    duree = (fin - deb).days
    fin_m1 = deb - timedelta(days=1)
    deb_m1 = fin_m1 - timedelta(days=duree)
    return deb_m1, fin_m1


# ── FG138 — Relevé de déductions détaillé (annexe TVA, DGI) ────────────────

def _taux_tva(base_ht, tva):
    """Taux de TVA en % déduit de (TVA / base HT), arrondi à 2 décimales.

    Renvoie ``None`` quand la base HT est nulle (taux indéterminé) — le relevé
    affiche alors le montant de TVA sans imputer un taux fictif.
    """
    if not base_ht:
        return None
    return (tva / base_ht * Decimal('100')).quantize(Decimal('0.01'))


def releve_deductions_tva(company, *, date_debut, date_fin,
                          validees_seulement=False):
    """Annexe DGI : relevé ligne par ligne des déductions de TVA (FG138).

    La DGI exige, à l'appui de la déclaration (FG137), la liste détaillée de
    chaque pièce ouvrant droit à déduction de TVA. On lit le grand livre : pour
    chaque ÉCRITURE portant une ligne de TVA récupérable (comptes 3455…), on
    produit une ligne d'annexe avec la date, la référence/pièce, le journal, le
    tiers (fournisseur résolu via l'auxiliaire de la ligne 4411 de la même
    écriture), la base HT (Σ des lignes de charge/immobilisation hors TVA et hors
    compte fournisseur, débit − crédit), le montant de TVA déductible
    (3455… débit − crédit) et le taux déduit. La somme des TVA des lignes
    reconcilie 1:1 avec ``tva_deductible`` de ``preparer_declaration_tva`` sur la
    même période. Borné à ``[date_debut ; date_fin]``, lecture seule, scopé
    société. Renvoie ``{'date_debut', 'date_fin', 'lignes': [...], 'totaux':
    {'base_ht', 'tva'}}``.
    """
    # Toutes les lignes de TVA déductible de la période, groupées par écriture.
    tva_qs = _lignes_qs(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement).filter(
        compte__numero__in=_COMPTES_TVA_DEDUCTIBLE).order_by(
        'ecriture__date_ecriture', 'ecriture_id', 'id')

    tva_par_ecriture = {}
    ordre_ecritures = []
    for ligne in tva_qs:
        eid = ligne.ecriture_id
        if eid not in tva_par_ecriture:
            tva_par_ecriture[eid] = {
                'ecriture': ligne.ecriture,
                'tva': Decimal('0'),
                # XACC11 — la ligne 3455 porte « (prorata NN%) » dans son
                # PROPRE libellé quand un coefficient < 100 % a été appliqué
                # à la source (cf. ``services.ecriture_pour_facture_
                # fournisseur``) — jamais un champ séparé, dérivé du GL.
                'prorata_applique': False,
            }
            ordre_ecritures.append(eid)
        tva_par_ecriture[eid]['tva'] += (
            (ligne.debit or Decimal('0')) - (ligne.credit or Decimal('0')))
        if '(prorata ' in (ligne.libelle or ''):
            tva_par_ecriture[eid]['prorata_applique'] = True

    if not ordre_ecritures:
        return {
            'date_debut': date_debut,
            'date_fin': date_fin,
            'lignes': [],
            'totaux': {'base_ht': Decimal('0'), 'tva': Decimal('0')},
        }

    # Toutes les AUTRES lignes de ces écritures (base HT + tiers fournisseur).
    autres_qs = LigneEcriture.objects.filter(
        company=company, ecriture_id__in=ordre_ecritures).select_related(
        'compte', 'ecriture', 'ecriture__journal').exclude(
        compte__numero__in=_COMPTES_TVA_DEDUCTIBLE)

    base_par_ecriture = {eid: Decimal('0') for eid in ordre_ecritures}
    tiers_par_ecriture = {}
    for ligne in autres_qs:
        eid = ligne.ecriture_id
        numero = ligne.compte.numero
        # Le tiers fournisseur de la pièce vient de la ligne 4411 (auxiliaire).
        if numero in _COMPTES_FOURNISSEURS_AP:
            if ligne.tiers_id is not None and eid not in tiers_par_ecriture:
                tiers_par_ecriture[eid] = (ligne.tiers_type, ligne.tiers_id)
            continue  # le compte fournisseur n'entre pas dans la base HT.
        # Base HT = charges/immobilisations (débit − crédit), hors TVA & tiers.
        base_par_ecriture[eid] += (
            (ligne.debit or Decimal('0')) - (ligne.credit or Decimal('0')))

    lignes = []
    total_base = total_tva = Decimal('0')
    for eid in ordre_ecritures:
        ecriture = tva_par_ecriture[eid]['ecriture']
        tva = tva_par_ecriture[eid]['tva']
        base_ht = base_par_ecriture.get(eid, Decimal('0'))
        tiers = tiers_par_ecriture.get(eid)
        tiers_nom = ''
        tiers_type = ''
        tiers_id = None
        if tiers is not None:
            tiers_type, tiers_id = tiers
            tiers_nom = _nom_fournisseur(company, tiers_type, tiers_id)
        total_base += base_ht
        total_tva += tva
        lignes.append({
            'date': ecriture.date_ecriture,
            'reference': ecriture.reference or f'{ecriture.journal.code}-{eid}',
            'journal': ecriture.journal.code,
            'libelle': ecriture.libelle,
            'tiers_type': tiers_type,
            'tiers_id': tiers_id,
            'tiers': tiers_nom,
            'base_ht': base_ht,
            'tva': tva,
            'prorata_applique': tva_par_ecriture[eid]['prorata_applique'],
            'taux': _taux_tva(base_ht, tva),
        })

    return {
        'date_debut': date_debut,
        'date_fin': date_fin,
        'lignes': lignes,
        'totaux': {'base_ht': total_base, 'tva': total_tva},
    }


# ── FG139 — Retenue à la source (RAS) : liste & bordereau de versement ──────

def _retenues_qs(company, *, date_debut=None, date_fin=None, statut=None):
    """Retenues à la source d'une société, bornées sur la DATE DE PIÈCE.

    Le bornage suit ``date_piece`` (le fait générateur de la retenue) — c'est ce
    qui définit la période du bordereau de versement. Lecture seule, scopée
    société.
    """
    qs = RetenueSource.objects.filter(company=company)
    if date_debut:
        qs = qs.filter(date_piece__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_piece__lte=date_fin)
    if statut:
        qs = qs.filter(statut=statut)
    return qs


def retenues_source_periode(company, *, date_debut=None, date_fin=None,
                            statut=None):
    """Liste détaillée des RAS sur une période (FG139).

    Renvoie ``{'date_debut', 'date_fin', 'lignes': [...], 'totaux':
    {'base', 'montant', 'net'}}`` où chaque ligne porte la pièce, le tiers, le
    type de prestation, la base, le taux, le montant retenu et le net à payer.
    Bornée sur ``date_piece``, lecture seule, scopée société.
    """
    qs = _retenues_qs(
        company, date_debut=date_debut, date_fin=date_fin, statut=statut,
    ).order_by('date_piece', 'id')
    lignes = []
    total_base = total_montant = Decimal('0')
    for ras in qs:
        base = ras.base or Decimal('0')
        montant = ras.montant or Decimal('0')
        total_base += base
        total_montant += montant
        lignes.append({
            'id': ras.id,
            'reference': ras.reference,
            'piece': ras.piece,
            'date_piece': ras.date_piece,
            'type_prestation': ras.type_prestation,
            'tiers_type': ras.tiers_type,
            'tiers_id': ras.tiers_id,
            'tiers_nom': ras.tiers_nom,
            'identifiant_fiscal': ras.identifiant_fiscal,
            'base': base,
            'taux': ras.taux or Decimal('0'),
            'montant': montant,
            'net_a_payer': base - montant,
            'statut': ras.statut,
        })
    return {
        'date_debut': date_debut,
        'date_fin': date_fin,
        'lignes': lignes,
        'totaux': {
            'base': total_base,
            'montant': total_montant,
            'net': total_base - total_montant,
        },
    }


def bordereau_versement_ras(company, *, date_debut=None, date_fin=None,
                            statut=None):
    """Bordereau de versement de la RAS : totaux PAR PRESTATAIRE (FG139).

    La déclaration/versement de la retenue à la source à l'administration se fait
    sur un bordereau récapitulatif : une ligne par prestataire (regroupé sur
    l'auxiliaire ``tiers_id`` du tiers, ou à défaut sur le couple nom + IF pour
    les tiers libres), portant l'identifiant fiscal, la base cumulée et le
    montant total retenu sur la période. Le ``total_a_verser`` est la somme des
    montants retenus — c'est ce que la société reverse au Trésor. Bornée sur
    ``date_piece``, lecture seule, scopée société. Renvoie ``{'date_debut',
    'date_fin', 'lignes': [...], 'totaux': {'base', 'montant', 'nb_pieces'},
    'total_a_verser'}``.
    """
    qs = _retenues_qs(
        company, date_debut=date_debut, date_fin=date_fin, statut=statut,
    ).order_by('tiers_id', 'id')
    par_tiers = {}
    ordre = []
    for ras in qs:
        # Clé de regroupement : l'auxiliaire tiers s'il existe, sinon le couple
        # (nom, identifiant fiscal) pour un prestataire saisi librement.
        if ras.tiers_id is not None:
            cle = ('tiers', ras.tiers_type, ras.tiers_id)
        else:
            cle = ('libre', ras.tiers_nom, ras.identifiant_fiscal)
        entry = par_tiers.get(cle)
        if entry is None:
            entry = {
                'tiers_type': ras.tiers_type,
                'tiers_id': ras.tiers_id,
                'tiers_nom': ras.tiers_nom,
                'identifiant_fiscal': ras.identifiant_fiscal,
                'base': Decimal('0'),
                'montant': Decimal('0'),
                'nb_pieces': 0,
            }
            par_tiers[cle] = entry
            ordre.append(cle)
        # Garde le nom/IF le plus renseigné rencontré pour ce tiers.
        if not entry['tiers_nom'] and ras.tiers_nom:
            entry['tiers_nom'] = ras.tiers_nom
        if not entry['identifiant_fiscal'] and ras.identifiant_fiscal:
            entry['identifiant_fiscal'] = ras.identifiant_fiscal
        entry['base'] += ras.base or Decimal('0')
        entry['montant'] += ras.montant or Decimal('0')
        entry['nb_pieces'] += 1

    lignes = [par_tiers[cle] for cle in ordre]
    lignes.sort(key=lambda e: e['montant'], reverse=True)
    total_base = sum((e['base'] for e in lignes), Decimal('0'))
    total_montant = sum((e['montant'] for e in lignes), Decimal('0'))
    total_pieces = sum(e['nb_pieces'] for e in lignes)
    return {
        'date_debut': date_debut,
        'date_fin': date_fin,
        'lignes': lignes,
        'totaux': {
            'base': total_base,
            'montant': total_montant,
            'nb_pieces': total_pieces,
        },
        'total_a_verser': total_montant,
    }


def declaration_honoraires(company, annee, *, type_prestation=None):
    """Déclaration annuelle des honoraires / état 9421 (FG143).

    Obligation marocaine (DGI) : déclarer chaque année, par bénéficiaire, le
    total des honoraires / rémunérations / commissions versés à des tiers, avec
    l'identité fiscale du bénéficiaire (IF/ICE). On agrège ici, par tiers
    (prestataire), les retenues à la source enregistrées (FG139,
    ``RetenueSource``) dont la ``date_piece`` tombe dans l'année civile
    ``annee`` : ce sont les paiements aux tiers ouvrant la déclaration. Pour
    chaque bénéficiaire on restitue son IF/ICE, le montant brut versé (somme des
    bases), la retenue à la source pratiquée le cas échéant et le net payé, plus
    le nombre de pièces. Aucun nouveau modèle : tout est dérivé du grand livre
    auxiliaire des RAS. Lecture seule, scopée société, bornée à l'année civile.

    ``annee`` est borné sur ``[annee-01-01 ; annee-12-31]`` (date de pièce).
    Renvoie ``{'annee', 'date_debut', 'date_fin', 'lignes': [...], 'totaux':
    {'brut', 'retenue', 'net', 'nb_pieces'}, 'nb_beneficiaires'}`` où chaque
    ligne porte ``tiers_type / tiers_id / tiers_nom / identifiant_fiscal /
    brut / retenue / net / nb_pieces``. Trié par montant brut décroissant.
    """
    annee = int(annee)
    date_debut = date(annee, 1, 1)
    date_fin = date(annee, 12, 31)
    qs = _retenues_qs(company, date_debut=date_debut, date_fin=date_fin)
    if type_prestation:
        qs = qs.filter(type_prestation=type_prestation)
    qs = qs.order_by('tiers_id', 'id')

    par_tiers = {}
    ordre = []
    for ras in qs:
        # Regroupement par bénéficiaire : l'auxiliaire tiers s'il existe, sinon
        # le couple (nom, identifiant fiscal) pour un prestataire saisi libre.
        if ras.tiers_id is not None:
            cle = ('tiers', ras.tiers_type, ras.tiers_id)
        else:
            cle = ('libre', ras.tiers_nom, ras.identifiant_fiscal)
        entry = par_tiers.get(cle)
        if entry is None:
            entry = {
                'tiers_type': ras.tiers_type,
                'tiers_id': ras.tiers_id,
                'tiers_nom': ras.tiers_nom,
                'identifiant_fiscal': ras.identifiant_fiscal,
                'brut': Decimal('0'),
                'retenue': Decimal('0'),
                'net': Decimal('0'),
                'nb_pieces': 0,
            }
            par_tiers[cle] = entry
            ordre.append(cle)
        # Garde le nom/IF le plus renseigné rencontré pour ce bénéficiaire.
        if not entry['tiers_nom'] and ras.tiers_nom:
            entry['tiers_nom'] = ras.tiers_nom
        if not entry['identifiant_fiscal'] and ras.identifiant_fiscal:
            entry['identifiant_fiscal'] = ras.identifiant_fiscal
        base = ras.base or Decimal('0')
        retenue = ras.montant or Decimal('0')
        entry['brut'] += base
        entry['retenue'] += retenue
        entry['net'] += base - retenue
        entry['nb_pieces'] += 1

    lignes = [par_tiers[cle] for cle in ordre]
    lignes.sort(key=lambda e: e['brut'], reverse=True)
    total_brut = sum((e['brut'] for e in lignes), Decimal('0'))
    total_retenue = sum((e['retenue'] for e in lignes), Decimal('0'))
    total_pieces = sum(e['nb_pieces'] for e in lignes)
    return {
        'annee': annee,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'lignes': lignes,
        'totaux': {
            'brut': total_brut,
            'retenue': total_retenue,
            'net': total_brut - total_retenue,
            'nb_pieces': total_pieces,
        },
        'nb_beneficiaires': len(lignes),
    }


# ── FG144 — Droit de timbre sur encaissements en espèces ───────────────────

def _timbres_qs(company, *, date_debut=None, date_fin=None, statut=None):
    """Droits de timbre d'une société, bornés sur la DATE D'ENCAISSEMENT.

    Le bornage suit ``date_encaissement`` (le fait générateur du timbre) — c'est
    ce qui définit la période de versement. Lecture seule, scopée société.
    """
    qs = TimbreFiscal.objects.filter(company=company)
    if date_debut:
        qs = qs.filter(date_encaissement__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_encaissement__lte=date_fin)
    if statut:
        qs = qs.filter(statut=statut)
    return qs


def timbres_fiscaux_periode(company, *, date_debut=None, date_fin=None,
                            statut=None):
    """Liste détaillée des droits de timbre sur une période (FG144).

    Renvoie ``{'date_debut', 'date_fin', 'lignes': [...], 'totaux':
    {'base', 'montant', 'nb_pieces'}, 'total_a_verser'}`` où chaque ligne porte
    le paiement d'origine (string-ref), le payeur, la base encaissée, le taux, le
    minimum et le droit de timbre. Bornée sur ``date_encaissement``, lecture
    seule, scopée société. ``total_a_verser`` = somme des droits de timbre — ce
    que la société reverse au Trésor.
    """
    qs = _timbres_qs(
        company, date_debut=date_debut, date_fin=date_fin, statut=statut,
    ).order_by('date_encaissement', 'id')
    lignes = []
    total_base = total_montant = Decimal('0')
    nb = 0
    for tf in qs:
        base = tf.base or Decimal('0')
        montant = tf.montant or Decimal('0')
        total_base += base
        total_montant += montant
        nb += 1
        lignes.append({
            'id': tf.id,
            'reference': tf.reference,
            'date_encaissement': tf.date_encaissement,
            'paiement_id': tf.paiement_id,
            'facture_ref': tf.facture_ref,
            'mode_reglement': tf.mode_reglement,
            'tiers_type': tf.tiers_type,
            'tiers_id': tf.tiers_id,
            'tiers_nom': tf.tiers_nom,
            'base': base,
            'taux': tf.taux or Decimal('0'),
            'minimum': tf.minimum or Decimal('0'),
            'montant': montant,
            'statut': tf.statut,
        })
    return {
        'date_debut': date_debut,
        'date_fin': date_fin,
        'lignes': lignes,
        'totaux': {
            'base': total_base,
            'montant': total_montant,
            'nb_pieces': nb,
        },
        'total_a_verser': total_montant,
    }


# ── FG140 — Aide au calcul de l'IS (impôt sur les sociétés) ─────────────────
#
# Aide à l'estimation de l'IS marocain depuis le CPC (résultat fiscal),
# l'échéancier des 4 acomptes provisionnels et la régularisation. C'est une
# AIDE indicative : le résultat comptable du CPC sert de base au résultat
# fiscal (les réintégrations/déductions extra-comptables ne sont pas saisies
# ici, elles peuvent être passées en argument). Aucune écriture n'est créée.
#
# Barème IS progressif (taux marginaux par tranche, CGI marocain) — exprimé en
# bornes cumulatives. La dernière tranche est ouverte (> 1 000 000 MAD).
_BAREME_IS = (
    # (borne_haute_ou_None, taux %)
    (Decimal('300000'), Decimal('10')),
    (Decimal('1000000'), Decimal('20')),
    (None, Decimal('31')),
)
# Cotisation minimale (CM) : plancher de l'IS. Taux de droit commun 0,25 % de
# la base CM (produits d'exploitation/financiers/non courants), avec un montant
# minimum forfaitaire.
_TAUX_CM = Decimal('0.25')          # %
_CM_MINIMUM = Decimal('3000')       # MAD — plancher forfaitaire de la CM.
# Comptes de produits (classe 7) entrant dans la base de la cotisation minimale.
# On retient le total des produits du CPC comme proxy de la base CM.
_QUANTUM = Decimal('0.01')


def _q(montant):
    """Arrondi monétaire à 2 décimales (demi-supérieur)."""
    return (montant or Decimal('0')).quantize(_QUANTUM, rounding=ROUND_HALF_UP)


def is_bareme(resultat_fiscal):
    """IS théorique au barème progressif marocain sur un résultat fiscal.

    Applique les taux marginaux par tranche (10 / 20 / 31 %). Renvoie un dict
    ``{'resultat_fiscal', 'tranches': [...], 'is_bareme'}`` où chaque tranche
    détaille ``{'de', 'a', 'taux', 'base', 'impot'}``. Un résultat ≤ 0 donne
    un IS au barème nul (la cotisation minimale s'applique alors séparément).
    """
    resultat = _q(resultat_fiscal)
    tranches = []
    total = Decimal('0')
    if resultat > 0:
        bas = Decimal('0')
        for borne, taux in _BAREME_IS:
            if borne is None:
                base = resultat - bas
            else:
                base = min(resultat, borne) - bas
            if base <= 0:
                break
            impot = _q(base * taux / Decimal('100'))
            tranches.append({
                'de': bas,
                'a': borne,
                'taux': taux,
                'base': _q(base),
                'impot': impot,
            })
            total += impot
            if borne is None or resultat <= borne:
                break
            bas = borne
    return {
        'resultat_fiscal': resultat,
        'tranches': tranches,
        'is_bareme': _q(total),
    }


def cotisation_minimale(base_cm):
    """Cotisation minimale = max(taux_CM × base, minimum forfaitaire).

    ``base_cm`` est la base de la CM (produits taxables, proxy = total produits
    du CPC). Renvoie ``{'base', 'taux', 'cm_calculee', 'cm_minimum', 'cm'}``.
    """
    base = _q(base_cm if base_cm and base_cm > 0 else Decimal('0'))
    calculee = _q(base * _TAUX_CM / Decimal('100'))
    cm = calculee if calculee > _CM_MINIMUM else _CM_MINIMUM
    return {
        'base': base,
        'taux': _TAUX_CM,
        'cm_calculee': calculee,
        'cm_minimum': _CM_MINIMUM,
        'cm': _q(cm),
    }


def estimer_is(company, exercice, *, reintegrations=None, deductions=None,
               validees_seulement=False):
    """Estime l'IS dû d'un exercice depuis le CPC (FG140).

    Le résultat comptable du CPC (produits classe 7 − charges classe 6) est la
    base. On y ajoute les ``reintegrations`` extra-comptables et on retranche
    les ``deductions`` pour obtenir le résultat fiscal. L'IS dû = max(IS au
    barème progressif, cotisation minimale). Lecture seule, scopée société
    (l'exercice DOIT appartenir à ``company``).

    Renvoie ``{'exercice', 'date_debut', 'date_fin', 'resultat_comptable',
    'reintegrations', 'deductions', 'resultat_fiscal', 'bareme',
    'cotisation_minimale', 'is_du', 'base_retenue'}`` où ``base_retenue`` vaut
    'bareme' ou 'cotisation_minimale'.
    """
    if exercice.company_id != company.id:
        raise ValueError("L'exercice n'appartient pas à cette société.")
    etat = cpc(
        company, date_debut=exercice.date_debut, date_fin=exercice.date_fin,
        validees_seulement=validees_seulement)
    resultat_comptable = _q(etat['resultat'])
    reint = _q(reintegrations or Decimal('0'))
    deduc = _q(deductions or Decimal('0'))
    resultat_fiscal = _q(resultat_comptable + reint - deduc)
    bareme = is_bareme(resultat_fiscal)
    cm = cotisation_minimale(etat['total_produits'])
    if cm['cm'] > bareme['is_bareme']:
        is_du = cm['cm']
        base_retenue = 'cotisation_minimale'
    else:
        is_du = bareme['is_bareme']
        base_retenue = 'bareme'
    return {
        'exercice': exercice.id,
        'date_debut': exercice.date_debut,
        'date_fin': exercice.date_fin,
        'resultat_comptable': resultat_comptable,
        'reintegrations': reint,
        'deductions': deduc,
        'resultat_fiscal': resultat_fiscal,
        'bareme': bareme,
        'cotisation_minimale': cm,
        'is_du': _q(is_du),
        'base_retenue': base_retenue,
    }


def echeancier_acomptes(company, exercice, *, is_reference=None,
                        validees_seulement=False):
    """Échéancier des 4 acomptes provisionnels d'IS d'un exercice (FG140).

    Chaque acompte = 25 % de l'IS de l'exercice de référence (l'IS « N-1 »,
    c.-à-d. l'IS dû au titre de l'exercice clos précédent). Les acomptes d'un
    exercice ``N`` sont versés avant la fin des 3e, 6e, 9e et 12e mois de
    l'exercice ``N`` (CGI marocain). Si ``is_reference`` n'est pas fourni, on
    estime l'IS de l'exercice courant comme proxy (le fiduciaire ajustera).

    Renvoie ``{'exercice', 'is_reference', 'acomptes': [{'numero',
    'date_echeance', 'montant'}], 'total_acomptes'}``.
    """
    if exercice.company_id != company.id:
        raise ValueError("L'exercice n'appartient pas à cette société.")
    if is_reference is None:
        is_reference = estimer_is(
            company, exercice, validees_seulement=validees_seulement)['is_du']
    is_reference = _q(is_reference)
    unitaire = _q(is_reference / Decimal('4'))
    debut = exercice.date_debut
    acomptes = []
    cumul = Decimal('0')
    for index, mois in enumerate((3, 6, 9, 12), start=1):
        # Le 4e acompte solde l'arrondi pour que la somme = is_reference.
        montant = unitaire if index < 4 else _q(is_reference - cumul)
        cumul += montant
        acomptes.append({
            'numero': index,
            # Échéance = dernier jour du Nᵉ mois de l'exercice (3/6/9/12) ; le
            # Nᵉ mois est à (N−1) mois du mois de début (1er mois = début).
            'date_echeance': _fin_de_mois(debut, mois - 1),
            'montant': montant,
        })
    return {
        'exercice': exercice.id,
        'is_reference': is_reference,
        'acomptes': acomptes,
        'total_acomptes': _q(cumul),
    }


def regularisation_is(company, exercice, *, is_reference=None,
                      reintegrations=None, deductions=None,
                      validees_seulement=False):
    """Régularisation d'IS d'un exercice (FG140).

    Régularisation = IS dû de l'exercice − total des acomptes versés (les 4
    acomptes provisionnels, basés sur l'IS de référence). Positive ⇒ reliquat
    à payer ; négative ⇒ excédent (crédit d'IS imputable / à restituer). Le
    reliquat est exigible avant la fin du 3e mois suivant la clôture.

    Renvoie ``{'exercice', 'is_du', 'total_acomptes', 'regularisation',
    'sens', 'date_limite_paiement'}`` (``sens`` ∈ {'a_payer', 'excedent',
    'solde'}).
    """
    estimation = estimer_is(
        company, exercice, reintegrations=reintegrations, deductions=deductions,
        validees_seulement=validees_seulement)
    is_du = estimation['is_du']
    echeancier = echeancier_acomptes(
        company, exercice, is_reference=is_reference,
        validees_seulement=validees_seulement)
    total_acomptes = echeancier['total_acomptes']
    regularisation = _q(is_du - total_acomptes)
    if regularisation > 0:
        sens = 'a_payer'
    elif regularisation < 0:
        sens = 'excedent'
    else:
        sens = 'solde'
    return {
        'exercice': exercice.id,
        'is_du': is_du,
        'total_acomptes': total_acomptes,
        'regularisation': regularisation,
        'sens': sens,
        'date_limite_paiement': _fin_de_mois(exercice.date_fin, 3),
    }


def aide_calcul_is(company, exercice, *, is_reference=None,
                   reintegrations=None, deductions=None,
                   validees_seulement=False):
    """Synthèse complète de l'aide au calcul de l'IS (FG140) : estimation +
    échéancier des 4 acomptes + régularisation, en un seul appel."""
    estimation = estimer_is(
        company, exercice, reintegrations=reintegrations, deductions=deductions,
        validees_seulement=validees_seulement)
    echeancier = echeancier_acomptes(
        company, exercice, is_reference=is_reference,
        validees_seulement=validees_seulement)
    regularisation = regularisation_is(
        company, exercice, is_reference=is_reference,
        reintegrations=reintegrations, deductions=deductions,
        validees_seulement=validees_seulement)
    return {
        'estimation': estimation,
        'echeancier_acomptes': echeancier,
        'regularisation': regularisation,
    }


def _fin_de_mois(reference, mois_apres_debut):
    """Dernier jour du mois situé ``mois_apres_debut`` mois après ``reference``.

    Ex. 2026-01-01 + 3 mois ⇒ 2026-04-30 ; 2026-12-31 + 3 mois ⇒ 2027-03-31.
    Gère les fins de mois et les changements d'année sans dépendance externe.
    """
    total_mois = (reference.month - 1) + mois_apres_debut
    annee = reference.year + total_mois // 12
    mois = total_mois % 12 + 1
    # Premier jour du mois suivant − 1 jour = dernier jour du mois cible.
    if mois == 12:
        premier_suivant = date(annee + 1, 1, 1)
    else:
        premier_suivant = date(annee, mois + 1, 1)
    return premier_suivant - timedelta(days=1)


# ── FG142 — Trousse liasse fiscale (états de synthèse, paquet DGI) ──────────

# Sections normalisées de la liasse fiscale (ordre figé pour l'export
# multi-sections destiné au fiduciaire / à la DGI).
LIASSE_SECTIONS = ['bilan', 'cpc', 'balance', 'annexe_tva']


def liasse_fiscale(company, exercice, *, validees_seulement=False):
    """Trousse « liasse fiscale » d'un exercice : les états de synthèse en un paquet.

    Assemble — SANS rien recalculer — les états de synthèse déjà produits par les
    sélecteurs existants, tous bornés à l'exercice (``date_debut``/``date_fin``) :

    * ``bilan`` — actif/passif au format CGNC à la clôture (FG114, ``bilan``) ;
    * ``cpc`` — compte de produits & charges de l'exercice (FG113, ``cpc``) ;
    * ``balance`` — balance générale (trial balance) de l'exercice (FG111,
      ``balance_generale``) ;
    * ``annexe_tva`` — relevé de déductions de TVA, l'annexe DGI (FG138,
      ``releve_deductions_tva``).

    Le bilan se lit à la date de clôture (cumul depuis l'ouverture), tandis que le
    CPC, la balance et l'annexe se bornent à l'intervalle de l'exercice — le même
    cadrage que les états standalone, d'où des totaux strictement cohérents avec
    eux. Lecture seule, scopée société ; aucune écriture n'est créée. Renvoie
    ``{'exercice', 'date_debut', 'date_fin', 'sections', 'bilan', 'cpc',
    'balance', 'annexe_tva', 'resultat', 'equilibre'}`` où ``sections`` =
    ``LIASSE_SECTIONS`` (ordre de la trousse).
    """
    date_debut = exercice.date_debut
    date_fin = exercice.date_fin
    # On RÉUTILISE les sélecteurs existants — aucun recalcul ad hoc ici.
    etat_bilan = bilan(
        company, date_fin=date_fin, validees_seulement=validees_seulement)
    etat_cpc = cpc(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement)
    etat_balance = balance_generale(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement)
    annexe_tva = releve_deductions_tva(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement)
    return {
        'exercice': exercice.libelle or str(exercice.pk),
        'date_debut': date_debut.isoformat(),
        'date_fin': date_fin.isoformat(),
        'sections': list(LIASSE_SECTIONS),
        'bilan': etat_bilan,
        'cpc': etat_cpc,
        'balance': etat_balance,
        'annexe_tva': annexe_tva,
        # Indicateurs de tête repris des états (cohérence garantie 1:1).
        'resultat': etat_cpc['resultat'],
        'equilibre': etat_bilan['equilibre'] and etat_balance['equilibree'],
    }


# ── FG145 — Retenue de garantie & cautions bancaires sur marchés ───────────
def retenues_garantie_a_echeance(company, *, jours=30, date_reference=None):
    """RG dont la levée prévue arrive à échéance sous ``jours`` (FG145).

    Liste les ``RetenueGarantie`` ENCORE retenues (non libérées) dont la
    ``date_levee_prevue`` tombe entre ``date_reference`` (défaut = aujourd'hui) et
    ``date_reference + jours``. Les RG en RETARD (levée prévue déjà passée et non
    libérée) sont incluses (elles arrivent « à échéance » au plus tard). Lecture
    seule, scopée société, ordonnée par échéance.
    """
    ref = date_reference or timezone.now().date()
    limite = ref + timedelta(days=int(jours))
    qs = RetenueGarantie.objects.filter(
        company=company,
        statut=RetenueGarantie.Statut.RETENUE,
        date_levee_prevue__isnull=False,
        date_levee_prevue__lte=limite,
    ).order_by('date_levee_prevue', 'id')
    lignes = []
    total = Decimal('0')
    for rg in qs:
        en_retard = rg.date_levee_prevue < ref
        lignes.append({
            'id': rg.id,
            'reference': rg.reference,
            'marche_ref': rg.marche_ref,
            'facture_ref': rg.facture_ref,
            'tiers_nom': rg.tiers_nom,
            'base': rg.base,
            'taux': rg.taux,
            'montant': rg.montant,
            'date_constitution': rg.date_constitution,
            'date_levee_prevue': rg.date_levee_prevue,
            'statut': rg.statut,
            'en_retard': en_retard,
        })
        total += rg.montant or Decimal('0')
    return {
        'date_reference': ref,
        'jours': int(jours),
        'date_limite': limite,
        'lignes': lignes,
        'total_montant': total,
        'nb': len(lignes),
    }


def cautions_a_echeance(company, *, jours=30, date_reference=None):
    """Cautions bancaires ACTIVES arrivant à échéance sous ``jours`` (FG145).

    Liste les ``CautionBancaire`` encore ACTIVES (non mainlevées/restituées) dont
    la ``date_echeance`` tombe entre ``date_reference`` (défaut = aujourd'hui) et
    ``date_reference + jours`` (les échéances déjà dépassées et non levées sont
    incluses). Lecture seule, scopée société, ordonnée par échéance.
    """
    ref = date_reference or timezone.now().date()
    limite = ref + timedelta(days=int(jours))
    qs = CautionBancaire.objects.filter(
        company=company,
        statut=CautionBancaire.Statut.ACTIVE,
        date_echeance__isnull=False,
        date_echeance__lte=limite,
    ).order_by('date_echeance', 'id')
    lignes = []
    total = Decimal('0')
    for c in qs:
        en_retard = c.date_echeance < ref
        lignes.append({
            'id': c.id,
            'reference': c.reference,
            'type_caution': c.type_caution,
            'marche_ref': c.marche_ref,
            'tiers_nom': c.tiers_nom,
            'banque': c.banque,
            'montant': c.montant,
            'date_emission': c.date_emission,
            'date_echeance': c.date_echeance,
            'statut': c.statut,
            'en_retard': en_retard,
        })
        total += c.montant or Decimal('0')
    return {
        'date_reference': ref,
        'jours': int(jours),
        'date_limite': limite,
        'lignes': lignes,
        'total_montant': total,
        'nb': len(lignes),
    }


# ── FG146 — Reconnaissance du revenu par avancement (% completion) ──────────

def avancement_contrat(company, contrat):
    """Synthèse d'avancement et de marge d'un contrat (FG146).

    Renvoie ``{'revenu_total', 'cout_total_estime', 'revenu_reconnu',
    'reste_a_reconnaitre', 'dernier_pourcentage', 'marge_estimee',
    'constats': [...]}``. Lecture seule, scopée société. ``constats`` liste
    chaque arrêté avec son % et le revenu reconnu sur la période (snapshot
    figé).
    """
    constats = list(
        contrat.avancements.order_by('date_arrete', 'id'))
    revenu_reconnu = sum(
        (c.revenu_periode or Decimal('0') for c in constats), Decimal('0'))
    revenu_total = contrat.revenu_total or Decimal('0')
    cout = contrat.cout_total_estime or Decimal('0')
    dernier_pct = constats[-1].pourcentage if constats else Decimal('0')
    return {
        'contrat_id': contrat.id,
        'reference': contrat.reference,
        'libelle': contrat.libelle,
        'methode': contrat.methode,
        'statut': contrat.statut,
        'revenu_total': revenu_total,
        'cout_total_estime': cout,
        'marge_estimee': revenu_total - cout,
        'revenu_reconnu': revenu_reconnu,
        'reste_a_reconnaitre': revenu_total - revenu_reconnu,
        'dernier_pourcentage': dernier_pct,
        'constats': [
            {
                'id': c.id,
                'date_arrete': c.date_arrete,
                'pourcentage': c.pourcentage,
                'cout_engage_cumule': c.cout_engage_cumule,
                'revenu_cumule': c.revenu_cumule,
                'revenu_periode': c.revenu_periode,
                'ecriture_id': c.ecriture_id,
            }
            for c in constats
        ],
        'nb_constats': len(constats),
    }


# ── FG149 — Suivi budget-vs-réalisé ────────────────────────────────────────

def budget_vs_realise(company, budget, *, date_fin=None):
    """Variance budget-vs-réalisé d'un budget annuel (FG149).

    Pour chaque ligne de budget : budget annuel (somme des mois) vs réalisé lu
    du grand livre (solde du compte sur l'année du budget, débit − crédit pour
    les charges, crédit − débit pour les produits). Renvoie
    ``{'annee', 'lignes': [...], 'total_budget', 'total_realise',
    'total_variance'}``. Lecture seule, scopée société.
    """
    annee = budget.annee
    debut = date(annee, 1, 1)
    fin = date_fin or date(annee, 12, 31)
    lignes = []
    total_budget = Decimal('0')
    total_realise = Decimal('0')
    for bl in budget.lignes.select_related('compte', 'centre_cout').all():
        budgete = bl.montant_annuel
        agg = LigneEcriture.objects.filter(
            company=company, compte=bl.compte,
            ecriture__date_ecriture__gte=debut,
            ecriture__date_ecriture__lte=fin,
        )
        if bl.centre_cout_id:
            agg = agg.filter(centre_cout=bl.centre_cout)
        agg = agg.aggregate(debit=Sum('debit'), credit=Sum('credit'))
        debit = agg['debit'] or Decimal('0')
        credit = agg['credit'] or Decimal('0')
        # Charge (classe 6) : solde débiteur ; produit (classe 7) : créditeur.
        if bl.compte.classe == 7:
            realise = credit - debit
        else:
            realise = debit - credit
        variance = realise - budgete
        total_budget += budgete
        total_realise += realise
        lignes.append({
            'id': bl.id,
            'compte_numero': bl.compte.numero,
            'compte_intitule': bl.compte.intitule,
            'centre_cout': bl.centre_cout.code if bl.centre_cout else '',
            'libelle': bl.libelle,
            'budget': budgete,
            'realise': realise,
            'variance': variance,
            'taux_consommation': (
                (realise / budgete * Decimal('100')).quantize(Decimal('0.01'))
                if budgete else Decimal('0')),
        })
    return {
        'budget_id': budget.id,
        'annee': annee,
        'libelle': budget.libelle,
        'lignes': lignes,
        'total_budget': total_budget,
        'total_realise': total_realise,
        'total_variance': total_realise - total_budget,
    }


# ── XACC21 — Contrôle du budget COMPTABLE à l'engagement ───────────────────

def budget_restant(company, *, centre_cout=None, compte=None, periode):
    """Budget COMPTABLE restant pour un centre de coût/compte à une période
    (XACC21), consommable par ``apps.stock``/``apps.rh`` (EN COMPLÉMENT du
    contrôle PROJET FG313, ``installations.selectors`` — jamais dupliqué ici).

    ``periode`` : une ``date`` dans l'année budgétaire visée (le budget de
    l'exercice ``periode.year`` de la société est utilisé — le PLUS RÉCENT si
    plusieurs budgets existent pour cette année). ``centre_cout``/``compte``
    filtrent les ``BudgetLigne`` concernées (au moins l'un des deux requis).
    Renvoie ``None`` si AUCUN budget n'est défini pour cette
    société/année/centre/compte (= aucun contrôle possible, comportement
    actuel intact) ; sinon ``{'budget_id', 'controle', 'montant_budgete',
    'realise', 'restant'}`` où ``restant`` peut être négatif (dépassement).
    Lecture seule, scopée société.
    """
    if centre_cout is None and compte is None:
        raise ValueError("centre_cout ou compte requis pour budget_restant.")
    annee = periode.year
    budget = Budget.objects.filter(
        company=company, annee=annee).order_by('-id').first()
    if budget is None:
        return None
    lignes_qs = budget.lignes.all()
    if centre_cout is not None:
        lignes_qs = lignes_qs.filter(centre_cout=centre_cout)
    if compte is not None:
        lignes_qs = lignes_qs.filter(compte=compte)
    if not lignes_qs.exists():
        return None

    total_budgete = Decimal('0')
    total_realise = Decimal('0')
    debut = date(annee, 1, 1)
    fin = date(annee, 12, 31)
    for bl in lignes_qs.select_related('compte'):
        total_budgete += bl.montant_annuel
        agg = LigneEcriture.objects.filter(
            company=company, compte=bl.compte,
            ecriture__date_ecriture__gte=debut,
            ecriture__date_ecriture__lte=fin,
        )
        if bl.centre_cout_id:
            agg = agg.filter(centre_cout=bl.centre_cout)
        agg = agg.aggregate(debit=Sum('debit'), credit=Sum('credit'))
        debit = agg['debit'] or Decimal('0')
        credit = agg['credit'] or Decimal('0')
        if bl.compte.classe == 7:
            total_realise += credit - debit
        else:
            total_realise += debit - credit
    return {
        'budget_id': budget.id,
        'controle': budget.controle,
        'montant_budgete': total_budgete,
        'realise': total_realise,
        'restant': total_budgete - total_realise,
    }


# ── FG150 — Comptabilité analytique / centres de coût ──────────────────────

def resultat_analytique(company, *, date_debut=None, date_fin=None,
                        validees_seulement=False):
    """Produits − charges ventilés par centre de coût (FG150 + XACC20).

    Agrège les ``LigneEcriture`` de classes 6/7 : une ligne portant une
    ``VentilationAnalytique`` (XACC20) est éclatée AU PRORATA des pourcentages
    de la distribution sur chacun de ses centres ; une ligne SANS ventilation
    retombe sur son ``centre_cout`` simple (FG150, rétro-compatible, comme
    avant XACC20). Renvoie le résultat (produits − charges) par axe
    analytique : ``{'centres': [{'code', 'libelle', 'axe', 'produits',
    'charges', 'resultat'}], 'sans_centre': {...}}``. Lecture seule, scopée
    société.
    """
    qs = _lignes_qs(company, date_debut=date_debut, date_fin=date_fin,
                    validees_seulement=validees_seulement).filter(
        compte__classe__in=[6, 7]).select_related(
        'centre_cout', 'compte').prefetch_related(
        'ventilation_analytique__distributions__centre_cout')

    centres = {}
    sans_centre = {'produits': Decimal('0'), 'charges': Decimal('0')}

    def _cible(cc):
        if cc is None:
            return sans_centre
        return centres.setdefault(cc.id, {
            'code': cc.code, 'libelle': cc.libelle, 'axe': cc.axe,
            'produits': Decimal('0'), 'charges': Decimal('0'),
        })

    for ligne in qs:
        montant_net = (ligne.credit or Decimal('0')) - (ligne.debit or Decimal('0'))
        classe = ligne.compte.classe
        ventilation = getattr(ligne, 'ventilation_analytique', None)
        distributions = list(ventilation.distributions.all()) if ventilation else []
        if distributions:
            for d in distributions:
                part = (montant_net * d.pourcentage / Decimal('100'))
                cible = _cible(d.centre_cout)
                if classe == 7:
                    cible['produits'] += part
                else:
                    cible['charges'] += -part
        else:
            cible = _cible(ligne.centre_cout)
            if classe == 7:
                cible['produits'] += montant_net
            else:
                cible['charges'] += -montant_net

    liste = []
    for data in centres.values():
        data['resultat'] = data['produits'] - data['charges']
        liste.append(data)
    liste.sort(key=lambda d: d['code'])
    sans_centre['resultat'] = (
        sans_centre['produits'] - sans_centre['charges'])
    return {
        'centres': liste,
        'sans_centre': sans_centre,
    }


# ── FG151 — Tableau de bord financier directeur ────────────────────────────

def pilotage_financier(company, *, date_debut=None, date_fin=None):
    """Cockpit directeur : résultat, trésorerie, DSO/DPO, marge brute (FG151).

    Distinct de FG45 (quote-to-cash) : agrège des indicateurs financiers du
    grand livre. Renvoie ``{'resultat_periode', 'tresorerie', 'marge_brute',
    'marge_brute_pct', 'encours_clients', 'encours_fournisseurs', 'dso',
    'dpo', 'top_encours_clients'}``. Lecture seule, scopée société.

    DSO (Days Sales Outstanding) ≈ encours clients / CA × jours de période ;
    DPO (Days Payable Outstanding) ≈ encours fournisseurs / achats × jours.
    """
    ref = _as_date(date_fin) or timezone.now().date()
    debut = _as_date(date_debut) or date(ref.year, 1, 1)
    nb_jours = max(1, (ref - debut).days + 1)

    compte_resultat = cpc(company, date_debut=debut, date_fin=ref)
    resultat = compte_resultat['resultat']
    ca = compte_resultat['total_produits']
    achats = compte_resultat['total_charges']
    marge_brute = ca - achats
    marge_pct = (
        (marge_brute / ca * Decimal('100')).quantize(Decimal('0.01'))
        if ca else Decimal('0'))

    # Trésorerie = solde net des comptes de classe 5 à la date.
    treso = LigneEcriture.objects.filter(
        company=company, compte__classe=5,
        ecriture__date_ecriture__lte=ref,
    ).aggregate(debit=Sum('debit'), credit=Sum('credit'))
    tresorerie = (treso['debit'] or Decimal('0')) - (
        treso['credit'] or Decimal('0'))

    # Encours clients (3421) / fournisseurs (4411) à la date.
    def _encours(numero, sens_actif=True):
        agg = LigneEcriture.objects.filter(
            company=company, compte__numero=numero,
            ecriture__date_ecriture__lte=ref,
        ).aggregate(debit=Sum('debit'), credit=Sum('credit'))
        d = agg['debit'] or Decimal('0')
        c = agg['credit'] or Decimal('0')
        return (d - c) if sens_actif else (c - d)

    encours_clients = _encours('3421', sens_actif=True)
    encours_fourn = _encours('4411', sens_actif=False)

    dso = (
        (encours_clients / ca * nb_jours).quantize(Decimal('1'))
        if ca > 0 else Decimal('0'))
    dpo = (
        (encours_fourn / achats * nb_jours).quantize(Decimal('1'))
        if achats > 0 else Decimal('0'))

    # Top encours clients par tiers (auxiliaire 3421 non lettré).
    top = LigneEcriture.objects.filter(
        company=company, compte__numero='3421', lettrage='',
        ecriture__date_ecriture__lte=ref,
    ).values('tiers_id').annotate(
        debit=Sum('debit'), credit=Sum('credit'))
    top_clients = []
    for row in top:
        solde = (row['debit'] or Decimal('0')) - (
            row['credit'] or Decimal('0'))
        if solde > 0:
            top_clients.append({
                'tiers_id': row['tiers_id'],
                'encours': solde,
            })
    top_clients.sort(key=lambda d: d['encours'], reverse=True)

    return {
        'date_debut': debut,
        'date_fin': ref,
        'resultat_periode': resultat,
        'chiffre_affaires': ca,
        'tresorerie': tresorerie,
        'marge_brute': marge_brute,
        'marge_brute_pct': marge_pct,
        'encours_clients': encours_clients,
        'encours_fournisseurs': encours_fourn,
        'dso': dso,
        'dpo': dpo,
        'top_encours_clients': top_clients[:10],
    }


# ── FG153 — Consolidation multi-entités ────────────────────────────────────

def cpc_consolide(company, *, date_debut=None, date_fin=None):
    """CPC consolidé du périmètre d'une société tête de groupe (FG153).

    Somme les CPC de CHAQUE entité du périmètre (tête + membres actifs), pondéré
    par le pourcentage d'intérêt pour la mise en équivalence (intégration
    globale = 100 %). NB : l'élimination des opérations inter-co fines est hors
    périmètre de ce premier agrégat (un marqueur ``inter_co`` futur l'affinera).
    Lecture seule. Renvoie ``{'entites': [...], 'total_produits',
    'total_charges', 'resultat'}``.
    """
    entites = [{
        'company_id': company.id,
        'pourcentage': Decimal('100.00'),
        'tete': True,
    }]
    membres = EntiteConsolidation.objects.filter(
        company=company, actif=True).select_related('entite')
    for m in membres:
        pct = (
            m.pourcentage_interet
            if m.methode == EntiteConsolidation.Methode.MISE_EN_EQUIVALENCE
            else Decimal('100.00'))
        entites.append({
            'company_id': m.entite_id,
            'company_obj': m.entite,
            'pourcentage': pct,
            'methode': m.methode,
            'tete': False,
        })
    total_produits = Decimal('0')
    total_charges = Decimal('0')
    detail = []
    for ent in entites:
        co = company if ent['tete'] else ent.get('company_obj')
        compte = cpc(co, date_debut=date_debut, date_fin=date_fin)
        pct = ent['pourcentage']
        prod = (compte['total_produits'] * pct / Decimal('100'))
        chg = (compte['total_charges'] * pct / Decimal('100'))
        total_produits += prod
        total_charges += chg
        detail.append({
            'company_id': ent['company_id'],
            'pourcentage': pct,
            'produits': prod,
            'charges': chg,
            'resultat': prod - chg,
        })
    return {
        'tete_groupe': company.id,
        'entites': detail,
        'total_produits': total_produits,
        'total_charges': total_charges,
        'resultat': total_produits - total_charges,
    }


# ── COMPTA37 — Export fiduciaire (Sage / CEGID) ────────────────────────────
#
# Export d'échange comptable OFFLINE destiné au cabinet fiduciaire : une ligne
# par ``LigneEcriture`` de l'exercice, dans un jeu de colonnes reconnu par les
# logiciels de tenue (Sage / CEGID). Aucun appel externe, aucune API payante :
# on produit un fichier téléchargeable à partir des seuls modèles comptables via
# les données déjà servies par ``export_fec`` (grand livre borné à l'exercice).
#
# Le format PNM Sage (« journal d'import ») est un enregistrement à colonnes
# fixes : code journal, date, compte général, compte auxiliaire, référence
# pièce, libellé, sens (D/C), montant. On expose ce même jeu de colonnes en
# délimité (point-virgule) — le pivot que Sage comme CEGID savent réimporter —
# et on l'accompagne d'une synthèse « liasse » (produits/charges/résultat) pour
# le dossier fiduciaire.
FIDUCIAIRE_COLUMNS = [
    'CodeJournal', 'DateEcriture', 'CompteGeneral', 'CompteAuxiliaire',
    'RefPiece', 'Libelle', 'Sens', 'Montant', 'Lettrage',
]


def _fiduciaire_montant(valeur):
    """Montant fiduciaire : décimale à virgule, deux décimales (jamais vide)."""
    return f'{(valeur or Decimal("0")):.2f}'.replace('.', ',')


def export_fiduciaire(company, exercice, *, validees_seulement=False):
    """Export fiduciaire Sage/CEGID des écritures d'un exercice (COMPTA37).

    Réutilise ``export_fec`` (mêmes lignes, même bornage à l'exercice, même
    ordre auditable, même scoping société) et les reprojette dans le jeu de
    colonnes d'échange fiduciaire ``FIDUCIAIRE_COLUMNS`` : une ligne par
    mouvement, avec un ``Sens`` explicite ``D``/``C`` et un ``Montant`` unique
    (le débit si sens D, sinon le crédit) — la forme qu'attendent les journaux
    d'import Sage/CEGID. Y est jointe une ``synthese`` (produits/charges/
    résultat de l'exercice, repris du CPC) pour le dossier de liasse.

    Lecture seule, scopée société ; aucune écriture n'est créée ni modifiée.
    Aucune donnée d'achat/marge n'y figure. Renvoie ``{'format', 'exercice',
    'date_debut', 'date_fin', 'columns', 'lignes', 'total_debit',
    'total_credit', 'equilibre', 'nb_lignes', 'synthese'}``.
    """
    fec = export_fec(
        company, exercice, validees_seulement=validees_seulement)
    lignes = []
    for src in fec['lignes']:
        # Sage/CEGID veulent un montant unique + un sens. Le FEC porte débit ET
        # crédit formatés ; on retrouve le montant significatif via le brut.
        debit = _fec_to_decimal(src['Debit'])
        credit = _fec_to_decimal(src['Credit'])
        sens = 'D' if debit >= credit else 'C'
        montant = debit if sens == 'D' else credit
        lignes.append({
            'CodeJournal': src['JournalCode'],
            'DateEcriture': src['EcritureDate'],
            'CompteGeneral': src['CompteNum'],
            'CompteAuxiliaire': src['CompAuxNum'],
            'RefPiece': src['PieceRef'],
            'Libelle': src['EcritureLib'],
            'Sens': sens,
            'Montant': _fiduciaire_montant(montant),
            'Lettrage': src['EcritureLet'],
        })
    etat_cpc = cpc(
        company, date_debut=exercice.date_debut, date_fin=exercice.date_fin,
        validees_seulement=validees_seulement)
    return {
        'format': 'sage-cegid',
        'exercice': fec['exercice'],
        'date_debut': fec['date_debut'],
        'date_fin': fec['date_fin'],
        'columns': list(FIDUCIAIRE_COLUMNS),
        'lignes': lignes,
        'total_debit': fec['total_debit'],
        'total_credit': fec['total_credit'],
        'equilibre': fec['equilibre'],
        'nb_lignes': len(lignes),
        'synthese': {
            'total_produits': etat_cpc['total_produits'],
            'total_charges': etat_cpc['total_charges'],
            'resultat': etat_cpc['resultat'],
        },
    }


# ── XACC15 — Charges constatées d'avance : solde restant à étaler ─────────

def solde_charges_constatees_avance(company, *, date_fin=None):
    """Rapport du solde 3491 restant à étaler par charge, à une date donnée
    (XACC15). Pour chaque ``ChargeConstateeAvance`` de la société : montant
    total, Σ des dotations postées jusqu'à ``date_fin`` (défaut aujourd'hui),
    et solde restant = montant total − dotations postées. Renvoie
    ``{'charges': [...], 'total_restant': Decimal}``. Lecture seule.
    """
    date_fin = date_fin or timezone.localdate()
    charges = ChargeConstateeAvance.objects.filter(
        company=company).prefetch_related('dotations').order_by('-date_debut', '-id')
    resultat = []
    total_restant = Decimal('0')
    for charge in charges:
        dote = sum(
            (d.montant for d in charge.dotations.all()
             if d.posted and d.date_dotation <= date_fin),
            Decimal('0'))
        restant = (charge.montant_total or Decimal('0')) - dote
        if restant < 0:
            restant = Decimal('0')
        total_restant += restant
        resultat.append({
            'id': charge.id,
            'reference': charge.reference,
            'libelle': charge.libelle,
            'montant_total': charge.montant_total,
            'dote': dote,
            'solde_restant': restant,
        })
    return {'charges': resultat, 'total_restant': total_restant}


# ── XACC17 — Table de taux de change ────────────────────────────────────────

def taux_du_jour(company, devise, une_date=None):
    """Taux de change ``devise`` → MAD applicable à ``une_date`` (XACC17).

    Renvoie le ``TauxDevise`` le PLUS RÉCENT dont ``date_taux`` est
    antérieure ou égale à ``une_date`` (défaut aujourd'hui) — ou ``None`` si
    aucune table n'existe pour cette devise/société (repli MAD/1 intact côté
    appelant). MAD est toujours 1:1 (jamais de table nécessaire). Lecture
    seule, scopée société.
    """
    devise = (devise or 'MAD').upper()
    if devise == 'MAD':
        return None
    une_date = une_date or timezone.localdate()
    return TauxDevise.objects.filter(
        company=company, devise=devise, date_taux__lte=une_date,
    ).order_by('-date_taux').first()


# ── XACC19 — Générateur d'états financiers personnalisés ───────────────────

class FormuleEtatInvalideError(Exception):
    """Formule de ligne d'état personnalisé invalide (terme non reconnu)."""


def _parser_formule(formule):
    """Parse ``formule`` (« +70,+71,-60 ») en liste de ``(signe, prefixe)``.

    Un terme valide commence par ``+`` ou ``-`` suivi d'un préfixe de compte
    non vide (chiffres). Lève ``FormuleEtatInvalideError`` si un terme est mal
    formé — le service appelant transforme ça en 400 explicite.
    """
    termes = []
    for brut in (formule or '').split(','):
        terme = brut.strip()
        if not terme:
            continue
        signe = terme[0]
        if signe not in ('+', '-'):
            raise FormuleEtatInvalideError(
                f"Terme invalide « {terme} » : doit commencer par + ou -.")
        prefixe = terme[1:].strip()
        if not prefixe or not prefixe.isdigit():
            raise FormuleEtatInvalideError(
                f"Terme invalide « {terme} » : préfixe de compte manquant "
                "ou non numérique.")
        termes.append((1 if signe == '+' else -1, prefixe))
    if not termes:
        raise FormuleEtatInvalideError("La formule ne contient aucun terme.")
    return termes


def _evaluer_formule_sur_balance(formule, balance_lignes):
    """Évalue une formule sur les lignes d'une ``balance_generale`` (pur calcul).

    Chaque terme ``(signe, prefixe)`` somme le SOLDE (débiteur − créditeur,
    signé naturel du compte) de tous les comptes dont le numéro commence par
    ``prefixe``, multiplié par ``signe``. Renvoie un ``Decimal``.
    """
    termes = _parser_formule(formule)
    total = Decimal('0')
    for signe, prefixe in termes:
        for ligne in balance_lignes:
            if ligne['numero'].startswith(prefixe):
                solde = ligne['solde_debiteur'] - ligne['solde_crediteur']
                total += signe * solde
    return total


def evaluer_etat_personnalise(etat, *, colonnes_override=None):
    """Évalue un ``EtatPersonnalise`` : une valeur par (ligne, colonne) — XACC19.

    Pour chaque colonne (période, comparatif N-1, budget, écart %), calcule la
    balance générale de la période correspondante puis évalue la formule de
    chaque ligne TOTAL dessus (une ligne TITRE n'a aucune valeur). Une formule
    invalide lève ``FormuleEtatInvalideError`` (le service/la vue la
    transforme en 400 explicite). Sans N-1 disponible (colonne comparatif hors
    de toute donnée), la valeur est simplement 0 (jamais d'erreur). Renvoie
    ``{'lignes': [{'id', 'libelle', 'type_ligne', 'valeurs': {colonne_id: val}}],
    'colonnes': [...]}``.
    """
    company = etat.company
    colonnes = list(colonnes_override or etat.colonnes.all().order_by('ordre', 'id'))
    balances_par_colonne = {}
    for colonne in colonnes:
        if colonne.type_colonne == 'budget':
            # Colonne budget : valeur = somme des montants annuels du budget
            # référencé, appliquée directement (pas de formule sur la balance).
            balances_par_colonne[colonne.id] = None
            continue
        date_debut, date_fin = colonne.date_debut, colonne.date_fin
        if colonne.type_colonne == 'comparatif_n1' and date_debut and date_fin:
            try:
                date_debut = date_debut.replace(year=date_debut.year - 1)
                date_fin = date_fin.replace(year=date_fin.year - 1)
            except ValueError:
                # 29 février d'une année non bissextile : recule d'un jour.
                from datetime import timedelta
                date_debut = date_debut.replace(
                    year=date_debut.year - 1, day=28) if date_debut.month == 2 else date_debut
                date_fin = date_fin - timedelta(days=1)
        balance = balance_generale(company, date_debut=date_debut, date_fin=date_fin)
        balances_par_colonne[colonne.id] = balance['lignes']

    lignes_resultat = []
    for ligne in etat.lignes.all().order_by('ordre', 'id'):
        valeurs = {}
        if ligne.type_ligne == 'total':
            for colonne in colonnes:
                if colonne.type_colonne == 'budget':
                    if colonne.budget_id:
                        total = BudgetLigne.objects.filter(
                            budget_id=colonne.budget_id).aggregate(
                            **{f'm{i:02d}': Sum(f'm{i:02d}') for i in range(1, 13)})
                        valeurs[colonne.id] = sum(
                            (total.get(f'm{i:02d}') or Decimal('0') for i in range(1, 13)),
                            Decimal('0'))
                    else:
                        valeurs[colonne.id] = Decimal('0')
                    continue
                balance_lignes = balances_par_colonne.get(colonne.id) or []
                valeurs[colonne.id] = _evaluer_formule_sur_balance(
                    ligne.formule, balance_lignes)
        lignes_resultat.append({
            'id': ligne.id,
            'libelle': ligne.libelle,
            'type_ligne': ligne.type_ligne,
            'valeurs': valeurs,
        })
    return {
        'colonnes': [
            {'id': c.id, 'libelle': c.libelle, 'type_colonne': c.type_colonne}
            for c in colonnes
        ],
        'lignes': lignes_resultat,
    }


# ── XACC24 — Validation RIB (comptes de trésorerie) ────────────────────────

def comptes_tresorerie_rib_invalides(company):
    """Liste les ``CompteTresorerie`` actifs dont le RIB porte une clé fausse
    (XACC24), en WARNING pur — jamais un blocage de saisie historique. Un RIB
    vide n'est PAS signalé (compte sans RIB renseigné, cas normal). Renvoie
    une liste de ``{'id', 'libelle', 'rib', 'erreurs'}``. Lecture seule.
    """
    from core.rib import valider_rib

    resultat = []
    for compte in CompteTresorerie.objects.filter(company=company, actif=True):
        if not (compte.rib or '').strip():
            continue
        diagnostic = valider_rib(compte.rib)
        if not diagnostic['valide']:
            resultat.append({
                'id': compte.id, 'libelle': compte.libelle,
                'rib': compte.rib, 'erreurs': diagnostic['erreurs'],
            })
    return resultat


# ── XPAI25 — Indemnités chantier remboursables via la paie ─────────────────

def indemnites_chantier_remboursables_par_paie(
        company, employe_user_id, date_debut, date_fin):
    """Indemnités chantier VALIDÉES non payées d'un employé sur une période.

    Sélecteur cross-app fin (XPAI25) : la paie appelle CE sélecteur pour
    lister les ``IndemniteChantier`` (FG136) éligibles à un remboursement via
    le bulletin de salaire — validées (``statut == VALIDEE``, jamais déjà
    remboursées, ni côté paie ni côté trésorerie) dont ``date_deplacement``
    tombe dans ``[date_debut, date_fin]``. Jamais ``compta.models`` importé
    hors de ce module (lecture seule, cadrée société). Renvoie un queryset.
    """
    return (
        IndemniteChantier.objects
        .filter(
            company=company, employe_id=employe_user_id,
            statut=IndemniteChantier.Statut.VALIDEE,
            date_deplacement__gte=date_debut, date_deplacement__lte=date_fin,
        )
        .order_by('date_deplacement', 'id')
    )


# ── XCTR14 — Résolution du compte portail client par token (lecture seule) ──

def compte_portail_par_token(token):
    """Résout un ``ComptePortailClient`` ACTIF par son ``token_acces`` (FG228).

    Point d'entrée LECTURE SEULE pour les apps consommatrices du portail
    tokenisé existant (ex. ``apps.contrats`` — XCTR14) : jamais un import du
    modèle ``ComptePortailClient`` en dehors de ``compta``. Renvoie ``None``
    si le token est vide, inconnu, ou correspond à un compte inactif — sans
    distinguer les deux cas (aucune fuite d'existence du token)."""
    if not token:
        return None
    from .models import ComptePortailClient

    return (
        ComptePortailClient.objects
        .filter(token_acces=token, actif=True)
        .select_related('client')
        .first()
    )


# ── XACC26 — État récapitulatif des provisions (dotations/reprises) ────────

def etat_provisions(company, *, date_debut=None, date_fin=None, nature=None):
    """Mouvements de provisions (XACC26) de la période, groupés par nature.

    Liste chaque ``Provision`` dont la dotation OU la dernière reprise tombe
    dans ``[date_debut, date_fin]`` (bornes optionnelles), avec son solde
    courant. Renvoie un dict ``{nature: {'label', 'lignes': [...], 'total_dotation',
    'total_repris', 'total_solde'}}``. Lecture seule ; company-scopé.
    """
    date_debut = _as_date(date_debut)
    date_fin = _as_date(date_fin)
    qs = Provision.objects.filter(company=company)
    if nature:
        qs = qs.filter(nature=nature)
    if date_debut:
        qs = qs.filter(
            Q(date_dotation__gte=date_debut) |
            Q(date_derniere_reprise__gte=date_debut))
    if date_fin:
        qs = qs.filter(
            Q(date_dotation__lte=date_fin) |
            Q(date_derniere_reprise__lte=date_fin))
    result = {}
    for prov in qs.order_by('nature', 'date_dotation', 'id'):
        bucket = result.setdefault(prov.nature, {
            'label': prov.get_nature_display(),
            'lignes': [],
            'total_dotation': Decimal('0'),
            'total_repris': Decimal('0'),
            'total_solde': Decimal('0'),
        })
        bucket['lignes'].append({
            'id': prov.id,
            'reference': prov.reference,
            'motif': prov.motif,
            'date_dotation': prov.date_dotation,
            'montant_dotation': prov.montant_dotation,
            'montant_repris': prov.montant_repris,
            'solde': prov.solde,
            'date_derniere_reprise': prov.date_derniere_reprise,
        })
        bucket['total_dotation'] += prov.montant_dotation or Decimal('0')
        bucket['total_repris'] += prov.montant_repris or Decimal('0')
        bucket['total_solde'] += prov.solde
    return result


# ── XACC28 — Frais refacturables non facturés (billable expenses) ─────────

def frais_refacturables_non_factures(company, *, client_id=None):
    """Notes de frais refacturables VALIDÉES pas encore refacturées (XACC28).

    ``client_id`` (optionnel) filtre sur le client déjà rattaché à la note ;
    sans filtre, renvoie toutes les notes refacturables en attente, tous
    clients confondus. Lecture seule ; company-scopé."""
    qs = NoteFrais.objects.filter(
        company=company, refacturable=True,
        statut=NoteFrais.Statut.VALIDEE,
        facture_refacturation_id__isnull=True,
    )
    if client_id:
        qs = qs.filter(client_refacturation_id=client_id)
    return qs.order_by('date_frais', 'id')


# ── ZACC7 — Analyse des frais (pivot employé × catégorie × période) ───────

def analyse_notes_frais(company, *, date_debut=None, date_fin=None,
                        group_by='employe'):
    """ZACC7 — Agrège les ``NoteFrais`` (non brouillon) de la période par
    ``group_by`` ∈ {'employe', 'categorie', 'mois'} — le pivot « Expense
    Analysis » qui manquait (l'écran ne listait que les notes une par une).

    Renvoie ``{'lignes': [{'cle', 'libelle', 'total', 'nombre',
    'hors_politique_total'}], 'total_general'}`` — ``hors_politique_total``
    (XACC27, best-effort : 0 si le champ est absent d'anciennes notes) est
    la part des montants flaggés hors politique dans ce groupe. Exclut les
    notes ``brouillon`` (jamais soumises — pas encore une dépense engagée
    validable). Lecture seule ; company-scopée."""
    qs = (NoteFrais.objects
          .filter(company=company)
          .exclude(statut=NoteFrais.Statut.BROUILLON)
          .select_related('employe'))
    if date_debut:
        qs = qs.filter(date_frais__gte=_as_date(date_debut))
    if date_fin:
        qs = qs.filter(date_frais__lte=_as_date(date_fin))

    def _cle_libelle(note):
        if group_by == 'categorie':
            return note.categorie, note.get_categorie_display()
        if group_by == 'mois':
            mois = note.date_frais.strftime('%Y-%m') if note.date_frais else ''
            return mois, mois
        # défaut : 'employe'
        emp = note.employe
        nom = getattr(emp, 'get_full_name', lambda: '')() or (
            getattr(emp, 'username', '') if emp else '')
        return (emp.id if emp else None), (nom or '—')

    buckets = {}
    total_general = Decimal('0')
    for note in qs:
        cle, libelle = _cle_libelle(note)
        bucket = buckets.setdefault(cle, {
            'cle': cle, 'libelle': libelle, 'total': Decimal('0'),
            'nombre': 0, 'hors_politique_total': Decimal('0'),
        })
        montant = note.montant or Decimal('0')
        bucket['total'] += montant
        bucket['nombre'] += 1
        if getattr(note, 'hors_politique', False):
            bucket['hors_politique_total'] += montant
        total_general += montant

    lignes = sorted(
        buckets.values(), key=lambda b: b['total'], reverse=True)
    return {'lignes': lignes, 'total_general': total_general}


# ── XACC29 — Rapport de continuité des séquences (gap detection) ──────────

_SEQ_SUFFIX_RE = re.compile(r'^(.*?)-(\d+)$')


def _extraire_bucket_numero(reference):
    """Sépare ``reference`` en (radical, numéro) via le suffixe ``-NNNN``.

    Renvoie ``(None, None)`` si la référence n'a pas de suffixe numérique
    reconnaissable (jamais bloquant : la référence est alors simplement
    ignorée du contrôle de continuité)."""
    if not reference:
        return None, None
    m = _SEQ_SUFFIX_RE.match(reference)
    if not m:
        return None, None
    radical, numero = m.group(1), m.group(2)
    try:
        return radical, int(numero)
    except ValueError:
        return None, None


def _trous_pour_references(references, *, source_label):
    """Groupe ``references`` par radical (préfixe + éventuel segment période)
    et liste les numéros MANQUANTS entre le min et le max observés par
    groupe. Renvoie une liste de dicts ``{source, radical, plage, manquants}``
    — une entrée par radical avec au moins un trou (radical continu = omis)."""
    buckets = {}
    for ref in references:
        radical, numero = _extraire_bucket_numero(ref)
        if radical is None:
            continue
        buckets.setdefault(radical, set()).add(numero)
    rapport = []
    for radical, numeros in sorted(buckets.items()):
        lo, hi = min(numeros), max(numeros)
        manquants = sorted(set(range(lo, hi + 1)) - numeros)
        if manquants:
            rapport.append({
                'source': source_label,
                'journal': radical,
                'plage': [lo, hi],
                'manquants': manquants,
            })
    return rapport


def trous_sequences(company, *, exercice=None):
    """XACC29 — Rapport de continuité des numéros de pièces (audit marocain).

    Balaie les factures ventes (``ventes.selectors.references_factures``), les
    pièces comptables par journal (``EcritureComptable.reference`` de cette
    société — même app, lecture directe) et les avoirs
    (``ventes.selectors.references_avoirs``) — jamais un import de
    ``ventes.models``. Extrait le compteur final de chaque référence
    (suffixe ``-NNNN``) et liste, par radical (préfixe + période), les
    numéros manquants entre le plus petit et le plus grand observés. Une
    séquence sans trou n'apparaît pas dans le rapport (rapport vide = tout
    continu). ``exercice`` est actuellement ignoré (réservé, toutes les
    pièces de la société sont balayées — filtrage par exercice non câblé
    faute de champ d'exercice direct sur ``EcritureComptable``). Lecture
    seule ; company-scopé (jamais de fuite cross-company, les sélecteurs
    sous-jacents filtrent déjà par société)."""
    from apps.ventes import selectors as ventes_selectors

    rapport = []
    rapport += _trous_pour_references(
        ventes_selectors.references_factures(company), source_label='factures')
    rapport += _trous_pour_references(
        ventes_selectors.references_avoirs(company), source_label='avoirs')
    references_pieces = list(
        EcritureComptable.objects.filter(company=company)
        .exclude(reference='')
        .values_list('reference', flat=True)
    )
    rapport += _trous_pour_references(
        references_pieces, source_label='pieces_comptables')
    return rapport


# ── YLEDG13 — Rapprochement auxiliaire ↔ GL (tie-out AR/AP) ────────────────
# Compare l'encours DOCUMENTAIRE (lu via ventes.selectors / stock.selectors,
# jamais leurs models) au solde GL non lettré par tiers (3421/4411) — preuve
# que les deux systèmes restent égaux une fois YLEDG1/2 câblés. Lecture
# seule, scopée société.

def _encours_gl_par_tiers(company, compte_numero, *, tiers_type,
                          date=None):
    """Solde GL non lettré par ``tiers_id`` d'un compte de tiers donné."""
    qs = LigneEcriture.objects.filter(
        company=company, compte__numero=compte_numero, lettrage='',
        tiers_type=tiers_type, tiers_id__isnull=False)
    if date:
        qs = qs.filter(ecriture__date_ecriture__lte=date)
    par_tiers = {}
    for ligne in qs:
        tid = ligne.tiers_id
        par_tiers.setdefault(tid, Decimal('0'))
        # Client (actif) : débit − crédit. Fournisseur (passif) : crédit −
        # débit (inversé en aval selon l'appelant).
        par_tiers[tid] += (ligne.debit or Decimal('0')) - \
            (ligne.credit or Decimal('0'))
    return par_tiers


def rapprochement_auxiliaire_clients(company, date=None):
    """Compare l'encours documentaire clients (ventes) au solde GL 3421 non
    lettré, par tiers. Renvoie ``{'lignes': [...], 'ecart_total'}`` où chaque
    ligne est ``{'tiers_id', 'nom', 'encours_documentaire', 'solde_gl',
    'ecart', 'references'}`` — seuls les tiers en écart (≠ 0, tolérance 1
    centime) apparaissent. Un document jamais comptabilisé (toggle OFF, ou
    facture jamais émise) laisse le GL à 0 pendant que le documentaire porte
    l'encours → apparaît en écart avec sa référence. Une écriture manuelle sur
    3421 sans document source (donc absente de l'encours documentaire)
    apparaît symétriquement. Lecture seule."""
    from apps.ventes import selectors as ventes_selectors

    documentaire = {
        e['tiers_id']: e for e in ventes_selectors.encours_clients_par_tiers(
            company)
    }
    gl = _encours_gl_par_tiers(company, '3421', tiers_type='client',
                               date=date)
    tiers_ids = set(documentaire) | set(gl)
    lignes = []
    ecart_total = Decimal('0')
    for tid in tiers_ids:
        doc = documentaire.get(tid)
        doc_montant = doc['encours'] if doc else Decimal('0')
        gl_montant = gl.get(tid, Decimal('0'))
        ecart = doc_montant - gl_montant
        if abs(ecart) <= Decimal('0.01'):
            continue
        lignes.append({
            'tiers_id': tid,
            'nom': doc['nom'] if doc else '',
            'encours_documentaire': doc_montant,
            'solde_gl': gl_montant,
            'ecart': ecart,
            'references': doc['references'] if doc else [],
        })
        ecart_total += ecart
    lignes.sort(key=lambda e: abs(e['ecart']), reverse=True)
    return {'lignes': lignes, 'ecart_total': ecart_total}


def rapprochement_auxiliaire_fournisseurs(company, date=None):
    """Miroir AP de ``rapprochement_auxiliaire_clients`` : compare l'encours
    documentaire fournisseurs (stock) au solde GL 4411 non lettré, par tiers.
    Le compte 4411 est un PASSIF (solde naturel créditeur) : le GL est lu
    crédit − débit pour être homogène au sens « montant dû » du documentaire.
    Lecture seule."""
    from apps.stock import selectors as stock_selectors

    documentaire = {
        e['tiers_id']: e
        for e in stock_selectors.encours_fournisseurs_par_tiers(company)
    }
    gl_actif_sens = _encours_gl_par_tiers(
        company, '4411', tiers_type='fournisseur', date=date)
    # _encours_gl_par_tiers calcule débit − crédit (sens actif) ; un compte
    # fournisseur (passif) veut crédit − débit — on inverse le signe ici
    # plutôt que dupliquer la fonction.
    gl = {tid: -montant for tid, montant in gl_actif_sens.items()}
    tiers_ids = set(documentaire) | set(gl)
    lignes = []
    ecart_total = Decimal('0')
    for tid in tiers_ids:
        doc = documentaire.get(tid)
        doc_montant = doc['encours'] if doc else Decimal('0')
        gl_montant = gl.get(tid, Decimal('0'))
        ecart = doc_montant - gl_montant
        if abs(ecart) <= Decimal('0.01'):
            continue
        lignes.append({
            'tiers_id': tid,
            'nom': doc['nom'] if doc else '',
            'encours_documentaire': doc_montant,
            'solde_gl': gl_montant,
            'ecart': ecart,
            'references': doc['references'] if doc else [],
        })
        ecart_total += ecart
    lignes.sort(key=lambda e: abs(e['ecart']), reverse=True)
    return {'lignes': lignes, 'ecart_total': ecart_total}


def exposition_69_21(company, periode=None):
    """XFAC2 — Conformité loi 69-21 (délais de paiement légaux fournisseurs).

    Thin wrapper company-scopé sur ``stock.selectors.exposition_69_21``
    (lecture des factures fournisseur via le sélecteur de l'app cible —
    jamais un import de ``apps.stock.models`` ici). ``periode`` optionnel
    (``'YYYY-MM'``) borne au trimestre civil pour la déclaration DGI.
    Renvoie ``{'lignes': [...], 'total_amende_estimee': Decimal}``."""
    from apps.stock import selectors as stock_selectors

    lignes = stock_selectors.exposition_69_21(company, periode=periode)
    total = sum((ligne['amende_estimee'] for ligne in lignes), Decimal('0'))
    return {'lignes': lignes, 'total_amende_estimee': total}


_ICE_RE = re.compile(r'^\d{15}$')


def controle_identifiants_tiers(company):
    """ZACC14 — Liste les tiers (clients ENTREPRISE + fournisseurs) dont
    l'ICE est vide ou de format invalide (≠ 15 chiffres) — miroir marocain
    du contrôle VIES, utile pour la conformité facture/déclaration DGI et
    l'e-invoicing. Lecture via ``apps.crm.selectors`` /
    ``apps.stock.selectors`` (jamais un import de leurs modèles). Pas de
    service externe de vérification (aucune API publique ICE au Maroc à ce
    jour) : contrôle de FORMAT uniquement.

    Renvoie ``{'clients': [...], 'fournisseurs': [...]}`` où chaque entrée
    est ``{'id', 'nom', 'ice', 'if_fiscal', 'motif'}`` — motif ∈
    {'ice_absent', 'ice_invalide'}. Les tiers conformes sont exclus."""
    from apps.crm import selectors as crm_selectors
    from apps.stock import selectors as stock_selectors

    def _motif(ice):
        if not ice:
            return 'ice_absent'
        if not _ICE_RE.match(ice):
            return 'ice_invalide'
        return None

    clients = []
    for tiers in crm_selectors.clients_pour_controle_ice(company):
        motif = _motif(tiers['ice'])
        if motif:
            clients.append({**tiers, 'motif': motif})

    fournisseurs = []
    for tiers in stock_selectors.fournisseurs_pour_controle_ice(company):
        motif = _motif(tiers['ice'])
        if motif:
            fournisseurs.append({**tiers, 'motif': motif})

    return {'clients': clients, 'fournisseurs': fournisseurs}


def ecatalogue_public_par_token(token):
    """XPOS14 — E-catalogue public lu par son token (FG214), lecture seule.

    Utilisé par ``apps.ventes.public_views`` (frontière selectors — jamais
    d'import de ``compta.models`` côté ventes). Renvoie ``None`` si le token
    est inconnu, l'e-catalogue est inactif, ou expiré — un appelant public
    traite ``None`` comme 404, sans jamais fuiter d'information sur l'état
    réel (existe mais expiré / n'existe pas)."""
    from .models import ECatalogue
    try:
        cat = ECatalogue.objects.get(token=token, actif=True)
    except ECatalogue.DoesNotExist:
        return None
    if cat.expire_le and cat.expire_le < timezone.now():
        return None
    return cat


def produits_publics_du_catalogue(ecatalogue):
    """Produits exposés par un e-catalogue (prix public TTC uniquement,
    jamais `prix_achat`). Lecture seule, scopée à la société du catalogue."""
    from apps.stock.models import Produit
    return list(
        Produit.objects.filter(
            company_id=ecatalogue.company_id,
            id__in=ecatalogue.produit_ids or [],
        )
    )


# ── SCA44 — Abonnements de monitoring dus (facturation récurrente beat) ────

def abonnements_monitoring_dus_facturation(company, today=None):
    """``AbonnementMonitoring`` ACTIFS dont la période courante
    (``prochaine_echeance``, ou aujourd'hui si absente) est due aujourd'hui
    (ou en retard) ET pas encore facturée pour cette période — SCA44.

    Lecture seule, scopée société. Miroir de
    ``apps.sav.services.contrats_maintenance_dus_facturation`` : le beat
    quotidien de ``apps.contrats.scheduled`` appelle ce sélecteur (frontière
    ``selectors.py``, jamais un import direct de ``apps.monitoring.models``
    depuis ``contrats``) pour ne facturer que les abonnements réellement dus,
    sans jamais re-sélectionner un abonnement déjà facturé pour sa période
    courante (garde d'idempotence de ``derniere_facturation`` ==
    ``prochaine_echeance``, en plus de la garde déjà posée dans
    ``services.facturer_abonnement_monitoring``)."""
    from .models import AbonnementMonitoring

    if today is None:
        today = timezone.localdate()

    return [
        a for a in AbonnementMonitoring.objects.filter(
            company=company,
            statut=AbonnementMonitoring.Statut.ACTIF,
            prochaine_echeance__lte=today,
        )
        if a.derniere_facturation != (a.prochaine_echeance or today)
    ]


# ── ARC40 — provider KPI pour le reporting fédéré ────────────────────────────

def kpi_echeances(company):
    """ARC40 — tuiles KPI d'échéances de trésorerie (effets de commerce).

    Déclaré dans ``apps/compta/platform.py`` (surface ``kpi_providers``) et
    résolu par ``apps/reporting/reports.py::kpi_federes`` — le reporting
    n'importe JAMAIS les modèles compta, il appelle ce sélecteur (frontière
    inter-app). Un effet « ouvert » = en portefeuille ou remis (ni encaissé,
    ni payé, ni rejeté, ni mobilisé). Chaque tuile suit la forme normalisée
    ``{id, label, valeur, unite?}``. Lecture seule, scopé société.
    """
    from datetime import date, timedelta

    from .models import Effet

    today = date.today()
    horizon = today + timedelta(days=30)
    ouverts = Effet.objects.filter(
        company=company,
        statut__in=[Effet.Statut.PORTEFEUILLE, Effet.Statut.REMIS])
    a_echoir_30j = ouverts.filter(
        date_echeance__gte=today, date_echeance__lte=horizon).count()
    depassees = ouverts.filter(date_echeance__lt=today).count()
    return [
        {'id': 'compta_echeances_30j',
         'label': 'Échéances à 30 jours (effets ouverts)',
         'valeur': a_echoir_30j, 'unite': 'effets'},
        {'id': 'compta_echeances_depassees',
         'label': 'Échéances dépassées (effets ouverts)',
         'valeur': depassees, 'unite': 'effets'},
    ]


# ── NTFPA2 — lecture minimale pour l'app FP&A (apps.fpa) ────────────────────
# `apps.fpa.CycleBudgetaire.exercice_comptable_id` référence
# `ExerciceComptable` en STRING-ID (jamais un FK dur — cross-app boundary) ;
# ce sélecteur est le SEUL point de lecture que FP&A utilise pour résoudre le
# libellé/les bornes d'un exercice. Lecture seule, scopé société.
def get_exercice_label(company, exercice_id):
    """Libellé + bornes d'un ``ExerciceComptable`` (ou ``None`` si absent/hors
    société) — utilisé par ``apps.fpa`` sans jamais importer ``ExerciceComptable``
    directement."""
    if not exercice_id:
        return None
    from .models import ExerciceComptable

    exercice = ExerciceComptable.objects.filter(
        company=company, pk=exercice_id).first()
    if exercice is None:
        return None
    return {
        'id': exercice.pk,
        'libelle': exercice.libelle or f'Exercice {exercice.date_debut}',
        'date_debut': exercice.date_debut,
        'date_fin': exercice.date_fin,
        'statut': exercice.statut,
    }


def _mois_precedents(mois_reference, n_mois):
    """``n_mois`` tuples ``(annee, mois)`` STRICTEMENT avant ``mois_reference``
    (le mois de ``mois_reference`` lui-même est exclu), du plus ancien au plus
    récent."""
    annee, mois = mois_reference.year, mois_reference.month
    bornes = []
    for i in range(n_mois, 0, -1):
        m = mois - i
        a = annee
        while m <= 0:
            m += 12
            a -= 1
        bornes.append((a, m))
    return bornes


def moyenne_mensuelle_par_prefixes(company, prefixes, mois_reference, *,
                                   n_mois=3, validees_seulement=True):
    """NTFPA8 — moyenne mensuelle du montant net (Σ débit − Σ crédit) des
    comptes du plan CGNC dont le numéro commence par l'un des ``prefixes``,
    sur les ``n_mois`` mois CLOS précédant ``mois_reference`` (le mois de
    référence lui-même est exclu).

    Lecture seule ; c'est le SEUL point d'entrée que ``apps.fpa`` utilise pour
    amorcer une prévision glissante depuis le réel comptable (jamais un import
    direct de ``LigneEcriture``). Renvoie ``Decimal('0')`` si aucun mouvement.
    """
    prefixes = tuple(str(p) for p in (prefixes or ()))
    if not prefixes:
        return Decimal('0')

    mois_bornes = _mois_precedents(mois_reference, n_mois)
    annee_debut, mois_debut = mois_bornes[0]
    date_debut = date(annee_debut, mois_debut, 1)
    # Dernier jour du mois juste avant mois_reference.
    date_fin = date(mois_reference.year, mois_reference.month, 1) - timedelta(days=1)

    comptes = grand_livre(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement)
    total = Decimal('0')
    for bucket in comptes:
        if not str(bucket['numero']).startswith(prefixes):
            continue
        total += bucket['total_debit'] - bucket['total_credit']
    return total / Decimal(n_mois)


def total_reel_par_prefixes_mois(company, prefixes, annee, mois, *,
                                 validees_seulement=True):
    """NTFPA19 — total réel comptable (Σ débit − Σ crédit) des comptes dont le
    numéro commence par l'un des ``prefixes``, sur le mois ``(annee, mois)``.

    Lecture seule ; point d'entrée pour ``apps.fpa`` (variance budget vs réel).
    Renvoie ``Decimal('0')`` si aucun mouvement. Jamais un import de
    ``LigneEcriture`` côté FP&A."""
    prefixes = tuple(str(p) for p in (prefixes or ()))
    if not prefixes:
        return Decimal('0')
    date_debut = date(annee, mois, 1)
    if mois == 12:
        date_fin = date(annee, 12, 31)
    else:
        date_fin = date(annee, mois + 1, 1) - timedelta(days=1)
    comptes = grand_livre(
        company, date_debut=date_debut, date_fin=date_fin,
        validees_seulement=validees_seulement)
    total = Decimal('0')
    for bucket in comptes:
        if str(bucket['numero']).startswith(prefixes):
            total += bucket['total_debit'] - bucket['total_credit']
    return total
