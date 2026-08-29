"""Services Ventes — point d'entrée cross-app pour les ÉCRITURES ventes.

Les apps tierces (sav, installations, crm…) passent par ces fonctions pour
créer ou modifier des entités ventes (Facture, Paiement…) au lieu d'importer
directement les models ventes. Cela respecte la règle de modularité (CLAUDE.md).

════════════════════════════════════════════════════════════════════════════
LA RÈGLE DE CE FICHIER (QJR68, vague M3 — elle s'applique à partir d'ici)
════════════════════════════════════════════════════════════════════════════
Ce fichier est la **SURFACE d'écriture cross-app d'`apps.ventes`**, et rien
d'autre. **L'implémentation vit sous `apps/ventes/domain/`** : un module par
domaine, déplacé tel quel (corps identiques, zéro correction au passage), avec
ses propres tests. **Toute fonction ajoutée ici doit être un RÉ-EXPORT** d'un
module de `domain/` — jamais un corps neuf.

POURQUOI. Au 29/08/2026 ce fichier portait 245 définitions de niveau module sur
11 231 lignes, pour quatorze domaines sans rapport entre eux (bordereau,
facturation, e-signature, catalogue, géométrie, composition, études…). La
vague M3 les déplace un domaine à la fois ; `services.py` garde le ré-export
tant qu'un appelant l'y lit, et finit en pure façade (imports + affectations).

COMMENT ON RÉ-EXPORTE, ET POURQUOI PAS `from … import …`. Le ré-export est une
**affectation de niveau module** (`nom = _module.nom`). Le pin de surface
`apps/ventes/tests/test_services_surface.py` lit ce fichier par AST et ne
compte comme définition qu'un `def`/`class`/affectation : un `from … import`
ferait disparaître le nom de la liste dorée et masquerait tout élargissement
futur de la surface. L'affectation garde le pin EXACT sans le retoucher.

ORDRE DE CHARGEMENT (insensible au sens d'import, dans les DEUX sens) : les
imports des modules de `domain/` sont **à la toute fin du fichier**, après
toutes les définitions restantes ; symétriquement, un module de `domain/` qui a
encore besoin d'un nom hébergé ici l'importe **en bas de son propre fichier**.
Ainsi, quel que soit le module chargé le premier, chaque attribut lu à l'import
existe déjà.
"""
from collections import namedtuple
from decimal import Decimal, ROUND_HALF_UP
import logging
import math

# QJR71 — `re` et `unicodedata` ont suivi les classifieurs et les normalisations
# de libellé dans `domain/catalogue.py` : plus AUCUN lecteur ici.
# QJR69 — `from apps.stock.services import qr_svg_for` a suivi son SEUL lecteur,
# `qr_svg_for_facture_pdf`, dans `domain/encaissements.py` : le garder ici en
# import mort ferait croire qu'un `mock.patch('…services.qr_svg_for')` couvre
# encore ce chemin, alors qu'un patch n'affecte que l'espace de noms qu'il vise.

logger = logging.getLogger(__name__)


def _add_months(d, months):
    """YSUBS9 — `d` décalée de `months` mois (jour recadré fin de mois).

    Fonction pure stdlib (pas de dépendance ajoutée), même calcul que
    `apps.sav.dateutils.add_months` mais gardée locale pour ne pas coupler
    `ventes` à `sav` pour une simple arithmétique de date."""
    if d is None or months is None:
        return None
    import calendar
    total = d.month - 1 + int(months)
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    from datetime import date
    return date(year, month, day)


def create_draft_devis_from_ocr(*, company, user, lead, fields):
    """FG106 — crée un DEVIS brouillon (sans lignes) à partir d'un document OCR.

    Point d'entrée cross-app sanctionné (services.py) pour la passerelle
    OCR → ventes (apps.publicapi). Le devis part TOUJOURS d'un lead (le client
    est résolu côté serveur via crm.services, sans doublon — réutilise la même
    règle que le générateur). Les lignes ne sont PAS créées : une LigneDevis
    exige un Produit du catalogue, qu'un document OCR brut ne fournit pas — le
    devis brouillon est laissé à compléter dans l'éditeur. Les montants/numéro
    extraits sont consignés dans la note du devis pour aider la saisie.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4).
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference
    from apps.crm.services import resolve_client_for_lead

    if lead is None:
        raise ValueError("create_draft_devis_from_ocr requires a lead")
    client = resolve_client_for_lead(lead)

    fields = fields or {}
    notes = ["Devis brouillon créé depuis un document OCR."]
    for key, label in (('numero', 'N° document'), ('montant_ht', 'Montant HT'),
                       ('montant_tva', 'Montant TVA'),
                       ('montant_ttc', 'Montant TTC'), ('date', 'Date')):
        val = fields.get(key)
        if val not in (None, ''):
            notes.append(f"{label} : {val}")
    note = "\n".join(notes)

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            lead=lead,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    logger.info('FG106: devis brouillon %s créé depuis OCR (company %s)',
                devis.reference, getattr(company, 'id', '?'))
    return devis


def dupliquer_devis(devis, *, user):
    """NTUX13 — Duplique ``devis`` en un devis BROUILLON totalement
    INDÉPENDANT (nouveau numéro, jamais le statut de la source — même un
    devis ``accepte``/``envoye`` redémarre en ``brouillon``).

    À la différence de ``dupliquer-variante`` (QJ15, ``views/devis.py``) qui
    groupe ses copies avec l'original via ``version_parent``/``version`` pour
    une comparaison côte-à-côte, CE duplicata est délibérément SANS lien de
    version : ``version=1``, ``version_parent=None``. Aucun chantier/
    BonCommande/Facture n'est jamais copié — ces objets naissent en aval d'un
    devis ACCEPTÉ (rule #4) et ne sont référencés nulle part sur ``Devis``
    lui-même, donc un brouillon frais n'en hérite jamais.

    Les lignes sont clonées à l'identique (mêmes quantités/prix/sections)."""
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.company_settings import create_numbered

    company = devis.company
    holder = {}

    def _save(ref):
        obj = Devis.objects.create(
            company=company, reference=ref,
            client=devis.client, lead=devis.lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=devis.taux_tva,
            remise_globale=devis.remise_globale,
            note=(f'[Copie de {devis.reference}] ' + (devis.note or '')).strip(),
            mode_installation=devis.mode_installation,
            etude_params=devis.etude_params,
            prix_cible_kwc=devis.prix_cible_kwc,
            devise=devis.devise,
            taux_change=devis.taux_change,
            created_by=user,
            # Duplicata indépendant : jamais de groupe de version (à la
            # différence de dupliquer-variante, QJ15).
            version=1, version_parent=None, is_active=True,
        )
        holder['obj'] = obj
        return obj

    create_numbered(Devis, company, 'devis', _save)
    copie = holder['obj']

    for ligne in devis.lignes.all():
        LigneDevis.objects.create(
            devis=copie, produit=ligne.produit, designation=ligne.designation,
            quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire,
            remise=ligne.remise, type_ligne=ligne.type_ligne, ordre=ligne.ordre,
            taux_tva=ligne.taux_tva, groupe_index=ligne.groupe_index,
            groupe_label=ligne.groupe_label,
        )
    logger.info('NTUX13: devis %s dupliqué en %s (company %s)',
                devis.reference, copie.reference, getattr(company, 'id', '?'))
    return copie


# ── GAMMES — offre à DEUX GAMMES paramétrable (fondateur 2026-08-18) ────────
# Une GAMME est une VARIANTE de devis : un devis frère COMPLET (composition et
# prix propres) groupé par ``version_parent`` — exactement la mécanique QJ15
# (``views/devis.py:dupliquer_variante``). Jamais un second axe DANS un devis :
# l'axe « avec / sans batterie » (OptionKey/option_acceptee, PV86) reste
# INTERNE à chaque gamme et inchangé.
#
# Le libellé est une DONNÉE, jamais une marque codée en dur : il vit dans
# ``Devis.etude_params['gamme']`` (aucun changement de modèle) :
#     {'nom': 'Essentielle', 'recommandee': False, 'envoi': 'les_deux'}
#  * ``nom``        — libellé libre saisi par le vendeur ;
#  * ``recommandee``— la gamme portant le badge « Recommandé » ;
#  * ``envoi``      — mode d'envoi réglé À L'ENVOI : « les_deux » (DÉFAUT
#                    fondateur — même philosophie que l'axe batterie, dont le
#                    défaut est déjà les deux options) ou « seule » (le lien
#                    rend le devis comme aujourd'hui, sans aucune mention de
#                    l'autre gamme).
GAMME_ENVOI_SEULE = 'seule'
GAMME_ENVOI_LES_DEUX = 'les_deux'
GAMME_ENVOI_DEFAUT = GAMME_ENVOI_LES_DEUX
GAMME_ENVOIS = (GAMME_ENVOI_SEULE, GAMME_ENVOI_LES_DEUX)
# Défauts proposés à l'écran ; le vendeur reste libre de saisir ce qu'il veut.
GAMME_NOMS_DEFAUT = ('Essentielle', 'Premium')


def gamme_info(devis):
    """Renvoie le dict ``gamme`` du devis (jamais None) — lecture défensive.

    Un devis sans gamme renvoie ``{}`` : tout le reste du système se comporte
    alors exactement comme aujourd'hui (aucun bloc de choix, aucune mention)."""
    params = getattr(devis, 'etude_params', None) or {}
    g = params.get('gamme') if isinstance(params, dict) else None
    return dict(g) if isinstance(g, dict) else {}


def gamme_nom(devis):
    """Libellé de gamme du devis, ou '' — jamais une marque codée en dur."""
    return str(gamme_info(devis).get('nom') or '').strip()


def gamme_envoi(devis):
    """Mode d'envoi de la gamme : « seule » ou « les_deux ».

    DÉFAUT fondateur : « les_deux » — une paire de gammes envoyée sans réglage
    explicite propose donc le choix au client (le vendeur peut restreindre)."""
    mode = str(gamme_info(devis).get('envoi') or '').strip()
    return mode if mode in GAMME_ENVOIS else GAMME_ENVOI_DEFAUT


def _set_gamme(devis, **champs):
    """Écrit (fusionne) les clés de gamme dans ``etude_params`` et sauvegarde.

    Copie le dict au lieu de le muter en place : ``dupliquer_variante`` passe
    la MÊME référence de dict aux copies, une mutation fuirait sur le frère.

    QJR62 — passe par l'ÉCRIVAIN UNIQUE ``domain.etude_schema.ecrire`` : la
    fusion et le refus des clés dérivées vivent à UN seul endroit, plus dans
    chaque appelant."""
    from apps.ventes.domain.etude_schema import ECRAN, ecrire

    params = dict(getattr(devis, 'etude_params', None) or {})
    gamme = dict(params.get('gamme') or {})
    gamme.update({k: v for k, v in champs.items() if v is not None})
    ecrire(devis, proprietaire=ECRAN, gamme=gamme)
    return gamme


def gamme_soeur(devis):
    """Le devis frère PORTANT UNE GAMME (même groupe ``version_parent``), ou None.

    Ne considère que les frères ACTIFS et encore vivants (brouillon/envoyé) de
    la même société : une gamme non retenue (auto-refusée à l'acceptation,
    YDOCF3) disparaît donc naturellement du choix."""
    from django.db.models import Q
    from apps.ventes.models import Devis
    if not gamme_nom(devis):
        return None
    root = devis.version_parent_id or devis.pk
    freres = (
        Devis.objects
        .filter(company=devis.company, is_active=True,
                statut__in=(Devis.Statut.BROUILLON, Devis.Statut.ENVOYE))
        .filter(Q(pk=root) | Q(version_parent_id=root))
        .exclude(pk=devis.pk)
        .order_by('version', 'id')
    )
    for frere in freres:
        if gamme_nom(frere):
            return frere
    return None


def creer_variante_gamme(devis, nom_gamme, *, user=None,
                         nom_gamme_source=None, recommandee=False):
    """Crée la SŒUR « gamme » de ``devis`` et pose les libellés des deux côtés.

    Réutilise TELLE QUELLE la mécanique de variantes QJ15 : nouveau devis
    BROUILLON complet, même client/lead/mode/TVA/remise, lignes clonées à
    l'identique (à retoucher ensuite — chaque gamme a sa composition et ses
    prix PROPRES), groupé par ``version_parent`` = racine du groupe et
    ``is_active=True`` (une alternative, pas un remplacement). Aucun statut
    n'est touché (règle #4) ; le numéro vient de ``create_numbered``.

    ``recommandee=True`` désigne la NOUVELLE gamme comme recommandée (et retire
    le badge de la source) — sinon la source garde/reçoit la recommandation :
    par défaut le devis porteur EST la gamme recommandée.
    """
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.company_settings import create_numbered

    nom_gamme = str(nom_gamme or '').strip()
    if not nom_gamme:
        raise ValueError('creer_variante_gamme exige un nom de gamme.')
    company = devis.company
    root = devis.version_parent or devis
    holder = {}

    # etude_params est COPIÉ (jamais partagé) : la gamme sœur porte son propre
    # bloc ``gamme`` sans jamais toucher celui de la source.
    params_soeur = dict(getattr(devis, 'etude_params', None) or {})
    params_soeur['gamme'] = {
        'nom': nom_gamme,
        'recommandee': bool(recommandee),
        'envoi': gamme_envoi(devis),
    }

    def _save(ref):
        obj = Devis.objects.create(
            company=company, reference=ref,
            client=devis.client, lead=devis.lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=devis.taux_tva,
            remise_globale=devis.remise_globale,
            note=(f'[Gamme {nom_gamme}] ' + (devis.note or '')).strip(),
            mode_installation=devis.mode_installation,
            etude_params=params_soeur,
            prix_cible_kwc=devis.prix_cible_kwc,
            devise=devis.devise,
            taux_change=devis.taux_change,
            created_by=user,
            version=devis.version + 1,
            version_parent=root,
            is_active=True,
        )
        holder['obj'] = obj
        return obj

    create_numbered(Devis, company, 'devis', _save)
    soeur = holder['obj']

    for ligne in devis.lignes.all():
        LigneDevis.objects.create(
            devis=soeur, produit=ligne.produit, designation=ligne.designation,
            quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire,
            remise=ligne.remise, type_ligne=ligne.type_ligne, ordre=ligne.ordre,
            taux_tva=ligne.taux_tva, groupe_index=ligne.groupe_index,
            groupe_label=ligne.groupe_label,
        )

    # La SOURCE reçoit son propre libellé (défaut : l'autre nom proposé) et la
    # recommandation quand la sœur ne la prend pas.
    nom_source = (str(nom_gamme_source or '').strip()
                  or gamme_nom(devis)
                  or next((n for n in GAMME_NOMS_DEFAUT
                           if n.lower() != nom_gamme.lower()),
                          GAMME_NOMS_DEFAUT[0]))
    _set_gamme(devis, nom=nom_source, recommandee=(not recommandee),
               envoi=gamme_envoi(devis))
    logger.info('GAMME: variante « %s » (%s) créée depuis %s (company %s)',
                nom_gamme, soeur.reference, devis.reference,
                getattr(company, 'id', '?'))
    return soeur


def regler_envoi_gamme(devis, mode):
    """Règle le MODE D'ENVOI de la paire de gammes, des DEUX côtés.

    Appelé au moment de l'envoi (lien / WhatsApp / email). ``mode`` invalide ou
    devis sans gamme → no-op silencieux (l'envoi ne doit jamais échouer pour
    ça). Renvoie le mode effectif."""
    mode = str(mode or '').strip()
    if mode not in GAMME_ENVOIS or not gamme_nom(devis):
        return gamme_envoi(devis)
    _set_gamme(devis, envoi=mode)
    soeur = gamme_soeur(devis)
    if soeur is not None:
        _set_gamme(soeur, envoi=mode)
    return mode


# ── PVMRQ — marque préférée par gamme/rôle (fondateur 18/08/2026) ──────────
#
# ``ParametresGammes`` (apps/ventes/models.py) porte le réglage ; ces deux
# fonctions en sont la SEULE voie de lecture — aucun autre code ne doit lire
# ``ParametresGammes.marques`` directement (le contrat JSON n'a qu'un seul
# lecteur, donc qu'un seul endroit à faire évoluer si sa forme change).

def get_parametres_gammes(company):
    """Réglages « gammes » de la société (get-or-create singleton, NTTRE27-like).

    Une société sans réglage explicite obtient les valeurs par défaut
    (``deux_gammes=False``, ``marques={}``) — aucune régression sur la
    composition automatique tant que le fondateur n'a rien configuré."""
    from .models import ParametresGammes
    params, _ = ParametresGammes.objects.get_or_create(company=company)
    return params


def create_devis_from_reserve(*, reserve, user):
    """XFSM18 — crée un DEVIS brouillon de réparation à partir d'une réserve
    d'intervention (`installations.Reserve`), pour donner un chemin de devis
    payant au pipeline de réparation.

    Le client est celui du CHANTIER (`reserve.intervention.installation.client`,
    déjà résolu — aucune re-résolution lead nécessaire ici, à la différence de
    `create_draft_devis_from_ocr`). La description est pré-remplie depuis la
    réserve ; aucune ligne n'est créée (une LigneDevis exige un Produit du
    catalogue) — le devis brouillon est laissé à compléter dans l'éditeur.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4). Aucun impact sur `/proposal`.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.references import create_with_reference

    installation = reserve.intervention.installation
    if installation is None or installation.client_id is None:
        raise ValueError(
            "create_devis_from_reserve requires a reserve whose intervention "
            "is attached to a chantier with a resolved client")
    client = installation.client
    company = reserve.company or installation.company

    description = (reserve.description or '').strip()
    note_lines = ["Devis de réparation généré depuis une réserve d'intervention."]
    if description:
        note_lines.append(f"Description : {description}")
    if reserve.photo_id:
        note_lines.append(f"Photo référencée : pièce jointe #{reserve.photo_id}")
    note = "\n".join(note_lines)

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    logger.info(
        'XFSM18: devis de réparation %s créé depuis la réserve %s (company %s)',
        devis.reference, reserve.id, getattr(company, 'id', '?'))
    return devis


def lead_from_source_devis(document):
    """U12 — résout le lead d'origine d'une Facture / d'un BonCommande.

    Le lien direct ``lead`` de la Facture/BC est snapshoté depuis le devis
    source à la création. On le résout ici, de façon centralisée, pour les deux
    voies de création :

    * facture d'échéancier ou BC directement lié à un devis → ``document.devis``;
    * chaîne BC → facture (la facture porte ``bon_commande``, pas ``devis``) →
      ``document.bon_commande.devis``.

    Renvoie l'instance ``crm.Lead`` du devis source, ou ``None`` si aucun devis
    source ne porte de lead (ex. facture de contrat de maintenance, BC sans
    devis). Ne lève jamais : un attribut absent retombe sur ``None``.
    """
    devis = getattr(document, 'devis', None)
    if devis is None:
        bc = getattr(document, 'bon_commande', None)
        if bc is not None:
            devis = getattr(bc, 'devis', None)
    if devis is None:
        return None
    return getattr(devis, 'lead', None)


# PVSCE — vocabulaire du choix de scénario, tel que le moteur PDF le LIT dans
# ``etude_params['scenario']`` (quote_engine/builder.py, QF6). Le LIBELLÉ
# FRANÇAIS est le contrat : un 'reseau'/'avec_batterie' n'y serait pas reconnu
# et le moteur retomberait sur l'inférence par les lignes — c'est-à-dire sur le
# repli qu'on cherche précisément à ne plus dépendre.
SCENARIO_SANS_BATTERIE = 'Sans batterie'
SCENARIO_AVEC_BATTERIE = 'Avec batterie'
#: U2 — devis à DEUX OPTIONS : le client compare « sans » et « avec » dans un
#: seul document. Libellé RECONNU TEL QUEL par le moteur PDF
#: (``quote_engine/builder.py``) : ne pas le reformuler.
SCENARIO_LES_DEUX = 'Les deux (Sans + Avec)'


def _scenario_stocke(avec_batterie):
    """Le libellé à ranger dans ``etude_params['scenario']``.

    On ne stocke « Avec batterie » que quand l'équipement peut réellement le
    servir (onduleur hybride ET batterie) : un choix stocké que les lignes ne
    peuvent pas honorer serait un mensonge que le moteur devrait défaire.
    """
    return SCENARIO_AVEC_BATTERIE if avec_batterie else SCENARIO_SANS_BATTERIE


def _aspect_to_orientation(aspect):
    """FG248 — azimut PVGIS (0=Sud, -90=Est, 90=Ouest, ±180=Nord) → libellé FR.

    Miroir inverse de ``orientationToAspect`` (apps/web/src/lib/roof.ts) pour que
    le devis affiche la même orientation que l'outil 3D. Aspect inconnu → ''."""
    try:
        a = float(aspect)
    except (TypeError, ValueError):
        return ''
    # Normalise dans [-180, 180].
    a = (a + 180.0) % 360.0 - 180.0
    table = [
        (0.0, 'Sud'), (-45.0, 'Sud-Est'), (45.0, 'Sud-Ouest'),
        (-90.0, 'Est'), (90.0, 'Ouest'),
        (-135.0, 'Nord-Est'), (135.0, 'Nord-Ouest'),
        (180.0, 'Nord'), (-180.0, 'Nord'),
    ]
    return min(table, key=lambda t: abs(a - t[0]))[1]


def _azimut_boussole_vers_aspect(azimut):
    """Azimut BOUSSOLE du builder (180 = Sud) → azimut PVGIS (0 = Sud).

    MÊME formule que le builder lui-même (``roofPro11/prodWindow.ts`` :
    ``aspect: res.facingAzimuthDeg - 180``), normalisée dans [-180, 180] pour
    que ±180 reste bien le Nord. Valeur illisible → ``None`` (le libellé est
    alors omis, jamais deviné)."""
    try:
        a = float(azimut)
    except (TypeError, ValueError):
        return None
    return (a - 180.0 + 180.0) % 360.0 - 180.0


def _aspect_vers_azimut_boussole(aspect):
    """Azimut PVGIS (0 = Sud) → azimut BOUSSOLE (180 = Sud), dans [0, 360).

    Réciproque de :func:`_azimut_boussole_vers_aspect`. Elle existe pour que
    ``_pans_geometry['azimut_deg']`` n'ait qu'UN SEUL repère quelle que soit la
    clé source du layout (F3) — voir :func:`extract_roof_config`. Valeur
    illisible → ``None``.
    """
    try:
        a = float(aspect)
    except (TypeError, ValueError):
        return None
    return (a + 180.0) % 360.0


def extract_roof_config(layout):
    """FG248 — extrait la config TOITURE d'un layout 3D (roofPro11) en un dict
    plat, JSON-sérialisable, indépendant de la version de l'outil.

    Lit les PANS de toiture (``areas``/``zones``/``pans``) — chacun portant
    ``roofType``, ``pitchDeg``/``pitch``, ``facingAzimuthDeg``/``aspect`` et un
    ``result`` ``{count, kwc, areaM2}`` (PV14 : à défaut, le bloc ``geometry``
    par pan de la sérialisation v1) — et en agrège :

        {surface_m2, nb_pans, nb_panneaux, kwc, orientation_principale,
         azimut_deg, inclinaison_deg, pans: [{...}]}

    Tolérant : entrées manquantes → champs omis ; aucune exception. Renvoie {}
    si le layout ne contient aucune géométrie de toiture exploitable (pour ne
    rien changer au comportement historique du seul bloc ``result``).
    """
    layout = layout or {}
    areas = (layout.get('areas') or layout.get('zones')
             or layout.get('pans') or [])
    if not isinstance(areas, list) or not areas:
        return {}

    pans = []
    total_surface = 0.0
    total_panels = 0
    total_kwc = 0.0
    best = None  # pan le plus puissant → orientation principale
    for a in areas:
        if not isinstance(a, dict):
            continue
        res = a.get('result') or {}
        # PV14 — les layouts DÉJÀ STOCKÉS (sérialisation roofPro11 v1) ne
        # portent PAS de bloc ``result`` par pan : la puissance et le compte
        # RÉELS y vivent dans le bloc ``geometry`` de la zone (WJ24 :
        # {azimuthDeg, tiltDeg, family, flush, kwc, count, origin, panels}).
        # Sans cette lecture un tel blob remontait 0 kWc — et le devis
        # reconstruit perdait le wattage panneau (aucun watt déductible, donc
        # plus de choix de produit à wattage exact). L'ordre est STRICT :
        # ``result`` d'abord (comportement historique inchangé au bit près),
        # ``geometry`` ensuite, ``neededPanels`` en tout dernier recours (le
        # compte SOUHAITÉ, pas le compte POSÉ).
        geo = a.get('geometry')
        if not isinstance(geo, dict):
            geo = {}
        count = int(res.get('count') or geo.get('count')
                    or a.get('neededPanels') or 0)
        kwc = float(res.get('kwc') or geo.get('kwc') or 0.0)
        surface = float(res.get('areaM2') or geo.get('areaM2')
                        or a.get('areaM2') or 0.0)
        # ── DEUX CONVENTIONS D'ANGLE, ET ELLES SONT OPPOSÉES ────────────────
        # ``facingAzimuthDeg`` est l'AZIMUT BOUSSOLE du builder (180 = Sud) —
        # c'est ce que ``newAreaRecord()`` pose par défaut et ce que le solveur
        # d'orientation écrit ; le builder lui-même le convertit pour PVGIS en
        # retranchant 180 (``roofPro11/prodWindow.ts`` : « jambe sud : aspect =
        # azimut − 180 »).
        # ``aspect``, lui, est DÉJÀ l'azimut PVGIS (0 = Sud), et c'est cette
        # convention-là qu'attend ``_aspect_to_orientation``.
        #
        # Les deux entraient ici SANS conversion : un pan plein Sud
        # (``facingAzimuthDeg: 180``) ressortait donc « Nord », et l'annexe
        # « paramètres du site » de la proposition CLIENT publiait
        # ``orientation_deg: 180`` juste à côté de ``orientation: 'Nord'`` —
        # deux affirmations contradictoires, dont une fausse, sous les yeux du
        # client. On convertit désormais à la lecture, à l'endroit exact où la
        # convention est connue. ``azimut_deg`` reste la valeur BRUTE (aucun
        # autre consommateur ne change de repère) : seul le LIBELLÉ est corrigé.
        #
        # F3 — ET ``azimut_deg`` NE PUBLIE QU'UN SEUL REPÈRE. Il recopiait la
        # valeur BRUTE de la clé source : COMPASS venant de ``facingAzimuthDeg``,
        # PVGIS venant de ``aspect``. Deux toits plein Sud pouvaient donc sortir
        # d'ici avec ``azimut_deg`` 180 pour l'un et 0 pour l'autre, tous deux
        # étiquetés « Sud » — et ses consommateurs (annexe client, étude
        # bancable) n'avaient aucun moyen de savoir lequel ils lisaient. Le
        # repère PUBLIÉ est désormais la BOUSSOLE, toujours : la branche
        # ``facingAzimuthDeg`` garde sa valeur brute (aucun consommateur ne
        # change de repère), la branche ``aspect`` est convertie.
        brut = a.get('facingAzimuthDeg')
        if brut is not None:
            azimut_boussole = brut
            aspect_pvgis = _azimut_boussole_vers_aspect(brut)
        else:
            aspect_pvgis = a.get('aspect')
            azimut_boussole = _aspect_vers_azimut_boussole(aspect_pvgis)
        pitch = a.get('pitchDeg')
        if pitch is None:
            pitch = a.get('pitch')
        pan = {
            'label': a.get('label') or '',
            'roof_type': a.get('roofType') or '',
            'nb_panneaux': count,
            'kwc': round(kwc, 3) if kwc else 0.0,
            'surface_m2': round(surface, 2) if surface else 0.0,
            # BOUSSOLE (180 = Sud), toujours — voir F3 ci-dessus. Tout lecteur
            # qui a besoin de l'aspect PVGIS convertit lui-même, avec
            # ``_azimut_boussole_vers_aspect``.
            'azimut_deg': azimut_boussole,
            'inclinaison_deg': pitch,
            'orientation': _aspect_to_orientation(aspect_pvgis),
        }
        pans.append(pan)
        total_surface += surface
        total_panels += count
        total_kwc += kwc
        if best is None or kwc > best['kwc']:
            best = pan

    if not pans:
        return {}

    cfg = {
        'surface_m2': round(total_surface, 2),
        'nb_pans': len(pans),
        'nb_panneaux': total_panels,
        'kwc': round(total_kwc, 3),
        'pans': pans,
    }
    if best is not None:
        cfg['orientation_principale'] = best['orientation']
        cfg['azimut_deg'] = best['azimut_deg']
        cfg['inclinaison_deg'] = best['inclinaison_deg']
    return cfg


def layout_hash(layout):
    """QJ17 — deterministic SHA-256 fingerprint of a roof layout dict.

    Used to detect duplicate ``from-layout`` submissions (same geometry re-sent
    after a network retry or a double-click).  Only the geometry-bearing keys are
    hashed (``zones``/``areas``/``pans``, ``result``, ``scenario``, ``panelWatt``,
    ``watt``, ``battery``) so that transient UI state (``pin``, ``outline``,
    ``billKwh``, ``activeAreaId``, ``renderPlan``…) never prevents deduplication.
    """
    import hashlib
    import json as _json

    if not isinstance(layout, dict):
        return ''
    canonical = {
        'zones': layout.get('zones') or layout.get('areas') or layout.get('pans'),
        'result': layout.get('result'),
        'scenario': layout.get('scenario'),
        'panelWatt': layout.get('panelWatt') or layout.get('watt'),
        'battery': bool(layout.get('battery')),
    }
    blob = _json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                       default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def validate_composition_for_layout(layout, company):
    """QJ17 — pre-flight composition check before building a devis.

    Returns ``None`` when the composition is valid.  Returns a list of French
    error strings when problems are detected (caller should surface them inline
    rather than raising a PDF error at render time).

    Rules (aligned with quote_engine/builder.py keyword classification):
    - At least 1 panel is required.
    - A battery scenario requires both a hybrid inverter AND a battery in the
      catalogue (priced); if either is missing, warn the agent.
    - A réseau scenario requires a réseau/injection inverter (priced).
    - A price-less required product blocks the composition (never auto-quote it).
    """
    if not isinstance(layout, dict):
        return ['Layout invalide — impossible de valider la composition.']

    result = dict((layout.get('result') or {}))
    nb_panneaux = int(result.get('panels') or 0)
    toiture = extract_roof_config(layout)
    if nb_panneaux <= 0 and toiture.get('nb_panneaux'):
        nb_panneaux = int(toiture['nb_panneaux'])

    errors = []
    if nb_panneaux <= 0:
        errors.append(
            'Aucun panneau détecté dans le layout. '
            'Terminez le tracé du toit et relancez l\'optimiseur avant de générer.')

    scenario = (layout.get('scenario') or '').lower()
    wants_battery = ('batterie' in scenario or 'hybride' in scenario
                     or bool(layout.get('battery')))

    if wants_battery:
        # PVMRQ — pas de devis ici (pré-vol AVANT création) ⇒ pas de gamme
        # connue : ``marque_preferee`` retombe explicitement sur le slot
        # Essentielle.
        inv = _pick_product(company, _is_hybrid_inverter, role='onduleur_hybride')
        # PVOND — garde batterie PILOTÉ PAR LA DONNÉE : la batterie retenue doit
        # entrer dans la plage batterie de l'onduleur hybride effectivement
        # choisi ci-dessus. Sans plage déclarée (ou sans fiche batterie), repli
        # sur le mot-clé « haute tension » d'hier (PVG4) — jamais de régression
        # silencieuse.
        bat = _pick_batterie(company, onduleur=inv)
        if inv is None:
            errors.append(
                'Aucun onduleur hybride disponible (ou sans prix) dans le catalogue. '
                'Ajoutez un onduleur hybride tarifé avant de générer ce devis.')
        if bat is None:
            # PVOND — DIRE POURQUOI : « aucune batterie » et « aucune batterie
            # COMPATIBLE avec cet onduleur » n'appellent pas le même geste.
            plage = _plage_batterie_de_l_onduleur(inv)
            if plage and plage[1] > 0:
                errors.append(
                    'Aucune batterie compatible tarifée pour cet onduleur '
                    '(plage %s-%s V). Ajoutez une batterie compatible tarifée, '
                    'ou choisissez un autre onduleur, avant de générer ce '
                    'devis.' % (_v_txt(plage[0]), _v_txt(plage[1])))
            else:
                errors.append(
                    'Aucune batterie disponible (ou sans prix) dans le '
                    'catalogue. Ajoutez une batterie tarifée avant de générer '
                    'ce devis.')
    else:
        inv = _pick_product(company, _is_reseau_inverter, role='onduleur_reseau')
        if inv is None:
            errors.append(
                'Aucun onduleur réseau disponible (ou sans prix) dans le catalogue. '
                'Ajoutez un onduleur réseau/injection tarifé avant de générer.')

    return errors if errors else None


# ── PV16 — la CIBLE de calepinage se lit dans les LIGNES du devis ───────────
#
# L'écran de conception 3D doit repartir de ce que le devis DIT AUJOURD'HUI
# (combien de panneaux, quelle puissance unitaire, quel scénario), pas d'un
# blob de layout qui peut être absent, périmé ou d'une version antérieure de
# l'outil. Les lignes du devis, elles, sont la source vivante — c'est ce qui a
# été chiffré et, pour un devis envoyé, ce que le client a sous les yeux.
#
# Fonction PURE de lecture : elle ne touche NI le statut, NI les lignes, NI
# l'étude. Elle expose ses doutes plutôt que de les cacher — d'où la liste
# ``avertissements`` en français, affichable telle quelle.

#: Wattage retenu quand plus rien n'est lisible (panneau catalogue courant).
CIBLE_WATT_DEFAUT = 550


def _lignes_produit(devis):
    """Lignes PRODUIT d'un devis — les sections/notes n'en sont pas.

    Une ligne de SECTION/NOTE (XSAL14) ne porte ni produit, ni prix, ni
    quantité : elle ne peut donc ni compter dans une cible ni recevoir un
    écart de calepinage.
    """
    if devis is None:
        return []
    return [ligne for ligne in devis.lignes.all()
            if getattr(ligne, 'type_ligne', 'produit') == 'produit']


def _classe_ligne(ligne, predicat):
    """Classe une ligne sur sa DÉSIGNATION, à défaut sur le nom du produit.

    La désignation est ce que lit ``quote_engine/builder.py`` (contrat
    d'alignement des mots-clés, CLAUDE.md règle #4) ; le nom du produit n'est
    consulté qu'en second, pour rattraper une désignation réécrite à la main
    (« Modules PV posés » sur un produit « Panneau Jinko 550W »).
    """
    return (predicat(ligne.designation or '')
            or predicat(getattr(ligne.produit, 'nom', '') or ''))


def _pmax_wc_du_produit(produit):
    """Pmax (Wc) de la fiche technique d'un produit, ou ``None``.

    Passe par ``apps.stock.selectors.specs_for_produit`` — le point d'entrée
    cross-app SANCTIONNÉ pour lire une ``FicheTechnique`` (jamais un import de
    ``apps.stock.models`` ici). Ce sélecteur peut ne pas encore exister dans
    l'arbre : son absence est un NON-ÉVÉNEMENT (on retombe simplement sur la
    lecture du wattage dans le libellé), jamais une exception.
    """
    if produit is None:
        return None
    try:
        from apps.stock import selectors as _stock_selectors
    except Exception:  # noqa: BLE001 — app absente / import cassé : on ignore
        return None
    lire = getattr(_stock_selectors, 'specs_for_produit', None)
    if lire is None:
        return None
    try:
        specs = lire(produit)
    except TypeError:
        # Le sélecteur peut attendre un id plutôt que l'objet.
        try:
            specs = lire(getattr(produit, 'id', None))
        except Exception:  # noqa: BLE001
            return None
    except Exception:  # noqa: BLE001
        return None
    if specs is None:
        return None
    pmax = (specs.get('pmax_wc') if isinstance(specs, dict)
            else getattr(specs, 'pmax_wc', None))
    try:
        pmax = int(round(float(pmax)))
    except (TypeError, ValueError):
        return None
    return pmax if pmax > 0 else None


def lignes_de_variante(lignes, variante):
    """Les lignes qui composent l'option ``variante`` d'un devis.

    C'est-à-dire les lignes COMMUNES (``variante=''`` — donc TOUTES celles d'un
    devis non varianté) plus celles qui sont propres à cette option. Une ligne
    de l'AUTRE option décrit une AUTRE installation : la faire entrer dans ce
    panier donnerait un ensemble qu'aucun client n'achète.

    ``variante`` vaut ``'sans'`` (défaut) ou ``'avec'``.
    """
    propre = VARIANTE_AVEC if variante == VARIANTE_AVEC else VARIANTE_SANS
    return [li for li in lignes
            if (getattr(li, 'variante', '') or '')
            in (VARIANTE_COMMUNE, propre)]


def option_avec_servable(devis):
    """Ce devis peut-il RÉELLEMENT livrer l'option « Avec batterie » ?

    MÊME critère que partout ailleurs dans le domaine — le moteur PDF
    (``quote_engine/builder.py`` : ``avec_ok = has_hybride and has_batterie``,
    d'où descendent ``variantes_servables`` et ``dimensionnement_options``) et
    le scénario stocké à la création (``_a_batterie and _a_hybride``) : l'option
    « avec » exige un onduleur HYBRIDE ET une BATTERIE. Lu sur le sous-ensemble
    de lignes qui compose CETTE option, jamais sur le panier mélangé.

    LECTURE PURE : n'écrit rien, ne lève pas sur un devis sans lignes.
    """
    lignes = lignes_de_variante(_lignes_produit(devis), VARIANTE_AVEC)
    return (any(_classe_ligne(li, _is_hybrid_inverter) for li in lignes)
            and any(_classe_ligne(li, _is_battery) for li in lignes))


def cible_depuis_lignes(devis, variante='sans'):
    """PV16 — cible de calepinage LUE DANS LES LIGNES du devis.

    Rend toujours le même dict, quelles que soient les données :

        {panneaux, kwc, panel_watt, scenario, batterie, avertissements}

    * ``panneaux`` — somme des quantités des lignes classées « panneau » par le
      classifieur partagé ``_is_panel`` (aligné sur ``quote_engine/builder.py``).
      Les lignes de SECTION/NOTE (sans prix ni quantité) sont ignorées.
    * ``panel_watt`` — wattage unitaire de la ligne dominante DE CETTE OPTION
      (QJR33), dans cet ordre : la fiche technique du produit dominant
      (``pmax_wc``), sinon le wattage lu dans le libellé (désignation puis nom
      du produit), sinon déduit du kWc de l'étude, sinon ``CIBLE_WATT_DEFAUT``
      — et là SEULEMENT un avertissement est levé.
    * ``kwc`` — puissance recalculée DEPUIS LES LIGNES (``panneaux × watt``),
      pas recopiée de l'étude : c'est le devis qui fait foi ici, pas un
      paramètre d'étude qui a pu se désynchroniser.
    * ``scenario`` — ``avec_batterie`` dès qu'une batterie est présente, sinon
      ``hybride`` si un onduleur hybride l'est, sinon ``reseau`` (défaut
      résidentiel, même arbitrage que ``build_devis_from_layout``).
    * ``avertissements`` — messages FRANÇAIS affichables tels quels.

    L-2OPT — LA CIBLE SE LIT PAR VARIANTE. Un devis « Les deux » dont les deux
    optimums divergent porte DEUX comptes de panneaux : les lignes
    ``variante=''`` + ``'sans'`` font l'option SANS, les lignes ``''`` +
    ``'avec'`` font l'option AVEC. ``panneaux`` / ``kwc`` sont ceux de l'option
    SANS — l'option 1 du document, celle que l'écran de calepinage dessine.
    Additionner les deux vues (ce que faisait la somme brute des lignes)
    donnerait un nombre qui ne décrit AUCUNE installation.

    CTX3D (25/08/2026) — ``scenario`` ET ``batterie`` DÉCRIVENT LA MÊME OPTION
    QUE ``panneaux``. Ils se lisaient sur TOUTES les lignes du devis pendant que
    le compte, lui, était filtré : un devis « Les deux » rendait donc
    ``panneaux`` = l'option SANS accompagné de ``scenario='avec_batterie'`` —
    une cible que rien ne décrit, envoyée telle quelle à l'écran 3D (PV17). Les
    quatre grandeurs viennent désormais du MÊME sous-ensemble de lignes.

    QJR33 (29/08/2026) — ``panel_watt`` REJOINT ENFIN CE SOUS-ENSEMBLE. La ligne
    DOMINANTE (celle qui porte le wattage) se cherchait encore dans TOUTES les
    lignes panneau du devis : sur un devis « Les deux » à DEUX modèles de
    panneau, le ``kwc`` rendu mariait le COMPTE d'une option au WATTAGE de
    l'autre (5,68 kWc observés au lieu de 4,40), et ce kWc partait tel quel dans
    le contrat 3D. Les CINQ grandeurs viennent maintenant de la même variante.

    ``variante`` choisit ce sous-ensemble : ``'sans'`` (défaut — l'option 1,
    celle que l'écran dessine, comportement historique) ou ``'avec'``. Sur un
    devis NON varianté les deux vues sont identiques : les lignes y sont toutes
    communes.

    LA FORME DU DICT NE BOUGE PAS : ces six clés sont un contrat gelé (le
    contexte de conception PV17 le repique tel quel). Un devis NON varianté —
    tous ceux d'hier — rend donc exactement les mêmes valeurs qu'avant.

    LECTURE PURE : aucun statut, aucune ligne, aucune étude n'est écrite.
    """
    lignes = _lignes_produit(devis)
    # Le panier de CETTE option — la seule base légitime de tous les scalaires
    # ci-dessous (cf. CTX3D dans le docstring).
    lignes_option = lignes_de_variante(lignes, variante)

    def _nom(ligne):
        return ligne.designation or getattr(ligne.produit, 'nom', '') or ''

    lignes_panneau = [li for li in lignes if _classe_ligne(li, _is_panel)]

    def _quantite(ligne):
        try:
            # ArithmeticError couvre decimal.InvalidOperation.
            return int(Decimal(str(ligne.quantite or 0)))
        except (ArithmeticError, TypeError, ValueError):
            return 0

    # L-2OPT — LE COMPTE EST CELUI DE L'OPTION DEMANDÉE : les lignes COMMUNES
    # (``variante=''``, c'est-à-dire toutes celles d'un devis d'hier) plus
    # celles qui lui sont propres. Une ligne de l'autre option décrit une AUTRE
    # installation — la compter ici donnerait la somme des deux paniers, un
    # nombre de panneaux qu'aucune installation ne porte.
    lignes_panneau_option = [li for li in lignes_option
                             if _classe_ligne(li, _is_panel)]
    panneaux = sum(_quantite(li) for li in lignes_panneau_option)

    # CTX3D — MÊME sous-ensemble que le compte : sur un devis « Les deux », la
    # batterie et l'onduleur hybride appartiennent à l'option « avec ». Les
    # chercher dans tout le devis faisait décrire l'option 1 par le scénario de
    # l'option 2.
    batterie = any(_classe_ligne(li, _is_battery) for li in lignes_option)
    hybride = any(_classe_ligne(li, _is_hybrid_inverter)
                  for li in lignes_option)
    if batterie:
        scenario = 'avec_batterie'
    elif hybride:
        scenario = 'hybride'
    else:
        scenario = 'reseau'

    avertissements = []
    if not lignes_panneau:
        avertissements.append(
            'Aucune ligne de panneau dans ce devis : la cible de calepinage '
            'est vide. Ajoutez les panneaux au devis avant de concevoir la '
            'toiture.')

    # Ligne dominante = la plus GROSSE quantité : c'est elle qui porte le
    # wattage de référence, et c'est elle que PV18 ajustera en cas d'écart.
    #
    # QJR33 (29/08/2026) — ELLE SE LIT DANS LE PANIER DE CETTE OPTION, comme le
    # COMPTE juste au-dessus. Elle était cherchée dans TOUTES les lignes
    # panneau du devis : sur un devis « Les deux » à DEUX modèles de panneau
    # (8 × 710 Wc en « sans », 10 × 440 Wc en « avec »), le ``kwc`` rendu
    # mariait le compte d'une option au wattage de l'AUTRE — 5,68 kWc au lieu
    # de 4,40 — et ce kWc partait tel quel dans le contexte 3D (PV17).
    dominante = None
    if lignes_panneau_option:
        dominante = max(
            lignes_panneau_option,
            key=lambda li: Decimal(str(li.quantite or 0)))

    # Deux modèles de panneau différents dans un même devis : le calepinage ne
    # sait pas répartir l'écart — on le DIT au lieu de choisir en silence.
    #
    # L-2OPT — L'IDENTITÉ NE COMPTE PAS LA VARIANTE, EXPRÈS : deux lignes
    # variantées du MÊME modèle (8 panneaux « sans » / 10 panneaux « avec »)
    # sont UN SEUL modèle, et cet avertissement ne doit surtout pas se
    # déclencher pour elles — sinon tout devis à deux optimiseurs crierait au
    # « devis à deux modèles » alors qu'il n'en porte qu'un.
    identites = {
        (li.produit_id, (li.designation or '').strip().lower())
        for li in lignes_panneau
    }
    # QJR33 — ``dominante`` est désormais celle de CETTE option : elle peut être
    # absente (option sans aucune ligne panneau) alors que le devis, lui, porte
    # plusieurs modèles. On ne nomme alors aucune ligne plutôt que d'en inventer
    # une (et surtout plutôt que de planter sur ``None``).
    if len(identites) > 1 and dominante is not None:
        avertissements.append(
            'Ce devis porte %d modèles de panneau différents : l\'écart de '
            'calepinage sera appliqué à la ligne la plus grosse (« %s »).'
            % (len(identites), _nom(dominante)))

    panel_watt = None
    if dominante is not None:
        panel_watt = _pmax_wc_du_produit(dominante.produit)
        if not panel_watt:
            panel_watt = (_parse_watt(dominante.designation or '')
                          or _parse_watt(
                              getattr(dominante.produit, 'nom', '') or ''))

    if not panel_watt and panneaux > 0:
        # Dernier repli chiffré : la puissance de l'étude, divisée par le
        # nombre de panneaux réellement en ligne.
        etude = getattr(devis, 'etude_params', None) or {}
        try:
            kwc_etude = float(etude.get('puissance_kwc') or 0)
        except (TypeError, ValueError):
            kwc_etude = 0.0
        if kwc_etude > 0:
            panel_watt = int(round(kwc_etude * 1000 / panneaux / 10) * 10)

    if not panel_watt:
        panel_watt = CIBLE_WATT_DEFAUT
        if lignes_panneau:
            avertissements.append(
                'Puissance unitaire du panneau illisible (ni fiche technique '
                'ni wattage dans le libellé) : %d Wc retenus par défaut.'
                % CIBLE_WATT_DEFAUT)

    kwc = round(panneaux * panel_watt / 1000.0, 3) if panneaux else 0.0

    return {
        'panneaux': panneaux,
        'kwc': kwc,
        'panel_watt': int(panel_watt),
        'scenario': scenario,
        'batterie': bool(batterie),
        'avertissements': avertissements,
    }


# ── AOF164 — bascule du calcul résidentiel sur le MOTEUR PARTAGÉ ────────────
#
# Le compte de panneaux du devis résidentiel vient aujourd'hui du cerveau
# TypeScript de roofPro11 (``layout['result']['panels']``). Le moteur
# ``core/calepinage`` sait faire le même travail, en exact et avec sa preuve —
# mais on ne remplace pas un calcul en production sur une intuition : la
# bascule vit derrière un DRAPEAU (défaut OFF) et se juge sur des écarts
# JOURNALISÉS, pas sur une conviction.
#
# Trois invariants tiennent cette tâche :
#   * drapeau OFF -> comportement BIT-IDENTIQUE (retour immédiat, avant tout
#     appel moteur et avant toute écriture de journal) ;
#   * un devis DÉJÀ ÉMIS n'est jamais recalculé (voir
#     ``apps.ventes.selectors.comparaison_calepinage_devis``) ;
#   * une panne du moteur ne fait JAMAIS échouer une création de devis : on
#     journalise et on garde le compte historique.
#
# Les mots-clés de classification (panneau / onduleur réseau|injection|hybride
# / batterie) ne bougent pas : ils sont le contrat d'alignement avec
# ``quote_engine/builder.py`` dont dépend le découpage des options du PDF
# (CLAUDE.md, règle #4). Cette tâche ne touche QUE le COMPTE.

#: Nom du drapeau — lu par ``getattr`` pour que l'ABSENCE du réglage vaille OFF.
DRAPEAU_MOTEUR_CALEPINAGE = 'USE_MOTEUR_CALEPINAGE'

# ── PVG2 — garde de TOLÉRANCE sur l'arbitrage A/B (décision fondateur) ───────
#
# La bascule AOF164 remplaçait le compte historique par celui du moteur DÈS que
# le drapeau était levé, quelle que soit l'ampleur de l'écart. Un moteur qui
# lit mal une géométrie (un pan sans obstacle déclaré, un contour ouvert, une
# unité inattendue) pouvait donc, silencieusement, faire passer une villa de 12
# à 40 panneaux — et le devis partait ainsi.
#
# Décision du fondateur : SÉCURITÉ PAR DÉFAUT. Un petit écart est une
# correction (le moteur est plus fin que le cerveau TypeScript, c'est le but de
# la bascule) ; un GRAND écart est une ANOMALIE, et devant une anomalie on
# garde le compte historique et on ALERTE — jamais un remplacement silencieux.
#
# Deux tolérances, satisfaites en OU (l'une suffit) : un écart de quelques
# modules est absolu (une villa de 12 panneaux tolère ±2), un écart relatif
# couvre les grandes toitures (200 modules tolèrent ±5 %, soit ±10).
#: Écart ABSOLU toléré, en nombre de modules.
TOLERANCE_ARBITRAGE_MODULES = 2
#: Écart RELATIF toléré, en % du compte historique.
TOLERANCE_ARBITRAGE_PCT = 5.0


def _ecart_dans_la_tolerance(ancien, ecart):
    """L'écart moteur↔historique reste-t-il dans la tolérance PVG2 ?

    Vrai dès qu'UNE des deux tolérances est satisfaite (modules OU pourcentage).
    Un compte historique nul ou négatif n'a pas de pourcentage qui ait un sens :
    seule la tolérance en modules s'applique alors (jamais une division par 0).
    """
    ecart_abs = abs(int(ecart))
    if ecart_abs <= TOLERANCE_ARBITRAGE_MODULES:
        return True
    if ancien > 0:
        return (ecart_abs * 100.0 / ancien) <= TOLERANCE_ARBITRAGE_PCT
    return False


def moteur_calepinage_actif():
    """Le drapeau de bascule est-il levé ? ABSENT = OFF (jamais l'inverse)."""
    from django.conf import settings

    return bool(getattr(settings, DRAPEAU_MOTEUR_CALEPINAGE, False))


def _zone_villa_depuis_pan(pan):
    """``AreaRecord`` roofPro11 -> ``AreaRecord`` attendu par l'adaptateur villa.

    roofPro11 sérialise ``vertices: LngLat[]`` (``[lng, lat]``) et des obstacles
    ``{centerLng, centerLat, lengthM (nord-sud), widthM (est-ouest)}``.
    L'adaptateur d'AOF162 attend ``polygon`` / ``center`` / ``widthM`` /
    ``heightM`` avec ``heightM`` = étendue NORD-SUD : la correspondance est
    faite ICI, explicitement, et jamais devinée ailleurs.

    Rend ``None`` quand le pan ne porte pas de contour exploitable — un layout
    sans géométrie n'est pas une erreur, c'est simplement un cas où le moteur
    n'a rien à dire.
    """
    if not isinstance(pan, dict):
        return None
    sommets = pan.get('vertices') or pan.get('polygon') or pan.get('points')
    if not isinstance(sommets, (list, tuple)) or len(sommets) < 3:
        return None

    obstacles = []
    for brut in (pan.get('obstacles') or ()):
        if not isinstance(brut, dict):
            continue
        lng = brut.get('centerLng')
        lat = brut.get('centerLat')
        if lng is None or lat is None:
            continue
        obstacles.append({
            'id': brut.get('id') or 'OBS',
            'center': [lng, lat],
            # widthM = est-ouest (axe x du moteur villa) ;
            # lengthM = nord-sud (axe y).
            'widthM': brut.get('widthM') or 1.0,
            'heightM': brut.get('lengthM') or brut.get('heightM') or 1.0,
        })

    type_toit = (pan.get('roofType') or '').lower()
    pente = pan.get('pitchDeg')
    if pente is None:
        pente = pan.get('pitch') or 0.0
    azimut = pan.get('facingAzimuthDeg')
    if azimut is None:
        azimut = pan.get('aspect')
    return {
        'id': str(pan.get('id') or pan.get('label') or 'ZONE'),
        'polygon': [list(p) for p in sommets],
        'flat': type_toit != 'pitched',
        'tilt': float(pente or 0.0),
        'azimuth': float(azimut if azimut is not None else 180.0),
        'obstacles': obstacles,
    }


def _produit_panneau_du_devis(devis):
    """PV42 — le produit PANNEAU d'un devis EXISTANT, ou ``None``.

    Première ligne classée « panneau » qui porte une fiche produit (une ligne
    libre n'a pas de géométrie à donner au calepinage). Même classification que
    partout ailleurs — la désignation d'abord, le nom du produit ensuite.
    """
    if devis is None:
        return None
    for ligne in _lignes_produit(devis):
        if not _classe_ligne(ligne, _is_panel):
            continue
        produit = getattr(ligne, 'produit', None)
        if produit is not None:
            return produit
    return None


def _panneau_pour_calepinage(layout, *, company=None, devis=None):
    """PV42 — le PANNEAU sur lequel calepiner, et la société qui le scope.

    Deux sources, dans cet ordre : la ligne panneau du devis quand il en existe
    un (le module RÉELLEMENT vendu), sinon le catalogue de la société au
    wattage annoncé par le layout (``panelWatt``/``watt``, à défaut déduit du
    kWc) — la même sélection que celle qui composera les lignes du devis.

    Rend ``(produit, company_de_scoping)``. La société n'est rendue QUE si le
    produit lui appartient vraiment : un produit GLOBAL (``company`` nulle,
    catalogue partagé) passé avec une société ferait lever le garde-fou de
    ``kit_panneau_du_produit`` (« appartient à une autre société ») et on
    perdrait le kit réel pour rien. Aucun produit trouvé → ``(None, None)``,
    et le moteur retombe sur son kit villa par défaut.
    """
    produit = _produit_panneau_du_devis(devis)
    if produit is None and company is not None:
        layout = layout or {}
        watt = layout.get('panelWatt') or layout.get('watt')
        if not watt:
            result = dict(layout.get('result') or {})
            panneaux = int(result.get('panels') or 0)
            kwc = float(result.get('kwc') or 0.0)
            if panneaux and kwc:
                watt = int(round(kwc * 1000 / panneaux / 10) * 10)
        try:
            # PVMRQ — le devis (s'il en existe déjà un) donne sa gamme réelle ;
            # sans lui, ``marque_preferee`` retombe sur le slot Essentielle.
            produit = _pick_product(
                company, _is_panel, watt=watt, role='panneau',
                gamme=gamme_nom(devis) if devis is not None else None)
        except Exception:      # pragma: no cover - catalogue indisponible
            produit = None
    if produit is None:
        return None, None
    proprietaire = getattr(produit, 'company_id', None)
    if proprietaire is None:
        # Produit du catalogue GLOBAL : aucun scoping société à opposer.
        return produit, None
    return produit, company


def compte_moteur_du_layout(layout, *, company=None, devis=None):
    """Compte de modules rendu par le MOTEUR pour ce layout, ou ``None``.

    Somme les pans : chacun passe par ``apps.ao.selectors.calepinage_villa``
    (lecture cross-app sanctionnée — jamais ``apps.ao.models``), qui délègue au
    moteur partagé d'AOF163. Aucune ligne AO n'est créée.

    PV42 — ``company``/``devis`` servent à résoudre le PANNEAU réellement vendu
    et à le passer en ``produit_panneau`` (PV12) : le calepinage est alors posé
    sur la géométrie de CE module, plus sur le kit villa générique. Sans
    panneau résoluble (ni devis, ni société, ni catalogue), l'appel est
    strictement celui d'hier.

    Rend ``None`` (et jamais une exception) dès que la géométrie manque ou que
    le moteur refuse : l'appelant garde alors le compte historique.
    """
    pans = ((layout or {}).get('areas') or (layout or {}).get('zones')
            or (layout or {}).get('pans') or [])
    if not isinstance(pans, list) or not pans:
        return None

    from apps.ao.selectors import calepinage_villa

    produit_panneau, societe_panneau = _panneau_pour_calepinage(
        layout, company=company, devis=devis)

    modules = 0
    detail = []
    for pan in pans:
        zone = _zone_villa_depuis_pan(pan)
        if zone is None:
            continue
        try:
            sortie = calepinage_villa(zone, ordre='lnglat',
                                      produit_panneau=produit_panneau,
                                      company=societe_panneau)
        except Exception:
            logger.warning(
                'AOF164: le moteur a refusé le pan %s — compte historique '
                'conservé pour ce pan', zone.get('id'), exc_info=True)
            continue
        resultat = sortie['resultat']
        modules += int(resultat.modules)
        detail.append({
            'zone': zone['id'],
            'modules': int(resultat.modules),
            'hash_entree': resultat.hash_entree,
            'version_moteur': resultat.version_moteur,
            'methode': sortie['preuve']['methode'],
            'compte_optimal': sortie['preuve']['compte_optimal'],
        })
    if not detail:
        return None
    return {'modules': modules, 'pans': tuple(detail),
            'produit_panneau': getattr(produit_panneau, 'pk', None)}


def arbitrer_compte_calepinage(layout, compte_historique, *, company=None,
                               devis=None):
    """Compare ancien et nouveau compte et JOURNALISE l'écart, ou rend ``None``.

    ``None`` signifie « ne change rien » : drapeau baissé (cas par défaut,
    retour AVANT tout calcul et tout journal) ou moteur sans réponse.
    Sinon rend ``{'ancien', 'nouveau', 'ecart', 'retenu', 'pans',
    'hors_tolerance', 'motif'}``.

    ``retenu`` est le compte du MOTEUR tant que l'écart reste DANS la tolérance
    PVG2 (``TOLERANCE_ARBITRAGE_MODULES`` modules OU ``TOLERANCE_ARBITRAGE_PCT``
    %) — c'est le sens même de la bascule. Au-delà, l'écart n'est plus une
    correction mais une ANOMALIE : ``retenu`` reste le compte HISTORIQUE,
    ``hors_tolerance`` vaut ``True``, et l'écart part en ``logger.warning`` avec
    les DEUX comptes et la référence du devis. Jamais un remplacement
    silencieux, jamais une exception (décision fondateur : sécurité par défaut).

    PV42 — ``company``/``devis`` sont transmis au moteur pour qu'il calepine sur
    le panneau réellement vendu (PV12).
    """
    if not moteur_calepinage_actif():
        return None
    try:
        mesure = compte_moteur_du_layout(layout, company=company, devis=devis)
    except Exception:
        # Une panne du moteur ne fait JAMAIS échouer une création de devis :
        # on journalise et on garde le compte historique.
        logger.warning('AOF164: moteur indisponible — compte historique '
                       'conservé pour ce devis', exc_info=True)
        return None
    if mesure is None:
        return None
    ancien = int(compte_historique or 0)
    nouveau = int(mesure['modules'])
    ecart = nouveau - ancien
    logger.info(
        'AOF164: bascule moteur ACTIVE — compte TypeScript %d, compte moteur '
        '%d, écart %+d (%d pan(s) calepiné(s))',
        ancien, nouveau, ecart, len(mesure['pans']))

    # PVG2 — garde de tolérance : au-delà, on GARDE le compte historique et on
    # alerte (le journal porte les deux comptes + la référence, pour que
    # l'anomalie soit diagnosticable sans rejouer le calcul).
    if not _ecart_dans_la_tolerance(ancien, ecart):
        motif = 'écart au-delà de la tolérance — compte historique conservé'
        logger.warning(
            'PVG2: %s (devis %s) : compte TypeScript %d, compte moteur %d, '
            'écart %+d — tolérance %d module(s) ou %.1f %%',
            motif, getattr(devis, 'reference', '?') or '?', ancien, nouveau,
            ecart, TOLERANCE_ARBITRAGE_MODULES, TOLERANCE_ARBITRAGE_PCT)
        return {'ancien': ancien, 'nouveau': nouveau, 'ecart': ecart,
                'retenu': ancien, 'pans': mesure['pans'],
                'hors_tolerance': True, 'motif': motif}

    return {'ancien': ancien, 'nouveau': nouveau, 'ecart': ecart,
            'retenu': nouveau, 'pans': mesure['pans'],
            'hors_tolerance': False, 'motif': ''}


def concevoir_electrique_du_devis(devis, *, origine=''):
    """PV42 — enchaîne la conception ÉLECTRIQUE derrière le calepinage, SANS
    jamais pouvoir casser le devis.

    Le calepinage vient d'être rangé dans ``roof_layout`` : ses pans
    (``_pans_geometry``) sont exactement ce que ``electrical_service`` attend
    pour composer UN GROUPE DE CHAÎNES PAR PAN — deux orientations ne partagent
    jamais une entrée MPPT (le moteur PV34 le refuse structurellement).

    **Meilleur effort, et c'est structurel** : une panne d'étude électrique est
    une pièce technique manquante, jamais une création (ou une resynchro) de
    devis perdue. Toute exception est journalisée et avalée, et la fonction rend
    ``None``. Elle n'écrit que ``electrical_design``/``electrical_design_hash``
    (règle #4 : aucun statut, aucune ligne, aucun prix).
    """
    try:
        from apps.ventes import electrical_service
        return electrical_service.build_electrical_design(devis)
    except Exception:
        logger.warning(
            'PV42: conception électrique indisponible pour le devis %s (%s) — '
            'le devis est intact, la pièce technique sera recalculée à la '
            'demande', getattr(devis, 'reference', '?'), origine or 'layout',
            exc_info=True)
        return None


# ── PVKIT — la composition RÉSIDENTIELLE COMPLÈTE (port de solar.js) ─────────
#
# Un devis issu du calepinage ne composait jusqu'ici qu'un SQUELETTE : le
# panneau, l'onduleur, et la batterie quand le scénario en veut une. Ce n'est
# pas ce qui est vendu. Le kit réel — celui de l'ancien simulateur, porté à
# l'écran par ``autoFillLines`` (frontend/src/features/ventes/solar.js) — porte
# aussi les structures de fixation, les socles, les accessoires (câblage DC/AC,
# connecteurs), le tableau de protection AC/DC, l'installation, le transport et,
# DERRIÈRE UN ONDULEUR HUAWEI SEULEMENT, le Smart Meter et la clé Wifi.
#
# Ce bloc est le port Python FIDÈLE de ``autoFillLines`` : mêmes classes de
# mots-clés (alignées sur ``quote_engine/builder.py`` — règle du dépôt, le
# découpage des options du PDF en dépend), mêmes règles de quantités, mêmes
# paliers de prix par blocs de 5 kWc, même choix de structure. Trois écarts,
# assumés et seulement trois :
#
#   1. **Les lignes à quantité nulle ne sont pas enregistrées.** L'écran les
#      affiche pour qu'on puisse les saisir ; ``autoFillLines`` le dit mot pour
#      mot dans son propre en-tête (« lignes à quantité nulle comprises — elles
#      s'affichent mais ne sont pas enregistrées »). Un devis, lui, n'écrit que
#      ce qu'il vend.
#   2. **Le scénario tranche entre les deux onduleurs.** L'écran propose les
#      deux options côte à côte (option 1 sans batterie / option 2 avec) et les
#      totaux les séparent au moment de l'affichage ; un devis construit depuis
#      un calepinage a DÉJÀ choisi. On ne quote donc qu'un onduleur, et les
#      batteries ne suivent que le scénario batterie.
#   3. **Un produit SANS PRIX n'entre JAMAIS dans le kit** (garde ``_has_price``,
#      règle du dépôt) ; l'écran, lui, affiche une ligne à 0 à compléter.
#
# Un composant absent du catalogue est SAUTÉ, jamais fatal : le kit se dégrade
# proprement (c'est exactement ce que fait l'écran avec un produit introuvable).
# Le panneau, lui, reste gardé EN AMONT par ``validate_composition_for_layout``
# — un devis sans panneau est une erreur 422 explicite, pas un kit silencieux.

#: Une ligne composée, prête à devenir une ``LigneDevis``. ``prix_unitaire``
#: est TOUJOURS un montant **HT** (le modèle stocke du HT ; le simulateur
#: raisonne en TTC, la conversion se fait dans la composition).
#:
#: L-2OPT — ``variante`` dit à QUELLE option la ligne appartient ('' = commune
#: aux deux, 'sans' / 'avec' = propre à cette option-là). Le champ porte un
#: DÉFAUT VIDE : tout appelant historique construit sa ``LigneKit`` sans le
#: mentionner et obtient exactement la ligne d'hier.
LigneKit = namedtuple('LigneKit',
                      'produit designation quantite prix_unitaire variante',
                      defaults=('',))

#: L-2OPT — les trois valeurs de ``LigneDevis.variante`` / ``LigneKit.variante``.
#: Répétées ici (chaînes nues) plutôt qu'importées de ``models`` : ce module
#: n'importe les modèles qu'en local, dans les fonctions.
VARIANTE_COMMUNE = ''
VARIANTE_SANS = 'sans'
VARIANTE_AVEC = 'avec'


class CompositionLignes(list):
    """U3 — le résultat de ``composition_residentielle``.

    C'est une LISTE de ``LigneKit`` (tout appelant historique la parcourt sans
    rien changer) qui porte EN PLUS les métadonnées de la composition. Une
    liste nue ne peut pas porter d'attribut : c'est la seule raison de cette
    sous-classe, et c'est ce qui permet au dry-run de rendre à l'écran ce que
    le serveur a réellement décidé (wattage retenu, kWc réel, marques
    introuvables) au lieu de le laisser le recalculer de son côté.
    """

    roles = ()
    nb_panneaux = 0
    panel_watt_reel = 0
    kwc_reel = 0.0
    blocs = 1
    marques_manquantes = ()
    # ── L-2OPT — métadonnées de la composition FUSIONNÉE (deux optimiseurs) ──
    # ``variantes`` reste False sur toute composition d'hier : une composition
    # mono-optimum n'a que des lignes communes. Les deux clés ``_avec`` ne
    # valent quelque chose que quand l'optimum AVEC batterie a choisi un AUTRE
    # champ PV que l'optimum SANS.
    variantes = False
    nb_panneaux_avec = 0
    kwc_reel_avec = 0.0


def ordonner_par_role(taguees, ordre_lignes):
    """PVORD — trie des couples ``(rôle, objet)`` selon une séquence de rôles.

    Miroir EXACT de ``solar.js::orderLinesByRolePreference`` : un rôle PRÉSENT
    dans ``ordre_lignes`` est classé à sa position ; un rôle ABSENT garde son
    rang canonique mais TOUJOURS après tout rôle explicitement préféré. Tri
    STABLE — les deux lignes « batterie » (5 / 10 kWh) gardent leur ordre
    relatif. Séquence absente ou vide : la liste est rendue TELLE QUELLE
    (ordre canonique du simulateur, comportement historique).
    """
    couples = list(taguees or [])
    if not isinstance(ordre_lignes, (list, tuple)) or not ordre_lignes:
        return couples
    rangs = {}
    for position, role in enumerate(ordre_lignes):
        rangs.setdefault(role, position)
    grand = len(couples) + len(ordre_lignes) + 1
    return sorted(
        couples,
        key=lambda couple: rangs.get(couple[0], grand))


def avertissement_vivier_batterie_vide(plage):
    """Le message FRANÇAIS d'un vivier batterie VIDE sous un onduleur à plage.

    Une seule formulation, partagée par tous les chemins qui savent avertir
    (composition, resynchronisation de calepinage, pré-vol de composition) :
    le commercial doit lire la MÊME phrase quel que soit le bouton utilisé."""
    if plage and plage[1] > 0:
        return ('Aucune batterie compatible tarifée pour cet onduleur '
                '(plage %s-%s V) : le devis a été composé SANS batterie. '
                'Ajoutez une batterie compatible au catalogue, ou changez '
                'd\'onduleur.' % (_v_txt(plage[0]), _v_txt(plage[1])))
    return ('Aucune batterie tarifée au catalogue : le devis a été composé '
            'SANS batterie. Ajoutez une batterie tarifée.')


def avertissement_batterie_rupture_stock():
    """BATHOMO/F5 (fondateur 26/08/2026) — message DISTINCT de
    ``avertissement_vivier_batterie_vide`` : ici, une (ou plusieurs)
    batterie(s) COMPATIBLE(S) existent (le couple électrique est bon) mais
    leur STOCK est à 0. Conflater ce cas avec « aucune batterie compatible »
    enverrait le commercial vers le mauvais correctif (« changez d'onduleur »
    quand le vrai geste est de réapprovisionner, ou de choisir un autre
    module déjà en stock)."""
    return ('Batterie(s) compatibles en rupture de stock : le devis a été '
            'composé SANS batterie. Réapprovisionnez, ou choisissez un '
            'autre module batterie.')


def avertissement_batterie_plafond_banc():
    """BATHOMO/F3 (fondateur 26/08/2026) — message DISTINCT des deux
    précédents : des batteries compatibles ET en stock existent, mais
    ``bat_max_modules_par_banc`` (le plafond fondateur de modules par
    banque) a rejeté TOUTES les candidates homogènes pour cette cible —
    jamais une banque tronquée, jamais un « avec batterie » qui part sans
    aucune batterie sans le dire."""
    return ('Aucune banque batterie ne respecte le plafond de modules par '
            'banc pour cette cible : le devis a été composé SANS batterie. '
            'Augmentez le plafond, ou choisissez un autre module.')


def avertissement_batterie_pin_sans_correspondance(calibre_impose):
    """A1 (revue adversariale Fable, 26/08/2026) — message DISTINCT des trois
    précédents : le devis vend DÉJÀ un calibre précis (``batterie_module_
    kwh``, lu par ``dimensionnement.module_batterie_du_devis``), mais AUCUNE
    batterie de ce calibre n'existe dans le vivier COMPATIBLE — ni stock, ni
    plafond en cause, le calibre lui-même n'est pas composable sous cet
    onduleur (ex. un système haute tension jamais compatible avec un
    hybride basse tension). « Honest absence beats a wrong pairing » :
    repeindre la banque dans un AUTRE calibre que celui déjà vendu serait
    exactement la violation que ce chantier ferme — la composition part
    donc SANS batterie plutôt que dans un calibre que ce devis ne vend pas."""
    return ('Le module batterie déjà vendu sur ce devis (%s kWh) ne '
            'correspond à aucune batterie du vivier compatible : le devis a '
            'été composé SANS batterie plutôt que dans un autre calibre. '
            'Vérifiez le catalogue, ou la compatibilité électrique de ce '
            'module avec l\'onduleur retenu.' % _v_txt(calibre_impose))


def _v_txt(volts):
    """« 160.0 » → « 160 » (une tension entière ne s'écrit pas avec un ,0)."""
    try:
        f = float(volts)
    except (TypeError, ValueError):
        return str(volts)
    return str(int(f)) if f == int(f) else ('%g' % f)


def avertissement_aucun_onduleur_triphase():
    """L-TRI — le message FRANÇAIS d'un client TRIPHASÉ sans onduleur triphasé.

    Une seule formulation, comme ``avertissement_vivier_batterie_vide`` : le
    commercial doit lire la MÊME phrase quel que soit le bouton utilisé. Elle
    dit la seule chose vraie — la composition a été REFUSÉE, il manque une
    référence au catalogue — et surtout PAS « composition en monophasé à
    valider » : un onduleur monophasé n'est pas une solution dégradée pour un
    client triphasé, c'est une erreur de devis (ordre fondateur 24/08/2026).
    """
    return ('Raccordement TRIPHASÉ déclaré — aucun onduleur TRIPHASÉ '
            'disponible au catalogue : la composition a été REFUSÉE plutôt '
            'que de coter un onduleur monophasé. Ajoutez un onduleur '
            'triphasé (tarifé, fiche technique complète) au catalogue.')


def _vivier_onduleurs_par_phase(candidats, phase):
    """PVCOMPAT — restreint un vivier d'onduleurs au RACCORDEMENT du client.

    Le client déclare son raccordement sur sa fiche lead (``raccordement``), et
    jusqu'ici la composition l'ignorait complètement : un client MONOPHASÉ
    pouvait se voir composer un onduleur triphasé — impossible à raccorder chez
    lui, donc un devis à refaire.

    Deux traitements DIFFÉRENTS, et c'est voulu :

    * ``monophase`` — les triphasés sont ÉCARTÉS du vivier (on ne raccorde pas
      du triphasé sur un abonnement monophasé). Si cela vide le vivier, on rend
      le vivier D'ORIGINE et on le DIT : mieux vaut un devis à valider qu'aucun
      onduleur du tout (même principe que ``_filtrer_onduleurs_complets`` : un
      verrou qui vide la table est une panne).
    * ``triphase`` — L-TRI (incident fondateur 24/08/2026 : « pourquoi j'ai du
      mono alors que le client est tri ») — les monophasés sont ÉCARTÉS, sans
      AUCUN repli. La préférence tri d'hier n'était qu'un départage À PUISSANCE
      ÉGALE (``choisir_onduleur``) : dès que le premier palier triphasé du
      catalogue (10 kW) était plus GROS que le plus petit modèle ≥ 80 % du kWc,
      le monophasé gagnait — un client triphasé se voyait coter un « Onduleur
      réseau Huawei 5kW Monophasé ». Le vivier est donc TRIPHASÉ EXCLUSIVEMENT :
      un petit kWc prend le plus petit triphasé du catalogue, même très
      surdimensionné (la règle des 80 % est un PLANCHER, jamais une raison de
      retomber en monophasé), et un catalogue sans triphasé ne compose AUCUN
      onduleur — le refus est annoncé par ``choisir_onduleur``.

    Rend ``(vivier, a_replie)``. ``a_replie`` reste le drapeau du SEUL repli qui
    subsiste, celui du monophasé. ``phase`` vide/inconnue ⇒ vivier inchangé,
    donc comportement d'avant à l'octet près.
    """
    from apps.ventes.compatibilites import (
        PHASE_MONO, PHASE_TRI, est_triphase_produit)
    source = list(candidats or [])
    if phase == PHASE_TRI:
        # Jamais de repli : un vivier vide vaut mieux qu'une ligne monophasée.
        return [p for p in source if est_triphase_produit(p)], False
    if phase != PHASE_MONO:
        return source, False
    monophases = [p for p in source if not est_triphase_produit(p)]
    if monophases:
        return monophases, False
    return source, True


def _statut_couple_panneau(panneau, onduleurs):
    """PVCOMPAT — le PIRE verdict d'un panneau face aux onduleurs VENDUS.

    En forme deux options les DEUX onduleurs partent au devis : un panneau qui
    coince avec l'un des deux coince pour le devis entier. L'ordre de sévérité
    est celui du noyau — ``incompatible`` (bloquant matériel) l'emporte sur
    ``reserve`` (production dégradée), qui l'emporte sur ``inconnu`` (fiche
    incomplète), qui l'emporte sur ``compatible``.
    """
    from apps.ventes.compatibilites import (
        STATUT_COMPATIBLE, STATUT_INCOMPATIBLE, STATUT_INCONNU,
        STATUT_RESERVE, verdict_panneau_onduleur)
    severite = {STATUT_INCOMPATIBLE: 3, STATUT_RESERVE: 2,
                STATUT_INCONNU: 1, STATUT_COMPATIBLE: 0}
    pire = (0, STATUT_COMPATIBLE, None)
    for onduleur in onduleurs:
        verdict = verdict_panneau_onduleur(panneau, onduleur)
        rang = severite.get(verdict['statut'], 0)
        if rang > pire[0]:
            pire = (rang, verdict['statut'], (onduleur, verdict))
    return pire[1], pire[2]


def composition_residentielle(produits, *, kwc, panel_watt, nb_panneaux=0,
                              avec_batterie=False, structure_type='acier',
                              taux_tva=Decimal('20'), avertissements=None,
                              deux_options=False, marques=None,
                              ordre_lignes=None, mppt_paires=1, phase=None,
                              batterie_cible_kwh=None,
                              batterie_module_kwh=None):
    """Le KIT résidentiel COMPLET composé depuis un catalogue.

    U3 (fondateur 20/08/2026) — CETTE FONCTION EST LA SOURCE DE VÉRITÉ de la
    composition résidentielle. Elle porte désormais TOUTES les règles qui
    n'existaient que dans ``solar.js::autoFillLines`` :

      · ``marques`` — PVMRQ, carte ``{rôle: marque}`` DÉJÀ résolue par
        l'appelant (via ``marque_preferee``, seule voie de lecture du réglage
        gammes ; cette fonction reste PURE et ne requête rien). Une marque
        épinglée restreint le vivier de son rôle À ELLE SEULE ; sans candidat,
        le vivier est VIDE — jamais un repli silencieux sur une autre marque —
        et le rôle est consigné dans ``.marques_manquantes``.
      · ``ordre_lignes`` — PVORD, séquence de rôles préférée ; absente, l'ordre
        canonique du simulateur est rendu tel quel.
      · ``mppt_paires`` — C4/PVCBL, nombre de paires de câble DC descendantes
        (60 m par paire) ; repli fondateur explicite à 1 paire.
      · ``phase`` — PVCOMPAT, le RACCORDEMENT déclaré par le client
        (``'monophase'`` / ``'triphase'``, cf.
        ``compatibilites.normaliser_phase``). Monophasé : les onduleurs
        triphasés sortent du vivier ; triphasé : le départage à puissance égale
        préfère DUREMENT le triphasé. ``None`` (défaut) ⇒ aucun filtre, donc
        comportement byte-identique à l'historique.

    PVCOMPAT (fondateur 20/08/2026) — LE COUPLE PANNEAU/ONDULEUR EST VÉRIFIÉ.
    Le panneau et l'onduleur étaient choisis INDÉPENDAMMENT (l'un au wattage
    demandé, l'autre à la puissance) et rien ne vérifiait qu'ils allaient
    ensemble : « il n'y a pas de PV parce que le courant maxi par MPPT de cet
    onduleur est sous le courant de nos panneaux » ne pouvait pas être dit. Le
    verdict du noyau électrique est désormais consulté APRÈS les deux choix :
    un couple INCOMPATIBLE fait chercher un autre panneau du vivier (marque
    épinglée respectée) ; à défaut, le choix d'origine est CONSERVÉ — jamais
    une composition morte — et le problème est ANNONCÉ par ``avertissements``.

    Le résultat est une ``CompositionLignes`` : une LISTE de ``LigneKit`` (tout
    appelant historique la lit sans rien changer) qui porte en plus les
    métadonnées de la composition (``nb_panneaux``, ``panel_watt_reel``,
    ``kwc_reel``, ``roles``, ``marques_manquantes``) — le dry-run les rend à
    l'écran.

    ``deux_options`` (U2, fondateur 20/08/2026) — compose la forme DEUX
    OPTIONS que la proposition résidentielle rend déjà : les DEUX onduleurs
    (réseau ET hybride) et les batteries dans UN seul devis. C'est le
    découpage que lisent ``optionTotalsTTC`` (écran) et le moteur PDF :
      · option « sans batterie » = tout SAUF batterie + onduleur hybride ;
      · option « avec batterie »  = tout SAUF onduleur réseau.
    Le client compare, puis choisit. Sans ce drapeau (défaut), la composition
    reste MONO-OPTION et byte-identique à l'historique : ``avec_batterie``
    décide seul quel onduleur est vendu — c'est ce que veut le calepinage 3D,
    où le scénario a DÉJÀ été arrêté à l'écran.

    Fonction PURE : elle ne requête rien, n'écrit rien, ne touche aucun statut.
    ``produits`` est un itérable de produits DÉJÀ cantonnés à la société
    appelante (voir ``catalogue_de_la_societe``) ; les produits sans prix de
    vente en sont écartés d'entrée de jeu.

    ``taux_tva`` — le taux du DEVIS. Il servait à reconvertir en HT les trois
    prix forfaitaires que le simulateur exprimait en TTC ; depuis L-FORFAIT
    (fondateur 24/08/2026) ces forfaits sont dictés EN HT et lus au catalogue
    (``stock.Produit.prix_fixe_ht`` / ``prix_par_panneau_ht``), donc plus rien
    ici ne convertit quoi que ce soit. Le paramètre est CONSERVÉ — tous les
    appelants le passent et la TVA reste celle du devis — mais il n'influence
    plus aucun montant composé.

    ``batterie_cible_kwh`` (DIM2, fondateur 24/08/2026) — capacité de stockage
    VISÉE, en kWh, servie par les modules du catalogue. ``None`` (LE DÉFAUT,
    épinglé par un test) ⇒ la règle historique du simulateur reste seule maître
    à bord : ``cible = max(5, arrondi(kwp / 5) × 5)``. **Le devis automatique ne
    passe JAMAIS ce paramètre** : sa batterie reste une conséquence des kWc,
    exactement comme avant. Seul le TABLEAU de dimensionnement
    (``apps.ventes.dimensionnement``) l'utilise, pour EXPLORER le stockage comme
    une deuxième dimension et montrer au fondateur ce qu'une banque plus grande
    changerait — explorer n'est pas décider.

    ``batterie_module_kwh`` (BATHOMO, fondateur 26/08/2026 — « if the quote has
    5 kWh batteries the web page should only show 5 kWh batteries ; and we can
    go up to 30 or 40 kWh using 5 kWh batteries, no problem ») — IMPOSE le
    calibre (``5`` ou ``10``) de la banque, plutôt que de laisser le choix « au
    plus proche de la cible » ci-dessous décider. Un appelant qui connaît déjà
    le module RÉELLEMENT engagé par un devis (lu sur ses LIGNES vendues, jamais
    redeviné ici) l'impose ainsi pour toute l'échelle qu'il explore : la banque
    grandit alors en N modules de CE calibre — jusqu'à 6-8 packs de 5 kWh pour
    atteindre 30-40 kWh — sans jamais glisser vers l'autre calibre au passage
    d'un multiple de 10 (où le choix « au plus proche » préfère normalement le
    plus gros module). ``None`` (LE DÉFAUT) ⇒ comportement inchangé : le
    calibre le plus proche de ``cible_kwh`` décide, égalité tranchée pour le
    plus gros. Calibre imposé absent du catalogue ⇒ repli silencieux sur ce
    même choix « au plus proche » — jamais une banque vide du seul fait d'un
    calibre non stocké.

    ``avertissements`` (optionnel) est LE CANAL de cette fonction : une liste
    que l'appelant fournit et que la composition enrichit sur place quand elle
    a dû composer AUTREMENT que demandé — aujourd'hui le seul cas est un vivier
    batterie VIDE alors que ``avec_batterie`` était demandé. Sans ce canal, un
    devis « avec batterie » pouvait partir SANS aucune ligne batterie et sans
    que personne ne l'apprenne. Absent (``None``) ⇒ comportement inchangé.

    Rend la liste ORDONNÉE des ``LigneKit`` à créer, dans l'ordre canonique du
    simulateur, quantités nulles exclues. Liste vide si la puissance est nulle.
    """
    kwp = float(kwc or 0)
    if kwp <= 0:
        return []
    watt = float(panel_watt or 0) or 550.0

    # Catalogue indexé par catégorie. Le filtre de prix passe ICI, une fois
    # pour toutes : aucune branche ne peut ensuite coter un produit non tarifé.
    par_type = {}
    for produit in produits:
        if not _has_price(produit):
            continue
        categorie = classer_produit(getattr(produit, 'nom', ''))
        if categorie:
            par_type.setdefault(categorie, []).append(produit)

    # ── PVMRQ (U3) — restriction par marque épinglée ────────────────────────
    # Miroir EXACT de ``_filtrerParMarque`` (solar.js) : sans préférence, le
    # vivier passe TEL QUEL ; avec une préférence sans aucun candidat, le
    # vivier est VIDE et le rôle est consigné UNE fois (jamais un repli
    # silencieux sur une autre marque — ordre fondateur #5).
    carte_marques = marques if isinstance(marques, dict) else {}
    marques_manquantes = []
    _roles_signales = set()

    def par_marque(pool, role):
        source = list(pool or [])
        marque = str(carte_marques.get(role) or '').strip()
        if not marque:
            return source
        filtres = [p for p in source if _marque_correspond(p, marque)]
        if not filtres and role not in _roles_signales:
            _roles_signales.add(role)
            marques_manquantes.append({'role': role, 'marque': marque})
        return filtres

    def premier(categorie):
        pool = par_marque(par_type.get(categorie), categorie)
        return pool[0] if pool else None

    # ── Panneaux : compte explicite, sinon dérivé de la puissance ──
    # U1 — dérivation AU PLAFOND (``plafond_panneaux``) : 5 kWc en 710 Wc font
    # 8 panneaux, jamais 7. Un compte fourni explicitement est déjà un ENTIER
    # de panneaux ; il garde son arrondi au plus proche.
    nb = (_arrondi_js(nb_panneaux) if float(nb_panneaux or 0) > 0
          else max(1, plafond_panneaux(kwp * 1000 / watt)))

    # ── Onduleur : plus petit modèle ≥ 80 % de la puissance, sinon le plus
    # gros du catalogue ; à puissance égale, Triphasé au-delà de 10 kW ──
    seuil = kwp * 0.8

    # PVCOMPAT — le raccordement déclaré, normalisé une seule fois.
    from apps.ventes.compatibilites import (
        PHASE_MONO, PHASE_TRI, avertissement_raccordement, normaliser_phase)
    phase_client = normaliser_phase(phase)

    def _avertir(message):
        """Consigne un avertissement UNE fois (deux onduleurs, un message)."""
        if avertissements is None:
            logger.warning('PVCOMPAT: %s', message)
            return
        if message not in avertissements:
            avertissements.append(message)

    # PVCOMPAT — catégories dont le vivier a dû IGNORER le raccordement
    # déclaré. On ne prévient PAS ici : les deux catégories sont toujours
    # explorées (réseau ET hybride) alors qu'une seule part au devis en forme
    # mono-option — avertir depuis le vivier ferait crier l'onduleur invendu.
    # Le message est prononcé plus bas, pour les seules catégories VENDUES.
    replis_phase = {}
    # L-TRI — catégories dont le vivier TRIPHASÉ est VIDE alors que le client
    # est triphasé : la composition a REFUSÉ de coter un monophasé. Même
    # discipline que ``replis_phase`` — on ne prononce le message que pour les
    # catégories réellement VENDUES.
    refus_tri = {}

    def choisir_onduleur(categorie):
        candidats = []
        # PVOND — VERROU DE COMPLÉTUDE, miroir de solar.js::pickInverter : un
        # onduleur au contrat incomplet est écarté de l'auto-composition AVANT
        # le tri par puissance, exactement comme à l'écran.
        # PVCOMPAT/L-TRI — puis le RACCORDEMENT du client réduit le vivier :
        # monophasé (les triphasés sortent, repli toléré) comme triphasé (les
        # monophasés sortent, AUCUN repli).
        complets = _filtrer_onduleurs_complets(
            par_marque(par_type.get(categorie), categorie))
        vivier, replie = _vivier_onduleurs_par_phase(complets, phase_client)
        replis_phase[categorie] = replie
        refus_tri[categorie] = False
        for produit in vivier:
            kw = _parse_kw(getattr(produit, 'nom', ''))
            if kw and kw > 0:
                candidats.append((kw, getattr(produit, 'id', 0) or 0, produit))
        if not candidats:
            # L-TRI — distinguer « catalogue vide pour cette catégorie »
            # (silence historique) de « il y avait des onduleurs, mais AUCUN
            # triphasé » : ce second cas est un REFUS, et un refus se dit.
            refus_tri[categorie] = bool(
                phase_client == PHASE_TRI and complets)
            return None, None
        candidats.sort(key=lambda c: (c[0], c[1]))
        # Le plus petit modèle ≥ 80 % du kWc : sur un vivier déjà réduit au
        # raccordement du client, ce PLANCHER ne peut plus faire changer de
        # phase — un petit kWc prend simplement le plus petit triphasé.
        valides = [c for c in candidats if c[0] >= seuil] or [candidats[-1]]
        meilleure = valides[0][0]
        memes = [c for c in valides if c[0] == meilleure]
        # PVCOMPAT — un raccordement DÉCLARÉ passe devant l'heuristique
        # « ≥ 10 kW ⇒ triphasé » : le client sait de quel abonnement il dispose,
        # la puissance n'en est qu'un indice. Sans déclaration, l'heuristique
        # historique décide seule, à l'identique.
        if phase_client == PHASE_TRI:
            prefere_tri = True
        elif phase_client == PHASE_MONO:
            prefere_tri = False
        else:
            prefere_tri = meilleure >= 10
        assortis = [c for c in memes
                    if _est_triphase(getattr(c[2], 'nom', '')) == prefere_tri]
        retenu = (assortis or memes)[0]
        return retenu[2], retenu[0]

    def quantite_onduleur(kw):
        """Un onduleur suffit dès qu'il couvre le seuil ; sinon on en met assez
        pour absorber le champ (blocs entiers, jamais moins d'un)."""
        if not kw or kw >= seuil:
            return 1
        return max(1, int(math.ceil(kwp / kw)))

    onduleur_reseau, kw_reseau = choisir_onduleur('onduleur_reseau')
    onduleur_hybride, kw_hybride = choisir_onduleur('onduleur_hybride')
    onduleur = onduleur_hybride if avec_batterie else onduleur_reseau
    kw_onduleur = kw_hybride if avec_batterie else kw_reseau

    # PVCOMPAT — le raccordement n'a pas pu être tenu SUR UN ONDULEUR VENDU :
    # on le dit UNE fois. Un repli sur une catégorie qui ne part pas au devis
    # (l'hybride d'un devis « sans batterie », par exemple) ne concerne
    # personne et reste muet.
    _categories_vendues = (
        ('onduleur_reseau', 'onduleur_hybride') if deux_options
        else (('onduleur_hybride',) if avec_batterie
              else ('onduleur_reseau',)))
    _onduleurs_par_categorie = {'onduleur_reseau': onduleur_reseau,
                                'onduleur_hybride': onduleur_hybride}
    if phase_client and any(
            replis_phase.get(categorie)
            and _onduleurs_par_categorie.get(categorie) is not None
            for categorie in _categories_vendues):
        _avertir(avertissement_raccordement(PHASE_MONO))
    # L-TRI — le raccordement TRIPHASÉ n'a AUCUN onduleur au catalogue sur une
    # catégorie VENDUE : la composition part sans onduleur (jamais un
    # monophasé), et elle le DIT — sinon le devis mentirait par omission.
    if phase_client == PHASE_TRI and any(
            refus_tri.get(categorie) for categorie in _categories_vendues):
        _avertir(avertissement_aucun_onduleur_triphase())
    # U2 — en forme DEUX OPTIONS, le stockage fait partie du devis : les
    # batteries sont composées même si ``avec_batterie`` est faux, puisque
    # c'est l'option « avec » qui les porte.
    veut_batterie = bool(avec_batterie or deux_options)

    # ── Panneau : wattage demandé d'abord, à défaut le plus proche ──
    # PVMRQ — la marque épinglée restreint le vivier AVANT le rapprochement de
    # wattage : la substitution « wattage le plus proche » ne joue plus que
    # DANS la marque retenue, jamais hors d'elle (miroir de l'écran).
    tries = []
    for produit in par_marque(par_type.get('panneau'), 'panneau'):
        w = _parse_watt(getattr(produit, 'nom', ''))
        if w is not None:
            tries.append((w, produit))
    exacts = [c for c in tries if c[0] == int(watt)]
    if exacts:
        # Même départage qu'à l'écran : un Canadien Solar passe devant.
        exacts.sort(key=lambda c: 0 if 'canadien' in _sans_accents(
            getattr(c[1], 'nom', '')) else 1)
        panneau = exacts[0][1]
    elif tries:
        panneau = min(tries, key=lambda c: abs(c[0] - watt))[1]
    else:
        panneau = None

    # ── PVCOMPAT — LE COUPLE PANNEAU / ONDULEUR EST VÉRIFIÉ ────────────────
    # Les deux choix ci-dessus sont INDÉPENDANTS : rien ne garantissait qu'ils
    # allaient ensemble. On demande au noyau électrique son verdict et on agit
    # SANS JAMAIS produire une composition morte :
    #   · incompatible → on cherche un autre panneau du vivier (le vivier DÉJÀ
    #     restreint par la marque épinglée : on ne contourne pas une consigne
    #     de gamme pour réparer une incompatibilité) ; si aucun ne va, on GARDE
    #     le choix d'origine et on DIT le problème ;
    #   · réserve      → on garde et on DIT (écrêtage : ça s'installe, ça
    #     produit moins — le client doit l'apprendre du devis, pas du toit) ;
    #   · inconnu      → on se tait : la fiche incomplète est déjà signalée
    #     ailleurs (verrou de complétude), le répéter ne dirait rien de neuf.
    onduleurs_vendus = [o for o in (
        (onduleur_reseau, onduleur_hybride) if deux_options else (onduleur,))
        if o is not None]
    if panneau is not None and onduleurs_vendus:
        from apps.ventes.compatibilites import (
            STATUT_INCOMPATIBLE, STATUT_RESERVE,
            avertissement_panneau_onduleur)
        statut, coince = _statut_couple_panneau(panneau, onduleurs_vendus)
        if statut == STATUT_INCOMPATIBLE:
            # Repli ORDONNÉ : d'abord les wattages exacts (l'ordre de départage
            # de l'écran), puis les plus proches — la même préférence que le
            # choix initial, appliquée aux candidats restants.
            replis = [c[1] for c in exacts] + [
                c[1] for c in sorted(tries, key=lambda c: abs(c[0] - watt))]
            vus = set()
            for candidat in replis:
                if id(candidat) in vus or candidat is panneau:
                    vus.add(id(candidat))
                    continue
                vus.add(id(candidat))
                statut_bis, coince_bis = _statut_couple_panneau(
                    candidat, onduleurs_vendus)
                if statut_bis != STATUT_INCOMPATIBLE:
                    _avertir(
                        'Panneau remplacé pour compatibilité électrique : '
                        '« %s » ne se raccorde pas à l\'onduleur retenu, '
                        '« %s » a été composé à la place.'
                        % (getattr(panneau, 'nom', '') or '?',
                           getattr(candidat, 'nom', '') or '?'))
                    panneau, statut, coince = candidat, statut_bis, coince_bis
                    break
        if statut in (STATUT_INCOMPATIBLE, STATUT_RESERVE) and coince:
            _avertir(avertissement_panneau_onduleur(
                panneau, coince[0], coince[1]))

    # ── Batteries : cible = kWc arrondi au multiple de 5 (5 kWh au minimum),
    # servie en modules HOMOGÈNES (un seul calibre par banque — voir la garde
    # plus bas, après le choix du vivier) ──
    # TOLÉRANCE DEUX ORTHOGRAPHES : la marque s'écrit « Dyness » (correction
    # fondateur 2026-08-18) ; un produit encore nommé « Deyness » (base non
    # migrée, saisie manuelle, fixture ancienne) doit rester reconnu, sans quoi
    # le vivier retomberait sur TOUTES les batteries du catalogue.
    # DIM2 — une cible EXPLICITE (balayage du stockage) prime sur la règle
    # kWc ; sans elle, la règle historique décide seule, à l'octet près.
    if batterie_cible_kwh is not None and float(batterie_cible_kwh) > 0:
        cible_kwh = max(5, _arrondi_js(float(batterie_cible_kwh) / 5) * 5)
    else:
        cible_kwh = max(5, _arrondi_js(kwp / 5) * 5)
    # PVOND — GARDE BATTERIE PILOTÉ PAR LA DONNÉE (remplace le mot-clé PVG4) :
    # une batterie n'entre au vivier que si sa TENSION NOMINALE tombe dans la
    # PLAGE BATTERIE de l'onduleur retenu ci-dessus. Le repli par mot-clé
    # « haute tension » ne joue QUE lorsque L'ONDULEUR ne déclare aucune plage
    # (catalogue non renseigné : comportement d'hier, byte-identique) ; dès
    # qu'une plage existe, une candidate sans tension mesurée est EXCLUE.
    # Sur un devis SANS batterie, ``onduleur`` vaut l'onduleur réseau : la
    # question ne se pose pas (le vivier n'est lu que si ``avec_batterie``).
    # U2 — la batterie pend TOUJOURS à l'onduleur HYBRIDE : en forme deux
    # options, c'est lui qui décide de la plage, jamais l'onduleur réseau de
    # l'option « sans ».
    _plage_bat = _plage_batterie_de_l_onduleur(
        onduleur_hybride if veut_batterie else onduleur)
    # PVMRQ — la compatibilité ÉLECTRIQUE se calcule sur le vivier COMPLET
    # (c'est elle qui alimente l'avertissement « vivier vide », un motif
    # DISTINCT de « marque introuvable ») ; la marque ne restreint qu'ENSUITE.
    # Même ordre que l'écran et que ``_pick_product`` : garde métier d'abord.
    # BATHOMO (26/08/2026, F1 recalé) — DEUX VIVIERS, PAS UN. La
    # COMPATIBILITÉ (tension) est un fait électrique qui s'applique TOUJOURS ;
    # le STOCK, lui, ne s'applique QU'AU CHOIX ÉCONOMIQUE (une composition
    # SANS pin — une NOUVELLE sélection). Un devis qui vend DÉJÀ un calibre
    # (``batterie_module_kwh``) l'a COMMIS : la loi fondateur est « la page
    # suit les articles du devis », donc le pin reste composable même si son
    # stock est tombé à 0 depuis — repeindre la banque en 10 kWh (un module
    # que ce devis ne vend PAS) serait exactement la violation que ce
    # correctif devait éliminer, et avec les DEUX calibres à 0 la page
    # mourrait sur un devis pourtant déjà signé. SCOPÉ AU RÔLE BATTERIE SEUL :
    # aucun autre rôle (panneaux/onduleurs) n'a cette garde de stock — un
    # filtre global casserait la composition pour un catalogue au stock non
    # suivi (cf. ``_batterie_en_stock``).
    batteries_compat = [(_parse_kwh(getattr(p, 'nom', '')), p)
                        for p in par_marque(
                            [p for p in par_type.get('batterie') or []
                             if _batterie_compatible(p, _plage_bat)],
                            'batterie')]
    dyness_compat = [b for b in batteries_compat
                     if any(marque in _sans_accents(getattr(b[1], 'nom', ''))
                            for marque in ('dyness', 'deyness'))]
    vivier_compat = dyness_compat or batteries_compat
    # Le vivier ÉCONOMIQUE (nouvelle sélection, sans pin) : compatible ET en
    # stock — sous-ensemble du vivier compatible, jamais un second filtrage
    # indépendant (une marque non stockée reste hors des deux).
    vivier_stock = [(cap, p) for cap, p in vivier_compat
                    if _batterie_en_stock(p)]
    # A1 — ``bat5_compat``/``bat10_compat`` (le vivier COMPATIBLE, 5/10 SEUL)
    # ont disparu : le pin résout désormais N'IMPORTE QUEL calibre du vivier
    # compatible (recherche directe dans ``vivier_compat``, voir plus bas) —
    # seul le repli ÉCONOMIQUE (sans pin) reste borné à 5/10, et lui reste
    # STOCK-gaté.
    bat5_stock = next((p for cap, p in vivier_stock if cap == 5), None)
    bat10_stock = next((p for cap, p in vivier_stock if cap == 10), None)
    # ── BANQUE HOMOGÈNE + ÉCONOMIE DE CALIBRE (fondateur 26/08/2026) ──
    # JAMAIS un mélange de calibres dans la même banque : c'est électriquement
    # interdit (des modules 5 kWh et 10 kWh en parallèle/série ne s'équilibrent
    # pas), et c'est ce mélange, composé côté serveur, qui a fait retirer le
    # Dyness 10 kWh du stock de production (cf. ``apps.stock.management.
    # commands.seed_catalogue``).
    #
    # Pour CHAQUE calibre disponible (en stock, compatible, et dont le
    # plafond ``bat_max_modules_par_banc`` n'est pas dépassé — cf.
    # ``_max_modules_par_banc``), UNE SEULE candidate homogène est générée :
    # le plus petit N de modules IDENTIQUES qui ATTEINT OU DÉPASSE
    # ``cible_kwh`` (plafond arrondi, jamais un manque — « extra batteries
    # might add extra panels with extra cost, that is still fine »). Parmi
    # les candidates retenues, celle au prix TTC TOTAL LE PLUS BAS gagne,
    # égalité tranchée par le MOINS de modules (fondateur 26/08/2026 :
    # l'économie décide, pas une préférence de calibre — 2×5 kWh à 28 000
    # TTC bat 1×10 kWh à 30 000 pour une cible de 10 kWh dès que les modules
    # 5 kWh sont moins chers au kWh). C'est ce qui fait grandir la banque en
    # 5 kWh, sans jamais glisser vers le 10 kWh, tant que ce dernier reste
    # plus cher au kWh — et REDEVENIR compétitif tout seul si son prix ou
    # son stock changent. Aucun mélange n'est jamais formé : au plus UN des
    # deux compteurs ci-dessous est non nul.
    #
    # ``batterie_module_kwh`` COURT-CIRCUITE ce choix économique quand
    # l'appelant impose un calibre précis (module déjà engagé par un devis) :
    # la banque grandit alors en N modules de CE seul calibre, jamais l'autre
    # — c'est ce qui garantit que l'échelle explorée pour UN devis ne bascule
    # jamais vers un autre calibre que celui qu'il vend déjà. LE PIN LIT LE
    # VIVIER COMPATIBLE (F1) — jamais le vivier stock : le module déjà engagé
    # reste composable même hors stock, SEULE la sélection ÉCONOMIQUE (sans
    # pin) est stock-gatée.

    def _candidat(calibre, produit):
        """Une candidate homogène ``(prix_ttc, n, calibre, produit)`` pour ce
        calibre, ou ``None`` si son plafond fondateur de modules est dépassé."""
        n = max(1, int(math.ceil(cible_kwh / calibre - 1e-9)))
        plafond = _max_modules_par_banc(produit)
        if plafond is not None and n > plafond:
            return None
        prix_ttc = _prix_ttc_batterie(produit, n, taux_tva)
        return (round(prix_ttc, 2), n, calibre, produit)

    calibre_impose = None
    if batterie_module_kwh is not None:
        try:
            calibre_impose = float(batterie_module_kwh)
        except (TypeError, ValueError):
            calibre_impose = None

    # A1 (revue adversariale Fable, 26/08/2026) — LE PIN N'EST PLUS UN
    # WHITELIST 5/10. ``module_batterie_du_devis`` (dimensionnement.py, F6)
    # rend N'IMPORTE QUEL calibre positif lu sur les lignes du devis (le
    # Deye BOS-B-Pack16, 16 kWh, est un produit RÉEL des gammes) : un pin qui
    # ne matchait QUE 5.0/10.0 laissait un devis 16 kWh retomber en silence
    # sur le choix économique 5/10 — repeindre la banque dans un calibre que
    # ce devis ne vend PAS, exactement la violation que ce chantier devait
    # fermer. Résolution par CALIBRE LE PLUS PROCHE dans le vivier COMPATIBLE
    # (tolérance ±1 kWh, la même que ``_compter_modules_batterie``/
    # ``module_batterie_du_devis``), pour N'IMPORTE QUEL calibre du vivier —
    # jamais restreinte à 5/10.
    #
    # PIN SANS CORRESPONDANCE ⇒ AUCUN REPLI ÉCONOMIQUE (nouveauté A1) :
    # « honest absence beats a wrong pairing » (Fable) — si le calibre déjà
    # vendu n'existe même pas dans le vivier compatible (ex. un système HAUTE
    # TENSION jamais composable sous un onduleur basse tension), retomber sur
    # le choix économique 5/10 fabriquerait une banque d'un AUTRE calibre que
    # celui du devis. La composition part alors SANS batterie (même chemin
    # honnête que le vivier vide), et — en amont — l'échelle de paliers
    # (``dimensionnement.echelle_paliers_batterie``) omet purement ses rangs
    # au lieu d'en proposer dans le mauvais calibre : chaque cible sondée
    # retombe sur une capacité nulle, ``reels`` reste vide, la fonction rend
    # ``[]``. Un pin qui MATCHE mais dont le plafond de modules rejette la
    # seule candidate possible garde en revanche le repli économique
    # ci-dessous (F3, comportement inchangé — un plafond n'est pas une
    # absence de calibre).
    candidat_impose = None
    pin_sans_correspondance = False
    if calibre_impose is not None:
        correspondance = next(
            ((cap, p) for cap, p in vivier_compat
             if abs(cap - calibre_impose) < 1.0), None)
        if correspondance is not None:
            cap_trouve, produit_trouve = correspondance
            candidat_impose = _candidat(cap_trouve, produit_trouve)
        else:
            pin_sans_correspondance = True

    candidats = []
    if candidat_impose is not None:
        candidats = [candidat_impose]
    elif not pin_sans_correspondance:
        # Aucun calibre imposé, OU un calibre imposé dont le plafond de
        # modules interdit la seule candidate qu'il permettrait : repli sur
        # le choix économique parmi les calibres 5/10 EN STOCK — jamais une
        # banque vide du seul fait d'un calibre non stocké ou plafonné, MAIS
        # jamais non plus un calibre hors stock ressuscité par ce repli
        # (F1 : le repli économique reste stock-gaté, seul le PIN d'origine
        # bypassait le stock).
        for calibre, produit in ((5, bat5_stock), (10, bat10_stock)):
            if produit is None:
                continue
            candidat = _candidat(calibre, produit)
            if candidat is not None:
                candidats.append(candidat)

    if veut_batterie and not candidats:
        # AUCUNE candidate — via le pin ou l'économie : la composition part
        # sans batterie (jamais une banque fabriquée), mais elle le DIT —
        # sinon le devis mentait par omission. C'est CETTE garde qui rend
        # l'option « avec batterie » honnêtement non-servable (``avec_ok``/
        # ``variantes_servables``, quote_engine/builder.py) : aucune ligne
        # batterie n'est composée, donc ``has_batterie`` retombe à faux tout
        # seul — aucune machinerie neuve à câbler ici.
        #
        # F5 — LE DIAGNOSTIC SUIT LA VRAIE CAUSE (quatre messages distincts,
        # jamais « changez d'onduleur » quand le vrai geste est de
        # réapprovisionner, d'augmenter un plafond, ou de vérifier le
        # calibre) :
        #   0. (A1) le devis vend DÉJÀ un calibre précis, et ce calibre
        #      N'EXISTE PAS dans le vivier compatible → message dédié,
        #      jamais confondu avec « aucune batterie compatible » (le
        #      vivier peut très bien porter D'AUTRES calibres compatibles).
        #   1. vivier COMPATIBLE vide → aucune batterie ne convient à cet
        #      onduleur (tension) : le message historique.
        #   2. vivier compatible non vide mais vivier STOCK vide, et aucun
        #      pin n'a résolu (F3/F1) → rupture de stock.
        #   3. sinon (du stock existait ou un pin compatible existait) mais
        #      ``candidats`` est quand même vide → le plafond de modules a
        #      rejeté toutes les candidates possibles (F3).
        if pin_sans_correspondance:
            message = avertissement_batterie_pin_sans_correspondance(
                calibre_impose)
        elif not vivier_compat:
            message = avertissement_vivier_batterie_vide(_plage_bat)
        elif not vivier_stock and candidat_impose is None:
            message = avertissement_batterie_rupture_stock()
        else:
            message = avertissement_batterie_plafond_banc()
        if avertissements is not None:
            avertissements.append(message)
        else:
            logger.warning(
                'PVOND: aucune banque batterie composable (%s) alors que le '
                'devis est demandé AVEC batterie — composition SANS '
                'batterie ; cet appelant ne porte aucun canal '
                'd\'avertissement.', message)

    bat5 = bat10 = None
    nb5, nb10 = 0, 0
    if candidats:
        candidats.sort(key=lambda c: (c[0], c[1]))
        _prix_retenu, n_retenu, calibre_retenu, produit_retenu = candidats[0]
        # ``produit_retenu`` — jamais ``bat5_stock``/``bat10_stock`` : un pin
        # (F1) résout depuis le vivier COMPATIBLE, qui peut désigner un
        # produit hors stock que le vivier stock-gaté ne connaît pas.
        if calibre_retenu == 5:
            bat5, nb5 = produit_retenu, n_retenu
        else:
            bat10, nb10 = produit_retenu, n_retenu

    # ── Structure : le type demandé (acier par défaut), une par panneau ──
    # PVMRQ — DEUX rôles distincts (``structure_acier`` / ``structure_alu``,
    # comme ``ROLES_AUTO_COMPOSITION``) : chacun a sa marque épinglée, appliquée
    # sur le sous-vivier déjà filtré par mot-clé (même patron que l'écran).
    voulu = ('alu' if _sans_accents(structure_type).startswith('alu')
             else 'acier')
    role_structure = 'structure_alu' if voulu == 'alu' else 'structure_acier'
    structure = next(iter(par_marque(
        [p for p in par_type.get('structure') or []
         if voulu in _sans_accents(getattr(p, 'nom', ''))],
        role_structure)), None)

    # ── Câbles Nexans 6 mm² AU MÈTRE (C4/PVCBL, fondateur 18-19/08) ─────────
    # VERROU DE CONDITIONNEMENT : le métrage est en MÈTRES, donc un produit
    # conditionné en ROULEAU/touret (« … (100m) ») ne doit JAMAIS entrer au
    # vivier — même chiffré, même seul candidat. L'incident fondateur du 19/08
    # (60 « unités » d'un rouleau de 100 m = 71 400 MAD de câble) vient
    # exactement de là. Sans candidat au mètre : aucune ligne, jamais un repli
    # silencieux sur un autre conditionnement.
    def choisir_cable(role):
        pool = par_marque(
            [p for p in par_type.get(role) or []
             if _est_au_metre(getattr(p, 'nom', ''))], role)
        # Préférence NEXANS : un fournisseur confirmé par le fondateur, pas une
        # préférence de gamme — elle joue DANS le vivier déjà filtré.
        return next(
            (p for p in pool
             if 'nexans' in _sans_accents(getattr(p, 'nom', ''))),
            next(iter(pool), None))

    cable_dc = choisir_cable('cable_dc')
    cable_terre = choisir_cable('cable_terre')

    # ── Paliers de 5 kWc — ne servent plus QUE au métrage du câble de terre ──
    blocs = max(1, _arrondi_js(kwp / 5))

    # ── L-FORFAIT (fondateur 24/08/2026) — les trois forfaits se cotent AU
    # PANNEAU, depuis le BARÈME PORTÉ PAR LE PRODUIT (cf. ``prix_forfait_ht``) :
    # plus de marches par bloc de 5 kWc, et plus aucune conversion TTC→HT —
    # c'est pourquoi ``taux_tva`` ne sert plus ici.
    #
    # Le barème est appliqué à ces TROIS rôles NOMMÉMENT, jamais dans
    # ``ajouter`` : une part « par panneau » posée par erreur sur un produit
    # vendu à la quantité (panneau, structure, socle…) se multiplierait alors
    # DEUX fois — une fois dans le prix, une fois dans la quantité.
    produit_accessoires = premier('accessoires')
    produit_tableau = premier('tableau')
    produit_installation = premier('installation')

    # ── Smart Meter + clé Wifi : UNIQUEMENT derrière un onduleur Huawei ──
    # (miroir du garde ``info_hw`` de l'ancien simulateur). L'écran teste les
    # DEUX onduleurs parce qu'il les propose tous les deux ; ici un seul est
    # vendu, donc c'est celui-là qui décide.
    # U2 — en forme DEUX OPTIONS les deux onduleurs sont vendus : le garde
    # Huawei teste alors les DEUX, exactement comme l'écran (autoFillLines),
    # sinon l'option Huawei partirait sans son Smart Meter.
    def _est_huawei(produit):
        return 'huawei' in _sans_accents(
            '%s %s' % (getattr(produit, 'marque', '') or '',
                       getattr(produit, 'nom', '') or ''))

    huawei = (_est_huawei(onduleur_reseau) or _est_huawei(onduleur_hybride)
              if deux_options else _est_huawei(onduleur))

    taguees = []

    def ajouter(role, produit, quantite, prix_ht=None):
        """Ajoute une ligne — sauf produit absent du catalogue ou quantité nulle.

        PVORD — chaque ligne est TAGUÉE de son rôle avant l'assemblage final,
        pour que ``ordre_lignes`` puisse la reclasser sans jamais reclassifier
        une désignation après coup.
        """
        if produit is None or quantite <= 0:
            return
        taguees.append((role, LigneKit(
            produit=produit,
            designation=produit.nom,
            quantite=int(quantite),
            prix_unitaire=(Decimal(produit.prix_vente) if prix_ht is None
                           else prix_ht))))

    # Ordre canonique du simulateur (onduleur, accessoires Huawei, panneaux,
    # batteries, structures, socles, forfaits, transport).
    # U2 — forme DEUX OPTIONS : les DEUX onduleurs entrent au devis (le PDF et
    # l'écran répartissent ensuite chaque ligne dans l'option qui la concerne).
    # Forme mono-option : un seul, celui qu'``avec_batterie`` a désigné.
    if deux_options:
        ajouter('onduleur_reseau', onduleur_reseau,
                quantite_onduleur(kw_reseau))
        ajouter('onduleur_hybride', onduleur_hybride,
                quantite_onduleur(kw_hybride))
    else:
        role_ond = ('onduleur_hybride' if avec_batterie
                    else 'onduleur_reseau')
        ajouter(role_ond, onduleur, quantite_onduleur(kw_onduleur))
    ajouter('smart_meter', premier('smart_meter'), 1 if huawei else 0)
    ajouter('wifi_dongle', premier('wifi_dongle'), 1 if huawei else 0)
    ajouter('panneau', panneau, nb)
    if veut_batterie:
        ajouter('batterie', bat5, nb5)
        ajouter('batterie', bat10, nb10)
    ajouter(role_structure, structure, nb)
    ajouter('socle', premier('socle'), nb * 2)
    # C4/PVCBL — métrage AU MÈTRE : le DC suit les paires de MPPT, la terre
    # suit les paliers de 5 kWc (25 m de base + 15 m par palier).
    ajouter('cable_dc', cable_dc, metre_cable_dc_par_paires(mppt_paires))
    ajouter('cable_terre', cable_terre, metre_cable_terre(blocs))
    # L-FORFAIT — une SEULE ligne par forfait, quantité 1, dont le prix
    # unitaire EST le total du barème (désignations inchangées). Barème absent
    # du produit ⇒ ``prix_forfait_ht`` rend ``None`` et ``ajouter`` retombe sur
    # le ``prix_vente`` catalogue, comme n'importe quelle autre ligne.
    ajouter('accessoires', produit_accessoires, 1,
            prix_forfait_ht(produit_accessoires, nb))
    ajouter('tableau', produit_tableau, 1,
            prix_forfait_ht(produit_tableau, nb))
    ajouter('installation', produit_installation, 1,
            prix_forfait_ht(produit_installation, nb))
    ajouter('transport', premier('transport'), 1)

    # ── PVORD — ordre PAR DÉFAUT des lignes ────────────────────────────────
    taguees = ordonner_par_role(taguees, ordre_lignes)

    lignes = CompositionLignes(ligne for _, ligne in taguees)
    lignes.roles = [role for role, _ in taguees]
    lignes.nb_panneaux = nb
    # Le wattage RÉELLEMENT retenu peut différer de celui demandé (substitution
    # « le plus proche » quand le catalogue n'a pas la puissance demandée) : on
    # rend le vrai, pour que personne n'affiche un kWc théorique divergent.
    _watt_reel = _parse_watt(getattr(panneau, 'nom', '')) if panneau else None
    lignes.panel_watt_reel = _watt_reel or watt
    lignes.kwc_reel = round(nb * float(lignes.panel_watt_reel) / 1000.0, 3)
    lignes.blocs = blocs
    lignes.marques_manquantes = marques_manquantes
    # DIM2 — LES CAPACITÉS RÉELLEMENT DISPONIBLES, en kWh nominaux, telles que
    # le vivier batterie les a retenues (compatibilité de tension avec
    # l'onduleur hybride comprise). Le balayage du stockage lit CETTE liste
    # pour construire ses paliers : sans elle il devrait redevine
    # « 5 et 10 kWh », c'est-à-dire recréer un second catalogue en dur qui
    # divergerait au premier module ajouté.
    lignes.capacites_batterie_vivier = sorted(
        {float(cap) for cap, _p in vivier_compat if cap and float(cap) > 0})
    return lignes


# ── L-2OPT — DEUX OPTIMISEURS : le champ PV de l'option « avec » peut DIFFÉRER
# de celui de l'option « sans » ────────────────────────────────────────────────
#
# LE TROU QUE CECI BOUCHE. Le moteur calibré (``apps.ventes.dimensionnement``)
# calcule DEPUIS DIM2 deux gagnants distincts : ``recommandation`` (meilleur
# payback SANS stockage) et ``recommandation_avec`` (balayage CONJOINT
# champ × stockage, meilleur payback AVEC). Le second n'alimentait AUCUN chemin
# de génération de lignes : il ne servait qu'à l'affichage. Le devis « Les deux »
# composait donc UN SEUL champ PV et se contentait de le REGARDER de deux
# façons — le découpage sans/avec du PDF est un filtrage par MOTS-CLÉS
# (batterie → « avec », onduleur réseau → « sans »), si bien que les panneaux,
# la structure, les socles et la pose tombaient dans les DEUX options avec la
# MÊME quantité. Une option « avec batterie » qui, économiquement, veut deux
# panneaux de plus ne pouvait tout simplement pas être proposée.
#
# LA FUSION. On compose DEUX kits complets (chacun par la source de vérité
# ``composition_residentielle``, en forme MONO-option — donc aucune règle
# dupliquée) puis on les fusionne ligne à ligne :
#   · même produit, même désignation, même quantité, même prix unitaire dans
#     les deux kits → UNE ligne COMMUNE (``variante=''``) ;
#   · présente dans les deux mais avec une quantité (ou un prix) différente →
#     DEUX lignes, ``variante='sans'`` et ``variante='avec'`` ;
#   · présente dans un seul kit → une ligne portant la variante de ce kit
#     (batteries → « avec », onduleur réseau → « sans », hybride → « avec »).
#
# LE REPLI DE SÉCURITÉ EST ABSOLU : quand les deux dimensionnements sont ÉGAUX
# (même nombre de panneaux, aucune cible de stockage distincte), la fusion
# n'entre JAMAIS en jeu — on rend la composition « deux options » HISTORIQUE,
# telle quelle, toutes lignes communes. Un devis d'aujourd'hui reste donc
# byte-identique tant que le moteur ne dit pas deux choses différentes.


def _memes_lignes_kit(a, b):
    """Deux ``LigneKit`` sont-elles LA MÊME ligne (donc fusionnables) ?

    Compare ce qui fait le contenu d'une ligne de devis : le produit, la
    désignation, la quantité et le prix unitaire HT. La remise et la TVA n'en
    sont pas : une ligne composée automatiquement naît toujours sans remise et
    au taux du devis — les deux kits partagent donc forcément les mêmes.
    """
    if a is None or b is None:
        return False
    if _cle_produit(a.produit) != _cle_produit(b.produit):
        return False
    if (a.designation or '') != (b.designation or ''):
        return False
    try:
        if Decimal(str(a.quantite or 0)) != Decimal(str(b.quantite or 0)):
            return False
        return (Decimal(str(a.prix_unitaire or 0))
                == Decimal(str(b.prix_unitaire or 0)))
    except (TypeError, ValueError, ArithmeticError):
        return False


def _cle_produit(produit):
    """Identité STABLE d'un produit catalogue (pk quand il en a un)."""
    if produit is None:
        return None
    pk = getattr(produit, 'pk', None)
    if pk is None:
        pk = getattr(produit, 'id', None)
    return pk if pk is not None else ('nom', getattr(produit, 'nom', ''))


def fusionner_kits(taguees_sans, taguees_avec):
    """L-2OPT — fusionne deux kits ``(rôle, LigneKit)`` en UNE séquence variantée.

    Les deux kits sortent de la MÊME fonction de composition, donc leurs
    séquences de rôles sont deux sous-suites d'un même ordre canonique (celui
    des appels ``ajouter`` de ``composition_residentielle``, éventuellement
    reclassé par le MÊME ``ordre_lignes``). Un entrelacement stable les remet
    donc dans un ordre lisible sans qu'aucun ordre canonique n'ait à être
    recopié ici — une copie divergerait au premier rôle ajouté.

    Rend une liste de couples ``(rôle, LigneKit)`` dont chaque ligne porte sa
    ``variante``. Fonction PURE.
    """
    sans = list(taguees_sans or [])
    avec = list(taguees_avec or [])
    roles_avec = [role for role, _ in avec]
    fusion = []
    i = j = 0
    while i < len(sans) or j < len(avec):
        if i < len(sans) and j < len(avec):
            role_s, ligne_s = sans[i]
            role_a, ligne_a = avec[j]
            if role_s == role_a:
                if _memes_lignes_kit(ligne_s, ligne_a):
                    fusion.append(
                        (role_s, ligne_s._replace(variante=VARIANTE_COMMUNE)))
                else:
                    # Les deux options ne veulent pas la même chose de ce rôle
                    # (typiquement : le nombre de panneaux, donc aussi les
                    # structures, les socles et le forfait de pose). Les deux
                    # lignes restent CÔTE À CÔTE : le devis se lit.
                    fusion.append(
                        (role_s, ligne_s._replace(variante=VARIANTE_SANS)))
                    fusion.append(
                        (role_a, ligne_a._replace(variante=VARIANTE_AVEC)))
                i += 1
                j += 1
                continue
            if role_s in roles_avec[j:]:
                # Le rôle courant du kit « sans » réapparaît plus loin dans le
                # kit « avec » : ce qui est propre à « avec » (batteries,
                # onduleur hybride) passe d'abord, à sa place canonique.
                fusion.append(
                    (role_a, ligne_a._replace(variante=VARIANTE_AVEC)))
                j += 1
            else:
                fusion.append(
                    (role_s, ligne_s._replace(variante=VARIANTE_SANS)))
                i += 1
            continue
        if i < len(sans):
            role_s, ligne_s = sans[i]
            fusion.append((role_s, ligne_s._replace(variante=VARIANTE_SANS)))
            i += 1
        else:
            role_a, ligne_a = avec[j]
            fusion.append((role_a, ligne_a._replace(variante=VARIANTE_AVEC)))
            j += 1
    return fusion


def composition_deux_optimiseurs(produits, *, panel_watt,
                                 kwc_sans, nb_panneaux_sans,
                                 kwc_avec=None, nb_panneaux_avec=0,
                                 batterie_cible_kwh=None,
                                 structure_type='acier',
                                 taux_tva=Decimal('20'), avertissements=None,
                                 marques=None, ordre_lignes=None,
                                 mppt_paires=1, phase=None):
    """L-2OPT — LE devis « Les deux » quand les deux optimums DIVERGENT.

    Compose DEUX kits complets par ``composition_residentielle`` (la source de
    vérité — aucune règle de composition n'est réécrite ici) :

      · kit SANS  — ``nb_panneaux_sans`` panneaux, onduleur RÉSEAU, ZÉRO
        batterie (``avec_batterie=False``) ;
      · kit AVEC  — ``nb_panneaux_avec`` panneaux, onduleur HYBRIDE dimensionné
        pour CE champ-là, et les batteries du palier retenu
        (``batterie_cible_kwh`` ; absent ⇒ la règle historique kWc/5 décide,
        aucun chiffre inventé).

    puis les FUSIONNE (cf. :func:`fusionner_kits`).

    REPLI DE SÉCURITÉ ABSOLU — deux dimensionnements ÉGAUX (même nombre de
    panneaux ET aucune cible de stockage distincte) ⇒ la fusion n'est PAS
    jouée : on rend la composition « deux options » historique, toutes lignes
    communes, byte-identique à ce que ce dépôt produit aujourd'hui.

    Fonction PURE (elle ne requête ni n'écrit rien) ; ``produits`` est déjà
    cantonné à la société appelante par l'appelant.
    """
    nb_sans = int(nb_panneaux_sans or 0)
    nb_avec = int(nb_panneaux_avec or 0) or nb_sans
    cible_stockage = (float(batterie_cible_kwh)
                      if batterie_cible_kwh not in (None, '')
                      and float(batterie_cible_kwh) > 0 else None)
    kwc_s = float(kwc_sans or 0)
    # Un champ « avec » de 10 panneaux évalué à la puissance du champ « sans »
    # se verrait dimensionner l'onduleur (et la batterie) de l'autre option :
    # à défaut de kWc fourni, on le DÉRIVE de son propre compte de panneaux,
    # jamais on ne recopie celui d'en face.
    kwc_a = (float(kwc_avec or 0)
             or (nb_avec * float(panel_watt or 0) / 1000.0)
             or kwc_s)
    # Le catalogue est parcouru DEUX fois (un kit chacun) : on le matérialise
    # une bonne fois, sans quoi un itérable à usage unique livrerait un second
    # kit VIDE.
    catalogue = list(produits or ())

    commun = dict(
        panel_watt=panel_watt, structure_type=structure_type,
        taux_tva=taux_tva, avertissements=avertissements, marques=marques,
        ordre_lignes=ordre_lignes, mppt_paires=mppt_paires, phase=phase)

    # ── LE REPLI : les deux optimiseurs disent la même chose ────────────────
    if nb_avec == nb_sans and cible_stockage is None:
        return composition_residentielle(
            catalogue, kwc=kwc_s, nb_panneaux=nb_sans, deux_options=True,
            **commun)

    kit_sans = composition_residentielle(
        catalogue, kwc=kwc_s, nb_panneaux=nb_sans, avec_batterie=False,
        deux_options=False, **commun)
    kit_avec = composition_residentielle(
        catalogue, kwc=kwc_a, nb_panneaux=nb_avec, avec_batterie=True,
        deux_options=False, batterie_cible_kwh=cible_stockage, **commun)

    def _taguees(kit):
        roles = list(getattr(kit, 'roles', ()) or ())
        return [(roles[index] if index < len(roles) else None, ligne)
                for index, ligne in enumerate(kit)]

    fusion = fusionner_kits(_taguees(kit_sans), _taguees(kit_avec))

    lignes = CompositionLignes(ligne for _role, ligne in fusion)
    lignes.roles = [role for role, _ligne in fusion]
    lignes.variantes = any(ligne.variante for ligne in lignes)
    # Les métadonnées « nominales » restent celles de l'option SANS — c'est
    # l'option 1 du document (celle que la liste et le repli d'affichage
    # montrent) et c'est ce que les appelants historiques lisent. L'option AVEC
    # a ses propres clés, à côté, jamais à la place.
    lignes.nb_panneaux = getattr(kit_sans, 'nb_panneaux', nb_sans)
    lignes.panel_watt_reel = getattr(kit_sans, 'panel_watt_reel', panel_watt)
    lignes.kwc_reel = getattr(kit_sans, 'kwc_reel', 0.0)
    lignes.blocs = getattr(kit_sans, 'blocs', 1)
    lignes.nb_panneaux_avec = getattr(kit_avec, 'nb_panneaux', nb_avec)
    lignes.kwc_reel_avec = getattr(kit_avec, 'kwc_reel', 0.0)
    lignes.capacites_batterie_vivier = list(
        getattr(kit_avec, 'capacites_batterie_vivier', ()) or ())
    # Marques épinglées introuvables : l'UNION des deux kits, dédoublonnée —
    # un rôle manquant ne doit pas être annoncé deux fois parce qu'on a composé
    # deux fois.
    vues = set()
    manquantes = []
    for kit in (kit_sans, kit_avec):
        for manque in (getattr(kit, 'marques_manquantes', ()) or ()):
            cle = (manque.get('role'), manque.get('marque'))
            if cle in vues:
                continue
            vues.add(cle)
            manquantes.append(manque)
    lignes.marques_manquantes = manquantes
    return lignes


def build_devis_from_layout(*, layout, user, company, lead=None, client=None,
                            taux_tva=Decimal('20'), remise_globale=Decimal('0'),
                            deux_options=False, journal=None, phase=None,
                            dimensionnement_avec=None):
    """Q3 — turn a FINALISED roof layout into a coherent, company-scoped Devis.

    ``deux_options`` (U2, fondateur 20/08/2026) — compose la forme DEUX
    OPTIONS (« sans batterie » ET « avec batterie » dans un seul devis, cf.
    ``composition_residentielle``) et stocke le scénario correspondant. Défaut
    False : le calepinage 3D a DÉJÀ arrêté son scénario à l'écran, il garde
    donc sa composition mono-option, byte-identique à l'historique.

    ``dimensionnement_avec`` (L-2OPT, optionnel) — ce que le moteur calibré
    recommande POUR L'OPTION AVEC BATTERIE, quand ce n'est pas le même champ PV
    que l'option sans : ``{'nb_panneaux': int, 'kwc': float,
    'batterie_kwh': float | None}``. Combiné à ``deux_options``, il fait
    composer DEUX kits complets, fusionnés en lignes VARIANTÉES (cf.
    :func:`composition_deux_optimiseurs`). ``None`` (LE DÉFAUT) ⇒ un seul champ
    PV, exactement comme aujourd'hui — et un ``nb_panneaux`` identique à celui
    de l'option sans y retombe aussi, par le repli de sécurité de la fusion.

    ``journal`` (U3, optionnel) — dict que l'appelant fournit et que la
    construction remplit sur place avec ce que la composition a REFUSÉ de
    faire : ``marques_manquantes`` (rôles épinglés sans AUCUN candidat en
    stock) et ``avertissements`` (vivier batterie vide…). Sans ce canal, un
    devis pouvait partir SANS panneaux — la marque épinglée ayant vidé leur
    vivier — à un prix effondré, sans que personne ne l'apprenne. Absent
    (``None``) ⇒ comportement inchangé.

    ``phase`` (PVCOMPAT, optionnel) — le RACCORDEMENT déclaré par le client
    (``'monophase'``/``'triphase'``), transmis tel quel à
    ``composition_residentielle`` : un abonnement monophasé n'accepte pas un
    onduleur triphasé. ``None`` ⇒ aucun filtre, comportement inchangé.

    ``layout`` is the serialized roofPro11 output (see Devis.roof_layout):
    a ``result`` block ``{panels, kwc, annualKwh, savings}`` plus an optional
    ``scenario``/equipment hint. From it we compose Devis lines off the seeded
    catalogue via ``composition_residentielle`` — le KIT COMPLET du simulateur
    (panneau, onduleur du bon palier, batteries, structures, socles,
    accessoires, tableau de protection AC/DC, installation, transport, et le
    duo Smart Meter + clé Wifi derrière un onduleur Huawei), et non plus le seul
    squelette panneau + onduleur. La classification par mots-clés reste celle du
    moteur PDF (panneau / onduleur réseau|injection|hybride / batterie) et la
    référence passe toujours par l'util anti-collision (jamais count()+1). The
    client is resolved server-side from the lead via crm.services (no
    duplicates). The layout's production/savings are stored into
    ``etude_params``. A price-less catalogue product is NEVER quoted, and a
    component missing from the catalogue is skipped rather than fatal.

    QJ21 — the stored ``roof_layout`` is enriched with a ``_pans_geometry`` key
    holding the processed per-pan list (azimut_deg, inclinaison_deg, kwc,
    nb_panneaux, orientation, label, roof_type) so consumers never have to
    re-run ``extract_roof_config`` to access the full multi-plane design.

    Returns the created Devis. The Devis is left ``brouillon`` — this service
    only BUILDS; it never changes downstream statuses (rule #4).
    """
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.utils.references import create_with_reference

    if client is None:
        if lead is None:
            raise ValueError("build_devis_from_layout requires a lead or client")
        from apps.crm.services import resolve_client_for_lead
        client = resolve_client_for_lead(lead)

    result = dict((layout or {}).get('result') or {})
    nb_panneaux = int(result.get('panels') or 0)
    kwc = float(result.get('kwc') or 0)
    annual_kwh = result.get('annualKwh')
    savings = result.get('savings')

    # FG248 — pont 3D toiture → ERP : extrait la config toiture (surface/pans/
    # orientation/inclinaison/kWc) du builder 3D. Quand le bloc ``result`` ne
    # porte pas le nombre de panneaux / la puissance, on retombe sur la somme des
    # pans (cohérence kWc/panneaux écran ↔ pont 3D). Layout sans géométrie →
    # dict vide → comportement historique strictement inchangé.
    toiture = extract_roof_config(layout)
    if toiture:
        if nb_panneaux <= 0 and toiture.get('nb_panneaux'):
            nb_panneaux = int(toiture['nb_panneaux'])
        if not kwc and toiture.get('kwc'):
            kwc = float(toiture['kwc'])

    # AOF164 — BASCULE A/B sur le moteur de calepinage partagé, derrière le
    # drapeau ``USE_MOTEUR_CALEPINAGE`` (défaut OFF). Drapeau OFF : la fonction
    # rend ``None`` AVANT tout calcul — aucun appel moteur, aucun journal,
    # comportement bit-identique à aujourd'hui. Drapeau ON : le compte vient du
    # moteur et l'écart ancien/nouveau est journalisé pour arbitrage.
    # PVG2 — au-delà de la tolérance (TOLERANCE_ARBITRAGE_MODULES modules OU
    # TOLERANCE_ARBITRAGE_PCT %), ``retenu`` REDEVIENT le compte historique :
    # la condition ci-dessous est alors fausse et le devis garde ses panneaux,
    # l'anomalie partant en avertissement plutôt qu'en remplacement silencieux.
    arbitrage = arbitrer_compte_calepinage(layout, nb_panneaux,
                                           company=company)
    if arbitrage is not None and arbitrage['retenu'] != nb_panneaux:
        watt_reference = layout.get('panelWatt') or layout.get('watt')
        if not watt_reference and nb_panneaux and kwc:
            watt_reference = kwc * 1000.0 / nb_panneaux
        nb_panneaux = arbitrage['retenu']
        # Le kWc SUIT le compte : laisser l'ancien kWc face au nouveau compte
        # produirait un devis dont la puissance ne correspond plus aux panneaux.
        if watt_reference:
            kwc = round(nb_panneaux * float(watt_reference) / 1000.0, 3)

    # Panel wattage: prefer an explicit hint, else derive from kWc / panels.
    watt = layout.get('panelWatt') or layout.get('watt')
    if not watt and nb_panneaux and kwc:
        watt = int(round(kwc * 1000 / nb_panneaux / 10) * 10)
    if not watt and kwc:
        watt = 550

    # Scenario: 'avec_batterie' / 'hybride' → hybrid inverter + battery;
    # anything else → réseau (grid-tie). Default réseau (residential injection).
    scenario = (layout.get('scenario') or '').lower()
    wants_battery = ('batterie' in scenario or 'hybride' in scenario
                     or bool(layout.get('battery')))

    # ── Compose the equipment lines from the catalogue ──
    # PVKIT — le KIT COMPLET du simulateur (structures, socles, accessoires,
    # tableau de protection, installation, transport…), plus le squelette
    # panneau + onduleur ± batterie d'hier : voir ``composition_residentielle``.
    # Un composant absent (ou non tarifé) du catalogue est simplement sauté.
    kwc_composition = kwc or (nb_panneaux * float(watt or 550) / 1000.0)
    # Sans ``journal``, on ne fournit AUCUN canal d'avertissement : la
    # composition retombe alors sur son log interne — comportement historique
    # strictement inchangé. Fournir une liste que personne ne lit reviendrait
    # à ÉTEINDRE ce log.
    _avertissements = [] if journal is not None else None
    _commun_composition = dict(
        panel_watt=watt,
        taux_tva=taux_tva,
        # U3 — les règles de gamme vivent CÔTÉ SERVEUR : marques épinglées
        # (PVMRQ) et ordre par défaut (PVORD) sont lus ici et donnés à la
        # fonction pure, plus jamais recalculés par l'écran.
        marques=carte_marques_composition(company),
        ordre_lignes=ordre_lignes_societe(company),
        avertissements=_avertissements,
        # PVCOMPAT — le raccordement du client, quand l'appelant le connaît.
        phase=phase,
    )
    # ── L-2OPT — DEUX OPTIMISEURS quand le moteur en désigne deux ───────────
    # La fusion n'entre en jeu que sur un devis DÉCLARÉ « les deux » ET quand
    # l'appelant a réellement une recommandation « avec » à opposer. Sinon
    # (défaut, calepinage 3D, devis mono-option) c'est le chemin d'hier, mot
    # pour mot.
    _avec = dimensionnement_avec if isinstance(
        dimensionnement_avec, dict) else None
    if deux_options and _avec:
        line_specs = composition_deux_optimiseurs(
            catalogue_de_la_societe(company),
            kwc_sans=kwc_composition,
            nb_panneaux_sans=nb_panneaux,
            kwc_avec=_avec.get('kwc'),
            nb_panneaux_avec=_avec.get('nb_panneaux'),
            batterie_cible_kwh=_avec.get('batterie_kwh'),
            **_commun_composition)
    else:
        line_specs = composition_residentielle(
            catalogue_de_la_societe(company),
            kwc=kwc_composition,
            nb_panneaux=nb_panneaux,
            avec_batterie=wants_battery,
            deux_options=deux_options,
            # L-2OPT — devis MONO « avec batterie » : le champ PV vient déjà de
            # l'optimum AVEC (l'appelant l'a mis dans le layout) ; la CAPACITÉ
            # retenue par ce même optimum se transmet ici. Absente ⇒ la règle
            # historique kWc/5 décide seule, à l'octet près.
            batterie_cible_kwh=(
                _avec.get('batterie_kwh')
                if (wants_battery and not deux_options and _avec) else None),
            **_commun_composition)
    if journal is not None:
        journal['marques_manquantes'] = list(
            getattr(line_specs, 'marques_manquantes', ()) or ())
        journal['avertissements'] = list(_avertissements or ())
        journal['nb_panneaux'] = getattr(line_specs, 'nb_panneaux', 0)
        journal['kwc_reel'] = getattr(line_specs, 'kwc_reel', 0.0)

    etude_params = {}
    # PVSCE — le SCÉNARIO est stocké dès la création. Sans lui, le moteur PDF
    # (QF6) retombe sur l'inférence par les lignes, qui se trompe dès que la
    # composition est partielle. On stocke ce que les lignes peuvent RÉELLEMENT
    # servir : « Avec batterie » exige l'onduleur hybride ET la batterie.
    # U2 — un devis à DEUX OPTIONS ne stocke ni « sans » ni « avec » : il
    # stocke « les deux », le seul libellé qui dise au moteur PDF de rendre la
    # comparaison. Il faut que les lignes puissent RÉELLEMENT servir les deux
    # côtés (onduleur réseau d'un côté, hybride + batterie de l'autre) — sinon
    # on retombe sur le libellé mono-option, même garde anti-mensonge
    # qu'``_scenario_stocke``.
    _a_batterie = any(_is_battery(s.designation) for s in line_specs)
    _a_hybride = any(_is_hybrid_inverter(s.designation) for s in line_specs)
    _a_reseau = any(_is_reseau_inverter(s.designation) for s in line_specs)
    if deux_options and _a_reseau and _a_hybride and _a_batterie:
        etude_params['scenario'] = SCENARIO_LES_DEUX
    else:
        etude_params['scenario'] = _scenario_stocke(_a_batterie and _a_hybride)
    if annual_kwh is not None:
        etude_params['production_annuelle'] = int(annual_kwh)
    if savings is not None:
        etude_params['economies_annuelles'] = int(savings)
    if kwc:
        etude_params['puissance_kwc'] = kwc
    # FG248 — la config toiture importée du builder 3D est conservée avec le
    # devis (prête à servir au chantier).
    if toiture:
        etude_params['toiture'] = toiture

    # QJ21 — enrich roof_layout with a ``_pans_geometry`` key carrying the
    # PROCESSED per-pan data (azimut_deg, inclinaison_deg, kwc, nb_panneaux,
    # orientation, label, roof_type) so consumers never have to re-run
    # extract_roof_config.  We copy rather than mutate the caller's dict.
    stored_layout = dict(layout)
    if toiture and toiture.get('pans'):
        stored_layout['_pans_geometry'] = toiture['pans']

    def _create(ref):
        devis = Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            lead=lead,
            statut=Devis.Statut.BROUILLON,
            taux_tva=taux_tva,
            remise_globale=remise_globale,
            created_by=user,
            mode_installation=Devis.ModeInstallation.RESIDENTIEL,
            etude_params=etude_params or None,
            roof_layout=stored_layout,
        )
        # U3/PVORD — l'ordre VOULU est posé EXPLICITEMENT (``ordre=index``),
        # jamais laissé au tri de repli sur ``id`` : c'est la même garantie que
        # l'écran s'était donnée, et sans elle l'ordre par défaut de la société
        # ne survivrait pas à la première renumérotation.
        for index, spec in enumerate(line_specs):
            LigneDevis.objects.create(
                devis=devis,
                produit=spec.produit,
                designation=spec.designation,
                quantite=Decimal(str(spec.quantite)),
                prix_unitaire=Decimal(spec.prix_unitaire),
                remise=Decimal('0'),
                ordre=index,
                # L-2OPT — '' sur toute composition mono-optimum : la colonne
                # ne se remplit que quand la fusion a réellement distingué les
                # deux options.
                variante=getattr(spec, 'variante', '') or '',
            )
        return devis

    devis = create_with_reference(Devis, 'DEV', company, _create)
    # QJR63 — LE kWc EST RE-POSÉ PAR SON PROPRIÉTAIRE, sur les LIGNES qui
    # viennent d'être créées. Le kWc du calepinage 3D est celui de roofPro
    # (720 W constants) ; le devis, lui, vend le panneau RÉEL (710 W sur
    # DEV-202608-0007). Les stocker tous les deux mettait deux bases de
    # puissance dans le même document — c'est exactement ce que PVUNI corrige
    # au RENDU, et que la donnée STOCKÉE contredisait jusqu'ici.
    poser_puissance_kwc(devis)
    # QX23be — fige la marge interne dès la création (manager-only).
    refresh_marge_snapshot(devis)
    # PV42 — la boucle se ferme ici : calepinage rangé → conception électrique
    # par pan. Meilleur effort : un échec ne fait JAMAIS perdre le devis.
    concevoir_electrique_du_devis(devis, origine='création')
    logger.info(
        'Q3/QJ21: devis %s built from layout (%d lignes, %.2f kWc, %d pans, company %s)',
        devis.reference, len(line_specs), kwc,
        len(toiture.get('pans', [])) if toiture else 0,
        getattr(company, 'id', '?'))
    return devis


# ── PV18 — RESYNCHRONISER un devis existant sur un nouveau calepinage ───────
#
# `build_devis_from_layout` CRÉE un devis. Ici on en MET À JOUR un qui existe
# déjà, et la différence est tout le sujet : un devis vivant porte des prix
# négociés, des remises, des sections, des notes, un ordre d'affichage et des
# groupes multi-villa que personne n'a le droit de perdre parce que la toiture a
# bougé de deux panneaux. La mise à jour est donc CHIRURGICALE — on touche les
# quantités de panneaux et la présence de la batterie, RIEN d'autre — et jamais,
# sous aucune condition, le STATUT (règle #4 : ce chemin LIT les statuts, il ne
# les écrit pas ; `save(update_fields=...)` ci-dessous le rend structurel).


class SyncLayoutError(Exception):
    """Le devis n'est pas dans un état où son calepinage peut être resynchronisé.

    ``revision_possible`` distingue les deux refus : un devis ENVOYÉ peut être
    révisé (une nouvelle version repart en brouillon), un devis
    accepté/refusé/expiré est clos.
    """

    def __init__(self, detail, *, revision_possible=False):
        super().__init__(detail)
        self.detail = detail
        self.revision_possible = revision_possible


def _cible_panneaux_du_layout(layout, toiture):
    """Nombre de panneaux VOULU par un layout (même lecture que la création)."""
    result = dict((layout or {}).get('result') or {})
    cible = int(result.get('panels') or result.get('count') or 0)
    if cible <= 0 and toiture.get('nb_panneaux'):
        cible = int(toiture['nb_panneaux'])
    return cible


def _watt_du_layout(layout, toiture, cible_panneaux):
    """Wattage unitaire annoncé par le layout, ou déduit de son kWc."""
    watt = (layout or {}).get('panelWatt') or (layout or {}).get('watt')
    if watt:
        try:
            return int(round(float(watt)))
        except (TypeError, ValueError):
            pass
    result = dict((layout or {}).get('result') or {})
    kwc = float(result.get('kwc') or toiture.get('kwc') or 0.0)
    if kwc and cible_panneaux:
        return int(round(kwc * 1000 / cible_panneaux / 10) * 10)
    return CIBLE_WATT_DEFAUT


# ── PVHEAL — la resynchronisation GUÉRIT les devis SQUELETTES ────────────────
#
# `build_devis_from_layout` compose le KIT COMPLET (PVKIT) depuis PVKIT. Mais
# les devis créés AVANT lui sont restés des squelettes — panneau + onduleur
# (± batterie), parfois une pose et des accessoires — sans structures, sans
# socles, sans tableau de protection AC/DC, alors que le catalogue de la
# société les porte, actifs et tarifés. Ce que le client reçoit est alors un
# devis qui ne décrit pas ce qu'on lui installe.
#
# La resynchronisation les COMPLÈTE donc, sous trois règles DURES :
#
#   1. **Elle n'AJOUTE que.** Aucune ligne existante n'est modifiée, supprimée
#      ni re-tarifée : les prix négociés sont sacrés — c'est toute la promesse
#      « chirurgicale » de PV18, et compléter ne la desserre pas.
#   2. **Une classe déjà présente ne revient jamais.** La présence se lit avec
#      le MÊME classifieur par mots-clés que la composition et que le moteur PDF
#      (`classer_produit`) : la désignation d'abord, le nom du produit ensuite —
#      une ligne « Pose et mise en service » posée sur un produit
#      « Installation » compte donc bien comme l'installation.
#   3. **Un composant introuvable (ou sans prix) n'est jamais inventé** : il est
#      sauté ET DIT, en français, dans `avertissements`. Le silence d'hier est
#      exactement ce qui a laissé partir des devis amputés.
#
# Le duo Smart Meter + clé Wifi suit une quatrième règle, héritée du
# simulateur : il ne se vend que derrière un onduleur HUAWEI. Et c'est
# l'onduleur RÉELLEMENT posé sur le devis qui tranche — pas celui que la
# composition aurait choisi, puisqu'on ne remplace jamais l'onduleur en place.

#: Les classes du kit que la resynchronisation peut compléter : tout le kit
#: résidentiel SAUF les trois que la logique chirurgicale gère déjà (panneau,
#: batterie, onduleurs), dans l'ordre d'affichage du simulateur.
CLASSES_KIT_COMPLETABLES = (
    'smart_meter', 'wifi_dongle', 'structure', 'socle', 'accessoires',
    'tableau', 'installation', 'transport',
)

#: Le message FRANÇAIS d'une classe manquante, écrit EN ENTIER par classe pour
#: que l'accord soit juste (« Structure … absente », « Socles … absents »).
AVERTISSEMENTS_KIT_ABSENT = {
    'smart_meter': 'Smart Meter absent du catalogue ou sans prix — ligne non '
                   'ajoutée.',
    'wifi_dongle': 'Clé Wifi absente du catalogue ou sans prix — ligne non '
                   'ajoutée.',
    'structure': 'Structure de fixation absente du catalogue ou sans prix — '
                 'ligne non ajoutée.',
    'socle': 'Socles de lestage absents du catalogue ou sans prix — ligne non '
             'ajoutée.',
    'accessoires': 'Accessoires (câblage DC/AC, connecteurs) absents du '
                   'catalogue ou sans prix — ligne non ajoutée.',
    'tableau': 'Tableau de protection AC/DC absent du catalogue ou sans prix '
               '— ligne non ajoutée.',
    'installation': 'Installation (pose et mise en service) absente du '
                    'catalogue ou sans prix — ligne non ajoutée.',
    'transport': 'Transport absent du catalogue ou sans prix — ligne non '
                 'ajoutée.',
}


def _classe_kit_de_ligne(ligne):
    """Classe CATALOGUE d'une ligne de devis, ou ``None``.

    Même lecture que ``_classe_ligne`` (désignation d'abord, nom du produit
    ensuite) mais rendue par le classifieur PARTAGÉ ``classer_produit`` — celui
    de la composition et du moteur PDF. Une classe inventée ici ferait diverger
    « ce qu'on croit avoir » de « ce que le PDF montre ».
    """
    return (classer_produit(ligne.designation or '')
            or classer_produit(getattr(ligne.produit, 'nom', '') or ''))


def _est_au_prix_catalogue(ligne):
    """La ligne est-elle restée au prix CATALOGUE, sans remise ?

    Un « non » vaut prix NÉGOCIÉ : une telle ligne n'est jamais supprimée en
    silence (le chemin appelant avertit à la place). Sans produit rattaché on
    ne peut RIEN prouver — donc on répond non, le doute profitant à la ligne.
    """
    produit = getattr(ligne, 'produit', None)
    if produit is None or not _has_price(produit):
        return False
    try:
        if Decimal(str(ligne.remise or 0)) != Decimal('0'):
            return False
        return (Decimal(str(ligne.prix_unitaire or 0))
                == Decimal(produit.prix_vente))
    except (TypeError, ValueError, ArithmeticError):
        return False


def _completer_kit_residentiel(devis, *, kwc, watt, nb_panneaux,
                               avec_batterie, avertissements):
    """Ajoute les lignes du kit résidentiel ABSENTES du devis. N'écrit RIEN
    d'autre : aucune ligne existante n'est touchée (voir le bloc PVHEAL).

    ``avertissements`` est enrichi sur place pour chaque classe manquante que
    le catalogue ne sait pas servir. Rend le nombre de lignes AJOUTÉES.
    """
    from apps.ventes.models import LigneDevis

    if float(kwc or 0) <= 0:
        # Sans puissance, le kit n'est pas dimensionnable : on ne devine pas.
        return 0

    lignes = _lignes_produit(devis)
    presentes = set()
    onduleurs = []
    for ligne in lignes:
        classe = _classe_kit_de_ligne(ligne)
        if classe:
            presentes.add(classe)
        if classe in ('onduleur_reseau', 'onduleur_hybride'):
            onduleurs.append(ligne)

    huawei = any(
        'huawei' in _sans_accents('%s %s %s' % (
            ligne.designation or '',
            getattr(ligne.produit, 'nom', '') or '',
            getattr(ligne.produit, 'marque', '') or ''))
        for ligne in onduleurs)

    catalogue = catalogue_de_la_societe(devis.company)
    attendu = composition_residentielle(
        catalogue, kwc=kwc, panel_watt=watt, nb_panneaux=nb_panneaux,
        avec_batterie=avec_batterie,
        taux_tva=devis.taux_tva if devis.taux_tva is not None
        else Decimal('20'),
        # PVOND — ce chemin SAIT avertir : un vivier batterie vide remonte à
        # l'écran plutôt que de disparaître dans un kit silencieusement amputé.
        avertissements=avertissements)
    par_classe = {}
    for spec in attendu:
        classe = classer_produit(spec.designation)
        if classe and classe not in par_classe:
            par_classe[classe] = spec

    # Le duo Smart Meter + clé Wifi ne sort de la composition que si l'onduleur
    # QU'ELLE a choisi est un Huawei — or ici c'est celui du DEVIS qui décide.
    # On le retrouve donc directement au catalogue (même choix que la
    # composition : le premier produit tarifé de la classe, à l'unité). Sans ce
    # rattrapage, un devis Huawei face à un catalogue dont l'hybride est un
    # Deye s'entendrait dire, à tort, que son Smart Meter manque au catalogue.
    if huawei:
        for classe in ('smart_meter', 'wifi_dongle'):
            if classe in par_classe or classe in presentes:
                continue
            produit = next(
                (p for p in catalogue
                 if classer_produit(getattr(p, 'nom', '')) == classe
                 and _has_price(p)), None)
            if produit is not None:
                par_classe[classe] = LigneKit(
                    produit=produit, designation=produit.nom, quantite=1,
                    prix_unitaire=Decimal(produit.prix_vente))

    # Les lignes ajoutées se rangent APRÈS l'existant — sections et notes
    # COMPRISES : l'ordre d'affichage du commercial n'est jamais réécrit, et
    # une note de bas de devis ne doit pas se retrouver au milieu du kit.
    ordre = max([int(ligne.ordre or 0)
                 for ligne in devis.lignes.all()] or [0])
    ajoutees = 0
    for classe in CLASSES_KIT_COMPLETABLES:
        if classe in presentes:
            continue
        if classe in ('smart_meter', 'wifi_dongle') and not huawei:
            continue
        spec = par_classe.get(classe)
        if spec is None:
            avertissements.append(AVERTISSEMENTS_KIT_ABSENT[classe])
            continue
        ordre += 1
        LigneDevis.objects.create(
            devis=devis, produit=spec.produit, designation=spec.designation,
            quantite=Decimal(str(spec.quantite)),
            prix_unitaire=Decimal(spec.prix_unitaire),
            remise=Decimal('0'), ordre=ordre)
        ajoutees += 1
    return ajoutees


def _refuser_couple_panneau_onduleur_impossible(devis, lignes, lignes_panneau,
                                                cible_panneaux, watt, gamme):
    """DEV-202608-0016 — la resynchro 3D n'ÉCRIT PAS une composition impossible.

    L'outil 3D a posé 25 panneaux Canadian Solar 710 Wc (Isc 18,59 A par
    chaîne) sur un devis dont l'onduleur vendu est un Deye 5 kW monophasé dont
    chaque entrée MPPT admet 17 A en court-circuit. La resynchro prenait
    ``layout.result.panels`` pour vérité et écrivait la ligne sans jamais
    regarder l'onduleur du devis : le couple est physiquement impossible — UNE
    chaîne seule sort déjà de la borne — et rien ne le disait.

    LE VERDICT N'EST PAS RÉÉCRIT ICI : on appelle ``verdict_panneau_onduleur``,
    la logique compose-time qui existait déjà et qui n'avait simplement jamais
    été branchée sur ce chemin. Elle ne conclut ``incompatible`` que si AUCUNE
    configuration de chaînes n'évite un BLOQUANT — c'est-à-dire quand le couple
    lui-même est en cause, jamais parce que le compte du calepinage tombe mal.
    Les chiffres cités viennent des deux FICHES TECHNIQUES (règle fondateur du
    21/08/2026 : aucun seuil, aucune marge, aucun ratio inventé).

    Lève ``SyncLayoutError`` AVANT toute écriture — la transaction reste
    intacte. Un couple ``compatible``/``sous réserve``/``inconnu`` passe : une
    fiche muette ne fait pas un refus (c'est le domaine de PVFCH).
    """
    from apps.ventes.compatibilites import (STATUT_INCOMPATIBLE,
                                            verdict_panneau_onduleur)

    if cible_panneaux <= 0:
        return

    # Le panneau CONCERNÉ : celui que la resynchro va ajuster (la ligne
    # dominante, même politique que l'écriture plus bas), ou celui qu'elle
    # créerait s'il n'y a encore aucune ligne panneau.
    candidats = [li for li in lignes_panneau
                 if getattr(li, 'produit', None) is not None]
    if candidats:
        panneau = max(candidats,
                      key=lambda li: Decimal(str(li.quantite or 0))).produit
    else:
        panneau = _pick_product(devis.company, _is_panel, watt=watt,
                                role='panneau', gamme=gamme)
    if panneau is None:
        return

    onduleurs = [li.produit for li in lignes
                 if getattr(li, 'produit', None) is not None
                 and (_classe_ligne(li, _is_hybrid_inverter)
                      or _classe_ligne(li, _is_reseau_inverter))]
    for onduleur in onduleurs:
        verdict = verdict_panneau_onduleur(panneau, onduleur)
        if verdict.get('statut') != STATUT_INCOMPATIBLE:
            continue
        raisons = verdict.get('raisons') or []
        raise SyncLayoutError(
            '%d panneaux « %s » sont incompatibles avec « %s » : %s. '
            'Corrigez le nombre de panneaux ou changez d\'onduleur — le devis '
            'n\'a pas été modifié.'
            % (cible_panneaux, getattr(panneau, 'nom', '') or 'panneau',
               getattr(onduleur, 'nom', '') or 'onduleur',
               raisons[0] if raisons else
               'le couple sort des bornes de la fiche constructeur'),
            revision_possible=False)


def _resynchroniser_instance_appelante(devis, verrou):
    """QJR20 (29/08/2026) — recale l'instance de l'APPELANT sur ce qui vient
    d'être écrit sous verrou.

    LE DÉFAUT CORRIGÉ. :func:`sync_devis_from_layout` recharge le devis sous
    ``select_for_update()`` et mute CETTE instance-là (``verrou``) ; l'objet que
    l'appelant tient est celui chargé en début de requête — et le viewset le
    charge avec ``prefetch_related('lignes', 'lignes__produit')``, si bien que
    ``devis.lignes.all()`` continue de servir la composition d'AVANT même après
    la resynchro. Les quatre études rafraîchies juste après
    (``rafraichir_etudes_du_devis``) repartaient donc de l'ancienne
    composition, et RÉÉCRIVAIENT ``etude_params`` par-dessus ce que la
    resynchro venait d'y poser. La conception électrique — seule des quatre à
    n'être jamais recalculée à la lecture, et pourtant lue par la page publique
    et l'annexe PDF depuis L-1V — pouvait ainsi PERSISTER un schéma faux
    jusqu'à ce qu'un humain rouvre l'onglet électrique.

    ``refresh_from_db()`` sans ``fields`` VIDE ``_prefetched_objects_cache``
    (Django) : la prochaine lecture de ``devis.lignes`` repart en base. Le vidage
    explicite qui suit n'est qu'une ceinture, pour que ce contrat ne dépende pas
    d'un détail d'implémentation du framework. Best-effort : un devis
    entre-temps supprimé ne doit pas transformer une resynchro RÉUSSIE en erreur.
    """
    if devis is None or devis is verrou:
        return
    try:
        devis.refresh_from_db()
    except Exception:  # noqa: BLE001 — la resynchro est déjà validée en base
        logger.warning('QJR20: instance appelante non rechargeable (devis %s)',
                       getattr(devis, 'pk', '?'), exc_info=True)
        return
    devis._prefetched_objects_cache = {}


def scenario_effectif(devis, auto):
    """QJR64 — LE SCÉNARIO QUI FAIT FOI : le registre d'abord, la dérivation
    moteur seulement en son ABSENCE.

    CE QUI ÉTAIT FAUX. ``etude_params['scenario']`` était protégé par un CAS
    PARTICULIER CODÉ EN DUR dans la fusion ``etude_extra`` de
    ``build_devis_auto``, et RE-DÉRIVÉ sans condition par la resynchro : selon
    le chemin emprunté, un « Les deux (Sans + Avec) » déclaré par un humain
    pouvait redevenir « Avec batterie » sans que personne ne l'ait demandé —
    et le PDF cessait alors de rendre la comparaison.

    LA RÈGLE (décision fondateur D12) : ``scenario`` est un chemin du REGISTRE
    de surcharges. Un scénario DÉCLARÉ survit à TOUT recalcul aval ; la
    dérivation moteur ne s'applique qu'en son absence. Un changement de marché
    PROPOSE (il pose un override, ou n'en pose pas), il n'écrase plus.

    Une valeur surchargée qui n'est pas un scénario connu est IGNORÉE (on
    retombe sur ``auto``) : une surcharge illisible ne doit pas rendre un
    document muet.
    """
    from apps.ventes.domain.overrides import effectif

    connus = (SCENARIO_SANS_BATTERIE, SCENARIO_AVEC_BATTERIE,
              SCENARIO_LES_DEUX)
    try:
        valeur, source = effectif(devis, 'scenario', auto)
    except Exception:  # noqa: BLE001 — un registre illisible ne décide rien
        return auto
    if source == 'auto' or valeur not in connus:
        return auto
    return valeur


def recommended_option_effective(devis, auto):
    """QJR64 — jumelle de :func:`scenario_effectif` pour l'option MISE EN AVANT.

    ``recommended_option`` désigne laquelle des deux options le document
    recommande. Même règle : la déclaration du vendeur (registre) prime, la
    dérivation moteur ne joue qu'à défaut. Une valeur inconnue est ignorée.
    """
    from apps.ventes.domain.overrides import effectif

    connus = (SCENARIO_SANS_BATTERIE, SCENARIO_AVEC_BATTERIE)
    try:
        valeur, source = effectif(devis, 'recommended_option', auto)
    except Exception:  # noqa: BLE001 — un registre illisible ne décide rien
        return auto
    if source == 'auto' or valeur not in connus:
        return auto
    return valeur


def puissance_kwc_du_devis(devis):
    """QJR63 — LE kWc D'UN DEVIS. Une règle, un propriétaire, deux sources.

    CE QUI ÉTAIT FAUX. ``etude_params['puissance_kwc']`` avait QUATRE
    écrivains : ``build_devis_from_layout`` (depuis le layout),
    ``sync_devis_from_layout`` (depuis le layout, MÊME quand la règle de
    plafond de variante avait fait atterrir le devis sur un AUTRE compte),
    ``build_devis_auto`` (depuis ``target_kwc`` / la taille souhaitée du lead),
    et une RE-DÉRIVATION au rendu par ``quote_engine.builder`` (PVUNI, depuis
    les LIGNES — qui recalibrait et gagnait). Le kWc STOCKÉ pouvait donc
    décrire une installation NON VENDUE, et ``models.Devis.save`` le figeait
    ensuite pour toujours dans ``prix_par_kwc``.

    LA RÈGLE, désormais unique :

    1. le REGISTRE de surcharges (décision fondateur D12) — ``taille.kwc`` s'il
       est posé, sinon ``taille.nb_panneaux`` × le wattage RÉELLEMENT LU sur
       les lignes ;
    2. sinon la DÉRIVATION DEPUIS LES LIGNES —
       ``quote_engine.builder.panneaux_et_watt_lu``, exactement celle de PVUNI
       (« les lignes sont la source unique ») ; jamais une seconde dérivation.

    ``None`` quand rien n'est lisible : aucun panneau, ou un compte sans
    wattage. On n'invente pas un kWc à partir d'un wattage supposé (M3), et le
    calepinage 3D n'est PAS une source ici — il modélise à 720 W constants,
    ce n'est pas le panneau vendu.

    LECTURE PURE (règle #4).
    """
    from apps.ventes.domain.overrides import effectif
    from apps.ventes.quote_engine.builder import panneaux_et_watt_lu

    lignes = [li for li in devis.lignes.select_related(
        'produit', 'produit__fiche_technique').all()
        if getattr(li, 'type_ligne', 'produit') == 'produit'
        and not getattr(li, 'optionnelle', False)]
    nb_lu, watt_lu = panneaux_et_watt_lu(lignes)
    auto = (round(nb_lu * watt_lu / 1000, 2)
            if nb_lu > 0 and watt_lu else None)

    kwc_surcharge, source = effectif(devis, 'taille.kwc', None)
    if source != 'auto' and kwc_surcharge:
        try:
            return round(float(kwc_surcharge), 2)
        except (TypeError, ValueError):
            pass
    nb_surcharge, source_nb = effectif(devis, 'taille.nb_panneaux', None)
    if source_nb != 'auto' and nb_surcharge and watt_lu:
        try:
            return round(int(nb_surcharge) * float(watt_lu) / 1000, 2)
        except (TypeError, ValueError):
            pass
    return auto


def poser_puissance_kwc(devis):
    """QJR63 — L'UNIQUE ÉCRIVAIN de ``etude_params['puissance_kwc']``.

    La clé devient un CACHE de :func:`puissance_kwc_du_devis` : elle n'est plus
    une valeur d'origine différente selon le chemin qui l'a posée. Écrite par
    l'écrivain unique d'``etude_params`` (QJR62), donc en fusion et sans
    toucher ni statut, ni ligne, ni total (règle #4).

    ``None`` (rien de lisible) RETIRE la clé — règle Z2 : mieux vaut une
    absence qu'un kWc qui décrit une autre installation. Ne lève jamais.
    """
    from apps.ventes.domain.etude_schema import CALEPINAGE, ecrire
    try:
        ecrire(devis, proprietaire=CALEPINAGE,
               puissance_kwc=puissance_kwc_du_devis(devis))
    except Exception:  # noqa: BLE001 — un cache raté ne casse jamais un devis
        logger.warning('puissance_kwc non posée sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
    return (devis.etude_params or {}).get('puissance_kwc')


def _quantite_verrouillee(ligne):
    """QJR60 / décision fondateur D12 — la quantité de cette ligne a-t-elle été
    TAPÉE par le commercial ?

    Lu par ``getattr`` : une ligne d'un autre modèle (ou d'un test qui n'en
    porte pas) répond ``False``, donc la resynchro garde exactement le
    comportement d'avant les marqueurs QJR59.
    """
    return bool(getattr(ligne, 'quantite_manuelle', False))


def _avertir_verrouillee(avertissements, lignes, ce_qui_n_a_pas_ete_applique):
    """L'AVERTISSEMENT FR NOMMÉ d'une resynchro qui refuse d'écraser une saisie.

    Le vendeur doit apprendre l'écart AU MOMENT de la resynchro : une quantité
    verrouillée qui ne suit pas le calepinage est une divergence réelle entre
    le dessin et le devis — la taire la ferait découvrir sur le PDF client.
    Les lignes sont NOMMÉES (leur désignation), jamais un « une ligne » anonyme.
    """
    noms = ', '.join(
        sorted({(getattr(li, 'designation', '') or '?') for li in lignes}))
    avertissements.append(
        'Quantité verrouillée par le vendeur sur : %s. %s n\'a pas été '
        'appliqué — corrigez la quantité à la main si le calepinage fait foi.'
        % (noms, ce_qui_n_a_pas_ete_applique.capitalize()))


def sync_devis_from_layout(devis, layout, user=None, *, cible_exacte=False):
    """PV18 — aligne les LIGNES d'un devis brouillon sur un nouveau calepinage.

    Sous ``transaction.atomic()`` + ``select_for_update`` sur la ligne du devis
    (deux commerciaux sur le même devis ne peuvent pas s'écraser l'un l'autre).

    Comportement par statut — le statut est LU, JAMAIS écrit (règle #4) :

    * ``brouillon`` — mise à jour chirurgicale (voir plus bas) ;
    * ``envoye``    — ``SyncLayoutError(revision_possible=True)`` : le client a
      déjà cette version sous les yeux, le bon geste est « Réviser » ;
    * ``accepte`` / ``refuse`` / ``expire`` — ``SyncLayoutError`` : document
      clos, aucune révision de calepinage possible.

    Mise à jour chirurgicale, sur un brouillon :

    * les lignes PANNEAU sont portées au compte du layout ; quand il y en a
      plusieurs, l'écart va sur la PLUS GROSSE seule (les autres, souvent une
      seconde marque ou un second pan négocié, ne bougent pas) ;
    * aucune ligne panneau et un compte à poser → UNE ligne est créée depuis le
      catalogue au wattage du layout (``_pick_product``, catalogue société OU
      global, jamais un produit sans prix) ;
    * la BATTERIE suit le scénario : ajoutée si le layout en veut une et qu'il
      n'y en a pas, supprimée s'il n'en veut plus ;
    * l'ONDULEUR suit la batterie (PVSCE) : réseau → hybride quand une batterie
      entre, hybride → réseau quand elle sort, à quantité INCHANGÉE. Sans cette
      permutation la batterie serait « fantôme » — comptée dans le total du
      devis mais absente du PDF, que le moteur rendrait en « Sans batterie »
      faute d'onduleur hybride ;
    * un devis portant LES DEUX onduleurs (artefact d'anciens chemins) est
      ramené à celui du scénario — mais l'intrus n'est retiré que s'il est
      resté AU PRIX CATALOGUE, sans remise. Un prix modifié vaut prix négocié :
      la ligne est conservée et un avertissement le dit (PVHEAL) ;
    * L-2OPT — un devis DÉCLARÉ « Les deux (Sans + Avec) » (U2) échappe aux
      trois règles ci-dessus, qui ne connaissaient que les devis mono : ses
      DEUX onduleurs sont légitimes (aucun intrus, aucun avertissement), sa
      batterie n'est jamais retirée (elle EST l'option « avec »), l'onduleur
      qui manque est COMPLÉTÉ depuis le catalogue au lieu d'être permuté, et
      le scénario re-stocké reste « Les deux » — sauf si les lignes ne peuvent
      plus servir les deux côtés, auquel cas il dégrade au libellé mono ;
    * le KIT MANQUANT est COMPLÉTÉ (PVHEAL) : structures, socles, accessoires,
      tableau de protection AC/DC, installation, transport — et le duo Smart
      Meter + clé Wifi derrière un onduleur Huawei. Ces classes sont AJOUTÉES
      quand elles manquent, jamais re-tarifées quand elles sont là ; un
      composant introuvable ou non tarifé est sauté ET annoncé en français.
      Ni sur un devis agricole (pompage) ni sur un multi-villa : les deux
      demandent un kit qui ne se déduit pas d'une composition résidentielle ;
    * TOUT le reste est intact — prix unitaires, remises, TVA de ligne,
      sections, notes, ordre d'affichage, groupes multi-villa, et les produits
      des lignes non touchées ne sont JAMAIS re-choisis ;
    * ``roof_layout`` / ``layout_hash`` sont re-posés, et ``etude_params`` ne
      reçoit que ``puissance_kwc`` / ``production_annuelle`` /
      ``economies_annuelles`` / ``toiture`` / ``scenario`` — les champs d'étude
      du générateur (autoconsommation, payback, pompe…) ne sont jamais touchés.

    L-2OPT / RÈGLE TOIT — UN DEVIS À LIGNES VARIANTÉES (deux optimiseurs) SE
    RESYNCHRONISE PAR VARIANTE, ET LE CALEPINAGE N'Y EST QU'UN PLAFOND :

    * la ligne DOMINANTE se lit PAR VARIANTE — les lignes ``variante=''`` +
      ``'sans'`` pour l'option sans, ``''`` + ``'avec'`` pour l'option avec ;
    * le compte du calepinage est le nombre de panneaux PHYSIQUEMENT POSABLES.
      Une option dont le compte le DÉPASSE est ramenée à ce plafond (sur sa
      dominante) ; une option qui reste EN DESSOUS n'est JAMAIS augmentée —
      l'optimum économique a le droit de choisir moins que le toit, et une
      resynchro n'a pas à lui vendre des panneaux qu'il a refusés ;
    * les structures et les socles suivent le compte DE LEUR VARIANTE.

    Un devis SANS aucune ligne variantée (tous ceux d'hier) garde la règle
    historique mot pour mot : le compte est porté À LA CIBLE, à la hausse comme
    à la baisse.

    ``cible_exacte`` (défaut ``False`` — TOUS les appels d'hier, comportement
    byte-identique) RETOURNE cette règle du plafond, et uniquement pour les
    devis variantés : le compte du layout devient alors une CIBLE EXACTE que
    CHAQUE option est portée à, à la hausse comme à la baisse.

    POURQUOI CE COMMUTATEUR EXISTE (revue Fable, 29/08/2026). Le plafond est la
    bonne règle quand la cible vient d'un CALEPINAGE : le toit dit ce qui tient
    physiquement, et une option qui a délibérément choisi moins n'a pas à se
    voir vendre des panneaux qu'elle a écartés. Il est la MAUVAISE règle quand
    la cible vient d'un NOMBRE TAPÉ PAR LE VENDEUR sur la carte « Recommandé »
    (:func:`~apps.ventes.offres_tailles.appliquer_au_devis`) : là, le vendeur
    N'exprime PAS une contenance de toit, il exprime le devis qu'il veut. Sous
    la règle du plafond, taper un compte PLUS GRAND que celui du devis ne
    faisait STRICTEMENT RIEN — configuration consommée, message de succès,
    devis inchangé : très exactement le « les modifications ne changent rien au
    devis » que ce chemin existe pour clore.

    Re-soumettre le MÊME layout (même empreinte) ne fait AUCUNE écriture et
    renvoie ``inchange=True``.

    Renvoie toujours le même dict :
    ``{inchange, panneaux, kwc, scenario, batterie, lignes_modifiees,
    lignes_ajoutees, avertissements}`` — forme GELÉE, inchangée par L-2OPT ;
    sur un devis varianté ``panneaux`` est le compte de l'option SANS (l'option
    1), jamais la somme des deux (un nombre qui ne décrit aucune installation).
    ``lignes_modifiees`` compte ce que la logique chirurgicale a touché,
    ``lignes_ajoutees`` ce que la complétion du kit a ajouté.
    """
    from django.db import transaction

    from apps.ventes.models import Devis, LigneDevis

    layout = layout if isinstance(layout, dict) else {}
    nouveau_hash = layout_hash(layout)
    toiture = extract_roof_config(layout)
    cible_panneaux = _cible_panneaux_du_layout(layout, toiture)
    watt = _watt_du_layout(layout, toiture, cible_panneaux)

    scenario_brut = (layout.get('scenario') or '').lower()
    veut_batterie = ('batterie' in scenario_brut or 'hybride' in scenario_brut
                     or bool(layout.get('battery')))

    with transaction.atomic():
        verrou = (Devis.objects.select_for_update()
                  .filter(pk=getattr(devis, 'pk', None)).first())
        if verrou is None:
            raise SyncLayoutError('Devis introuvable.')

        # PVMRQ — gamme RÉELLE de ce devis, calculée une fois et transmise à
        # chaque ``_pick_product``/``_pick_batterie`` de cette resynchro.
        gamme = gamme_nom(verrou)

        # ── L-2OPT — LE DEVIS « LES DEUX » EST LU AVANT LA PREMIÈRE ÉCRITURE ──
        #
        # Incident DEV-202608-0023 (production) : un devis né « Les deux (Sans +
        # Avec) » (U2) porte LÉGITIMEMENT les deux onduleurs — réseau pour
        # l'option « sans », hybride + batterie pour l'option « avec ». La
        # resynchro, elle, ne connaissait que les devis MONO : elle voyait dans
        # l'onduleur réseau l'« intrus » de l'artefact deux-onduleurs, retirait
        # la batterie dès qu'un layout n'en voulait pas, et réécrivait le
        # scénario avec un libellé mono. Le moteur PDF relisait alors une
        # déclaration mono (PV86/QF6) : ``nb_options`` retombait à 1 et la page
        # publique ne montrait plus qu'une option — celle que le commercial
        # n'avait jamais choisie seule. Une resynchronisation de calepinage n'a
        # jamais le droit de retirer au client une option qu'on lui a promise.
        #
        # C'est la DÉCLARATION STOCKÉE qui fait foi (la même que le moteur lit),
        # relue ici sous verrou, avant que quoi que ce soit n'ait bougé.
        devis_deux_options = (
            (verrou.etude_params or {}).get('scenario') == SCENARIO_LES_DEUX)

        # ── Garde de statut : LECTURE du statut, jamais une écriture ──
        if verrou.statut == Devis.Statut.ENVOYE:
            raise SyncLayoutError(
                'Devis « Envoyé » : le client a déjà cette version sous les '
                'yeux. Créez une révision (« Réviser ») pour en changer le '
                'calepinage.',
                revision_possible=True)
        if verrou.statut != Devis.Statut.BROUILLON:
            raise SyncLayoutError(
                'Devis « %s » : son calepinage est figé, ce document est '
                'clos.' % verrou.get_statut_display(),
                revision_possible=False)

        lignes = _lignes_produit(verrou)
        lignes_panneau = [li for li in lignes
                          if _classe_ligne(li, _is_panel)]
        lignes_batterie = [li for li in lignes
                           if _classe_ligne(li, _is_battery)]
        a_batterie = bool(lignes_batterie)

        # ── L-2OPT — LES DEUX VUES DU CHAMP PV ─────────────────────────────
        # ``devis_variante`` est faux sur TOUS les devis d'hier (aucune ligne
        # variantée) : la resynchro reprend alors sa règle historique, mot pour
        # mot. Il n'est vrai que pour un devis composé par les deux
        # optimiseurs, et c'est là — et là seulement — que le calepinage
        # devient un PLAFOND plutôt qu'une cible.
        def _var(ligne):
            return getattr(ligne, 'variante', '') or ''

        def _lignes_de(variante):
            return [li for li in lignes_panneau
                    if _var(li) in ('', variante)]

        def _total_de(variante):
            return sum(int(li.quantite or 0) for li in _lignes_de(variante))

        devis_variante = any(_var(li) for li in lignes_panneau)
        total_panneaux = (_total_de(VARIANTE_SANS) if devis_variante
                          else sum(int(li.quantite or 0)
                                   for li in lignes_panneau))
        total_panneaux_avec = (_total_de(VARIANTE_AVEC) if devis_variante
                               else total_panneaux)

        avertissements = []
        # Cohérence avec PV17 : ces deux cas y sont déclarés NON modifiables.
        agricole = (
            verrou.mode_installation == Devis.ModeInstallation.AGRICOLE)
        if agricole:
            avertissements.append(
                'Devis agricole (pompage) — le calepinage de toiture ne '
                's\'applique pas.')
        multi_villa = verrou.lignes.filter(groupe_index__gte=1).exists()
        if multi_villa:
            avertissements.append(
                'Devis multi-villa : l\'écart de calepinage porte sur la ligne '
                'de panneaux la plus grosse, tous groupes confondus.')

        # ── Court-circuit : même géométrie → ZÉRO écriture ──
        if nouveau_hash and verrou.layout_hash == nouveau_hash:
            return {
                'inchange': True,
                'panneaux': total_panneaux,
                'kwc': round(total_panneaux * watt / 1000.0, 3),
                # L-2OPT — un devis à deux options le DIT, même quand il n'y a
                # rien eu à écrire : l'écran ne doit jamais lire « réseau » sur
                # un document qui propose les deux.
                'scenario': ('les_deux' if devis_deux_options
                             else ('avec_batterie' if a_batterie
                                   else 'reseau')),
                'batterie': a_batterie,
                'lignes_modifiees': 0,
                'lignes_ajoutees': 0,
                'avertissements': avertissements,
            }

        lignes_modifiees = 0
        # F8 — vrai UNIQUEMENT quand le compte de panneaux a réellement bougé
        # (ligne créée, ou ligne dominante réajustée) : c'est ce qui déclenche
        # la resynchro des câbles plus bas, jamais un layout qui ne change
        # rien aux panneaux.
        panneaux_ont_change = False
        panneaux_avant = total_panneaux

        # ── DEV-202608-0016 — LE VERROU DE POSSIBILITÉ, AVANT LA PREMIÈRE
        # ÉCRITURE ──
        #
        # Placé ICI et pas plus haut : le court-circuit « même géométrie » est
        # déjà passé (re-poster un layout identique n'écrit rien, donc n'a rien
        # à refuser), et aucune ligne n'a encore bougé — un refus laisse la
        # transaction absolument intacte.
        _refuser_couple_panneau_onduleur_impossible(
            verrou, lignes, lignes_panneau, cible_panneaux, watt, gamme)

        # ── Panneaux : porter le compte à la cible ──
        if cible_panneaux > 0 and not lignes_panneau:
            panneau = _pick_product(verrou.company, _is_panel, watt=watt,
                                    role='panneau', gamme=gamme)
            if panneau is None:
                avertissements.append(
                    'Aucun panneau tarifé au catalogue : la ligne de panneaux '
                    'n\'a pas pu être créée. Ajoutez un panneau tarifé.')
            else:
                LigneDevis.objects.create(
                    devis=verrou, produit=panneau, designation=panneau.nom,
                    quantite=Decimal(str(cible_panneaux)),
                    prix_unitaire=Decimal(panneau.prix_vente),
                    remise=Decimal('0'))
                lignes_modifiees += 1
                # La ligne créée est COMMUNE (``variante=''`` par défaut) :
                # elle sert donc les deux vues à l'identique.
                total_panneaux = cible_panneaux
                total_panneaux_avec = cible_panneaux
                panneaux_ont_change = True
        elif cible_panneaux <= 0:
            # Un layout sans compte de panneaux ne DÉTRUIT pas les lignes en
            # place : « 0 » veut dire « inconnu », pas « enlève tout ».
            avertissements.append(
                'Ce calepinage ne porte aucun panneau : les lignes de '
                'panneaux du devis n\'ont pas été modifiées.')
        elif lignes_panneau and devis_variante:
            # ── L-2OPT / RÈGLE TOIT — le calepinage est un PLAFOND ──────────
            # Chaque option a son propre compte, choisi par l'économie. Le
            # calepinage dit combien de panneaux TIENNENT sur le toit : une
            # option qui dépasse ce plafond est ramenée dessus (elle n'est
            # PHYSIQUEMENT pas posable), une option en dessous n'est jamais
            # augmentée — on ne rajoute pas au client des panneaux que
            # l'optimum a délibérément écartés.
            # ``cible_exacte`` — la cible vient d'un NOMBRE TAPÉ, pas d'un
            # toit : les DEUX options y sont portées, à la hausse comme à la
            # baisse. Sans lui, une augmentation était un NO-OP SILENCIEUX
            # (« une option qui reste EN DESSOUS n'est JAMAIS augmentée »),
            # configuration consommée et message de succès compris.
            for variante in (VARIANTE_SANS, VARIANTE_AVEC):
                vue = _lignes_de(variante)
                total_vue = sum(int(li.quantite or 0) for li in vue)
                if not vue:
                    continue
                if total_vue == cible_panneaux:
                    continue
                if not cible_exacte and total_vue < cible_panneaux:
                    continue
                # Rogner d'abord une ligne PROPRE à cette variante : toucher la
                # ligne commune rétrécirait AUSSI l'autre option, qui, elle,
                # tient peut-être sur le toit.
                propres = [li for li in vue if _var(li) == variante]
                # QJR60 / D12 — une quantité TAPÉE par le vendeur n'est pas
                # réécrite : elle sort du vivier, et si tout le vivier est
                # verrouillé l'écart est NOMMÉ au lieu d'être appliqué.
                libres = [li for li in (propres or vue)
                          if not _quantite_verrouillee(li)]
                if not libres:
                    _avertir_verrouillee(
                        avertissements, (propres or vue),
                        "l'écart de %d panneau(x) de l'option « %s »"
                        % (abs(total_vue - cible_panneaux), variante))
                    continue
                dominante = max(
                    libres,
                    key=lambda li: Decimal(str(li.quantite or 0)))
                nouvelle = int(dominante.quantite or 0) - (
                    total_vue - cible_panneaux)
                if nouvelle < 0:
                    # Même garde qu'en mono-option : jamais sous zéro, jamais
                    # une suppression silencieuse.
                    nouvelle = 0
                    avertissements.append(
                        'Le plafond du calepinage dépasse la plus grosse ligne '
                        'de panneaux de l\'option « %s » : elle a été ramenée '
                        'à 0, les autres lignes n\'ont pas été touchées.'
                        % variante)
                dominante.quantite = Decimal(str(nouvelle))
                dominante.save(update_fields=['quantite'])
                lignes_modifiees += 1
                panneaux_ont_change = True
            total_panneaux = _total_de(VARIANTE_SANS)
            total_panneaux_avec = _total_de(VARIANTE_AVEC)
        elif lignes_panneau and cible_panneaux != total_panneaux:
            # L'écart va sur la PLUS GROSSE ligne, elle seule : les autres
            # lignes panneau restent telles que le commercial les a posées.
            # QJR60 / D12 — et jamais sur une ligne dont la quantité a été
            # TAPÉE : elle sort du vivier.
            libres = [li for li in lignes_panneau
                      if not _quantite_verrouillee(li)]
            if not libres:
                _avertir_verrouillee(
                    avertissements, lignes_panneau,
                    "l'écart de %d panneau(x)"
                    % abs(cible_panneaux - total_panneaux))
            else:
                dominante = max(libres,
                                key=lambda li: Decimal(str(li.quantite or 0)))
                ecart = cible_panneaux - total_panneaux
                nouvelle = int(dominante.quantite or 0) + ecart
                if nouvelle < 0:
                    # Un retrait plus grand que la ligne dominante : on ne
                    # descend jamais sous zéro (et le compte final est renvoyé
                    # tel quel).
                    nouvelle = 0
                    avertissements.append(
                        'Le retrait demandé dépasse la plus grosse ligne de '
                        'panneaux : elle a été ramenée à 0, les autres lignes '
                        'n\'ont pas été touchées.')
                dominante.quantite = Decimal(str(nouvelle))
                dominante.save(update_fields=['quantite'])
                lignes_modifiees += 1
                total_panneaux = sum(
                    int(li.quantite or 0) for li in lignes_panneau)
                total_panneaux_avec = total_panneaux
                panneaux_ont_change = True

        # DEV-202608-0016 — la resynchro DIT ce qu'elle a changé. Le compte de
        # panneaux est la décision commerciale la plus lourde de cet écran
        # (il porte le kWc, donc le prix) : qu'il bouge sous l'effet d'une
        # conception 3D ne doit pas se découvrir en relisant le devis.
        if panneaux_ont_change and total_panneaux != panneaux_avant:
            avertissements.append(
                'La conception 3D porte le devis de %d à %d panneaux.'
                % (panneaux_avant, total_panneaux))

        # ── Kilowattage RETENU — déplacé ICI (F8) : le kit (PVHEAL) ET les
        # câbles (PVCBL, juste en dessous) en ont tous les deux besoin, et le
        # panel count qui vient d'être arrêté ci-dessus est son unique
        # dépendance restante.
        result = dict(layout.get('result') or {})
        kwc = float(result.get('kwc') or toiture.get('kwc') or 0.0)
        if not kwc and total_panneaux:
            kwc = round(total_panneaux * watt / 1000.0, 3)

        # ── PVCBL — LES CÂBLES SUIVENT LA TAILLE DU CALEPINAGE (F8, fondateur
        # 18/08/2026) ──
        #
        # Le compte de panneaux, la batterie et l'onduleur se resynchronisaient
        # déjà ; les DEUX lignes de câble (DC solaire + terre AC), elles,
        # restaient au métrage du premier calepinage — un devis ramené de
        # 10 à 5 kWc gardait ses 120 m de câble DC (60 m/palier × 2 paliers)
        # alors que 5 kWc n'en réclame que 60. Mêmes métrés que ``solar.js``
        # (paliers = max(1, round(kWc / 5))).
        #
        # Ne touche QUE des lignes DÉJÀ PRÉSENTES, classées par le même
        # mot-clé que l'écran et rattachées à un PRODUIT catalogue (au mètre)
        # — jamais une note texte, et jamais une ligne INVENTÉE : un devis
        # sans câble hier n'en gagne pas un ici (ce trou reste à la charge de
        # PVHEAL/``composition_residentielle``, hors périmètre de cette
        # resynchro). Ne se déclenche QUE si le compte de panneaux a bougé —
        # un layout qui ne change rien aux panneaux ne touche pas aux câbles
        # non plus.
        def _resynchroniser_quantite(predicat, cible, variante=None):
            """Porte à ``cible`` la quantité de la famille ``predicat``.

            Ne touche QUE des lignes déjà présentes ET rattachées à un produit
            catalogue ; renvoie True quand une ligne a réellement bougé.

            L-2OPT — ``variante`` restreint la famille aux lignes de CETTE
            option-là (jamais les communes : une ligne commune sert les deux
            options, la porter au compte d'une seule fausserait l'autre).
            ``None`` (LE DÉFAUT, tous les appels d'hier) ⇒ aucune restriction.
            """
            candidats = [li for li in lignes
                         if getattr(li, 'produit', None) is not None
                         and _classe_ligne(li, predicat)
                         and (variante is None or _var(li) == variante)]
            if not candidats:
                return False
            # QJR60 / D12 — LA QUANTITÉ TAPÉE PAR LE VENDEUR EST UNE ENTRÉE.
            # C'est ce chemin qui réécrivait les mètres de câble DC/terre et
            # les comptes structure/socle : une ligne verrouillée en sort, et
            # si la famille entière est verrouillée l'écart est NOMMÉ dans les
            # avertissements plutôt qu'appliqué en silence.
            libres = [li for li in candidats
                      if not _quantite_verrouillee(li)]
            if not libres:
                _avertir_verrouillee(
                    avertissements, candidats,
                    'la quantité %s demandée par le calepinage' % cible)
                return False
            # Plusieurs lignes de la même famille (rare) : seule la PLUS
            # GROSSE bouge, même politique que les panneaux ci-dessus.
            dominante = max(libres,
                            key=lambda li: Decimal(str(li.quantite or 0)))
            nouvelle = Decimal(str(cible))
            if Decimal(str(dominante.quantite or 0)) == nouvelle:
                return False
            dominante.quantite = nouvelle
            dominante.save(update_fields=['quantite'])
            return True

        if panneaux_ont_change and kwc > 0:
            paliers = max(1, _arrondi_js(kwc / 5))
            # C4 (fondateur 19/08/2026) — garde AU MÈTRE : la cible est un
            # MÉTRAGE, elle ne s'applique qu'aux lignes dont le produit se
            # vend au mètre. Une ligne ROULEAU (« (100m) ») garde sa quantité.
            if _resynchroniser_quantite(
                    lambda n: _is_cable_dc(n) and _est_au_metre(n),
                    metre_cable_dc(paliers)):
                lignes_modifiees += 1
            if _resynchroniser_quantite(
                    lambda n: _is_cable_terre(n) and _est_au_metre(n),
                    metre_cable_terre(paliers)):
                lignes_modifiees += 1

        # ── PVSTR — LES STRUCTURES ET LES SOCLES SUIVENT LE COMPTE DE
        # PANNEAUX (fondateur, 18/08/2026) ──
        #
        # Les panneaux, la batterie, l'onduleur et les câbles se
        # resynchronisaient déjà ; la FERRURE, elle, restait au compte du
        # premier calepinage. Le devis de production DEV-202608-0007 en porte
        # la trace exacte : 9 panneaux, mais 8 structures et 16 socles — le
        # calepinage était passé de 8 à 9 panneaux et rien d'autre n'avait
        # suivi. Le client reçoit alors une installation sous-ferrée sur le
        # papier, et un total faux d'une structure et de deux socles.
        #
        # Mêmes garde-fous que les câbles, sans exception : ne touche QUE des
        # lignes DÉJÀ PRÉSENTES rattachées à un produit catalogue (jamais une
        # note, jamais une ligne INVENTÉE — une ferrure absente reste à la
        # charge de PVHEAL juste en dessous, qui l'ajoute au bon compte), et ne
        # se déclenche QUE si le compte de panneaux a réellement bougé.
        #
        # L-2OPT — sur un devis VARIANTÉ, la ferrure suit le compte DE SA
        # VARIANTE : les structures « sans » sur le champ « sans », les
        # « avec » sur le champ « avec ». Une ligne de ferrure restée COMMUNE
        # n'est PAS touchée — elle vaut pour les deux options, la porter au
        # compte d'une seule fausserait l'autre (et la fusion, elle, variante
        # toujours la ferrure quand les champs divergent : une commune ne peut
        # venir que d'une retouche manuelle, que PV18 ne réécrit jamais).
        if panneaux_ont_change and total_panneaux > 0:
            if devis_variante:
                for variante, total_vue in (
                        (VARIANTE_SANS, total_panneaux),
                        (VARIANTE_AVEC, total_panneaux_avec)):
                    if total_vue <= 0:
                        continue
                    if _resynchroniser_quantite(
                            _is_structure,
                            total_vue * STRUCTURES_PAR_PANNEAU,
                            variante=variante):
                        lignes_modifiees += 1
                    if _resynchroniser_quantite(
                            _is_socle, total_vue * SOCLES_PAR_PANNEAU,
                            variante=variante):
                        lignes_modifiees += 1
            else:
                if _resynchroniser_quantite(
                        _is_structure,
                        total_panneaux * STRUCTURES_PAR_PANNEAU):
                    lignes_modifiees += 1
                if _resynchroniser_quantite(
                        _is_socle, total_panneaux * SOCLES_PAR_PANNEAU):
                    lignes_modifiees += 1

        # ── Batterie : présente si (et seulement si) le layout en veut une ──
        if veut_batterie and not a_batterie:
            # PVOND — garde batterie data-driven : c'est l'onduleur HYBRIDE
            # RÉELLEMENT posé sur le devis qui décide de la fenêtre de tension
            # (et non celui que la composition aurait choisi — on ne remplace
            # jamais l'onduleur en place). À défaut d'hybride sur le devis, on
            # se rabat sur celui du catalogue, puis sur le mot-clé (PVG4).
            _hybride_du_devis = next(
                (li.produit for li in lignes
                 if _classe_ligne(li, _is_hybrid_inverter)
                 and getattr(li, 'produit', None) is not None), None)
            if _hybride_du_devis is None:
                _hybride_du_devis = _pick_product(
                    verrou.company, _is_hybrid_inverter,
                    role='onduleur_hybride', gamme=gamme)
            batterie = _pick_batterie(
                verrou.company, onduleur=_hybride_du_devis, gamme=gamme)
            if batterie is None:
                _plage_devis = _plage_batterie_de_l_onduleur(_hybride_du_devis)
                if _plage_devis and _plage_devis[1] > 0:
                    avertissements.append(
                        'Aucune batterie compatible tarifée pour cet onduleur '
                        '(plage %s-%s V) : la ligne batterie n\'a pas pu être '
                        'ajoutée.'
                        % (_v_txt(_plage_devis[0]), _v_txt(_plage_devis[1])))
                else:
                    avertissements.append(
                        'Aucune batterie tarifée au catalogue : la ligne '
                        'batterie n\'a pas pu être ajoutée. Ajoutez une '
                        'batterie tarifée.')
            else:
                LigneDevis.objects.create(
                    devis=verrou, produit=batterie, designation=batterie.nom,
                    quantite=Decimal('1'),
                    prix_unitaire=Decimal(batterie.prix_vente),
                    remise=Decimal('0'))
                lignes_modifiees += 1
                a_batterie = True
        elif not veut_batterie and a_batterie and not devis_deux_options:
            # L-2OPT — sur un devis « Les deux », la batterie EST l'option
            # « avec » : un calepinage qui n'en veut pas décrit l'option
            # « sans », il ne retire pas l'autre du document.
            for ligne in lignes_batterie:
                ligne.delete()
            lignes_modifiees += len(lignes_batterie)
            a_batterie = False

        # ── L'ONDULEUR DOIT S'ACCORDER AU SCÉNARIO (batterie fantôme) ──
        #
        # La resynchro n'a longtemps touché QUE les panneaux et la batterie —
        # « chirurgical ». Mais un devis réseau resynchronisé « avec batterie »
        # finissait avec un onduleur RÉSEAU face à une batterie, et le moteur
        # PDF n'accorde l'option « Avec » qu'à un devis portant onduleur
        # hybride ET batterie (builder.py : ``avec_ok = has_hybride and
        # has_batterie``). Le document retombait donc sur « Sans batterie »,
        # qui EXCLUT la ligne batterie : elle gonflait le total du devis sans
        # apparaître ni au PDF ni au total affiché. Une batterie fantôme —
        # facturée, invisible.
        #
        # La permutation est aussi chirurgicale que le reste : la ligne
        # d'onduleur garde sa QUANTITÉ, seuls le produit, la désignation et le
        # prix catalogue changent. Le sens inverse compte tout autant : sans
        # lui, retirer la batterie d'un devis hybride laisserait un document
        # SANS aucune option rendable (le moteur refuse alors le PDF).
        lignes_reseau = [li for li in lignes
                         if _classe_ligne(li, _is_reseau_inverter)]
        lignes_hybride = [li for li in lignes
                          if _classe_ligne(li, _is_hybrid_inverter)]

        # ── ARTEFACT « DEUX ONDULEURS » (PVHEAL) ──
        #
        # Des devis de production portent LES DEUX onduleurs — hybride ET
        # réseau — vestige d'anciens chemins qui composaient les deux options
        # côte à côte. Le scénario, lui, n'en veut qu'un : le second est
        # facturé pour rien. On retire donc l'intrus… mais SEULEMENT s'il est
        # resté au prix catalogue, sans remise. Un prix modifié vaut prix
        # négocié : la ligne est conservée et l'écran le dit. Supprimer en
        # silence une ligne que quelqu'un a retouchée serait exactement la
        # perte que PV18 s'interdit.
        #
        # L-2OPT — SAUF sur un devis « Les deux » : là, les DEUX onduleurs sont
        # la composition NORMALE (réseau pour l'option « sans », hybride pour
        # l'option « avec »). Il n'y a pas d'intrus à retirer, ni rien à
        # signaler — c'est ce bloc qui rétrécissait DEV-202608-0023.
        if lignes_reseau and lignes_hybride and not devis_deux_options:
            intrus = lignes_reseau if a_batterie else lignes_hybride
            conserves = []
            for ligne in intrus:
                if _est_au_prix_catalogue(ligne):
                    ligne.delete()
                    lignes_modifiees += 1
                else:
                    conserves.append(ligne)
                    avertissements.append(
                        'Ce devis porte DEUX onduleurs (réseau et hybride). '
                        '« %s » n\'est pas au prix catalogue : il a été '
                        'CONSERVÉ (prix probablement négocié) — retirez-le à '
                        'la main s\'il n\'a rien à y faire.'
                        % (ligne.designation or 'ligne sans désignation'))
            if a_batterie:
                lignes_reseau = conserves
            else:
                lignes_hybride = conserves

        def _permuter_onduleur(ligne, predicat, role, motif_absence):
            remplacant = _pick_product(verrou.company, predicat, role=role,
                                       gamme=gamme)
            if remplacant is None:
                avertissements.append(motif_absence)
                return False
            ligne.produit = remplacant
            ligne.designation = remplacant.nom
            ligne.prix_unitaire = Decimal(remplacant.prix_vente)
            ligne.save(update_fields=['produit', 'designation',
                                      'prix_unitaire'])
            return True

        def _poser_onduleur_manquant(predicat, role, motif_absence):
            """L-2OPT — POSE l'onduleur qui manque à un devis « Les deux ».

            Un devis à deux options a besoin des DEUX familles : permuter celle
            qui reste reviendrait à détruire l'option qu'elle sert. On complète
            donc depuis le catalogue, au prix catalogue et sans remise (aucun
            chiffre inventé) ; sans produit tarifé, on le DIT et on laisse le
            scénario stocké dégrader honnêtement plus bas.
            """
            produit = _pick_product(verrou.company, predicat, role=role,
                                    gamme=gamme)
            if produit is None:
                avertissements.append(motif_absence)
                return None
            ordre_max = max([int(li.ordre or 0)
                             for li in verrou.lignes.all()] or [0])
            return LigneDevis.objects.create(
                devis=verrou, produit=produit, designation=produit.nom,
                quantite=Decimal('1'),
                prix_unitaire=Decimal(produit.prix_vente),
                remise=Decimal('0'), ordre=ordre_max + 1)

        if devis_deux_options:
            # Les deux familles sont légitimes : on COMPLÈTE ce qui manque, on
            # ne permute JAMAIS (une permutation retirerait au client l'option
            # que la ligne permutée servait).
            if lignes_hybride and not lignes_reseau:
                ligne = _poser_onduleur_manquant(
                    _is_reseau_inverter, 'onduleur_reseau',
                    'Aucun onduleur réseau tarifé au catalogue : ce devis à '
                    'deux options ne peut pas présenter l\'option sans '
                    'batterie. Ajoutez un onduleur réseau tarifé.')
                if ligne is not None:
                    lignes_reseau = [ligne]
                    lignes_modifiees += 1
            elif lignes_reseau and a_batterie and not lignes_hybride:
                ligne = _poser_onduleur_manquant(
                    _is_hybrid_inverter, 'onduleur_hybride',
                    'Aucun onduleur hybride tarifé au catalogue : ce devis à '
                    'deux options ne peut pas présenter l\'option avec '
                    'batterie. Ajoutez un onduleur hybride tarifé.')
                if ligne is not None:
                    lignes_hybride = [ligne]
                    lignes_modifiees += 1
        elif a_batterie and lignes_reseau and not lignes_hybride:
            if _permuter_onduleur(
                    lignes_reseau[0], _is_hybrid_inverter, 'onduleur_hybride',
                    'Aucun onduleur hybride tarifé au catalogue : l\'onduleur '
                    'réseau a été conservé. La proposition ne pourra pas '
                    'présenter l\'option avec batterie.'):
                lignes_hybride, lignes_reseau = [lignes_reseau[0]], []
                lignes_modifiees += 1
        elif not a_batterie and lignes_hybride and not lignes_reseau:
            if _permuter_onduleur(
                    lignes_hybride[0], _is_reseau_inverter, 'onduleur_reseau',
                    'Aucun onduleur réseau tarifé au catalogue : l\'onduleur '
                    'hybride a été conservé alors que la batterie a été '
                    'retirée.'):
                lignes_reseau, lignes_hybride = [lignes_hybride[0]], []
                lignes_modifiees += 1

        # ``result``/``kwc`` sont déjà résolus plus haut (F8, juste après le
        # bloc panneaux) — le kit ci-dessous et l'étude plus bas les
        # réutilisent tels quels.

        # ── PVHEAL — COMPLÉTER le kit manquant (structures, socles, tableau…) ──
        #
        # Le squelette des devis d'hier devient le kit réellement installé. La
        # complétion n'AJOUTE que : les lignes en place, leurs prix négociés et
        # leur ordre ne sont jamais touchés (voir le bloc PVHEAL plus haut).
        # Deux devis en sont écartés, parce qu'une composition RÉSIDENTIELLE ne
        # décrit pas leur kit : l'agricole (pompage — ni structure de toiture
        # ni socles) et le multi-villa (chaque villa a le sien, une série de
        # lignes hors groupe y serait fausse).
        lignes_ajoutees = 0
        if agricole or multi_villa:
            if multi_villa and not agricole:
                avertissements.append(
                    'Devis multi-villa : le kit manquant (structures, socles, '
                    'tableau de protection…) n\'a pas été complété '
                    'automatiquement — chaque villa a le sien.')
        else:
            lignes_ajoutees = _completer_kit_residentiel(
                verrou, kwc=kwc, watt=watt, nb_panneaux=total_panneaux,
                # L-2OPT — un devis à deux options doit porter le kit de
                # l'option la PLUS équipée : celle avec batterie. Le compléter
                # « sans » laisserait l'option « avec » incomplète au PDF.
                avec_batterie=True if devis_deux_options else a_batterie,
                avertissements=avertissements)

        # ── Étude : les clés géométriques + le scénario, jamais les champs
        # d'étude du générateur ──
        etude = dict(verrou.etude_params or {})
        if result.get('annualKwh') is not None:
            etude['production_annuelle'] = int(result['annualKwh'])
        if result.get('savings') is not None:
            etude['economies_annuelles'] = int(result['savings'])
        # QJR63 — LE kWc VIENT DE SON PROPRIÉTAIRE, PLUS DU LAYOUT. Ce site
        # écrivait ``kwc`` — celui du CALEPINAGE — même quand la règle de
        # plafond de variante venait de faire atterrir le devis sur un AUTRE
        # compte de panneaux : le kWc stocké décrivait alors une installation
        # NON VENDUE, que ``Devis.save`` figeait ensuite dans ``prix_par_kwc``.
        # Les lignes sont déjà resynchronisées à ce point : le propriétaire lit
        # donc l'état RÉEL (registre de surcharges, sinon dérivation PVUNI).
        _kwc_proprietaire = puissance_kwc_du_devis(verrou)
        if _kwc_proprietaire:
            etude['puissance_kwc'] = _kwc_proprietaire
        elif kwc:
            etude['puissance_kwc'] = kwc
        if toiture:
            etude['toiture'] = toiture
        # PVSCE — le scénario suit l'état RÉEL des lignes après resynchro : sans
        # lui, le moteur PDF garderait le choix stocké d'avant (ou déduirait
        # « Sans batterie » par repli) alors que l'équipement vient de changer.
        #
        # L-2OPT — un devis NÉ « Les deux » re-stocke « Les deux », jamais un
        # libellé mono : c'est cette déclaration que le moteur PDF lit pour
        # rendre la comparaison (PV86/QF6). Même garde anti-mensonge qu'à la
        # création (U2) : on ne le re-stocke que si les lignes peuvent
        # RÉELLEMENT servir les deux côtés (réseau d'un côté, hybride +
        # batterie de l'autre) — sinon on dégrade au libellé mono honnête.
        deux_options_servies = bool(
            devis_deux_options and lignes_reseau and lignes_hybride
            and a_batterie)
        if deux_options_servies:
            _scenario_auto = SCENARIO_LES_DEUX
        else:
            _scenario_auto = _scenario_stocke(
                a_batterie and bool(lignes_hybride))
        # QJR64 / décision fondateur D12 — UN SCÉNARIO DÉCLARÉ SURVIT À TOUT
        # RECALCUL. Ce site RE-DÉRIVAIT le scénario sans condition : un
        # « Les deux (Sans + Avec) » posé par un humain pouvait redevenir
        # « Avec batterie » à la première resynchro, et le PDF cessait de
        # rendre la comparaison. La dérivation ci-dessus reste le défaut ; elle
        # ne s'applique plus qu'en l'ABSENCE de surcharge au registre.
        etude['scenario'] = scenario_effectif(verrou, _scenario_auto)

        # QJ21 — le layout stocké porte la géométrie par pan DÉJÀ traitée, pour
        # que ses consommateurs n'aient pas à ré-extraire. Copie, jamais une
        # mutation du dict de l'appelant. L'empreinte, elle, est calculée sur
        # le layout D'ORIGINE (clés géométriques seules) : cet enrichissement
        # ne peut donc pas casser le court-circuit au prochain envoi.
        layout_stocke = dict(layout)
        if toiture and toiture.get('pans'):
            layout_stocke['_pans_geometry'] = toiture['pans']

        verrou.roof_layout = layout_stocke
        verrou.layout_hash = nouveau_hash or verrou.layout_hash
        # QJR62 — la RÈGLE de fusion vient de l'écrivain unique
        # (``domain.etude_schema``) ; seule la PERSISTANCE diffère ici, parce
        # que ce chemin écrit ``roof_layout`` + ``layout_hash`` +
        # ``etude_params`` d'un SEUL ``save`` (le scinder ferait deux
        # allers-retour et deux fenêtres de course pour rien).
        # On ne soumet au validateur que les clés que CE chemin a réellement
        # CHANGÉES : une clé héritée d'un devis ancien (et pas encore déclarée
        # au schéma) ne doit pas faire échouer une resynchro qui ne la touche
        # même pas.
        from apps.ventes.domain.etude_schema import CALEPINAGE, fusionner
        _avant = dict(verrou.etude_params or {})
        _modifiees = {cle: valeur for cle, valeur in etude.items()
                      if cle not in _avant or _avant[cle] != valeur}
        verrou.etude_params = fusionner(
            _avant, proprietaire=CALEPINAGE, **_modifiees)
        # `update_fields` EXCLUT `statut` : le statut ne peut pas partir d'ici,
        # même par accident (règle #4).
        verrou.save(update_fields=[
            'roof_layout', 'layout_hash', 'etude_params'])

        logger.info(
            'PV18: devis %s resynchronisé sur son calepinage (%d panneaux, '
            '%.2f kWc, %d ligne(s) touchée(s), %d ligne(s) de kit ajoutée(s), '
            'société %s, par %s)',
            verrou.reference, total_panneaux, kwc, lignes_modifiees,
            lignes_ajoutees, getattr(verrou.company, 'id', '?'),
            getattr(user, 'username', '?'))

        resultat = {
            'inchange': False,
            'panneaux': total_panneaux,
            'kwc': kwc,
            # L-2OPT — le champ dit l'état RÉEL du devis après resynchro :
            # « les_deux » (vocabulaire déjà en place, cf.
            # ``SCENARIOS_DEMANDABLES``) quand les deux options sont servies.
            'scenario': ('les_deux' if deux_options_servies
                         else ('avec_batterie' if a_batterie else 'reseau')),
            'batterie': a_batterie,
            'lignes_modifiees': lignes_modifiees,
            'lignes_ajoutees': lignes_ajoutees,
            'avertissements': avertissements,
        }

    # PV42 — la toiture a bougé : la conception ÉLECTRIQUE la suit, par pan.
    # HORS de la transaction, et en meilleur effort : une étude électrique en
    # panne ne doit ni annuler la resynchro déjà validée, ni salir sa
    # transaction. L'empreinte d'entrée (PV41) évite toute réécriture inutile.
    concevoir_electrique_du_devis(verrou, origine='resynchronisation')
    # QJR20 — l'appelant repart de CE QUI VIENT D'ÊTRE ÉCRIT (voir
    # ``_resynchroniser_instance_appelante`` : sans cela, les études
    # rafraîchies juste après décrivent la composition d'AVANT la resynchro).
    _resynchroniser_instance_appelante(devis, verrou)
    return resultat


# ── PVSYNC — le catalogue bouge, les devis VIVANTS suivent ───────────────────
#
# Jusqu'ici, corriger un prix ou renommer une référence dans le Stock laissait
# les devis déjà rédigés parler de l'ancien monde : le commercial rouvrait un
# brouillon de la semaine dernière et y lisait un prix que la société ne
# pratique plus. La resynchronisation de calepinage (PV18) savait déjà guérir
# un devis, mais seulement quand quelqu'un rouvrait la conception 3D — donc
# jamais pour un devis qu'on ne rouvre pas.
#
# Ce bloc rend la propagation ÉVÉNEMENTIELLE : ``stock`` annonce sur le bus M6
# qu'une référence a changé (``core.events.produit_modifie``), ``ventes`` s'y
# abonne dans son ``apps.py`` ``ready()`` et délègue à une tâche Celery. Les
# BORNES sont le sujet, et elles sont toutes dures :
#
#   1. **Seuls les statuts BROUILLON et ENVOYÉ bougent.** Un devis accepté,
#      refusé ou expiré est un document CONTRACTUEL : le client a signé (ou vu)
#      des montants, et aucune correction de catalogue n'a le droit de les
#      réécrire. Le statut est LU, JAMAIS écrit (règle #4) — les écritures se
#      limitent à ``LigneDevis`` et à une note de chatter.
#   2. **Une ligne NÉGOCIÉE n'est jamais recalée.** Le prix ne suit le
#      catalogue que si la ligne portait EXACTEMENT l'ANCIEN prix catalogue et
#      aucune remise de ligne ; la désignation ne suit que si elle valait
#      exactement l'ANCIEN nom. C'est pour cela que l'événement transporte
#      l'AVANT : après l'écriture du produit, comparer au prix COURANT ne
#      prouverait plus rien. Tout écart est CONSERVÉ et DIT.
#   3. **Aucune cascade possible.** Ce chemin n'écrit jamais un ``Produit`` :
#      il ne peut donc pas ré-émettre ``produit_modifie`` (garde structurelle,
#      pas une convention — et un test la vérifie).
#   4. **Silencieux quand il n'y a rien à dire.** Zéro ligne modifiée ⇒ aucune
#      note, aucune écriture. Rejouer le même événement est donc un no-op
#      complet (la tâche est at-least-once : elle DOIT être idempotente).
#   5. **Une société à la fois.** La requête est cantonnée à la société de
#      l'événement — le devis d'un autre tenant n'est jamais lu, encore moins
#      réécrit.

#: Résumé FRANÇAIS d'un champ produit, pour la note de chatter.
LIBELLES_CHAMPS_PRODUIT = {
    'nom': 'désignation',
    'prix_vente': 'prix',
}


def _valeurs_champ(champs, nom_champ):
    """``(avant, après)`` d'un champ du payload d'événement, ou ``(None, None)``.

    Le payload transporte des CHAÎNES (il traverse une file Celery) ; on ne les
    convertit pas ici, chaque appelant sait ce qu'il attend.
    """
    paire = (champs or {}).get(nom_champ)
    if not isinstance(paire, (list, tuple)) or len(paire) != 2:
        return None, None
    return paire[0], paire[1]


def _decimal_ou_none(valeur):
    """``Decimal`` d'une chaîne du payload — ``None`` si elle n'en est pas un."""
    if valeur in (None, ''):
        return None
    try:
        return Decimal(str(valeur))
    except (TypeError, ValueError, ArithmeticError):
        return None


def resynchroniser_devis_pour_produit(*, produit, company, champs, user=None):
    """PVSYNC — propage un changement de RÉFÉRENCE aux devis qui l'utilisent.

    Ne touche QUE les devis ``brouillon`` et ``envoye`` de ``company`` portant
    une ligne rattachée à ``produit`` (voir les cinq bornes du bloc ci-dessus).

    Renvoie toujours le même dict :
    ``{devis_touches, lignes_modifiees, lignes_conservees, avertissements}`` —
    ``lignes_conservees`` compte les lignes laissées telles quelles parce
    qu'elles portaient un prix ou une désignation NÉGOCIÉS.
    """
    from django.db import transaction

    from apps.ventes.models import Devis, LigneDevis

    from .activity import log_devis_resynchronisation

    ancien_nom, nouveau_nom = _valeurs_champ(champs, 'nom')
    ancien_prix_txt, nouveau_prix_txt = _valeurs_champ(champs, 'prix_vente')
    ancien_prix = _decimal_ou_none(ancien_prix_txt)
    nouveau_prix = _decimal_ou_none(nouveau_prix_txt)

    resultat = {'devis_touches': 0, 'lignes_modifiees': 0,
                'lignes_conservees': 0, 'avertissements': []}
    if company is None or produit is None:
        return resultat
    if not nouveau_nom and nouveau_prix is None:
        return resultat

    modifications = [LIBELLES_CHAMPS_PRODUIT[champ]
                     for champ in ('prix_vente', 'nom')
                     if champ in (champs or {})]

    with transaction.atomic():
        lignes = list(
            LigneDevis.objects
            .select_related('devis')
            .filter(produit=produit,
                    type_ligne=LigneDevis.TypeLigne.PRODUIT,
                    devis__company=company,
                    devis__statut__in=(Devis.Statut.BROUILLON,
                                       Devis.Statut.ENVOYE))
            .order_by('devis_id', 'id'))

        touches = {}
        for ligne in lignes:
            champs_ecrits = []
            conservee = False

            # ── Désignation : elle ne suit que si elle n'a jamais été retouchée
            if nouveau_nom and ancien_nom:
                if (ligne.designation or '') == ancien_nom:
                    ligne.designation = nouveau_nom
                    champs_ecrits.append('designation')
                elif (ligne.designation or '') != nouveau_nom:
                    conservee = True

            # ── Prix : il ne suit que si la ligne était AU PRIX CATALOGUE
            # d'avant, sans remise de ligne. Une remise ou un prix retouché
            # valent prix NÉGOCIÉ : intouchables, et on le dit.
            if nouveau_prix is not None and ancien_prix is not None:
                remise = _decimal_ou_none(ligne.remise) or Decimal('0')
                actuel = _decimal_ou_none(ligne.prix_unitaire)
                if actuel is not None and actuel == ancien_prix \
                        and remise == Decimal('0'):
                    ligne.prix_unitaire = nouveau_prix
                    champs_ecrits.append('prix_unitaire')
                elif actuel is None or actuel != nouveau_prix:
                    conservee = True

            if champs_ecrits:
                ligne.save(update_fields=champs_ecrits)
                resultat['lignes_modifiees'] += 1
                touches.setdefault(ligne.devis_id, ligne.devis)
            if conservee:
                resultat['lignes_conservees'] += 1

        # ── TRANSPARENCE D'UNE RESYNCHRO POST-ENVOI (fondateur 2026-08-18) ──
        #
        # Le périmètre reste brouillon + envoyé (décision fondateur, borne 1) :
        # un devis envoyé DOIT suivre le catalogue, sinon le commercial rappelle
        # un client avec un prix que la société ne pratique plus. Mais le client,
        # lui, tient un PDF FIGÉ au montant du jour de l'envoi pendant que sa
        # page /proposition est re-rendue en direct : sans marqueur, il pouvait
        # signer un montant différent de sa pièce jointe sans jamais l'avoir su.
        # On pose donc l'horodatage de la DERNIÈRE resynchro post-envoi (écrasé
        # à chaque passage — c'est un « depuis quand », pas un journal) et la
        # charge utile publique l'expose sous ``resync_apres_envoi``.
        # ``update_fields`` EXCLUT ``statut`` : rien ne peut partir d'ici (#4).
        from django.utils import timezone
        horodatage = timezone.now().isoformat()
        from apps.ventes.domain.etude_schema import CALEPINAGE, ecrire
        for devis in touches.values():
            if devis.statut == Devis.Statut.ENVOYE:
                # QJR62 — ÉCRIVAIN UNIQUE (fusion, jamais un remplacement).
                ecrire(devis, proprietaire=CALEPINAGE,
                       resync_apres_envoi={'date': horodatage})
            log_devis_resynchronisation(
                devis, produit=produit, modifications=modifications, user=user)
        resultat['devis_touches'] = len(touches)

    if resultat['lignes_conservees']:
        resultat['avertissements'].append(
            '%d ligne(s) de devis portaient un prix ou une désignation '
            'personnalisés : elles ont été CONSERVÉES telles quelles.'
            % resultat['lignes_conservees'])

    if resultat['devis_touches']:
        logger.info(
            'PVSYNC: produit %s modifié (%s) — %d devis resynchronisé(s), '
            '%d ligne(s) recalée(s), %d ligne(s) négociée(s) conservée(s), '
            'société %s',
            getattr(produit, 'sku', None) or getattr(produit, 'pk', '?'),
            ', '.join(modifications) or '—', resultat['devis_touches'],
            resultat['lignes_modifiees'], resultat['lignes_conservees'],
            getattr(company, 'id', '?'))
    return resultat


def on_produit_modifie(sender, produit, company, champs, user=None, **kwargs):
    """PVSYNC — récepteur du bus M6, câblé dans ``VentesConfig.ready()``.

    Il ne fait RIEN lui-même : il planifie la resynchronisation APRÈS le commit
    de la requête stock (``transaction.on_commit``) et la confie à Celery. Deux
    raisons, toutes deux dures :

    * un magasinier qui corrige un prix ne doit pas attendre que N devis soient
      relus — l'écran stock répond immédiatement ;
    * tant que la transaction du produit n'est pas commitée, la nouvelle valeur
      n'existe pas encore pour le worker : lancer la tâche avant le commit
      resynchroniserait sur l'ANCIEN prix (et sur une écriture qui peut encore
      être annulée).

    Best-effort de bout en bout : un bus ou un courtier en panne ne fait jamais
    échouer l'enregistrement du produit.
    """
    from django.db import transaction

    produit_id = getattr(produit, 'pk', None)
    company_id = getattr(company, 'pk', None)
    if not produit_id or not company_id or not champs:
        return
    user_id = getattr(user, 'pk', None)

    def _planifier():
        planifier_resynchronisation_produit(
            produit_id, company_id, champs, user_id)

    transaction.on_commit(_planifier)


def planifier_resynchronisation_produit(produit_id, company_id, champs,
                                        user_id=None):
    """PVSYNC — met la resynchronisation en file, ou la joue EN LIGNE à défaut.

    Le repli en ligne n'est pas un luxe : sans courtier joignable, une
    propagation silencieusement perdue laisserait des devis faux sans que
    personne ne le sache. On est déjà APRÈS le commit (appelé depuis
    ``on_commit``), donc jouer la tâche ici n'ouvre aucune transaction imbriquée.
    """
    from .tasks import task_resync_devis_apres_produit_modifie

    try:
        task_resync_devis_apres_produit_modifie.delay(
            produit_id, company_id, champs, user_id)
        return
    except Exception as exc:  # noqa: BLE001 — courtier indisponible
        logger.warning(
            'PVSYNC: file Celery indisponible (%s) — resynchronisation du '
            'produit %s jouée en ligne.', exc, produit_id)
    try:
        task_resync_devis_apres_produit_modifie(
            produit_id, company_id, champs, user_id)
    except Exception:  # noqa: BLE001 — jamais bloquant pour l'écriture stock
        logger.exception(
            'PVSYNC: resynchronisation en ligne du produit %s échouée.',
            produit_id)


# ── Copilote — devis AUTOMATIQUE (résidentiel) ───────────────────────────────
# Le Copilote ne doit JAMAIS créer un devis vide : il passe toujours par ce
# dimensionnement automatique, puis délègue à build_devis_from_layout
# (catalogue, numérotation, brouillon).
#
# ORDRE FONDATEUR (29/08/2026) — « ALL sizing should go through the new sizing
# tool, and i said ALL sizing ». La règle historique « 8 panneaux par tranche de
# 900 MAD de facture d'hiver » (port de ``estimerPanneaux`` de solar.js) NE
# DIMENSIONNE PLUS AUCUN DEVIS : elle a été SUPPRIMÉE de ce module. Deux leads
# portant la MÊME facture repartaient sinon avec deux tailles issues de deux
# règles différentes selon qu'un profil d'appel avait été rempli ou non
# (incident test18/test19 : 15/14 panneaux par le moteur contre 16/16 par la
# tranche). Désormais : le moteur horaire dimensionne DÈS QU'UNE DONNÉE DE
# CONSOMMATION EXISTE (la facture d'hiver suffit), et seule une puissance
# demandée — ``target_kwc`` pour ce devis, ou ``taille_souhaitee_kwc`` sur la
# fiche — reste souveraine (le commercial sait ce qu'il vend).

_AUTO_PANEL_WATT = 710        # Wc — panneau catalogue par défaut (cf. solar.js)


class AutoDevisError(Exception):
    """Le devis automatique ne peut pas être dimensionné (donnée manquante ou
    marché non géré). L'endpoint la traduit en 422 et l'agent demande la donnée
    (ou oriente vers le générateur) plutôt que de produire un devis vide."""

    def __init__(self, message, *, field=None):
        super().__init__(message)
        self.message = message
        self.field = field


def profil_reel_existe(lead):
    """CJ2a — le lead porte-t-il un PROFIL réel, et non juste une facture ?

    « Profil » = ce que le script d'appel a réellement recueilli et qui change
    la forme de la consommation heure par heure :

    * la présence en journée (``occupation_jour``) — le signal le plus fort :
      à facture égale, un foyer présent en journée autoconsomme presque le
      double d'un foyer absent ;
    * un équipement déclaré AVEC sa grandeur (piscine + kW, clim + pièces, VE +
      km/semaine) — les seules couches que le moteur sait composer ;
    * douze factures mensuelles réelles saisies sur le devis.

    NE CONDITIONNE PLUS AUCUN DIMENSIONNEMENT (ordre fondateur du 29/08/2026 :
    « ALL sizing should go through the new sizing tool »). Cette fonction était
    la porte du chemin horaire dans ``build_devis_auto`` ; elle n'y est plus
    appelée, car un lead SANS profil se dimensionne désormais lui aussi par le
    moteur (facture d'hiver inversée au barème ONEE + silhouette du DÉFAUT
    RÉSIDENTIEL FONDATEUR ``courbes_journalieres.DEFAUT_RESIDENTIEL``, QJR10 /
    D4), et non plus par la règle des 900 DH/mois — qui n'existe plus.

    Elle reste EXPOSÉE comme lecture de qualité de fiche (« ce lead porte-t-il
    autre chose qu'une facture ? »), utile pour nuancer un affichage ou
    relancer un commercial, jamais pour décider d'une taille.
    """
    if lead is None:
        return False
    if getattr(lead, 'occupation_jour', None) in ('present', 'absent', 'partiel'):
        return True
    couples = (
        ('equip_piscine', 'equip_piscine_pompe_kw'),
        ('equip_clim', 'equip_clim_pieces'),
        ('equip_voiture_electrique', 'equip_ve_km_semaine'),
    )
    for drapeau, grandeur in couples:
        if getattr(lead, drapeau, None) is True:
            valeur = getattr(lead, grandeur, None)
            if valeur not in (None, ''):
                try:
                    if float(valeur) > 0:
                        return True
                except (TypeError, ValueError):
                    continue
    return False


def phase_client_pour_dimensionnement(lead):
    """Raccordement normalisé du lead (mono/tri/None) — PVCOMPAT, une seule
    lecture. Isolé pour être appelable AVANT le dimensionnement, alors que
    ``build_devis_auto`` ne résout la phase qu'au moment de composer."""
    from apps.ventes.compatibilites import normaliser_phase
    return normaliser_phase(getattr(lead, 'raccordement', None))


#: Motifs d'ABSTENTION du moteur horaire — la donnée exacte qui manque, pour
#: que ``build_devis_auto`` puisse la NOMMER au commercial au lieu de retomber
#: en silence sur une autre règle (ordre fondateur du 29/08/2026 : il n'y a
#: plus d'autre règle).
MOTIF_FACTURE_ABSENTE = 'facture_absente'
MOTIF_LOCALISATION = 'localisation_inconnue'
MOTIF_CATALOGUE = 'catalogue_incomplet'
MOTIF_MOTEUR_INDISPONIBLE = 'moteur_indisponible'

#: Ce que l'agent doit demander pour chaque motif : ``{motif: (message, champ)}``.
#: Un refus NOMME la donnée manquante — c'est ce qui remplace l'ancien repli
#: silencieux sur la règle des 900 DH/mois.
_REFUS_DIMENSIONNEMENT = {
    MOTIF_FACTURE_ABSENTE: (
        "Données insuffisantes pour dimensionner le devis : renseignez la "
        "facture d'électricité d'hiver (ou la taille souhaitée en kWc) du lead.",
        'facture_hiver'),
    MOTIF_LOCALISATION: (
        "Le chantier n'est pas localisé : renseignez la ville (ou les "
        "coordonnées GPS) du lead — sans elle, le productible solaire du site "
        "est inconnu et aucune taille ne peut être calculée.",
        'ville'),
    MOTIF_CATALOGUE: (
        "Le catalogue de la société ne permet de composer aucune installation "
        "résidentielle pour ce lead : complétez-le (panneau, onduleur) puis "
        "relancez le devis automatique.",
        'catalogue'),
    MOTIF_MOTEUR_INDISPONIBLE: (
        "Le moteur de dimensionnement est momentanément indisponible : le "
        "devis n'a pas été créé plutôt que d'être dimensionné par une autre "
        "règle. Réessayez, ou précisez la taille souhaitée (kWc) du lead.",
        'dimensionnement'),
}


def _refus_dimensionnement(motif):
    """L'``AutoDevisError`` (→ 422) correspondant à un motif d'abstention.

    Motif inconnu ⇒ on refuse quand même, en le citant : on ne crée JAMAIS un
    devis dont la taille viendrait d'ailleurs que du moteur.
    """
    message, champ = _REFUS_DIMENSIONNEMENT.get(
        motif,
        ("Le devis n'a pas pu être dimensionné (motif « %s »)." % motif,
         'dimensionnement'))
    return AutoDevisError(message, field=champ)


def _panneaux_dimensionnement_horaire(*, lead, company, phase):
    """``(nb_panneaux, panel_watt, source, avec)`` recommandés par le moteur.

    C'EST LE SEUL DIMENSIONNEMENT du devis automatique quand aucune puissance
    n'est demandée (ordre fondateur du 29/08/2026). Il n'exige PAS un profil
    d'appel rempli : la seule donnée de consommation nécessaire est la facture
    d'hiver du lead.

    D'OÙ VIENNENT LES kWh QUAND LE LEAD N'A QU'UNE FACTURE. De
    ``etude_horaire.profil_depuis_factures`` → ``serie_mad_mensuelle`` (la
    facture d'hiver répétée sur les douze mois, remplacée par la facture d'été
    sur mai→octobre quand ``ete_differente`` en déclare une distincte) →
    ``serie_kwh_depuis_mad``, qui inverse le VRAI barème ONEE
    (``quote_engine.bareme.kwh_depuis_facture_mad`` : tranches progressives/
    sélectives, location + entretien, TPPAN) — JAMAIS une division par un prix
    moyen, jamais un tarif écrit ici.

    DÉFAUT DE FORME, DOCUMENTÉ (QJR10 / décision fondateur D4 du 29/08/2026).
    Sans réponse d'occupation sur la fiche, la silhouette 24 h est celle du
    DÉFAUT RÉSIDENTIEL FONDATEUR (``courbes_journalieres.DEFAUT_RESIDENTIEL``
    = présence en journée), exactement comme sur l'aperçu écran : le même lead
    ne peut plus être dimensionné sur deux journées différentes selon le chemin
    emprunté. Un équipement déclaré sans sa grandeur n'ajoute aucune couche.
    C'est le SEUL défaut : rien d'autre n'est supposé.

    Traduit la fiche du lead en entrées du dimensionnement, puis lit la
    recommandation. ``panel_watt`` est le wattage du panneau RÉEL sur lequel le
    balayage a décidé : l'appelant doit composer avec le MÊME, sinon la
    puissance livrée ne serait pas celle qui a été évaluée.

    L-2OPT — ``avec`` est le QUATRIÈME élément, et c'est la nouveauté : la
    recommandation de l'axe AVEC BATTERIE (``recommandation_avec``, le balayage
    CONJOINT champ × stockage de DIM2), rendue sous la forme
    ``{'nb_panneaux', 'kwc', 'panel_watt', 'batterie_kwh'}``. Ce gagnant
    existait depuis DIM2 mais n'alimentait AUCUN chemin de génération de
    lignes — il ne servait qu'à l'affichage. ``None`` quand le moteur n'a
    trouvé aucune configuration avec batterie livrable : l'appelant compose
    alors l'option « avec » sur le MÊME champ que l'option « sans »
    (comportement historique — jamais un chiffre inventé pour combler le trou).

    IMPOSSIBILITÉ ⇒ ``(0, None, <motif>, None)`` où ``<motif>`` est l'un des
    ``MOTIF_*`` ci-dessus — la donnée qui manque, NOMMÉE. Il n'y a plus de
    repli : l'appelant refuse le devis en citant ce motif (ordre fondateur —
    « the 900dh path must no longer decide ANY devis »). Ne lève jamais.
    """
    try:
        from apps.ventes.dimensionnement import recommander_taille
        from apps.ventes.domain.entrees import entrees_depuis_lead

        # QJR42 — LECTURE UNIQUE de la fiche : le MÊME adaptateur que le chemin
        # devis (``EntreesMoteur``), donc la même facture, la même
        # localisation, la même occupation (QJR10 / D4 — défaut PRÉSENCE) et
        # les 15 champs d'équipement du sélecteur CRM (QJR9). Il n'y a plus de
        # seconde traduction lead → entrées dans ce module.
        entrees = entrees_depuis_lead(lead, company)
        conso = entrees.conso_kwh_mensuelles if entrees else None
        if not conso:
            return 0, None, MOTIF_FACTURE_ABSENTE, None

        resultat = recommander_taille(
            company=entrees.company, conso_kwh_mensuelles=conso,
            ville=entrees.ville, lat=entrees.lat, lon=entrees.lon,
            occupation=entrees.occupation, equipements=entrees.equipements,
            phase=phase, source_conso=entrees.source_conso,
            jour_reference=entrees.jour_reference,
            # QJR46 — le barème de la SOCIÉTÉ, celui que le devis appliquera.
            tranches=entrees.tranches,
            charges_fixes_mad=entrees.charges_fixes_mad)
        recommandation = resultat.get('recommandation')
        if not recommandation:
            # Le tableau est vide pour DEUX raisons distinctes, et le
            # commercial n'a pas le même geste à faire : un ancrage de
            # productible introuvable se corrige sur la FICHE (ville ou tracé
            # GPS), un catalogue incomplet se corrige dans le CATALOGUE. On
            # relit donc la localisation — lecture en table/cache, pas un
            # second dimensionnement — pour nommer la bonne.
            from apps.parametres.pvgis_profils import productible_mensuel
            situe = productible_mensuel(
                ville=entrees.ville, lat=entrees.lat, lon=entrees.lon)
            return (0, None,
                    MOTIF_CATALOGUE if situe else MOTIF_LOCALISATION, None)
        return (int(recommandation['panneaux']),
                recommandation.get('panel_watt'), 'moteur_horaire',
                _recommandation_avec_rendue(resultat.get('recommandation_avec')))
    except Exception:  # noqa: BLE001 — l'appelant REFUSE le devis (il n'y a
        # plus de règle de repli) : on ne masque pas la panne, on la nomme.
        logger.warning('dimensionnement horaire indisponible', exc_info=True)
        return 0, None, MOTIF_MOTEUR_INDISPONIBLE, None


def _recommandation_avec_rendue(recommandation_avec):
    """L-2OPT — la ligne ``recommandation_avec`` du moteur, réduite à ce que la
    composition sait consommer : ``{nb_panneaux, kwc, panel_watt,
    batterie_kwh}``.

    ``None`` dès que la recommandation est absente ou ne porte pas de nombre de
    panneaux exploitable — REPLI EXPLICITE : l'appelant compose alors l'option
    « avec » sur le champ de l'option « sans », comme aujourd'hui. Aucun
    chiffre n'est ni inventé ni arrondi ici : tout vient du moteur.
    """
    if not isinstance(recommandation_avec, dict):
        return None
    try:
        panneaux = int(recommandation_avec.get('panneaux') or 0)
    except (TypeError, ValueError):
        return None
    if panneaux <= 0:
        return None
    batterie = recommandation_avec.get('batterie_kwh')
    try:
        batterie = float(batterie) if batterie not in (None, '') else None
    except (TypeError, ValueError):
        batterie = None
    return {
        'nb_panneaux': panneaux,
        'kwc': recommandation_avec.get('kwc'),
        'panel_watt': recommandation_avec.get('panel_watt'),
        'batterie_kwh': batterie if batterie and batterie > 0 else None,
    }


def rafraichir_etude_horaire(devis, *, kwc=None, batterie_kwh_utile=None):
    """CJ2a — (re)calcule ``etude_params['etude_horaire']`` et le RANGE.

    Point d'entrée unique pour poser le bloc canonique sur un devis. Écrit avec
    ``update_fields=['etude_params']`` UNIQUEMENT : ce chemin ne peut donc
    toucher NI le statut du devis, NI ses lignes, NI ses totaux (règle #4).

    Bloc non calculable (pas de facture, pas de localisation PVGIS, pas de
    puissance) ⇒ la clé est RETIRÉE plutôt que laissée périmée, et l'appelant
    retombe sur le forfait étiqueté (règle Z2). Ne lève jamais : une étude
    n'empêche pas d'enregistrer un devis.

    QJR44 — le bloc RANGÉ porte en plus ``_empreinte_entrees`` (l'estampille
    des entrées du moteur). La SORTIE du moteur
    (``etude_horaire_pour_devis``) reste byte-identique : l'estampille est
    posée ici, sur la copie persistée, jamais dans le moteur.

    QJR45 — les entrées sont lues UNE fois : le ``jour_reference`` qui part au
    moteur est EXACTEMENT celui que l'empreinte trace (une seconde lecture
    d'horloge pourrait tomber le lendemain et estampiller une date qui n'a pas
    servi).
    """
    from apps.ventes.domain.entrees import empreinte_entrees, entrees_depuis_devis
    from apps.ventes.domain.etude_schema import MOTEUR_HORAIRE, ecrire
    from apps.ventes.etude_horaire import etude_horaire_pour_devis
    try:
        entrees = entrees_depuis_devis(devis)
        bloc = etude_horaire_pour_devis(
            devis, kwc=kwc, batterie_kwh_utile=batterie_kwh_utile,
            jour_reference=(entrees.jour_reference if entrees else None))
        if bloc is None:
            if 'etude_horaire' not in (getattr(devis, 'etude_params', None)
                                       or {}):
                return None
        else:
            bloc = dict(bloc)
            bloc['_empreinte_entrees'] = (
                empreinte_entrees(entrees)
                if entrees is not None and entrees.conso_kwh_mensuelles
                else None)
        # QJR62 — ÉCRIVAIN UNIQUE : la fusion (et le retrait d'une clé posée à
        # ``None``, règle Z2) vit dans ``domain.etude_schema``, plus ici.
        ecrire(devis, proprietaire=MOTEUR_HORAIRE, etude_horaire=bloc)
        return bloc
    except Exception:  # noqa: BLE001 — jamais bloquant pour un devis
        logger.warning('etude_horaire non rafraîchie sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def _bloc_horaire_deja_a_jour(devis, kwc):
    """CJ2b — le bloc rangé sur ce devis décrit-il DÉJÀ cette composition ?

    RAISON D'ÊTRE : ÉVITER UN RECALCUL INUTILE DANS UN HANDLER HTTP. Un calcul
    horaire résout la localisation PVGIS du chantier, ce qui peut coûter un
    appel réseau (cache système de 30 jours, mais un cache froid part sur le
    réseau). Le déclencher à CHAQUE ligne ajoutée/modifiée/retirée ferait payer
    cette latence à l'utilisateur pour un bloc qui n'aurait pas bougé d'un
    chiffre — c'est exactement le genre d'appel qu'on ne veut pas voir
    apparaître dans une boucle d'édition.

    LE CRITÈRE EST CELUI DU MOTEUR, PAS UN SECOND. La tolérance vient de
    ``pricing._HORAIRE_TOLERANCE_KWC`` : ce qui rend un bloc PÉRIMÉ pour le
    document est exactement ce qui le rend À RECALCULER ici. Deux seuils
    différents laisseraient une zone où le document refuse un bloc que ce
    garde-fou juge encore frais — donc un devis sans économies, sans raison
    visible.

    La capacité batterie compte AUSSI : elle change l'autoconsommation et donc
    toutes les économies, sans toucher au kWc (remplacer une batterie 5 kWh par
    une 10 kWh ne bouge pas la puissance PV).

    QJR44 — L'EMPREINTE DES ENTRÉES S'AJOUTE, ELLE NE REMPLACE RIEN. Les deux
    contrôles ci-dessus lisent la COMPOSITION (kWc, capacité batterie) ; ils
    ne voient PAS un changement de PROFIL (facture, localisation, occupation,
    équipements), qui change pourtant toutes les économies du bloc. Le bloc
    n'est donc à jour que si, EN PLUS, l'estampille ``_empreinte_entrees``
    qu'il porte égale l'empreinte des entrées d'aujourd'hui. Un bloc sans
    estampille (antérieur à QJR44) est PÉRIMÉ — un recalcul, une fois.
    La tolérance ``pricing._HORAIRE_TOLERANCE_KWC`` reste celle du moteur :
    deux seuils différents rouvriraient la zone où un devis se retrouve sans
    économies sans raison visible.

    Renvoie ``False`` au moindre doute — on préfère recalculer pour rien que
    servir un bloc qui ne décrit plus le devis.
    """
    bloc = (getattr(devis, 'etude_params', None) or {}).get('etude_horaire')
    if not isinstance(bloc, dict) or not kwc:
        return False
    try:
        from apps.ventes.quote_engine.pricing import _HORAIRE_TOLERANCE_KWC
        kwc_bloc = float(bloc.get('kwc') or 0)
        if kwc_bloc <= 0:
            return False
        if abs(kwc_bloc - float(kwc)) / float(kwc) > _HORAIRE_TOLERANCE_KWC:
            return False
        from apps.ventes.etude_horaire import capacite_batterie_du_devis
        actuelle = capacite_batterie_du_devis(devis)
        rangee = bloc.get('batterie_kwh_utile')
        if (actuelle is None) != (rangee is None):
            return False
        if actuelle is not None and abs(float(actuelle) - float(rangee)) > 0.05:
            return False
        from apps.ventes.domain.entrees import empreinte_entrees_du_devis
        empreinte = empreinte_entrees_du_devis(devis)
        if not empreinte or bloc.get('_empreinte_entrees') != empreinte:
            return False
        return True
    except Exception:  # noqa: BLE001 — au moindre doute, on recalcule
        return False


def rafraichir_etude_horaire_devis(devis, *, force=False):
    """CJ2b — pose le bloc horaire canonique après une écriture SERVEUR d'un
    devis résidentiel (lignes ajoutées/modifiées/retirées, calepinage
    resynchronisé, devis mis à jour).

    Avant CJ2b, ``rafraichir_etude_horaire`` n'était appelé QUE par l'auto-devis
    (voir plus haut) : un devis résidentiel ÉDITÉ ensuite — panneau ajouté ou
    retiré, remplacement d'onduleur — gardait un bloc ``etude_horaire`` PÉRIMÉ
    ou ABSENT, et la page/le PDF retombaient alors sur le modèle « facture »/
    forfait alors qu'un calcul heure par heure exact restait possible. Ce point
    d'entrée unique referme la boucle depuis les chemins d'écriture du devis
    (``DevisViewSet.perform_update``, ``sync-layout``, ``LigneDevisViewSet``).

    RÉSIDENTIEL STRICT (``mode_installation == 'residentiel'``), volontairement
    PLUS STRICT que ``quote_engine.residential.renderer.is_residential`` (qui
    traite un mode VIDE comme résidentiel — un défaut d'AFFICHAGE PDF choisi
    pour ne jamais perdre le rendu d'un devis, pas une preuve que ce devis EST
    résidentiel). Poser un calcul horaire sur un devis dont le marché n'a
    simplement pas encore été choisi calculerait une étude sur une hypothèse
    non confirmée ; un devis dont le mode passe plus tard à 'residentiel'
    reçoit son bloc au prochain enregistrement — aucune perte, un calcul
    seulement différé.

    La puissance kWc vient EXCLUSIVEMENT de
    ``quote_engine.builder.panneaux_et_watt_lu``, sur le MÊME filtre de lignes
    que ``build_quote_data`` (lignes produit, non optionnelles) — jamais une
    seconde règle de dérivation (l'incident DEV-202608-0007 est précisément né
    de deux dérivations qui divergent). Sans panneau lisible, le rafraîchissement
    est appelé QUAND MÊME avec ``kwc=None`` : c'est ``rafraichir_etude_horaire``
    lui-même qui RETIRE alors le bloc devenu périmé plutôt que de le laisser
    décrire une installation qui n'existe plus (règle Z2 appliquée à la
    fraîcheur) — jamais un bloc laissé en place au hasard.

    ``force`` — recalculer MÊME si la composition n'a pas bougé. Les chemins
    « lignes » (ajout/modification/suppression, calepinage) ne touchent QUE la
    composition : quand celle-ci est inchangée, le bloc l'est aussi et
    ``_bloc_horaire_deja_a_jour`` court-circuite un calcul qui peut coûter un
    appel PVGIS. Les chemins « devis » (``perform_update``, ``replace-lines``)
    peuvent en revanche avoir changé les FACTURES ou le profil dans
    ``etude_params`` — grandeurs qu'aucune lecture de lignes ne verrait : ils
    passent ``force=True`` et acceptent le recalcul.

    Ne lève JAMAIS, ne touche NI le statut NI les lignes NI les totaux du devis
    (règle #4) : appelable en toute sécurité juste après une sauvegarde.
    """
    try:
        mode = (getattr(devis, 'mode_installation', None) or '').strip().lower()
        if mode != 'residentiel':
            return None
        from apps.ventes.quote_engine.builder import panneaux_et_watt_lu
        # Même filtre que build_quote_data : lignes PRODUIT non optionnelles
        # (les sections/notes n'ont pas de produit, les add-ons XSAL5 non
        # activés ne comptent pas encore dans la composition réelle).
        lignes = [
            li for li in devis.lignes.select_related(
                'produit', 'produit__fiche_technique').all()
            if getattr(li, 'type_ligne', 'produit') == 'produit'
            and not getattr(li, 'optionnelle', False)
        ]
        nb_panneaux, watt = panneaux_et_watt_lu(lignes)
        kwc = (round(nb_panneaux * watt / 1000, 2)
               if nb_panneaux > 0 and watt else None)
        if not force and _bloc_horaire_deja_a_jour(devis, kwc):
            return (devis.etude_params or {}).get('etude_horaire')
        return rafraichir_etude_horaire(devis, kwc=kwc)
    except Exception:  # noqa: BLE001 — un rafraîchissement raté n'empêche
        # jamais une sauvegarde de devis/ligne.
        logger.warning('rafraichir_etude_horaire_devis indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def entrees_dimensionnement_du_devis(devis, *, contexte=True):
    """RÉ-EXPORT (QJR42) de ``apps.ventes.domain.entrees.entrees_depuis_devis``.

    Le corps a été DÉPLACÉ TEL QUEL dans ``domain/entrees.py``, où il partage
    désormais sa forme (:class:`~apps.ventes.domain.entrees.EntreesMoteur`)
    avec l'adaptateur LEAD du chemin auto-devis / tunnel. Ce nom reste ici
    parce que trois modules l'importent depuis ``services``
    (``dimensionnement``, ``offres_tailles``, et ce module) — le pin
    ``tests/test_services_surface.py`` le vérifie.

    ``contexte=False`` est CONSERVÉ : il saute les lectures de localisation /
    occupation / équipements pour l'appelant qui n'a besoin que de la GARDE
    (voir la docstring de l'original).
    """
    from apps.ventes.domain.entrees import entrees_depuis_devis
    return entrees_depuis_devis(devis, contexte=contexte)


def rafraichir_dimensionnement_devis(devis, *, force=False):
    """T5 (24/08/2026) — pose ``etude_params['dimensionnement']`` sur un devis
    RÉSIDENTIEL, même point d'entrée-esprit que
    :func:`rafraichir_etude_horaire_devis` (RÉSIDENTIEL STRICT, mêmes chemins
    d'écriture) mais pour le TABLEAU de dimensionnement
    (``apps.ventes.dimensionnement.recommander_taille``) plutôt que le bloc
    horaire d'UNE taille : c'est ce que lit désormais le moteur PDF
    (``ETUDE['dimensionnement']``) et le payload public (T4 — falaise,
    tranche visée, régime batterie).

    Contrairement à ``rafraichir_etude_horaire_devis``, aucune donnée de
    LIGNES n'entre dans ce calcul (le tableau balaye TOUTES les tailles
    candidates, il ne lit pas la composition posée).

    QJR43 — L'EMPREINTE DES ENTRÉES DÉCIDE, PLUS LA PRÉSENCE DE LA CLÉ. Le
    bloc rangé porte ``_empreinte`` (``domain.entrees.empreinte_entrees``) et
    n'est recalculé QUE si l'empreinte des entrées d'aujourd'hui en diffère.
    Avant, le test était ``'dimensionnement' in etude_params`` : corriger la
    facture d'hiver, l'occupation ou les équipements du lead ne périmait RIEN,
    et le tableau servi restait celui de la toute première lecture. Un bloc
    SANS ``_empreinte`` (tout devis antérieur à QJR43) est traité comme PÉRIMÉ
    — un recalcul, une seule fois, par devis existant.

    ``force`` reste accepté et signifie désormais « recalcule même si
    l'empreinte concorde » ; il devient inutile sur les chemins qui ne
    changeaient que la composition (QJR47 les retire un par un).

    Ne lève JAMAIS, ne touche NI le statut NI les lignes NI les totaux
    (règle #4). ``None`` (⇒ clé ABSENTE) quand le profil n'est pas
    exploitable (pas de facture, pas de société, catalogue incomplet,
    localisation non résolue) — jamais un tableau inventé.
    """
    try:
        from apps.ventes.domain.entrees import empreinte_entrees
        from apps.ventes.domain.etude_schema import (
            MOTEUR_DIMENSIONNEMENT, ecrire)

        # P2-A / QJR42 — LECTURE UNIQUE des entrées : l'échelle de paliers
        # batterie part exactement des mêmes. Elle est faite AVEC contexte
        # parce que l'empreinte a besoin de la localisation, de l'occupation
        # et des équipements — c'est le prix (une lecture, pas un balayage)
        # d'un cache qui se périme vraiment, et il remplace les DEUX lectures
        # que faisait l'ancien chemin quand il recalculait.
        entrees = entrees_dimensionnement_du_devis(devis)
        if entrees is None:
            return None
        etude_params = entrees['etude_params']
        conso = entrees['conso_kwh_mensuelles']
        if not conso:
            if not force and 'dimensionnement' not in etude_params:
                return None
            # QJR62 — ÉCRIVAIN UNIQUE : ``None`` RETIRE la clé (règle Z2).
            ecrire(devis, proprietaire=MOTEUR_DIMENSIONNEMENT,
                   dimensionnement=None)
            return None

        empreinte = empreinte_entrees(entrees)
        bloc = etude_params.get('dimensionnement')
        if (not force and isinstance(bloc, dict)
                and bloc.get('_empreinte') == empreinte):
            return bloc

        from apps.ventes.dimensionnement import recommander_taille
        resultat = recommander_taille(
            company=entrees['company'], conso_kwh_mensuelles=conso,
            ville=entrees['ville'], lat=entrees['lat'], lon=entrees['lon'],
            occupation=entrees['occupation'],
            equipements=entrees['equipements'],
            source_conso=entrees['source_conso'],
            jour_reference=entrees['jour_reference'],
            # QJR46 — le barème de la SOCIÉTÉ, celui que le devis appliquera.
            tranches=entrees['tranches'],
            charges_fixes_mad=entrees['charges_fixes_mad'])
        resultat['_empreinte'] = empreinte
        ecrire(devis, proprietaire=MOTEUR_DIMENSIONNEMENT,
               dimensionnement=resultat)
        return resultat
    except Exception:  # noqa: BLE001 — un rafraîchissement raté n'empêche
        # jamais une sauvegarde de devis/ligne.
        logger.warning('rafraichir_dimensionnement_devis indisponible sur %s',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None


def rafraichir_etudes_du_devis(devis, *, force=False):
    """L-1V (24/08/2026) — LES QUATRE ÉTUDES D'UN DEVIS, EN UN SEUL GESTE.

    LE TROU QUE CECI BOUCHE. Un devis porte quatre études dérivées de ses
    lignes : le bloc horaire, le tableau de dimensionnement, les profils
    comparatifs et la conception électrique. Trois chemins d'écriture les
    posaient — ``atomic`` et ``replace-lines`` en rafraîchissaient les QUATRE
    (deux listes recopiées à la main, donc deux occasions d'en oublier une),
    tandis que ``LigneDevisViewSet`` (ajout/modification/suppression d'UNE
    ligne) n'en rafraîchissait qu'UNE : le bloc horaire. Modifier une ligne
    depuis l'écran de devis faisait donc bouger le graphe horaire de la page
    client SANS toucher à la conception électrique — et le client voyait un
    schéma unifilaire décrivant une composition qui n'existait plus. Une seule
    fonction, appelée par TOUS les chemins : on ne peut plus en oublier une.

    Chacune est BEST-EFFORT et indépendante (chaque rafraîchisseur avale déjà
    ses propres erreurs) : une étude en échec n'empêche jamais les trois autres,
    et n'annule JAMAIS l'enregistrement du devis ou de la ligne qui l'a
    déclenchée. Aucun statut, aucune ligne, aucun prix n'est touché (règle #4).

    L'ORDRE COMPTE, et il est celui que ``replace-lines`` avait déjà : le
    dimensionnement après le bloc horaire, les profils comparatifs après le
    dimensionnement (le profil RÉEL réutilise alors le tableau qui vient d'être
    calculé au lieu d'en refaire un), la conception électrique en dernier.

    Rend le dict des quatre résultats (``None`` pour celles qui n'ont rien
    produit) — pour un appelant qui veut savoir, jamais pour décider.
    """
    from apps.ventes.profils_comparatifs import (
        rafraichir_profils_comparatifs_devis)
    from apps.ventes.electrical_service import (
        rafraichir_conception_electrique_devis)

    return {
        'etude_horaire': rafraichir_etude_horaire_devis(devis, force=force),
        'dimensionnement': rafraichir_dimensionnement_devis(devis,
                                                            force=force),
        'profils_comparatifs': rafraichir_profils_comparatifs_devis(
            devis, force=force),
        # Idempotente par empreinte : mêmes entrées ⇒ aucune écriture.
        'conception_electrique': rafraichir_conception_electrique_devis(devis),
    }


def _residential_panel_count(*, taille_kwc=None, panel_watt=_AUTO_PANEL_WATT):
    """CONVERSION SEULE : une puissance demandée (kWc) → un nombre de panneaux.

    Ce n'est plus un dimensionnement — c'est de l'arithmétique. La branche
    « facture d'hiver ÷ 900 MAD × 8 panneaux » a été RETIRÉE le 29/08/2026
    (ordre fondateur « ALL sizing should go through the new sizing tool ») :
    une facture se dimensionne désormais par ``_panneaux_dimensionnement_horaire``
    et par rien d'autre. Ne subsiste ici que le chemin SOUVERAIN — la puissance
    que le commercial demande (``target_kwc``) ou que la fiche du lead porte
    (``taille_souhaitee_kwc``).

    U1 — le compte est un PLAFOND (``plafond_panneaux``), comme
    ``panneauxPourKwc`` / ``composition_residentielle`` : on ne descend jamais
    sous la puissance vendue. Renvoie 0 sans taille exploitable (le caller lève
    alors ``AutoDevisError``)."""
    if taille_kwc not in (None, '') and Decimal(str(taille_kwc)) > 0:
        return max(1, plafond_panneaux(float(taille_kwc) * 1000 / panel_watt))
    return 0


#: U3 — les trois scénarios batterie qu'un appelant peut demander POUR CE
#: DEVIS-LÀ, sans jamais réécrire la fiche du lead.
SCENARIOS_DEMANDABLES = ('sans', 'avec', 'les_deux')


def composer_devis_residentiel(*, company, kwc=None, nb_panneaux=0,
                               panel_watt=_AUTO_PANEL_WATT, scenario=None,
                               structure_type='acier',
                               taux_tva=Decimal('20'), mppt_paires=1,
                               gamme_nom_devis=None, phase=None,
                               dimensionnement_avec=None):
    """U3 — LE DRY-RUN : compose sans RIEN créer, et rend le résultat en clair.

    C'est la moitié « à blanc » de la source de vérité : le même catalogue, la
    même fonction pure, les mêmes règles de gamme que ``build_devis_auto`` —
    mais aucune écriture, aucun devis, aucun statut. L'écran générateur s'en
    sert pour PRÉREMPLIR ses lignes éditables au lieu de recomposer de son
    côté ; c'est ce qui fait qu'il n'existe plus « deux sortes de devis ».

    ``kwc`` OU ``nb_panneaux`` suffit : l'un se déduit de l'autre à
    ``panel_watt``. Company-scopé (le catalogue d'une autre société ne fuite
    jamais). Rend un dict SÉRIALISABLE — la forme figée dans
    ``contract_samples/composition_residentielle.json``.

    ``dimensionnement_avec`` (L-2OPT, optionnel) — l'optimum de l'axe AVEC
    BATTERIE (``{'nb_panneaux', 'kwc', 'batterie_kwh'}``), quand le moteur
    calibré en désigne un DIFFÉRENT de l'optimum sans stockage : le dry-run
    compose alors la même FUSION que la création (lignes variantées), sans quoi
    l'aperçu et le devis ne parleraient pas du même kit. ``None`` (LE DÉFAUT)
    ⇒ dry-run strictement inchangé, et chaque ligne rendue porte
    ``variante: ''``.
    """
    kwp = float(kwc or 0)
    nb_force = int(nb_panneaux or 0)
    watt = float(panel_watt or 0) or float(_AUTO_PANEL_WATT)
    if kwp <= 0 and nb_force > 0:
        kwp = nb_force * watt / 1000.0

    demande = (scenario or '').strip().lower()
    if demande and demande not in SCENARIOS_DEMANDABLES:
        raise AutoDevisError(
            'Scénario inconnu « %s » — attendu : %s.'
            % (scenario, ', '.join(SCENARIOS_DEMANDABLES)),
            field='scenario')
    # Même défaut que le devis auto (U2) : sans consigne, on propose LES DEUX.
    avec_batterie = demande == 'avec'
    deux_options = demande not in ('avec', 'sans')

    avertissements = []
    _avec = dimensionnement_avec if isinstance(
        dimensionnement_avec, dict) else None
    _commun = dict(
        panel_watt=watt,
        structure_type=structure_type,
        taux_tva=taux_tva,
        avertissements=avertissements,
        marques=carte_marques_composition(company, gamme_nom_devis),
        ordre_lignes=ordre_lignes_societe(company),
        mppt_paires=mppt_paires,
        # PVCOMPAT — le DRY-RUN doit voir la MÊME contrainte de raccordement
        # que la construction, sinon l'aperçu montrerait un onduleur que le
        # devis ne composerait pas.
        phase=phase,
    )
    if deux_options and _avec:
        lignes = composition_deux_optimiseurs(
            catalogue_de_la_societe(company),
            kwc_sans=kwp,
            nb_panneaux_sans=nb_force,
            kwc_avec=_avec.get('kwc'),
            nb_panneaux_avec=_avec.get('nb_panneaux'),
            batterie_cible_kwh=_avec.get('batterie_kwh'),
            **_commun)
    else:
        lignes = composition_residentielle(
            catalogue_de_la_societe(company),
            kwc=kwp,
            nb_panneaux=nb_force,
            avec_batterie=avec_batterie,
            deux_options=deux_options,
            # L-2OPT — miroir EXACT de ``build_devis_from_layout`` : un devis
            # mono « avec » retient la capacité du même optimum.
            batterie_cible_kwh=(
                _avec.get('batterie_kwh')
                if (avec_batterie and _avec) else None),
            **_commun)

    roles = list(getattr(lignes, 'roles', ()) or ())
    facteur = Decimal('1') + (Decimal(str(taux_tva or 20)) / Decimal('100'))
    rendu = []
    for index, ligne in enumerate(lignes):
        # Le TTC est DÉRIVÉ du HT stocké, jamais l'inverse : l'écran saisit en
        # TTC mais la base fait foi en HT (même aller-retour qu'`htFromTtc`).
        ttc = (Decimal(ligne.prix_unitaire) * facteur).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP)
        rendu.append({
            'ordre': index,
            'role': roles[index] if index < len(roles) else None,
            'produit': getattr(ligne.produit, 'id', None),
            'designation': ligne.designation,
            'quantite': int(ligne.quantite),
            'prix_unitaire_ht': str(Decimal(ligne.prix_unitaire)),
            'prix_unitaire_ttc': str(ttc),
            'taux_tva': str(Decimal(str(taux_tva or 20))),
            # L-2OPT — '' sur toute composition mono-optimum (le cas de tous
            # les aperçus d'hier) : la clé est ADDITIVE, jamais absente.
            'variante': getattr(ligne, 'variante', '') or '',
        })

    return {
        'lignes': rendu,
        'scenario': (SCENARIO_LES_DEUX if deux_options
                     else (SCENARIO_AVEC_BATTERIE if avec_batterie
                           else SCENARIO_SANS_BATTERIE)),
        'nb_panneaux': getattr(lignes, 'nb_panneaux', 0),
        'panel_watt': getattr(lignes, 'panel_watt_reel', watt),
        'kwc_reel': getattr(lignes, 'kwc_reel', 0.0),
        'blocs': getattr(lignes, 'blocs', 1),
        # L-2OPT — l'option « avec » quand elle a son PROPRE champ PV. Sur une
        # composition mono-optimum : ``variantes`` False et les deux valeurs
        # recopient l'option unique — aucun appelant ne peut lire un trou.
        'variantes': bool(getattr(lignes, 'variantes', False)),
        'nb_panneaux_avec': (getattr(lignes, 'nb_panneaux_avec', 0)
                             or getattr(lignes, 'nb_panneaux', 0)),
        'kwc_reel_avec': (getattr(lignes, 'kwc_reel_avec', 0.0)
                          or getattr(lignes, 'kwc_reel', 0.0)),
        'avertissements': list(avertissements),
        'marques_manquantes': [
            {**m, 'libelle_role': _libelle_role(m.get('role'))}
            for m in (getattr(lignes, 'marques_manquantes', ()) or ())
        ],
    }


def build_devis_auto(*, lead, user, company, taux_tva=Decimal('20'),
                     remise_globale=Decimal('0'), target_kwc=None,
                     scenario=None, etude_extra=None, plafond_toit=None,
                     journal_auto=None):
    """Crée un devis RÉSIDENTIEL automatiquement dimensionné depuis la fiche lead.

    Dimensionne le champ PV par le MOTEUR HORAIRE (ordre fondateur du
    29/08/2026 : « ALL sizing should go through the new sizing tool ») — sauf
    si une PUISSANCE est demandée (``target_kwc``, sinon la taille souhaitée du
    lead), auquel cas cette puissance est souveraine. Puis compose PAR DÉFAUT
    la forme DEUX OPTIONS
    (« sans batterie » ET « avec batterie » — U2 ; un ``batterie_souhaitee``
    explicite du lead, « avec » ou « sans », reste souverain et compose cette
    option-là seule) et délègue à ``build_devis_from_layout``
    (sélection catalogue, numérotation anti-collision, devis ``brouillon``). Lève
    ``AutoDevisError`` (→ 422) si le marché n'est pas résidentiel ou si aucune
    donnée de dimensionnement n'est exploitable — l'agent demande alors la donnée
    plutôt que de produire un devis vide. Ne change aucun statut (règle #4).

    Trois réglages POUR CE DEVIS-LÀ (U3), qui ne réécrivent JAMAIS la fiche du
    lead — c'est un choix ponctuel du commercial, pas une correction du lead :

    * ``target_kwc`` — puissance cible demandée (EZ5) ; passe devant la taille
      souhaitée du lead ET devant le dimensionnement du moteur.
    * ``scenario`` — ``'sans'`` / ``'avec'`` / ``'les_deux'`` ; passe devant le
      ``batterie_souhaitee`` du lead. Absent : c'est le lead qui décide, et son
      silence vaut « les deux » (U2).
    * ``etude_extra`` — clés d'étude à FUSIONNER dans ``etude_params`` (les
      factures mensuelles réelles du contrat PACT10, par exemple). Elles
      complètent ce que la construction a déjà écrit, sans jamais écraser le
      scénario arrêté ci-dessus.

    AUTO-PIPELINE (26/08/2026) — deux paramètres de plus, tous deux OPTIONNELS
    et sans effet quand ils sont absents (l'endpoint ``/devis/auto/`` est donc
    inchangé) :

    * ``plafond_toit`` — borne PHYSIQUE dure en panneaux (cf.
      ``plafond_physique_du_contour``). Elle ne peut que RÉDUIRE : jamais une
      cible relevée, jamais un chiffre ajouté au devis.
    * ``journal_auto`` — dict que l'appelant fournit pour recevoir ce qui s'est
      décidé sans lui (``plafond_applique``, ``panneaux_avant_plafond``,
      ``contour_client``), afin de pouvoir l'écrire NOIR SUR BLANC dans
      l'historique du lead. Rien n'y est écrit s'il n'est pas fourni.

    Et, quand le lead porte un tracé de toit, le layout du devis embarque
    désormais ce tracé comme VRAIE zone de calepinage
    (``zone_toit_depuis_contour``) : l'écran 3D ouvre sur le toit du client,
    déjà pavé, au lieu d'une carte vierge.
    """
    marche = (getattr(lead, 'type_installation', '') or '').lower()
    if marche and marche != 'residentiel':
        raise AutoDevisError(
            "L'auto-devis ne gère que le résidentiel pour l'instant. Pour "
            "l'industriel/commercial ou l'agricole, utilisez l'écran générateur "
            "de devis.",
            field='type_installation')

    taille_kwc = getattr(lead, 'taille_souhaitee_kwc', None)
    # U3/EZ5 — une cible demandée pour CE devis passe devant les deux données
    # du lead, sans les réécrire.
    cible = None
    if target_kwc not in (None, ''):
        from decimal import InvalidOperation
        try:
            cible = Decimal(str(target_kwc))
        except (InvalidOperation, TypeError, ValueError):
            raise AutoDevisError(
                'Puissance cible invalide.', field='target_kwc')
        if cible <= 0:
            raise AutoDevisError(
                'La puissance cible doit être supérieure à zéro.',
                field='target_kwc')
    # ── ORDRE FONDATEUR (29/08/2026) — TOUT PASSE PAR LE MOTEUR ─────────────
    # « why do i bloody have the 900dh path — all sizing should go through the
    # new sizing tool, and i said ALL sizing ».
    #
    # DEUX chemins, et deux seulement :
    #
    #   1. UNE PUISSANCE EST DEMANDÉE — ``target_kwc`` pour ce devis, sinon la
    #      ``taille_souhaitee_kwc`` de la fiche : elle est SOUVERAINE (le
    #      commercial sait ce qu'il vend). Simple conversion kWc → panneaux.
    #   2. SINON — le MOTEUR HORAIRE dimensionne, dès qu'une donnée de
    #      consommation existe (la facture d'hiver suffit : elle est inversée
    #      au barème ONEE réel, la forme 24 h vient de la silhouette de repli
    #      documentée). Il n'y a PLUS de troisième chemin : la règle des
    #      900 DH/mois ne décide plus aucun devis. Si le moteur ne peut pas
    #      dimensionner, on REFUSE en nommant la donnée manquante — jamais un
    #      repli silencieux qui donnerait au client une taille issue d'une
    #      autre règle que celle affichée sur sa proposition.
    panneaux = 0
    # Le wattage du panneau doit être CELUI SUR LEQUEL LE BALAYAGE A DÉCIDÉ :
    # dimensionner sur un panneau de 550 Wc puis composer à 710 Wc livrerait
    # une autre puissance que celle qui a été évaluée.
    watt_dimensionnement = _AUTO_PANEL_WATT
    # L-2OPT — ce que le moteur recommande POUR L'AXE AVEC BATTERIE. ``None``
    # sur le chemin souverain : une puissance demandée par le commercial vaut
    # pour les deux options.
    optimum_avec = None
    taille_demandee = cible if cible is not None else taille_kwc
    # Une taille NULLE ou illisible sur la fiche ne « demande » rien : elle
    # laisse la main au moteur plutôt que de refuser un lead parfaitement
    # dimensionnable (``target_kwc``, lui, a déjà été validé plus haut).
    if taille_demandee not in (None, ''):
        panneaux = _residential_panel_count(taille_kwc=taille_demandee)
    if panneaux > 0:
        source_dimensionnement = 'taille_demandee'
    else:
        panneaux, watt_retenu, source_dimensionnement, optimum_avec = (
            _panneaux_dimensionnement_horaire(
                lead=lead, company=company,
                phase=phase_client_pour_dimensionnement(lead)))
        if panneaux <= 0:
            raise _refus_dimensionnement(source_dimensionnement)
        if watt_retenu:
            watt_dimensionnement = watt_retenu

    kwc = round(panneaux * watt_dimensionnement / 1000, 2)
    # ── U2 (fondateur 20/08/2026) — LE DÉFAUT EST « LES DEUX OPTIONS » ──────
    # « le devis auto sort SANS batterie alors que le calepinage 3D sort AVEC ;
    # le DÉFAUT doit être le devis avec LES DEUX options ». Le devis auto ne
    # choisissait à la place du client que parce que le lead ne disait rien :
    # un lead SANS préférence de batterie repartait en « réseau », donc sans
    # stockage ni onduleur hybride, et le client ne voyait jamais l'option.
    # Désormais le silence du lead veut dire « propose les deux » — c'est la
    # forme que la proposition résidentielle sait déjà rendre.
    #
    # Un choix EXPLICITE du lead reste souverain : « avec » compose l'hybride
    # + batterie seuls, « sans » compose le réseau seul. On ne repropose pas
    # une option que le client a déjà écartée.
    # U3 — un scénario demandé POUR CE DEVIS passe devant la fiche du lead.
    demande = (scenario or '').strip().lower()
    if demande and demande not in SCENARIOS_DEMANDABLES:
        raise AutoDevisError(
            'Scénario inconnu « %s » — attendu : %s.'
            % (scenario, ', '.join(SCENARIOS_DEMANDABLES)),
            field='scenario')
    choix_batterie = (
        demande if demande
        else (getattr(lead, 'batterie_souhaitee', '') or '').strip())
    wants_battery = choix_batterie == 'avec'
    deux_options = choix_batterie not in ('avec', 'sans')

    # ── L-2OPT — L'AXE « AVEC BATTERIE » A SON PROPRE OPTIMUM ───────────────
    # Le moteur calibré désigne DEUX gagnants (DIM2) : ``recommandation`` au
    # meilleur payback SANS stockage, et ``recommandation_avec`` au meilleur
    # payback AVEC — issus d'un balayage CONJOINT champ × stockage. Le second
    # n'alimentait aucune ligne de devis.
    #
    #   · scénario MONO « avec » — le devis ne propose QUE le stockage : il
    #     doit donc être dimensionné sur l'optimum AVEC, pas sur celui d'un
    #     champ sans batterie que personne n'achètera. C'est tout l'objet de ce
    #     chantier ;
    #   · scénario « les deux » — les deux champs partent au devis, fusionnés
    #     en lignes variantées (cf. ``composition_deux_optimiseurs``) ;
    #   · scénario MONO « sans » — RIEN ne change : l'optimum « avec » ne le
    #     concerne pas.
    if wants_battery and optimum_avec:
        panneaux = int(optimum_avec['nb_panneaux'])
        watt_avec = optimum_avec.get('panel_watt')
        if watt_avec:
            watt_dimensionnement = float(watt_avec)
        kwc = round(panneaux * watt_dimensionnement / 1000, 2)
        source_dimensionnement = 'moteur_horaire_avec'
    elif not deux_options:
        # Mono « sans » : l'optimum « avec » n'a rien à faire dans ce devis.
        optimum_avec = None

    # ── AUTO-PIPELINE — LE PLAFOND PHYSIQUE DU TOIT, S'IL EST CONNU ────────
    # Il ne peut que RÉDUIRE, et il ne mord que sur une cible physiquement
    # impossible (surface du contour ÷ surface d'un panneau — voir
    # ``plafond_physique_du_contour`` pour pourquoi c'est le seul plafond
    # honnête à prononcer ici). Le plafond de CALEPINAGE, lui, reste celui du
    # moteur qui dessine, à l'écran.
    if plafond_toit:
        try:
            plafond = int(plafond_toit)
        except (TypeError, ValueError):
            plafond = 0
        if plafond > 0 and panneaux > plafond:
            logger.warning(
                'Auto-devis (lead %s): cible de %d panneaux ramenée à %d — '
                'le tracé du client ne peut pas en porter davantage.',
                getattr(lead, 'pk', '?'), panneaux, plafond)
            if isinstance(journal_auto, dict):
                journal_auto['panneaux_avant_plafond'] = panneaux
                journal_auto['plafond_applique'] = plafond
            panneaux = plafond
            kwc = round(panneaux * watt_dimensionnement / 1000, 2)
            if optimum_avec and int(optimum_avec.get('nb_panneaux') or 0) > plafond:
                # L'axe « avec batterie » subit le MÊME toit : sans cela le
                # devis proposerait une option qui ne rentre pas.
                optimum_avec = dict(optimum_avec)
                optimum_avec['nb_panneaux'] = plafond
                watt_avec = optimum_avec.get('panel_watt') or watt_dimensionnement
                optimum_avec['kwc'] = round(plafond * float(watt_avec) / 1000, 2)

    layout = {
        'result': {'panels': panneaux, 'kwc': kwc},
        'panelWatt': watt_dimensionnement,
        'scenario': 'avec_batterie' if wants_battery else 'reseau',
    }
    # ── AUTO-PIPELINE — LE TRACÉ DU CLIENT DEVIENT LA ZONE DU CALEPINAGE ───
    # Sans ces clés, le layout d'un devis automatique ne décrit AUCUNE
    # géométrie : l'écran 3D s'ouvrait sur une carte vierge et le commercial
    # devait re-tracer le toit pour voir un seul panneau, alors que le client
    # l'avait déjà dessiné. Avec elles, l'écran ouvre sur le contour du client
    # et le pave immédiatement. Absent de tracé → dict vide → comportement
    # STRICTEMENT inchangé.
    zone_client = zone_toit_depuis_contour(lead, panneaux=panneaux, kwc=kwc)
    if zone_client:
        layout.update(zone_client)
        if isinstance(journal_auto, dict):
            journal_auto['contour_client'] = len(zone_client['outline'])
    # ── U3 — GARDE MARQUE ÉPINGLÉE, portée côté SERVEUR ────────────────────
    # Cette garde ne vivait que dans `createAutoQuote` : le chemin backend en
    # était dépourvu. Une marque réglée dans Paramètres → Gammes mais absente
    # du stock VIDE le vivier de son rôle — le devis serait parti sans
    # panneaux, à un prix effondré.
    #
    # On le découvre par un DRY-RUN : exactement la composition qui sera
    # créée, sans aucune écriture. Refuser AVANT de créer vaut mieux que créer
    # puis effacer — un devis effacé rendrait sa référence au compteur, et le
    # numéro suivant la reprendrait.
    # ── PVCOMPAT — LE RACCORDEMENT DU CLIENT DESCEND JUSQU'À LA COMPOSITION ──
    # ``crm.Lead.raccordement`` ('monophase'/'triphase'/'inconnu') existe depuis
    # l'assistant du site et n'était lu NULLE PART côté composition : un client
    # monophasé pouvait se voir composer un onduleur triphasé, impossible à
    # raccorder chez lui. « inconnu » (ou vide) laisse la composition décider
    # exactement comme avant. Le DRY-RUN le reçoit aussi, sinon l'aperçu et le
    # devis ne parleraient pas du même onduleur.
    from apps.ventes.compatibilites import normaliser_phase
    phase_client = normaliser_phase(getattr(lead, 'raccordement', None))

    apercu = composer_devis_residentiel(
        company=company, nb_panneaux=panneaux,
        panel_watt=watt_dimensionnement,
        scenario=choix_batterie or 'les_deux', taux_tva=taux_tva,
        phase=phase_client,
        # L-2OPT — le DRY-RUN voit EXACTEMENT la composition qui sera créée,
        # fusion comprise : sans cela il contrôlerait les marques d'un kit qui
        # n'est pas celui du devis.
        dimensionnement_avec=optimum_avec)
    if apercu['marques_manquantes']:
        detail = ', '.join(
            '%s (%s)' % (m.get('marque'), m.get('libelle_role'))
            for m in apercu['marques_manquantes'])
        raise AutoDevisError(
            'Marque épinglée introuvable au stock : %s. Ajoutez le produit ou '
            'changez la marque dans Paramètres → Gammes.' % detail,
            field='marques')

    journal = {}
    devis = build_devis_from_layout(
        layout=layout, user=user, company=company, lead=lead,
        taux_tva=taux_tva, remise_globale=remise_globale,
        deux_options=deux_options, journal=journal, phase=phase_client,
        dimensionnement_avec=optimum_avec)
    for avertissement in journal.get('avertissements') or []:
        logger.warning('Auto-devis %s: %s', devis.reference, avertissement)

    # QJR63 — LE kWc EST POSÉ PAR SON PROPRIÉTAIRE, sur les lignes RÉELLEMENT
    # composées : ni ``target_kwc``, ni ``lead.taille_souhaitee_kwc``, qui sont
    # des DEMANDES et non ce que le catalogue a su servir (l'arrondi au palier
    # et le plafond de toit peuvent faire atterrir ailleurs).
    poser_puissance_kwc(devis)

    # U3/PACT10 — les clés d'étude apportées par l'appelant (factures
    # mensuelles réelles, consommation annuelle, distributeur) COMPLÈTENT
    # l'étude déjà écrite par la construction.
    if isinstance(etude_extra, dict) and etude_extra:
        # QJR62 — ÉCRIVAIN UNIQUE : la fusion vit dans ``domain.etude_schema``.
        # QJR64 / D12 — LE SCÉNARIO PASSE PAR LE REGISTRE, plus par un cas
        # particulier codé en dur. Le scénario qui fait foi est
        # ``scenario_effectif`` (surcharge déclarée, sinon celui que la
        # construction vient d'arrêter) : un corps de requête ne peut plus
        # l'écraser, et une déclaration humaine survit à tout recalcul aval.
        from apps.ventes.domain.etude_schema import AUTO_DEVIS, ecrire
        _scenario_arrete = scenario_effectif(
            devis, (devis.etude_params or {}).get('scenario'))
        _extra = {cle: valeur for cle, valeur in etude_extra.items()
                  if not (_scenario_arrete and cle == 'scenario')}
        if _scenario_arrete and _scenario_arrete != (
                devis.etude_params or {}).get('scenario'):
            _extra['scenario'] = _scenario_arrete
        if _extra:
            try:
                ecrire(devis, proprietaire=AUTO_DEVIS, **_extra)
            except ValueError as exc:
                # ``etude_extra`` vient du CORPS DE REQUÊTE : un refus du
                # schéma doit sortir en 422 NOMMÉ, jamais en 500.
                raise AutoDevisError(str(exc), field='etude_params')

    # L-1V (incident test16, 27/08/2026) — LES QUATRE ÉTUDES EN UN SEUL GESTE,
    # comme sur les chemins d'écriture du générateur (``atomic``,
    # ``replace-lines``, ``sync-layout``). Ce chemin gardait l'appel CJ2a
    # d'origine (bloc horaire SEUL) : un devis automatique naissait sans
    # ``dimensionnement``, et la page client perdait d'un coup les trois
    # tailles Éco/Recommandé/Max, la tranche tarifaire, le régime batterie,
    # le balayage de stockage et les profils comparatifs — jusqu'à la première
    # édition manuelle (DEV-202608-0033/0034). Posé APRÈS la fusion
    # ``etude_extra`` ci-dessus (les factures réelles nourrissent le
    # dimensionnement), toujours APRÈS la construction (la puissance et le
    # stockage réellement composés), best-effort et non bloquant : un devis
    # reste parfaitement valide sans ses études.
    # QJR47 — ``force=True`` RETIRÉ : le devis vient de NAÎTRE, il ne porte
    # aucun bloc estampillé, donc les quatre études se calculent de toute
    # façon (et la fusion ``etude_extra`` ci-dessus est déjà entrée dans
    # l'empreinte des entrées).
    rafraichir_etudes_du_devis(devis)

    logger.info(
        'Auto-devis %s: %d panneaux, %.2f kWc, batterie=%s, deux_options=%s, '
        'dimensionnement=%s (company %s)',
        devis.reference, panneaux, kwc, wants_battery, deux_options,
        source_dimensionnement, getattr(company, 'id', '?'))
    return devis


# ════════════════════════════════════════════════════════════════════════════
# AUTO-PIPELINE — DU TRACÉ DU CLIENT AU DEVIS BROUILLON, SANS MAIN HUMAINE
# ════════════════════════════════════════════════════════════════════════════
#
# ORDRE FONDATEUR (26/08/2026) : « si le client dessine son toit dans le
# tunnel, alors une fois que le lead arrive dans notre ERP ça crée
# automatiquement le devis automatique, et l'outil de calepinage dessine les
# panneaux tout seul — le commercial ne fait que VÉRIFIER ce qui a été fait
# automatiquement. »
#
# CE QUI N'EST PAS RÉINVENTÉ ICI (et ne doit jamais l'être) :
#   · le DIMENSIONNEMENT reste celui de ``build_devis_auto`` — facture d'hiver
#     ou profil horaire réel : exactement les mêmes chiffres qu'une création
#     manuelle, aucun nombre neuf n'entre dans le devis par ce chemin ;
#   · la COMPOSITION reste la source unique U3 (``composition_residentielle`` /
#     ``composition_deux_optimiseurs``) ;
#   · la NUMÉROTATION reste ``core.numbering`` (highest-used+1, JAMAIS
#     count()+1) via ``build_devis_from_layout`` ;
#   · le DESSIN des panneaux reste l'affaire du moteur de calepinage de
#     l'écran — celui-là même que le tunnel public utilise pour son estimation.
#     Un layout sérialisé ne transporte JAMAIS de pose : ``deserializeLayout``
#     rend ses zones avec ``result: null, renderPlan: null`` et l'écran re-pave
#     au boot. Poser des panneaux côté serveur avec un SECOND moteur ne ferait
#     donc qu'inventer un dessin que l'écran contredirait aussitôt.
#
# CE QUE CE BLOC FAIT, ET RIEN D'AUTRE : il transforme ``Lead.roof_outline`` en
# une VRAIE zone de toit dans le layout du devis, pour que l'écran ait le
# contour du client à paver au boot au lieu d'une page blanche.

_AUTO_ZONE_ID = 'area-1'
# ── CE QUE LA ZONE AUTOMATIQUE NE DIT PAS, ET POURQUOI (F2) ─────────────────
# Elle n'écrit NI ``roofType``, NI ``pitchDeg``, NI ``facingAzimuthDeg``.
#
# La première version les posait aux valeurs de la zone vierge du builder
# (``newAreaRecord()`` : flat / 22° / 180°) en se disant « ce sont les réglages
# que l'écran afficherait de toute façon ». À l'écran, oui — et ils y sont
# VISIBLEMENT MODIFIABLES. Mais un champ écrit dans le layout ne s'arrête pas
# à l'écran : il descend ``extract_roof_config`` → ``_pans_geometry`` →
# ``calepinage_options.parametres_site_publics``, et le CLIENT lisait alors
# « Orientation Sud (180°) · Inclinaison 22° · Toit plat » dans l'annexe
# « paramètres du site » de sa proposition — présenté comme un relevé, sur un
# toit que personne n'a mesuré. Avant ce lot ces trois champs étaient ABSENTS
# d'un devis automatique ; ils le restent.
#
# L'écran, lui, ne perd rien : ``deserializeLayout`` applique ses propres
# valeurs par défaut quand la clé manque (apps/web prefill.ts) — donc le
# commercial voit et corrige exactement ce qu'il verrait après avoir tracé le
# contour à la main. Dès qu'il enregistre, ``serializeLayout`` écrit les trois
# champs pour de bon et l'annexe les publie : un chiffre n'est publié qu'une
# fois qu'un humain l'a regardé.


def contour_client_lnglat(lead):
    """Le tracé du client en ``[[lng, lat], …]`` (convention builder), ou ``[]``.

    MÊMES règles que ``referenceContourRing`` (apps/web prefill.ts) et que
    ``normaliserContour`` (frontend traceToit.js) : les DEUX formes réellement
    stockées dans ``Lead.roof_outline`` — ``[lat, lng]`` (posée par le webhook,
    cf. ``_clean_roof_outline``) et ``{lat, lng}`` (import / saisie manuelle) —
    le MÊME bornage lat ∈ [-90, 90] / lng ∈ [-180, 180], et le MÊME seuil de
    3 sommets (un polygone commence à 3). Jamais une version plus permissive :
    un contour que l'écran refuse de dessiner ne doit pas devenir une zone
    côté serveur.
    """
    brut = getattr(lead, 'roof_outline', None)
    if not isinstance(brut, (list, tuple)):
        return []
    anneau = []
    for point in brut:
        if isinstance(point, dict):
            lat, lng = point.get('lat'), point.get('lng')
        elif isinstance(point, (list, tuple)) and len(point) >= 2:
            lat, lng = point[0], point[1]
        else:
            continue
        try:
            lat, lng = float(lat), float(lng)
        except (TypeError, ValueError):
            continue
        # Ce test rejette AUSSI les NaN : toute comparaison avec NaN est
        # fausse, donc `-90 <= nan <= 90` l'est, et le point est écarté. (Un
        # second garde-fou `lat != lat` vivait ici : il était inatteignable.)
        if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
            continue
        anneau.append([lng, lat])
    return anneau if len(anneau) >= 3 else []


def aire_contour_m2(contour):
    """L'aire (m²) d'un contour ``[[lng, lat], …]``, ou ``None``.

    Reprojection ENU par ``calepinage_options.anneau_enu`` (la formule DÉJÀ
    partagée avec l'écran), puis lacet de souliers. Aucune approximation
    maison : c'est la surface du polygone que le client a réellement tracé.
    """
    if len(contour or []) < 3:
        return None
    from .calepinage_options import anneau_enu

    origine = contour[0]
    anneau = anneau_enu(contour, origine)
    if len(anneau) < 3:
        return None
    aire2 = 0.0
    for i in range(len(anneau)):
        ax, ay = anneau[i]
        bx, by = anneau[(i + 1) % len(anneau)]
        aire2 += ax * by - bx * ay
    aire = abs(aire2) / 2.0
    return aire if aire > 0 else None


def plafond_physique_du_contour(contour, produit_panneau):
    """Le nombre de panneaux qu'un toit de cette SURFACE ne peut PAS dépasser.

    ``None`` dès qu'une donnée manque (contour illisible, produit sans
    dimensions) — jamais un plafond deviné.

    C'est une BORNE PHYSIQUE DURE, pas un calepinage : ``aire du contour ÷ aire
    d'un panneau``. Deux propriétés en font le seul plafond honnête qu'on
    puisse poser côté serveur :

    * elle ne dépend d'AUCUN paramètre que le client ne nous a pas donné (ni
      pente, ni azimut, ni retrait de rive, ni obstacles) — donc elle
      n'invente rien ;
    * elle est LARGE par construction (un calepinage réel tient toujours
      nettement moins que la surface brute), donc elle ne rabote jamais un
      devis légitime : elle n'attrape que les cibles physiquement impossibles.

    Le vrai plafond de calepinage, lui, est prononcé par le SEUL moteur qui
    dessine — celui de l'écran, au boot — qui pose le maximum tenable et lève
    son avertissement existant. Poser ici un second moteur (pente et azimut
    devinés) donnerait un nombre que l'écran contredirait : c'est exactement le
    piège que le drapeau ``USE_MOTEUR_CALEPINAGE`` existe pour tenir fermé.

    LES DIMENSIONS VIENNENT DE LA FICHE TECHNIQUE, PAS DU PRODUIT. Une première
    version lisait ``produit.longueur_mm``/``largeur_mm`` : ces champs
    n'existent PAS sur ``stock.Produit``, ils vivent sur sa ``FicheTechnique``
    (PV5). ``getattr(..., None)`` rendait donc silencieusement ``None`` et le
    plafond ne s'appliquait JAMAIS — une garde morte, verte en apparence. On
    passe désormais par ``stock.selectors.kit_from_produit`` (lecture cross-app
    sanctionnée, jamais ``stock.models``), qui est déjà LA source unique des
    dimensions réelles d'un module pour le moteur de calepinage : elle rend
    ``None`` dès qu'une des grandeurs requises manque, exactement la règle
    « on ne devine jamais une géométrie ».

    Conséquence assumée : sans fiche technique complète sur le panneau, il n'y
    a PAS de plafond. C'est le bon défaut — un plafond inventé serait pire que
    pas de plafond.
    """
    aire_toit = aire_contour_m2(contour)
    if not aire_toit or produit_panneau is None:
        return None
    try:
        from apps.stock.selectors import kit_from_produit
        kit = kit_from_produit(produit_panneau)
    except Exception:  # noqa: BLE001 — un catalogue illisible n'est pas un plafond
        logger.warning('Auto-devis: dimensions du panneau illisibles — aucun '
                       'plafond de toit appliqué.', exc_info=True)
        return None
    if kit is None:
        return None
    aire_panneau = float(kit.module_long_m) * float(kit.module_court_m)
    if aire_panneau <= 0:
        return None
    plafond = int(aire_toit // aire_panneau)
    return plafond if plafond > 0 else None


def zone_toit_depuis_contour(lead, *, panneaux, kwc=None):
    """Le fragment de layout roofPro11 qui porte le tracé du CLIENT, ou ``{}``.

    Rend exactement les clés que ``SerializedLayout`` déclare — ``version``,
    ``pin``, ``outline``, ``zones``, ``activeAreaId`` — donc ce que
    ``deserializeLayout`` / ``hydrateFromDevis`` savent déjà relire : l'écran
    ouvre alors sur la zone du client, la ferme et la pave, sans qu'un
    commercial ait à re-tracer quoi que ce soit.

    ``outline`` est en ``[[lat, lng], …]`` et ``zones[].vertices`` en
    ``[[lng, lat], …]`` : ce sont les DEUX conventions de ``serializeLayout``,
    respectées telles quelles (les inverser ferait atterrir le toit à des
    milliers de kilomètres).

    ``neededPanels`` porte la cible du devis et ``neededAuto`` vaut ``False`` :
    c'est le nombre VENDU qui pilote l'optimiseur, jamais un remplissage
    « au mieux ». Si la cible ne tient pas, l'écran pose le maximum et lève son
    avertissement — le plafond est prononcé par le moteur qui dessine.
    """
    contour = contour_client_lnglat(lead)
    if not contour:
        return {}
    point = getattr(lead, 'roof_point', None)
    pin = None
    if isinstance(point, dict):
        try:
            pin = {'lat': float(point['lat']), 'lng': float(point['lng'])}
        except (KeyError, TypeError, ValueError):
            pin = None
    if pin is None:
        # Centroïde du contour — MÊME repli que ``centroidOf`` côté écran
        # (moyenne des sommets), une valeur DÉRIVÉE du tracé réel, jamais une
        # position inventée.
        pin = {'lng': sum(p[0] for p in contour) / len(contour),
               'lat': sum(p[1] for p in contour) / len(contour)}
    cible = max(int(panneaux or 0), 0)
    # ``result`` par pan — les TROIS chiffres que ``extract_roof_config`` lit
    # pour écrire ``etude_params['toiture']``. Sans lui, la config toiture d'un
    # devis automatique repartait à « 0 kWc / 0 m² » : un zéro affiché est pire
    # qu'une absence. Les trois sont DÉRIVÉS et traçables — le compte est la
    # cible réellement composée, la puissance est celle du devis (le MÊME
    # ``result.kwc`` racine), et la surface est celle du polygone que le client
    # a tracé, mesurée par ``aire_contour_m2``. Aucun n'est neuf.
    resultat_pan = {'count': cible}
    if kwc:
        resultat_pan['kwc'] = float(kwc)
    aire = aire_contour_m2(contour)
    if aire:
        resultat_pan['areaM2'] = round(aire, 2)
    return {
        'version': 2,
        'pin': pin,
        'outline': [[lat, lng] for lng, lat in contour],
        'zones': [{
            'id': _AUTO_ZONE_ID,
            'label': 'Toit du client',
            'vertices': [list(p) for p in contour],
            'obstacles': [],
            # PAS de roofType / pitchDeg / facingAzimuthDeg : voir le bloc
            # « CE QUE LA ZONE AUTOMATIQUE NE DIT PAS » ci-dessus. `facingManual`
            # reste faux et le dit : personne n'a fixé d'orientation.
            'facingManual': False,
            'neededPanels': cible,
            'neededAuto': False,
            # Additif : ``deserializeLayout`` ignore les clés qu'il ne déclare
            # pas (il repave au boot de toute façon) — ceci ne sert qu'aux
            # lecteurs SERVEUR du layout.
            'result': resultat_pan,
        }],
        'activeAreaId': _AUTO_ZONE_ID,
        'source': 'lead',
        # Marqueur INTERNE (préfixe `_`, comme ``_pans_geometry``) : il dit que
        # cette zone vient du tracé du client et n'a jamais été validée par un
        # humain. L'écran s'en sert pour afficher « à vérifier » ; personne ne
        # doit le prendre pour une géométrie relevée.
        '_origine_calepinage': 'contour_client',
    }


def auto_devis_tunnel_actif(company):
    """La société veut-elle des devis automatiques depuis le tunnel ?

    Réglage de société (``parametres.CompanyProfile.devis_auto_depuis_tunnel``),
    ACTIF par défaut — c'est le flux que le fondateur a demandé. Une société
    qui n'a pas encore de profil hérite donc du défaut, jamais d'un « non »
    silencieux ; un profil illisible vaut « non » (on ne crée pas de document
    sur une lecture ratée).
    """
    try:
        from apps.parametres.models import CompanyProfile
        profil = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — table absente / migration en cours
        logger.warning(
            'Auto-devis: profil de société illisible (company %s) — '
            'création automatique désactivée par prudence.',
            getattr(company, 'pk', '?'))
        return False
    if profil is None:
        return True
    return bool(getattr(profil, 'devis_auto_depuis_tunnel', True))


_MARQUE_AUTO_DEVIS = 'ventes.auto_devis'


def _liberer_marque_auto_devis(company, lead_id):
    """F5 — RELÂCHE la marque d'achèvement d'un lead dont la création a échoué.

    ``dedupe_event`` pose sa ligne AVANT le travail — c'est ce qui lui permet
    de départager deux workers simultanés. Mais laissée en place après un
    échec, cette même ligne devient une porte fermée DÉFINITIVEMENT : un lead
    sans facture aujourd'hui, ou un catalogue momentanément incomplet, et plus
    jamais personne — ni un rejeu, ni un appel manuel du service — ne pourrait
    lui créer son devis automatique. La marque doit donc dire « c'est FAIT »,
    pas « ça a été tenté ».

    Best-effort et silencieuse sur erreur : elle est appelée depuis des
    chemins d'exception, et ne doit jamais masquer l'erreur d'origine.
    """
    try:
        from core.idempotency import ProcessedWebhookEvent
        ProcessedWebhookEvent.objects.filter(
            company=company, source=_MARQUE_AUTO_DEVIS,
            event_id=str(lead_id)).delete()
    except Exception:  # noqa: BLE001 — jamais au-dessus de l'erreur d'origine
        logger.warning(
            'Auto-devis: marque de dédup non relâchée pour le lead %s — un '
            'prochain essai sera refusé.', lead_id, exc_info=True)


def corps_note_refus_auto_devis(exc):
    """Le CORPS de la note d'abstention — pur, testable sans base.

    Il NOMME le motif : le champ que le moteur a trouvé manquant, et le
    message français qu'il oppose déjà au commercial sur l'écran de devis.
    C'est délibérément le MÊME texte des deux côtés : un lead refusé et un
    devis refusé le sont pour la même raison, et la lire deux fois formulée
    autrement ferait croire à deux problèmes.

    Le corps est DÉTERMINISTE (aucune date, aucun compteur) — c'est ce qui
    permet à la garde anti-répétition de reconnaître le même motif d'un rejeu
    à l'autre.
    """
    champ = getattr(exc, 'field', None) or 'donnée manquante'
    message = (str(exc) or '').strip()
    corps = ('Devis automatique NON créé depuis le tunnel — le '
             'dimensionnement s\'abstient (%s).' % champ)
    if message:
        corps += ' Motif : %s' % message
    corps += (' Complétez la fiche puis créez le devis à la main : rien n\'a '
              'été écrit sur ce lead.')
    return corps


def _noter_refus_auto_devis(company, lead_id, lead, exc):
    """Pose la note d'abstention. BEST-EFFORT : ne remonte jamais.

    Un chemin d'observabilité n'a pas le droit de transformer une abstention
    (cas normal) en erreur : l'appelant rend ``None`` dans les deux cas.
    """
    try:
        from apps.crm.services import ajouter_note_lead_si_nouvelle
        ajouter_note_lead_si_nouvelle(
            company=company, lead_id=lead_id,
            user=getattr(lead, 'owner', None),
            body=corps_note_refus_auto_devis(exc))
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'Auto-devis: note d\'abstention non posée sur le lead %s.',
            lead_id, exc_info=True)


def creer_devis_automatique_depuis_lead(*, lead_id, company_id):
    """AUTO-PIPELINE — le devis brouillon d'un lead arrivé du tunnel.

    Rend le ``Devis`` créé, ou ``None`` — et ``None`` n'est JAMAIS une erreur :
    c'est le cas normal quand le lead n'a pas de quoi être chiffré. LES PORTES,
    dans l'ordre, et aucune n'est nouvelle :

    1. **Société / lead lisibles** — lecture cross-app par
       ``crm.selectors.get_company_lead`` (jamais ``crm.models``).
    2. **Réglage de société** — ``auto_devis_tunnel_actif``.
    3. **IDEMPOTENCE — un lead, un devis**, en DEUX gardes distinctes, car
       elles n'attrapent pas la même chose :

       a. une lecture « ce lead porte-t-il déjà un devis ? » — elle couvre le
          cas courant (webhook re-livré plus tard, tâche rejouée après coup,
          devis déjà saisi à la main par un commercial) ;
       b. une MARQUE D'ACHÈVEMENT en base
          (``core.idempotency.dedupe_event``, contrainte d'unicité sur
          ``(company, source, event_id)``) — elle seule départage deux
          exécutions SIMULTANÉES, que la lecture (a) laisserait passer
          ensemble. Il n'y a ici NI transaction englobante, NI
          ``select_for_update`` : c'est la contrainte d'unicité qui arbitre,
          et le perdant de l'insertion abandonne sans rien créer.

       La marque n'est gardée QUE si un devis a réellement été créé : tout
       échec la relâche (voir ``_liberer_marque_auto_devis``), sans quoi un
       lead non chiffrable aujourd'hui — facture manquante, catalogue
       incomplet — resterait définitivement fermé à un appel ultérieur.
    4. **Assez de donnée RÉELLE** — c'est ``build_devis_auto`` qui tranche,
       avec EXACTEMENT les portes qu'il oppose déjà au commercial
       (``AutoDevisError`` : marché non résidentiel, aucune facture d'hiver ni
       taille souhaitée, marque épinglée absente du stock). Un lead incomplet
       ou parasite ne reçoit donc rien du tout, et surtout pas un devis vide.

    Le tracé du client, s'il existe, entre dans le layout du devis
    (``zone_toit_depuis_contour``) et borne physiquement la taille
    (``plafond_physique_du_contour``). Sans tracé : un devis automatique
    ordinaire, sans calepinage — le comportement d'aujourd'hui.
    """
    from django.db import transaction

    from apps.crm.selectors import get_company_lead
    from authentication.models import Company
    from core.idempotency import dedupe_event

    from .models import Devis

    company = Company.objects.filter(pk=company_id).first()
    if company is None:
        return None
    if not auto_devis_tunnel_actif(company):
        logger.info(
            'Auto-devis: désactivé pour la société %s — lead %s non chiffré.',
            company_id, lead_id)
        return None

    lead = get_company_lead(company, lead_id)
    if lead is None:
        return None

    # PORTE 3a — un lead qui porte déjà un devis (automatique OU saisi à la
    # main) n'en reçoit jamais un second.
    if Devis.objects.filter(company=company, lead=lead).exists():
        logger.info(
            'Auto-devis: le lead %s porte déjà un devis — rien créé.', lead_id)
        return None

    # PORTE 3b — LA COURSE. Deux livraisons simultanées du même webhook, ou un
    # rejeu Celery concurrent (``acks_late``), peuvent franchir la porte 3a
    # ensemble : seule une contrainte d'unicité en base les départage. C'est
    # EXACTEMENT la primitive que le webhook utilise déjà pour ses propres
    # rejeux (``core.idempotency.dedupe_event``) — on ne s'en réinvente pas une
    # seconde. Perdant = on ne crée rien, en silence : l'autre worker s'en
    # charge.
    if not dedupe_event(company=company, source=_MARQUE_AUTO_DEVIS,
                        event_id=str(lead_id)):
        logger.info(
            'Auto-devis: création déjà en cours/faite pour le lead %s '
            '(dédup) — rien créé.', lead_id)
        return None

    journal_auto = {}
    # Le ``try`` couvre TOUT ce qui suit la pose de la marque — y compris les
    # lectures catalogue/géométrie — et il ENVELOPPE la transaction (et non
    # l'inverse) : un refus de dimensionnement doit défaire ce que la
    # construction aurait pu commencer, jamais laisser un devis à moitié écrit.
    # F5 — chaque sortie en échec RELÂCHE la marque : elle atteste d'un devis
    # CRÉÉ, jamais d'une tentative.
    try:
        # Lectures pures (catalogue + géométrie du tracé) — hors transaction.
        produit_panneau, _societe = _panneau_pour_calepinage(
            {'panelWatt': _AUTO_PANEL_WATT}, company=company, devis=None)
        plafond = plafond_physique_du_contour(
            contour_client_lnglat(lead), produit_panneau)
        with transaction.atomic():
            devis = build_devis_auto(
                lead=lead,
                # Le devis est attribué au commercial qui possède le lead
                # quand il y en a un, à personne sinon — jamais à un
                # utilisateur inventé pour la circonstance.
                user=getattr(lead, 'owner', None),
                company=company, plafond_toit=plafond,
                journal_auto=journal_auto)
    except AutoDevisError as exc:
        _liberer_marque_auto_devis(company, lead_id)
        logger.info(
            'Auto-devis: lead %s non chiffrable (%s) — aucun devis créé.',
            lead_id, exc.field or 'donnée manquante')
        # ── F6 (revue Fable, 29/08/2026) — UN REFUS SE VOIT SUR LE LEAD ──
        #
        # Le refus ne laissait qu'une ligne de journal serveur. Côté
        # commercial, le lead arrivait NU, sans devis et sans un mot — alors
        # que la veille les mêmes leads en recevaient un. Le silence se lisait
        # comme une panne ; c'est une ABSTENTION, et elle a un motif nommable.
        #
        # UNE FOIS PAR MOTIF, JAMAIS PAR REJEU : le refus relâche la marque de
        # dédup (une donnée manquante aujourd'hui ne ferme pas le lead pour
        # toujours), si bien qu'une re-livraison du webhook rejoue le même
        # refus. ``ajouter_note_lead_si_nouvelle`` (apps.crm.services — la
        # frontière cross-app, jamais ``crm.models``) ne repose pas un corps
        # identique ; un motif DIFFÉRENT, lui, mérite bien sa note.
        _noter_refus_auto_devis(company, lead_id, lead, exc)
        return None
    except Exception:  # noqa: BLE001 — relâcher AVANT de laisser remonter
        _liberer_marque_auto_devis(company, lead_id)
        raise

    # ── LA BOUCLE DE VÉRIFICATION DU COMMERCIAL ───────────────────────────
    # Le devis porte le lead : il apparaît donc DÉJÀ dans la liste des devis et
    # sur la fiche du lead. Ce qui manquait, c'est le REÇU daté qui dit d'où il
    # sort et qu'il attend une relecture. Note d'historique (chatter existant,
    # aucun mécanisme neuf), best-effort : un devis créé ne doit jamais être
    # remis en cause par une note qui échoue.
    corps = (
        'Devis automatique créé depuis le tunnel — à vérifier : %s.'
        % devis.reference)
    if journal_auto.get('contour_client'):
        corps += (
            ' Le calepinage part du tracé du client (%d points) : ouvrez '
            '« Concevoir la toiture (3D) » pour le contrôler.'
            % journal_auto['contour_client'])
    if journal_auto.get('plafond_applique'):
        corps += (
            ' Taille ramenée de %d à %d panneaux : la surface du tracé du '
            'client ne peut physiquement pas en porter davantage.'
            % (journal_auto['panneaux_avant_plafond'],
               journal_auto['plafond_applique']))
    try:
        from apps.crm.services import ajouter_note_lead
        ajouter_note_lead(company=company, lead_id=lead_id,
                          user=getattr(lead, 'owner', None), body=corps)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'Auto-devis %s: note d\'historique échouée sur le lead %s.',
            devis.reference, lead_id, exc_info=True)

    logger.info('Auto-devis %s créé automatiquement pour le lead %s '
                '(company %s).', devis.reference, lead_id, company_id)
    return devis


def planifier_devis_automatique_pour_lead(lead_id, company_id):
    """Met la création du devis automatique EN FILE — jamais en ligne.

    Point d'entrée cross-app : ``apps.crm`` appelle CETTE fonction (règle
    services.py), et rien d'autre de ``ventes``.

    Contrairement à ``planifier_resynchronisation_produit`` (PVSYNC), il n'y a
    ici **aucun repli en ligne**, et c'est délibéré : le webhook du site est
    une surface PUBLIQUE dont le temps de réponse est un engagement, alors que
    la composition + l'étude horaire se comptent en secondes. Un courtier
    injoignable fait donc simplement retomber ce lead-là sur le chemin
    d'aujourd'hui — le commercial crée son devis à la main — ce qui est un
    dégradé acceptable ; un webhook qui met cinq secondes à répondre ne l'est
    pas. L'échec est journalisé, jamais avalé en silence.
    """
    from .tasks import task_devis_automatique_depuis_lead

    try:
        task_devis_automatique_depuis_lead.apply_async(
            args=[lead_id, company_id], retry=False)
    except Exception as exc:  # noqa: BLE001 — courtier indisponible
        logger.warning(
            'Auto-devis: file Celery indisponible (%s) — le lead %s n\'aura '
            'pas de devis automatique (création manuelle inchangée).',
            exc, lead_id)


def log_supplier_email(
        *, company, to_email, sujet, corps, attachment=None,
        attachment_name=None, reference='', user=None):
    """QS3 — Envoie un email FOURNISSEUR (PDF joint) et le consigne dans EmailLog.

    Point d'entrée cross-app pour ``stock`` (qui n'importe pas ``ventes.models``
    ni ``ventes.email_service``). Le fil EmailLog n'a pas de FK fournisseur : on
    consigne company + destinataire + référence (client/devis/facture restent
    nuls). NO-OP réseau sans clé configurée (backend console) — l'entrée est tout
    de même écrite. Renvoie ``(ok, log)``."""
    from apps.ventes.models import EmailLog
    from apps.ventes.email_service import _send, _from_email
    dest = (to_email or '').strip()
    log = EmailLog(
        company=company,
        direction=EmailLog.Direction.SORTANT,
        to_email=dest[:254], from_email=_from_email(),
        sujet=(sujet or '')[:300], corps=corps or '',
        reference=(reference or '')[:80],
        piece_jointe=(attachment_name or '')[:255],
        created_by=user if getattr(user, 'is_authenticated', False) else None,
    )
    if not dest:
        log.statut = EmailLog.Statut.ECHEC
        log.erreur = 'Aucune adresse email destinataire.'
        log.save()
        return False, log
    ok, err = _send(dest, sujet, corps, attachment, attachment_name)
    log.statut = EmailLog.Statut.ENVOYE if ok else EmailLog.Statut.ECHEC
    log.erreur = err
    log.save()
    return ok, log


# ════════════════════════════════════════════════════════════════════════════
# QJR48 (29/08/2026) — ``refresh_etude_consistency`` A ÉTÉ SUPPRIMÉE
# ════════════════════════════════════════════════════════════════════════════
# Elle écrivait ``etude_params['payback_annees']`` (TTC canonique ÷ économies
# annuelles stockées) à CHAQUE sauvegarde et à CHAQUE suppression de
# ``LigneDevis``, plus à chaque changement de remise globale — soit un
# ``Devis.save()`` par ligne PLUS une recomputation complète d'``option_totaux``.
#
# CETTE CLÉ N'AVAIT AUCUN LECTEUR. Le balayage du dépôt (joint au commit, et
# rejoué par ``tests/test_qjr_coherence_etude.py`` pour qu'il ne puisse pas
# repartir en silence) ne trouve ``payback_annees`` QUE dans des blocs qui
# portent leur PROPRE payback et le calculent eux-mêmes : les cartes
# ``offres_tailles``, les paliers de ``dimensionnement``, les comparateurs
# ``compta``/``parametres``. Le PDF et la page publique lisent, eux, la clé
# ``payback`` (industriel/commercial), recalculée par ``quote_engine/builder``
# — jamais ``payback_annees``.
#
# Les deux récepteurs QX24 (``apps/ventes/receivers.py``) ont été retirés dans
# le même commit : aucun chemin ne subsiste. Aucun chiffre rendu au client ne
# change.


def compute_marge_snapshot(devis):
    """QX23be — marge HT interne figée d'un devis (usage MANAGER UNIQUEMENT).

    marge = Σ(HT ligne, option acceptée si applicable) − Σ(qté × prix_achat).
    Renvoie un Decimal, ou None si AUCUN produit lié ne porte de prix_achat
    exploitable (on ne veut pas figer une fausse marge = 100 % du CA). Best-
    effort : jamais d'exception remontée.

    RÈGLE #4 : ``prix_achat`` ne quitte JAMAIS cette fonction interne — le
    résultat (une marge) n'est exposé qu'au responsable dans la vue liste,
    jamais dans un PDF/une sortie client.
    """
    from decimal import Decimal
    try:
        from apps.ventes.utils.options import option_lines
        lignes = option_lines(devis)
    except Exception:  # noqa: BLE001
        try:
            lignes = list(devis.lignes.select_related('produit').all())
        except Exception:  # noqa: BLE001
            return None
    ht = Decimal('0')
    cout = Decimal('0')
    a_un_cout = False
    for li in lignes:
        try:
            ht += Decimal(str(li.total_ht))
        except Exception:  # noqa: BLE001
            continue
        produit = getattr(li, 'produit', None)
        prix_achat = getattr(produit, 'prix_achat', None) if produit else None
        if prix_achat is not None and Decimal(str(prix_achat)) > 0:
            a_un_cout = True
            cout += Decimal(str(li.quantite)) * Decimal(str(prix_achat))
    if not a_un_cout:
        return None
    return (ht - cout).quantize(Decimal('0.01'))


def refresh_marge_snapshot(devis):
    """QX23be — recalcule et persiste ``marge_snapshot`` (best-effort)."""
    try:
        marge = compute_marge_snapshot(devis)
        if devis.marge_snapshot != marge:
            devis.marge_snapshot = marge
            devis.save(update_fields=['marge_snapshot'])
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        logger.warning('QX23: marge_snapshot échoué pour devis %s : %s',
                       getattr(devis, 'reference', '?'), exc)


def verifier_devis_envoyable(devis):
    """NTCPQ7 — lève ``ValidationError`` si une étape d'approbation de remise
    est encore ``en_attente`` (blocage envoi/génération PDF).

    Lecture cross-app cpq via import LOCAL (aucun cycle au niveau module).
    Aucune étape en attente ⇒ ne lève rien (comportement inchangé)."""
    from rest_framework.exceptions import ValidationError
    from apps.cpq.selectors import premiere_etape_en_attente
    etape = premiere_etape_en_attente(devis)
    if etape is not None:
        raise ValidationError({'statut': (
            f"Approbation de remise en attente (étape {etape.niveau}) : "
            "l'envoi est bloqué tant qu'elle n'est pas approuvée.")})


# ── QJ16 — Reusable quote presets ────────────────────────────────────────────

def save_devis_as_preset(devis, nom: str, description: str = "", *, user=None):
    """QJ16 — snapshot a Devis into a company-scoped DevisPreset.

    The preset captures the line configuration (designation, quantite,
    prix_unitaire, remise, taux_tva per line, plus taux_tva and remise_globale
    at devis level) as a JSON snapshot.  The company is ALWAYS forced from
    ``devis.company`` — never from user input.

    Price-less lines are excluded at save time (same guard as auto-fill): if a
    line's produit has no sell price, it is still captured in the snapshot so the
    preset is complete, but at apply-time such lines are re-checked and skipped
    if the product is no longer priced.

    Returns the created DevisPreset.
    """
    from apps.ventes.models import DevisPreset

    company = devis.company
    if company is None:
        raise ValueError("save_devis_as_preset: devis has no company")

    def _ds(value):
        # Normalise a Decimal to a clean string (strip trailing zeros):
        # 10.00 -> "10", 10.50 -> "10.5". None stays None.
        if value is None:
            return None
        s = str(value)
        return s.rstrip('0').rstrip('.') if '.' in s else s

    lignes_snapshot = []
    for ligne in devis.lignes.select_related('produit').order_by('id'):
        produit = ligne.produit
        lignes_snapshot.append({
            'produit_id': produit.pk if produit else None,
            'designation': ligne.designation,
            'quantite': _ds(ligne.quantite),
            'prix_unitaire': _ds(ligne.prix_unitaire),
            'remise': _ds(ligne.remise),
            'taux_tva': _ds(ligne.taux_tva),
        })

    preset = DevisPreset.objects.create(
        company=company,
        nom=nom.strip(),
        description=description,
        mode_installation=devis.mode_installation or None,
        taux_tva=devis.taux_tva,
        remise_globale=devis.remise_globale,
        lignes_snapshot=lignes_snapshot,
        etude_params_snapshot=dict(devis.etude_params) if devis.etude_params else None,
        created_by=user,
    )
    logger.info(
        'QJ16: preset "%s" saved (id=%s, company=%s, %d lignes)',
        preset.nom, preset.pk, company.pk, len(lignes_snapshot))
    return preset


def apply_preset_to_devis(preset, devis, *, skip_priceless: bool = True) -> list:
    """QJ16 — apply a DevisPreset to an existing (empty) Devis.

    Creates LigneDevis rows on ``devis`` from the preset snapshot.  The caller
    is responsible for ensuring ``devis`` is brouillon and belongs to the same
    company as the preset (enforced below — cross-company apply is refused).

    ``skip_priceless=True`` (default): lines whose snapshot product no longer
    has a sell price are skipped (same guard as auto-fill — never auto-quote a
    price-less product).  Pass ``skip_priceless=False`` only in tests that need
    to exercise the skipping logic.

    Returns the list of created LigneDevis instances (may be empty if all lines
    are priceless).

    RULE #4: this service only builds lines — it never changes Devis.statut.
    """
    from apps.ventes.models import LigneDevis
    from apps.stock.models import Produit

    if preset.company_id != devis.company_id:
        raise ValueError(
            "apply_preset_to_devis: preset and devis belong to different companies"
        )

    created = []
    for snap in preset.lignes_snapshot:
        produit_id = snap.get('produit_id')
        produit = None
        if produit_id:
            try:
                produit = Produit.objects.get(
                    pk=produit_id, company=devis.company)
            except Produit.DoesNotExist:
                # Product deleted or belongs to another company — try global
                try:
                    produit = Produit.objects.get(
                        pk=produit_id, company__isnull=True)
                except Produit.DoesNotExist:
                    produit = None

        if skip_priceless and produit is not None and not _has_price(produit):
            logger.info(
                'QJ16 apply_preset: skipping priceless product %s ("%s")',
                produit_id, snap.get('designation', ''))
            continue

        taux_snap = snap.get('taux_tva')
        ligne = LigneDevis.objects.create(
            devis=devis,
            produit=produit,
            designation=snap['designation'],
            quantite=Decimal(str(snap['quantite'])),
            prix_unitaire=Decimal(str(snap['prix_unitaire'])),
            remise=Decimal(str(snap.get('remise', '0'))),
            taux_tva=Decimal(str(taux_snap)) if taux_snap is not None else None,
        )
        created.append(ligne)

    # Apply devis-level settings from preset if the devis is fresh (no lignes yet
    # before this call means we can safely update tva and remise).
    if created:
        devis.taux_tva = preset.taux_tva
        devis.remise_globale = preset.remise_globale
        if preset.mode_installation:
            devis.mode_installation = preset.mode_installation
        if preset.etude_params_snapshot and not devis.etude_params:
            devis.etude_params = dict(preset.etude_params_snapshot)
        devis.save(update_fields=[
            'taux_tva', 'remise_globale', 'mode_installation', 'etude_params'])

    logger.info(
        'QJ16 apply_preset: applied preset "%s" to devis %s (%d lines)',
        preset.nom, getattr(devis, 'reference', devis.pk), len(created))
    return created


# ── XSAV3 — Devis de réparation hors garantie depuis un ticket SAV ───────────

def create_devis_pour_ticket(*, company, user, client_id, lignes, note=None):
    """XSAV3 — Crée un Devis BROUILLON pour un travail SAV non couvert.

    Point d'entrée cross-app (sav → ventes) : ``apps.sav`` appelle CETTE
    fonction plutôt que d'importer ``apps.ventes.models`` directement (règle
    de modularité CLAUDE.md). ``lignes`` est une liste de dicts
    ``{'produit_id': int, 'designation': str, 'quantite': Decimal,
    'prix_unitaire': Decimal}`` — le prix unitaire attendu ici est TOUJOURS le
    prix de VENTE catalogue (``Produit.prix_vente``), jamais ``prix_achat``.

    Référence générée via ``apps.ventes.utils.references`` (jamais count()+1).
    Renvoie le ``Devis`` créé (brouillon, sans lien lead — un ticket SAV n'a
    pas de lead d'origine).
    """
    from .models import Devis, LigneDevis
    from .utils.references import create_with_reference
    from apps.crm.models import Client

    client = Client.objects.get(pk=client_id, company=company)

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client,
            statut=Devis.Statut.BROUILLON, created_by=user,
            note=note or '',
        )
    devis = create_with_reference(Devis, 'DEV', company, _create)

    for ligne in (lignes or []):
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        LigneDevis.objects.create(
            devis=devis,
            produit_id=produit_id,
            designation=ligne.get('designation') or '',
            quantite=Decimal(str(ligne.get('quantite') or 1)),
            prix_unitaire=Decimal(str(ligne.get('prix_unitaire') or 0)),
        )
    return devis


# ── ZFSM5 — Devis d'upsell créé sur place depuis l'intervention ────────────
# apps.installations ne peut PAS importer apps.ventes.models directement
# (règle de modularité CLAUDE.md) : cette fonction est son unique porte
# d'entrée pour générer un devis brouillon d'upsell depuis une intervention
# (opportunité vue sur place — 2ᵉ site, batterie, extension) — DISTINCT de
# XFSM18 (réserve → devis de RÉPARATION, reprise d'un défaut).

def create_devis_upsell_from_intervention(*, intervention, user):
    """ZFSM5 — crée un DEVIS brouillon d'upsell à partir d'une intervention,
    pour le cas où le technicien voit une opportunité sur place. Le client
    est celui du CHANTIER (`intervention.installation.client`, déjà résolu —
    pattern `create_devis_from_reserve`, aucune re-résolution lead
    nécessaire). La description est pré-remplie depuis le chantier/type
    d'intervention ; aucune ligne n'est créée (une LigneDevis exige un
    Produit du catalogue) — le devis brouillon est laissé à compléter dans
    l'éditeur.

    Le devis reste ``brouillon`` : ce service CRÉE, il ne change aucun statut
    aval (règle #4). Aucun impact sur `/proposal`.

    IDEMPOTENT : si ``intervention.devis_upsell_id`` pointe déjà vers un
    devis existant, le renvoie tel quel plutôt que d'en créer un second.
    Renvoie le ``Devis`` créé (ou réutilisé)."""
    from .models import Devis
    from .utils.references import create_with_reference

    if intervention.devis_upsell_id:
        existant = Devis.objects.filter(
            pk=intervention.devis_upsell_id, company=intervention.company
        ).first()
        if existant is not None:
            return existant

    installation = intervention.installation
    if installation is None or installation.client_id is None:
        raise ValueError(
            "create_devis_upsell_from_intervention requires an intervention "
            "attached to a chantier with a resolved client")
    client = installation.client
    company = intervention.company or installation.company

    note = (
        "Devis d'upsell généré depuis une intervention sur place.\n"
        f"Chantier : {installation.reference}\n"
        f"Type d'intervention : {intervention.get_type_intervention_display()}")

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
        )

    devis = create_with_reference(Devis, 'DEV', company, _create)
    intervention.devis_upsell_id = devis.id
    intervention.save(update_fields=['devis_upsell_id'])
    logger.info(
        'ZFSM5: devis upsell %s créé depuis intervention %s (company %s)',
        devis.reference, intervention.id, getattr(company, 'id', '?'))
    return devis


def _round2(x):
    """Arrondi MAD à 2 décimales, HALF_UP (comme le reste du module)."""
    return Decimal(x).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _regle_applicable(regles, produit, quantite):
    """XSAL2 — la règle la plus spécifique dont le palier est atteint.

    Ordre : spécificité de portée (produit > catégorie > marque > catalogue)
    d'abord, puis priorité explicite, puis palier le plus élevé atteint par
    `quantite`. Une règle inactive ou dont le palier n'est pas atteint est
    ignorée."""
    candidates = [
        r for r in regles
        if r.actif and r.matches_produit(produit) and quantite >= r.quantite_min
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda r: (r.specificite, r.priorite, r.quantite_min), reverse=True)
    return candidates[0]


def _appliquer_regle(regle, prix_base):
    """XSAL2 — applique une règle résolue au prix de base (jamais à
    `prix_achat`)."""
    if regle.type_regle == regle.TypeRegle.PRIX_FIXE:
        return _round2(regle.valeur)
    if regle.type_regle == regle.TypeRegle.REMISE_PCT:
        return _round2(prix_base * (1 - regle.valeur / 100))
    if regle.type_regle == regle.TypeRegle.FORMULE_SUR_PRIX_VENTE:
        return _round2(prix_base * regle.valeur)
    return _round2(prix_base)  # pragma: no cover - défensif, type inconnu


def _prix_contractuel(client, produit):
    """NTCPQ5 — Prix contractuel actif pour un couple client/produit.

    Lecture cross-app cpq via import LOCAL (aucun import de cpq.models au niveau
    module ; évite tout cycle ventes↔cpq). Renvoie l'instance ``PrixContractuel``
    active la plus récente, ou ``None``."""
    if client is None or produit is None:
        return None
    company_id = getattr(client, 'company_id', None)
    if company_id is None:
        return None
    from apps.cpq.models import PrixContractuel
    candidates = PrixContractuel.objects.filter(
        company_id=company_id, client_id=client.id, produit_id=produit.id,
    ).order_by('-date_creation')
    for candidate in candidates:
        if candidate.est_actif:
            return candidate
    return None


def _resolve_liste_prix(client):
    """NTCPQ4 — Sélectionne la liste de prix applicable à un client.

    Priorité : liste explicitement assignée au client (``client.liste_prix``)
    si elle est active > liste de la société correspondant au SEGMENT du client
    (la plus récente active) > aucune. Les listes hors fenêtre de validité ou
    archivées (``est_active`` False) ne sont JAMAIS retenues, même si leur
    segment correspond au client (NTCPQ4). Renvoie une ``ListePrix`` active ou
    ``None``."""
    if client is None:
        return None
    liste = getattr(client, 'liste_prix', None)
    if liste is not None and liste.est_active:
        return liste
    # Segment du client : champ dédié s'il existe, sinon type de client.
    segment = (getattr(client, 'segment_client', '')
               or getattr(client, 'type_client', '') or '')
    company_id = getattr(client, 'company_id', None)
    if segment and company_id is not None:
        from apps.ventes.models import ListePrix
        candidates = ListePrix.objects.filter(
            company_id=company_id, segment_client=segment, archived=False,
        ).order_by('-created_at')
        for candidate in candidates:
            if candidate.est_active:
                return candidate
    return None


def prix_applicable(*, produit, client=None, quantite=1):
    """XSAL1/XSAL2 — Prix unitaire résolu pour un produit/client/quantité.

    Ordre de résolution :
      1. `client.liste_prix` (si assignée et active) → règles de paliers/
         portée (XSAL2, la plus spécifique satisfaite par `quantite`) →
         sinon le prix de ligne fixe (`LignePrixListe`) → sinon
         `produit.prix_vente`.
      2. Sans liste (client=None, `liste_prix` vide, ou liste inactive) →
         `produit.prix_vente` (comportement historique, octet-identique).

    Ne renvoie et ne consulte JAMAIS `produit.prix_achat`. Renvoie un dict
    `{"prix": Decimal, "source": "liste"|"regle"|"standard",
    "liste_nom": str|None}` pour que l'appelant (endpoint XSAL3) puisse
    afficher le badge « Tarif : <nom de la liste> »."""
    quantite = Decimal(str(quantite or 1))
    prix_standard = produit.prix_vente

    # NTCPQ5 — priorité 1 : prix contractuel négocié (client + produit). Écrase
    # toute liste de prix générique (segment/assignée) pour ce couple.
    contractuel = _prix_contractuel(client, produit)
    if contractuel is not None:
        return {
            'prix': contractuel.prix_ht,
            'source': 'contractuel',
            'liste_nom': contractuel.motif or None,
        }

    liste = _resolve_liste_prix(client)
    if liste is None:
        return {'prix': prix_standard, 'source': 'standard', 'liste_nom': None}

    regles = list(liste.regles.filter(actif=True).select_related('produit'))
    regle = _regle_applicable(regles, produit, quantite)
    if regle is not None:
        prix_ligne = liste.lignes.filter(produit=produit).values_list(
            'prix_unitaire', flat=True).first()
        base = prix_ligne if prix_ligne is not None else prix_standard
        return {
            'prix': _appliquer_regle(regle, base),
            'source': 'regle',
            'liste_nom': liste.nom,
        }

    ligne = liste.lignes.filter(produit=produit).first()
    if ligne is not None:
        return {'prix': ligne.prix_unitaire, 'source': 'liste', 'liste_nom': liste.nom}

    return {'prix': prix_standard, 'source': 'standard', 'liste_nom': None}


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR68 : bordereau / BOQ → ``domain/bordereau.py``
# ═══════════════════════════════════════════════════════════════════════════
# Chaque nom est ré-exporté par une AFFECTATION de niveau module (et non par
# ``from … import …``) : c'est la forme que le pin de surface
# ``tests/test_services_surface.py`` reconnaît comme une définition (il lit
# ``services.py`` par AST, où un import n'est pas une définition). La liste
# dorée du pin reste donc EXACTE sans être retouchée.
from apps.ventes.domain import bordereau as _bordereau  # noqa: E402
BOQ_CATEGORIES = _bordereau.BOQ_CATEGORIES
_BOQ_FAMILLES = _bordereau._BOQ_FAMILLES
_BOQ_FAMILLES_CABLE = _bordereau._BOQ_FAMILLES_CABLE
_BOQ_FAMILLES_CALIBREES = _bordereau._BOQ_FAMILLES_CALIBREES
BOQ_SUFFIXE_A_CHIFFRER = _bordereau.BOQ_SUFFIXE_A_CHIFFRER
_BOQ_NOMBRE_RE = _bordereau._BOQ_NOMBRE_RE
_boq_normaliser = _bordereau._boq_normaliser
_boq_famille = _bordereau._boq_famille
_boq_polarite = _bordereau._boq_polarite
_boq_nombres = _bordereau._boq_nombres
_boq_courant = _bordereau._boq_courant
_boq_section = _bordereau._boq_section
_boq_courant_alternatif = _bordereau._boq_courant_alternatif
_boq_candidats = _bordereau._boq_candidats
_boq_apparier = _bordereau._boq_apparier
_boq_prix = _bordereau._boq_prix
ajouter_lignes_boq_electrique = _bordereau.ajouter_lignes_boq_electrique
_QUANTUM_QUANTITE = _bordereau._QUANTUM_QUANTITE
_PU_DEVIS_MAX = _bordereau._PU_DEVIS_MAX
_QUANTITE_DEVIS_MAX = _bordereau._QUANTITE_DEVIS_MAX
_designation_ligne_bordereau = _bordereau._designation_ligne_bordereau
_signature_lignes_devis = _bordereau._signature_lignes_devis
_signature_specs_bordereau = _bordereau._signature_specs_bordereau
_reouvrir_devis_depuis_bordereau = _bordereau._reouvrir_devis_depuis_bordereau
creer_devis_depuis_bordereau = _bordereau.creer_devis_depuis_bordereau
resume_devis_depuis_bordereau = _bordereau.resume_devis_depuis_bordereau


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR69 (1/3) : recouvrement → ``domain/recouvrement.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import recouvrement as _recouvrement  # noqa: E402
RELANCE_AUTO_NOTE = _recouvrement.RELANCE_AUTO_NOTE
RELANCE_AUTO_NOTE_RESOLUE = _recouvrement.RELANCE_AUTO_NOTE_RESOLUE
reset_relance_escalation = _recouvrement.reset_relance_escalation
PaiementRejectError = _recouvrement.PaiementRejectError
rejeter_paiement = _recouvrement.rejeter_paiement
abandonner_solde_facture = _recouvrement.abandonner_solde_facture
anomalies_emission_facture = _recouvrement.anomalies_emission_facture
CreditHoldError = _recouvrement.CreditHoldError
verifier_credit_hold = _recouvrement.verifier_credit_hold
SaleWarningError = _recouvrement.SaleWarningError
verifier_sale_warnings = _recouvrement.verifier_sale_warnings
_s2 = _recouvrement._s2
dossier_contentieux_data = _recouvrement.dossier_contentieux_data
ouvrir_dossier_contentieux = _recouvrement.ouvrir_dossier_contentieux
enregistrer_contestation_portail = _recouvrement.enregistrer_contestation_portail
_NUDGE_MSG_FR = _recouvrement._NUDGE_MSG_FR
_NUDGE_MSG_AR = _recouvrement._NUDGE_MSG_AR
_build_wa_draft_url = _recouvrement._build_wa_draft_url
_get_nudge_days = _recouvrement._get_nudge_days
_nudge_suppressed = _recouvrement._nudge_suppressed
_journaliser_relance_marketing = _recouvrement._journaliser_relance_marketing
send_devis_followup_nudges = _recouvrement.send_devis_followup_nudges
_send_nudge_email = _recouvrement._send_nudge_email
expire_stale_devis = _recouvrement.expire_stale_devis
_COLD_AFTER_FOLLOWUP_DAYS = _recouvrement._COLD_AFTER_FOLLOWUP_DAYS
_advance_lead_on_expiry = _recouvrement._advance_lead_on_expiry


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR69 (2/3) : encaissements → ``domain/encaissements.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import encaissements as _encaissements  # noqa: E402
enregistrer_paiement = _encaissements.enregistrer_paiement
facture_montant_du = _encaissements.facture_montant_du
affecter_encaissement_groupe = _encaissements.affecter_encaissement_groupe
_creer_paiement_groupe = _encaissements._creer_paiement_groupe
create_payment_link = _encaissements.create_payment_link
_public_url = _encaissements._public_url
qr_svg_for_facture_pdf = _encaissements.qr_svg_for_facture_pdf
record_payment_from_link = _encaissements.record_payment_from_link
enregistrer_avance = _encaissements.enregistrer_avance
ventiler_avance = _encaissements.ventiler_avance
enregistrer_paiement_avec_retenue = _encaissements.enregistrer_paiement_avec_retenue
consolider_factures = _encaissements.consolider_factures
mandat_actif_pour_client = _encaissements.mandat_actif_pour_client
DUNNING_RETRY_DAYS = _encaissements.DUNNING_RETRY_DAYS
debiter_mandat_pour_facture = _encaissements.debiter_mandat_pour_facture


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR69 (3/3) : facturation → ``domain/facturation_ops.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import facturation_ops as _facturation_ops  # noqa: E402
StockInsuffisantError = _facturation_ops.StockInsuffisantError
reserver_stock_devis_facture = _facturation_ops.reserver_stock_devis_facture
creer_facture_contrat = _facturation_ops.creer_facture_contrat
creer_facture_regie = _facturation_ops.creer_facture_regie
creer_facture_acompte_situation = _facturation_ops.creer_facture_acompte_situation
creer_facture_classique = _facturation_ops.creer_facture_classique
_PRODUIT_FRAIS_REFACTURES_NOM = _facturation_ops._PRODUIT_FRAIS_REFACTURES_NOM
_produit_frais_refactures = _facturation_ops._produit_frais_refactures
ajouter_lignes_frais_refactures = _facturation_ops.ajouter_lignes_frais_refactures
_recalculer_totaux_facture = _facturation_ops._recalculer_totaux_facture
calculer_date_echeance = _facturation_ops.calculer_date_echeance
get_facture_or_none = _facturation_ops.get_facture_or_none
facturables_pour_devis = _facturation_ops.facturables_pour_devis
_main_oeuvre_produit = _facturation_ops._main_oeuvre_produit
generer_facture_ticket_sav = _facturation_ops.generer_facture_ticket_sav
generer_facture_intervention = _facturation_ops.generer_facture_intervention


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR70 : cycle de vie du devis → ``domain/cycle_vie.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import cycle_vie as _cycle_vie  # noqa: E402
AcceptError = _cycle_vie.AcceptError
activate_optional_line = _cycle_vie.activate_optional_line
OTP_CACHE_TTL = _cycle_vie.OTP_CACHE_TTL
_esign_otp_enabled = _cycle_vie._esign_otp_enabled
_otp_cache_key = _cycle_vie._otp_cache_key
_generate_otp = _cycle_vie._generate_otp
request_esign_otp = _cycle_vie.request_esign_otp
OTP_MAX_ATTEMPTS = _cycle_vie.OTP_MAX_ATTEMPTS
_otp_attempts_key = _cycle_vie._otp_attempts_key
validate_esign_otp = _cycle_vie.validate_esign_otp
OTP_LECTURE_VERIFIED_TTL = _cycle_vie.OTP_LECTURE_VERIFIED_TTL
_otp_lecture_cache_key = _cycle_vie._otp_lecture_cache_key
_otp_lecture_attempts_key = _cycle_vie._otp_lecture_attempts_key
_otp_lecture_verified_key = _cycle_vie._otp_lecture_verified_key
request_otp_lecture = _cycle_vie.request_otp_lecture
validate_otp_lecture = _cycle_vie.validate_otp_lecture
otp_lecture_verified = _cycle_vie.otp_lecture_verified
_send_otp_whatsapp = _cycle_vie._send_otp_whatsapp
_send_otp_email = _cycle_vie._send_otp_email
_create_esign_record = _cycle_vie._create_esign_record
_store_signed_pdf = _cycle_vie._store_signed_pdf
_acceptance_deposit_block = _cycle_vie._acceptance_deposit_block
_send_acceptance_emails = _cycle_vie._send_acceptance_emails
_notify_seller_accepted = _cycle_vie._notify_seller_accepted
_build_acceptance_wa_url = _cycle_vie._build_acceptance_wa_url
_ATTRIBUTION_FIELDS = _cycle_vie._ATTRIBUTION_FIELDS
_persist_attribution = _cycle_vie._persist_attribution
_fire_capi_signed_quote = _cycle_vie._fire_capi_signed_quote
accept_devis = _cycle_vie.accept_devis
share_link_for_bcf = _cycle_vie.share_link_for_bcf
INSTALLATION_SHARE_UTM_CAMPAIGN = _cycle_vie.INSTALLATION_SHARE_UTM_CAMPAIGN
installation_share_link = _cycle_vie.installation_share_link
bcf_share_url = _cycle_vie.bcf_share_url
contexte_clauses_devis = _cycle_vie.contexte_clauses_devis
figer_clauses_devis = _cycle_vie.figer_clauses_devis
configuration_devis_contenu = _cycle_vie.configuration_devis_contenu
capturer_configuration_devis = _cycle_vie.capturer_configuration_devis
diff_configurations_devis = _cycle_vie.diff_configurations_devis
renouveler_devis = _cycle_vie.renouveler_devis
mark_devis_sent = _cycle_vie.mark_devis_sent


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR71 : catalogue → ``domain/catalogue.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import catalogue as _catalogue  # noqa: E402
marque_preferee = _catalogue.marque_preferee
LIBELLES_ROLES = _catalogue.LIBELLES_ROLES
_libelle_role = _catalogue._libelle_role
carte_marques_composition = _catalogue.carte_marques_composition
ordre_lignes_societe = _catalogue.ordre_lignes_societe
_WATT_RE = _catalogue._WATT_RE
_is_panel = _catalogue._is_panel
_is_battery = _catalogue._is_battery
CABLE_DC_M_PAR_PALIER = _catalogue.CABLE_DC_M_PAR_PALIER
CABLE_TERRE_M_BASE = _catalogue.CABLE_TERRE_M_BASE
CABLE_TERRE_M_PAR_PALIER = _catalogue.CABLE_TERRE_M_PAR_PALIER
metre_cable_dc = _catalogue.metre_cable_dc
metre_cable_dc_par_paires = _catalogue.metre_cable_dc_par_paires
metre_cable_terre = _catalogue.metre_cable_terre
_is_cable_terre = _catalogue._is_cable_terre
_is_cable_dc = _catalogue._is_cable_dc
_est_au_metre = _catalogue._est_au_metre
STRUCTURES_PAR_PANNEAU = _catalogue.STRUCTURES_PAR_PANNEAU
SOCLES_PAR_PANNEAU = _catalogue.SOCLES_PAR_PANNEAU
_is_structure = _catalogue._is_structure
_is_socle = _catalogue._is_socle
_is_battery_basse_tension = _catalogue._is_battery_basse_tension
_plage_batterie_de_l_onduleur = _catalogue._plage_batterie_de_l_onduleur
_tension_nominale_batterie = _catalogue._tension_nominale_batterie
_max_modules_par_banc = _catalogue._max_modules_par_banc
_prix_ttc_batterie = _catalogue._prix_ttc_batterie
_batterie_compatible = _catalogue._batterie_compatible
_pick_batterie = _catalogue._pick_batterie
_onduleur_complet = _catalogue._onduleur_complet
_filtrer_onduleurs_complets = _catalogue._filtrer_onduleurs_complets
_is_hybrid_inverter = _catalogue._is_hybrid_inverter
_is_reseau_inverter = _catalogue._is_reseau_inverter
_has_price = _catalogue._has_price
_batterie_en_stock = _catalogue._batterie_en_stock
_marque_correspond = _catalogue._marque_correspond
_pick_product = _catalogue._pick_product
_parse_watt = _catalogue._parse_watt
_au_centime = _catalogue._au_centime
prix_forfait_ht = _catalogue.prix_forfait_ht
_KW_RE = _catalogue._KW_RE
_KWH_RE = _catalogue._KWH_RE
_TRI_RE = _catalogue._TRI_RE
_sans_accents = _catalogue._sans_accents
_arrondi_js = _catalogue._arrondi_js
PANNEAUX_CEIL_EPS = _catalogue.PANNEAUX_CEIL_EPS
plafond_panneaux = _catalogue.plafond_panneaux
_parse_kw = _catalogue._parse_kw
_parse_kwh = _catalogue._parse_kwh
_est_triphase = _catalogue._est_triphase
classer_produit = _catalogue.classer_produit
catalogue_de_la_societe = _catalogue.catalogue_de_la_societe
