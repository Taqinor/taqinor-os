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

CE QUE QJR57 NE FAIT PAS. Il ne PERSISTE rien : la colonne ``Devis.overrides``
n'existe pas encore (migration QJR58), et aucun appelant n'est branché. Les
fonctions d'écriture sont donc PURES — elles rendent le registre RÉSULTANT, que
l'endpoint de QJR58 écrira par un UPDATE d'UNE SEULE colonne (patron
``offres_tailles._ecrire_colonne``).
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
_MSG_INCONNU = (
    "Chemin inconnu du registre de surcharges : la liste blanche (décision "
    "fondateur D12) est la seule porte."
)
_MSG_POSITION = (
    "Interdit : une clé indexée par la POSITION d'une ligne déplacerait "
    "silencieusement la surcharge sur une autre ligne. Les surcharges de "
    "ligne sont des CHAMPS du modèle (quantite_manuelle / prix_manuel), "
    "adressés par l'identifiant stable de la ligne."
)


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


def _registre(devis):
    """Le registre RANGÉ sur ce devis, toujours un dict (jamais ``None``).

    Lu par ``getattr`` : la colonne ``Devis.overrides`` n'existe qu'à partir de
    QJR58, ce module fonctionne donc AVANT elle comme APRÈS.
    """
    brut = getattr(devis, 'overrides', None)
    return dict(brut) if isinstance(brut, dict) else {}


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
