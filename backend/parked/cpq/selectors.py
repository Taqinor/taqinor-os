"""Sélecteurs (lectures) de l'app CPQ.

Fonctions de lecture pures, scopées société. Aucun import des modèles des
autres apps domaine (string-FK uniquement)."""
from decimal import Decimal

from core.rules import evaluate_condition_group
from .models import (
    ContrainteCompatibilite, RegleProduitCPQ, SeuilMargeFamille,
    EtapeApprobationDevis, ClauseCGV,
)


def contexte_session_configurateur(session):
    """NTCPQ9 — Contexte plat {champ: valeur} construit depuis les réponses
    d'une session de configurateur (pour l'évaluation des règles NTCPQ2)."""
    context = {}
    for rep in session.reponses.select_related('question').all():
        context[rep.question.champ] = rep.valeur
    return context


def resoudre_configurateur(session):
    """NTCPQ9 — Résout les produits/bundles d'une session via les règles
    produit NTCPQ2. Renvoie ``{context, actions_declenchees}``."""
    context = contexte_session_configurateur(session)
    actions = evaluer_regles_produit(
        company=session.company, context=context)
    return {'context': context, 'actions_declenchees': actions}


def premiere_etape_en_attente(devis):
    """NTCPQ7 — Première étape d'approbation de remise encore ``en_attente``
    pour un devis (ordre ``niveau``), ou ``None`` si aucune. Sert au blocage
    de l'envoi/PDF tant qu'une approbation est requise."""
    return EtapeApprobationDevis.objects.filter(
        devis_id=devis.id,
        statut=EtapeApprobationDevis.Statut.EN_ATTENTE,
    ).order_by('niveau', 'id').first()


def etapes_approbation_devis(devis):
    """NTCPQ8 — Étapes d'approbation de remise d'un devis, en dicts JSON-safe
    (pour l'écran « Approbation » du devis)."""
    etapes = EtapeApprobationDevis.objects.filter(
        devis_id=devis.id).select_related('approbateur').order_by(
            'niveau', 'id')
    return [{
        'id': e.id,
        'niveau': e.niveau,
        'niveau_approbation': e.niveau_approbation,
        'statut': e.statut,
        'approbateur': (
            getattr(e.approbateur, 'username', None) if e.approbateur_id
            else None),
        'decision_le': e.decision_le.isoformat() if e.decision_le else None,
        'commentaire': e.commentaire,
    } for e in etapes]


def violations_compatibilite(*, company, produit_ids):
    """NTCPQ1 — Évalue les contraintes de compatibilité pour une sélection.

    ``produit_ids`` : itérable d'IDs de ``stock.Produit`` sélectionnés. Renvoie
    une liste de dicts ``{type, produit_a, produit_b, message, bloquante}`` pour
    chaque contrainte de la société qui est violée par la sélection :

      * ``INCOMPATIBLE`` : les deux produits sont présents → violation bloquante.
      * ``REQUIERT`` : ``produit_a`` présent sans ``produit_b`` → bloquante.
      * ``RECOMMANDE`` : ``produit_a`` présent sans ``produit_b`` → avertissement.
    """
    ids = {int(p) for p in produit_ids if p is not None}
    if not ids:
        return []
    qs = ContrainteCompatibilite.objects.filter(
        company=company, produit_a__in=ids)
    violations = []
    for c in qs:
        a_present = c.produit_a_id in ids
        b_present = c.produit_b_id in ids
        if not a_present:
            continue
        if c.type == ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE:
            if b_present:
                violations.append(_violation(c))
        else:  # REQUIERT / RECOMMANDE : a présent, b manquant → déclenche.
            if not b_present:
                violations.append(_violation(c))
    return violations


def _violation(contrainte):
    return {
        'type': contrainte.type,
        'produit_a': contrainte.produit_a_id,
        'produit_b': contrainte.produit_b_id,
        'message': contrainte.message_utilisateur,
        'bloquante': contrainte.bloquante,
    }


def alternatives_violation(*, company, produit_ids, violation):
    """NTCPQ29 — Alternatives COMPATIBLES pour résoudre une violation
    bloquante (issue de ``violations_compatibilite``), au lieu d'un simple
    message d'erreur sans issue.

      * ``REQUIERT`` (``produit_a`` présent sans ``produit_b``) : la SEULE
        alternative valable est d'AJOUTER ``produit_b`` (le produit requis
        lui-même) — ``source: 'a_ajouter'``.
      * ``INCOMPATIBLE`` : cherche un SUBSTITUT du produit incompatible
        (``ProduitEquivalent``, NTCPQ16, n'importe quel tier) puis, à
        défaut, des produits ``RECOMMANDE`` (NTCPQ1) liés à l'AUTRE membre
        de la violation — jamais un produit déjà dans la sélection.

    Renvoie jusqu'à 3 dicts ``{produit_id, nom, source}``, liste vide si
    aucune alternative connue (l'appelant retombe alors sur le simple
    message)."""
    # Lecture cross-app stock via son SÉLECTEUR (règle de modularité
    # CLAUDE.md : jamais un import de `apps.stock.models` depuis une autre
    # app). `get_produit_scoped` est exactement le même filtre scopé société.
    from apps.stock.selectors import get_produit_scoped
    from .models import ProduitEquivalent

    ids = {int(p) for p in produit_ids if p is not None}

    if violation['type'] != ContrainteCompatibilite.TypeContrainte.INCOMPATIBLE:
        # REQUIERT : produit_b est le produit MANQUANT — l'ajouter EST la
        # résolution, pas un substitut.
        produit = get_produit_scoped(company, violation['produit_b'])
        if produit is None:
            return []
        return [{'produit_id': produit.id, 'nom': produit.nom,
                 'source': 'a_ajouter'}]

    cible = violation['produit_b']
    autre = violation['produit_a']
    vus = set()
    candidats = []

    for eq in (ProduitEquivalent.objects
               .filter(company=company, produit_source_id=cible, actif=True)
               .select_related('produit_substitut')
               .order_by('tier', 'id')):
        if eq.produit_substitut_id in ids or eq.produit_substitut_id in vus:
            continue
        vus.add(eq.produit_substitut_id)
        candidats.append({
            'produit_id': eq.produit_substitut_id,
            'nom': eq.produit_substitut.nom, 'source': 'substitut'})

    if len(candidats) < 3:
        recommande = ContrainteCompatibilite.TypeContrainte.RECOMMANDE
        qs_reco = (ContrainteCompatibilite.objects
                   .filter(company=company, produit_a_id=autre,
                           type=recommande)
                   .select_related('produit_b').order_by('id'))
        for c in qs_reco:
            if c.produit_b_id in ids or c.produit_b_id in vus:
                continue
            vus.add(c.produit_b_id)
            candidats.append({
                'produit_id': c.produit_b_id, 'nom': c.produit_b.nom,
                'source': 'recommande'})
            if len(candidats) >= 3:
                break

    return candidats[:3]


def evaluer_regles_produit(*, company, context):
    """NTCPQ2 — Évalue les règles produit actives de la société contre un
    ``context`` (dict plat construit par l'appelant depuis les lignes/champs du
    devis) via ``core.rules.evaluate_condition_group``.

    Renvoie la liste des règles déclenchées :
    ``[{regle_id, nom, actions}, ...]``."""
    if not isinstance(context, dict):
        context = {}
    declenchees = []
    for regle in RegleProduitCPQ.objects.filter(company=company, actif=True):
        if evaluate_condition_group(regle.condition_group, context):
            declenchees.append({
                'regle_id': regle.id,
                'nom': regle.nom,
                'actions': regle.actions,
                # NTCPQ21 — avertissement (défaut) vs règle bloquante.
                'bloquante': regle.bloquante,
            })
    return declenchees


def contexte_regles_devis(devis):
    """NTCPQ21 — Contexte plat d'un devis pour l'évaluation des règles NTCPQ2.

    Expose ``produit_ids`` (liste — utilisable avec l'opérateur ``contains``),
    ``designations``, ``mode_installation``, ``total_ht``, ``nb_lignes`` et
    ``puissance_kwc``. Aucune donnée de marge / ``prix_achat``."""
    lignes = list(devis.lignes.all())
    etude = devis.etude_params if isinstance(devis.etude_params, dict) else {}
    try:
        kwc = float(etude.get('puissance_kwc') or 0)
    except (TypeError, ValueError):
        kwc = 0.0
    try:
        total_ht = float(devis.total_ht or 0)
    except (TypeError, ValueError):
        total_ht = 0.0
    return {
        'produit_ids': [li.produit_id for li in lignes if li.produit_id],
        'designations': [li.designation for li in lignes],
        'mode_installation': devis.mode_installation or '',
        'type_deal': devis.mode_installation or '',
        'total_ht': total_ht,
        'nb_lignes': len(lignes),
        'puissance_kwc': kwc,
    }


def etat_configuration_devis(devis):
    """NTCPQ21 — État de conformité de la configuration d'un devis.

    Exécute les règles produit (NTCPQ2) ET les contraintes de compatibilité
    (NTCPQ1) et renvoie ::

        {'configuration_valide': bool, 'bloquant': bool, 'violations': [...]}

    ``configuration_valide`` est faux dès qu'une violation existe (badge
    rouge) ; ``bloquant`` n'est vrai que pour une contrainte bloquante
    (INCOMPATIBLE/REQUIERT) ou une règle explicitement ``bloquante`` — un
    simple avertissement n'empêche JAMAIS l'enregistrement en brouillon.
    Calculé à la volée, jamais stocké."""
    company = getattr(devis, 'company', None)
    if company is None:
        return {'configuration_valide': True, 'bloquant': False,
                'violations': []}

    violations = []
    produit_ids = [li.produit_id for li in devis.lignes.all() if li.produit_id]
    for v in violations_compatibilite(company=company,
                                      produit_ids=produit_ids):
        violations.append({
            'source': 'compatibilite',
            'type': v['type'],
            'message': v['message'] or (
                f"Produits {v['produit_a']} / {v['produit_b']} : "
                f"{v['type'].lower()}"),
            'bloquante': v['bloquante'],
        })

    for regle in evaluer_regles_produit(
            company=company, context=contexte_regles_devis(devis)):
        violations.append({
            'source': 'regle',
            'type': 'REGLE',
            'regle_id': regle['regle_id'],
            'message': regle['nom'],
            'bloquante': bool(regle.get('bloquante')),
        })

    return {
        'configuration_valide': not violations,
        'bloquant': any(v['bloquante'] for v in violations),
        'violations': violations,
    }


def devis_marge_sous_seuil(devis):
    """NTCPQ6 — INTERNE : une ligne du devis est-elle sous le seuil de marge
    minimale de sa famille (catégorie) ?

    Marge ligne = ``(prix_unitaire - produit.prix_achat) / prix_unitaire`` en %.
    Comparée à ``SeuilMargeFamille.marge_min_pct`` de la catégorie du produit.
    Renvoie ``True`` dès qu'une ligne passe sous son seuil. Aucun seuil
    configuré ⇒ ``False``. JAMAIS exposé côté client (règle #4)."""
    company_id = getattr(devis, 'company_id', None)
    if company_id is None:
        return False
    seuils = {
        s.categorie_id: s.marge_min_pct
        for s in SeuilMargeFamille.objects.filter(company_id=company_id)}
    if not seuils:
        return False
    for ligne in devis.lignes.all():
        produit = ligne.produit
        if produit is None or ligne.prix_unitaire is None:
            continue
        seuil = seuils.get(produit.categorie_id)
        if seuil is None:
            continue
        pv = Decimal(str(ligne.prix_unitaire))
        if pv <= 0:
            continue
        pa = Decimal(str(produit.prix_achat or 0))
        marge_pct = (pv - pa) / pv * Decimal('100')
        if marge_pct < Decimal(str(seuil)):
            return True
    return False


def clause_sapplique(clause, context):
    """NTCPQ11 — Une clause s'applique-t-elle à ce contexte de devis ?

    Deux filtres cumulés : ``type_deal`` (référentiel libre, vide = tous types,
    comparaison insensible à la casse/aux espaces) puis ``applicable_si``
    (arbre ET/OU/NON évalué par ``core.rules`` ; vide = toujours vrai)."""
    if not isinstance(context, dict):
        context = {}
    attendu = (clause.type_deal or '').strip().lower()
    if attendu:
        recu = str(context.get('type_deal') or '').strip().lower()
        if recu != attendu:
            return False
    arbre = clause.applicable_si
    if not arbre:
        return True
    return evaluate_condition_group(arbre, context)


_OPERATEURS_LISIBLES = {
    'eq': '=', 'ne': '≠', 'gt': '>', 'gte': '≥', 'lt': '<', 'lte': '≤',
    'in': 'parmi', 'not_in': 'hors de', 'contains': 'contient',
    'startswith': 'commence par', 'exists': 'est renseigné',
}
_GROUPES_LISIBLES = {'and': ' ET ', 'or': ' OU '}


def condition_en_clair(noeud):
    """NTCPQ12 — Traduit un arbre ``core.rules`` en français lisible.

    Ex. ``{'op': 'and', 'conditions': [{'field': 'type_deal', ...}, ...]}``
    → ``"type_deal=Industriel ET montant>500000"``. Arbre vide → « toujours »
    (une clause sans condition s'applique systématiquement). Purement
    descriptif : n'évalue rien, ne lève jamais."""
    if not noeud:
        return 'toujours'
    if not isinstance(noeud, dict):
        return str(noeud)
    op = noeud.get('op')
    if 'conditions' in noeud or op in ('and', 'or', 'not'):
        enfants = noeud.get('conditions') or []
        rendus = [condition_en_clair(e) for e in enfants if e]
        if not rendus:
            return 'toujours'
        if op == 'not':
            return f'NON ({rendus[0]})'
        joint = _GROUPES_LISIBLES.get(op or 'and', ' ET ')
        if len(rendus) == 1:
            return rendus[0]
        return joint.join(f'({r})' if ' ET ' in r or ' OU ' in r else r
                          for r in rendus)
    champ = noeud.get('field', '?')
    operateur = noeud.get('operator', 'eq')
    valeur = noeud.get('value')
    lisible = _OPERATEURS_LISIBLES.get(operateur, operateur)
    if operateur == 'exists':
        return f'{champ} {lisible}'
    if isinstance(valeur, (list, tuple)):
        valeur = ', '.join(str(v) for v in valeur)
    if lisible in ('=', '≠', '>', '≥', '<', '≤'):
        return f'{champ}{lisible}{valeur}'
    return f'{champ} {lisible} {valeur}'


def _percentile(valeurs_triees, p):
    """Percentile ``p`` (0-100) par interpolation linéaire (méthode « nearest
    rank » interpolée, sans dépendance externe). ``valeurs_triees`` DOIT déjà
    être triée. Renvoie 0 sur une liste vide."""
    if not valeurs_triees:
        return 0
    if len(valeurs_triees) == 1:
        return valeurs_triees[0]
    k = (len(valeurs_triees) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(valeurs_triees) - 1)
    if f == c:
        return valeurs_triees[f]
    return valeurs_triees[f] + (valeurs_triees[c] - valeurs_triees[f]) * (k - f)


def delai_approbation_stats(company, *, date_debut=None, date_fin=None,
                            approbateur_id=None):
    """NTCPQ48 — moyenne + p90 (heures) du délai entre création d'une
    ``EtapeApprobationDevis`` (NTCPQ7) et sa décision, sur les étapes déjà
    DÉCIDÉES (``decision_le`` renseigné — une étape encore ``en_attente``
    n'a pas de délai final). Filtrable par période (``date_creation``) et
    par ``approbateur_id`` — utilisé par le widget KPI fédéré SANS filtre
    (période complète) et directement testable AVEC filtres.

    Renvoie ``{'moyenne_heures': float, 'p90_heures': float, 'count': int}``
    (zéros si aucune étape décidée)."""
    qs = EtapeApprobationDevis.objects.filter(
        company=company, decision_le__isnull=False)
    if date_debut:
        qs = qs.filter(date_creation__date__gte=date_debut)
    if date_fin:
        qs = qs.filter(date_creation__date__lte=date_fin)
    if approbateur_id:
        qs = qs.filter(approbateur_id=approbateur_id)

    delais = sorted(
        (e.decision_le - e.date_creation).total_seconds() / 3600
        for e in qs.only('decision_le', 'date_creation'))
    if not delais:
        return {'moyenne_heures': 0.0, 'p90_heures': 0.0, 'count': 0}
    moyenne = round(sum(delais) / len(delais), 1)
    p90 = round(_percentile(delais, 90), 1)
    return {'moyenne_heures': moyenne, 'p90_heures': p90, 'count': len(delais)}


def kpi_delai_approbation(company):
    """NTCPQ48 — provider KPI fédéré (ARC40, ``core.platform.kpi_providers``) :
    tuiles ``[{id, label, valeur, unite}]`` — délai moyen ET p90
    d'approbation de remise (NTCPQ7), sur toute la société (pas de filtre —
    le détail filtrable par période/approbateur vit dans
    ``delai_approbation_stats``, appelable directement). Liste vide tant
    qu'aucune étape n'a été décidée (jamais de tuile à 0 trompeuse)."""
    stats = delai_approbation_stats(company)
    if not stats['count']:
        return []
    return [
        {'id': 'cpq_delai_moyen_approbation',
         'label': "Délai moyen d'approbation de remise",
         'valeur': stats['moyenne_heures'], 'unite': 'h'},
        {'id': 'cpq_delai_p90_approbation',
         'label': "Délai p90 d'approbation de remise",
         'valeur': stats['p90_heures'], 'unite': 'h'},
    ]


def taux_utilisation_offres_groupees(company):
    """NTCPQ49(a) — % des devis ENVOYÉS (``date_envoi`` renseigné) contenant
    au moins une ``OffreGroupee`` (NTCPQ3) appliquée. ``LigneDevis`` ne
    porte pas de référence structurelle vers l'offre qui l'a créée — le
    signal utilisé est l'entrée chatter posée par NTCPQ45
    (``« Offre groupée » appliquée``, ``apps.cpq.services.
    appliquer_offre_groupee``), unique marqueur fiable disponible.
    ``0.0`` sans devis envoyé (jamais une division par zéro)."""
    from apps.ventes.selectors import devis_envoyes_periode
    devis_qs = devis_envoyes_periode(company)
    total = devis_qs.count()
    if not total:
        return 0.0
    avec_bundle = devis_qs.filter(
        activites__body__icontains='Offre groupée').distinct().count()
    return round(avec_bundle * 100.0 / total, 1)


def taux_conversion_configurateur(company):
    """NTCPQ49(b) — % des sessions configurateur (NTCPQ9, démarrage) ayant
    abouti à un devis ENVOYÉ (funnel démarrage → devis brouillon → devis
    envoyé). N'INCLUT JAMAIS un devis encore brouillon non envoyé au
    numérateur (``devis__date_envoi__isnull=False`` strict). ``0.0`` sans
    session (jamais une division par zéro)."""
    from .models import SessionConfigurateur
    total = SessionConfigurateur.objects.filter(company=company).count()
    if not total:
        return 0.0
    envoyes = SessionConfigurateur.objects.filter(
        company=company, devis__isnull=False,
        devis__date_envoi__isnull=False).count()
    return round(envoyes * 100.0 / total, 1)


def kpi_taux_bundle_configurateur(company):
    """NTCPQ49 — provider KPI fédéré (ARC40) : deux tuiles, taux
    d'utilisation des offres groupées (a) et taux de conversion
    configurateur → devis envoyé (b). Une tuile n'apparaît que si son
    dénominateur est non nul (jamais un « 0 % » trompeur sans aucune
    donnée)."""
    tuiles = []
    from apps.ventes.selectors import devis_envoyes_periode
    from .models import SessionConfigurateur
    if devis_envoyes_periode(company).exists():
        tuiles.append({
            'id': 'cpq_taux_offres_groupees',
            'label': "Devis envoyés avec offre groupée",
            'valeur': taux_utilisation_offres_groupees(company),
            'unite': '%'})
    if SessionConfigurateur.objects.filter(company=company).exists():
        tuiles.append({
            'id': 'cpq_taux_conversion_configurateur',
            'label': 'Conversion configurateur → devis envoyé',
            'valeur': taux_conversion_configurateur(company),
            'unite': '%'})
    return tuiles


def clauses_applicables(*, company, context):
    """NTCPQ11 — Clauses/CGV actives de la société qui s'appliquent au contexte.

    Renvoie une liste JSON-safe (ordonnée par ``ordre`` puis ``id``) :
    ``[{clause_id, nom, corps_texte, type_deal, ordre}, ...]``. C'est cette
    liste qui est FIGÉE sur ``Devis.clauses_appliquees`` à l'envoi."""
    clauses = ClauseCGV.objects.filter(
        company=company, actif=True).order_by('ordre', 'id')
    return [{
        'clause_id': c.id,
        'nom': c.nom,
        'corps_texte': c.corps_texte,
        'type_deal': c.type_deal,
        'ordre': c.ordre,
    } for c in clauses if clause_sapplique(c, context)]
