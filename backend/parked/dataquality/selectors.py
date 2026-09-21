"""NTDATA16 — COMPLÉTUDE par module : « quelle part de nos fiches est remplie ? »

LA DIFFÉRENCE AVEC LES RÈGLES (NTDATA14/15). Une règle dit « ce qui est écrit
est-il VALIDE ? » ; la complétude dit « est-ce seulement ÉCRIT ? ». Les deux
sont nécessaires : un ICE au mauvais format et un ICE absent ne se corrigent
pas de la même façon, et les confondre rend le rapport inactionnable.

CE QUE « CRITIQUE » VEUT DIRE. Un champ est critique quand son absence EMPÊCHE
une opération du métier — pas quand il serait « bien de l'avoir ». Un lead sans
téléphone n'est pas rappelable ; une facture sans échéance n'est pas
recouvrable ; un produit sans référence ne se commande pas. La liste est
DÉCLARÉE ici, par entité, et chaque entrée porte la raison en commentaire.

RIEN N'EST INVENTÉ. Les taux viennent des lignes réelles des datasets déjà
déclarés par les apps métier. Une population VIDE rend un score VIDE (``None``)
et jamais 100 % : « aucune fiche » n'est pas « toutes les fiches sont
complètes ».
"""
from __future__ import annotations

from .services import _est_vide

#: Entité métier → (dataset enregistré, champs CRITIQUES).
#: L'ordre des champs est celui du rendu (stable).
CHAMPS_CRITIQUES = {
    'clients': {
        'dataset': 'crm_clients',
        'libelle': 'Clients',
        # nom : identifier la fiche ; telephone : joindre ; adresse : livrer
        # et facturer ; ice : facturer une entreprise (mention légale).
        'champs': ['nom', 'telephone', 'adresse', 'ice'],
    },
    'leads': {
        'dataset': 'crm_leads',
        'libelle': 'Pistes',
        # telephone : rappeler ; ville : qualifier le gisement solaire ;
        # canal : savoir d'où vient l'affaire (et donc quoi financer).
        'champs': ['nom', 'telephone', 'ville', 'canal'],
    },
    'produits': {
        'dataset': 'stock_produits',
        'libelle': 'Catalogue produits',
        # sku : commander et réceptionner ; nom : figurer sur un devis ;
        # prix_vente : chiffrer ; categorie__nom : classer et filtrer.
        'champs': ['sku', 'nom', 'prix_vente', 'categorie__nom'],
    },
    'factures': {
        'dataset': 'ventes_factures',
        'libelle': 'Factures',
        # client : savoir QUI doit ; date_echeance : savoir QUAND relancer ;
        # montant_ttc : savoir COMBIEN.
        'champs': ['client', 'date_echeance', 'montant_ttc'],
    },
}


def _lignes(company, user, dataset, champs):
    """Les lignes d'un dataset, ou ``None`` s'il n'est pas enregistré."""
    from core import data_explorer

    try:
        return data_explorer.run_query(
            dataset, company, user,
            {'select': sorted({'id'} | set(champs)), 'limit': 5000})
    except (data_explorer.DatasetInconnu, data_explorer.ChampNonAutorise):
        return None


def completude_entite(company, user, entite):
    """Le score de complétude d'UNE entité, champ par champ.

    Renvoie ``None`` si l'entité n'est pas déclarée ou si son dataset n'est
    pas enregistré (module désactivé) — jamais un score fabriqué.
    """
    declaration = CHAMPS_CRITIQUES.get(entite)
    if declaration is None:
        return None
    champs = declaration['champs']
    lignes = _lignes(company, user, declaration['dataset'], champs)
    if lignes is None:
        return None

    nb_lignes = len(lignes)
    # Un champ ÉCARTÉ par la permission du lecteur (AUD801) n'est présent dans
    # aucune ligne : le noter « manquant » accuserait l'utilisateur d'un trou
    # qui n'existe pas. On l'exclut du score et on le DIT.
    presents = [c for c in champs
                if not lignes or any(c in ligne for ligne in lignes)]
    masques = [c for c in champs if c not in presents]

    par_champ = {}
    remplies = 0
    for champ in presents:
        nb_remplis = sum(1 for ligne in lignes
                         if not _est_vide(ligne.get(champ)))
        remplies += nb_remplis
        par_champ[champ] = (round(nb_remplis / nb_lignes * 100, 1)
                            if nb_lignes else None)
    cellules = nb_lignes * len(presents)
    return {
        'entite': entite,
        'libelle': declaration['libelle'],
        'dataset': declaration['dataset'],
        'nb_lignes': nb_lignes,
        'champs_critiques': presents,
        'champs_masques': masques,
        'par_champ': par_champ,
        'score_pct': (round(remplies / cellules * 100, 1)
                      if cellules else None),
    }


def completude_module(company, user=None):
    """Le tableau de complétude de TOUTES les entités déclarées.

    Renvoie ``{'entites': [...], 'score_global': …}``. Le score global est la
    moyenne des scores d'entité RÉELLEMENT calculés (une entité sans fiche ne
    tire pas la moyenne vers le bas : elle n'y entre pas du tout). Aucune
    entité mesurable ⇒ ``score_global`` vide, jamais 0.
    """
    entites = []
    for cle in CHAMPS_CRITIQUES:
        mesure = completude_entite(company, user, cle)
        if mesure is not None:
            entites.append(mesure)
    scores = [e['score_pct'] for e in entites if e['score_pct'] is not None]
    return {
        'entites': entites,
        'score_global': (round(sum(scores) / len(scores), 1)
                         if scores else None),
    }


# ── NTDATA21 — CARTE « SANTÉ DES DONNÉES » (3 indicateurs, tous réels) ─────
#
# Trois chiffres, et rien d'autre : est-ce REMPLI (complétude), est-ce JUSTE
# (règles bloquantes en violation), est-ce UNIQUE (doublons en attente de
# décision). Chacun vient de la couche qui le mesure déjà — aucune quatrième
# définition n'apparaît ici.
#
# CE QUI N'EST PAS MESURABLE EST OMIS, JAMAIS REMPLACÉ PAR ZÉRO. Un score de
# complétude VIDE (aucune fiche du tout) reste vide : afficher 0 % dirait
# « tout est à refaire » et afficher 100 % dirait « tout va bien » — les deux
# seraient faux. De même, une règle bloquante JAMAIS ÉVALUÉE n'est pas comptée
# comme conforme : elle est comptée à part (`bloquantes_non_evaluees`), pour
# que « 0 violation » ne veuille pas dire « 0 mesure ».

def sante_donnees(company, user=None):
    """Les 3 indicateurs de la carte « Santé des données ».

    Rend ``{'disponible', 'completude_globale_pct', 'regles_bloquantes_en_
    violation', 'bloquantes_non_evaluees', 'doublons_en_attente'}``.

    ``disponible`` est FAUX tant que la société n'a déclaré AUCUNE règle de
    qualité : la carte se masque alors côté écran, plutôt que d'afficher trois
    zéros qui ressembleraient à un bon bulletin.
    """
    from .models import PropositionFusion, RegleQualite, ResultatQualite

    regles = RegleQualite.objects.filter(company=company)
    if not regles.exists():
        return {
            'disponible': False,
            'completude_globale_pct': None,
            'regles_bloquantes_en_violation': None,
            'bloquantes_non_evaluees': None,
            'doublons_en_attente': None,
        }

    bloquantes = list(
        regles.filter(actif=True,
                      severite=RegleQualite.Severite.BLOQUANT)
        .values_list('id', flat=True))

    # Le DERNIER résultat de chaque règle bloquante (une seule requête).
    dernier = {}
    for resultat in (ResultatQualite.objects
                     .filter(company=company, regle__in=bloquantes)
                     .order_by('regle_id', '-evalue_le', '-id')):
        dernier.setdefault(resultat.regle_id, resultat)

    en_violation = sum(1 for identifiant in bloquantes
                       if (dernier.get(identifiant) is not None
                           and dernier[identifiant].nb_violations > 0))
    non_evaluees = sum(1 for identifiant in bloquantes
                       if dernier.get(identifiant) is None)

    return {
        'disponible': True,
        'completude_globale_pct': completude_module(
            company, user)['score_global'],
        'regles_bloquantes_en_violation': en_violation,
        'bloquantes_non_evaluees': non_evaluees,
        'doublons_en_attente': PropositionFusion.objects.filter(
            company=company,
            statut=PropositionFusion.Statut.EN_ATTENTE).count(),
    }
