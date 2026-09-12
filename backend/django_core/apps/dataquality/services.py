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

from .models import (
    GoldenRecord, RegleQualite, RegleSurvivorship, ResultatQualite,
)


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


# ── NTDATA19 — DÉDOUBLONNAGE FOURNISSEURS & PRODUITS ────────────────────────
#
# Les fiches sont lues par les points d'entrée cross-app de `stock.selectors`
# (jamais un import de `apps.stock.models`) : le filtre société y est posé, les
# fiches déjà archivées en sont exclues, et AUCUN prix d'achat n'en sort — la
# détection ne travaille que sur l'identité et les références.


def doublons_fournisseurs(company, user=None):
    """Groupes de fournisseurs qui désignent probablement la même entreprise.

    Rapprochement par ICE (identifiant légal — le plus sûr), puis email,
    téléphone et raison sociale normalisée approchée.
    """
    from apps.crm.selectors import (
        normalize_email_key, normalize_name_key, normalize_phone_key,
    )
    from apps.stock.selectors import fournisseurs_pour_dedoublonnage

    from .dedoublonnage import grouper_doublons

    return grouper_doublons(
        fournisseurs_pour_dedoublonnage(company),
        criteres=('ice', 'telephone', 'email', 'nom'),
        normaliseurs={
            'ice': lambda v: (str(v or '').strip() or None),
            'telephone': normalize_phone_key,
            'email': normalize_email_key,
            'nom': lambda v: normalize_name_key(v),
        },
    )


def doublons_produits(company, user=None):
    """Groupes de produits qui désignent probablement le même article.

    Rapprochement par RÉFÉRENCE (``sku``, insensible à la casse et aux
    espaces) puis par désignation normalisée approchée. La référence est
    traitée comme un identifiant : deux fiches qui la partagent sont presque
    certainement la même — d'où un poids proche de celui d'un ICE.
    """
    from apps.crm.selectors import normalize_name_key
    from apps.stock.selectors import produits_pour_dedoublonnage

    from .dedoublonnage import grouper_doublons

    return grouper_doublons(
        produits_pour_dedoublonnage(company),
        criteres=('reference', 'nom'),
        normaliseurs={
            'reference': lambda v: (str(v or '').strip().lower() or None),
            'nom': lambda v: normalize_name_key(v),
        },
        # La référence catalogue d'un produit vit dans `sku`.
        champs={'reference': 'sku'},
    )


def fusionner_fournisseurs(company, user, survivant_id, doublons_ids):
    """NTDATA19 — déclenche la fusion supervisée via ``stock.services``."""
    from apps.stock.services import fournisseurs_par_ids, merge_fournisseurs

    return _fusionner_via(
        company, user, survivant_id, doublons_ids,
        chargeur=fournisseurs_par_ids, fusion=merge_fournisseurs,
        libelle='fournisseur')


def fusionner_produits(company, user, survivant_id, doublons_ids):
    """NTDATA19 — déclenche la fusion supervisée via ``stock.services``."""
    from apps.stock.services import merge_produits, produits_par_ids

    return _fusionner_via(
        company, user, survivant_id, doublons_ids,
        chargeur=produits_par_ids, fusion=merge_produits, libelle='produit')


def _fusionner_via(company, user, survivant_id, doublons_ids, *, chargeur,
                   fusion, libelle):
    """Charge les fiches DANS la société puis délègue à l'app propriétaire.

    Aucune logique de fusion ici : ``dataquality`` déclenche, l'app qui possède
    les données exécute. Lève ``ValueError`` avec un message FRANÇAIS.
    """
    doublons_ids = [i for i in (doublons_ids or []) if i != survivant_id]
    if not doublons_ids:
        raise ValueError('Indiquez au moins un doublon à fusionner.')
    fiches = {f.pk: f for f in chargeur(
        company, [survivant_id] + list(doublons_ids))}
    survivant = fiches.get(survivant_id)
    if survivant is None:
        raise ValueError(
            'Fiche %s survivante introuvable dans cette société (#%s).'
            % (libelle, survivant_id))
    absorbes = [fiches[i] for i in doublons_ids if i in fiches]
    if not absorbes:
        raise ValueError(
            "Aucun des doublons indiqués n'existe dans cette société.")
    return fusion(survivant, absorbes, user)


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


# ── NTDATA23 — SURVIVORSHIP & CONSOLIDATION DES GOLDEN RECORDS ─────────────
#
# `consolider_golden(company, entite)` prend les GROUPES de doublons détectés
# (NTDATA17/19), en tire une CLÉ MÉTIER stable, puis calcule champ par champ la
# valeur gagnante selon les `RegleSurvivorship` de la société.
#
# TROIS GARANTIES, et elles ne se négocient pas :
#
#  1. AUCUNE MUTATION DES SOURCES. Le golden record est une VUE. Le recalculer
#     ne touche pas une seule fiche ; le supprimer ne perd rien d'original.
#  2. UNE VALEUR VIDE NE GAGNE JAMAIS contre une valeur renseignée. Consolider
#     ne doit pas EFFACER ce qu'une des fiches portait.
#  3. LA STRATÉGIE QUI A TRANCHÉ EST NOMMÉE, champ par champ, dans
#     `attributs[champ]['strategie']`. En particulier, `plus_recent` sur une
#     entité SANS signal de fraîcheur (``crm.Client`` n'a aucune date de
#     modification) retombe sur le défaut et l'ÉCRIT — jamais une fraîcheur
#     devinée qui ferait passer un arbitraire pour une mesure.

#: Stratégie appliquée quand aucune `RegleSurvivorship` ne couvre le champ :
#: la première valeur NON VIDE dans l'ordre de lecture — la fiche d'origine
#: fait foi, et rien n'est perdu.
STRATEGIE_DEFAUT = RegleSurvivorship.Strategie.SOURCE_PRIORITAIRE

#: Entité → (champs consolidés, critères de clé métier par ordre de sûreté,
#: champ portant la fraîcheur s'il en existe un). ``champ_fraicheur=None``
#: signifie « cette entité ne sait pas dire quand une fiche a été modifiée » —
#: c'est un FAIT du schéma, pas un oubli, et `plus_recent` le dit.
#
# LE NOM N'EST JAMAIS UNE CLÉ MÉTIER. Deux « Atlas Energie » peuvent être deux
# entreprises : ranger leurs fiches sous un golden record commun créerait
# exactement le doublon que ce module existe pour réduire. Seuls des
# IDENTIFIANTS entrent dans ``cles`` (ICE, téléphone, email, référence
# catalogue) ; un groupe qui n'en partage aucun n'est PAS consolidé.
CONSOLIDATION = {
    GoldenRecord.Entite.CLIENT: {
        'champs': ['nom', 'telephone', 'email', 'ice', 'adresse', 'ville'],
        'cles': ['ice', 'telephone', 'email'],
        'champ_fraicheur': None,
    },
    GoldenRecord.Entite.FOURNISSEUR: {
        'champs': ['nom', 'ice', 'email', 'telephone'],
        'cles': ['ice', 'telephone', 'email'],
        'champ_fraicheur': None,
    },
    GoldenRecord.Entite.PRODUIT: {
        'champs': ['nom', 'sku', 'marque'],
        'cles': ['sku'],
        'champ_fraicheur': None,
    },
}

#: Détecteur de doublons par entité (NTDATA17/19) — réutilisé tel quel, jamais
#: un second regroupement qui dériverait du premier.
_DETECTEURS_ENTITE = {
    GoldenRecord.Entite.CLIENT: 'doublons_clients',
    GoldenRecord.Entite.FOURNISSEUR: 'doublons_fournisseurs',
    GoldenRecord.Entite.PRODUIT: 'doublons_produits',
}


def _lignes_entite(company, user, entite):
    """Les fiches d'une entité, à plat, par les MÊMES lecteurs que la détection.

    Clients : le dataset `crm_clients` (déjà scopé société par le CRM).
    Fournisseurs / produits : les points d'entrée `stock.selectors`. Aucun
    import de modèle d'app métier, aucun prix d'achat.
    """
    if entite == GoldenRecord.Entite.CLIENT:
        from core import data_explorer
        try:
            return data_explorer.run_query(
                'crm_clients', company, user,
                {'select': ['id', 'nom', 'telephone', 'email', 'ice',
                            'adresse', 'ville'],
                 'limit': LIMITE_LECTURE})
        except data_explorer.DatasetInconnu:
            return []
    if entite == GoldenRecord.Entite.FOURNISSEUR:
        from apps.stock.selectors import fournisseurs_pour_dedoublonnage
        return list(fournisseurs_pour_dedoublonnage(company))
    if entite == GoldenRecord.Entite.PRODUIT:
        from apps.stock.selectors import produits_pour_dedoublonnage
        return list(produits_pour_dedoublonnage(company))
    return []


def _normaliseur_de_cle(critere):
    """Le normaliseur du CRM pour ce critère (jamais réécrit ici)."""
    from apps.crm.selectors import (
        normalize_email_key, normalize_name_key, normalize_phone_key,
    )

    if critere in ('ice', 'sku', 'reference'):
        return lambda v: (str(v or '').strip().lower() or None)
    if critere == 'telephone':
        return normalize_phone_key
    if critere == 'email':
        return normalize_email_key
    return lambda v: normalize_name_key(v)


def cle_metier(entite, sources):
    """La clé STABLE qui identifie ce groupe, ou ``None`` s'il n'en a aucune.

    On prend l'identifiant le plus SÛR effectivement partagé par le groupe
    (ICE ou référence avant téléphone, téléphone avant email) — le même ordre
    de confiance que la détection (``POIDS_CRITERES``). Aucun identifiant
    partagé ⇒ ``None`` : le groupe n'est PAS consolidé plutôt que d'être rangé
    sous une clé fabriquée.
    """
    declaration = CONSOLIDATION.get(entite)
    if not declaration or not sources:
        return None
    for critere in declaration['cles']:
        normaliseur = _normaliseur_de_cle(critere)
        valeurs = {normaliseur(s.get(critere)) for s in sources}
        valeurs.discard(None)
        if len(valeurs) == 1:
            return str(next(iter(valeurs)))[:120]
    return None


def _nb_renseignes(source, champs):
    """Nombre de champs NON VIDES d'une fiche (mesure de complétude)."""
    return sum(1 for champ in champs if not _est_vide(source.get(champ)))


def _candidats(champ, sources):
    """Les fiches qui portent réellement une valeur pour ``champ``.

    Une valeur VIDE n'est jamais candidate : consolider ne doit pas effacer.
    """
    return [s for s in sources if not _est_vide(s.get(champ))]


def valeur_gagnante(champ, sources, strategie, *, champs=None,
                    champ_fraicheur=None, parametres=None):
    """La valeur retenue pour ``champ`` + la stratégie qui a RÉELLEMENT tranché.

    ``sources`` — fiches du groupe, dans l'ordre de lecture (la plus ancienne
    d'abord). Renvoie ``(valeur, strategie_effective)``. Aucune fiche ne porte
    de valeur ⇒ ``(None, '')`` : un champ vide partout reste vide, jamais
    rempli d'un défaut.
    """
    candidats = _candidats(champ, sources)
    if not candidats:
        return None, ''
    champs = list(champs or [])
    parametres = parametres if isinstance(parametres, dict) else {}
    effective = strategie

    if strategie == RegleSurvivorship.Strategie.PLUS_RECENT:
        if champ_fraicheur and any(
                c.get(champ_fraicheur) is not None for c in candidats):
            avec = [c for c in candidats
                    if c.get(champ_fraicheur) is not None]
            gagnant = max(avec, key=lambda c: c[champ_fraicheur])
            return gagnant.get(champ), strategie
        # Aucun signal de fraîcheur : on NE DEVINE PAS. On retombe sur le
        # défaut et on l'écrit, pour qu'un lecteur du golden record sache que
        # « le plus récent » n'a pas pu être mesuré.
        effective = '%s (repli : %s)' % (strategie, STRATEGIE_DEFAUT)
        strategie = STRATEGIE_DEFAUT

    if strategie == RegleSurvivorship.Strategie.PLUS_COMPLET:
        gagnant = max(candidats,
                      key=lambda c: (_nb_renseignes(c, champs),
                                     -_rang(c)))
        return gagnant.get(champ), effective

    if strategie == RegleSurvivorship.Strategie.PLUS_FREQUENT:
        comptes = {}
        for index, source in enumerate(candidats):
            valeur = source.get(champ)
            cle = str(valeur)
            if cle not in comptes:
                comptes[cle] = [0, index, valeur]
            comptes[cle][0] += 1
        meilleur = min(comptes.values(), key=lambda t: (-t[0], t[1]))
        return meilleur[2], effective

    # SOURCE_PRIORITAIRE (et le défaut) : la fiche désignée si elle porte une
    # valeur, sinon la PREMIÈRE fiche non vide dans l'ordre de lecture.
    source_id = parametres.get('source_id')
    if source_id is not None:
        for source in candidats:
            if source.get('id') == source_id:
                return source.get(champ), effective
    return candidats[0].get(champ), effective


def _rang(source):
    """Rang de lecture d'une fiche (son id — les ids sont monotones)."""
    identifiant = source.get('id')
    return identifiant if isinstance(identifiant, int) else 0


def regles_survivorship(company, entite):
    """``{champ: RegleSurvivorship}`` actives de cette société pour l'entité."""
    return {
        regle.champ: regle
        for regle in RegleSurvivorship.objects.filter(
            company=company, entite=entite, actif=True).order_by('champ', 'id')
    }


def consolider_groupe(company, entite, sources, *, regles=None):
    """Les attributs consolidés d'UN groupe de fiches (calcul pur, sans écriture).

    Renvoie ``{champ: {'valeur': …, 'strategie': …, 'sources': [ids]}}`` — le
    champ, ce qui a gagné, et POURQUOI. Un champ vide partout est ABSENT du
    résultat plutôt que présent à ``null`` : « personne ne l'a renseigné » se
    lit dans l'absence, pas dans une case vide qui ressemble à une donnée.
    """
    declaration = CONSOLIDATION.get(entite)
    if not declaration:
        return {}
    regles = regles if regles is not None else regles_survivorship(
        company, entite)
    champs = declaration['champs']
    attributs = {}
    for champ in champs:
        regle = regles.get(champ)
        strategie = regle.strategie if regle else STRATEGIE_DEFAUT
        parametres = regle.parametres if regle else None
        valeur, effective = valeur_gagnante(
            champ, sources, strategie, champs=champs,
            champ_fraicheur=declaration['champ_fraicheur'],
            parametres=parametres)
        if valeur is None:
            continue
        attributs[champ] = {
            'valeur': valeur,
            'strategie': effective,
            'sources': [s.get('id') for s in _candidats(champ, sources)],
        }
    return attributs


def consolider_golden(company, entite, *, user=None, lignes=None,
                      groupes=None, now=None):
    """NTDATA23 — (re)calcule les golden records d'une entité. Renvoie la liste.

    ``lignes``/``groupes`` peuvent être injectés (tests, recalcul ciblé) ;
    sinon les fiches sont lues par les mêmes lecteurs que la détection et les
    groupes viennent du détecteur de l'entité (NTDATA17/19).

    Un groupe sans clé métier stable est IGNORÉ (jamais rangé sous une clé
    fabriquée). Un golden record existant est mis à jour EN PLACE : la clé
    métier est son identité, pas son numéro de ligne.
    """
    from django.utils import timezone

    if entite not in CONSOLIDATION:
        raise ValueError(
            'Entité inconnue pour la consolidation : « %s » (attendu : %s).'
            % (entite, ', '.join(sorted(CONSOLIDATION))))
    if lignes is None:
        lignes = _lignes_entite(company, user, entite)
    if groupes is None:
        detecteur = globals().get(_DETECTEURS_ENTITE[entite])
        groupes = detecteur(company, user) if detecteur else []

    par_id = {ligne.get('id'): ligne for ligne in lignes}
    regles = regles_survivorship(company, entite)
    horodatage = now or timezone.now()

    consolides = []
    for groupe in groupes:
        sources = [par_id[i] for i in (groupe.get('ids') or [])
                   if i in par_id]
        if len(sources) < 2:
            continue  # une fiche seule n'a rien à consolider.
        cle = cle_metier(entite, sources)
        if not cle:
            continue
        attributs = consolider_groupe(company, entite, sources, regles=regles)
        golden, _cree = GoldenRecord.objects.update_or_create(
            company=company, entite=entite, cle_metier=cle,
            defaults={
                'source_ids': [s.get('id') for s in sources],
                'attributs': attributs,
                'derniere_consolidation_le': horodatage,
            },
        )
        consolides.append(golden)
    return consolides


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
