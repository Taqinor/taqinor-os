"""Sélecteurs LECTURE SEULE du calepinage et de la conception 3D du devis
(contexte de conception, calepinage et schéma unifilaire du devis, péremption
du layout, comparaison calepinage/devis) — sortis de
``apps/ventes/selectors.py`` par SPL144 (déplacement pur, corps inchangés ;
propriétaire : calepinage).

Les autres apps continuent de lire ces fonctions par la FAÇADE
``apps.ventes.selectors`` (ré-export en fin de fichier) ; ce module est PLAT :
aucun import de ``.selectors`` en tête (cycle).
"""


def conception_pour_lead(lead, company):
    """PV78 — la conception 3D la plus RÉCENTE d'un lead, en lecture seule.

    Rend TOUJOURS le même dict ``{kwc, image_url}`` — jamais une clé absente,
    jamais un ``None`` global : une fiche lead sans conception affiche deux
    valeurs vides, elle ne plante pas sur ``undefined``.

    * ``kwc`` — la puissance crête RÉELLEMENT calepinée, lue dans le layout du
      devis (``roof_layout['result']['kwc']``), à défaut la puissance de
      l'étude. C'est le chiffre de la TOITURE, pas une cible commerciale ;
    * ``image_url`` — URL PRÉ-SIGNÉE (lecture seule, expirante) du rendu 3D
      stocké, via le helper existant ``utils.pdf.roof_image_signed_url``.
      Jamais une URL de bucket publique.

    Company-scopée : seul un devis de ``company`` est regardé (un lead d'une
    autre société ne fait rien fuiter). Point d'entrée cross-app pour
    ``apps.crm`` — jamais un import des modèles ventes de son côté.
    """
    vide = {'kwc': None, 'image_url': None}
    lead_id = getattr(lead, 'pk', None) or getattr(lead, 'id', None)
    if not lead_id or company is None:
        return vide
    from .models import Devis
    devis = (Devis.objects
             .filter(lead_id=lead_id, company=company,
                     roof_layout__isnull=False)
             .order_by('-date_creation', '-id')
             .first())
    if devis is None:
        return vide

    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else {}
    resultat = layout.get('result') if isinstance(layout, dict) else None
    kwc = (resultat or {}).get('kwc') if isinstance(resultat, dict) else None
    if kwc in (None, ''):
        kwc = (devis.etude_params or {}).get('puissance_kwc')
    try:
        kwc = float(kwc) if kwc not in (None, '') else None
    except (TypeError, ValueError):
        kwc = None

    image_url = None
    if devis.roof_image:
        try:
            from .utils.pdf import roof_image_signed_url
            image_url = roof_image_signed_url(devis.roof_image)
        except Exception:  # noqa: BLE001 — un rendu absent ne casse pas la fiche
            image_url = None
    return {'kwc': kwc, 'image_url': image_url}


def calepinage_du_devis(devis, company=None):
    """CAL28 — le calepinage qui PILOTE ce devis, ou ``None``.

    Le lien inverse n'existait pas : la fiche devis ne savait pas qu'un
    calepinage la pilote, alors que c'est lui qui porte les versions, les
    variantes et la planche. Cette fonction est le pont — MINCE, en lecture
    seule, et passant par ``apps.calepinage.selectors`` (import FONCTION-LOCAL
    pour éviter le cycle au chargement) : ``ventes`` n'importe JAMAIS
    ``apps.calepinage.models``.

    ``a_jour`` est une COMPARAISON DES DEUX EMPREINTES, jamais un recalcul de
    géométrie : le devis et son calepinage portent la même empreinte tant que
    la conception n'a pas divergé. Empreinte manquante d'un côté ⇒ ``None``
    (inconnu), jamais ``False`` — on ne déclare pas « périmé » ce qu'on n'a pas
    mesuré.
    """
    from apps.calepinage.selectors import calepinage_du_devis as _lire

    if devis is None:
        return None
    company = company or getattr(devis, 'company', None)
    calepinage = _lire(getattr(devis, 'pk', None), company)
    if calepinage is None:
        return None
    empreinte_devis = getattr(devis, 'layout_hash', '') or ''
    empreinte_cal = calepinage.layout_hash or ''
    return {
        'id': calepinage.pk,
        'titre': calepinage.titre or '',
        'layout_hash': empreinte_cal or None,
        'a_jour': (empreinte_devis == empreinte_cal
                   if empreinte_devis and empreinte_cal else None),
    }


def schema_unifilaire_svg(*, devis=None, entree=None, resultat=None,
                          cartouche=None, standard=False):
    """CAL195 — LE producteur de schéma unifilaire, par SA porte cross-app.

    Le schéma existe depuis PV46, mais il était enfermé : il part d'un DEVIS,
    et le seul chemin vers lui traverse le moteur vendorisé
    (``quote_engine.builder._sld_svg``). Or ce moteur REND — il ne s'importe
    pas (règle #4), et aucune autre app n'a le droit d'atteindre un de ses
    modules internes. Un calepinage sans devis n'avait donc aucun schéma, alors
    que le dessin lui-même est produit par un module PUR
    (``core.electrique.schema``) qui ne connaît ni devis, ni prix, ni statut.

    Cette fonction est la porte, et elle ne DESSINE rien :

    * ``devis=`` — délégation stricte à ``electrical_service.
      rendre_schema_du_devis``, l'appel que ``_sld_svg`` fait déjà. Le SVG
      d'un devis reste donc BYTE-IDENTIQUE : aucun paramètre n'est ajouté,
      aucun repli n'est introduit, et les trois portails (étude présente,
      fiches complètes, conception conforme) restent les siens.
    * ``entree=``/``resultat=`` — un appelant qui porte DÉJÀ les objets du
      moteur électrique (``core.electrique.types``) : c'est le cas d'
      ``apps.calepinage``, dont la ``Conception`` (CAL124) est bâtie sur ces
      mêmes types, chaînes par MPPT (CAL125), câbles dimensionnés (CAL131) et
      check-list d'organes (CAL132) comprises. Le dessin est alors celui du
      MÊME moteur, jamais une seconde planche.

    ``None`` dès qu'il manque de quoi dessiner — même discipline que
    PVFCH-ANNEXE : une fiche incomplète n'obtient PAS un schéma approximatif,
    elle n'en obtient aucun.
    """
    if devis is not None:
        from .electrical_service import rendre_schema_du_devis
        return rendre_schema_du_devis(devis, standard=standard)
    if entree is None or resultat is None:
        return None
    from core.electrique.schema import rendre_schema
    return rendre_schema(entree, resultat, cartouche=cartouche or {},
                         standard=standard)


def lignes_produits_calepinage(devis):
    """CAL243 — les lignes PRODUIT « retenues » d'un devis, pour l'équipement
    d'un calepinage lié.

    Point d'entrée cross-app LECTURE SEULE (``apps.calepinage`` n'importe
    JAMAIS ``apps.ventes.models``) : un objet léger par ligne
    (``produit``, ``designation``, ``quantite``), jamais le modèle
    ``LigneDevis`` lui-même. Ne rend que les lignes de type ``'produit'``
    dont le produit est renseigné, et EXCLUT la variante ``'avec'`` (option
    « avec batterie ») : la disposition retient l'équipement de l'option PAR
    DÉFAUT (commune + « sans »), jamais un mélange des deux options d'un
    devis « Les deux ». Devis ``None`` -> liste vide.
    """
    if devis is None:
        return []
    return [
        {'produit': ligne.produit, 'designation': ligne.designation,
         'quantite': ligne.quantite}
        for ligne in (devis.lignes
                      .filter(type_ligne='produit', produit_id__isnull=False)
                      .exclude(variante='avec')
                      .select_related('produit')
                      .order_by('id'))
    ]


def peremption_layout_devis(devis):
    """CAL189 — ``{layout_stale, layout_nb_panneaux}`` d'un devis.

    LE MÊME CALCUL QUE LA PAGE PUBLIQUE, pas un second. ``layout_stale``
    n'était publié que dans la charge utile de la proposition
    (``public_views.py`` ← ``quote_engine/builder.py``) : l'API interne ne
    l'exposait nulle part, donc l'écran ERP ne pouvait pas dire au commercial
    que sa 3D ne décrit plus ce que le devis vend. Le compte de modules du
    layout est lu par le HELPER du moteur PDF (``_panneaux_du_layout``), et les
    comptes des LIGNES par les mêmes primitives que le reste du domaine.

    Un document à DEUX OPTIONS a DEUX comptes valides (LAYSTALE) : le
    calepinage n'est périmé que s'il ne correspond à AUCUNE des deux — sinon on
    afficherait au client un avertissement FAUX.

    ``layout_stale`` vaut ``False`` quand le devis ne porte AUCUNE ligne de
    panneau : il n'y a alors rien à comparer, et un « périmé » là-dessus serait
    une alerte inventée.
    """
    from apps.ventes.dimensionnement import _lignes_produit_du_devis
    from apps.ventes.quote_engine.builder import _panneaux_du_layout
    from apps.ventes.services import _is_panel

    if devis is None:
        return {'layout_stale': None, 'layout_nb_panneaux': None}
    layout_nb_panneaux = _panneaux_du_layout(
        getattr(devis, 'roof_layout', None))

    comptes = {}
    for ligne in _lignes_produit_du_devis(devis):
        if not _is_panel(getattr(ligne, 'designation', '') or ''):
            continue
        variante = (getattr(ligne, 'variante', '') or '')
        cle = 'avec' if variante == 'avec' else 'sans'
        try:
            quantite = int(float(getattr(ligne, 'quantite', 0) or 0))
        except (TypeError, ValueError):
            continue
        comptes[cle] = comptes.get(cle, 0) + quantite
        if variante == '':
            # Une ligne COMMUNE compte dans les deux options.
            comptes['avec'] = comptes.get('avec', 0) + quantite
    valides = {n for n in comptes.values() if n}
    return {
        'layout_stale': bool(layout_nb_panneaux and valides
                             and layout_nb_panneaux not in valides),
        'layout_nb_panneaux': layout_nb_panneaux,
    }


def devis_brouillon_pour_layout(company, lead_id, empreinte):
    """CAL24 — le BROUILLON déjà né de ce calepinage, ou ``None``.

    C'est la dédup de QJ17 (``lead`` + ``layout_hash``), rendue lisible aux
    autres apps : re-cliquer « Générer le devis » doit redonner le brouillon
    EXISTANT, jamais un doublon. Elle vivait inline dans la vue ``from-layout``
    de ventes ; tout autre créateur (le module Calepinage) l'aurait recopiée,
    donc fait dériver.

    Scopée société, et seulement les BROUILLONS : un devis déjà envoyé ne se
    « réutilise » pas — il se révise.

    ACAL88 (C-ACAL-104) — et seulement les brouillons ACTIFS : un brouillon
    archivé (``is_active=False``, QJR661) n'est plus jamais rendu.
    """
    from .models import Devis

    if company is None or not lead_id or not empreinte:
        return None
    return (Devis.objects
            .filter(company=company, lead_id=lead_id, is_active=True,
                    statut=Devis.Statut.BROUILLON, layout_hash=empreinte)
            .order_by('-date_creation')
            .first())


# ── AOF164 — comparaison A/B du calepinage d'un devis (LECTURE SEULE) ───────
#
# C'est le SEUL endroit qui confronte le compte d'un devis EXISTANT au compte
# du moteur. Il ne récrit rien : ni les lignes, ni ``etude_params``, ni
# ``layout_hash``. **Un devis déjà émis ne doit jamais voir son compte bouger
# rétroactivement** — un client qui a reçu « 24 panneaux » a reçu 24 panneaux,
# quelle que soit l'opinion ultérieure du moteur. La fonction refuse donc
# explicitement tout devis hors ``brouillon``, avec un motif en français.

#: Le seul statut dont le compte est encore malléable.
STATUT_RECALCULABLE = 'brouillon'


def comparaison_calepinage_devis(devis):
    """Compare le compte STOCKÉ du devis au compte du moteur — sans rien écrire.

    Rend un dict ``{'recalculable', 'motif', 'compte_stocke', 'compte_moteur',
    'ecart'}``. ``recalculable`` est ``False`` dès que le devis a quitté le
    brouillon : la comparaison reste LISIBLE (elle informe l'arbitrage), mais
    aucun appelant n'a le droit de l'appliquer.
    """
    from .services import _is_panel, compte_moteur_du_layout

    if devis is None:
        return None
    statut = getattr(devis, 'statut', '')
    stocke = 0
    for ligne in devis.lignes.all():
        if _is_panel(ligne.designation):
            stocke += int(ligne.quantite or 0)

    if statut != STATUT_RECALCULABLE:
        return {
            'recalculable': False,
            'motif': ("Devis %s au statut « %s » : un devis déjà émis n'est "
                      'jamais recalculé.'
                      % (devis.reference, devis.get_statut_display())),
            'compte_stocke': stocke,
            'compte_moteur': None,
            'ecart': None,
        }

    # PV42 — le moteur calepine sur le PANNEAU du devis (kit-produit, PV12) :
    # sans lui, cette comparaison opposerait un compte posé sur le module vendu
    # à un compte posé sur le kit générique — un écart inventé de toutes pièces.
    mesure = compte_moteur_du_layout(
        devis.roof_layout, company=getattr(devis, 'company', None),
        devis=devis)
    if mesure is None:
        return {
            'recalculable': True,
            'motif': ('Aucune géométrie exploitable : le moteur ne se '
                      'prononce pas sur ce devis.'),
            'compte_stocke': stocke,
            'compte_moteur': None,
            'ecart': None,
        }
    return {
        'recalculable': True,
        'motif': '',
        'compte_stocke': stocke,
        'compte_moteur': int(mesure['modules']),
        'ecart': int(mesure['modules']) - stocke,
    }


# ── PV17 — contexte COMPLET de l'écran de conception 3D d'un devis ──────────
#
# UN SEUL appel, UN SEUL dict, TOUTES les clés TOUJOURS présentes (contrat
# ``apps/ventes/contract_samples/devis_design_context.json``). L'écran ne doit
# jamais avoir à deviner : une clé absente, c'est un ``.map()`` sur
# ``undefined`` en production — l'incident exact que ``check_api_shapes.py``
# garde. Un panier vide vaut ``[]``, une valeur inconnue vaut ``None`` ou
# ``''``, jamais une clé manquante.
#
# LECTURE PURE : aucun statut, aucune ligne, aucun layout n'est écrit ici.


def _config_carte():
    """Clés carte du builder 3D — MIROIR de ``views/roof_config.py``.

    Mêmes variables d'environnement (``PUBLIC_MAPTILER_KEY`` /
    ``PUBLIC_MAPBOX_TOKEN``), même forme ``{available, maptilerKey,
    mapboxToken}`` : l'écran de conception lit la carte DANS le contexte plutôt
    que d'enchaîner un second appel. Aucune donnée société, aucune écriture.
    """
    import os

    maptiler = os.environ.get('PUBLIC_MAPTILER_KEY', '') or ''
    mapbox = os.environ.get('PUBLIC_MAPBOX_TOKEN', '') or ''
    return {
        'available': bool(maptiler),
        'maptilerKey': maptiler,
        'mapboxToken': mapbox or None,
    }


#: CALX104/CALX403 — les sections de réglages société que l'atelier 3D lit
#: (option de boot ``reglagesAtelier``). Les NOMS sont ceux de
#: ``apps.calepinage.selectors.SECTIONS_PARAMETRES`` : l'atelier les consomme
#: sans traduction de clé, donc on ne les renomme pas au passage.
SECTIONS_ATELIER_3D = ('zones_types', 'degagements')


def _reglages_atelier(company):
    """CALX104/CALX403 — les deux sections de réglages que l'atelier 3D lit.

    ``zones_types`` porte les gabarits d'obstacle saisis par la société,
    ``degagements`` le retrait de rive et la largeur d'allée. L'écran de
    conception en mode DEVIS tient une garantie testée — « un seul appel :
    rien n'est complété par une requête annexe » — donc ces deux sections
    voyagent DANS le contexte agrégé plutôt que par une seconde porte.

    FRONTIÈRE INTER-APPS : la lecture passe par le selector de l'app
    propriétaire (``apps.calepinage.selectors``), jamais par ses modèles.

    ÉQUIVALENCE : une société qui n'a rien réglé reçoit ``{}`` pour chacune —
    donc aucun gabarit proposé, aucune largeur préremplie, l'atelier
    d'aujourd'hui exactement. Rien n'est inventé ici.
    """
    from apps.calepinage.selectors import parametres_de_societe

    reglages = parametres_de_societe(company) or {}
    return {section: (reglages.get(section) or {})
            for section in SECTIONS_ATELIER_3D}


def devis_concevables(qs):
    """QJR636 — les devis de ``qs`` dont la toiture se calepine encore.

    La règle de statut est LUE dans la table de ``domain/modifiabilite``
    (geste CALEPINAGE, devis actif) — jamais recopiée ici ; s'y ajoutent les
    deux exclusions propres à l'écran 3D : un devis agricole (pompage) et un
    devis multi-villa (une ligne ``groupe_index >= 1``). Ne borne pas la
    société : l'appelant passe un queryset déjà scopé. Présence ici ⇔
    ``contexte_conception_devis(...)['modifiable']``.
    """
    from django.db.models import Exists, OuterRef

    from .domain.modifiabilite import CALEPINAGE, GESTES
    from .models import Devis, LigneDevis
    return (qs.filter(is_active=True, statut__in=GESTES[CALEPINAGE])
            .exclude(mode_installation=Devis.ModeInstallation.AGRICOLE)
            .exclude(Exists(LigneDevis.objects.filter(
                devis=OuterRef('pk'), groupe_index__gte=1))))


def contexte_conception_devis(devis, company):
    """PV17 — tout ce que l'écran de conception toiture doit savoir d'un devis.

    Rend ``None`` quand le devis appartient à une AUTRE société (l'appelant
    répond alors 404 — jamais d'oracle d'existence). Sinon un dict à la forme
    FIXE :

        {devis: {id, reference, statut, mode_installation, lead, client,
                 client_nom},
         geometrie: {source, roof_layout, pin, outline, contour_client},
         cible: {panneaux, kwc, panel_watt, scenario, batterie,
                 avertissements, bill_kwh},
         carte: {available, maptilerKey, mapboxToken},
         modifiable, raison_lecture_seule, avertissements}

    L-MAP (fondateur 26/08/2026 : « i want it visible on the map in the 3D
    layouter ») — ``geometrie.contour_client`` porte TOUJOURS le contour
    ORIGINAL dessiné par le client sur le tunnel public (``Lead.roof_outline``,
    tel quel, jamais recalculé), À PART de ``outline`` qui peut déjà être le
    contour COURANT du calepinage une fois le devis édité (``layout.get
    ('outline')``). Sans ce champ distinct, un devis déjà calepiné perdait
    toute trace de ce que le client avait réellement tracé. Liste vide (jamais
    ``None``) sans lead ou sans contour posé.

    CTX3D (25/08/2026) — ``cible`` décrit L'OPTION 1 (« sans batterie »), celle
    que l'écran dessine par défaut : son compte de panneaux ET son scénario
    viennent maintenant du MÊME sous-ensemble de lignes (avant, le scénario
    était lu sur tout le devis et pouvait annoncer « avec_batterie » au-dessus
    d'un compte de panneaux « sans »).

    UNE CLÉ SŒUR OPTIONNELLE, ``cible_avec`` (même forme que ``cible``, ses six
    clés PV16 — sans ``bill_kwh``, la consommation du client étant unique et
    déjà portée par ``cible``), décrit L'OPTION 2 d'un devis qui la sert
    réellement. Elle n'est présente QUE si les lignes peuvent livrer l'option
    « Avec batterie » — onduleur hybride ET batterie, le MÊME critère
    ``avec_ok`` que le moteur PDF, ``variantes_servables`` et
    ``dimensionnement_options`` (``services.option_avec_servable``) — et ABSENTE
    sinon : jamais une option que ce devis ne peut pas livrer. Un écran qui ne
    la lit pas est strictement inchangé (clé purement additive).

    ``geometrie.source`` vaut ``'devis'`` (le devis porte déjà un layout 3D),
    ``'lead'`` (repli sur l'épingle/le contour posés au diagnostic) ou
    ``'none'``. ``modifiable`` est faux — avec une raison FRANÇAISE dans
    ``raison_lecture_seule`` — pour un devis sorti du cycle d'édition
    (accepté/refusé/expiré), un devis agricole (pompage) et un devis
    multi-villa. ``raison_lecture_seule`` vaut ``''`` quand le devis est
    modifiable, jamais ``None``.
    """
    from .models import Devis
    from .services import cible_depuis_lignes, option_avec_servable

    if devis is None:
        return None
    # Garde société DÉFENSIVE (le queryset de l'appelant borne déjà) : un
    # superutilisateur sans société passe outre, comme partout ailleurs.
    company_id = getattr(company, 'id', None)
    if company_id is not None and devis.company_id != company_id:
        return None

    lead = getattr(devis, 'lead', None)
    # O4 (revue adversariale 26/08/2026, défense en profondeur) — un
    # `devis.lead` ne devrait JAMAIS appartenir à une AUTRE société que le
    # devis lui-même (la garde ci-dessus ne borne que `devis.company_id`),
    # mais si cet invariant était un jour rompu (bug ailleurs, migration de
    # données), aucun champ du lead (contour, GPS, téléphone, adresse…) ne
    # doit fuiter par cet endpoint : on le traite comme absent, exactement
    # le repli déjà utilisé partout ci-dessous (`if lead else None`).
    if lead is not None and company_id is not None \
            and getattr(lead, 'company_id', None) != company_id:
        lead = None

    # L-MAP (fondateur 26/08/2026) — le contour ORIGINAL du client, capturé
    # UNE FOIS pour toutes ici, AVANT toute logique de layout : `outline`
    # ci-dessous peut déjà être le contour COURANT du calepinage (celui du
    # layout, potentiellement édité par le commercial) ; `contour_client` ne
    # bouge JAMAIS avec lui. La validation (>= 3 sommets exploitables) est
    # déjà l'affaire de `traceToit.js` côté écran (MÊME fonction que la fiche
    # lead, PR #568) — on ne la refait pas ici, on transmet tel quel.
    contour_lead_brut = getattr(lead, 'roof_outline', None) if lead else None
    contour_client = contour_lead_brut if isinstance(contour_lead_brut, list) else []

    # ── Cible : ce que le devis DIT aujourd'hui (PV16) + la conso du lead ──
    cible = cible_depuis_lignes(devis)
    bill_kwh = getattr(lead, 'bill_kwh', None) if lead is not None else None
    try:
        cible['bill_kwh'] = float(bill_kwh) if bill_kwh is not None else None
    except (TypeError, ValueError):
        cible['bill_kwh'] = None

    # CTX3D — L'OPTION 2, quand ce devis la sert VRAIMENT. Sur un devis « Les
    # deux » les deux options n'ont ni le même champ ni le même scénario : la
    # cible seule ne pouvait en décrire qu'une, et l'écran n'avait aucun moyen
    # de savoir que l'autre existait. Critère = celui du moteur PDF (onduleur
    # hybride ET batterie dans le panier « avec »), jamais une option inventée.
    cible_avec = (cible_depuis_lignes(devis, variante='avec')
                  if option_avec_servable(devis) else None)

    # ── Géométrie : le layout du devis PRIME sur le repère du lead ──
    # QJR598 — LE repère toit du lead (crm.selectors.repere_toit) : le GPS
    # corrigé prime sur l'épingle du tunnel, sinon l'épingle, sinon le GPS.
    from apps.crm.selectors import repere_toit
    pin_lead = repere_toit(lead)[0] if lead is not None else None
    layout = devis.roof_layout if isinstance(devis.roof_layout, dict) else None
    if layout:
        source = 'devis'
        roof_layout = layout
        pin_brut = layout.get('pin')
        contour = layout.get('outline')
        pin = pin_brut if isinstance(pin_brut, dict) else None
        outline = contour if isinstance(contour, list) else []
        # ── AUTO-PIPELINE (ordre fondateur 26/08/2026) — LE TRACÉ DU CLIENT
        # NE DOIT JAMAIS SE PERDRE DERRIÈRE UN LAYOUT SANS GÉOMÉTRIE ──────────
        # Un devis peut porter un `roof_layout` qui ne décrit AUCUNE géométrie :
        # c'est le cas de tout devis AUTOMATIQUE d'avant ce lot (le layout de
        # `build_devis_auto` ne portait que `result`/`panelWatt`/`scenario`).
        # `outline` valait alors `[]` et `zones` était absent : côté écran,
        # `hydrateFromDevis` ne trouvait ni zone ni contour, retombait sur
        # l'épingle seule, et le commercial devait RE-DESSINER le toit pour voir
        # un seul panneau — alors que le tracé du client était là, juste à côté,
        # dessiné en calque passif (`contour_client`). C'était LA cause du
        # « le calepinage ne se fait pas tout seul ».
        #
        # Repli STRICTEMENT non destructif : il ne s'applique que si le layout
        # ne dit RIEN de la géométrie (ni `outline` exploitable, ni `zones`) —
        # un devis déjà calepiné garde son dessin, intact, en toutes
        # circonstances. Le contour rendu reste celui du CLIENT (`contour_client`,
        # `Lead.roof_outline` tel quel), jamais une géométrie inventée.
        if not outline and not (layout.get('zones') or layout.get('areas')):
            outline = contour_client
    else:
        roof_layout = None
        pin = pin_lead
        outline = contour_client
        source = 'lead' if (pin or outline) else 'none'
    # Un layout sans épingle centre quand même la carte sur le repère du lead
    # (n'écrit rien nulle part ; jamais une valeur inventée).
    if pin is None and pin_lead is not None:
        pin = pin_lead
        if source == 'none':
            source = 'lead'

    # ── Modifiable ? Trois raisons de LECTURE SEULE, toutes en français ──
    # QJR636 — UNE règle (devis_concevables, qui lit le geste CALEPINAGE de
    # la table de modifiabilité) ; les branches ci-dessous ne font que NOMMER
    # la raison d'un refus.
    from .domain.modifiabilite import CALEPINAGE, verdict as _verdict
    concevable = devis_concevables(
        Devis.objects.filter(pk=devis.pk)).exists()
    if concevable:
        raison = ''
    elif not _verdict(devis, CALEPINAGE)['modifiable']:
        raison = (
            'Devis « %s » : le calepinage n\'est plus modifiable. Utilisez '
            '« Réviser » pour en créer une nouvelle version.'
            % devis.get_statut_display())
    elif devis.mode_installation == Devis.ModeInstallation.AGRICOLE:
        raison = ('Devis agricole (pompage) — le calepinage de toiture ne '
                  's\'applique pas.')
    else:
        raison = ('Devis multi-villa : chaque villa porte son propre '
                  'calepinage — cet écran ne peut pas en modifier une seule.')

    avertissements = list(cible['avertissements'])
    if source == 'none':
        avertissements.append(
            'Aucune géométrie de toiture connue pour ce devis : commencez par '
            'situer le bâtiment sur la carte.')

    client = getattr(devis, 'client', None)
    # PV23bis (fondateur 20/08/2026 : « link this 3D layouter to the quote »)
    # — l'outil 3D doit connaître le CLIENT du devis, pas seulement son nom :
    # téléphone, ville et adresse alimentent le formulaire du builder
    # (`hydrateFromDevis` sait déjà les lire) et le centrage de la carte quand
    # aucune géométrie n'existe. Client d'abord, repli sur le lead (même
    # priorité whatsapp > téléphone que le mode lead de l'écran) ; vide quand
    # personne ne le sait — jamais une valeur inventée.
    telephone = (getattr(client, 'telephone', '') or '').strip() if client else ''
    adresse = (getattr(client, 'adresse', '') or '').strip() if client else ''
    ville = ''  # crm.Client ne porte pas de ville — elle vient du lead.
    if lead is not None:
        telephone = telephone or (getattr(lead, 'whatsapp', '') or '').strip() \
            or (getattr(lead, 'telephone', '') or '').strip()
        adresse = adresse or (getattr(lead, 'adresse', '') or '').strip()
        ville = (getattr(lead, 'ville', '') or '').strip()
    contexte = {
        'devis': {
            'id': devis.pk,
            'reference': devis.reference,
            'statut': devis.statut,
            'mode_installation': devis.mode_installation or '',
            'lead': devis.lead_id,
            'client': devis.client_id,
            'client_nom': (getattr(client, 'nom', '') or '') if client else '',
            'client_telephone': telephone,
            'client_ville': ville,
            'client_adresse': adresse,
        },
        'geometrie': {
            'source': source,
            'roof_layout': roof_layout,
            'pin': pin,
            'outline': outline,
            'contour_client': contour_client,
        },
        'cible': cible,
        'carte': _config_carte(),
        'modifiable': not raison,
        'raison_lecture_seule': raison,
        'avertissements': avertissements,
        # CALX104/CALX403 câblage — les DEUX sections de réglages société que
        # l'atelier 3D consomme (`reglagesAtelier`) : les gabarits d'obstacle
        # (`zones_types`) et la largeur d'allée / le retrait de rive
        # (`degagements`). Les modes lead et calepinage les lisent sur
        # ``GET /api/django/calepinage/parametres/`` ; le mode DEVIS, lui, tient
        # la garantie testée « un seul appel : rien n'est complété par une
        # requête annexe », donc elles voyagent ICI.
        #
        # Servies TELLES QUELLES, par le selector de l'app propriétaire (jamais
        # ses modèles — frontière cross-app). ÉQUIVALENCE : une société qui n'a
        # rien réglé reçoit ``{}`` pour chacune, donc aucun gabarit proposé et
        # aucune largeur préremplie : l'atelier d'aujourd'hui exactement.
        **_reglages_atelier(company),
    }
    # CTX3D — clé OPTIONNELLE : présente seulement quand l'option 2 est
    # réellement servable. Absente (et non ``None``) sinon : un écran qui teste
    # sa présence sait alors qu'il n'y a rien à proposer, sans avoir à
    # distinguer « pas d'option » de « option vide ».
    if cible_avec is not None:
        contexte['cible_avec'] = cible_avec
    return contexte
