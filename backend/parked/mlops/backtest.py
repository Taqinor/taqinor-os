"""NTAI28 — Backtesting des scorers purs de ``core/*.py`` (évaluation sur
historique CONNU).

Pur, OFFLINE, déterministe : aucun appel réseau/LLM, aucune bibliothèque
tierce (précision/rappel/exactitude/AUC sont calculés à la main — le dépôt ne
dépend pas de ``scikit-learn``). Les features rejouées viennent des datasets
BI existants (``core.data_explorer``, déjà scopés société) — jamais un import
direct de ``crm``/``ventes``.

MÉTHODOLOGIE — POURQUOI ``stage``/``perdu`` NE SONT JAMAIS REJOUÉS EN ENTRÉE.
``core.win_probability.win_probability`` court-circuite à 1.0 quand
``stage == 'SIGNED'`` et à 0.0 quand ``perdu is True`` — or ``crm_leads``
n'expose que l'état COURANT (final) d'un lead, jamais un instantané au moment
de la prédiction (cet historique n'existe pas encore — c'est justement ce que
``FeatureVector``, NTAI30, commence à matérialiser POUR L'AVENIR). Rejouer le
``stage`` final ou le drapeau ``perdu`` reviendrait à donner au scorer la
réponse : le backtest mesurerait sa propre tautologie, jamais son pouvoir
prédictif. Ce module ne rejoue donc QUE les signaux connus AVANT l'issue
(``canal``, ``priorite``) — un backtest honnête sur un jeu de features
partiel, jamais un chiffre gonflé par la fuite de l'étiquette.
"""
from __future__ import annotations

# Seuil de classification par défaut (score >= seuil ⇒ prédiction « gagné »).
SEUIL_DEFAUT = 0.5

# Borne défensive sur la taille de l'échantillon rejoué (les métriques restent
# en O(n) ; seule l'AUC est O(n_positifs × n_negatifs) — voir ``_auc``).
LIMITE_ECHANTILLON = 2000

SCORERS_SUPPORTES = ('win_proba', 'retard_paiement')


def _confusion_metrics(y_true, y_scores, *, seuil):
    """Précision/rappel/exactitude à un seuil fixe, sur des labels CONNUS.

    Une métrique de classification binaire n'a pas de sens sur un jeu à une
    seule classe : ``precision``/``rappel`` valent ``None`` (jamais 0 ou 1
    inventés) quand leur dénominateur est nul."""
    vp = fp = vn = fn = 0
    for y, score in zip(y_true, y_scores):
        prediction = score >= seuil
        if y and prediction:
            vp += 1
        elif y and not prediction:
            fn += 1
        elif not y and prediction:
            fp += 1
        else:
            vn += 1
    return {
        'precision': (vp / (vp + fp)) if (vp + fp) else None,
        'rappel': (vp / (vp + fn)) if (vp + fn) else None,
        'exactitude': ((vp + vn) / len(y_true)) if y_true else None,
        'vrais_positifs': vp, 'faux_positifs': fp,
        'vrais_negatifs': vn, 'faux_negatifs': fn,
    }


def _auc(y_true, y_scores):
    """Aire sous la courbe ROC (statistique U de Mann-Whitney), sans
    dépendance externe. ``None`` si l'échantillon ne porte qu'une seule
    classe (l'AUC n'est alors pas définie)."""
    positifs = [s for y, s in zip(y_true, y_scores) if y]
    negatifs = [s for y, s in zip(y_true, y_scores) if not y]
    if not positifs or not negatifs:
        return None
    total = 0.0
    for p in positifs:
        for n in negatifs:
            if p > n:
                total += 1.0
            elif p == n:
                total += 0.5
    return round(total / (len(positifs) * len(negatifs)), 4)


def _backtest_win_proba(company, *, user=None, seuil=SEUIL_DEFAUT,
                        periode=None, limite=LIMITE_ECHANTILLON):
    from core import data_explorer
    from core.win_probability import win_probability

    filtres = {}
    if periode:
        debut, fin = periode
        if debut:
            filtres['mois_creation__gte'] = debut
        if fin:
            filtres['mois_creation__lte'] = fin

    try:
        lignes = data_explorer.run_query(
            'crm_leads', company, user,
            {'select': ['id', 'canal', 'priorite', 'perdu_bool',
                        'signe_num'],
             'filters': filtres, 'limit': limite})
    except data_explorer.DatasetInconnu:
        return {'nom': 'win_proba', 'disponible': False,
                'motif': 'Dataset crm_leads introuvable.'}

    y_true, y_scores = [], []
    for ligne in lignes:
        signe = bool(ligne.get('signe_num'))
        perdu = bool(ligne.get('perdu_bool'))
        if not signe and not perdu:
            continue  # issue encore inconnue (en cours) : hors échantillon.
        # Rejoue UNIQUEMENT canal/priorite (voir docstring de tête — jamais
        # stage/perdu, qui fuiteraient l'étiquette).
        resultat = win_probability({
            'canal': ligne.get('canal'), 'priorite': ligne.get('priorite'),
        })
        y_true.append(signe)
        y_scores.append(resultat.probability)

    if not y_true:
        return {
            'nom': 'win_proba', 'disponible': False,
            'motif': ('Aucun lead à issue connue (signé ou perdu) dans le '
                      'périmètre demandé.'),
        }

    metriques = _confusion_metrics(y_true, y_scores, seuil=seuil)
    return {
        'nom': 'win_proba',
        'disponible': True,
        'taille_echantillon': len(y_true),
        'seuil': seuil,
        'auc': _auc(y_true, y_scores),
        **metriques,
    }


def backtester(company, nom, periode=None, *, seuil=SEUIL_DEFAUT, user=None):
    """NTAI28 — Rejoue un scorer sur un jeu HISTORIQUE dont l'issue est
    CONNUE et calcule précision/rappel/exactitude/AUC. Pur, offline,
    déterministe.

    ``nom`` — ``'win_proba'`` (rejoue ``core.win_probability`` sur les leads
    SIGNÉS/PERDUS, dataset ``crm_leads``) ou ``'retard_paiement'``. ``periode``
    — ``(date_debut, date_fin)`` (objets ``date``, bornes incluses, l'une ou
    l'autre optionnelle) filtrant sur le MOIS de création du lead
    (``mois_creation``, seule granularité temporelle exposée par le dataset).

    Lève ``ValueError`` sur un nom de scorer inconnu (erreur de programmation
    de l'appelant — pas une réponse HTTP)."""
    if nom == 'win_proba':
        return _backtest_win_proba(company, user=user, seuil=seuil,
                                   periode=periode)
    if nom == 'retard_paiement':
        # AUCUNE date de paiement réelle n'est exposée par un sélecteur
        # accessible ici : `ventes.bi_datasets` (`ventes_factures`) ne porte
        # que `date_echeance`/`reste_du` (état COURANT), jamais la date à
        # laquelle une facture soldée a été RÉELLEMENT payée — et
        # `facturation`/`compta` (qui portent `date_paiement`) sont hors du
        # périmètre de cette app. Sans cette donnée, « payé en retard » ne
        # peut être ni lu ni dérivé : jamais un chiffre inventé à la place.
        return {
            'nom': 'retard_paiement',
            'disponible': False,
            'motif': (
                "Backtest indisponible : aucune date de paiement réelle "
                "n'est exposée à ce module (ventes_factures n'a que "
                "date_echeance/reste_du) pour déterminer si une facture "
                "soldée a été payée en retard."),
        }
    raise ValueError(
        'Scorer de backtest inconnu (attendu : %s).'
        % ', '.join(SCORERS_SUPPORTES))
