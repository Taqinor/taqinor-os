"""QJR61 — ``etude_params`` a enfin un SCHÉMA, un VALIDATEUR et UN ÉCRIVAIN.

CE QUE CE MODULE FERME. ``Devis.etude_params`` est un JSONField sans forme
déclarée, écrit par une douzaine de chemins (le générateur, les quatre
rafraîchisseurs serveur, la fusion ``etude_extra`` de l'auto-devis, la
resynchro, le PATCH du devis…). Personne ne pouvait dire QUELLE clé appartient
à QUI, ni si elle est une ENTRÉE du client ou une valeur DÉRIVÉE du moteur.
Conséquence vécue : un PATCH partiel venu de l'écran REMPLAÇAIT le bloc entier
et faisait disparaître en silence ``factures_mensuelles_reelles``, ``gamme``,
``etude_horaire`` et ``dimensionnement``.

LES TROIS PIÈCES.

* :data:`SCHEMA` — par clé de TÊTE : son type, son PROPRIÉTAIRE (l'étape qui a
  le droit de l'écrire) et sa nature (ENTRÉE du client / DÉRIVÉE du moteur).
* :func:`valider` — PURE, sans base : rend la liste des reproches (clé
  inconnue, type impossible), jamais une exception.
* :func:`ecrire` — LE SEUL écrivain. Il **FUSIONNE** (jamais un remplacement en
  bloc), REFUSE une clé DÉRIVÉE écrite par un non-propriétaire, et persiste en
  ``update_fields=['etude_params']`` — donc sans jamais toucher un statut, une
  ligne ou un total (règle #4).

POURQUOI « PROPRIÉTAIRE » ET PAS « LECTURE SEULE ». Une valeur dérivée n'est pas
interdite d'écriture : elle est interdite à QUI NE LA CALCULE PAS. Le
rafraîchisseur horaire a le droit de poser ``etude_horaire`` — c'est lui qui le
produit ; l'écran, non. Ce module NOMME cette différence au lieu de la laisser
se jouer au dernier arrivé.
"""

# ── Les PROPRIÉTAIRES (l'étape qui a le droit d'écrire une clé DÉRIVÉE) ──────
#: L'écran / le générateur de devis (entrées du commercial).
ECRAN = 'ecran'
#: Le rafraîchisseur d'étude horaire (``services.rafraichir_etude_horaire``).
MOTEUR_HORAIRE = 'moteur_horaire'
#: Le rafraîchisseur de dimensionnement (``rafraichir_dimensionnement_devis``).
MOTEUR_DIMENSIONNEMENT = 'moteur_dimensionnement'
#: ``profils_comparatifs.rafraichir_profils_comparatifs_devis``.
MOTEUR_PROFILS = 'moteur_profils'
#: La tâche d'étude bankable asynchrone (``tasks.task_simulate_bankable_study``).
MOTEUR_SIMULATION = 'moteur_simulation'
#: Le calepinage 3D (``build_devis_from_layout`` / ``sync_devis_from_layout``).
CALEPINAGE = 'calepinage'
#: La création automatique depuis un lead (``services.build_devis_auto``).
AUTO_DEVIS = 'auto_devis'
#: Personne : clé HISTORIQUE que plus aucun chemin ne pose (voir les notes).
ORPHELINE = 'orpheline'

#: Nature d'une clé.
ENTREE = 'entree'
DERIVEE = 'derivee'


def _cle(type_attendu, proprietaire, nature, note=''):
    return {'type': type_attendu, 'proprietaire': proprietaire,
            'nature': nature, 'note': note}


#: LE SCHÉMA des clés de TÊTE d'``etude_params``, relevé par scan de l'arbre
#: (29/08/2026). ``type`` est un tuple accepté par ``isinstance`` ; ``None`` y
#: est TOUJOURS toléré (une clé absente et une clé nulle disent la même chose :
#: « pas calculable », règle Z2).
SCHEMA = {
    # ── Les CHOIX du commercial (ENTRÉES) ────────────────────────────────────
    'scenario': _cle((str,), ECRAN, ENTREE,
                     'Sans batterie / Avec batterie / Les deux — QJR64 le fait '
                     'passer par le registre de surcharges.'),
    'recommended_option': _cle((str,), ECRAN, ENTREE),
    'gamme': _cle((str, dict), ECRAN, ENTREE),
    'mode_installation': _cle((str,), ECRAN, ENTREE),
    'tension_raccordement': _cle((str,), ECRAN, ENTREE),
    'distributeur': _cle((str,), ECRAN, ENTREE),
    'categorie_commerciale': _cle((str,), ECRAN, ENTREE),
    'origine': _cle((str,), ECRAN, ENTREE),
    'nombre_proprietes': _cle((int,), ECRAN, ENTREE),
    'factures_mensuelles_reelles': _cle((list,), ECRAN, ENTREE,
                                        'Les factures RÉELLES du client — la '
                                        'donnée la plus précieuse du dossier.'),
    'conso_kwh_mensuelles': _cle((list,), ECRAN, ENTREE),
    'conso_annuelle': _cle((int, float), ECRAN, ENTREE),
    'toiture': _cle((dict,), ECRAN, ENTREE),
    'attribution': _cle((dict,), ECRAN, ENTREE),
    'resync_apres_envoi': _cle((bool,), CALEPINAGE, ENTREE),

    # ── Ce que le MOTEUR calcule (DÉRIVÉES) ──────────────────────────────────
    'etude_horaire': _cle((dict,), MOTEUR_HORAIRE, DERIVEE),
    'dimensionnement': _cle((dict,), MOTEUR_DIMENSIONNEMENT, DERIVEE),
    'profils_comparatifs': _cle((dict,), MOTEUR_PROFILS, DERIVEE),
    'simulation': _cle((dict,), MOTEUR_SIMULATION, DERIVEE),
    'puissance_kwc': _cle((int, float), CALEPINAGE, DERIVEE,
                          'QJR63 lui donne UN propriétaire : le registre, '
                          'sinon la dérivation depuis les LIGNES.'),
    'production_annuelle': _cle((int, float), CALEPINAGE, DERIVEE),
    'economies_annuelles': _cle((int, float), CALEPINAGE, DERIVEE),
    'autoconso_sans': _cle((int, float), CALEPINAGE, DERIVEE),
    'autoconso_avec': _cle((int, float), CALEPINAGE, DERIVEE),

    # ── Le bloc AGRICOLE (pompage) — dérivé de l'étude de pompage ────────────
    'pompe_cv': _cle((int, float), ECRAN, ENTREE),
    'pompe_kw': _cle((int, float), ECRAN, ENTREE),
    'hmt_m': _cle((int, float), ECRAN, ENTREE),
    'debit_hmt_m3h': _cle((int, float), ECRAN, DERIVEE),
    'm3_jour': _cle((int, float), ECRAN, DERIVEE),
    'champ_kwc': _cle((int, float), ECRAN, DERIVEE),
    'irrigation_method': _cle((str,), ECRAN, ENTREE),

    # ── Les DÉRIVÉES du marché industriel / commercial ───────────────────────
    'taux_autoconso': _cle((int, float), ECRAN, DERIVEE),
    'taux_couverture': _cle((int, float), ECRAN, DERIVEE),
    'payback': _cle((int, float), ECRAN, DERIVEE),
    'injection_kwh_an': _cle((int, float), ECRAN, DERIVEE),
    'injection_dh_an': _cle((int, float), ECRAN, DERIVEE),

    # ── Clé HISTORIQUE sans écrivain ─────────────────────────────────────────
    'payback_annees': _cle(
        (int, float), ORPHELINE, DERIVEE,
        "QJR48 a supprimé son unique écrivain (le récepteur QX24) : aucun "
        "consommateur du dépôt ne la lit. Déclarée ici pour qu'un devis "
        "ANCIEN qui la porte encore ne soit pas signalé comme invalide."),
}


def valider(etude_params):
    """Les reproches faits à un bloc ``etude_params`` — ``[]`` quand tout va.

    PURE, sans base, sans exception : c'est une LISTE de messages FR, pour que
    l'appelant décide (400 côté endpoint, avertissement côté outillage).

    Deux reproches seulement, et ils sont structurels :

    * une clé de TÊTE inconnue du schéma — c'est ainsi qu'un champ inventé
      côté client se glissait dans les entrées du PDF ;
    * une valeur du mauvais TYPE — une liste de factures rendue en texte, un
      bloc horaire rendu en liste.

    ``None`` est TOUJOURS toléré : une clé absente et une clé nulle disent la
    même chose (« pas calculable » — règle Z2).
    """
    if etude_params is None:
        return []
    if not isinstance(etude_params, dict):
        return ['`etude_params` doit être un objet JSON.']
    reproches = []
    for cle, valeur in etude_params.items():
        regle = SCHEMA.get(cle)
        if regle is None:
            reproches.append(
                "Clé inconnue de l'étude : « %s ». Le schéma "
                '(`domain/etude_schema.py`) est la seule porte.' % cle)
            continue
        if valeur is None:
            continue
        if isinstance(valeur, bool) and bool not in regle['type']:
            reproches.append(
                '« %s » : un booléen n\'est pas une valeur admise ici.' % cle)
            continue
        if not isinstance(valeur, regle['type']):
            reproches.append(
                '« %s » : type %s inattendu (attendu : %s).'
                % (cle, type(valeur).__name__,
                   ' ou '.join(t.__name__ for t in regle['type'])))
    return reproches


def cles_refusees_pour(proprietaire, cles):
    """Les clés DÉRIVÉES que ``proprietaire`` n'a pas le droit d'écrire.

    Une clé d'ENTRÉE est écrivable par n'importe quelle étape (c'est un choix
    du commercial, il peut arriver de plusieurs écrans). Une clé DÉRIVÉE
    n'appartient qu'à l'étape QUI LA CALCULE : la laisser écrire par une autre,
    c'est exactement le mécanisme par lequel un chiffre du moteur se faisait
    remplacer par un chiffre d'écran.

    ``proprietaire=None`` (aucune étape déclarée) ⇒ AUCUNE clé dérivée n'est
    admise : un écrivain anonyme ne pose que des entrées.
    """
    refusees = []
    for cle in cles:
        regle = SCHEMA.get(cle)
        if regle is None or regle['nature'] != DERIVEE:
            continue
        if regle['proprietaire'] != proprietaire:
            refusees.append(cle)
    return refusees


def ecrire(devis, *, proprietaire=None, **cles):
    """L'UNIQUE écrivain d'``etude_params`` — il FUSIONNE, il ne remplace pas.

    C'EST LA DIFFÉRENCE QUI COMPTE. Un PATCH partiel écrasait le bloc entier :
    toute clé que l'émetteur ne reconstruisait pas lui-même
    (``factures_mensuelles_reelles``, ``gamme``, et tout ce que les quatre
    rafraîchisseurs du serveur avaient écrit) DISPARAISSAIT à la sauvegarde
    suivante. Ici, seules les clés REÇUES bougent ; les autres sont intouchées,
    bit à bit.

    ``proprietaire`` — l'étape qui écrit (voir les constantes du module). Une
    clé DÉRIVÉE dont elle n'est pas propriétaire lève ``ValueError``, jamais un
    silence : c'est l'appelant qui doit dire d'où vient son chiffre.

    Une valeur ``None`` RETIRE la clé (règle Z2 : une étude qui n'est plus
    calculable est retirée, jamais laissée périmée).

    Persiste en ``update_fields=['etude_params']`` : ni statut, ni ligne, ni
    total ne sont touchés (règle #4). Rend le bloc résultant.
    """
    refusees = cles_refusees_pour(proprietaire, cles)
    if refusees:
        raise ValueError(
            'Clé(s) dérivée(s) %s : seule l\'étape qui les CALCULE peut les '
            'écrire (propriétaire déclaré : %s).'
            % (', '.join(sorted(refusees)), proprietaire or 'aucun'))
    reproches = valider(cles)
    if reproches:
        raise ValueError(' ; '.join(reproches))

    bloc = dict(getattr(devis, 'etude_params', None) or {})
    for cle, valeur in cles.items():
        if valeur is None:
            bloc.pop(cle, None)
        else:
            bloc[cle] = valeur
    devis.etude_params = bloc
    if getattr(devis, 'pk', None) is not None:
        devis.save(update_fields=['etude_params'])
    return bloc
