"""QJR57 — LE REGISTRE UNIQUE DES SURCHARGES D'UN DEVIS.

CE QUE CE MODULE FERME. L'audit L3 du 29/08/2026 a trouvé QUATRE mécanismes de
surcharge incompatibles (le mécanisme ``saisie_manuelle`` noms-seuls, des
attributs épars sur ``etude_params``, des recalculs silencieux à chaque lecture,
et RIEN DU TOUT pour d'autres champs) qui ne s'accordent jamais sur ce que le
vendeur a TAPÉ vs ce que le moteur aurait CALCULÉ. Ici : une liste blanche, un
résolveur, un sérialiseur. Un seul endroit.

LES TROIS PROPRIÉTÉS DE SÛRETÉ, écrites dans le contrat PACT10
``apps/ventes/contract_samples/devis_overrides.json`` et tenues par ce module :

1. **ENTRÉES SEULES.** Le registre ne porte QUE des choix du vendeur que le
   moteur ne peut pas redériver. Jamais un CHAMP DÉRIVÉ (un total, un ratio, un
   montant calculé) : l'y poser créerait un second endroit où ce nombre pourrait
   diverger de celui que le moteur recalcule — exactement le bug que ce registre
   existe pour éliminer. Un chemin de :data:`CHAMPS_DERIVES` est refusé en 400.
2. **DÉRIVATION À CHAQUE LECTURE.** ``effectif`` n'est JAMAIS stocké : il est
   recalculé à chaque lecture depuis la valeur ``auto`` que le moteur dériverait
   AUJOURD'HUI et l'override ``manuel`` s'il existe.
3. **``regenerer`` SUPPRIME, il ne REMPLACE JAMAIS.** « Retour à l'automatique »
   ne s'exprime pas en réécrivant une valeur calculée : le chemin repasse en
   mode automatique, et reposer une valeur exige un NOUVEAU PATCH explicite.

INTERDIT EXPLICITEMENT : aucune clé indexée par la POSITION d'une ligne (ex.
``lignes[3].prix_manuel``) — une ligne supprimée ou réordonnée déplacerait
silencieusement l'override sur la MAUVAISE ligne. ``LigneDevis.quantite_manuelle``
et ``prix_manuel`` (QJR59) sont des CHAMPS DU MODÈLE, adressés par l'identifiant
STABLE de la ligne.

L'ÉTAT RÉEL DE CE MODULE (QJR227, 31/08/2026) — CE PARAGRAPHE DISAIT TROIS
CHOSES FAUSSES : « il ne persiste rien », « la colonne ``Devis.overrides``
n'existe pas encore », « aucun appelant n'est branché ». Les trois ont cessé
d'être vraies et c'est le premier texte que lit le prochain lecteur :

* la colonne ``Devis.overrides`` EXISTE (migration ``0107_qjr58_devis_overrides``) ;
* :func:`ecrire_colonne` la PERSISTE — par un ``UPDATE`` d'UNE SEULE colonne
  (patron ``offres_tailles._ecrire_colonne``), délibérément PAS par
  ``Devis.save`` : ni ``updated_at`` ni le gel ``prix_par_kwc`` ne doivent
  bouger pour une pose de surcharge ;
* les appelants SONT branchés — l'endpoint ``GET/PATCH/DELETE
  /ventes/devis/<pk>/overrides/`` (QJR58), les lecteurs
  :func:`effectif` de ``domain.scenario`` (scénario, option recommandée, kWc)
  et de ``quote_engine.builder``, et la règle de préséance R4-A
  (:func:`preseance_nb_panneaux`, appelée par
  ``domain.scenario.puissance_kwc_du_devis`` depuis QJR217).

CE QUI RESTE VRAI, ET QUI COMPTE : les fonctions de construction du registre
(:func:`poser`, :func:`regenerer`, :func:`fusionner`) sont PURES — elles rendent
le registre RÉSULTANT sans rien écrire. Seule :func:`ecrire_colonne` touche la
base, et elle ne touche QUE cette colonne.
"""
#: Les ORIGINES admises d'un override — jamais une quatrième inventée sans que
#: le contrat PACT10 ne soit d'abord mis à jour.
ORIGINE_MANUEL = 'manuel'
ORIGINE_IMPORT = 'import'
ORIGINE_API = 'api'
ORIGINES = (ORIGINE_MANUEL, ORIGINE_IMPORT, ORIGINE_API)

#: Le préfixe du SEUL chemin à motif dynamique : ``profil.equipements.<clef>``
#: où ``<clef>`` est le nom d'un équipement RÉEL (piscine, climatisation,
#: chauffe_eau, vehicule_electrique…), jamais un index de position.
PREFIXE_EQUIPEMENT = 'profil.equipements.'

#: LISTE BLANCHE — décision fondateur D12 du 29/08/2026, recopiée À L'IDENTIQUE
#: du contrat ``contract_samples/devis_overrides.json`` (aucun chemin ajouté ni
#: retiré ; un test l'épingle contre le fichier). Tout PATCH sur un chemin
#: absent est refusé en 400 : la surface est FERMÉE, il n'existe aucun
#: ``**kwargs`` silencieux.
CHAMPS_OVERRIDABLES = (
    'taille.nb_panneaux',
    'taille.panel_watt',
    'taille.kwc',
    'taille.batterie_nb_modules',
    'taille.batterie_module_kwh',
    'scenario',
    'recommended_option',
    'profil.occupation',
    'profil.factures_mensuelles_reelles',
    'profil.conso_annuelle',
    PREFIXE_EQUIPEMENT + '<clef>',
    'tarif.distributeur',
    'tarif.tranches',
    'tarif.charges_fixes_mad',
    'etude.jour_reference',
    'mode_installation',
    'structure',
    'tension',
    'pompe_alim',
)

#: Les champs que le MOTEUR calcule. Les poser ici serait poser un nombre que
#: personne ne pourrait plus rapprocher de son calcul — refus BRUYANT (400),
#: jamais un silence (même raisonnement mot pour mot que
#: ``OffreTailleConfigSerializer``).
CHAMPS_DERIVES = (
    'production_annuelle',
    'economies_annuelles',
    'payback_annees',
    'puissance_kwc',
    'prix_ttc',
    'prix_par_kwc',
    'couverture_pct',
    'taux_autoconso_pct',
    'taux_autoconsommation',
    'economies_cumulees_25_ans_mad',
    'prix_kwc',
    'total_ht',
    'total_ttc',
)

_MSG_DERIVE = (
    'Champ calculé par le moteur : il ne peut pas être surchargé. Modifiez '
    'les ENTRÉES (taille, profil, tarif) et le moteur le recalculera.'
)
MSG_CHEMIN_INCONNU = (
    "Chemin inconnu du registre de surcharges : la liste blanche (décision "
    "fondateur D12) est la seule porte."
)
_MSG_INCONNU = MSG_CHEMIN_INCONNU
_MSG_POSITION = (
    "Interdit : une clé indexée par la POSITION d'une ligne déplacerait "
    "silencieusement la surcharge sur une autre ligne. Les surcharges de "
    "ligne sont des CHAMPS du modèle (quantite_manuelle / prix_manuel), "
    "adressés par l'identifiant stable de la ligne."
)


#: R4-A — LA TABLE DE PRÉSÉANCE entre les DEUX niveaux de surcharge de
#: quantité de panneaux. Message d'AVERTISSEMENT, jamais un refus : les deux
#: surcharges sont légitimes séparément, seule leur COEXISTENCE divergente
#: mérite d'être dite au vendeur — et elle doit l'être en NOMMANT la ligne.
MSG_CONFLIT_QUANTITE = (
    'Quantité de panneaux déclarée deux fois sur « %s » : la ligne est '
    'verrouillée à %s (saisie du vendeur, elle fait foi pour cette ligne) '
    'tandis que la surcharge de devis « taille.nb_panneaux » vaut %s (elle '
    'alimente le dimensionnement). Alignez les deux si le document doit '
    'annoncer un seul nombre de panneaux.'
)

#: Les trois provenances possibles de la quantité RETENUE pour la ligne
#: panneau dominante — jamais une quatrième inventée.
SOURCE_LIGNE_MANUELLE = 'ligne_manuelle'
SOURCE_DEVIS = 'devis'
SOURCE_AUTO = 'auto'


class PreseanceQuantite:
    """Le verdict de :func:`preseance_nb_panneaux` — R4-A, tranché le 29/08.

    * ``quantite_ligne`` — la quantité qui vaut pour CETTE ligne ;
    * ``source_ligne`` — laquelle des trois l'a décidée ;
    * ``cible_dimensionnement`` — le ``taille.nb_panneaux`` de NIVEAU DEVIS
      qui alimente ``pipeline.decider_taille`` (``None`` s'il n'est pas
      surchargé). Il RESTE renseigné même quand la ligne gagne : les deux
      chemins ne servent pas la même chose, et écraser l'un par l'autre est
      exactement ce que cette table existe pour empêcher ;
    * ``conflit`` / ``avertissement`` — vrai et NOMMÉ quand les deux niveaux
      annoncent des nombres différents.
    """

    __slots__ = ('quantite_ligne', 'source_ligne', 'cible_dimensionnement',
                 'conflit', 'avertissement')

    def __init__(self, quantite_ligne, source_ligne, cible_dimensionnement,
                 conflit, avertissement):
        self.quantite_ligne = quantite_ligne
        self.source_ligne = source_ligne
        self.cible_dimensionnement = cible_dimensionnement
        self.conflit = conflit
        self.avertissement = avertissement

    def __repr__(self):  # pragma: no cover — confort de débogage
        return ('<PreseanceQuantite %s par %s (cible %s, conflit=%s)>'
                % (self.quantite_ligne, self.source_ligne,
                   self.cible_dimensionnement, self.conflit))


def _entier_ou_none(valeur):
    """La valeur en entier, ou ``None`` si elle n'en est pas un.

    Un override illisible (texte, ``None``, objet) ne DÉCIDE rien : il est
    ignoré comme une absence, jamais converti en un nombre inventé.
    """
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def preseance_nb_panneaux(devis, ligne_dominante, *, avertissements=None):
    """R4-A — QUI GAGNE entre ``taille.nb_panneaux`` et ``quantite_manuelle`` ?

    LE PROBLÈME. Le registre D12 porte ``taille.nb_panneaux`` au niveau du
    DEVIS ; ``LigneDevis.quantite_manuelle`` (QJR59) marque, au niveau de LA
    LIGNE, une quantité TAPÉE par le vendeur. Rien ne disait lequel gagne — et
    tant que rien ne le dit, chaque appelant tranche à sa façon : c'est
    littéralement le patron « quatre mécanismes de surcharge incompatibles »
    que le registre existe pour fermer.

    LA RÈGLE (R4-A, tranchée le 29/08/2026), en trois phrases :

    1. **Le drapeau de LIGNE gagne pour la quantité de CETTE ligne.** Le
       vendeur a tapé ce nombre sur cette ligne-là ; aucun recalcul ne
       l'écrase (même geste que ``resynchronisation._quantite_verrouillee``).
    2. **Le chemin de NIVEAU DEVIS alimente ``decider_taille``.** Il ne
       disparaît pas parce qu'une ligne est verrouillée : il décrit la CIBLE
       du dimensionnement, pas la quantité d'une ligne.
    3. **Un désaccord entre les deux émet un AVERTISSEMENT FR qui NOMME la
       ligne** — jamais un silence, jamais un refus : le vendeur doit
       apprendre l'écart AVANT que le client ne le lise sur le PDF.

    ``ligne_dominante`` est la ligne PANNEAU dominante du devis (``None`` s'il
    n'y en a pas). ``avertissements``, quand une liste est fournie, reçoit le
    message — même convention que ``resynchronisation._avertir_verrouillee``.

    QJR217 (31/08/2026) — CETTE RÈGLE A ENFIN UN APPELANT DE PRODUCTION.
    Elle était écrite, testée dans les deux sens, et JAMAIS appelée hors des
    tests : l'avertissement promis n'atteignait aucun vendeur. Elle est
    désormais appliquée par ``domain.scenario.puissance_kwc_du_devis`` (le
    lecteur du kWc du devis, là où le niveau LIGNE et le niveau DEVIS se
    rencontrent), et son avertissement remonte par la liste
    ``avertissements`` de ``domain.resynchronisation.reconcilier`` jusqu'à la
    réponse ``sync-layout`` que l'écran affiche déjà.

    LECTURE PURE : rien n'est écrit, ni sur le devis, ni sur la ligne.
    """
    nb_devis_brut, source_devis = effectif(devis, 'taille.nb_panneaux', None)
    cible = (_entier_ou_none(nb_devis_brut)
             if source_devis != 'auto' else None)

    verrou = bool(getattr(ligne_dominante, 'quantite_manuelle', False))
    qte_ligne = _entier_ou_none(getattr(ligne_dominante, 'quantite', None))

    if verrou:
        quantite, source = qte_ligne, SOURCE_LIGNE_MANUELLE
    elif cible is not None:
        quantite, source = cible, SOURCE_DEVIS
    else:
        quantite, source = qte_ligne, SOURCE_AUTO

    conflit = bool(verrou and cible is not None and qte_ligne is not None
                   and qte_ligne != cible)
    message = None
    if conflit:
        message = MSG_CONFLIT_QUANTITE % (
            (getattr(ligne_dominante, 'designation', '') or '?'),
            qte_ligne, cible)
        if avertissements is not None:
            avertissements.append(message)
    return PreseanceQuantite(quantite, source, cible, conflit, message)


def chemin_autorise(chemin):
    """Le chemin est-il dans la liste blanche D12 ?

    ``profil.equipements.<clef>`` est le SEUL motif dynamique : toute clef
    d'équipement NON VIDE et sans point y est admise (un nom d'équipement réel),
    jamais un index de position.
    """
    if not isinstance(chemin, str) or not chemin:
        return False
    if chemin.startswith(PREFIXE_EQUIPEMENT):
        clef = chemin[len(PREFIXE_EQUIPEMENT):]
        return bool(clef) and '.' not in clef and not clef.isdigit()
    return chemin in CHAMPS_OVERRIDABLES


def registre_du_devis(devis):
    """Le registre RANGÉ sur ce devis, toujours un dict (jamais ``None``).

    Lu par ``getattr`` : la colonne ``Devis.overrides`` n'existe qu'à partir de
    QJR58, ce module fonctionne donc AVANT elle comme APRÈS. Rendu par COPIE :
    un appelant qui le modifie ne touche jamais l'instance.
    """
    brut = getattr(devis, 'overrides', None)
    return dict(brut) if isinstance(brut, dict) else {}


#: Alias interne historique — ce module l'utilise sous ce nom court.
_registre = registre_du_devis


def effectif(devis, chemin, auto):
    """``(valeur, source)`` — LA valeur qui vaut aujourd'hui pour ce chemin.

    ``auto`` est ce que le moteur dériverait MAINTENANT (l'appelant le lui
    fournit : ce module ne calcule rien). Un override posé prime, et ``source``
    NOMME sa provenance (``manuel`` / ``import`` / ``api``) ; sinon la valeur
    automatique, ``source='auto'``.

    RIEN N'EST STOCKÉ ICI : un devis dont le catalogue a changé depuis la pose
    de l'override voit son ``auto`` bouger sans que ``manuel`` ne change, et un
    chemin RESTÉ automatique reflète toujours l'état actuel — jamais une valeur
    figée au moment d'une lecture passée.
    """
    entree = _registre(devis).get(chemin)
    if not isinstance(entree, dict) or 'valeur' not in entree:
        return auto, 'auto'
    origine = entree.get('origine')
    return entree['valeur'], (origine if origine in ORIGINES
                              else ORIGINE_MANUEL)


def vue_effective(devis, autos):
    """Le bloc ``effectif`` du contrat : ``{chemin: {auto, manuel, effectif,
    source}}`` pour les chemins dont l'appelant a fourni la valeur ``auto``.

    ``autos`` est une carte ``{chemin: valeur_auto}``. Les chemins surchargés
    mais absents d'``autos`` sont rendus quand même, avec ``auto=None`` : un
    override posé ne disparaît jamais d'une lecture.
    """
    registre = _registre(devis)
    chemins = list(autos or {})
    for chemin in registre:
        if chemin not in chemins:
            chemins.append(chemin)
    bloc = {}
    for chemin in chemins:
        auto = (autos or {}).get(chemin)
        valeur, source = effectif(devis, chemin, auto)
        entree = registre.get(chemin)
        manuel = (entree.get('valeur')
                  if isinstance(entree, dict) and 'valeur' in entree else None)
        bloc[chemin] = {'auto': auto, 'manuel': manuel,
                        'effectif': valeur, 'source': source}
    return bloc


#: QJR216 — LES CHEMINS DONT LE MOTEUR SAIT DÉRIVER UNE VALEUR, et EUX SEULS.
#: Chaque entrée est documentée par sa dérivation dans :func:`autos_du_devis`.
#: Les autres chemins de la liste blanche D12 (profil, tarif, structure…)
#: n'ont AUCUN dérivateur serveur à ce jour : ils sont OMIS de la carte plutôt
#: que remplis d'un zéro ou d'un défaut — règle Z2, « mieux vaut taire ».
CHEMINS_AVEC_AUTO = (
    'taille.nb_panneaux',
    'taille.panel_watt',
    'taille.kwc',
    'mode_installation',
)


def autos_du_devis(devis):
    """QJR216 — LA CARTE ``{chemin: valeur AUTO}`` QUE LE MOTEUR REND AUJOURD'HUI.

    CE QUI ÉTAIT FAUX. ``views/devis._overrides_reponse`` construisait toujours
    ``vue_effective(devis, {})`` — une carte ``autos`` VIDE — donc **toute**
    réponse de l'endpoint annonçait ``auto: null``, y compris sur les chemins
    dont le moteur a une valeur parfaitement lisible. Le bloc ``effectif``
    promettait « valeur posée vs valeur moteur, côte à côte » et n'a jamais
    porté la seconde.

    LA DÉRIVATION EST CELLE DU MOTEUR, PAS UNE SECONDE. Le nombre de panneaux
    et le wattage viennent de ``quote_engine.builder.panneaux_et_watt_lu`` — LE
    lecteur unique des lignes (PVUNI, celui qu'utilise déjà
    ``scenario.puissance_kwc_du_devis``) — et le kWc en est le produit, comme
    dans sa branche AUTO. Aucun repli catalogue, aucun wattage supposé : un
    devis dont les lignes ne portent pas de panneau lisible n'a simplement pas
    ces clés.

    LECTURE PURE, ET JAMAIS LE REGISTRE. Ce sont les valeurs AUTOMATIQUES :
    elles ignorent délibérément les surcharges posées, sinon ``auto`` et
    ``manuel`` diraient la même chose et le vendeur ne verrait plus l'écart.

    Ne lève JAMAIS : un devis illisible rend une carte partielle (ou vide), et
    le bloc ``effectif`` retombe alors sur ``auto: null`` — l'état d'avant.
    """
    autos = {}
    nb, watt = 0, None
    try:
        from apps.ventes.quote_engine.builder import panneaux_et_watt_lu

        lignes = [
            li for li in devis.lignes.select_related(
                'produit', 'produit__fiche_technique').all()
            if getattr(li, 'type_ligne', 'produit') == 'produit'
            and not getattr(li, 'optionnelle', False)]
        nb, watt = panneaux_et_watt_lu(lignes)
    except Exception:  # noqa: BLE001 — une lecture ratée n'invente rien
        nb, watt = 0, None
    if nb:
        autos['taille.nb_panneaux'] = nb
    if watt:
        autos['taille.panel_watt'] = watt
    if nb and watt:
        autos['taille.kwc'] = round(nb * watt / 1000, 2)
    mode = getattr(devis, 'mode_installation', None)
    if mode:
        autos['mode_installation'] = mode
    return autos


def poser(devis, chemin, valeur, *, utilisateur=None,
          origine=ORIGINE_MANUEL, horodatage=None):
    """Le registre RÉSULTANT après la pose d'UN chemin — les autres INTOUCHÉS.

    FONCTION PURE (QJR57) : elle ne persiste rien. QJR58 écrira le dict rendu
    par un UPDATE d'UNE SEULE colonne, à la manière d'``offres_tailles.
    _ecrire_colonne`` — sans faire avancer ``updated_at`` ni déclencher le gel
    ``prix_par_kwc``, deux effets de bord de ``Devis.save`` qui sont FAUX pour
    une pose d'override.

    ``ValueError`` (traduit en 400 par le sérialiseur) sur un chemin hors
    liste blanche ou sur un champ dérivé — jamais un silence.
    """
    if chemin in CHAMPS_DERIVES:
        raise ValueError('%s : %s' % (chemin, _MSG_DERIVE))
    if not chemin_autorise(chemin):
        raise ValueError('%s : %s' % (chemin, _MSG_INCONNU))
    if origine not in ORIGINES:
        raise ValueError(
            "origine « %s » inconnue : %s." % (origine, ', '.join(ORIGINES)))
    if horodatage is None:
        from django.utils import timezone
        horodatage = timezone.now()
    registre = _registre(devis)
    registre[chemin] = {
        'valeur': valeur,
        'pose_le': horodatage.isoformat(),
        'pose_par': _identite(utilisateur),
        'origine': origine,
    }
    return registre


def regenerer(devis, chemin):
    """Le registre RÉSULTANT après SUPPRESSION de l'override d'un chemin.

    C'est la SEULE forme dans laquelle « retour à l'automatique » s'exprime
    sans inventer de valeur (même geste que ``offres_tailles.regenerer_taille``)
    : le chemin repasse en mode automatique et ``effectif`` redevient ``auto``.
    On ne REMPLACE jamais l'override par une valeur calculée écrite en dur —
    reposer une valeur exige un NOUVEAU PATCH explicite du vendeur.

    Supprimer un chemin non posé est un NO-OP (idempotent), jamais une erreur.

    QJR216 — « SUPPRIMER » N'EST PAS « FAIRE DISPARAÎTRE DE LA RÉPONSE ».
    Le registre perd bien le chemin (c'est tout l'objet de cette fonction),
    mais l'endpoint doit RENDRE le chemin régénéré avec la valeur que le moteur
    calcule — sinon « retour à l'automatique » se solde par un trou dans la
    réponse au lieu de la valeur promise. C'est la vue (``vue_effective``)
    qui le porte, alimentée par :func:`autos_du_devis`.
    """
    registre = _registre(devis)
    registre.pop(chemin, None)
    return registre


def fusionner(devis, patch, *, utilisateur=None, origine=ORIGINE_MANUEL,
              horodatage=None):
    """Le registre RÉSULTANT après un PATCH — FUSION, jamais un remplacement.

    Envoyer ``{'taille.nb_panneaux': {'valeur': 14}}`` ne touche AUCUN autre
    chemin déjà posé. Les chemins sont posés dans l'ordre du dict reçu ; le
    premier chemin refusé lève, et RIEN n'est rendu à moitié (l'appelant
    n'écrit que le dict final).
    """
    registre = _registre(devis)
    for chemin, entree in (patch or {}).items():
        valeur = entree.get('valeur') if isinstance(entree, dict) else entree
        registre = poser(
            _DevisAvecRegistre(devis, registre), chemin, valeur,
            utilisateur=utilisateur,
            origine=(entree.get('origine', origine)
                     if isinstance(entree, dict) else origine),
            horodatage=horodatage)
    return registre


class _DevisAvecRegistre:
    """Porteur MINIMAL d'un registre intermédiaire pour :func:`fusionner`.

    Poser N chemins d'affilée doit partir du registre DÉJÀ enrichi par les
    précédents ; ce mince objet évite de rendre ``poser`` impur pour autant.
    """

    __slots__ = ('_devis', 'overrides')

    def __init__(self, devis, registre):
        self._devis = devis
        self.overrides = registre


def _identite(utilisateur):
    """L'identité tracée dans ``pose_par`` — l'e-mail, sinon le nom d'utilisateur.

    ``None`` quand aucun utilisateur n'est connu (pose programmatique) : on
    n'invente pas un auteur.
    """
    if utilisateur is None:
        return None
    return (getattr(utilisateur, 'email', None)
            or getattr(utilisateur, 'username', None) or None)


def ecrire_colonne(devis, registre):
    """QJR58 — écrit ``Devis.overrides`` — CETTE COLONNE, ET RIEN D'AUTRE.

    POURQUOI PAS ``devis.save(update_fields=['overrides'])`` — copie mot pour
    mot du raisonnement d'``offres_tailles._ecrire_colonne``, parce que les
    DEUX effets de bord de ``Devis.save`` sont FAUX pour une pose d'override :

    * SCA47 — ``save`` DÉRIVE ET GÈLE ``prix_par_kwc`` (write-once) dès qu'un
      kWc et un total existent. Poser une surcharge d'ENTRÉE aurait donc pu
      figer au passage un prix par kWc que ce geste ne concerne pas — et
      write-once veut dire : pour toujours.
    * VX98 — ``updated_at`` (``auto_now``) aurait avancé, et la page aurait
      annoncé « modifié il y a N minutes » sur un devis dont AUCUNE ligne,
      AUCUN total et AUCUN statut n'a bougé.

    L'instance en mémoire est resynchronisée pour que l'appelant relise ce
    qu'il vient d'écrire.
    """
    type(devis).objects.filter(pk=devis.pk).update(overrides=registre)
    devis.overrides = registre
    return registre


def erreurs_de_chemins(data):
    """Les refus d'un corps de PATCH, ``{chemin: message FR}`` — ``{}`` si OK.

    Sortie ici (et pas dans le sérialiseur) pour que la RÈGLE vive avec la
    liste blanche qu'elle applique : le sérialiseur ne fait que la traduire en
    400. Trois refus, tous BRUYANTS : la clé indexée par POSITION, le champ
    DÉRIVÉ, le chemin INCONNU.
    """
    erreurs = {}
    for chemin in data or {}:
        if not isinstance(chemin, str):
            erreurs[str(chemin)] = _MSG_INCONNU
        elif '[' in chemin or ']' in chemin:
            erreurs[chemin] = _MSG_POSITION
        elif chemin in CHAMPS_DERIVES:
            erreurs[chemin] = _MSG_DERIVE
        elif not chemin_autorise(chemin):
            erreurs[chemin] = _MSG_INCONNU
    return erreurs


def normaliser_patch(data):
    """Un corps ``{chemin: valeur}`` ou ``{chemin: {valeur, origine?}}`` rendu
    sous la forme UNIQUE ``{chemin: {valeur, origine}}``.

    Lève ``ValueError`` sur une origine inconnue — jamais une quatrième valeur
    inventée sans que le contrat ne soit d'abord mis à jour.
    """
    propre = {}
    for chemin, entree in (data or {}).items():
        if isinstance(entree, dict) and 'valeur' in entree:
            origine = entree.get('origine', ORIGINE_MANUEL)
            valeur = entree['valeur']
        else:
            origine, valeur = ORIGINE_MANUEL, entree
        if origine not in ORIGINES:
            raise ValueError(
                "%s : origine « %s » inconnue (%s)."
                % (chemin, origine, ', '.join(ORIGINES)))
        propre[chemin] = {'valeur': valeur, 'origine': origine}
    return propre
