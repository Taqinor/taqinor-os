"""Clonage, duplication et modèles de devis (SPL268, déplacé de ``domain/creation.py``).

QJR407 ``cloner_devis`` — LE cloneur du domaine (la seule liste des champs
qu'une copie porte, révision QJR558 comprise), ``dupliquer_devis`` (NTUX13,
un devis indépendant qui redémarre en brouillon) et QJ16
``save_devis_as_preset`` (modèle réutilisable ; l'étude du client source n'est
jamais copiée, QJR547). Les noms lus ailleurs dans ``domain/`` sont importés
EN BAS de ce fichier, en visant le module qui porte le corps — jamais la
façade. Aucun statut n'est réécrit (règle #4). Déplacement pur : corps
octet-identiques, prouvé par ``tests/golden/split_dm_clone.json``.

NOM DU LOGGER FIGÉ sur ``apps.ventes.services`` : des tests capturent ce nom.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


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


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Imports EN BAS DE FICHIER, visant le module qui PORTE chaque corps.
from apps.ventes.domain.etudes import (  # noqa: E402
    etude_params_pour_copie,
    rafraichir_etudes_du_devis,
)
# QJR84 — l'écrivain unique des lignes (le seul constructeur de LigneDevis).
from apps.ventes.domain.lignes import cloner_lignes  # noqa: E402
