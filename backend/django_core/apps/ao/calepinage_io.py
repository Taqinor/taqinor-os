"""AOF60 — la COUTURE entre ``apps.ao`` (persistance) et ``core.calepinage``
(moteur pur) : traduction, et RIEN d'autre.

Ce module ne contient **aucune géométrie**. Il ne compte rien, ne pose rien,
ne décide rien : il transforme des lignes de l'ORM en un DOCUMENT conforme au
contrat JSON versionné d'AOF57 (``core.calepinage.serialisation``), et
retransforme la sortie du moteur en JSON persistable pour
``VarianteCalepinage.resultat`` / ``.preuve``.

Pourquoi une couche à part
--------------------------
Sans elle, le service d'orchestration accumulerait des ``if forme == 'arc'`` et
finirait par porter une deuxième géométrie — exactement le défaut que le paquet
pur supprime. Ici la règle est mécanique : **l'ORM entre, un dict sort**. Le
moteur ne voit jamais un modèle Django, l'ORM ne voit jamais une dataclass du
moteur.

Repère et unités
----------------
Le moteur a UN repère unifié (``core/calepinage/surfaces/base.py``) : ``x``
court LE LONG de la rangée, ``y`` est l'axe TRANSVERSAL sur lequel les rangées
se rangent. ``ToitureAO.contour_local_m`` est déjà en mètres dans le repère
local (AOF19) — aucune conversion d'unité n'a lieu ici, seulement un
changement de représentation.

Affectation des obstacles en multi-surfaces
-------------------------------------------
Une toiture en arc est découpée en SEGMENTS (murets au ras) : chaque segment a
son propre plan de pose et sa propre abscisse locale, si bien qu'un obstacle ne
peut pas être rattaché à un segment par sa seule géométrie (les segments se
recouvrent en coordonnées locales). Le document porte donc une clé
``affectations`` — ``{repère de surface: [repères d'obstacles]}`` — que le
contrat pur IGNORE (``EntreeCalepinage.depuis_dict`` ne lit que ses clés). En
son absence et à plusieurs surfaces, on REFUSE avec un motif nommé : deviner
une affectation produirait un compte faux que personne ne verrait.
"""
from __future__ import annotations

from decimal import Decimal

from core.calepinage.version import SCHEMA_VERSION, VERSION_MOTEUR

__all__ = [
    'EntreeInvalide', 'NATURE_VERS_TYPE_MOTEUR', 'PROVENANCE_VERS_MOTEUR',
    'MODE_POSE_IMPOSE', 'TIROIRS', 'CHAMPS_RIVES_VERS_CONTRAT',
    'document_entree', 'affectations_du_document',
    'kits_vers_document', 'parametres_vers_document',
    'rangees_imposees_du_preset', 'surface_vers_document',
    'obstacles_vers_document', 'zones_vers_document',
    'resultat_vers_json', 'preuve_vers_json',
    'marges_vers_json', 'tiroirs_vers_json', 'tiroirs_vides',
    'PATCH_MOTEUR_VERS_PARAMS', 'PATCH_MOTEUR_VERS_OBSTACLE',
    'action_de_patch', 'suggestion_vers_json', 'suggestions_vers_json',
]


class EntreeInvalide(ValueError):
    """L'entrée persistée ne peut pas produire un document de calepinage.

    Toujours porteuse d'un motif en FRANÇAIS : c'est ce que l'utilisateur lit
    dans un 400, pas un code d'erreur.
    """


#: ``ObstacleAO.Nature`` (13 valeurs métier AO) -> ``TypeObstacle`` du moteur
#: (13 valeurs). Les natures AO sans équivalent exact tombent sur
#: ``NATURE_INCONNUE`` — sans conséquence sur le calcul : le dégagement
#: RÉELLEMENT appliqué est toujours celui que l'ORM a dérivé (AOF22), transmis
#: en surcharge explicite, jamais redevine par le moteur.
NATURE_VERS_TYPE_MOTEUR = {
    'caisson_technique': 'CAISSON_BETON',
    'cage_escalier': 'CAGE_ESCALIER',
    'edicule': 'EDICULE',
    'souche': 'SOUCHE',
    'groupe_clim': 'CLIMATISEUR',
    'acrotere': 'ACROTERE',
    'joint_dilatation': 'JOINT_DILATATION',
    'muret': 'MURET',
    'decrochement_niveau': 'MURET',
    'pan_coupe': 'NATURE_INCONNUE',
    'lanterneau': 'LANTERNEAU',
    'exutoire_fumee': 'NATURE_INCONNUE',
    'chemin_cables': 'NATURE_INCONNUE',
}

#: ``ObstacleAO.Provenance`` -> ``Provenance`` du moteur. Le vocabulaire AO est
#: le format CANONIQUE (en-tête du groupe) ; le moteur nomme ``RELEVE`` ce que
#: l'AO nomme ``MESURE``.
PROVENANCE_VERS_MOTEUR = {
    'MESURE': 'RELEVE',
    'MESURE_DOUTEUX': 'RELEVE_DOUTEUX',
    'PLAN': 'PLAN',
    'DEVINE': 'DEVINE',
    'DECLARE_CLIENT': 'DECLARE_CLIENT',
    'ECARTE': 'ECARTE',
}


def _f(valeur, defaut=None):
    """``Decimal``/``str``/``None`` -> ``float`` (ou ``defaut``)."""
    if valeur is None or valeur == '':
        return defaut
    if isinstance(valeur, Decimal):
        return float(valeur)
    return float(valeur)


def _contour(points):
    return [[_f(p[0], 0.0), _f(p[1], 0.0)] for p in (points or [])]


# ─────────────────────────────────────────────────────── surfaces
def surface_vers_document(toiture, *, rives, axe_rangee):
    """La ou les surfaces d'une ``ToitureAO``, en forme de contrat.

    * ``arc`` -> une surface ``arc`` par segment déclaré dans
      ``arc_segments`` (les murets au ras SÉPARENT : aucune rangée n'est à
      cheval, chaque segment a ses propres rives d'extrémité) ; à défaut de
      segments, un arc unique de développé ``developpe_m``.
    * toute autre forme -> un ``polygone`` bâti sur ``contour_local_m``. Le
      polygone couvre le rectangle et le L sans cas particulier : c'est le
      contour lui-même qui répond, et il porte son décalage d'origine (un
      ``rectangle`` du contrat est implicitement calé en (0, 0), ce qui
      décalerait tous les obstacles d'une enveloppe relevée ailleurs).
    """
    commun = {
        'rives': dict(rives),
        'axe_rangee': axe_rangee,
        'niveau': int(toiture.niveau or 0),
        'azimut_deg': _f(toiture.angle_nord_deg, 180.0),
        'origine': [0.0, 0.0],
        'coupures': [],
    }
    repere_base = toiture.code_document or f'TOITURE_{toiture.pk}'

    if toiture.forme == toiture.Forme.ARC:
        rayon = _f(toiture.rayon_ext_m)
        largeur = _f(toiture.largeur_m)
        if rayon is None or largeur is None:
            raise EntreeInvalide(
                "Une toiture en arc exige un rayon extérieur ET une largeur "
                "de bande : sans les deux, l'arc n'est pas développable.")
        segments = [_f(s, 0.0) for s in (toiture.arc_segments or [])
                    if _f(s, 0.0)]
        if not segments:
            raise EntreeInvalide(
                "Une toiture en arc exige au moins un segment de développé "
                "(`arc_segments`) : le développé muret-à-muret n'est pas "
                "déductible du rayon seul.")
        surfaces = []
        for index, developpe in enumerate(segments, start=1):
            surfaces.append(dict(
                commun, type='arc', repere=f'{repere_base}_S{index}',
                rayon_ext_m=rayon, largeur_m=largeur, developpe_m=developpe))
        return surfaces

    contour = _contour(toiture.contour_local_m)
    if len(contour) < 3:
        raise EntreeInvalide(
            "L'enveloppe de la toiture est vide : au moins 3 sommets sont "
            "nécessaires pour calepiner.")
    return [dict(commun, type='polygone', repere=repere_base,
                 contour=contour, trous=[])]


# ─────────────────────────────────────────────────────── obstacles
def obstacles_vers_document(toiture):
    """Les obstacles ACTIFS d'une toiture, en forme de contrat.

    Trois règles, toutes trois portées par la donnée et non par le moteur :

    * seuls les obstacles ``actif=True`` sortent — un obstacle désactivé n'est
      pas une géométrie du site ;
    * un obstacle ``hors_zone_pv`` est EXCLU du document : il ne bloque rien
      (série de questions FRDISI n°3 — « structure de rive hors zone PV », +6
      modules) ; le conserver bloquerait une bande que le client a confirmée
      libre ;
    * le ``degagement_m`` de l'ORM (dérivé par AOF22 : ``max(nature,
      provenance)``, ou surcharge motivée) est transmis TEL QUEL. Le moteur le
      lit comme une surcharge explicite et ne redevine jamais un dégagement.
    """
    sortie = []
    for obstacle in toiture.obstacles.filter(actif=True).order_by(
            'repere', 'id'):
        if obstacle.hors_zone_pv:
            continue
        x0, x1 = _f(obstacle.rect_x0_m), _f(obstacle.rect_x1_m)
        y0, y1 = _f(obstacle.rect_y0_m), _f(obstacle.rect_y1_m)
        if None in (x0, x1, y0, y1):
            polygone = _contour(obstacle.polygone_local_m)
            if len(polygone) < 3:
                raise EntreeInvalide(
                    "L'obstacle « %s » n'a ni emprise rectangulaire complète "
                    "ni polygone : sa géométrie est inexploitable."
                    % (obstacle.repere or f'#{obstacle.pk}'))
            xs = [p[0] for p in polygone]
            ys = [p[1] for p in polygone]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        sortie.append({
            'repere': obstacle.repere or f'OBS{obstacle.pk}',
            'x0': min(x0, x1), 'x1': max(x0, x1),
            'y0': min(y0, y1), 'y1': max(y0, y1),
            'type_obstacle': NATURE_VERS_TYPE_MOTEUR.get(
                obstacle.nature, 'NATURE_INCONNUE'),
            'provenance': PROVENANCE_VERS_MOTEUR.get(
                obstacle.provenance, 'PLAN'),
            'degagement_m': _f(obstacle.degagement_m, 0.30),
            'hauteur_m': _f(obstacle.hauteur_m),
            'regle_appliquee': obstacle.regle_degagement or '',
        })
    return sortie


# ─────────────────────────────────────────────────────── zones (PV55)
def zones_vers_document(toiture):
    """Les ZONES d'une toiture, en forme de contrat (``serialisation._zone``).

    Le document portait ``zones: []`` EN DUR : le moteur sait consommer quatre
    natures de contour depuis AOF57, et aucune ne lui parvenait jamais. Une
    servitude ou une bande coupe-feu tracée par le dessinateur ne changeait donc
    rien au compte publié — silencieusement.

    Trois règles, toutes portées par la donnée :

    * un contour VIDE est ignoré — une zone en cours de saisie ne délimite rien
      et ne peut donc ni bloquer ni préférer quoi que ce soit ;
    * un contour de 1 ou 2 sommets est un REFUS NOMMÉ : c'est un tracé à
      moitié fait, et ``ZoneAO.clean`` le refuse déjà à la saisie. L'ignorer
      ici laisserait croire qu'une zone interdite bloque, alors qu'elle ne
      bloquerait rien ;
    * la ``nature`` passe TELLE QUELLE : ``ZoneAO.Nature`` reprend les valeurs
      de ``NatureZone`` à la lettre, précisément pour qu'aucune traduction ne
      s'intercale ici.
    """
    sortie = []
    for zone in toiture.zones.all().order_by('repere', 'id'):
        sommets = _contour(zone.sommets)
        if not sommets:
            continue
        if len(sommets) < 3:
            raise EntreeInvalide(
                "La zone « %s » n'a que %d sommet(s) : un contour de moins de "
                '3 points ne délimite aucune surface.'
                % (zone.repere or f'#{zone.pk}', len(sommets)))
        sortie.append({
            'repere': zone.repere or f'ZONE{zone.pk}',
            'nature': zone.nature,
            'sommets': sommets,
            'hauteur_m': _f(zone.hauteur_m),
            'retrait_m': _f(zone.retrait_m, 0.0),
        })
    return sortie


# ─────────────────────────────────────────────────────── kits
def kits_vers_document(kits):
    """``KitCalepinage`` -> kits du contrat, géométrie DÉ-DÉRIVÉE.

    Le modèle AO porte ``pas_rangee_m`` (le long de la rangée) et
    ``longueur_pente_m`` (dans la pente) ; le contrat porte le GRAND et le
    PETIT côté du module. La correspondance dépend de l'orientation, et
    l'inversion est exacte : en PORTRAIT le pas est le petit côté, en PAYSAGE
    c'est le grand.
    """
    document = []
    for kit in kits:
        pas = _f(kit.pas_rangee_m)
        pente = _f(kit.longueur_pente_m)
        if not pas or not pente:
            raise EntreeInvalide(
                "Le kit « %s » n'a pas de géométrie exploitable (pas de "
                "rangée et longueur dans la pente sont obligatoires)."
                % kit.code)
        if kit.orientation_modules == kit.Orientation.PORTRAIT:
            module_long, module_court = pente, pas
        else:
            module_long, module_court = pas, pente
        if module_long < module_court:
            raise EntreeInvalide(
                "Le kit « %s » déclare un grand côté (%.3f m) plus petit que "
                "son petit côté (%.3f m) : l'orientation ou les dimensions "
                "sont incohérentes." % (kit.code, module_long, module_court))
        document.append({
            'code': kit.code,
            'libelle': kit.libelle,
            'module_long_m': module_long,
            'module_court_m': module_court,
            'puissance_module_wc': float(kit.puissance_module_w),
            'inclinaison_deg': _f(kit.inclinaison_deg, 15.0),
            'orientation': ('PORTRAIT'
                            if kit.orientation_modules
                            == kit.Orientation.PORTRAIT else 'PAYSAGE'),
            'modules_par_table': int(kit.modules_par_kit or 1),
            'faitage_m': _f(kit.faitage_m, 0.0),
        })
    return document


# ─────────────────────────────────────────────────────── paramètres
def rives_du_preset(params):
    """Les 4 rives NOMMÉES depuis un dict de preset (AOF27)."""
    return {
        'laterale_m': float(params.get('rive_laterale_m', 0.35)),
        'extremite_m': float(params.get('rive_extremite_m', 0.35)),
        'acrotere_m': float(params.get('acrotere_m', 0.0)),
        'joint_m': float(params.get('joint_m', 0.0)),
    }


#: Valeur de ``mode_pose`` qui EXIGE des rangées imposées (PV29).
MODE_POSE_IMPOSE = 'rangees_imposees_utilisateur'


def rangees_imposees_du_preset(brut, codes_kits):
    """PV30 — ``[[y0, code_kit], …]`` du preset -> forme du contrat, ou REFUS.

    Le champ traverse l'API tel que l'utilisateur l'a saisi : c'est ICI, à la
    couture, qu'il devient une donnée du contrat ou un refus NOMMÉ en français.
    Le moteur porte la même garde (``optimum._rangees_imposees``), mais il lève
    l'exception du NOYAU, que l'API ne sait pas retraduire en 400 : laisser le
    refus descendre jusque-là transformerait une faute de saisie en erreur 500.

    Absent, vide ou ``None`` -> ``None`` (le paramètre est alors OMIS du
    document, exactement comme le fait ``serialisation._parametres`` : écrire
    ``"rangees_imposees": null`` partout ferait bouger l'empreinte de relevés
    que personne n'a touchés).
    """
    if brut in (None, '', (), []):
        return None
    if isinstance(brut, dict) or not isinstance(brut, (list, tuple)):
        raise EntreeInvalide(
            'Les rangées imposées doivent être une liste de couples '
            '[position, code de kit] — reçu %s.' % type(brut).__name__)
    connus = list(codes_kits)
    rangees = []
    for rang, entree in enumerate(brut, start=1):
        if isinstance(entree, (str, bytes, dict)) or \
                not isinstance(entree, (list, tuple)) or len(entree) != 2:
            raise EntreeInvalide(
                "Rangée imposée n°%d : attendu un couple [position, code de "
                'kit], reçu %r.' % (rang, entree))
        position, code = entree
        try:
            position = float(position)
        except (TypeError, ValueError):
            raise EntreeInvalide(
                "Rangée imposée n°%d : la position « %r » n'est pas un nombre "
                'de mètres.' % (rang, position)) from None
        code = str(code)
        if code not in connus:
            raise EntreeInvalide(
                "Rangée imposée n°%d : le kit « %s » n'est pas autorisé sur "
                'cette toiture (kits déclarés : %s).'
                % (rang, code, ', '.join(connus) or 'aucun'))
        rangees.append([position, code])
    return rangees


def parametres_vers_document(params, codes_kits):
    """Paramètres du preset AO (AOF27) -> ``Parametres`` du contrat.

    Les dégagements par provenance du preset servent de PLANCHER générique ;
    le dégagement réellement appliqué reste celui de chaque obstacle.

    **PV30 — les deux paramètres de pose du plan passent d'un bout à l'autre.**
    ``rangees_imposees`` (PV29 : le dessinateur fixe lui-même ses rangées) et
    ``phase_forcee_m`` (PV52 : republier à l'identique une planche déjà posée
    sur chantier) voyagent depuis le dict de paramètres de la requête jusqu'au
    document du contrat, SANS nouvel endpoint : ``calculer`` et ``lancer`` les
    portent déjà, leur champ ``params`` étant un ``JSONField`` opaque. Ils sont
    OMIS du document quand ils ne disent rien — l'empreinte d'entrée d'un
    relevé que personne n'a touché ne doit pas bouger.
    """
    degagements = params.get('degagements_par_provenance_m') or {}
    mode_pose = params.get('mode_pose', 'rangees_explicites_dp')
    document = {
        'kits': list(codes_kits),
        'rives': rives_du_preset(params),
        'axe_rangee': params.get('axe_rangee', 'NORD_SUD'),
        'mode_pose': mode_pose,
        'allee_m': float(params.get('allee_min_m', 0.60)),
        'degagement_defaut_m': float(degagements.get('MESURE', 0.30)),
        'degagement_nature_inconnue_m': float(degagements.get('DEVINE', 0.50)),
        'pas_recherche_m': float(params.get('pas_recherche_m', 0.01)),
        'engagement_modules': params.get('engagement_modules'),
        'plafond_kwc': params.get('plafond_kwc'),
        'marge_troncon_min_m': float(params.get('marge_troncon_min_m', 0.02)),
        'marge_bande_min_m': float(params.get('marge_bande_min_m', 0.04)),
        'graine': int(params.get('graine', 0)),
    }

    rangees = rangees_imposees_du_preset(
        params.get('rangees_imposees'), codes_kits)
    if rangees is not None:
        document['rangees_imposees'] = rangees
    elif mode_pose == MODE_POSE_IMPOSE:
        # Se replier en silence sur le DP ferait croire à l'utilisateur qu'il a
        # imposé un plan que personne n'a posé — et le résultat porterait la
        # preuve « optimum prouvé » d'un plan qu'il n'a pas choisi.
        raise EntreeInvalide(
            'Mode « rangées imposées par l\'utilisateur » : aucune rangée '
            "n'est fournie (`rangees_imposees`). Le moteur ne pose pas un "
            "plan à la place de l'utilisateur.")

    phase = params.get('phase_forcee_m')
    if phase not in (None, ''):
        try:
            document['phase_forcee_m'] = float(phase)
        except (TypeError, ValueError):
            raise EntreeInvalide(
                "La phase forcée « %r » n'est pas un nombre de mètres."
                % (phase,)) from None
    return document


# ─────────────────────────────────────────────────────── document complet
def document_entree(toiture, *, params=None, kits=None):
    """Le DOCUMENT d'entrée complet d'une toiture, conforme à AOF57.

    ``params`` : dict de preset (défaut : l'instantané
    ``toiture.parametres_calepinage``, posé par ``services.appliquer_preset``).
    ``kits`` : itérable de ``KitCalepinage`` (défaut : ceux dont le code figure
    dans ``params['kits_autorises']``, actifs et de la MÊME société — un kit
    d'une autre société ne peut jamais entrer dans un calcul).
    """
    params = dict(params if params is not None
                  else (toiture.parametres_calepinage or {}))
    if kits is None:
        codes = params.get('kits_autorises') or []
        from .models import KitCalepinage

        requete = KitCalepinage.objects.filter(
            company=toiture.company, actif=True)
        if codes:
            requete = requete.filter(code__in=list(codes))
        kits = list(requete.order_by('code'))
    else:
        kits = list(kits)
    if not kits:
        raise EntreeInvalide(
            "Aucun kit de calepinage actif n'est disponible pour cette "
            "toiture : le calcul n'a rien à poser.")

    document_kits = kits_vers_document(kits)
    codes_kits = [k['code'] for k in document_kits]
    parametres = parametres_vers_document(params, codes_kits)
    surfaces = surface_vers_document(
        toiture, rives=parametres['rives'],
        axe_rangee=parametres['axe_rangee'])
    obstacles = obstacles_vers_document(toiture)

    document = {
        'schema_version': SCHEMA_VERSION,
        'repere': toiture.code_document or f'TOITURE_{toiture.pk}',
        'surfaces': surfaces,
        'kits': document_kits,
        'parametres': parametres,
        'obstacles': obstacles,
        # PV55 — les zones de la toiture, enfin transmises (elles étaient une
        # liste vide EN DUR : le moteur savait les lire, personne ne les lui
        # donnait).
        'zones': zones_vers_document(toiture),
        'engagements': [],
    }
    # PV44 — la section ÉLECTRIQUE, OMISE quand rien n'est imposé : le contrat
    # pur l'ignore (``EntreeCalepinage.depuis_dict`` ne lit que ses clés), et
    # l'empreinte d'un relevé que personne n'a touché ne bouge pas.
    electrique = electrique_du_preset(params)
    if electrique:
        document['electrique'] = electrique
    engagement = params.get('engagement_modules')
    if engagement:
        document['engagements'] = [[document['repere'], int(engagement)]]
    if len(surfaces) > 1:
        # Arc découpé en segments : les obstacles d'une toiture d'arc portent
        # leur segment dans leur repère (``S1_…``). Sans affectation explicite
        # le service REFUSE — on ne devine pas.
        document['affectations'] = _affectations_par_prefixe(surfaces,
                                                             obstacles)
    return document


def _affectations_par_prefixe(surfaces, obstacles):
    """Affecte chaque obstacle au segment dont le repère porte le suffixe.

    Convention de relevé (planches FRDISI) : un obstacle du segment ``S2``
    s'appelle ``S2_cage``. On rattache par ce préfixe ; un obstacle qui ne
    désigne AUCUN segment n'est pas affecté — le service refusera, plutôt que
    de le compter partout (il bloquerait trois fois) ou nulle part (il
    disparaîtrait du plan).
    """
    affectations = {}
    for index, surface in enumerate(surfaces, start=1):
        prefixe = 'S%d_' % index
        affectations[surface['repere']] = [
            o['repere'] for o in obstacles
            if o['repere'].startswith(prefixe)
            or o['repere'].startswith('%s_' % surface['repere'])
        ]
    return affectations


def affectations_du_document(document, surfaces, obstacles):
    """``{repère de surface: (obstacles du moteur, …)}`` — jamais deviné.

    Une seule surface : tous les obstacles. Plusieurs surfaces : l'affectation
    DOIT être déclarée et COMPLÈTE (chaque obstacle appartient à exactement une
    surface). Toute lacune est un refus nommé, jamais un compte silencieux.
    """
    obstacles = tuple(obstacles)
    if len(surfaces) == 1:
        return {surfaces[0].repere: obstacles}

    declarees = (document or {}).get('affectations')
    if not declarees:
        raise EntreeInvalide(
            "Entrée à %d surfaces sans affectation des obstacles : préciser "
            "`affectations` ({repère de surface: [repères d'obstacles]}). "
            "Deviner l'affectation produirait un compte faux."
            % len(surfaces))

    par_repere = {o.repere: o for o in obstacles}
    resultat = {}
    affectes = set()
    for surface in surfaces:
        reperes = declarees.get(surface.repere)
        if reperes is None:
            raise EntreeInvalide(
                "La surface « %s » n'a aucune affectation d'obstacles "
                "déclarée." % surface.repere)
        lot = []
        for repere in reperes:
            if repere not in par_repere:
                raise EntreeInvalide(
                    "La surface « %s » référence l'obstacle inconnu « %s »."
                    % (surface.repere, repere))
            lot.append(par_repere[repere])
            affectes.add(repere)
        resultat[surface.repere] = tuple(lot)

    orphelins = sorted(set(par_repere) - affectes)
    if orphelins:
        raise EntreeInvalide(
            "Obstacles non affectés à une surface : %s. Un obstacle sans "
            "segment disparaîtrait du plan sans que personne le voie."
            % ', '.join(orphelins))
    return resultat


# ─────────────────────────────────────────────────────── sortie
def preuve_vers_json(preuve, marges, *, controles=(), pas_recherche_m=0.01):
    """La PREUVE persistable d'AOF28, dans SON vocabulaire.

    Les clés sont celles que ``VarianteCalepinage.raisons_de_non_publiabilite``
    lit (``total_retenu``, ``total_optimal``, ``marge_troncon_min``,
    ``marge_bande_min``) : c'est ce qui rend la garde de publication effective
    au lieu d'être un commentaire.

    **Une marge NON MESURÉE vaut ``None``, jamais 0.** ``Marges`` du moteur
    rend ``0.0`` aussi bien pour « au ras » que pour « aucune marge de ce type
    n'existe dans ce plan » (une toiture sans obstacle n'a aucune marge de
    bande). Persister ce ``0.0`` refuserait la publication d'un plan sans
    obstacle : la garde d'AOF28 se dévaluerait, et l'utilisateur apprendrait à
    l'ignorer. Le critère de mesure est le repère fautif : ``marges_du_plan``
    ne nomme une rangée ou un obstacle QUE lorsqu'il a réellement mesuré
    quelque chose.
    """
    troncon = bande = None
    if marges is not None:
        if marges.rangee_critique:
            troncon = round(marges.troncon_min_m, 6)
        if marges.obstacle_critique:
            bande = round(marges.bande_min_m, 6)
    return {
        'total_retenu': preuve.compte_retenu,
        'total_optimal': preuve.compte_optimal,
        'methode': preuve.methode.value,
        'methode_exacte': bool(preuve.methode.exacte),
        'optimal': bool(preuve.optimal),
        'libelle': preuve.libelle,
        'pas_cm': round(pas_recherche_m * 100.0, 3),
        'nb_optima': preuve.nb_plans_optimaux,
        'borne_superieure': preuve.borne_superieure,
        'marge_troncon_min': troncon,
        'marge_bande_min': bande,
        'rangee_critique': marges.rangee_critique if marges else '',
        'obstacle_critique': marges.obstacle_critique if marges else '',
        'controles': list(controles),
        'version_moteur': VERSION_MOTEUR,
    }


def marges_vers_json(marges):
    """PV49 — les marges de robustesse PUBLIÉES, en centimètres.

    **Une grandeur NON MESURÉE vaut ``None``, jamais ``0``.** ``Marges`` du
    moteur rend ``0.0`` aussi bien pour « au ras » que pour « ce plan n'a
    aucune marge de ce type » (une toiture sans obstacle n'a aucune marge de
    bande). Publier ce zéro ferait lire « marge nulle » là où rien n'a été
    mesuré — exactement l'erreur que ``preuve_vers_json`` évite déjà, avec le
    MÊME critère : le repère fautif. ``marges_du_plan`` ne nomme une rangée ou
    un obstacle QUE lorsqu'il a réellement mesuré quelque chose.
    """
    troncon = bande = None
    rangee = obstacle = ''
    if marges is not None:
        rangee = marges.rangee_critique or ''
        obstacle = marges.obstacle_critique or ''
        if rangee:
            troncon = round(marges.troncon_min_cm, 3)
        if obstacle:
            bande = round(marges.bande_min_cm, 3)
    return {
        'troncon_min_cm': troncon,
        'bande_min_cm': bande,
        'rangee_critique': rangee,
        'obstacle_critique': obstacle,
    }


# ─────────────────────────────────────────────────────── tiroirs (PV49)
#
# Le moteur (``core.calepinage.tiroirs``) CALCULE les charges utiles des
# tiroirs ; il ne connaît pas le vocabulaire de l'écran. La traduction est ici,
# et elle suit UNE règle : **on renomme ce qui a un correspondant fidèle, on ne
# rebaptise JAMAIS une grandeur du nom d'une autre.** Un dégagement ne devient
# pas une allée parce que le contrat aurait mis une allée à cette place.

#: Vocabulaire du MOTEUR -> vocabulaire du CONTRAT, pour les champs du tiroir
#: « Rives & dégagements » (les seuls qui divergent).
CHAMPS_RIVES_VERS_CONTRAT = {
    'rive_laterale_m': 'rive_laterale',
    'rive_extremite_m': 'rive_extremite',
    'degagement_defaut_m': 'degagement_standard',
    'degagement_nature_inconnue_m': 'degagement_inconnu',
}

#: Les 5 tiroirs du contrat. ``electrique`` est produit depuis PV44 par
#: ``core.electrique`` (voir plus bas) ; il retombe sur ``donnees: null`` quand
#: le budget synchrone ne permet pas de le calculer — l'écran fait
#: ``if (!donnees) return null`` plutôt que d'afficher des chiffres creux.
TIROIRS = ('kits', 'allees', 'rives', 'orientation', 'electrique')


def tiroirs_vides():
    """Les 5 tiroirs à l'état « rien de calculé » — la forme reste ENTIÈRE.

    Un tiroir dégradé garde sa clé et son couple ``(donnees, valeurs)`` : un
    écran qui reçoit parfois 4 clés et parfois 5 finit par tester l'absence de
    clé au lieu de l'absence de données, et c'est là qu'il casse.
    """
    return {nom: {'donnees': None, 'valeurs': {}} for nom in TIROIRS}


def _champ_rives_vers_contrat(champ):
    """Un champ du tiroir « Rives » : code traduit, ``impacts`` TOUJOURS là."""
    sortie = dict(champ)
    sortie['code'] = CHAMPS_RIVES_VERS_CONTRAT.get(champ.get('code'),
                                                   champ.get('code'))
    sortie.setdefault('impacts', [])
    return sortie


def _rives_vers_contrat(donnees):
    sortie = dict(donnees)
    sortie['champs'] = [_champ_rives_vers_contrat(c)
                        for c in donnees.get('champs') or ()]
    variante = donnees.get('variante_conservatrice')
    if variante is not None:
        variante = dict(variante)
        variante['valeurs'] = {
            CHAMPS_RIVES_VERS_CONTRAT.get(cle, cle): valeur
            for cle, valeur in (variante.get('valeurs') or {}).items()}
        sortie['variante_conservatrice'] = variante
    return sortie


def _kits_vers_contrat(donnees):
    """``approvisionnement`` porte TOUJOURS ses deux clés.

    Tant qu'aucun contrôle n'a confirmé l'approvisionnement (AOF119), le moteur
    ne rend que ``confirme: False`` ; l'argument est alors une chaîne VIDE, pas
    une phrase inventée.
    """
    sortie = dict(donnees)
    appro = dict(donnees.get('approvisionnement') or {})
    appro.setdefault('confirme', False)
    appro.setdefault('argument', '')
    sortie['approvisionnement'] = appro
    return sortie


def _valeurs_kits(parametres):
    kits = tuple(parametres.kits)
    return {'kit': kits[0].code if len(kits) == 1 else '',
            'granularite_kit': 'site'}


def _valeurs_rives(parametres):
    rives = parametres.rives
    return {
        'rive_laterale': rives.laterale_m,
        'rive_extremite': rives.extremite_m,
        'degagement_standard': parametres.degagement_defaut_m,
        'degagement_inconnu': parametres.degagement_nature_inconnue_m,
    }


def _valeurs_orientation(parametres):
    kits = tuple(parametres.kits)
    return {
        'sens_rangees': parametres.axe_rangee.value,
        'orientation_table': (kits[0].orientation.value if len(kits) == 1
                              else ''),
        # Le moteur n'a NI modèle de segmentation NI traitement du L : aucune
        # option n'est proposée, donc aucune n'est sélectionnée.
        'segmentation': '',
        'forme_l': '',
    }


def tiroirs_vers_json(donnees, parametres):
    """``DonneesTiroirs`` du moteur -> les 5 tiroirs du contrat.

    Chaque tiroir porte ``donnees`` (ce que le composant affiche) et
    ``valeurs`` (la sélection COURANTE à préremplir). ``valeurs`` est lu sur
    les ``Parametres`` réellement calculés — jamais recopié depuis la requête :
    un écran préremplirait alors ce que l'utilisateur a demandé plutôt que ce
    que le serveur a retenu.

    Le tiroir ÉLECTRIQUE ne sort PAS d'ici : il ne vient pas du moteur de
    calepinage mais de ``core.electrique`` (PV44), et l'appelant l'ajoute par
    ``tiroir_electrique_vers_json``.
    """
    if donnees is None:
        return tiroirs_vides()
    brut = donnees.vers_dict()
    sortie = tiroirs_vides()
    sortie['kits'] = {'donnees': _kits_vers_contrat(brut['kits']),
                      'valeurs': _valeurs_kits(parametres)}
    sortie['allees'] = {'donnees': brut['allees'],
                        'valeurs': {'allee_m': parametres.allee_m}}
    sortie['rives'] = {'donnees': _rives_vers_contrat(brut['rives']),
                       'valeurs': _valeurs_rives(parametres)}
    sortie['orientation'] = {'donnees': brut['orientation'],
                             'valeurs': _valeurs_orientation(parametres)}
    return sortie


# ────────────────────────────── PV44 — le tiroir ÉLECTRIQUE, pour de vrai ────
#
# Il sortait ``donnees: null`` parce qu'au moment où la lane AO l'a posé, aucun
# moteur électrique n'existait. ``core.electrique`` existe maintenant (PV33-39)
# et publie déjà la projection EXACTE que ``TiroirElectrique.jsx`` lit. Il ne
# reste donc qu'une traduction — et c'est ce module-ci qui traduit.
#
# CE QUE LE DOCUMENT AO SAIT, ET CE QU'IL NE SAIT PAS
# ---------------------------------------------------
# Un document de calepinage AO décrit une TOITURE et des TABLES : contour,
# obstacles, kits, puissance unitaire du module. Il ne décrit AUCUN appareil :
# ni la fiche du module vendu, ni l'onduleur retenu, ni la longueur des
# liaisons. Le moteur électrique, lui, a besoin des deux.
#
# La règle appliquée ici est celle du dépôt : **ce qu'on sait, on le calcule ;
# ce qu'on ne sait pas, on ne l'invente pas.**
#
# * SU : le nombre de modules, la puissance crête, le nombre d'onduleurs imposé
#   par le plafond de 60 kWc du dossier, la longueur de chaîne de dossier (16),
#   le reste hors chaîne. Tous CALCULÉS, tous publiés.
# * PAS SU : la puissance AC de l'onduleur retenu — c'est un fait d'achat, pas
#   une donnée de toiture. ``ac_kw`` reste donc à ZÉRO, et le moteur publie
#   lui-même « puissance AC de l'onduleur non renseignée — ratio DC/AC non
#   calculable, à vérifier avant dépôt du dossier » avec un ratio « — ». Un
#   ratio calculé sur un onduleur imaginaire serait pire que pas de ratio.
# * PAS SU NON PLUS : le nombre d'entrées MPPT et leur courant admissible.
#   ``i_max_mppt_a=0`` désactive la vérification côté moteur (c'est SON échappée
#   pour « non renseigné ») : sans elle, un « répartir les chaînes sur d'autres
#   entrées » serait publié à propos d'un onduleur que personne n'a choisi.
#
# Ce qui RESTE déclaré est l'ENVELOPPE physique commune à tous les onduleurs de
# chaîne 1100 V du marché — 1100 V absolus, plage MPPT 200-1000 V. Elle ne sert
# QU'À une chose : valider ou refuser la longueur de chaîne. C'est la borne dont
# le dépassement DÉTRUIT du matériel, et la refuser tôt vaut mieux que la
# découvrir en exécution.

#: Module de RÉFÉRENCE du dossier : les tensions d'un module cristallin
#: 144 demi-cellules du marché (celles de ``core/tests/test_electrique_golden``).
#: Elles bougent de quelques volts sur toute la famille 500-700 Wc — c'est la
#: raison pour laquelle on les tient FIXES et qu'on fait varier les COURANTS.
MODULE_REFERENCE_VMP_V = 41.5
MODULE_REFERENCE_VOC_V = 49.5
#: Rapport Isc/Imp de ce même module de référence (13,9 / 13,26). Il fixe le
#: courant de court-circuit à partir du courant au point de puissance maximale.
MODULE_REFERENCE_RAPPORT_ISC_IMP = 13.9 / 13.26

#: Longueurs de liaison RETENUES AU DOSSIER, faute de plan de câblage : 50 m de
#: DC (champ → local onduleur) et 20 m d'AC (onduleur → TGBT). Elles n'entrent
#: dans AUCUN chiffre du tiroir (qui ne montre que chaînes, onduleurs, ratio et
#: conformité) : elles ne servent qu'à ce que les étages câbles/protections du
#: moteur travaillent sur des longueurs plausibles plutôt que sur zéro.
LIAISON_DC_DEFAUT_M = 50.0
LIAISON_AC_DEFAUT_M = 20.0

#: Raccordement TRIPHASÉ par défaut : une centrale AO de plusieurs dizaines de
#: kWc n'existe pas en monophasé.
PHASES_DEFAUT = 3


def taille_chaine_du_preset(params):
    """La longueur de chaîne IMPOSÉE par l'utilisateur, ou ``None``.

    ``taille_chaine`` est le nom que porte déjà le champ de saisie de
    ``TiroirElectrique.jsx`` et le ``patch`` que le moteur électrique propose :
    le paramètre porte donc le MÊME nom d'un bout à l'autre, faute de quoi le
    bouton « appliquer la répartition conforme » enverrait une clé que le
    serveur ignorerait en silence.
    """
    brut = (params or {}).get('taille_chaine')
    if brut in (None, ''):
        return None
    try:
        valeur = int(brut)
    except (TypeError, ValueError):
        raise EntreeInvalide(
            "La longueur de chaîne « %r » n'est pas un nombre de modules."
            % (brut,)) from None
    if valeur <= 0:
        raise EntreeInvalide(
            'La longueur de chaîne doit être strictement positive '
            '(%d demandé).' % valeur)
    return valeur


def electrique_du_preset(params):
    """La section ÉLECTRIQUE du document — ``{}`` quand rien n'est imposé.

    OMISE du document quand elle est vide, exactement comme ``rangees_imposees``
    et ``phase_forcee_m`` (PV29/PV52) : l'empreinte d'un relevé que personne n'a
    touché ne doit pas bouger parce qu'une section vide s'est ajoutée.
    """
    taille = taille_chaine_du_preset(params)
    return {} if taille is None else {'taille_chaine': taille}


def module_de_reference(puissance_module_wc):
    """``SpecModule`` d'un module de ``puissance_module_wc`` Wc.

    Les TENSIONS sont celles du module de référence (elles ne bougent
    pratiquement pas sur la famille) ; les COURANTS sont déduits pour que
    ``Vmp × Imp`` redonne EXACTEMENT la puissance déclarée par le kit. La fiche
    ainsi construite est donc cohérente avec elle-même — jamais un assemblage de
    valeurs prises à trois modules différents.
    """
    from core.electrique.types import SpecModule

    pmax = float(puissance_module_wc or 0.0)
    imp = pmax / MODULE_REFERENCE_VMP_V if pmax > 0 else 0.0
    return SpecModule(
        vmp_v=MODULE_REFERENCE_VMP_V, voc_v=MODULE_REFERENCE_VOC_V,
        isc_a=imp * MODULE_REFERENCE_RAPPORT_ISC_IMP, imp_a=imp, pmax_wc=pmax)


def onduleur_de_reference():
    """L'ENVELOPPE d'un onduleur de chaîne 1100 V — sans son calibre AC.

    ``ac_kw=0`` et ``i_max_mppt_a=0`` ne sont pas des oublis : ce sont les deux
    valeurs que le moteur interprète comme « non renseigné » et qu'il rapporte
    lui-même, en français, au lieu de calculer sur une hypothèse.
    """
    from core.electrique.types import SpecOnduleur

    return SpecOnduleur(
        n_mppt=1, mppt_v_min=200.0, mppt_v_max=1000.0, v_max_abs=1100.0,
        i_max_mppt_a=0.0, ac_kw=0.0, phases=PHASES_DEFAUT)


def entree_electrique(pans, puissance_module_wc, taille_chaine=None):
    """``EntreeElectrique`` d'un calepinage — un GROUPE PAR PAN.

    Un pan par surface, jamais un groupe unique : deux orientations
    n'atteignent pas leur point de puissance maximale au même instant, et le
    moteur électrique refuse par principe de les mélanger sur une entrée MPPT.
    Sur une toiture à une seule surface, cela rend exactement un groupe.

    Le plafond de 60 kWc par onduleur vient de
    ``core.calepinage.electrique.PLAFOND_DC_PAR_ONDULEUR_KWC`` — la règle du
    dossier FRDISI, lue à sa source et jamais recopiée.
    """
    from core.calepinage.electrique import (
        MODULES_PAR_CHAINE, PLAFOND_DC_PAR_ONDULEUR_KWC,
    )
    from core.electrique.types import EntreeElectrique, GroupePan

    groupes = tuple(
        GroupePan(label=str(pan.get('label') or 'PAN'),
                  nb_modules=int(pan.get('nb_modules') or 0),
                  azimut_deg=float(pan.get('azimut_deg') or 180.0),
                  inclinaison_deg=float(pan.get('inclinaison_deg') or 0.0))
        for pan in (pans or ()) if int(pan.get('nb_modules') or 0) > 0)
    return EntreeElectrique(
        module=module_de_reference(puissance_module_wc),
        onduleur=onduleur_de_reference(),
        groupes=groupes,
        dc_m=LIAISON_DC_DEFAUT_M, ac_m=LIAISON_AC_DEFAUT_M,
        phases=PHASES_DEFAUT,
        plafond_kwc_par_onduleur=PLAFOND_DC_PAR_ONDULEUR_KWC,
        longueur_chaine_forcee=(MODULES_PAR_CHAINE if taille_chaine is None
                                else int(taille_chaine)))


#: Patch du moteur ÉLECTRIQUE -> clé du dict de PARAMÈTRES de l'API. Même
#: discipline que ``PATCH_MOTEUR_VERS_PARAMS`` (PV50) : une clé non cartographiée
#: fait TOMBER la proposition entière plutôt que de publier un bouton
#: « appliquer » que ``majParametres`` renverrait dans le vide.
PATCH_ELECTRIQUE_VERS_PARAMS = {
    'taille_chaine': 'taille_chaine',
}


def patch_electrique_vers_params(patch):
    """``patch`` du moteur électrique -> patch de PARAMÈTRES, ou ``None``."""
    if not patch:
        return None
    if not set(patch) <= set(PATCH_ELECTRIQUE_VERS_PARAMS):
        return None
    return {PATCH_ELECTRIQUE_VERS_PARAMS[cle]: valeur
            for cle, valeur in patch.items()}


def tiroir_electrique_vers_json(projection, taille_chaine):
    """La projection ``tiroirs['electrique']`` du moteur -> tiroir du contrat.

    La répartition proposée n'est publiée que si son patch est REJOUABLE par
    ``majParametres`` ; sinon elle est mise à ``null`` — honnêtement, plutôt
    qu'un bouton qui ne ferait rien.
    """
    if not projection:
        return {'donnees': None, 'valeurs': {}}
    donnees = {cle: dict(valeur) for cle, valeur in projection.items()}
    conformite = donnees.get('conformite') or {}
    proposee = conformite.get('repartition_proposee')
    if proposee:
        patch = patch_electrique_vers_params(proposee.get('patch'))
        conformite['repartition_proposee'] = (
            None if patch is None
            else {'texte': proposee.get('texte', ''), 'patch': patch})
    donnees['conformite'] = conformite
    return {'donnees': donnees, 'valeurs': {'taille_chaine': taille_chaine}}


# ─────────────────────────────────────────────────── suggestions (PV50)
#
# ``recommandations.proposer`` rend des ``Recommandation`` dont le
# ``patch_entree`` est écrit dans le vocabulaire du MOTEUR (``allee_m``,
# ``kits``, ``ecarter``…). L'écran, lui, ne sait appliquer que deux choses :
# un patch de PARAMÈTRES de calepinage (le dict que ``parametres_vers_document``
# relit) ou une décision sur un OBSTACLE (le champ ``provenance`` d'un
# ``ObstacleAO``). La traduction est donc EXPLICITE, clé par clé — et une clé
# non cartographiée fait TOMBER la suggestion entière plutôt que de publier un
# bouton « appliquer » qui n'appliquerait rien.

#: Patch MOTEUR -> clé du dict de PARAMÈTRES de l'API (vocabulaire du preset).
#: Seul ``allee_m`` change de nom : les autres portent déjà le même.
PATCH_MOTEUR_VERS_PARAMS = {
    'allee_m': 'allee_min_m',
    'rive_laterale_m': 'rive_laterale_m',
    'rive_extremite_m': 'rive_extremite_m',
    'axe_rangee': 'axe_rangee',
    'kits': 'kits_autorises',
}

#: Patch MOTEUR -> provenance AO visée. Le vocabulaire AO est le format
#: CANONIQUE (cf. ``PROVENANCE_VERS_MOTEUR``) : le moteur nomme ``RELEVE`` ce
#: que l'AO nomme ``MESURE``, et c'est la valeur AO qui doit voyager, puisque
#: c'est elle que l'écran écrira sur ``ObstacleAO.provenance``.
PATCH_MOTEUR_VERS_OBSTACLE = {
    'ecarter': 'ECARTE',
    'confirmer': 'MESURE',
}


def _valeur_de_patch(cle, valeur):
    """Convertit la valeur d'un patch (le moteur les écrit en CHAÎNES)."""
    if cle in ('allee_m', 'rive_laterale_m', 'rive_extremite_m'):
        return float(valeur)
    if cle == 'kits':
        return [code for code in str(valeur).split('+') if code]
    return str(valeur)


def action_de_patch(patch_entree):
    """``patch_entree`` du moteur -> ``action`` DISCRIMINÉE, ou ``None``.

    Deux familles, jamais mélangées dans la même action : un patch qui
    toucherait à la fois un paramètre et un obstacle n'aurait aucun bouton
    capable de l'appliquer d'un clic. ``None`` = suggestion à JETER.
    """
    patch = list(patch_entree or ())
    if not patch:
        return None
    cles = {cle for cle, _valeur in patch}
    if not cles <= (set(PATCH_MOTEUR_VERS_PARAMS)
                    | set(PATCH_MOTEUR_VERS_OBSTACLE)):
        # Clé de patch inconnue de cette table : le moteur a gagné un levier
        # que l'écran ne sait pas appliquer. On JETTE la suggestion — publier
        # un bouton qui n'applique rien est pire que ne rien proposer.
        return None
    if cles <= set(PATCH_MOTEUR_VERS_OBSTACLE):
        if len(patch) != 1:
            return None  # deux décisions d'obstacle = deux suggestions
        cle, repere = patch[0]
        return {'type': 'obstacle', 'obstacle': str(repere),
                'provenance': PATCH_MOTEUR_VERS_OBSTACLE[cle]}
    if cles <= set(PATCH_MOTEUR_VERS_PARAMS):
        return {'type': 'parametres',
                'patch': {PATCH_MOTEUR_VERS_PARAMS[cle]:
                          _valeur_de_patch(cle, valeur)
                          for cle, valeur in patch}}
    return None  # patch MIXTE paramètres + obstacle : inapplicable en un clic


def suggestion_vers_json(recommandation):
    """Une ``Recommandation`` du moteur -> une suggestion du contrat.

    Rend ``None`` quand l'action n'est pas traduisible (cf. ``action_de_patch``).

    ``gain_modules`` est SIGNÉ : un arbitrage d'obstacle peut coûter des
    modules, et le publier positif ferait passer une perte assumée pour un
    gain. ``gain_kwc``, ``confiance`` et ``question_a_poser`` sont déclarés
    FACULTATIFS par le contrat ; le moteur les CALCULE pour toutes ses
    propositions, alors on ne les jette pas.
    """
    action = action_de_patch(recommandation.patch_entree)
    if action is None:
        return None
    return {
        'code': recommandation.code,
        'titre': recommandation.titre,
        'gain_modules': int(recommandation.gain_modules),
        'gain_kwc': round(float(recommandation.gain_kwc), 3),
        'confiance': recommandation.confiance.value,
        'question_a_poser': recommandation.question_a_poser,
        'action': action,
    }


def suggestions_vers_json(recommandations):
    """La liste des suggestions traduisibles, dans l'ordre reçu."""
    sortie = []
    for recommandation in recommandations or ():
        suggestion = suggestion_vers_json(recommandation)
        if suggestion is not None:
            sortie.append(suggestion)
    return sortie


def resultat_vers_json(*, repere, hash_entree, modules, kwc, plans,
                       engageable=True, motifs_non_engageable=()):
    """Le RÉSULTAT persistable d'AOF28 : rangées explicites + tables + totaux.

    **Sur la clé ``x0``.** Le contrat d'AOF28 nomme ``x0`` la position d'une
    rangée ; le moteur, dans son repère unifié, la nomme ``y0`` (``x`` court le
    long de la rangée, ``y`` en travers). Les deux clés sont émises avec la
    MÊME valeur — elles ne peuvent donc pas diverger — pour honorer le contrat
    déjà publié sans inscrire un axe faux dans la donnée.
    """
    return {
        'repere': repere,
        'hash_entree': hash_entree,
        'version_moteur': VERSION_MOTEUR,
        'schema_version': SCHEMA_VERSION,
        'total_modules': int(modules),
        'kwc': round(float(kwc), 3),
        'engageable': bool(engageable),
        'motifs_non_engageable': list(motifs_non_engageable),
        'plans': list(plans),
        'rangees': [rangee for plan in plans for rangee in plan['rangees']],
    }


def plan_vers_json(surface_repere, resultat_optimum, tables=()):
    """Un plan de pose (une surface) : rangées explicites + tables posées."""
    rangees = []
    for rangee in resultat_optimum.plan.rangees:
        rangees.append({
            'surface': surface_repere,
            # même valeur sous les deux noms — voir ``resultat_vers_json``
            'x0': round(rangee.y0, 4),
            'y0': round(rangee.y0, 4),
            'kit': rangee.kit_code,
            'modules': int(rangee.modules),
            'emprise_m': round(rangee.emprise_m, 4),
            'troncons': [[round(a, 4), round(b, 4)]
                         for a, b in rangee.troncons],
        })
    return {
        'surface': surface_repere,
        'modules': int(resultat_optimum.plan.modules),
        'ecart_a_l_optimum': int(resultat_optimum.ecart_a_l_optimum),
        'rangees': rangees,
        'tables': [{'x0': round(t.x0, 4), 'x1': round(t.x1, 4),
                    'y0': round(t.y0, 4), 'y1': round(t.y1, 4),
                    'kit': t.kit_code}
                   for t in tables],
    }
