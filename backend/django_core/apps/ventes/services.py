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
from decimal import Decimal, ROUND_HALF_UP
import logging

# QJR74 — `namedtuple` (porteur de `LigneKit`) et `math` ont suivi le cœur de
# composition dans `domain/composition.py` : plus AUCUN lecteur ici.
# QJR71 — `re` et `unicodedata` ont suivi les classifieurs et les normalisations
# de libellé dans `domain/catalogue.py` : plus AUCUN lecteur ici.
# QJR69 — `from apps.stock.services import qr_svg_for` a suivi son SEUL lecteur,
# `qr_svg_for_facture_pdf`, dans `domain/encaissements.py` : le garder ici en
# import mort ferait croire qu'un `mock.patch('…services.qr_svg_for')` couvre
# encore ce chemin, alors qu'un patch n'affecte que l'espace de noms qu'il vise.

logger = logging.getLogger(__name__)

# ── LA SEULE EXCEPTION À « LES IMPORTS DE ``domain/`` SONT EN FIN DE FICHIER » ─
# ``composer_devis_residentiel`` (plus bas) porte ``panel_watt=_AUTO_PANEL_WATT``
# comme VALEUR PAR DÉFAUT : une valeur par défaut est évaluée à la définition de
# la fonction, donc AU CHARGEMENT DU MODULE — bien avant le bloc de ré-exports.
# Le nom doit exister ici, pas à la fin. ``domain/taille`` est une FEUILLE (il
# n'importe que ``domain/catalogue``, qui n'importe rien de ``ventes``) : cet
# import amont ne peut donc pas boucler. Le ré-export prend la forme d'une
# AFFECTATION, comme tous les autres, pour rester visible du pin de surface.
from apps.ventes.domain import taille as _taille_amont  # noqa: E402
_AUTO_PANEL_WATT = _taille_amont._AUTO_PANEL_WATT


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


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR72 : géométrie → ``domain/geometrie.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import geometrie as _geometrie  # noqa: E402
_aspect_to_orientation = _geometrie._aspect_to_orientation
_azimut_boussole_vers_aspect = _geometrie._azimut_boussole_vers_aspect
_aspect_vers_azimut_boussole = _geometrie._aspect_vers_azimut_boussole
extract_roof_config = _geometrie.extract_roof_config
layout_hash = _geometrie.layout_hash
validate_composition_for_layout = _geometrie.validate_composition_for_layout
DRAPEAU_MOTEUR_CALEPINAGE = _geometrie.DRAPEAU_MOTEUR_CALEPINAGE
TOLERANCE_ARBITRAGE_MODULES = _geometrie.TOLERANCE_ARBITRAGE_MODULES
TOLERANCE_ARBITRAGE_PCT = _geometrie.TOLERANCE_ARBITRAGE_PCT
_ecart_dans_la_tolerance = _geometrie._ecart_dans_la_tolerance
moteur_calepinage_actif = _geometrie.moteur_calepinage_actif
_zone_villa_depuis_pan = _geometrie._zone_villa_depuis_pan
_produit_panneau_du_devis = _geometrie._produit_panneau_du_devis
_panneau_pour_calepinage = _geometrie._panneau_pour_calepinage
compte_moteur_du_layout = _geometrie.compte_moteur_du_layout
arbitrer_compte_calepinage = _geometrie.arbitrer_compte_calepinage
_cible_panneaux_du_layout = _geometrie._cible_panneaux_du_layout
_watt_du_layout = _geometrie._watt_du_layout
_AUTO_ZONE_ID = _geometrie._AUTO_ZONE_ID
contour_client_lnglat = _geometrie.contour_client_lnglat
aire_contour_m2 = _geometrie.aire_contour_m2
plafond_physique_du_contour = _geometrie.plafond_physique_du_contour
zone_toit_depuis_contour = _geometrie.zone_toit_depuis_contour


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR73 : lignes du devis → ``domain/lignes.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import lignes as _lignes  # noqa: E402
CIBLE_WATT_DEFAUT = _lignes.CIBLE_WATT_DEFAUT
_lignes_produit = _lignes._lignes_produit
_classe_ligne = _lignes._classe_ligne
_pmax_wc_du_produit = _lignes._pmax_wc_du_produit
lignes_de_variante = _lignes.lignes_de_variante
option_avec_servable = _lignes.option_avec_servable
cible_depuis_lignes = _lignes.cible_depuis_lignes


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR74 : composition → ``domain/composition.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import composition as _composition  # noqa: E402
LigneKit = _composition.LigneKit
VARIANTE_COMMUNE = _composition.VARIANTE_COMMUNE
VARIANTE_SANS = _composition.VARIANTE_SANS
VARIANTE_AVEC = _composition.VARIANTE_AVEC
CompositionLignes = _composition.CompositionLignes
ordonner_par_role = _composition.ordonner_par_role
avertissement_vivier_batterie_vide = _composition.avertissement_vivier_batterie_vide
avertissement_batterie_rupture_stock = _composition.avertissement_batterie_rupture_stock
avertissement_batterie_plafond_banc = _composition.avertissement_batterie_plafond_banc
avertissement_batterie_pin_sans_correspondance = _composition.avertissement_batterie_pin_sans_correspondance
_v_txt = _composition._v_txt
avertissement_aucun_onduleur_triphase = _composition.avertissement_aucun_onduleur_triphase
_vivier_onduleurs_par_phase = _composition._vivier_onduleurs_par_phase
_statut_couple_panneau = _composition._statut_couple_panneau
composition_residentielle = _composition.composition_residentielle
_memes_lignes_kit = _composition._memes_lignes_kit
_cle_produit = _composition._cle_produit
fusionner_kits = _composition.fusionner_kits
composition_deux_optimiseurs = _composition.composition_deux_optimiseurs
CLASSES_KIT_COMPLETABLES = _composition.CLASSES_KIT_COMPLETABLES
AVERTISSEMENTS_KIT_ABSENT = _composition.AVERTISSEMENTS_KIT_ABSENT
_classe_kit_de_ligne = _composition._classe_kit_de_ligne
_est_au_prix_catalogue = _composition._est_au_prix_catalogue
_completer_kit_residentiel = _composition._completer_kit_residentiel
_refuser_couple_panneau_onduleur_impossible = _composition._refuser_couple_panneau_onduleur_impossible


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR75 (1/2) : taille → ``domain/taille.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import taille as _taille  # noqa: E402
AutoDevisError = _taille.AutoDevisError
phase_client_pour_dimensionnement = _taille.phase_client_pour_dimensionnement
MOTIF_FACTURE_ABSENTE = _taille.MOTIF_FACTURE_ABSENTE
MOTIF_LOCALISATION = _taille.MOTIF_LOCALISATION
MOTIF_CATALOGUE = _taille.MOTIF_CATALOGUE
MOTIF_MOTEUR_INDISPONIBLE = _taille.MOTIF_MOTEUR_INDISPONIBLE
_REFUS_DIMENSIONNEMENT = _taille._REFUS_DIMENSIONNEMENT
_refus_dimensionnement = _taille._refus_dimensionnement
_panneaux_dimensionnement_horaire = _taille._panneaux_dimensionnement_horaire
_recommandation_avec_rendue = _taille._recommandation_avec_rendue
_residential_panel_count = _taille._residential_panel_count


# ═══════════════════════════════════════════════════════════════════════════
# RÉ-EXPORTS — QJR75 (2/2) : études → ``domain/etudes.py``
# ═══════════════════════════════════════════════════════════════════════════
from apps.ventes.domain import etudes as _etudes  # noqa: E402
rafraichir_etude_horaire = _etudes.rafraichir_etude_horaire
_bloc_horaire_deja_a_jour = _etudes._bloc_horaire_deja_a_jour
rafraichir_etude_horaire_devis = _etudes.rafraichir_etude_horaire_devis
rafraichir_dimensionnement_devis = _etudes.rafraichir_dimensionnement_devis
rafraichir_etudes_du_devis = _etudes.rafraichir_etudes_du_devis
compute_marge_snapshot = _etudes.compute_marge_snapshot
refresh_marge_snapshot = _etudes.refresh_marge_snapshot
