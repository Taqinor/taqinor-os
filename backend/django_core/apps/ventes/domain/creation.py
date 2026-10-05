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
    from apps.ventes.utils.references import create_with_reference
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

    devis = create_with_reference(Devis, 'DEV', company, _create)
    logger.info('FG106: devis brouillon %s créé depuis OCR (company %s)',
                devis.reference, getattr(company, 'id', '?'))
    return devis


def cloner_devis(devis, *, user, note=None, version=1, version_parent=None,
                 remplacements=None, revision=False):
    """QJR407 — LE CLONEUR DU DOMAINE : le SEUL endroit où la liste des champs
    qu'une copie de devis porte est écrite.

    Trois chemins produisent une copie de devis : la duplication
    (:func:`dupliquer_devis`), la RÉVISION et la DUPLICATION EN VARIANTES
    (``views/devis.py``). Les deux derniers réimplémentaient
    ``Devis.objects.create(...)`` à la main et OMETTAIENT les sept champs que
    ce cloneur porte explicitement depuis QJR146(a) — ``devise``,
    ``taux_change``, ``echeancier``, ``acompte_pct``, ``acompte_montant``,
    ``entite``, ``custom_data``. Un devis dont l'échéancier avait été NÉGOCIÉ
    repartait donc sur l'échéancier par DÉFAUT de la société, et c'est la
    première tranche de cet échéancier que l'email de confirmation annonce au
    client comme acompte.

    Ce qui DIFFÈRE d'un chemin à l'autre — et seulement cela — est paramétré :

    * ``note`` — le préfixe éditorial de la copie (``None`` ⇒ la note de la
      source, telle quelle) ;
    * ``version`` / ``version_parent`` — le duplicata est SANS lien de version
      (1 / ``None``), la révision et la variante sont GROUPÉES sur la racine ;
    * ``remplacements`` — la mise à l'échelle des quantités, propre à la
      duplication en variantes (passée telle quelle à ``cloner_lignes``) ;
    * ``revision`` — QJR558 : UN booléen (jamais un tuple de noms de champs,
      que QJR407 a supprimé), que SEUL ``reviser_devis`` passe à ``True``. Une
      révision repart du devis TEL QU'IL EST, travail manuel compris : la
      conception toiture 3D (``roof_layout`` + ``layout_hash``), son rendu
      (``roof_image``, clé MinIO — par référence), le registre D12
      (``overrides``) et les tailles explorées (``offres_tailles_config``),
      en ``copy.deepcopy`` (aliasing S5-2). Porter ``roof_layout`` est sûr :
      les dérivées sont purgées par ``etude_params_pour_copie`` et recalculées
      (``force=True``) ci-dessous. ``date_validite`` n'est JAMAIS copiée
      (re-dérivée, ``utils/expiry``). Duplicata, variante et gamme : inchangés.

    ATOMICITÉ (S5-4) : la création du devis ET le clonage de ses lignes se font
    dans UNE transaction. Les deux vues créaient le devis PUIS clonaient ses
    lignes hors transaction : un incident entre les deux étapes laissait un
    brouillon ORPHELIN sans lignes, visible dans la liste et chiffrable à zéro.

    ALIASING (S5-2) : ``etude_params`` passe TOUJOURS par
    ``etude_params_pour_copie`` — la copie ne partage plus l'objet de la source
    et ne publie plus les chiffres dérivés d'une AUTRE taille d'installation.
    Les études de la copie sont ensuite recalculées sur SES lignes
    (``force=True``), comme sur les trois chemins du domaine.
    """
    from django.db import transaction

    from apps.ventes.models import Devis
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
            note=(devis.note if note is None else note),
            mode_installation=devis.mode_installation,
            # QJR117 — la CONFIGURATION du source, jamais ses chiffres
            # dérivés : sans ``roof_layout``, le recalage qui les rendait
            # honnêtes ne s'exécute pas sur la copie et le moteur les
            # prenait verbatim (CS4).
            etude_params=etude_params_pour_copie(devis.etude_params),
            prix_cible_kwc=devis.prix_cible_kwc,
            devise=devis.devise,
            taux_change=devis.taux_change,
            # ── QJR146 (a) — LES CONDITIONS DE PAIEMENT SUIVENT LA COPIE ────
            # Les deux JSONField sont COPIÉS, jamais partagés par référence
            # (le piège que QJR117 a fermé pour ``etude_params``).
            echeancier=(list(devis.echeancier)
                        if isinstance(devis.echeancier, list)
                        else devis.echeancier),
            acompte_pct=devis.acompte_pct,
            acompte_montant=devis.acompte_montant,
            entite=devis.entite,
            custom_data=(dict(devis.custom_data)
                         if isinstance(devis.custom_data, dict)
                         else devis.custom_data),
            created_by=user,
            version=version, version_parent=version_parent, is_active=True,
            **_champs_de_revision(devis, revision),
        )
        holder['obj'] = obj
        return obj

    with transaction.atomic():
        create_numbered(Devis, company, 'devis', _save)
        copie = holder['obj']
        # QJR116 — UN SEUL cloneur de LIGNES pour tous les chemins de copie
        # (``domain/lignes.cloner_lignes``) : la liste de champs n'est plus
        # maintenue à la main, elle ne peut donc plus diverger. Elle reprend le
        # jeu COMPLET — y compris le rattachement au LOT.
        cloner_lignes(devis, copie, remplacements=remplacements)
    # QJR117 — les études de la COPIE sont recalculées sur SES lignes, en
    # ``force`` : sans lui, le dimensionnement se court-circuite sur empreinte
    # concordante et l'édition de ligne ne rattrape jamais. Best-effort — aucun
    # rafraîchisseur ne lève, aucun ne touche statut/lignes/totaux (règle #4).
    # HORS transaction : un rafraîchissement raté n'annule jamais une copie.
    rafraichir_etudes_du_devis(copie, force=True)
    return copie


def _champs_de_revision(devis, revision):
    """QJR558 — le travail MANUEL qu'une révision (et elle seule) porte."""
    if not revision:
        return {}
    import copy
    return {
        'roof_layout': copy.deepcopy(devis.roof_layout),
        'layout_hash': devis.layout_hash,
        'roof_image': devis.roof_image,
        'overrides': copy.deepcopy(devis.overrides),
        'offres_tailles_config': copy.deepcopy(devis.offres_tailles_config),
    }


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

    Les lignes sont clonées à l'identique (mêmes quantités/prix/sections).

    QJR407 — LE CORPS EST CELUI DU CLONEUR (:func:`cloner_devis`) : la
    liste des champs n'est plus écrite ici. Ce chemin ne garde que ce qui
    lui est propre — le préfixe de note et l'absence de lien de version.
    """
    copie = cloner_devis(
        devis, user=user,
        note=(f'[Copie de {devis.reference}] ' + (devis.note or '')).strip(),
        # Duplicata indépendant : jamais de groupe de version (à la
        # différence de dupliquer-variante, QJ15).
        version=1, version_parent=None)
    logger.info('NTUX13: devis %s dupliqué en %s (company %s)',
                devis.reference, copie.reference,
                getattr(devis.company, 'id', '?'))
    return copie


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


# ── QJ16 — Reusable quote presets ────────────────────────────────────────────

def save_devis_as_preset(devis, nom: str, description: str = "", *, user=None):
    """QJ16 — snapshot a Devis into a company-scoped DevisPreset.

    The preset captures the line configuration (QJR547 — every field of
    ``lignes.CHAMPS_CLONES`` per line, ordered like the devis, plus taux_tva
    and remise_globale at devis level) as a JSON snapshot. The source client's
    study (``etude_params``) is NEVER captured.  The company is ALWAYS forced from
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

    # QJR547 (contrat QJR508, devis_preset.json) — chaque entrée reprend le
    # jeu de champs du CLONEUR (``lignes.CHAMPS_CLONES``, jamais retapé ici) :
    # variante, option, type, ordre, verrous manuels, rôle, groupe — sans quoi
    # un modèle « Les deux » ramenait ses deux onduleurs dans la partie commune
    # et un prix négocié n'était plus verrouillé. Triées comme le devis
    # (ordre, id). Le produit est porté par ``produit_id`` ; le lot (propre à
    # UN devis) n'est jamais capturé. Jamais ``prix_achat``.
    from decimal import Decimal as _Decimal
    from apps.ventes.domain.lignes import CHAMPS_CLONES

    def _valeur(v):
        if isinstance(v, _Decimal):
            return _ds(v)
        return v

    lignes_snapshot = []
    for ligne in devis.lignes.order_by('ordre', 'id'):
        entree = {'produit_id': ligne.produit_id}
        for champ in CHAMPS_CLONES:
            if champ in ('produit', 'lot'):
                continue
            entree[champ] = _valeur(getattr(ligne, champ))
        lignes_snapshot.append(entree)

    preset = DevisPreset.objects.create(
        company=company,
        nom=nom.strip(),
        description=description,
        mode_installation=devis.mode_installation or None,
        taux_tva=devis.taux_tva,
        remise_globale=devis.remise_globale,
        lignes_snapshot=lignes_snapshot,
        # QJR547 — l'étude du client SOURCE (factures, attribution) n'est plus
        # jamais capturée : le champ reste (sans migration), toujours vide.
        etude_params_snapshot=None,
        created_by=user,
    )
    logger.info(
        'QJ16: preset "%s" saved (id=%s, company=%s, %d lignes)',
        preset.nom, preset.pk, company.pk, len(lignes_snapshot))
    return preset


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
    from ..utils.references import create_with_reference
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
    from ..utils.references import create_with_reference

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
    etude_params_pour_copie,
    rafraichir_etudes_du_devis,
    refresh_marge_snapshot,
)
from apps.ventes.domain.lignes import (  # noqa: E402,F401
    cloner_lignes,
    creer_ligne,
)
from apps.ventes.domain.scenario import (  # noqa: E402,F401
    poser_puissance_kwc,
)
