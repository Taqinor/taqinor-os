"""NTDATA14 — évaluation des règles de qualité sur une population de lignes.

Fonctions PURES au-dessus de ``core.rules`` : elles prennent des dicts (les
lignes que ``core.data_explorer.run_query`` rend déjà) et disent lesquelles
sont EN VIOLATION. Aucun import d'app métier, aucune écriture.

POURQUOI UNE COUCHE AU-DESSUS DE ``core.rules``. Deux types de règles n'y sont
pas exprimables et c'est assumé, pas contourné :

* ``format`` — ``core.rules`` n'a aucun opérateur d'expression régulière
  (ses opérateurs de feuille sont ``eq/ne/gt/gte/lt/lte/in/not_in/contains/
  startswith/exists``). Y ajouter une regex serait ouvrir un évaluateur non
  borné dans la couche fondation ; on compile donc le motif ici, une fois par
  règle.
* ``unicite`` — la conformité d'une ligne dépend des AUTRES lignes. Aucun
  moteur ligne-par-ligne ne peut répondre.

``non_vide`` et ``plage`` passent, eux, PAR ``core.rules``
(``evaluate_condition_group``) — jamais une seconde implémentation.

UNE VALEUR VIDE N'EST PAS UNE VIOLATION, sauf pour ``non_vide``. Un ICE absent
est un trou de COMPLÉTUDE (NTDATA16), pas un format faux : dire « format
invalide » d'une case vide gonflerait artificiellement le taux de non-conformité
et ferait chercher une faute qui n'existe pas.
"""
from __future__ import annotations

import re

from .models import RegleQualite, ResultatQualite


def _est_vide(valeur):
    """Vrai pour ``None`` et pour une chaîne blanche — jamais pour 0/False.

    Zéro et « faux » sont des valeurs RENSEIGNÉES : les compter comme vides
    ferait passer un stock à 0 ou une case décochée pour une donnée manquante.
    """
    if valeur is None:
        return True
    if isinstance(valeur, str):
        return not valeur.strip()
    return False


def _viole_format(regle, valeur):
    motif = (regle.parametres or {}).get('motif')
    if not motif:
        return False
    try:
        compile_ = re.compile(motif)
    except re.error:
        # Motif devenu invalide après coup : on ne juge RIEN plutôt que de
        # déclarer toute la population fautive.
        return False
    return compile_.match(str(valeur)) is None


def _viole_reference(regle, valeur):
    valeurs = (regle.parametres or {}).get('valeurs') or []
    return valeur not in valeurs


def _viole_core_rules(regle, ligne):
    """``non_vide`` / ``plage`` — délégué à ``core.rules`` (jamais réécrit)."""
    from core.rules import evaluate_condition_group

    condition = regle.condition_core_rules
    if condition is None:
        return False
    if not condition.get('conditions') and 'op' in condition:
        # Groupe VIDE (une règle « plage » sans borne ne devrait pas exister,
        # la validation du modèle l'interdit) : rien à juger.
        return False
    conforme = evaluate_condition_group(condition, dict(ligne))
    return not conforme


def ligne_en_violation(regle, ligne):
    """Cette ligne viole-t-elle ``regle`` ? (règles LIGNE À LIGNE uniquement)

    ``unicite`` renvoie toujours ``False`` ici : elle se juge sur la
    population (voir :func:`violations`).
    """
    valeur = ligne.get(regle.champ)
    if regle.type_regle == RegleQualite.TypeRegle.NON_VIDE:
        # `exists` de core.rules teste la PRÉSENCE de la clé ; une chaîne
        # blanche est présente mais vide. On écarte donc le cas vide ici, et
        # on laisse core.rules juger la présence.
        if _est_vide(valeur):
            return True
        return _viole_core_rules(regle, ligne)
    if _est_vide(valeur):
        # Trou de complétude, pas une faute de format/plage/référentiel.
        return False
    if regle.type_regle == RegleQualite.TypeRegle.FORMAT:
        return _viole_format(regle, valeur)
    if regle.type_regle == RegleQualite.TypeRegle.REFERENCE_VALIDE:
        return _viole_reference(regle, valeur)
    if regle.type_regle == RegleQualite.TypeRegle.PLAGE:
        return _viole_core_rules(regle, ligne)
    return False


def violations(regle, lignes, *, cle_id='id'):
    """Les identifiants des lignes en violation de ``regle``.

    ``lignes`` — itérable de dicts (le rendu de ``data_explorer.run_query``).
    Renvoie ``(nb_lignes, identifiants_en_violation)``, les identifiants dans
    l'ordre de lecture (déterministe).
    """
    lignes = list(lignes)
    if regle.type_regle == RegleQualite.TypeRegle.UNICITE:
        vues = {}
        fautives = []
        for ligne in lignes:
            valeur = ligne.get(regle.champ)
            if _est_vide(valeur):
                continue  # une case vide n'est jamais un doublon
            cle = str(valeur).strip().lower()
            if cle in vues:
                # La PREMIÈRE occurrence compte aussi : un doublon est un
                # groupe, pas une ligne isolée.
                if vues[cle] is not None:
                    fautives.append(vues[cle])
                    vues[cle] = None
                fautives.append(ligne.get(cle_id))
            else:
                vues[cle] = ligne.get(cle_id)
        return len(lignes), fautives
    fautives = [ligne.get(cle_id) for ligne in lignes
                if ligne_en_violation(regle, ligne)]
    return len(lignes), fautives


def taux_conformite(nb_lignes, nb_violations):
    """Part conforme, en pourcentage arrondi au dixième.

    Population VIDE ⇒ ``None``, jamais 100 % : « aucune donnée » n'est pas
    « tout est bon » — afficher 100 % sur zéro ligne serait un chiffre faux.
    """
    if not nb_lignes:
        return None
    conformes = max(0, nb_lignes - nb_violations)
    return round(conformes / nb_lignes * 100, 1)


# ── NTDATA15 — EXÉCUTION & RAPPORT ──────────────────────────────────────────
#
# `evaluer_regles` parcourt les datasets CIBLÉS par les règles actives d'une
# société, applique chaque règle et PERSISTE un `ResultatQualite` daté. Elle ne
# corrige rien et ne bloque rien : elle mesure.
#
# Le queryset de chaque dataset est déjà borné à la société par l'app
# propriétaire (contrat `core.data_explorer`) — la qualité de données ne peut
# donc pas sortir du périmètre du tenant. Le lecteur est transmis pour que les
# champs sous permission (AUD801) restent masqués : une règle posée sur un
# champ que le lecteur ne peut pas voir ne rend RIEN plutôt que de divulguer.

#: Borne dure de lecture par dataset — une évaluation de qualité n'est pas un
#: export. Au-delà, `run_query` tronque et le résultat le DIT (`tronque`).
LIMITE_LECTURE = 5000


def _lignes_du_dataset(company, user, entite, champs):
    """Les lignes d'un dataset pour l'évaluation, ou ``None`` s'il est absent.

    ``None`` (dataset non enregistré : module désactivé, nom obsolète) fait
    IGNORER les règles qui le visent, jamais échouer tout le rapport.
    """
    from core import data_explorer

    try:
        data_explorer.run_query(entite, company, user, {'limit': 1})
    except data_explorer.DatasetInconnu:
        return None
    projection = sorted({'id'} | set(champs or []))
    try:
        return data_explorer.run_query(
            entite, company, user,
            {'select': projection, 'limit': LIMITE_LECTURE})
    except data_explorer.ChampNonAutorise:
        # Un champ hors liste blanche (règle mal paramétrée) : on retombe sur
        # la projection par défaut du dataset plutôt que de tout abandonner.
        return data_explorer.run_query(
            entite, company, user, {'limit': LIMITE_LECTURE})


def evaluer_regles(company, entite=None, *, user=None):
    """Évalue les règles ACTIVES de ``company`` et persiste les résultats.

    ``entite`` restreint à un seul dataset. ``user`` est le LECTEUR (ses
    permissions s'appliquent aux champs gated) ; ``None`` = aucun champ sous
    permission n'est lisible, ce qui est le bon défaut pour un job planifié.

    Renvoie la liste des ``ResultatQualite`` créés, dans l'ordre des règles.
    """
    regles = RegleQualite.objects.filter(company=company, actif=True)
    if entite:
        regles = regles.filter(entite=entite)
    regles = list(regles.order_by('entite', 'champ', 'id'))
    if not regles:
        return []

    # Une seule lecture PAR DATASET, partagée par toutes ses règles (jamais
    # une requête par règle).
    champs_par_entite = {}
    for regle in regles:
        champs_par_entite.setdefault(regle.entite, set()).add(regle.champ)
    lignes_par_entite = {
        nom: _lignes_du_dataset(company, user, nom, champs)
        for nom, champs in champs_par_entite.items()
    }

    resultats = []
    for regle in regles:
        lignes = lignes_par_entite.get(regle.entite)
        if lignes is None:
            continue  # dataset absent : règle ignorée, jamais un faux 0 %.
        nb_lignes, fautives = violations(regle, lignes)
        resultats.append(ResultatQualite.objects.create(
            company=company,
            regle=regle,
            entite=regle.entite,
            nb_lignes=nb_lignes,
            nb_violations=len(fautives),
            taux_conformite=taux_conformite(nb_lignes, len(fautives)),
            echantillon=[
                identifiant for identifiant
                in fautives[:ResultatQualite.TAILLE_ECHANTILLON]
            ],
        ))
    return resultats


# ── NTDATA17 — DÉDOUBLONNAGE CLIENTS ────────────────────────────────────────
#
# La détection PROPOSE des groupes ; elle ne fusionne jamais (deux clients au
# même numéro peuvent être un père et son fils). La fusion supervisée vit dans
# `crm.services.merge_clients` (NTDATA18).
#
# AUCUN IMPORT DE `crm.models` : les fiches sont lues par le dataset
# `crm_clients` (déjà scopé société par l'app propriétaire) et les clés de
# rapprochement viennent des points d'entrée sanctionnés de `crm.selectors` —
# si le CRM change sa règle de téléphone, la détection suit toute seule.


def doublons_clients(company, user=None):
    """Groupes de ``crm.Client`` qui désignent probablement la même personne.

    Rapprochement par téléphone normalisé (clé marocaine du CRM), email en
    minuscules, ICE, et nom normalisé approché. Renvoie des groupes
    ``{ids, score, motifs, libelles}`` — le score est la confiance du
    DÉTECTEUR, jamais une mesure métier.
    """
    from apps.crm.selectors import (
        normalize_email_key, normalize_name_key, normalize_phone_key,
    )
    from core import data_explorer

    from .dedoublonnage import grouper_doublons

    try:
        lignes = data_explorer.run_query(
            'crm_clients', company, user,
            {'select': ['id', 'nom', 'telephone', 'email', 'ice'],
             'limit': LIMITE_LECTURE})
    except data_explorer.DatasetInconnu:
        return []
    return grouper_doublons(
        lignes,
        criteres=('ice', 'telephone', 'email', 'nom'),
        normaliseurs={
            'ice': lambda v: (str(v or '').strip() or None),
            'telephone': normalize_phone_key,
            'email': normalize_email_key,
            'nom': lambda v: normalize_name_key(v),
        },
    )


def fusionner_clients(company, user, survivant_id, doublons_ids):
    """NTDATA18 — déclenche la fusion supervisée via ``crm.services``.

    LA DÉCISION EST HUMAINE : cette fonction n'est appelée que sur action
    explicite. Elle ne contient AUCUNE logique de fusion — tout se passe dans
    ``crm.services.merge_clients``, l'app propriétaire des clients. Ici on ne
    fait que charger les fiches DANS LA SOCIÉTÉ de l'appelant (via le point
    d'entrée ``crm.selectors``/``crm.services``, jamais ``crm.models``) et
    refuser proprement ce qui n'a pas de sens.

    Lève ``ValueError`` avec un message FRANÇAIS quand le survivant est
    introuvable dans la société ou qu'aucun doublon valide n'est fourni.
    """
    from apps.crm.services import clients_par_ids, merge_clients

    doublons_ids = [i for i in (doublons_ids or []) if i != survivant_id]
    if not doublons_ids:
        raise ValueError('Indiquez au moins un doublon à fusionner.')
    fiches = {c.pk: c for c in clients_par_ids(
        company, [survivant_id] + list(doublons_ids))}
    survivant = fiches.get(survivant_id)
    if survivant is None:
        raise ValueError(
            'Client survivant introuvable dans cette société (#%s).'
            % survivant_id)
    absorbes = [fiches[i] for i in doublons_ids if i in fiches]
    if not absorbes:
        raise ValueError(
            'Aucun des doublons indiqués n\'existe dans cette société.')
    return merge_clients(survivant, absorbes, user)


def rapport_qualite(company, entite=None):
    """Le DERNIER résultat de chaque règle active — la photo du moment.

    Lecture seule : n'évalue rien (le rapport lit ce que le job a produit).
    Une règle jamais évaluée apparaît avec ``resultat=None`` plutôt que
    d'être masquée : « pas encore mesuré » est une information.
    """
    regles = RegleQualite.objects.filter(company=company, actif=True)
    if entite:
        regles = regles.filter(entite=entite)
    regles = list(regles.order_by('entite', 'champ', 'id'))
    dernier = {}
    for resultat in (ResultatQualite.objects
                     .filter(company=company,
                             regle__in=[r.pk for r in regles])
                     .order_by('regle_id', '-evalue_le', '-id')):
        dernier.setdefault(resultat.regle_id, resultat)
    lignes = []
    for regle in regles:
        resultat = dernier.get(regle.pk)
        lignes.append({
            'regle': regle.pk,
            'libelle': str(regle),
            'entite': regle.entite,
            'champ': regle.champ,
            'type_regle': regle.type_regle,
            'severite': regle.severite,
            'nb_lignes': resultat.nb_lignes if resultat else None,
            'nb_violations': resultat.nb_violations if resultat else None,
            'taux_conformite': (str(resultat.taux_conformite)
                                if resultat and resultat.taux_conformite
                                is not None else None),
            'echantillon': list(resultat.echantillon) if resultat else [],
            'evalue_le': (resultat.evalue_le.isoformat()
                          if resultat else None),
        })
    return lignes
