"""Sélecteurs LECTURE SEULE de la Comptabilité générale (états & restitutions).

Grand livre (FG110), balance générale (FG111), lettrage (FG112), CPC (FG113) et
bilan (FG114) se déduisent tous des ``LigneEcriture`` du grand livre. Aucune
écriture n'est modifiée ici. Toutes les fonctions sont scopées par société.
"""
from decimal import Decimal

from django.db.models import Sum

from .models import CompteComptable, CompteTresorerie, LigneEcriture


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


# ── FG111 / COMPTA20 — Balance générale (trial balance) ────────────────────

def balance_generale(company, *, date_debut=None, date_fin=None,
                     validees_seulement=False):
    """Débit/crédit/solde par compte sur une période (≠ balance âgée clients).

    Renvoie une liste de dicts triée par numéro + des totaux globaux. La somme
    des débits doit égaler la somme des crédits (le grand livre est équilibré).
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
    return {
        'lignes': lignes,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'equilibree': total_debit == total_credit,
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


# ── FG113 / COMPTA27 — CPC (Compte de Produits et Charges) ─────────────────

def cpc(company, *, date_debut=None, date_fin=None, validees_seulement=False):
    """État de résultat (CPC) : produits (classe 7) − charges (classe 6).

    Renvoie ``{'produits', 'total_produits', 'charges', 'total_charges',
    'resultat'}``. Le résultat positif = bénéfice, négatif = perte.
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
    return {
        'produits': produits,
        'total_produits': total_produits,
        'charges': charges,
        'total_charges': total_charges,
        'resultat': total_produits - total_charges,
    }


# ── FG114 / COMPTA28 — Bilan (format CGNC) ─────────────────────────────────

def bilan(company, *, date_fin=None, validees_seulement=False):
    """Bilan : actif (classes 2,3,5) / passif (classes 1,4) depuis les soldes.

    Le résultat de l'exercice (CPC) est porté au passif pour équilibrer
    (équation comptable : Actif = Passif + Résultat). Renvoie
    ``{'actif', 'total_actif', 'passif', 'total_passif', 'resultat',
    'equilibre'}``.
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
    resultat = cpc(
        company, date_fin=date_fin,
        validees_seulement=validees_seulement)['resultat']
    return {
        'actif': actif,
        'total_actif': total_actif,
        'passif': passif,
        'total_passif': total_passif,
        'resultat': resultat,
        'equilibre': total_actif == (total_passif + resultat),
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
    (classe 5). Renvoie ``{'comptes': [...], 'total': Decimal}`` où chaque entrée
    porte ``{'id', 'libelle', 'type_compte', 'banque', 'devise', 'solde_initial',
    'mouvements', 'solde'}``. Lecture seule, scopée société.
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
    return {'comptes': comptes, 'total': total}


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
    rapproche = (
        bool(lignes) and toutes_concordantes and ecart == Decimal('0'))
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
