import logging

logger = logging.getLogger(__name__)
"""QJR516 (Groupe QJR5, D-QJR5-1 / D-QJR5-2 / D-QJR5-5) — UN SEUL prédicat de
modifiabilité d'un devis, PAR GESTE, servi au front.

LE CONSTAT. La règle « ce devis se modifie-t-il encore ? » était recopiée en
ligne à six endroits (``_MODIFIABLES`` ×2 dans ``views/devis.py``, ``FROZEN``
×2 dans ``views/devis.py`` et ``views/ligne_devis.py``, le tuple des options
de ``cycle_vie.activate_optional_line``, le brouillon-seul de la
resynchronisation) — et huit écritures (layout, roof-image, overrides,
etude-params, offres-tailles config/regenerer, lots) n'en portaient AUCUNE :
un devis ACCEPTÉ, dont la chaîne BC/Facture dépend, restait modifiable par
elles. Le sélecteur du contexte 3D déclarait modifiable un calepinage que
sync-layout refusait.

LA TABLE (geste → statuts qui l'acceptent). Un devis INACTIF (remplacé par une
révision, archivé) n'accepte AUCUN geste et n'est pas révisable (on révise sa
remplaçante) ; un devis accepté / refusé / expiré n'accepte aucun geste mais
est révisable (D-QJR5-2).

* ``LIGNES`` / ``ENTETE`` / ``BOQ`` / ``OPTIONS`` / ``ETUDE`` — brouillon +
  envoyé (D-QJR5-1 : un envoyé se corrige SUR PLACE). ``ETUDE`` couvre les
  écritures d'étude et de rendu qui ne recomposent pas les lignes
  (etude-params, overrides, offres-tailles config/regenerer, layout brut,
  roof-image).
* ``CALEPINAGE`` / ``TAILLE`` — brouillon + envoyé depuis QJR557
  (D-QJR5-5, même règle que l'Édition complète : la resynchronisation des
  lignes depuis un calepinage et l'application d'une taille d'offre
  corrigent un envoyé SUR PLACE, tracées par ``fin_de_geste_devis`` —
  chatter « corrigé après envoi : calepinage » / « : taille d'offre »).
* ``ECHEANCIER`` — brouillon + envoyé + ACCEPTÉ (VNT25, D-VNT-3) ; la règle
  d'argent est :func:`controler_echeancier_vente`.

Ce module LIT le statut, il ne l'écrit jamais (règle #4). Les tuples de CYCLE
DE VIE (acceptation, expiration, gammes…) n'en font PAS partie : ce prédicat ne
dit que « ce geste d'ÉDITION est-il permis ? ».
"""

LIGNES = 'LIGNES'
ENTETE = 'ENTETE'
BOQ = 'BOQ'
OPTIONS = 'OPTIONS'
ETUDE = 'ETUDE'
CALEPINAGE = 'CALEPINAGE'
TAILLE = 'TAILLE'
ECHEANCIER = 'ECHEANCIER'

_BROUILLON = 'brouillon'
_ENVOYE = 'envoye'
_ACCEPTE = 'accepte'

#: La table unique geste → statuts qui l'acceptent.
GESTES = {
    LIGNES: frozenset({_BROUILLON, _ENVOYE}),
    ENTETE: frozenset({_BROUILLON, _ENVOYE}),
    BOQ: frozenset({_BROUILLON, _ENVOYE}),
    OPTIONS: frozenset({_BROUILLON, _ENVOYE}),
    ETUDE: frozenset({_BROUILLON, _ENVOYE}),
    # QJR557 (D-QJR5-5) — un envoyé se corrige aussi par le calepinage 3D et
    # par « appliquer une taille d'offre » (accepté/refusé/expiré → Réviser).
    CALEPINAGE: frozenset({_BROUILLON, _ENVOYE}),
    TAILLE: frozenset({_BROUILLON, _ENVOYE}),
    # VNT25 (D-VNT-3) — l'échéancier se réécrit même sur un ACCEPTÉ.
    ECHEANCIER: frozenset({_BROUILLON, _ENVOYE, _ACCEPTE}),
}

#: Les statuts CLOS (document engagé ou abandonné) : révisables, jamais
#: modifiables.
STATUTS_CLOS = frozenset({'accepte', 'refuse', 'expire'})


class DevisNonModifiable(Exception):
    """Levée par :func:`exiger_modifiable` — l'appelant la traduit en 409
    ``{detail, statut, revision_possible}`` (ou garde son propre code
    historique, voir les sites d'appel)."""

    def __init__(self, detail, *, statut='', revision_possible=False):
        super().__init__(detail)
        self.detail = detail
        self.statut = statut
        self.revision_possible = revision_possible

    def corps(self):
        return {'detail': self.detail, 'statut': self.statut,
                'revision_possible': self.revision_possible}


def _libelle_statut(devis):
    try:
        return devis.get_statut_display()
    except Exception:  # noqa: BLE001 — objet léger sans choices (D-ENF22-BLE001)
        logger.warning("modifiabilite._libelle_statut : erreur ignorée (mode dégradé)", exc_info=True)
        return str(getattr(devis, 'statut', '') or '')


def _reference_successeur(devis):
    if not getattr(devis, 'superseded_by_id', None):
        return None
    try:
        return devis.superseded_by.reference
    except Exception:  # noqa: BLE001 — successeur supprimé entre-temps (D-ENF22-BLE001)
        logger.warning("modifiabilite._reference_successeur : erreur ignorée (mode dégradé)", exc_info=True)
        return None


def revision_possible(devis):
    """D-QJR5-2 — actif ET pas brouillon (envoyé, accepté, refusé, expiré)."""
    return bool(getattr(devis, 'is_active', True)
                and getattr(devis, 'statut', None) != _BROUILLON)


def verdict(devis, geste=ENTETE):
    """Le verdict d'UN geste sur ce devis, sous la forme du contrat
    ``contract_samples/devis_modifiabilite.json`` :
    ``{modifiable, raison_non_modifiable, revision_possible}`` — la raison est
    toujours une chaîne (``''`` quand modifiable)."""
    if geste not in GESTES:
        raise ValueError(f'Geste de modification inconnu : {geste!r}.')
    statut = getattr(devis, 'statut', None)
    actif = bool(getattr(devis, 'is_active', True))
    revisable = revision_possible(devis)
    if not actif:
        ref = _reference_successeur(devis)
        raison = (f'Remplacé par {ref}' if ref
                  else 'Devis archivé : il ne se modifie plus')
        return {'modifiable': False, 'raison_non_modifiable': raison,
                'revision_possible': False}
    if statut in GESTES[geste]:
        return {'modifiable': True, 'raison_non_modifiable': '',
                'revision_possible': revisable}
    if statut == 'accepte':
        raison = 'Devis accepté : révisez-le'
    elif statut in STATUTS_CLOS:
        raison = 'Révisez-le (nouvelle version)'
    else:
        # Statut ouvert mais geste plus étroit (aucun depuis QJR557 ; garde
        # défensive si la table se resserre un jour).
        raison = (f'Devis « {_libelle_statut(devis)} » : révisez-le pour '
                  'faire ce changement')
    return {'modifiable': False, 'raison_non_modifiable': raison,
            'revision_possible': revisable}


def est_modifiable(devis, geste=ENTETE):
    return verdict(devis, geste)['modifiable']


def exiger_modifiable(devis, geste):
    """Lève :class:`DevisNonModifiable` si ``geste`` n'est pas permis."""
    v = verdict(devis, geste)
    if not v['modifiable']:
        raise DevisNonModifiable(
            v['raison_non_modifiable'],
            statut=str(getattr(devis, 'statut', '') or ''),
            revision_possible=v['revision_possible'])
    return v


# ── ADEV7 (C-ADEV-002) — UNE VERSION REMPLACÉE EST HORS JEU ────────────────
#
# Distinct de la table d'ÉDITION ci-dessus : les gestes de CYCLE DE VIE
# (accepter, refuser, envoyer, relancer) ne lisent ici QUE la règle « version
# en jeu » — leurs propres conditions de statut restent à leurs sites
# (``accept_devis``, ``refuser``, ``mark_devis_sent``). Une V1 révisée
# (``is_active=False``) n'accepte AUCUN de ces gestes : la refuser émettait
# ``devis_refused`` et clôturait le lead alors que la V2 vit ; la renvoyer
# relançait le client sur une proposition caduque. Une seule règle, partagée
# avec la garde QJR520 de l'acceptation. Lecture seule (règle #4).

ACCEPTER = 'ACCEPTER'
REFUSER = 'REFUSER'
ENVOYER = 'ENVOYER'
RELANCER = 'RELANCER'
GESTES_CYCLE = frozenset({ACCEPTER, REFUSER, ENVOYER, RELANCER})
CODE_VERSION_REMPLACEE = 'version_remplacee'


def successeur_actif(devis):
    """VNT24 — ``{id, reference}`` de la TÊTE de chaîne : le devis au bout de
    ``superseded_by`` (jamais ``version_parent``, partagé avec variantes et
    gammes) ; ``None`` sans successeur. V1 → V2 → V3 : V1 et V2 désignent V3."""
    from apps.ventes.models import Devis
    pk, tete, vus = getattr(devis, 'superseded_by_id', None), None, set()
    while pk and pk not in vus:
        vus.add(pk)
        ligne = (Devis.objects.filter(pk=pk, company_id=devis.company_id)
                 .values('id', 'reference', 'superseded_by_id').first())
        if ligne is None:
            break
        tete = {'id': ligne['id'], 'reference': ligne['reference']}
        pk = ligne['superseded_by_id']
    return tete


def message_version_remplacee(devis, successeur=None):
    """Le message unique d'une version hors jeu (repris de QJR520) ; il
    nomme la TÊTE de chaîne (VNT24)."""
    successeur = successeur or successeur_actif(devis)
    ref = successeur['reference'] if successeur else None
    if ref:
        return f'Cette proposition a été remplacée par {ref}.'
    return "Cette proposition n'est plus active."


def geste_cycle_permis(devis, geste):
    """``(permis, message)`` — un geste de cycle de vie sur ce devis est-il
    permis au regard de la version en jeu ? ``message`` vaut ``''`` quand
    permis."""
    if geste not in GESTES_CYCLE:
        raise ValueError(f'Geste de cycle de vie inconnu : {geste!r}.')
    if not bool(getattr(devis, 'is_active', True)):
        return False, message_version_remplacee(devis)
    return True, ''


def corps_version_remplacee(devis, detail=None):
    """LE corps 409 ``{detail, code, successeur}`` (contrats
    ``devis_refuser.json`` / ``devis_prix_negocie.json``) — repris tel quel
    par accepter, réviser, refuser et envoyer (VNT24). ``successeur`` =
    ``{id, reference}`` de la tête de chaîne, ``None`` pour un archivé."""
    successeur = successeur_actif(devis)
    return {'detail': detail or message_version_remplacee(devis, successeur),
            'code': CODE_VERSION_REMPLACEE, 'successeur': successeur}


# ── VNT25 — LE GESTE ÉCHÉANCIER (brouillon / envoyé / ACCEPTÉ) ─────────────
#
# D-VNT-3 : la valeur d'acompte tapée écrit l'échéancier du devis, même
# accepté. Règle (AGNR12 étendue) : une tranche COUVERTE par une facture
# (émise ; brouillon aussi par défaut) reste inchangée ; Σ des tranches NON
# dernières ≤ prix convenu et un acompte ≥ prix convenu est refusé ; la
# DERNIÈRE vaut le reste (en MAD hors tout-%) ; tout en % ⇒ total 100.
# 15 000 MAD + 60 % (29 400) = 44 400 ≤ 49 000 : permis (« Σ des valeurs
# déclarées ≤ TTC » refusait 49 300). Le statut n'est jamais écrit (règle #4).

CODE_SOMME_INVALIDE = 'somme_invalide'
CODE_TRANCHE_FACTUREE = 'tranche_facturee'
CODE_ECHEANCIER_INVALIDE = 'echeancier_invalide'
_DETAIL_SOMME = 'Les tranches ne totalisent pas le prix convenu.'


class EcheancierRefuse(Exception):
    """Refus du geste ÉCHÉANCIER : ``corps()`` = ``{detail, code[, tranche]}``
    (contrat ``devis_echeancier.json``) ; ``status`` = 400 ou 409."""

    def __init__(self, detail, *, code, status=400, tranche=None):
        super().__init__(detail)
        self.detail, self.code, self.status = detail, code, status
        self.tranche = tranche

    def corps(self):
        corps = {'detail': self.detail, 'code': self.code}
        if self.tranche is not None:
            corps['tranche'] = self.tranche
        return corps


def _entree_stockee(entree):
    """Une tranche du contrat ``{cle, libelle, unite, valeur}`` sous la forme
    stockée ``{type, libelle, unite, pct_or_montant}`` (le reste intouché)."""
    if not isinstance(entree, dict) or 'pct_or_montant' in entree \
            or 'valeur' not in entree:
        return entree
    sortie = {k: v for k, v in entree.items() if k not in ('cle', 'valeur')}
    sortie['pct_or_montant'] = entree['valeur']
    if entree.get('cle') and not sortie.get('type'):
        sortie['type'] = str(entree['cle']).split('#')[0]
    return sortie


def regle_somme_vente(tranches, prix_convenu):
    """PURE — ``(montants TTC des tranches NON dernières, reste de la
    dernière)`` en ``Decimal`` ; lève :class:`EcheancierRefuse`
    ``somme_invalide``. Tout en % : total 100 (AGNR12) ; toujours Σ des non
    dernières ≤ prix convenu et un acompte < prix convenu."""
    from decimal import Decimal, ROUND_HALF_UP

    from apps.ventes.utils.echeancier import (
        UNITE_MONTANT, UNITE_PCT, EcheancierInvalide, controler_somme_echeancier)
    prix = Decimal(str(prix_convenu))
    if not tranches:
        raise EcheancierRefuse(_DETAIL_SOMME, code=CODE_SOMME_INVALIDE)
    if all(t['unite'] == UNITE_PCT for t in tranches):
        try:
            controler_somme_echeancier(None, tranches)
        except EcheancierInvalide as exc:
            raise EcheancierRefuse(str(exc), code=CODE_SOMME_INVALIDE)
    montants = [(Decimal(str(t['valeur'])) if t['unite'] == UNITE_MONTANT
                 else prix * Decimal(str(t['valeur'])) / 100).quantize(
                     Decimal('0.01'), rounding=ROUND_HALF_UP)
                for t in tranches[:-1]]
    total = sum(montants, Decimal('0'))
    if total > prix or (montants and montants[0] >= prix):
        raise EcheancierRefuse(_DETAIL_SOMME, code=CODE_SOMME_INVALIDE)
    return montants, prix - total


def _exiger_couvertes_inchangees(plan, tranches, figer_brouillons):
    """409 ``tranche_facturee`` si une tranche couverte (émise ; brouillon
    quand ``figer_brouillons``) disparaît ou change (unité, valeur, libellé)."""
    from decimal import Decimal

    from apps.ventes.utils.echeancier import cles_tranches
    neuves = dict(zip(cles_tranches(tranches), tranches))
    figes = ('emise', 'brouillon') if figer_brouillons else ('emise',)
    for t in plan['tranches']:
        n = neuves.get(t['cle'])
        if t['statut'] not in figes or (
                n is not None and n['unite'] == t['unite']
                and n['libelle'] == t['libelle']
                and Decimal(str(n['valeur'])) == Decimal(str(t['valeur']))):
            continue
        raise EcheancierRefuse(
            f"La tranche « {t['libelle']} » est déjà facturée : elle ne peut "
            'plus être modifiée.', code=CODE_TRANCHE_FACTUREE, status=409,
            tranche={'cle': t['cle'], 'libelle': t['libelle']})


def controler_echeancier_vente(devis, entries, *, figer_brouillons=True):
    """VNT25 — LE contrôle du geste ÉCHÉANCIER (lecture seule). Rend les
    entrées À ÉCRIRE dans ``Devis.echeancier`` (forme stockée ; hors tout-%
    la dernière devient le reste en MAD). Lève :class:`DevisNonModifiable`
    (statut ou version hors jeu) ou :class:`EcheancierRefuse` (400
    ``echeancier_invalide`` / ``somme_invalide``, 409 ``tranche_facturee``).
    ``figer_brouillons=False`` : l'écrivain d'acompte (VNT28) qui édite son
    propre brouillon dans le même geste. Sur un accepté, l'écrivain trace par
    ``consigner_correction_apres_envoi(..., apres_acceptation=True)``."""
    from apps.ventes.utils.echeancier import (
        UNITE_MONTANT, UNITE_PCT, EcheancierInvalide, valider_echeancier)
    from apps.ventes.vente_facturation import plan_facturation
    exiger_modifiable(devis, ECHEANCIER)
    entrees = [_entree_stockee(e) for e in (entries or [])]
    try:
        tranches = valider_echeancier(entrees, controler_somme=False)
    except EcheancierInvalide as exc:
        raise EcheancierRefuse(str(exc), code=CODE_ECHEANCIER_INVALIDE)
    plan = plan_facturation(devis)
    _montants, reste = regle_somme_vente(tranches, plan['prix_convenu_ttc'])
    if any(t['unite'] != UNITE_PCT for t in tranches):
        entrees[-1] = dict(entrees[-1], pct_or_montant=float(reste),
                           unite=UNITE_MONTANT)
        tranches[-1] = dict(tranches[-1], valeur=float(reste),
                            unite=UNITE_MONTANT)
    _exiger_couvertes_inchangees(plan, tranches, figer_brouillons)
    return entrees


# ── QJR518 — UNE CORRECTION APRÈS ENVOI EST TRACÉE À UN SEUL POINT ─────────
#
# D-QJR5-1 : un devis ENVOYÉ se corrige SUR PLACE — même référence, même lien
# public, statut « envoyé » intouché. Mais l'état que le client a vu ne doit
# pas disparaître (replace-lines recrée les lignes, nouveaux ids), et la
# correction doit se voir : chatter du devis ET du lead, « Document mis à jour
# le … » sur la page publique (``etude_params.resync_apres_envoi``).
#
# LE PATRON, À CHAQUE SITE D'ÉCRITURE (pipeline MODE_ECRIRE / RECONCILIER,
# perform_update, etude-params, overrides, LigneDevisViewSet,
# catalogue_events) :
#
#     avant = debut_de_geste_devis(devis, user)   # AVANT la 1re écriture
#     ... écritures ...
#     fin_de_geste_devis(devis, user, avant=avant, objet='…')
#
# ``debut`` ne fait rien hors ENVOYÉ (rend ``None``) ; sur un envoyé il prend
# l'instantané (dédoublonné : un contenu identique au dernier n'en crée pas un
# second) et rend l'empreinte VISIBLE. ``fin`` compare : SEULEMENT si un
# contenu visible a changé, ``consigner_correction_apres_envoi`` écrit la
# trace. Aucun événement core ici (``devis_corrige_apres_envoi`` relève de
# QJR660). Le statut n'est JAMAIS écrit (règle #4).

#: Les champs d'une ligne que le client voit (jamais ``prix_achat``, jamais
#: l'id — replace-lines recrée les lignes, un id neuf n'est pas un changement).
_CHAMPS_LIGNE_VISIBLES = (
    'type_ligne', 'produit_id', 'designation', 'quantite', 'prix_unitaire',
    'remise', 'taux_tva', 'optionnelle', 'variante', 'groupe_index',
    'groupe_label',
)
#: L'en-tête CLIENT (ce que le PDF / la proposition impriment).
_CHAMPS_ENTETE_VISIBLES = (
    'client_id', 'date_validite', 'taux_tva', 'remise_globale', 'echeancier',
    'acompte_pct', 'acompte_montant',
)
#: ADEV18 — nom PUBLIC de la même liste : l'instantané restaurable
#: (``historique_config.configuration_devis_contenu``) la lit pour porter
#: chaque champ d'en-tête que l'empreinte compare — une seule source.
CHAMPS_ENTETE_VISIBLES = _CHAMPS_ENTETE_VISIBLES
_LIBELLES = {
    'lignes': 'lignes',
    'entete': 'en-tête',
    'note': 'note',
    'option': 'option recommandée',
    'conception': 'conception',
}
#: QJR557 — les gestes NOMMÉS dans le chatter (« corrigé après envoi :
#: calepinage (lignes) »). Les autres objets gardent le résumé seul.
_OBJETS_NOMMES = {
    'calepinage': 'calepinage',
    'taille': "taille d'offre",
    # ADEV19 — l'option activée par le CLIENT sur sa page publique.
    'option client': 'option client',
}


def empreinte_visible(devis):
    """Ce que le CLIENT voit de ce devis, relu en BASE (jamais l'instance en
    mémoire, qui peut être périmée ou déjà mutée) : ``{lignes, entete, note,
    option, conception}``."""
    from apps.ventes.models import Devis, LigneDevis

    ligne_devis = (Devis.objects.filter(pk=devis.pk)
                   .values(*_CHAMPS_ENTETE_VISIBLES, 'note', 'etude_params',
                           'layout_hash')
                   .first()) or {}
    # ATOT20 — une ligne sans taux (« Vide = taux global du devis ») et la
    # même ligne réécrite avec le taux du DEVIS sont le MÊME contenu visible :
    # le taux comparé est le taux EFFECTIF, sinon réenregistrer à l'identique
    # une ligne ancienne d'un envoyé tracerait une fausse correction.
    i_taux = _CHAMPS_LIGNE_VISIBLES.index('taux_tva')
    taux_devis = ligne_devis.get('taux_tva')

    def _visible(ligne):
        valeurs = list(ligne)
        if valeurs[i_taux] is None:
            valeurs[i_taux] = taux_devis
        return tuple(str(v) if v is not None else None for v in valeurs)

    lignes = [
        _visible(ligne)
        for ligne in LigneDevis.objects.filter(devis_id=devis.pk)
        .order_by('ordre', 'id').values_list(*_CHAMPS_LIGNE_VISIBLES)
    ]
    etude = ligne_devis.get('etude_params') or {}
    if not isinstance(etude, dict):
        etude = {}
    return {
        'lignes': lignes,
        'entete': tuple(str(ligne_devis.get(c)) for c in
                        _CHAMPS_ENTETE_VISIBLES),
        'note': (ligne_devis.get('note') or '').strip(),
        'option': str(etude.get('recommended_option') or ''),
        # ACAL41 (C-ACAL-090, D-ACAL-21) — la CONCEPTION imprimée : l'empreinte
        # « imprimée » du layout (``geometrie.layout_hash`` étendue par ACAL40 :
        # pans, surfaces de pose, exclusions, module, batterie, ombrage dessiné,
        # horizon) relue en base. Une correction d'un ENVOYÉ qui ne déplace que
        # des panneaux ou ne retouche que l'ombrage est ainsi tracée.
        'conception': ligne_devis.get('layout_hash') or '',
    }


#: ADEV96 — les chiffres de l'étude C&I SCELLÉS (projection ``chiffres_cles``
#: de ``quote_engine/ci/synthese``, celle que lisent la page et le PDF) :
#: kWc, production, consommation, autoconsommation, couverture, économie de
#: l'année 1 et sa base, retour, revente, « sous réserve ».
CLES_CHIFFRES_SCELLES = (
    'kwc', 'production_kwh_an', 'conso_kwh_an', 'taux_autoconso_pct',
    'taux_couverture_pct', 'economie_annuelle_mad', 'base_economie',
    'payback_ans', 'revente_kwh_an', 'revente_mad_an', 'sous_reserve',
)


def synthese_ci_lue(devis, link=None):
    """ADEV96 — la ``synthese_ci`` que la page ``/proposition`` montre : MÊME
    fonction que le PDF, sur la charge moteur assainie (``_strip_confidential
    _deep``) ; argent retiré quand la section « économies » n'est pas servie
    sur ``link``. ``None`` hors commercial / industriel (sans rendu moteur).
    Point de sauvegarde : appelée DANS la transaction d'acceptation, un
    incident de lecture ne la rend jamais invalide (``None``, journalisé)."""
    mode = str(getattr(devis, 'mode_installation', '') or '').strip().lower()
    if devis is None or mode not in ('commercial', 'industriel'):
        return None
    from django.db import transaction
    from apps.ventes.public.noyau import _strip_confidential_deep
    from apps.ventes.public.payload_economie import _sans_internes_bancables
    from apps.ventes.quote_engine.builder import build_quote_data
    from apps.ventes.quote_engine.ci.synthese import synthese_ci
    opts = {'pdf_mode': 'full'}
    if (getattr(link, 'token', '') or '').strip():
        opts['share_token'] = link.token.strip()
    try:
        with transaction.atomic():
            # Les MÊMES étapes que ``proposal_data`` avant sa ``synthese_ci``.
            synthese = synthese_ci(_sans_internes_bancables(
                _strip_confidential_deep(build_quote_data(devis, opts))))
    except Exception:  # noqa: BLE001 — sceau sans étude plutôt qu'une signature cassée (D-ENF22-BLE001)
        logger.warning('ADEV96 : synthèse C&I illisible (devis %s)',
                       getattr(devis, 'reference', '?'), exc_info=True)
        return None
    if synthese is not None and link is not None \
            and not link.section_servie('economies'):
        synthese = {cle: val for cle, val in synthese.items() if cle != 'argent'}
    return synthese


def figures_etude_scellees(synthese):
    """ADEV96 — ce que le sceau couvre de l'étude C&I : les chiffres de
    :data:`CLES_CHIFFRES_SCELLES`, les indicateurs (retour, TRI et son
    horizon), l'économie de l'année 1 HT/TTC, les hypothèses chiffrées du bloc
    argent et les CLÉS des hypothèses imprimées. ``None`` sans synthèse (hors
    C&I) : le contenu scellé est alors celui d'avant, à l'octet."""
    if not isinstance(synthese, dict):
        return None
    from apps.ventes.quote_engine.ci.synthese import chiffres_cles
    chiffres = chiffres_cles(synthese)
    argent = synthese.get('argent') if isinstance(synthese.get('argent'), dict) else {}
    eco = argent.get('economie_annee1') if isinstance(
        argent.get('economie_annee1'), dict) else {}
    return {
        'chiffres': {cle: chiffres.get(cle) for cle in CLES_CHIFFRES_SCELLES},
        'indicateurs': argent.get('indicateurs') or {},
        'economie_annee1': {'ht': eco.get('total_mad'),
                            'ttc': eco.get('total_mad_ttc')},
        'hypotheses_argent': argent.get('hypotheses') or {},
        'hypotheses': sorted(str(h.get('cle')) for h in synthese.get(
            'hypotheses') or [] if isinstance(h, dict)),
    }


def _est_envoye(devis):
    from apps.ventes.models import Devis
    statut = (Devis.objects.filter(pk=getattr(devis, 'pk', None))
              .values_list('statut', flat=True).first())
    return statut == Devis.Statut.ENVOYE


def debut_de_geste_devis(devis, user=None):
    """AVANT la première écriture d'un geste. Hors ENVOYÉ → ``None`` (rien à
    tracer). Sur un envoyé : instantané de l'état vu par le client
    (dédoublonné) + l'empreinte visible, à rendre à :func:`fin_de_geste_devis`.
    Ne lève jamais : la trace ne bloque pas une écriture."""
    if devis is None or getattr(devis, 'pk', None) is None:
        return None
    try:
        if not _est_envoye(devis):
            return None
        from apps.ventes.models import Devis
        from apps.ventes.domain.historique_config import capturer_configuration_devis
        frais = Devis.objects.get(pk=devis.pk)
        capturer_configuration_devis(frais, user=user, avant_correction=True)
        return empreinte_visible(frais)
    except Exception:  # noqa: BLE001 — jamais bloquant (D-ENF22-BLE001)
        logger.warning("modifiabilite.debut_de_geste_devis : erreur ignorée (mode dégradé)", exc_info=True)
        import logging
        logging.getLogger(__name__).exception(
            'QJR518 : début de geste ignoré (devis %s)', devis.pk)
        return None


def fin_de_geste_devis(devis, user=None, *, avant=None, objet=''):
    """APRÈS les écritures d'un geste. Si ``avant`` (l'empreinte de
    :func:`debut_de_geste_devis`) diffère de l'empreinte courante, consigne
    la correction ; sinon rien (un enregistrement sans changement réel
    n'écrit ni chatter ni marqueur). Rend l'activité créée ou ``None``."""
    if avant is None or devis is None:
        return None
    try:
        if not _est_envoye(devis):
            return None
        apres = empreinte_visible(devis)
        changes = [cle for cle in ('lignes', 'entete', 'note', 'option',
                                   'conception')
                   if avant.get(cle) != apres.get(cle)]
        if not changes:
            return None
        resume = ', '.join(_LIBELLES[c] for c in changes)
        if objet in _OBJETS_NOMMES:
            resume = '%s (%s)' % (_OBJETS_NOMMES[objet], resume)
        return consigner_correction_apres_envoi(
            devis, user=user, objet=objet, resume=resume)
    except Exception:  # noqa: BLE001 — jamais bloquant (D-ENF22-BLE001)
        logger.warning("modifiabilite.fin_de_geste_devis : erreur ignorée (mode dégradé)", exc_info=True)
        import logging
        logging.getLogger(__name__).exception(
            'QJR518 : fin de geste ignorée (devis %s)', devis.pk)
        return None


def consigner_correction_apres_envoi(devis, *, user=None, objet='',
                                     resume='', apres_acceptation=False):
    """La TRACE d'une correction après envoi, en un seul point :

    * une ``DevisActivity`` « Corrigé après envoi — <resume> » ;
    * ``etude_params.resync_apres_envoi = {'date': <iso>}`` sous son
      propriétaire (CALEPINAGE, ``etude_schema``), écrit sur une RELECTURE du
      devis (l'instance de l'appelant peut porter des études périmées) ;
    * un reflet best-effort sur le chatter du lead
      (``crm.services.noter_devis_corrige``).

    Référence, jeton et statut inchangés (règle #4). No-op hors ENVOYÉ —
    VNT25 : ``apres_acceptation=True`` trace aussi un ACCEPTÉ (geste
    ÉCHÉANCIER) : « Corrigé après acceptation — <resume> », clauses signées
    jamais re-gelées."""
    from django.utils import timezone

    from apps.ventes import activity
    from apps.ventes.models import Devis, DevisActivity
    from apps.ventes.domain.etude_schema import CALEPINAGE, ecrire

    frais = Devis.objects.select_related('lead').filter(pk=devis.pk).first()
    statuts = ((Devis.Statut.ENVOYE, Devis.Statut.ACCEPTE)
               if apres_acceptation else (Devis.Statut.ENVOYE,))
    if frais is None or frais.statut not in statuts:
        return None
    libelle = resume or objet or 'contenu'
    accepte = frais.statut == Devis.Statut.ACCEPTE
    entree = (DevisActivity.objects.create(
        company=frais.company, devis=frais, user=user,
        kind=DevisActivity.Kind.MODIFICATION,
        field='correction_apres_acceptation',
        field_label='Corrigé après acceptation', new_value=libelle,
        body=f'Corrigé après acceptation — {libelle}.') if accepte else
        activity.log_devis_correction_apres_envoi(frais, user, libelle))
    ecrire(frais, proprietaire=CALEPINAGE,
           resync_apres_envoi={'date': timezone.now().isoformat()})
    # L'instance de l'appelant suit (sa réponse sérialise le marqueur) : on ne
    # recopie QUE la clé du marqueur, jamais le bloc (QJR105).
    if isinstance(devis.etude_params, dict):
        devis.etude_params['resync_apres_envoi'] = (
            frais.etude_params or {}).get('resync_apres_envoi')
    # QJR668 — les clauses/CGV gelées à l'envoi sont RE-gelées sur le contenu
    # corrigé (le PDF les imprime telles quelles) ; l'instance suit.
    if not accepte:
        from apps.ventes.domain.envoi import figer_clauses_devis
        figer_clauses_devis(frais)
        devis.clauses_appliquees = frais.clauses_appliquees
    if frais.lead_id:
        try:
            from apps.crm.services import noter_devis_corrige
            noter_devis_corrige(frais.reference, frais.lead, (
                f'{libelle}, après acceptation' if accepte else libelle))
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant (D-ENF22-BLE001)
            logger.warning(
                "modifiabilite.consigner_correction_apres_envoi : erreur ignorée (mode dégradé)", exc_info=True)
    return entree
