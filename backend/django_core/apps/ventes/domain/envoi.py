"""Le geste d'envoi du devis (SPL264, déplacé de ``domain/cycle_vie.py``).

Clauses CGV (contexte, clauses particulières ``cpq``, gel à l'envoi —
QJR668), ``mark_devis_sent`` (LE chemin brouillon → envoyé, règle #4 :
déplacé verbatim, aucun statut ne change) et validité du devis
(``poser_validite_devis``, CAD57 ``jours_validite_societe`` /
``date_validite_credit``). Aucune dépendance interne : les lectures d'autres
modules restent des imports FONCTION-LOCAUX. Déplacement pur : corps
octet-identiques, prouvé par ``tests/golden/split_dm_envoi.json``.
"""
import logging

logger = logging.getLogger("apps.ventes.services")


def contexte_clauses_devis(devis):
    """NTCPQ11 — Contexte plat servant à évaluer les clauses/CGV dynamiques.

    Clés exposées : ``type_deal`` (= ``mode_installation``), ``montant``
    (= total TTC), ``total_ht``, ``total_ttc``, ``remise_globale``,
    ``puissance_kwc``, ``devise``. Aucun prix d'achat / aucune marge (donnée
    interne — jamais dans un texte destiné au client).

    QJR54 (29/08/2026) — LE MONTANT QUI CHOISIT LA TRANCHE EST LE **NET**. Ces
    clauses sont sélectionnées par tranche de montant PUIS IMPRIMÉES sur le PDF
    client : alimenter le moteur avec un total non remisé pouvait figer un
    devis remisé avec le jeu de CGV d'une tranche SUPÉRIEURE. La lecture passe
    donc par la vue NET NOMMÉE de ``domain.argent`` — remise globale honorée et
    option effective — au lieu de dépendre de ce que ``Devis.total_*`` veut
    dire ce mois-ci.
    """
    from decimal import Decimal, InvalidOperation

    from apps.ventes.domain.argent import Vue, totaux as totaux_argent

    # ERR-QAC-MULTIVILLA-TOTAL-XN — ``montant`` est le total ×N d'un devis
    # « N villas identiques » : le kWc du même contexte est celui du PROJET.
    from apps.ventes.selectors import puissance_kwc_projet
    try:
        kwc = float(puissance_kwc_projet(devis) or 0)
    except (TypeError, ValueError, InvalidOperation):
        kwc = 0.0
    try:
        vue = totaux_argent(devis, vue=Vue.NET)
        total_ht = float(vue.ht_net or 0)
        total_ttc = float(vue.ttc or 0)
    except (TypeError, ValueError, InvalidOperation):
        total_ht = total_ttc = 0.0
    return {
        'type_deal': devis.mode_installation or '',
        'mode_installation': devis.mode_installation or '',
        'montant': total_ttc,
        'total_ht': total_ht,
        'total_ttc': total_ttc,
        'remise_globale': float(devis.remise_globale or Decimal('0')),
        'puissance_kwc': kwc,
        'devise': devis.devise or 'MAD',
    }


#: ERR-QJR668 — type de l'entrée de ``Devis.clauses_appliquees`` qui porte les
#: puces CGV DE LA SOCIÉTÉ gelées à l'envoi. Ce n'est PAS une clause
#: particulière : ``builder`` l'en écarte et la rend dans le bloc CGV standard
#: (``doc_texts['cgv_bullets']``) — jamais deux fois.
TYPE_CGV_GELEES = 'cgv_gelees'

#: ADEV30 (C-ADEV-041, D-ASTK-1) — type de l'entrée qui porte le BARÈME des
#: forfaits au panneau (``prix_fixe_ht`` / ``prix_par_panneau_ht`` par
#: produit) gelé à l'envoi : un envoyé dont le nombre de panneaux change est
#: re-tarifé sur CE barème, jamais sur celui du jour. Entrée INTERNE : jamais
#: imprimée comme clause particulière.
TYPE_BAREMES_GELES = 'baremes_forfaits_geles'

#: Les entrées de ``Devis.clauses_appliquees`` qui ne sont PAS des clauses
#: particulières ``cpq`` (gels internes) : ``builder`` ne les imprime pas dans
#: le bloc « Clauses particulières », et un re-gel cpq ne les efface jamais.
#: APDF20 (C-APDF-006) — type de l'entrée qui porte l'ENSEMBLE des textes
#: contractuels du devis gelés à l'envoi (``DocumentTemplates.as_doc_texts``
#: fusionné au défaut du moteur, une clé par ``DEVIS_TEXT_KEYS``) et la
#: ``version`` des modèles de documents. Contrat figé par
#: ``tests/test_apdf_gel_textes.py`` (lu par APDF14) :
#: ``{'type': 'doc_texts_geles', 'textes': {<DEVIS_TEXT_KEYS>}, 'version': int}``.
TYPE_DOC_TEXTS_GELES = 'doc_texts_geles'

TYPES_GELS_INTERNES = frozenset(
    {TYPE_CGV_GELEES, TYPE_BAREMES_GELES, TYPE_DOC_TEXTS_GELES})


def est_gel_interne(entree):
    """Vrai si ``entree`` (de ``clauses_appliquees``) est un gel INTERNE et
    non une clause particulière à imprimer."""
    return isinstance(entree, dict) and entree.get('type') in TYPES_GELS_INTERNES


def _decimal_texte(valeur):
    return None if valeur is None else str(valeur)


def figer_baremes_forfaits(devis):
    """ADEV30 — GÈLE, au passage brouillon → envoyé (appelé par
    :func:`mark_devis_sent` seulement, donc une fois par envoi), le barème de
    chaque forfait au panneau porté par les lignes du devis
    (``{produit_id: {prix_fixe_ht, prix_par_panneau_ht}}``). Une entrée
    héritée (copie d'une V1 par révision/clonage) est REMPLACÉE : le brouillon
    suivait le barème du jour, c'est celui-là que le client reçoit. Les
    corrections sur place d'un envoyé ne le rappellent jamais. Rend ``True``
    quand l'entrée a été (ré)écrite. Ne touche jamais au statut (règle #4)."""
    from apps.ventes.domain.catalogue import porte_bareme_par_panneau
    from apps.ventes.models import LigneDevis

    existant = [c for c in (devis.clauses_appliquees or [])
                if not (isinstance(c, dict)
                        and c.get('type') == TYPE_BAREMES_GELES)]
    produits = {}
    lignes = (LigneDevis.objects.filter(devis_id=devis.pk, type_ligne='produit')
              .select_related('produit'))
    for ligne in lignes:
        produit = ligne.produit
        if produit is None or not porte_bareme_par_panneau(produit):
            continue
        produits[str(produit.pk)] = {
            'prix_fixe_ht': _decimal_texte(produit.prix_fixe_ht),
            'prix_par_panneau_ht': _decimal_texte(produit.prix_par_panneau_ht),
        }
    if not produits:
        if existant != list(devis.clauses_appliquees or []):
            devis.clauses_appliquees = existant
            devis.save(update_fields=['clauses_appliquees'])
            return True
        return False
    devis.clauses_appliquees = existant + [
        {'type': TYPE_BAREMES_GELES, 'produits': produits}]
    devis.save(update_fields=['clauses_appliquees'])
    return True


def baremes_forfaits_geles(devis):
    """ADEV30 — le barème gelé à l'envoi ``{produit_id(str): {...}}``, ou
    ``{}`` (devis envoyé avant ce gel, ou brouillon)."""
    for c in (getattr(devis, 'clauses_appliquees', None) or []):
        if isinstance(c, dict) and c.get('type') == TYPE_BAREMES_GELES:
            produits = c.get('produits')
            return produits if isinstance(produits, dict) else {}
    return {}


def doc_texts_a_geler(company):
    """APDF20 — l'entrée ``doc_texts_geles`` de ``company`` : les textes
    contractuels EFFECTIFS (défaut du moteur, surchargé par chaque texte non
    vide de la société — même fusion que le rendu) et la version des modèles.
    Une société sans aucun texte personnalisé gèle les textes PAR DÉFAUT."""
    import copy

    from apps.parametres.models_documents import (
        DEVIS_TEXT_KEYS, DocumentTemplates)
    from apps.ventes.quote_engine.generate_devis_premium import (
        DEFAULT_DOC_TEXTS)

    modeles = DocumentTemplates.get(company=company)
    surcharges = modeles.as_doc_texts()
    textes = {}
    for cle in DEVIS_TEXT_KEYS:
        valeur = surcharges.get(cle, DEFAULT_DOC_TEXTS.get(cle, ''))
        textes[cle] = copy.deepcopy(valeur)
    return {'type': TYPE_DOC_TEXTS_GELES, 'textes': textes,
            'version': int(modeles.version or 1)}


def clauses_applicables_devis(devis):
    """QJR668 — les clauses PARTICULIÈRES du catalogue ``cpq`` qui s'appliquent
    à ce devis (``[{clause_id, nom, corps_texte, type_deal, ordre}]``), ou
    ``None`` quand AUCUN catalogue n'est disponible.

    Le catalogue NTCPQ11 vit dans l'app ``cpq`` (``selectors.clauses_applicables``
    évalue chaque clause contre :func:`contexte_clauses_devis`). Tant que
    ``cpq`` est PARQUÉE (MVP solaire, SOLMVP), le module n'existe pas : la
    fonction rend ``None`` et le gel n'écrit aucune clause particulière — un
    snapshot déjà posé n'est jamais effacé faute de source. Import dynamique :
    aucune arête statique ventes → cpq. Les CGV de la société ne passent
    PAS par ici (voir :func:`figer_clauses_devis`)."""
    import importlib

    try:
        source = importlib.import_module('apps.cpq.selectors')
        clauses_applicables = source.clauses_applicables
    except (ImportError, AttributeError):
        return None
    clauses = clauses_applicables(
        company=devis.company, context=contexte_clauses_devis(devis))
    return [dict(c) for c in (clauses or []) if isinstance(c, dict)]


def figer_clauses_devis(devis):
    """QJR668 (décision fondateur 01/10/2026) — GÈLE sur
    ``Devis.clauses_appliquees`` : (1) les clauses PARTICULIÈRES ``cpq``
    (bloc « Clauses particulières »), et (2) ERR-QJR668 — les puces CGV de la
    SOCIÉTÉ (``DocumentTemplates.cgv_bullets``, marqueurs conservés), dans UNE
    entrée ``{'type': 'cgv_gelees', 'bullets': [...]}`` que ``builder`` lit
    pour le bloc CGV STANDARD du PDF — jamais pour « Clauses particulières ».

    Appelé sur le chemin d'envoi (:func:`mark_devis_sent`) puis RE-appelé à
    chaque correction sur place d'un envoyé
    (``modifiabilite.consigner_correction_apres_envoi``, QJR518). Les clauses
    cpq suivent le contenu corrigé ; les CGV société sont gelées UNE fois (ce
    que le client a reçu) : un texte édité après l'envoi ne les change pas.
    Sans source, rien n'est écrit ni effacé. Rend ``True`` quand le snapshot a
    été (ré)écrit. Ne touche jamais au statut (règle #4)."""
    from apps.parametres.selectors import cgv_mode_societe

    existant = list(devis.clauses_appliquees or [])

    def _est_cgv(c):
        return isinstance(c, dict) and c.get('type') == TYPE_CGV_GELEES

    def _est_doc_texts(c):
        return isinstance(c, dict) and c.get('type') == TYPE_DOC_TEXTS_GELES

    cgv = [c for c in existant if _est_cgv(c)]
    doc_texts = [c for c in existant if _est_doc_texts(c)]
    # ADEV30 — les autres gels internes (barème des forfaits) sont conservés
    # tels quels : un re-gel cpq ne les efface jamais.
    autres_gels = [c for c in existant
                   if est_gel_interne(c) and not _est_cgv(c)
                   and not _est_doc_texts(c)]
    particulieres = [c for c in existant if not est_gel_interne(c)]
    if not cgv:
        # CIQ218 — un devis C&I gèle la variante de SON mode (sinon l'autre
        # variante C&I) ; sans variante, les puces société comme hier.
        source = cgv_mode_societe(devis.company, devis.mode_installation)
        if source:
            entree = {'type': TYPE_CGV_GELEES, 'bullets': source['bullets']}
            if source.get('mode'):
                entree.update(mode=source['mode'], titre=source['titre'])
            cgv = [entree]
    if not doc_texts:
        # APDF20 — les textes contractuels sont gelés UNE fois, même sans
        # personnalisation (les défauts) ; un texte édité ensuite dans
        # Paramètres ne les change pas. Une correction sur place d'un envoyé
        # d'avant ce gel le pose.
        doc_texts = [doc_texts_a_geler(devis.company)]
    cpq = clauses_applicables_devis(devis)
    if cpq is not None:
        particulieres = cpq
    cible = particulieres + cgv + doc_texts + autres_gels
    if cible == existant or (not cible and not existant):
        return False
    devis.clauses_appliquees = cible
    devis.save(update_fields=['clauses_appliquees'])
    return True


def mark_devis_sent(*, devis, user=None):
    """U4 — flip a Devis to « envoyé » through the ONE status-change path.

    Called when a quote is shared with the client (e.g. the lead WhatsApp
    action builds a wa.me link). It is the single place that moves a quote
    document from « brouillon » to « envoyé » outside the viewset's own
    perform_update, so rule #4 status semantics + the chatter log are
    preserved (no raw ``.statut =`` write elsewhere).

    Behaviour:

    * a ``brouillon`` devis flips to ``envoye``, stamps ``date_envoi`` once,
      writes the « envoyé » chatter entry, and emits the ``devis_sent`` domain
      event so ``crm`` advances the lead funnel to QUOTE_SENT — without
      ventes importing crm directly (mirror of ``accept_devis``) ;
    * idempotent — an already-``envoye`` devis is returned unchanged (no second
      stamp, no second event, no duplicate chatter line) ;
    * NEVER regresses a further-along devis: ``accepte`` / ``refuse`` /
      ``expire`` are left exactly as-is (returned untouched).

    Returns the (possibly unchanged) Devis. Tenant scoping is the caller's
    responsibility — the devis is always passed already company-resolved.
    """
    from django.utils import timezone
    from apps.ventes.models import Devis
    from apps.ventes import activity
    from core.events import devis_sent

    # Already sent (or beyond): never re-stamp, never downgrade. Only a live
    # brouillon advances — accepté/refusé/expiré are terminal-or-further and
    # must stay put (the guard the test pins).
    if devis.statut != Devis.Statut.BROUILLON:
        return devis

    # ADEV7 — une version REMPLACÉE ou archivée (``is_active=False``) n'est
    # jamais marquée envoyée : aucun tampon, aucun ``devis_sent`` (funnel,
    # cadence). Les vues d'envoi renvoient 409 ``version_remplacee`` AVANT
    # d'arriver ici ; ce filet couvre les appelants internes (crm), sans
    # changer leur signature : le devis est rendu inchangé.
    from apps.ventes.domain.modifiabilite import ENVOYER, geste_cycle_permis
    if not geste_cycle_permis(devis, ENVOYER)[0]:
        return devis

    # QJR539 — FILET T17 (brouillon seulement) : chaque vue d'envoi appelle
    # déjà la garde AVANT ses effets ; ce filet couvre tout autre appelant.
    # Lève ``RemiseNonApprouvee`` — le devis reste brouillon.
    from apps.ventes.domain.tarification import exiger_approbation_remise
    exiger_approbation_remise(devis, user)

    ancien = devis.statut
    devis.statut = Devis.Statut.ENVOYE
    devis.date_envoi = timezone.now()
    devis.save(update_fields=['statut', 'date_envoi'])
    # QX23be — fige la marge interne au moment de l'envoi (manager-only).
    refresh_marge_snapshot(devis)
    # QJR668 — fige les clauses/CGV de l'affaire au moment de l'envoi.
    figer_clauses_devis(devis)
    # ADEV30 — fige le barème des forfaits au panneau (D-ASTK-1).
    figer_baremes_forfaits(devis)
    activity.log_devis_sent(devis, user)
    devis_sent.send(
        sender=Devis, devis=devis, user=user, ancien_statut=ancien)
    return devis


def poser_validite_devis(devis, date_validite):
    """VALID1 (fondateur 07/09/2026) — pose ``date_validite`` si VIDE.

    Appelée par ``apps.crm`` au DÉMARRAGE du plan après-devis : la
    proposition est valable jusqu'à la FIN du plan de suivi (la date de sa
    dernière touche — dérivée des cadences configurées par le fondateur,
    jamais un nombre inventé). Les messages WhatsApp « validité de la
    proposition » cessent ainsi d'omettre leur phrase. Une validité DÉJÀ
    posée (choix humain) n'est jamais écrasée. Renvoie True si posée."""
    if devis is None or getattr(devis, 'date_validite', None):
        return False
    if not date_validite:
        return False
    devis.date_validite = date_validite
    devis.save(update_fields=['date_validite'])
    _prolonger_liens(devis)
    return True


def _prolonger_liens(devis):
    """CIQ511 — une validité posée ou prolongée recule les liens publics
    vivants du devis (jamais raccourcis). Best-effort : un incident ici ne
    défait jamais l'écriture de la validité."""
    try:
        from apps.ventes.models import ShareLink
        ShareLink.prolonger_pour_devis(devis)
    except Exception:  # noqa: BLE001 — best-effort, journalisé
        logger.warning(
            'CIQ511 : liens non prolongés (devis #%s)',
            getattr(devis, 'pk', '?'), exc_info=True)


# ── CAD57 (21/09/2026) — validité d'un dossier FINANCÉ À CRÉDIT ────────────
#
# La validité du devis était posée sur la DERNIÈRE touche de la cadence de
# suivi, c'est-à-dire J+14 : le devis expirait le jour exact où le suivi
# s'arrête. Pour un PARTICULIER, la loi 31-08 (protection du consommateur)
# impose, une fois l'offre de crédit émise, 10 jours de réflexion PUIS 7 jours
# de rétractation avant déblocage des fonds — il ne peut pas, légalement,
# boucler dans la fenêtre qu'on lui annonce. Pour un PROFESSIONNEL (CIQ510),
# la loi 31-08 ne vise pas ses achats (art. 2 : besoins non professionnels) :
# c'est le délai d'instruction de la banque ou de l'organisme, ou l'attente
# d'un accord déclarée, qui allonge la validité — sans conclusion juridique
# (l'avis d'un juriste reste une tâche manuelle).
#
# DÉCISION FONDATEUR du 21/09/2026 : validité distincte et plus longue pour un
# dossier financé à crédit (J+30), J+14 (la fin du suivi) pour les autres.
# Le NOMBRE de jours n'est pas écrit ici : il vient du réglage société
# ``CompanyProfile.quote_validity_days`` — le MÊME que celui dont le PDF se
# sert déjà (``utils/expiry.date_expiration``), pour que les deux voix ne se
# contredisent jamais (CAD59).

def jours_validite_societe(company):
    """Le réglage société ``quote_validity_days``, en jours.

    Point d'entrée unique : ni le moteur de devis, ni le message WhatsApp, ni
    la cadence n'écrivent ce nombre en dur. Retombe sur le défaut DÉCLARÉ du
    champ (jamais un littéral choisi ici) quand le profil est illisible.
    """
    from apps.ventes.utils.expiry import _validity_days
    return _validity_days(company)


def date_validite_credit(devis, depart=None):
    """La date de validité d'un dossier FINANCÉ : ``depart`` + le réglage.

    ``depart`` est la date d'envoi (un ``date`` ou un ``datetime``) ; à défaut,
    la date de création du devis. ``None`` quand aucune des deux n'est
    connue — l'appelant garde alors la règle ordinaire plutôt que d'inventer
    une date.
    """
    import datetime as _dt

    if devis is None:
        return None
    base = depart or getattr(devis, 'date_envoi', None) \
        or getattr(devis, 'date_creation', None)
    if base is None:
        return None
    if isinstance(base, _dt.datetime):
        base = base.date()
    jours = jours_validite_societe(getattr(devis, 'company', None))
    return base + _dt.timedelta(days=jours)


def prolonger_validite_devis(devis, date_cible):
    """CIQ510 — porte la validité d'un devis ENVOYÉ à ``date_cible`` si elle
    est PLUS LOINTAINE que sa validité effective (``date_validite``, sinon le
    repli du PDF ``utils/expiry.date_expiration``).

    Jamais plus courte ; jamais sur un devis accepté, refusé, expiré ou
    brouillon ; aucun statut ne change (règle #4 : le moteur lit
    ``date_validite``). Rend la nouvelle date, ou ``None`` si rien n'a
    bougé."""
    from apps.ventes.models import Devis
    from apps.ventes.utils.expiry import date_expiration

    if devis is None or not date_cible:
        return None
    if getattr(devis, 'statut', None) != Devis.Statut.ENVOYE:
        return None
    actuelle = date_expiration(devis)
    if actuelle is not None and date_cible <= actuelle:
        return None
    devis.date_validite = date_cible
    devis.save(update_fields=['date_validite'])
    _prolonger_liens(devis)
    return date_cible


# ── PONTS M3 : noms hébergés ailleurs ────────────────────────────────────────
# Import EN BAS DE FICHIER (règle de ``domain/__init__.py``), vers le module qui
# PORTE le corps — jamais la façade.
from apps.ventes.domain.etudes import refresh_marge_snapshot  # noqa: E402
