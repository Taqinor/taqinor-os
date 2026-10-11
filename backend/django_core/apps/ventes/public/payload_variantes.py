"""Variantes, gammes et version remplaçante de la proposition publique (SPL249, déplacé de ``public_views.py``).

Total TTC et résumés des variantes, lignes et comparatif des gammes, bloc
``remplace_par`` d'une version remplacée — assemblés par
``public_views.proposal_data``. Aucune vue ici. Déplacement pur : corps
octet-identiques (seule la profondeur des imports relatifs locaux change),
prouvé par ``tests/golden/split_pv_variantes.json``.
"""
import logging

from django.db import models
from django.utils import timezone

from ..models import ShareLink
from ..utils.anticopie import (
    agreger_designations_kit as _agreger_designations_kit,
)

# Même émetteur de journal qu'avant le déplacement (filtres et tests inchangés).
logger = logging.getLogger("apps.ventes.public_views")


def _variant_total_ttc(frere):
    """QJR11 — total TTC AFFICHÉ d'un devis frère, par la chaîne canonique.

    UNE seule chaîne monétaire (``utils.options.option_totaux`` →
    ``selectors._canonical_totaux``) : HT brut des lignes qui COMPTENT
    (``compte_dans_totaux`` — donc jamais une option non activée ni une ligne
    de section/note) → remise globale → TVA **par ligne** → TTC au centime.

    L'option retenue est celle que porte le total d'affichage canonique
    (``builder.display_total`` / ``utils.options.totaux_affichage_repli``,
    LANE CHOIX-AVEC du 25/08) : sur un devis à DEUX options c'est l'option
    AVEC batterie — jamais la somme des deux, un montant qui n'existe dans
    aucun document. Le prédicat utilisé est le prédicat LÉGER
    (``deux_options_declarees``) : la bande des variantes ne doit pas payer un
    rendu PDF complet par frère, et un moteur en échec ne doit pas la faire
    retomber silencieusement sur la somme des deux options.
    """
    from ..utils.options import (
        AVEC_BATTERIE, SANS_BATTERIE, deux_options_declarees,
        filter_lines_for_option, option_totaux,
    )
    lignes = list(frere.lignes.select_related('produit', 'devis').all())
    if not deux_options_declarees(frere):
        # Option unique / pompage / liste libre : tout le devis, comme la liste.
        return option_totaux(frere, option='', lignes=lignes)['ttc']
    avec = option_totaux(
        frere, option='',
        lignes=filter_lines_for_option(lignes, AVEC_BATTERIE))['ttc']
    if avec:
        return avec
    # Panier « avec » sans total lisible → l'autre option, jamais un forfait.
    return option_totaux(
        frere, option='',
        lignes=filter_lines_for_option(lignes, SANS_BATTERIE))['ttc']


def _variant_summaries(devis) -> list:
    """QJ15 — côte-à-côte : résumé minimal de chaque variante du devis.

    Retourne une liste de dicts (non vide uniquement quand il existe au moins
    une autre variante active partageant le même version_parent). La liste est
    vide si le devis est isolé (pas de version_parent, pas de frère/sœur actif).

    Le summary est volontairement minimal : id, reference, version, note,
    total_ttc. Jamais de prix d'achat ni de marge (règle #4).

    QJR11 (29/08/2026) — ``total_ttc`` passait par une SEPTIÈME chaîne
    monétaire écrite ici à la main (``.values('quantite', ...)`` puis produit
    en Python) : elle ne filtrait pas ``compte_dans_totaux`` (donc comptait les
    options non activées et plantait sur une ligne de section, ``quantite``
    NULL), appliquait le taux de TVA du DEVIS au lieu du taux par ligne, et sur
    un frère à deux options additionnait les DEUX paniers. Elle est remplacée
    par la chaîne canonique (:func:`_variant_total_ttc`). Un frère dont le
    total est illisible est OMIS de la bande — jamais un chiffre de repli
    (règle fondateur « zéro chiffre inventé ») — et un frère en échec ne
    supprime plus la bande entière (constat V1 : l'``except`` de sortie
    renvoyait ``[]``).
    """
    root = devis.version_parent_id or devis.pk
    try:
        from ..models import Devis as DevisModel
        # Include root + all siblings with the same version_parent.
        siblings = list(
            DevisModel.objects
            .filter(
                company=devis.company,
                is_active=True,
            )
            .filter(
                models.Q(pk=root) | models.Q(version_parent_id=root)
            )
            .exclude(pk=devis.pk)   # exclude self — self is the main payload
            # QJR537 — un BROUILLON n'est JAMAIS montré au client (même règle
            # que ``selectors.devis_du_client_portail``) : après une révision,
            # la page de v1 exposait la v2 EN COURS de correction et son total.
            .exclude(statut=DevisModel.Statut.BROUILLON)
            .order_by('version', 'id')
            # ``etude_params`` est chargé ici (et non différé) : le filtre de
            # gamme ci-dessous le lit sur chaque sœur — le différer coûterait
            # une requête par ligne.
            .only('id', 'reference', 'version', 'note',
                  'taux_tva', 'remise_globale', 'etude_params')
        )
        # GAMMES — une sœur porteuse d'un libellé de gamme n'est PAS une
        # « autre taille » : elle est rendue par le bloc « gammes » (mode
        # d'envoi « les_deux ») ou tue (mode « seule »). L'exclure ici évite le
        # doublon dans la bande « Autres tailles proposées » ET toute fuite de
        # l'autre gamme quand le vendeur a choisi d'en envoyer une seule.
        from ..services import gamme_nom
        siblings = [s for s in siblings if not gamme_nom(s)]
        if not siblings:
            return []
        out = []
        for s in siblings:
            try:
                total_ttc = _variant_total_ttc(s)
            except Exception:  # noqa: BLE001 — un frère illisible n'efface
                # pas la bande : il est simplement OMIS (jamais un forfait).
                logger.warning(
                    "Total de variante illisible pour le devis %s — frère omis",
                    getattr(s, 'pk', None))
                continue
            out.append({
                'id': s.id,
                'reference': s.reference,
                'version': s.version,
                'note': (s.note or ''),
                'total_ttc': round(float(total_ttc), 2),
            })
        return out
    except Exception:  # noqa: BLE001 — best-effort, never break the proposal
        logger.warning(
            "Bande des variantes indisponible pour le devis %s",
            getattr(devis, 'pk', None))
        return []


# ── GAMMES — offre à DEUX GAMMES, envoi à la carte (fondateur 2026-08-18) ───
# Une gamme = un devis frère COMPLET (mécanique de variantes QJ15). Le lien
# client rend TOUJOURS le devis de son jeton ; en mode « les_deux » il expose
# EN PLUS le résumé de la gamme sœur pour que le client choisisse AVANT de
# signer. En mode « seule » : rien de la sœur ne franchit la frontière.
# UN PDF = UNE GAMME : chaque carte pointe vers le PDF de SA gamme (le jeton
# de la sœur), jamais un PDF fusionné.
def _gamme_lignes_publiques(devis, est_standard=False):
    """Composition CLIENT d'un devis : (désignation, quantité) par ligne.

    L-NIV (24/08/2026) — ``est_standard`` applique LA règle d'agrégation « kit »
    (``utils.anticopie``, la même que la charge utile JSON et le PDF public)
    AVANT de publier la composition : sans elle, le comparatif de gammes
    republiait ligne à ligne la nomenclature fixation/câblage/protection que le
    reste de la page venait de masquer — la fuite par la porte de côté.

    Whitelist stricte — ni prix d'achat, ni marge, ni champ interne (règle #4).
    Sert au tableau comparatif factuel des lignes qui diffèrent entre gammes.

    PÉRIMÈTRE = celui de la CHAÎNE CANONIQUE, pas un périmètre à part. Seules
    les lignes qui entrent réellement dans le total comparé sont publiées :
    lignes PRODUIT non optionnelles, exactement comme
    ``quote_engine/builder.py`` (``lignes = [li for li in lignes if not
    li.optionnelle]``) et ``selectors.ligne_compte_dans_totaux``. Sans ce
    filtre, un add-on ``optionnelle=True`` (XSAL5, HORS total) et les
    intertitres ``SECTION`` (XSAL14, sans quantité) s'affichaient à côté d'un
    ``total_ttc`` qui, lui, les EXCLUT : le client concluait qu'une gamme
    incluait un matériel qu'elle ne facture pas."""
    from ..models import LigneDevis
    lignes = []
    for ln in (LigneDevis.objects
               .filter(devis=devis,
                       type_ligne=LigneDevis.TypeLigne.PRODUIT,
                       optionnelle=False)
               .order_by('ordre', 'id')
               .values('designation', 'quantite')):
        designation = (ln['designation'] or '').strip()
        if not designation:
            continue
        try:
            qte = float(ln['quantite'])
        except (TypeError, ValueError):
            qte = None
        lignes.append({'designation': designation, 'quantite': qte})
    if est_standard:
        lignes = _agreger_designations_kit(lignes)
    return lignes


def _gamme_comparatif(lignes_ici, lignes_soeur):
    """Lignes qui DIFFÈRENT entre les deux compositions (jamais les communes).

    Comparaison par désignation : une désignation absente d'un côté, ou
    présente des deux côtés avec une quantité différente, entre au comparatif.
    Une valeur absente est omise (jamais un « 0 » inventé).

    Les quantités d'une MÊME désignation sont AGRÉGÉES (somme) : un devis
    multi-villa (QJ29/QJ30) ou sectionné (XSAL14) répète la même désignation
    une fois par groupe. Ne garder que la première (``setdefault``) publiait
    « 10 » là où le devis porte 10 + 6 = 16 panneaux — un chiffre faux présenté
    au client comme la composition de sa gamme."""
    def _index(lignes):
        out = {}
        for ln in lignes:
            designation, qte = ln['designation'], ln['quantite']
            if designation not in out:
                out[designation] = qte
            elif qte is not None:
                out[designation] = (out[designation] or 0) + qte
        return out

    ici, soeur = _index(lignes_ici), _index(lignes_soeur)
    lignes = []
    for designation in list(ici) + [d for d in soeur if d not in ici]:
        q_ici, q_soeur = ici.get(designation), soeur.get(designation)
        if designation in ici and designation in soeur and q_ici == q_soeur:
            continue
        ligne = {'designation': designation}
        if q_ici is not None:
            ligne['quantite'] = q_ici
        if q_soeur is not None:
            ligne['quantite_soeur'] = q_soeur
        lignes.append(ligne)
    return lignes


def _gammes_public(devis, est_standard=False):
    """Bloc « choix de gamme » de la charge utile publique, ou ``None``.

    ``est_standard`` (L-NIV) est passé tel quel à ``_gamme_lignes_publiques`` :
    le comparatif obéit au MÊME niveau que le reste de la page.

    ``None`` (clé absente) dans TOUS les cas où le client ne doit rien voir de
    l'autre gamme : devis sans gamme, gamme sans sœur vivante, ou mode d'envoi
    « seule ». L'écart est donné en MAD ABSOLUS et signé côté client.

    LES DEUX CÔTÉS DU COMPARATIF SORTENT DE LA MÊME FONCTION (fondateur
    2026-08-18 ; note recalée 25/08 — depuis la règle « choix forcé = avec »,
    ``display_total`` porte l'option AVEC sur un devis bi-option) :
    ``display_totals(...)['total']`` pour la gamme courante COMME
    pour la sœur. ``data['display_total']`` seul ne suffit pas partout : il ne
    couvre pas le repli léger (moteur en échec) que ``build_quote_data`` ne
    gère pas (``utils/options.totaux_affichage_repli``). Comparer un devis
    bi-option à un devis mono-option revenait donc à soustraire deux
    compositions différentes — l'écart annoncé au client (« + 44 000 MAD »)
    n'était l'écart de rien. Même appel des deux côtés ⇒ sémantique identique
    ⇒ écart comparable, et toujours un prix qui existe dans un document
    (PV86)."""
    from ..services import (
        GAMME_ENVOI_LES_DEUX, gamme_envoi, gamme_info, gamme_soeur,
    )
    try:
        info = gamme_info(devis)
        if not info.get('nom'):
            return None
        if gamme_envoi(devis) != GAMME_ENVOI_LES_DEUX:
            return None
        soeur = gamme_soeur(devis)
        if soeur is None:
            return None
        from ..models import ShareLink
        from ..quote_engine.builder import display_totals
        from ..utils.client_links import chemin_proposition

        info_soeur = gamme_info(soeur)
        lien_soeur = ShareLink.for_devis(soeur)
        total_soeur = display_totals(soeur).get('total')
        total_soeur = (round(float(total_soeur), 2)
                       if total_soeur is not None else None)
        total_courant = display_totals(devis).get('total')
        courant = (round(float(total_courant), 2)
                   if total_courant is not None else None)
        ecart = (round(total_soeur - courant, 2)
                 if (total_soeur is not None and courant is not None) else None)
        lignes_ici = _gamme_lignes_publiques(devis, est_standard)
        lignes_soeur = _gamme_lignes_publiques(soeur, est_standard)
        return {
            'envoi': GAMME_ENVOI_LES_DEUX,
            'courante': {
                'nom': str(info.get('nom') or ''),
                'recommandee': bool(info.get('recommandee')),
                'reference': devis.reference,
                'total_ttc': courant,
            },
            'soeur': {
                'nom': str(info_soeur.get('nom') or ''),
                'recommandee': bool(info_soeur.get('recommandee')),
                'reference': soeur.reference,
                'total_ttc': total_soeur,
                # Le jeton de la sœur : la carte « choisir cette gamme » ouvre
                # SON lien (document complet) et SON PDF — la signature porte
                # donc toujours sur le devis de la gamme réellement choisie.
                'proposition_path': chemin_proposition(soeur, lien_soeur.token),
                'ecart_ttc': ecart,
            },
            'comparatif': _gamme_comparatif(lignes_ici, lignes_soeur),
        }
    except Exception:  # noqa: BLE001 — jamais casser la proposition
        return None


def _remplace_par_public(devis):
    """QJR536 — la version qui REMPLACE ce devis, telle que la page publique
    peut la montrer : ``None`` si le devis n'a pas été remplacé, sinon
    ``{'reference', 'url'}``.

    Suit la chaîne ``superseded_by`` jusqu'à la DERNIÈRE version de la MÊME
    société (jamais une autre société ; une boucle est coupée). ``url`` = le
    chemin public du successeur SEULEMENT s'il n'est pas brouillon et porte un
    ``ShareLink`` déjà valide — aucun lien n'est créé ici (lecture pure) ;
    sinon ``None`` (on dit « remplacée par … » sans servir un brouillon)."""
    from ..models import Devis
    from ..utils.client_links import chemin_proposition

    courant = devis
    vus = {devis.pk}
    while courant.superseded_by_id and courant.superseded_by_id not in vus:
        suivant = (Devis.objects
                   .filter(pk=courant.superseded_by_id,
                           company_id=devis.company_id)
                   .select_related('client', 'lead')
                   .first())
        if suivant is None:
            break
        vus.add(suivant.pk)
        courant = suivant
    if courant.pk == devis.pk:
        return None
    url = None
    if courant.statut != Devis.Statut.BROUILLON:
        lien = (ShareLink.objects
                .filter(devis=courant, expires_at__gt=timezone.now())
                .order_by('-expires_at')
                .first())
        if lien is not None:
            url = chemin_proposition(courant, lien.token)
    return {'reference': courant.reference, 'url': url}
