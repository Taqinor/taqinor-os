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

SOURCE_VARIANTE = 'variante retenue'
SOURCE_CALEPINAGE = 'document du calepinage'

MENTION_SANS_SAISIE = (
    "Aucun relevé de pose n'a été saisi pour ce pan : l'écart n'est pas "
    "affiché (il serait supposé, pas mesuré)."
)
MENTION_SANS_PREVU = (
    "Ce pan n'existe pas dans la variante retenue : il n'y a rien à quoi "
    "comparer le posé."
)

__all__ = [
    'SOURCE_VARIANTE', 'SOURCE_CALEPINAGE', 'MENTION_SANS_SAISIE',
    'comparer', 'pans_prevus', 'ecarts_du_calepinage',
    # CALX366 — la porte HTTP ``pose-reelle/``.
    'PREFIXE_VERSION_POSE', 'PoseRefusee', 'etat_pose_reelle',
    'enregistrer_pose', 'version_depuis_ecarts',
]


def comparer(prevus, saisies):
    """``[{pan, prevu, pose, ecart, ecarts_position, releve_le, mention}]``.

    Args:
        prevus: ``[{pan, modules}]`` — les pans de la variante retenue.
        saisies: ``[{pan, modules_poses, ecarts_position, releve_le}]``.

    Un pan prévu SANS saisie sort avec ``pose = None`` et ``ecart = None`` ;
    un pan SAISI qui n'existe pas au prévu sort avec ``prevu = None`` — les
    deux cas sont VISIBLES, aucun n'est silencieusement écarté.
    """
    par_pan = {}
    for saisie in saisies or []:
        pan = str((saisie or {}).get('pan') or '').strip()
        if pan:
            par_pan[pan] = saisie

    lignes, vus = [], set()
    for prevu in prevus or []:
        pan = str((prevu or {}).get('pan') or '').strip()
        vus.add(pan)
        lignes.append(_ligne(pan, prevu.get('modules'), par_pan.get(pan)))
    for pan, saisie in par_pan.items():
        if pan not in vus:
            lignes.append(_ligne(pan, None, saisie))
    return lignes


def _entier(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    if isinstance(valeur, (int, float)):
        return int(valeur)
    return None


def _ligne(pan, modules_prevus, saisie):
    prevu = _entier(modules_prevus)
    pose = _entier((saisie or {}).get('modules_poses'))
    if pose is None:
        mention = MENTION_SANS_SAISIE
    elif prevu is None:
        mention = MENTION_SANS_PREVU
    else:
        mention = ''
    return {
        'pan': pan,
        'prevu': prevu,
        'pose': pose,
        # L'écart n'existe QUE quand les deux nombres sont des saisies
        # réelles — jamais une différence avec un zéro supposé.
        'ecart': (pose - prevu if pose is not None and prevu is not None
                  else None),
        'ecarts_position': ((saisie or {}).get('ecarts_position') or ''),
        'releve_le': (saisie or {}).get('releve_le'),
        'mention': mention,
    }


def pans_prevus(calepinage):
    """Les pans PRÉVUS : ceux de la variante RETENUE, sinon du document.

    Renvoie ``(pans, source)`` — la source est PUBLIÉE pour qu'un écart lu
    sur le document du calepinage ne se lise jamais comme un écart avec la
    variante contractuelle.
    """
    from .production import pans_du_layout

    variante = (calepinage.variantes.filter(retenue=True).first()
                if hasattr(calepinage, 'variantes') else None)
    if variante is not None and variante.roof_layout:
        return (pans_du_layout(variante.roof_layout), SOURCE_VARIANTE)
    return (pans_du_layout(getattr(calepinage, 'roof_layout', None)),
            SOURCE_CALEPINAGE)


def ecarts_du_calepinage(calepinage):
    """L'as-built COMPLET d'un calepinage : prévu, posé, écart, totaux.

    Lecture PURE, bornée société par l'appelant. ``ecart_total`` n'existe que
    si AU MOINS un pan a été relevé — sinon il vaudrait « 0 » sur un chantier
    dont personne n'a compté un seul module.
    """
    from ..models import PoseReelle

    prevus, source = pans_prevus(calepinage)
    saisies = [
        {'pan': pose.pan, 'modules_poses': pose.modules_poses,
         'ecarts_position': pose.ecarts_position, 'releve_le': pose.releve_le}
        for pose in PoseReelle.objects.filter(calepinage=calepinage)
    ]
    lignes = comparer([{'pan': pan['pan'], 'modules': pan['modules']}
                       for pan in prevus], saisies)
    return _agreger(calepinage.pk, source, lignes)


def _agreger(calepinage_id, source, lignes):
    """Les totaux des lignes de ``comparer`` — PUR (aucune base).

    CALX366 — extrait tel quel de ``ecarts_du_calepinage`` pour que la forme
    du contrat se rejoue sans base : même ``total_pose`` à ``None`` tant que
    rien n'est relevé, même ``ecart_total`` à ``None`` sans pan comparable.
    """
    releves = [ligne for ligne in lignes if ligne['pose'] is not None]
    comparables = [ligne for ligne in lignes if ligne['ecart'] is not None]
    return {
        'calepinage': calepinage_id,
        'source_prevu': source,
        'pans': lignes,
        'pans_releves': len(releves),
        'total_prevu': sum(ligne['prevu'] for ligne in lignes
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


def _valider_saisie(donnees, pans):
    """La saisie d'UN pan, validée contre les pans PRÉVUS — PURE.

    Ordre des refus : ``pan`` (inconnu du prévu), puis ``modules_poses``,
    puis ``releve_le`` — un message par champ, la forme ``refus_*`` du
    contrat.
    """
    if not isinstance(donnees, dict):
        raise PoseRefusee("Le corps attendu est la saisie d'un pan : "
                          "{pan, modules_poses, ecarts_position, releve_le}.",
                          'pan')
    pan = str(donnees.get('pan') or '').strip()
    if pan not in pans:
        raise PoseRefusee(
            f"Pan inconnu du document : « {pan} ». Pans prévus : "
            f"{', '.join(pans) or 'aucun'}.", 'pan')
    return {
        'pan': pan,
        'modules_poses': _modules_poses(donnees.get('modules_poses')),
        'ecarts_position': str(donnees.get('ecarts_position') or ''),
        'releve_le': _releve_le(donnees.get('releve_le')),
    }


def enregistrer_pose(calepinage, donnees, *, user=None):
    """POST — enregistre (ou met à jour) la pose réelle d'UN pan.

    Un seul relevé par pan (contrainte ``uniq_pose_reelle_par_pan``) : une
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

    prevus, _source = pans_prevus(calepinage)
    saisie = _valider_saisie(donnees, [pan['pan'] for pan in prevus])
    auteur = user if getattr(user, 'pk', None) else None
    with transaction.atomic():
        pose = (PoseReelle.objects.select_for_update()
                .filter(calepinage=calepinage, pan=saisie['pan']).first())
        ancien = pose.modules_poses if pose is not None else None
        if pose is None:
            pose = PoseReelle(company=calepinage.company,
                              calepinage=calepinage, pan=saisie['pan'])
        pose.modules_poses = saisie['modules_poses']
        pose.ecarts_position = saisie['ecarts_position']
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


def _libelle_version(ecarts):
    """Le libellé qui NOMME les pans en écart — PUR, borné à 200 caractères.

    « En écart » = un pan dont le posé diffère du prévu, ou un pan posé sans
    prévu ; un pan non relevé est nommé à part (on ne sait pas s'il est en
    écart). Le nombre de modules RÉELLEMENT posés y figure toujours.
    """
    en_ecart, non_releves = [], []
    for ligne in ecarts['pans']:
        if ligne['pose'] is None:
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
