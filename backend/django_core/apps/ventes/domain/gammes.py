"""Gammes — Essentielle / Premium, et les devis qui en naissent.

Le libellé de gamme d'un devis et sa gamme sœur, le mode d'envoi
(une seule gamme ou les deux), la création d'une variante de gamme, les
paramètres de gammes d'une société, le devis créé depuis une réserve et le
lead d'origine d'un devis dérivé.

QJR76 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``, dernier de la
vague : après lui, ``services.py`` n'est plus qu'une façade de ré-exports. Les
corps sont recopiés à l'identique ; la seule retouche possible est mécanique
(`from .x` → `from ..x`, MÊME cible).

ORDRE DE CHARGEMENT : ``services.py`` importe ``domain/`` à la toute fin ; un
module de ``domain/`` importe en BAS de fichier les noms qu'il lit ailleurs, et
il vise TOUJOURS le module qui porte le corps — jamais la façade.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


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
    from apps.ventes.models import Devis
    from apps.ventes.domain.lignes import cloner_lignes
    from apps.ventes.domain.etudes import (
        etude_params_pour_copie, rafraichir_etudes_du_devis)
    from apps.ventes.utils.company_settings import create_numbered

    nom_gamme = str(nom_gamme or '').strip()
    if not nom_gamme:
        raise ValueError('creer_variante_gamme exige un nom de gamme.')
    company = devis.company
    root = devis.version_parent or devis
    holder = {}

    # etude_params est COPIÉ (jamais partagé) : la gamme sœur porte son propre
    # bloc ``gamme`` sans jamais toucher celui de la source.
    #
    # QJR117 / CS5 — et elle ne porte plus les CHIFFRES du frère : la docstring
    # promet « chaque gamme a sa composition et ses prix PROPRES », or la sœur
    # recevait son ``etude_horaire``, son ``dimensionnement`` (coût, payback)
    # et ses économies. Les deux gammes partant ENSEMBLE par défaut
    # (``GAMME_ENVOI_LES_DEUX``), le client comparait deux offres dont l'une
    # affichait le payback de l'autre.
    params_soeur = etude_params_pour_copie(
        getattr(devis, 'etude_params', None)) or {}
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

    # QJR116 — même cloneur unique que le duplicata et le renouvellement
    # (``domain/lignes.cloner_lignes``) : la sœur est une COPIE CONFORME, et
    # ce qu'« à l'identique » recouvre n'est plus retapé à trois endroits.
    cloner_lignes(devis, soeur)
    # QJR117 — les études de la SŒUR sont recalculées sur SES lignes (force :
    # le dimensionnement se court-circuite sinon sur empreinte concordante).
    rafraichir_etudes_du_devis(soeur, force=True)

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
    from ..models import ParametresGammes
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
