"""Création d'un devis — les chemins par lesquels un devis naît.

Le devis composé depuis un layout 3D (`build_devis_from_layout`), le dry-run
qui l'approuve (`composer_devis_residentiel`), le devis AUTOMATIQUE depuis un
lead (dimensionnement, refus motivé, marque anti-doublon, planification), le
brouillon issu d'un document OCR, la duplication, le devis SAV et l'upsell
d'intervention, et les préréglages (enregistrer / appliquer).

LES CHEMINS PASSENT PAR LE PIPELINE. Le calepinage (`build_devis_from_layout`)
et le devis automatique (`build_devis_auto`) appellent `pipeline.appliquer` ;
le dry-run appelle les mêmes étapes `verifier` / `composer` (QJR80-QJR85, puis
les bascules M5). Les comportements ont donc changé depuis le déplacement
QJR76 (QJR95/QJR96 notamment) : ce module n'est plus une simple copie.

IMPORT AMONT DE `domain/taille` : `composer_devis_residentiel` porte
`panel_watt=_AUTO_PANEL_WATT` comme VALEUR PAR DÉFAUT, évaluée à la
définition de la fonction — donc au chargement du module, avant tout pont de
bas de fichier. `domain/taille` est une FEUILLE (il n'importe que
`domain/catalogue`), l'import ne peut donc pas boucler.

QJR76 (M3) — DÉPLACEMENT PUR depuis ``apps/ventes/services.py``, dernier de la
vague : après lui, ``services.py`` n'est plus qu'une façade de ré-exports. Les
corps sont recopiés à l'identique ; la seule retouche possible est mécanique
(`from .x` → `from ..x`, MÊME cible).

ORDRE DE CHARGEMENT : ``services.py`` importe ``domain/`` à la toute fin ; un
module de ``domain/`` importe en BAS de fichier les noms qu'il lit ailleurs, et
il vise TOUJOURS le module qui porte le corps — jamais la façade.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
from decimal import Decimal
import logging

logger = logging.getLogger("apps.ventes.services")


# ── QJR129 — UN DEVIS NAÎT AVEC UN MARCHÉ, JAMAIS AVEC UN BLANC ─────────────
#
# Constat CS7 (audit du 30/08/2026), vérifié en code : les trois chemins qui
# créent un devis « à partir de rien » (bordereau AO, OCR, réserve
# d'intervention) laissaient ``mode_installation`` NULL, alors que le chemin
# canonique le pose explicitement.
#
# Le discriminateur de rendu ACCEPTE le vide (``quote_engine/residential/
# renderer.is_residential`` : ``if mode not in ("", "residentiel", …)``), un
# repli que le dépôt qualifie lui-même de « défaut d'AFFICHAGE PDF choisi pour
# ne jamais perdre le rendu d'un devis, PAS une preuve que ce devis EST
# résidentiel » — et ``is_residential`` pilote AUSSI la page publique client.
# Un bordereau de marché à prix unitaires (« Terrassement (m³) ») partait donc
# au client dans la présentation « proposition solaire résidentielle ».
#
# La règle : le marché DÉCLARÉ quand il existe (le lead de l'affaire, le
# chantier, le devis d'origine du chantier), sinon un défaut EXPLICITE et
# documenté par chemin. Aucun de ces trois documents n'est une étude solaire
# résidentielle : le défaut ne peut donc pas l'être.

#: Les quatre marchés de ``Devis.ModeInstallation``. ``crm.Lead.
#: TypeInstallation`` porte EXACTEMENT les mêmes quatre valeurs ;
#: ``installations.Installation.TypeInstallation`` n'en porte que trois (son
#: « industriel » est libellé « Industriel / Commercial »). Le recoupement est
#: donc direct, sans table de correspondance.
MODES_INSTALLATION = ('residentiel', 'industriel', 'commercial', 'agricole')


def mode_installation_declare(*sources, defaut):
    """QJR129 — le premier marché DÉCLARÉ parmi ``sources``, sinon ``defaut``.

    ``sources`` — des objets susceptibles de porter ``mode_installation`` (un
    devis) ou ``type_installation`` (un lead, un chantier) ; ``None`` est
    ignoré. Le premier non vide et RECONNU gagne : une valeur hors des quatre
    choix fermés est écartée plutôt que posée telle quelle.

    Ne lit RIEN en base et n'écrit rien : elle ne fait que lire des attributs
    d'objets déjà chargés par l'appelant (aucun import cross-app).
    """
    for source in sources:
        if source is None:
            continue
        for attribut in ('mode_installation', 'type_installation'):
            valeur = (getattr(source, attribut, None) or '').strip().lower()
            if valeur in MODES_INSTALLATION:
                return valeur
    return defaut


def create_draft_devis_from_ocr(*, company, user, lead, fields, origine=None):
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

    NTAPI18 — ``origine`` remplace la PREMIÈRE ligne de la note (celle qui dit
    d'où vient le brouillon). Défaut : le texte OCR historique, inchangé au
    caractère près. L'API publique (`devis:write`) passe sa propre phrase :
    écrire « créé depuis un document OCR » sur un devis créé par une
    intégration serait tout simplement faux pour le commercial qui le relit.
    Le RESTE du comportement (résolution du client, référence anti-collision,
    statut brouillon, marché déclaré) est identique — c'est bien le MÊME
    service cross-app, pas un second chemin de création.
    """
    from apps.ventes.models import Devis
    from apps.ventes.utils.company_settings import create_numbered
    from apps.crm.services import resolve_client_for_lead

    if lead is None:
        raise ValueError("create_draft_devis_from_ocr requires a lead")
    client = resolve_client_for_lead(lead)

    fields = fields or {}
    notes = [origine or "Devis brouillon créé depuis un document OCR."]
    for key, label in (('numero', 'N° document'), ('montant_ht', 'Montant HT'),
                       ('montant_tva', 'Montant TVA'),
                       ('montant_ttc', 'Montant TTC'), ('date', 'Date')):
        val = fields.get(key)
        if val not in (None, ''):
            notes.append(f"{label} : {val}")
    note = "\n".join(notes)

    # QJR129 / CS7 — le marché du LEAD quand il est déclaré, sinon COMMERCIAL.
    # Un document OCR n'est PAS une étude solaire résidentielle : le laisser à
    # NULL le faisait router vers le rendu « proposition solaire résidentielle »
    # (écran client compris). Le brouillon ne porte de toute façon aucune ligne
    # et le commercial fixe le vrai marché dans l'éditeur.
    mode = mode_installation_declare(
        lead, defaut=Devis.ModeInstallation.COMMERCIAL)

    def _create(ref):
        return Devis.objects.create(
            company=company,
            reference=ref,
            client=client,
            lead=lead,
            statut=Devis.Statut.BROUILLON,
            created_by=user,
            note=note,
            mode_installation=mode,
        )

    devis = create_numbered(Devis, company, 'devis', _create)
    logger.info('FG106: devis brouillon %s créé depuis OCR (company %s)',
                devis.reference, getattr(company, 'id', '?'))
    return devis


def _structure_demandee(lead, produit_id=None, type_demande=None):
    """STKCAT9 — ``(id de produit, type)`` de structure POUR CE DEVIS-LÀ.

    L'ordre est celui des trois réglages ponctuels de ``build_devis_auto`` :

      1. CE QUE L'APPELANT IMPOSE — un choix fait à l'écran pour ce devis-là
         reste souverain et ne réécrit jamais la fiche du lead ;
      2. LE PRODUIT ÉPINGLÉ SUR LE LEAD (``structure_produit``) — la pergola,
         le carport, le bac lesté : tout ce qu'``structure_pref`` ne sait pas
         dire ;
      3. LA PRÉFÉRENCE ``structure_pref`` du lead, mappée par MOT-CLÉ sur le
         vocabulaire de la composition (« aluminium » → ``'alu'``, « acier » →
         ``'acier'``) ;
      4. à défaut, ``(None, 'acier')`` — le défaut historique, donc un lead
         qui ne dit rien produit EXACTEMENT le devis d'hier.

    LECTURE PAR ``getattr`` SUR L'INSTANCE DÉJÀ CHARGÉE : ``apps.ventes``
    n'importe jamais les modèles d'``apps.crm`` (règle de modularité du
    dépôt), et lire ``structure_produit_id`` plutôt que ``structure_produit``
    évite de charger le produit pour n'en prendre que la clé. Un ``lead``
    absent (``None``) rend le défaut, sans lever.
    """
    if produit_id:
        return produit_id, (type_demande or 'acier')
    if type_demande:
        return None, type_demande
    produit_lead = getattr(lead, 'structure_produit_id', None)
    if produit_lead:
        return produit_lead, 'acier'
    pref = str(getattr(lead, 'structure_pref', '') or '').strip().lower()
    if pref.startswith('alu'):
        return None, 'alu'
    return None, 'acier'


# ── QJR563 — devise par défaut d'un devis créé ───────────────────────────────

def devise_par_defaut(company):
    """QJR563 — LA devise d'un devis créé sans devise explicite : celle de la
    société (``CompanyProfile.devise_defaut``, FG52), repli ``'MAD'``. Un seul
    helper pour ``POST /devis/`` ET ``/devis/atomic/`` (chemin réel du
    générateur), qui ne l'appliquait pas."""
    if company is None:
        return 'MAD'
    from apps.parametres.models import CompanyProfile
    try:
        profil = CompanyProfile.get(company=company)
    except Exception:  # noqa: BLE001 — jamais bloquant : repli MAD
        return 'MAD'
    return getattr(profil, 'devise_defaut', '') or 'MAD'


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
    from ..models import Devis
    from apps.ventes.utils.company_settings import create_numbered
    from apps.crm.models import Client

    client = Client.objects.get(pk=client_id, company=company)

    def _create(ref):
        return Devis.objects.create(
            company=company, reference=ref, client=client,
            statut=Devis.Statut.BROUILLON, created_by=user,
            note=note or '',
        )
    devis = create_numbered(Devis, company, 'devis', _create)

    for ligne in (lignes or []):
        produit_id = ligne.get('produit_id')
        if not produit_id:
            continue
        creer_ligne(
            devis,
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
    from ..models import Devis
    from apps.ventes.utils.company_settings import create_numbered

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

    devis = create_numbered(Devis, company, 'devis', _create)
    intervention.devis_upsell_id = devis.id
    intervention.save(update_fields=['devis_upsell_id'])
    logger.info(
        'ZFSM5: devis upsell %s créé depuis intervention %s (company %s)',
        devis.reference, intervention.id, getattr(company, 'id', '?'))
    return devis


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.bordereau import concevoir_electrique_du_devis  # noqa: E402,F401
from apps.ventes.domain.catalogue import (  # noqa: E402,F401
    _is_battery,
    _is_hybrid_inverter,
    _is_reseau_inverter,
    carte_marques_composition,
    ordre_lignes_societe,
)
from apps.ventes.domain.composition import (  # noqa: E402,F401
    composition_deux_optimiseurs,
    composition_residentielle,
)
from apps.ventes.domain.etudes import (  # noqa: E402,F401
    refresh_marge_snapshot,
)
from apps.ventes.domain.lignes import (  # noqa: E402,F401
    creer_ligne,
)
from apps.ventes.domain.scenario import (  # noqa: E402,F401
    poser_puissance_kwc,
)
