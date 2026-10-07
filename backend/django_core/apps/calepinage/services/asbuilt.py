"""CAL212 — l'AS-BUILT : le posé réel comparé à la variante retenue.

LA RÈGLE, ET ELLE EST TOUTE LA TÂCHE
-------------------------------------
L'écart affiché est la DIFFÉRENCE DE DEUX SAISIES RÉELLES :

* le PRÉVU vient de la variante RETENUE du calepinage (CAL9/CAL209) — le
  document que le chantier a reçu, pas un dimensionnement souhaité ;
* le POSÉ vient de ``PoseReelle``, saisi sur le chantier.

Un pan SANS saisie de pose n'affiche AUCUN écart. Pas un zéro : un zéro dirait
« conforme » alors que personne n'a compté. C'est le même refus que partout
dans ce module — on préfère le trou visible au chiffre rassurant.

LE CHANTIER RESTE LE CHANTIER
------------------------------
Le module ``installations`` ne porte aucun champ calepinage (règle fondateur
12/09/2026 : « le module chantier ne garde QUE son cœur ») : il se branche sur
``apps.calepinage.selectors.calepinage_retenu_pour_devis`` par son propre
sélecteur ``calepinage_retenu_du_chantier`` (CAL209). Ce module ne fait donc
JAMAIS le chemin inverse en important ``apps.installations`` — il travaille
sur le calepinage qu'on lui donne.

La comparaison elle-même (``comparer``) ne connaît que des dictionnaires :
elle se teste sans base.

CALX366 — LA PORTE. Jusqu'ici ``pans_prevus`` et ``ecarts_du_calepinage``
n'avaient AUCUN appelant hors de leurs tests. ``etat_pose_reelle`` /
``enregistrer_pose`` / ``version_depuis_ecarts`` (en fin de fichier) sont
servies par ``views/asbuilt.py`` (``GET/POST calepinages/<pk>/pose-reelle/``)
— le chantier répond enfin à la conception.
"""
from __future__ import annotations

#: ACAL107 — GARDÉE pour relire les relevés/blocs déjà stockés avec cette
#: source ; plus jamais produite (la variante retenue EST la conception).
SOURCE_VARIANTE = 'variante retenue'
SOURCE_CALEPINAGE = 'document du calepinage'
#: ACAL107 (D-ACAL-23) — l'instantané figé de la version ACCEPTÉE du devis.
SOURCE_DEVIS_ACCEPTE = 'devis accepté'

MENTION_SANS_SAISIE = (
    "Aucun relevé de pose n'a été saisi pour ce pan : l'écart n'est pas "
    "affiché (il serait supposé, pas mesuré)."
)
MENTION_SANS_PREVU = (
    "Ce pan n'existe pas dans la conception prévue : il n'y a rien à quoi "
    "comparer le posé."
)
#: ACAL267 — un relevé dont le pan n'existe plus (supprimé du document) :
#: GARDÉ, hors totaux, retirable (DELETE pose-reelle/<zone_id>/).
MENTION_ORPHELIN = (
    "Ce pan n'existe plus dans la conception : la ligne est conservée, hors "
    "totaux."
)
#: ACAL267 — le refus d'un DELETE sur un pan sans relevé (contrat
#: ``delete_pose_reelle.refus_404``).
MESSAGE_AUCUNE_POSE = "Aucune pose réelle n'est saisie pour ce pan."
#: ACAL248 — le prévu FIGÉ au relevé diffère de la conception d'aujourd'hui.
MENTION_CONCEPTION_MODIFIEE = 'conception modifiée depuis le relevé'

#: ACAL248 — ``PoseReelle.prevu_source`` (20 caractères) : d'où vient le prévu
#: figé à la saisie du relevé.
PREVU_SOURCE_COURT = {SOURCE_DEVIS_ACCEPTE: 'devis_accepte'}
PREVU_SOURCE_DEFAUT = 'calepinage'

__all__ = [
    'SOURCE_VARIANTE', 'SOURCE_CALEPINAGE', 'SOURCE_DEVIS_ACCEPTE',
    'MENTION_SANS_SAISIE', 'MENTION_CONCEPTION_MODIFIEE',
    'comparer', 'conception_du_chantier', 'pans_prevus',
    'ecarts_du_calepinage',
    # CALX366 — la porte HTTP ``pose-reelle/``.
    'PREFIXE_VERSION_POSE', 'PoseRefusee', 'etat_pose_reelle',
    'enregistrer_pose', 'version_depuis_ecarts',
    # ACAL267 — retirer le relevé d'un pan (ligne orpheline comprise).
    'MENTION_ORPHELIN', 'MESSAGE_AUCUNE_POSE', 'supprimer_pose',
]


def comparer(prevus, saisies):
    """``[{pan, prevu, pose, ecart, ecarts_position, releve_le, mention,
    prevu_fige, prevu_actuel, conception_modifiee}]``.

    Args:
        prevus: ``[{pan, modules}]`` — les pans de la conception COURANTE.
        saisies: ``[{pan, modules_poses, ecarts_position, releve_le,
            modules_prevus?}]`` — ``modules_prevus`` = le prévu FIGÉ au
            relevé (ACAL248), ``None`` pour un relevé ancien (prévu vivant).

    ACAL248 — l'écart d'un pan relevé se lit contre le prévu DU JOUR DU
    RELEVÉ : retoucher le toit après coup ne réécrit plus l'écart passé ;
    ``prevu_actuel`` et ``conception_modifiee`` disent que la conception a
    changé depuis.

    Un pan prévu SANS saisie sort avec ``pose = None`` et ``ecart = None`` ;
    un pan SAISI qui n'existe pas au prévu sort avec ``prevu = None`` — les
    deux cas sont VISIBLES, aucun n'est silencieusement écarté.
    """
    # ACAL267 — la clé d'une ligne est l'identifiant STABLE du pan
    # (``zone_id``), à défaut son ancien libellé : deux pans de même libellé
    # sont deux lignes, et un pan renommé garde son relevé.
    # Une saisie SANS ``zone_id`` (forme historique : le libellé seul) se
    # rattache au pan prévu de même libellé, s'il est UNIQUE.
    par_libelle = {}
    for prevu in prevus or []:
        libelle = str((prevu or {}).get('libelle') or prevu.get('pan') or '')
        par_libelle.setdefault(libelle, []).append(_cle_de_ligne(prevu))
    par_pan = {}
    for saisie in saisies or []:
        cle = _cle_de_ligne(saisie)
        if not (saisie or {}).get('zone_id'):
            memes = par_libelle.get(cle) or []
            cle = memes[0] if len(memes) == 1 else cle
        if cle:
            par_pan[cle] = saisie

    lignes, vus = [], set()
    for prevu in prevus or []:
        cle = _cle_de_ligne(prevu)
        vus.add(cle)
        libelle = str((prevu or {}).get('libelle') or prevu.get('pan')
                      or cle)
        lignes.append(_ligne(cle, prevu.get('modules'), par_pan.get(cle),
                             libelle=libelle))
    for cle, saisie in par_pan.items():
        if cle not in vus:
            # Un relevé dont le pan n'existe plus : ORPHELIN, hors totaux.
            lignes.append(_ligne(
                cle, None, saisie, orphelin=True,
                libelle=str(saisie.get('libelle') or saisie.get('pan')
                            or cle)))
    return lignes


def _cle_de_ligne(element):
    """La clé d'un prévu / d'une saisie : ``zone_id``, sinon ``pan``."""
    element = element or {}
    return str(element.get('zone_id') or element.get('pan') or '').strip()


def _entier(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return int(valeur)
    return None


def _ligne(pan, modules_prevus, saisie, *, libelle=None, orphelin=False):
    actuel = _entier(modules_prevus)
    fige = _entier((saisie or {}).get('modules_prevus'))
    prevu_fige = fige is not None
    # Un pan qui n'existe plus au prévu (ORPHELIN) garde son prévu figé pour
    # mémoire, mais aucun écart n'est calculé contre une conception où il
    # n'est plus.
    prevu = fige if (prevu_fige and (actuel is not None or orphelin)) \
        else actuel
    pose = _entier((saisie or {}).get('modules_poses'))
    if orphelin:
        mention = MENTION_ORPHELIN
    elif pose is None:
        mention = MENTION_SANS_SAISIE
    elif prevu is None:
        mention = MENTION_SANS_PREVU
    else:
        mention = ''
    libelle = libelle or pan
    return {
        # ACAL267 — ``pan`` est le libellé AFFICHÉ du pan vivant ; pour un
        # orphelin, son identifiant (le libellé figé reste dans ``libelle``).
        'pan': pan if orphelin else libelle,
        'zone_id': pan,
        'libelle': libelle,
        'orphelin': bool(orphelin),
        'prevu': prevu,
        'pose': pose,
        # L'écart n'existe QUE quand les deux nombres sont des saisies
        # réelles — jamais une différence avec un zéro supposé.
        'ecart': (pose - prevu if pose is not None and prevu is not None
                  and not orphelin else None),
        'ecarts_position': ((saisie or {}).get('ecarts_position') or ''),
        'releve_le': (saisie or {}).get('releve_le'),
        'releve_par': (saisie or {}).get('releve_par'),
        'mention': mention,
        'prevu_fige': prevu_fige,
        'prevu_actuel': actuel,
        'conception_modifiee': bool(prevu_fige and actuel is not None
                                    and actuel != fige),
    }


def conception_du_chantier(calepinage):
    """ACAL107 (D-ACAL-2, D-ACAL-23) — LA conception que le chantier reçoit.

    Renvoie ``(roof_layout, source)`` :

    * le ``Devis.roof_layout`` FIGÉ de la DERNIÈRE version ACCEPTÉE de la
      chaîne de révision du devis lié (V1 tant que la V2 n'est pas acceptée,
      V2 dès son acceptation) — ``source`` = :data:`SOURCE_DEVIS_ACCEPTE` ;
    * sinon ``Calepinage.roof_layout``, la conception COURANTE (retenir une
      variante l'y a écrite) — ``source`` = :data:`SOURCE_CALEPINAGE`.

    La variante retenue n'est plus lue en parallèle : elle EST la conception
    courante. Lecture pure ; la chaîne de révision est lue par
    ``apps.ventes.selectors`` (frontière inter-apps).
    """
    devis_id = getattr(calepinage, 'devis_id', None)
    company = getattr(calepinage, 'company', None)
    if devis_id and company is not None:
        from apps.ventes.selectors import instantane_accepte_en_vigueur

        instantane = instantane_accepte_en_vigueur(devis_id, company)
        if instantane is not None and isinstance(
                instantane.get('roof_layout'), dict):
            return instantane['roof_layout'], SOURCE_DEVIS_ACCEPTE
    return getattr(calepinage, 'roof_layout', None), SOURCE_CALEPINAGE


def pans_prevus(calepinage, *, conception=None):
    """Les pans PRÉVUS : ceux de :func:`conception_du_chantier`.

    Renvoie ``(pans, source)`` — la source est PUBLIÉE pour qu'un écart lu
    sur la conception courante ne se lise jamais comme un écart avec
    l'instantané accepté (contractuel). ``conception`` (``(document,
    source)``, ACAL248) évite de relire la conception quand l'appelant la
    tient déjà — le document as-built rend ainsi tableau ET planche depuis
    la MÊME conception.
    """
    # ACAL259 — LA lecture du module (``mesures_du_document``) : le même
    # compte par pan que la présentation, le journal et les exports.
    from .mesures import mesures_du_document

    from .production import cles_des_pans

    document, source = (conception if conception is not None
                        else conception_du_chantier(calepinage))
    # ACAL267 — chaque pan porte son identifiant STABLE (``zone_id``) à côté
    # de son libellé (``pan``) : la pose réelle s'y rattache.
    pans = [dict(pan, zone_id=cle, libelle=pan['pan'])
            for pan, cle in zip(mesures_du_document(document)['pans'],
                                cles_des_pans(document))]
    return pans, source


def ecarts_du_calepinage(calepinage, *, conception=None):
    """L'as-built COMPLET d'un calepinage : prévu, posé, écart, totaux.

    Lecture PURE, bornée société par l'appelant. ``ecart_total`` n'existe que
    si AU MOINS un pan a été relevé — sinon il vaudrait « 0 » sur un chantier
    dont personne n'a compté un seul module.
    """
    from ..models import PoseReelle

    prevus, source = pans_prevus(calepinage, conception=conception)
    saisies = [
        {'pan': pose.pan, 'zone_id': pose.zone_id or pose.pan,
         'libelle': pose.pan, 'modules_poses': pose.modules_poses,
         'ecarts_position': pose.ecarts_position, 'releve_le': pose.releve_le,
         'releve_par': _auteur_publie(pose.releve_par),
         # ACAL248 — le prévu FIGÉ au relevé (``None`` : relevé ancien).
         'modules_prevus': pose.modules_prevus}
        for pose in PoseReelle.objects.filter(calepinage=calepinage)
        .select_related('releve_par')
    ]
    lignes = comparer([{'pan': pan['pan'], 'zone_id': pan['zone_id'],
                        'libelle': pan['libelle'], 'modules': pan['modules']}
                       for pan in prevus], saisies)
    return _agreger(calepinage.pk, source, lignes)


def _auteur_publie(user):
    """``{id, nom_complet}`` de l'auteur du releve, ou ``None``."""
    if user is None:
        return None
    nom = (user.get_full_name() or '').strip() or str(user.get_username())
    return {'id': user.pk, 'nom_complet': nom}


def _agreger(calepinage_id, source, lignes):
    """Les totaux des lignes de ``comparer`` — PUR (aucune base).

    CALX366 — extrait tel quel de ``ecarts_du_calepinage`` pour que la forme
    du contrat se rejoue sans base : même ``total_pose`` à ``None`` tant que
    rien n'est relevé, même ``ecart_total`` à ``None`` sans pan comparable.
    """
    # ACAL267 — une ligne ORPHELINE (pan supprimé) reste visible mais HORS
    # totaux : son relevé ne se compare plus à rien.
    vivantes = [ligne for ligne in lignes if not ligne.get('orphelin')]
    releves = [ligne for ligne in vivantes if ligne['pose'] is not None]
    comparables = [ligne for ligne in vivantes if ligne['ecart'] is not None]
    return {
        'calepinage': calepinage_id,
        'source_prevu': source,
        'pans': lignes,
        'pans_releves': len(releves),
        'total_prevu': sum(ligne['prevu'] for ligne in vivantes
                           if ligne['prevu'] is not None),
        'total_pose': (sum(ligne['pose'] for ligne in releves)
                       if releves else None),
        'ecart_total': (sum(ligne['ecart'] for ligne in comparables)
                        if comparables else None),
    }


# ── CALX366 — LA PORTE : saisir un pan, lire les écarts, geler une version ──
#
# Contrat ``contract_samples/calepinage_asbuilt_ecarts.json`` (CALX337), porte
# ``views/asbuilt.py``. Tout ce qui suit est la forme publiée par
# ``GET/POST calepinages/<pk>/pose-reelle/`` : une ligne par pan
# ``{pan, modules_prevus, modules_poses, ecart, ecarts_position, mention}``,
# ``total_pose`` à ``None`` tant qu'aucun pan n'est relevé, ``version_creee``
# à ``None`` tant que personne n'a demandé la version.

#: Préfixe du libellé de la version née des écarts : c'est LUI qui retrouve
#: la version (``version_creee``). Une version RESTAURÉE porte le libellé
#: « Restauration de la version #N » — elle ne se confond donc jamais avec
#: une reprise des écarts, même si elle en copie le résultat gelé.
PREFIXE_VERSION_POSE = 'Pose réelle'

#: Longueur maximale d'un libellé de version (``CalepinageVersion.libelle``).
LIBELLE_MAX = 200


class PoseRefusee(ValueError):
    """Refus métier, en français, avec le CHAMP fautif nommé."""

    def __init__(self, message, champ='pan'):
        super().__init__(message)
        self.champ = champ

    def corps(self):
        return {self.champ or 'detail': str(self)}


def _ligne_du_contrat(ligne):
    """Une ligne de ``comparer`` → la ligne publiée (contrat CALX337)."""
    return {
        'pan': ligne['pan'],
        'modules_prevus': ligne['prevu'],
        'modules_poses': ligne['pose'],
        'ecart': ligne['ecart'],
        'ecarts_position': ligne['ecarts_position'] or '',
        'mention': ligne['mention'] or '',
        # ACAL245 - la date SAISIE du releve de CE pan et son auteur.
        'releve_le': (ligne['releve_le'].isoformat()
                      if hasattr(ligne.get('releve_le'), 'isoformat')
                      else ligne.get('releve_le')),
        'releve_par': ligne.get('releve_par'),
        # ACAL267 — l'identifiant STABLE du pan, son libellé et l'orphelin.
        'zone_id': ligne.get('zone_id') or ligne['pan'],
        'libelle': ligne.get('libelle') or ligne['pan'],
        'orphelin': bool(ligne.get('orphelin')),
        # ACAL248 — le prévu figé au relevé, et la conception d'aujourd'hui.
        'prevu_fige': bool(ligne.get('prevu_fige')),
        'prevu_actuel': ligne.get('prevu_actuel'),
        'conception_modifiee': bool(ligne.get('conception_modifiee')),
    }


def _forme_contrat(ecarts, version_creee):
    """La réponse de ``pose-reelle/`` — PURE, la MÊME en GET et en POST."""
    return {
        'source': ecarts['source_prevu'],
        'lignes': [_ligne_du_contrat(ligne) for ligne in ecarts['pans']],
        'total_prevu': ecarts['total_prevu'],
        'total_pose': ecarts['total_pose'],
        'version_creee': version_creee,
    }


def _derniere_version_pose(calepinage):
    """La dernière version née des écarts de pose, ou ``None``."""
    from ..models import CalepinageVersion

    if calepinage is None or not getattr(calepinage, 'pk', None):
        return None
    return (CalepinageVersion.objects
            .filter(calepinage=calepinage,
                    libelle__startswith=PREFIXE_VERSION_POSE)
            .order_by('-created_at', '-id')
            .first())


def etat_pose_reelle(calepinage):
    """GET — prévu, posé, écart par pan, totaux et version née des écarts."""
    version = _derniere_version_pose(calepinage)
    return _forme_contrat(ecarts_du_calepinage(calepinage),
                          version.pk if version is not None else None)


def _modules_poses(brut):
    """Un entier positif ou nul, ou un refus qui NOMME ``modules_poses``.

    L'intention claire est normalisée (``"3"``, ``3.0`` → ``3``) ; tout le
    reste — négatif, décimal, texte, booléen, vide — est refusé, la valeur
    reçue recopiée dans le message.
    """
    valeur = brut
    if isinstance(valeur, str) and valeur.strip().lstrip('-').isdigit():
        valeur = int(valeur.strip())
    if isinstance(valeur, float) and valeur.is_integer():
        valeur = int(valeur)
    if isinstance(valeur, bool) or not isinstance(valeur, int) or valeur < 0:
        raise PoseRefusee(
            "Le nombre de modules réellement posés est un entier positif ou "
            f"nul (reçu : « {brut} »).", 'modules_poses')
    return valeur


def _releve_le(brut):
    """La date SAISIE du relevé (``AAAA-MM-JJ``), ou un refus nommé."""
    from datetime import date

    from django.utils.dateparse import parse_date

    if isinstance(brut, date):
        return brut
    texte = brut.strip() if isinstance(brut, str) else ''
    releve_le = parse_date(texte) if texte else None
    if releve_le is None:
        raise PoseRefusee(
            "La date du relevé est obligatoire et s'écrit AAAA-MM-JJ : elle "
            "est SAISIE, jamais déduite de la date de synchronisation.",
            'releve_le')
    return releve_le


def _zone_de_la_saisie(pan, pans):
    """ACAL267 — ``(zone_id, libellé)`` désigné par ``pan`` : l'identifiant
    STABLE d'un pan prévu, à défaut son libellé s'il est UNIQUE. ``pans`` :
    ``[{zone_id, libelle}]`` (ou des libellés seuls, forme historique)."""
    pans = [p if isinstance(p, dict) else {'zone_id': p, 'libelle': p}
            for p in pans or ()]
    for prevu in pans:
        if prevu['zone_id'] == pan:
            return prevu['zone_id'], prevu['libelle']
    memes = [prevu for prevu in pans if prevu['libelle'] == pan]
    if len(memes) == 1:
        return memes[0]['zone_id'], memes[0]['libelle']
    if len(memes) > 1:
        raise PoseRefusee(
            f"Plusieurs pans portent le libellé « {pan} » : désignez le pan "
            f"par son identifiant ({', '.join(p['zone_id'] for p in memes)}).",
            'pan')
    raise PoseRefusee(
        f"Pan inconnu du document : « {pan} ». Pans prévus : "
        f"{', '.join(p['libelle'] for p in pans) or 'aucun'}.", 'pan')


def _valider_saisie(donnees, pans, deja_releves=()):
    """La saisie d'UN pan, validée contre les pans PRÉVUS — PURE.

    Ordre des refus : ``pan`` (inconnu du prévu), puis ``modules_poses``,
    puis ``releve_le`` — un message par champ, la forme ``refus_*`` du
    contrat. ACAL245 : ``releve_le`` n'est facultative qu'en CORRECTION d'un
    pan deja releve (``deja_releves``) ; la premiere saisie reste refusee.
    ACAL267 : ``pan`` désigne le pan par son identifiant STABLE (le libellé
    unique reste admis) ; ``deja_releves`` porte des identifiants.
    """
    if not isinstance(donnees, dict):
        raise PoseRefusee("Le corps attendu est la saisie d'un pan : "
                          "{pan, modules_poses, ecarts_position, releve_le}.",
                          'pan')
    pan = str(donnees.get('pan') or '').strip()
    zone_id, libelle = _zone_de_la_saisie(pan, pans)
    return {
        'pan': libelle,
        'zone_id': zone_id,
        'modules_poses': _modules_poses(donnees.get('modules_poses')),
        'ecarts_position': str(donnees.get('ecarts_position') or ''),
        'releve_le': (None if zone_id in deja_releves
                      and not str(donnees.get('releve_le') or '').strip()
                      else _releve_le(donnees.get('releve_le'))),
    }


def enregistrer_pose(calepinage, donnees, *, user=None):
    """POST — enregistre (ou met à jour) la pose réelle d'UN pan.

    Un seul relevé par pan (contrainte ``uniq_pose_reelle_par_zone``) : une
    seconde saisie du même pan le CORRIGE, sous verrou de ligne. La société
    et l'auteur viennent du serveur ; le geste est journalisé.

    Raises:
        PoseRefusee: pan inconnu, nombre illisible, date manquante ou future
            — le champ fautif est toujours nommé.
    """
    from django.core.exceptions import ValidationError
    from django.db import transaction

    from ..models import PoseReelle
    from .journal import journaliser_pose_reelle

    prevus, source = pans_prevus(calepinage)
    deja = set(PoseReelle.objects.filter(calepinage=calepinage)
               .values_list('zone_id', flat=True))
    saisie = _valider_saisie(
        donnees, [{'zone_id': pan['zone_id'], 'libelle': pan['libelle']}
                  for pan in prevus], deja)
    prevu_du_pan = next((pan['modules'] for pan in prevus
                         if pan['zone_id'] == saisie['zone_id']), None)
    auteur = user if getattr(user, 'pk', None) else None
    with transaction.atomic():
        pose = (PoseReelle.objects.select_for_update()
                .filter(calepinage=calepinage, zone_id=saisie['zone_id'])
                .first())
        ancien = pose.modules_poses if pose is not None else None
        if pose is None:
            pose = PoseReelle(company=calepinage.company,
                              calepinage=calepinage,
                              zone_id=saisie['zone_id'])
        # Le libellé AFFICHÉ (figé pour un pan qui disparaîtrait).
        pose.pan = saisie['pan']
        if ancien is None or ancien != saisie['modules_poses']:
            # ACAL248 — le prévu est FIGÉ à la saisie (et re-figé quand le
            # nombre posé change) : retoucher le toit après coup ne réécrit
            # plus l'écart de ce relevé.
            pose.modules_prevus = _entier(prevu_du_pan)
            pose.prevu_source = PREVU_SOURCE_COURT.get(source,
                                                       PREVU_SOURCE_DEFAUT)
        pose.modules_poses = saisie['modules_poses']
        pose.ecarts_position = saisie['ecarts_position']
        if saisie['releve_le'] is not None:
            # ACAL245 - la date n'est reecrite que si elle est FOURNIE ; une
            # correction du seul texte conserve la date ET l'auteur.
            pose.releve_le = saisie['releve_le']
            pose.releve_par = auteur
        try:
            pose.full_clean(exclude=['company', 'calepinage', 'releve_par'])
        except ValidationError as erreur:
            champ, messages = sorted(erreur.message_dict.items())[0]
            raise PoseRefusee(messages[0], champ)
        pose.save()
    journaliser_pose_reelle(calepinage, pan=saisie['pan'], ancien=ancien,
                            nouveau=saisie['modules_poses'],
                            ecarts_position=saisie['ecarts_position'],
                            user=auteur)
    return pose


def supprimer_pose(calepinage, zone_id, *, user=None):
    """ACAL267 — DELETE ``pose-reelle/<zone_id>/`` : retire le relevé d'un pan
    (ligne ORPHELINE comprise), geste journalisé.

    Raises:
        PoseRefusee: aucun relevé pour ce pan (champ ``detail`` → 404).
    """
    from django.db import transaction

    from ..models import PoseReelle
    from .journal import journaliser_pose_reelle

    zone_id = str(zone_id or '').strip()
    with transaction.atomic():
        pose = (PoseReelle.objects.select_for_update()
                .filter(calepinage=calepinage, zone_id=zone_id).first())
        if pose is None:
            raise PoseRefusee(MESSAGE_AUCUNE_POSE, 'detail')
        ancien, libelle = pose.modules_poses, pose.pan
        pose.delete()
    journaliser_pose_reelle(calepinage, pan=libelle, ancien=ancien,
                            nouveau=None,
                            user=user if getattr(user, 'pk', None) else None)


def _libelle_version(ecarts):
    """Le libellé qui NOMME les pans en écart — PUR, borné à 200 caractères.

    « En écart » = un pan dont le posé diffère du prévu, ou un pan posé sans
    prévu ; un pan non relevé est nommé à part (on ne sait pas s'il est en
    écart). Le nombre de modules RÉELLEMENT posés y figure toujours.
    """
    en_ecart, non_releves = [], []
    for ligne in ecarts['pans']:
        if ligne.get('orphelin'):
            en_ecart.append(f"{ligne.get('libelle') or ligne['pan']} "
                            "(hors prévu)")
        elif ligne['pose'] is None:
            non_releves.append(ligne['pan'])
        elif ligne['prevu'] is None:
            en_ecart.append(f"{ligne['pan']} (hors prévu)")
        elif ligne['ecart']:
            en_ecart.append(f"{ligne['pan']} ({ligne['ecart']:+d})")
    morceaux = [f"{PREFIXE_VERSION_POSE} — {ecarts['total_pose']} module(s) "
                f"posé(s) sur {ecarts['total_prevu']} prévu(s)"]
    morceaux.append('écarts : ' + ', '.join(en_ecart) if en_ecart
                    else 'aucun écart sur les pans relevés')
    if non_releves:
        morceaux.append('non relevé(s) : ' + ', '.join(non_releves))
    libelle = ' ; '.join(morceaux)
    if len(libelle) > LIBELLE_MAX:
        libelle = libelle[:LIBELLE_MAX - 1] + '…'
    return libelle


def version_depuis_ecarts(calepinage, user=None):
    """POST ``creer_version`` — gèle une ``CalepinageVersion`` des écarts.

    Le chemin est LE chemin unique d'historisation
    (``services/versions.py::enregistrer_version``). Le dessin n'est pas
    touché (le chantier ne le redessine pas) : la version gèle le document
    courant, et son résultat gelé porte en plus le bloc ``asbuilt`` — les
    lignes du contrat et le nombre de modules RÉELLEMENT posés. Le libellé
    nomme les pans en écart. Un second appel sur les MÊMES écarts rend la
    version déjà gelée au lieu d'en empiler une copie.

    Returns:
        ``(version, creee)``.

    Raises:
        PoseRefusee: aucun pan relevé — il n'y a aucun écart à figer
            (champ ``creer_version``).
    """
    from .journal import journaliser_version_pose
    from .versions import enregistrer_version

    ecarts = ecarts_du_calepinage(calepinage)
    if ecarts['total_pose'] is None:
        raise PoseRefusee(
            "Aucun pan n'a été relevé sur le chantier : il n'y a aucun écart "
            "à figer en version. Saisissez d'abord les modules posés.",
            'creer_version')
    bloc = {
        'source': ecarts['source_prevu'],
        'total_prevu': ecarts['total_prevu'],
        'total_pose': ecarts['total_pose'],
        'lignes': [_ligne_du_contrat(ligne) for ligne in ecarts['pans']],
    }
    precedente = _derniere_version_pose(calepinage)
    if (precedente is not None
            and (precedente.resultat or {}).get('asbuilt') == bloc):
        return precedente, False
    resultat = (dict(calepinage.resultat)
                if isinstance(calepinage.resultat, dict) else {})
    resultat['asbuilt'] = bloc
    auteur = user if getattr(user, 'pk', None) else None
    version = enregistrer_version(calepinage, user=auteur,
                                  libelle=_libelle_version(ecarts),
                                  resultat=resultat,
                                  meme_empreinte_admise=True)
    journaliser_version_pose(calepinage, version=version, user=auteur)
    return version, True
