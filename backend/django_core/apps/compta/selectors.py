"""Sélecteurs LECTURE SEULE de la Comptabilité générale (états & restitutions).

Grand livre (FG110), balance générale (FG111), lettrage (FG112), CPC (FG113) et
bilan (FG114) se déduisent tous des ``LigneEcriture`` du grand livre. Aucune
écriture n'est modifiée ici. Toutes les fonctions sont scopées par société.
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum
from django.utils import timezone

from .models import (
    Caisse, CompteComptable, CompteTresorerie, Effet, LigneEcriture,
    LignePrevisionnelTresorerie, MouvementCaisse, Rapprochement, RetenueSource,
)


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
                             validees_seulement=False):
    """Calcule la TVA à déclarer sur une période depuis le grand livre (FG137).

    TVA collectée = Σ crédit − Σ débit des comptes 4455… (passif : un avoir
    annulant une vente DÉBITE 4455, on le déduit). TVA déductible = Σ débit − Σ
    crédit des comptes 3455… (actif : un avoir fournisseur CRÉDITE 3455). La TVA
    nette à déclarer = max(0, collectée − déductible − crédit antérieur) ;
    l'excédent éventuel devient un crédit reportable. ``regime`` (mensuel /
    trimestriel) et ``methode`` (débit / encaissement) qualifient le dépôt mais
    n'altèrent pas l'agrégation GL (la période en porte la portée). Lecture
    seule, scopée société. Renvoie un dict prêt à figer sur une ``DeclarationTVA``.
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
    return {
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
            }
            ordre_ecritures.append(eid)
        tva_par_ecriture[eid]['tva'] += (
            (ligne.debit or Decimal('0')) - (ligne.credit or Decimal('0')))

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
