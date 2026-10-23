"""QJR668 (décision fondateur 01/10/2026) — le bloc « Clauses particulières »
imprimé par TOUS les gabarits du devis (résidentiel, commercial, industriel,
legacy plein format et une page).

Source unique : ``data['clauses_cgv']`` posé par ``builder`` depuis le
snapshot ``Devis.clauses_appliquees`` (gelé à l'envoi, re-gelé à chaque
correction par ``domain/cycle_vie``). Le moteur ne fait que RENDRE : aucune
clause n'est choisie ni recalculée ici.

Les textes arrivent DÉJÀ échappés (``builder.echapper_textes_client`` pour
les gabarits maison, ``apply_quote_data`` pour le legacy) : rien n'est
ré-échappé. Sans clause → chaîne vide (document octet-identique).
"""

from decimal import Decimal

from . import i18n_labels
from .montants import regles_origine

#: AMOT81 — modes dont les puces CGV de REPLI sont au ton C&I : UNE puce
#: échéancier (N jalons), jamais les trois créneaux résidentiels ni « barème
#: ONEE/SRM ». Les puces saisies ou gelées par la société restent telles.
MODES_CI = ("commercial", "industriel")

#: APDF9 — le titre vit dans ``i18n_labels`` (clé ``clauses_particulieres``) ;
#: ``TITRE`` en reste la forme française.
TITRE = i18n_labels.libelle("clauses_particulieres", "fr")


def bloc_clauses_html(clauses, *, couleur_titre="#0f2a44",
                      couleur_texte="#334155", taille_pt="7.5", langue=None):
    """HTML compact des clauses gelées, ou ``""`` quand il n'y en a pas.

    APDF9 — ``langue`` choisit le titre (``i18n_labels``) ; absente : le
    français d'hier, octet pour octet."""
    lignes = []
    for c in clauses or []:
        if not isinstance(c, dict):
            continue
        nom = str(c.get("nom") or "").strip()
        corps = str(c.get("corps_texte") or "").strip()
        if not nom and not corps:
            continue
        tete = f"<b>{nom}</b>" + (" &#8212; " if nom and corps else "")
        lignes.append(f'<div style="margin-top:2px;">{tete}{corps}</div>')
    if not lignes:
        return ""
    return (
        f'<div class="clauses-cgv" style="margin-top:8px;font-size:{taille_pt}pt;'
        f'line-height:1.35;color:{couleur_texte};">'
        f'<div style="font-weight:700;color:{couleur_titre};'
        'text-transform:uppercase;letter-spacing:.8px;">'
        f'{i18n_labels.libelle("clauses_particulieres", langue)}</div>'
        f'{"".join(lignes)}</div>')


def cgv_bullets_defaut(langue=None, mode=None):
    """APDF10 — puces CGV PAR DÉFAUT dans la langue du document : fr →
    ``DEFAULT_DOC_TEXTS['cgv_bullets']`` (octet pour octet) ; en/ar → les clés
    ``cgv_*`` d'``i18n_labels``, mêmes marqueurs, mêmes pourcentages.

    APDF13 × AGR310 — un devis AGRICOLE ne cite aucun barème ONEE/SRM
    (« aucune mécanique résidentielle ») : la dernière puce par défaut
    (« Tarifs de référence ») est retirée pour ce mode, sur le PDF comme sur
    la page publique (même fonction)."""
    if i18n_labels.normaliser(langue) == "fr":
        puces = DEFAULT_DOC_TEXTS["cgv_bullets"]
    else:
        puces = ["{validite_offre}"] + [
            i18n_labels.libelle(cle, langue) for cle in (
                "cgv_acompte_commande", "cgv_reception_materiel",
                "cgv_mise_en_marche")] + [
            "{tva_note}", i18n_labels.libelle("cgv_tarifs_reference", langue)]
    if (mode or "").strip().lower() == "agricole":
        return puces[:-1]
    return puces


def _puces_cgv(bullets, langue, mode=None):
    """APDF10 — puces saisies (souveraines) ou, à défaut, celles du moteur
    dans la langue du document (et du mode, APDF13 × AGR310)."""
    if not bullets or bullets == DEFAULT_DOC_TEXTS["cgv_bullets"]:
        return cgv_bullets_defaut(langue, mode)
    return bullets


def _pct_nul(valeur):
    """AMOT19 — un pourcentage d'échéancier NUL (créneau absent) ?"""
    try:
        return float(valeur) == 0
    except (TypeError, ValueError):
        return False


def remplir_cgv_bullets(bullets, *, acompte, materiel, solde, tva_note,
                        valid_until, langue=None):
    """QJR668 — LA fonction qui remplit les cases des puces CGV.

    Substitue {acompte}/{materiel}/{solde}/{tva_note}/{validite_offre} et rend
    les puces NON VIDES, entités HTML conservées (le moteur ne les échappe
    pas). Une puce au gabarit illisible (case inconnue, accolade seule) est
    rendue telle quelle ; une puce vide après remplissage (échéance inconnue)
    est omise. Pure (aucun global) : le PDF (:func:`_cgv_bullets_html`) et la
    page publique de signature (``public_views._conditions_publiques``, via
    :func:`cgv_bullets_remplies`) passent par ELLE — jamais une seconde copie
    du remplissage."""
    out = []
    for raw in bullets or ():
        # AMOT19 — un créneau ABSENT de l'échéancier (deux tranches : matériel
        # à 0) n'est jamais imprimé « 0 % à la réception du matériel » : la
        # puce qui le porte est omise, comme les cases du « Devis final ».
        # Décision fondateur 08/10/2026 — devis envoyé avant AMOT19 : les puces
        # d'hier (rien d'omis).
        if ("{materiel}" in str(raw) and _pct_nul(materiel)
                and not regles_origine()):
            continue
        try:
            txt = raw.format(
                acompte=acompte, materiel=materiel, solde=solde,
                tva_note=tva_note,
                # M7 — échéance RÉELLE ; inconnue ⇒ chaîne vide ⇒ puce omise.
                validite_offre=(i18n_labels.libelle(
                    "cgv_validite_offre", langue).format(date=valid_until)
                    if valid_until else ""))
        except (KeyError, IndexError, ValueError):
            txt = raw
        if not str(txt).strip():
            continue
        out.append(txt)
    return out


def _pct_txt(valeur):
    try:
        return format(Decimal(str(valeur)).normalize(), "f")
    except (ArithmeticError, ValueError, TypeError):
        return str(valeur)


def puce_echeancier_ci(data, langue=None):
    """AMOT81 — « Échéancier de paiement : Commande : 30 % ; … » : les N
    jalons servis par le builder (``jalons_paiement``, CIQ212), sinon les
    créneaux SERVIS de ``payment_terms`` (jamais un repli 30/60/10, QJR146) ;
    un créneau nul est omis. Un libellé renommé par la société reste tel
    quel ; aucun chiffre recalculé."""
    jalons = [(j.get("jalon"), j.get("libelle"), j.get("pct"))
              for j in data.get("jalons_paiement") or [] if isinstance(j, dict)]
    if not jalons:
        terms = data.get("payment_terms") or {}
        jalons = [(cle, None, terms.get(cle))
                  for cle in ("acompte", "materiel", "solde")]
    morceaux = []
    for cle, nom, pct in jalons:
        if pct is None or _pct_nul(pct):
            continue
        cat = f"cgv_jalon_{cle}"
        if cat in i18n_labels.LIBELLES and nom in (
                None, "", i18n_labels.LIBELLES[cat]["fr"]):
            nom = i18n_labels.libelle(cat, langue)
        morceaux.append(i18n_labels.libelle("cgv_jalon_format", langue).format(
            libelle=nom or cle, valeur=_pct_txt(pct), unite="%"))
    if not morceaux:
        return ""
    separateur = ("&#160;: " if i18n_labels.normaliser(langue) == "fr"
                  else ": ")
    return (i18n_labels.libelle("ci_echeancier", langue) + separateur
            + " ; ".join(morceaux))


def cgv_bullets_remplies(data, bullets=None):
    """QJR668 — les puces CGV que le rendu de ``data`` (sortie de
    ``build_quote_data``) IMPRIME, cases remplies, entités HTML conservées.

    Mêmes entrées que le rendu, lues dans le MÊME dict : les puces de
    ``data['doc_texts']`` (où le builder a déjà substitué la version GELÉE à
    l'envoi — ``Devis.clauses_appliquees`` ``cgv_gelees``, ERR-QJR668) sinon
    le littéral par défaut ; les pourcentages de ``data['payment_terms']``
    (échéancier du devis rabattu par le builder, QJR623) ; ``tva_note`` ;
    ``valid_until``. Pure : ne lit ni n'écrit aucun global de rendu.
    ``bullets`` (AMOT81) : les puces à remplir, à la place de celles-ci."""
    data = data or {}
    surcharges = data.get("doc_texts") or {}
    langue = data.get("langue_sortie")
    if bullets is None:
        bullets = _puces_cgv(surcharges.get("cgv_bullets")
                             if isinstance(surcharges, dict) else None,
                             langue, data.get("mode_installation"))
    terms = data.get("payment_terms") or {}
    try:
        brut = data.get("taux_tva")
        tva_pct = 20.0 if brut is None or brut == "" else float(brut)  # AMOT73 : 0 % reste 0 %
    except (TypeError, ValueError):
        tva_pct = 20.0
    return remplir_cgv_bullets(
        bullets,
        acompte=_pct_echeance(terms.get("acompte"), 30),
        materiel=_pct_echeance(terms.get("materiel"), 60),
        solde=_pct_echeance(terms.get("solde"), 10),
        tva_note=(data.get("tva_note")
                  or _tva_note_par_defaut(tva_pct, langue)),
        valid_until=(data.get("valid_until") or "").strip(), langue=langue)


def cgv_imprimees(data):
    """APDF12 (C-APDF-005) — LES conditions générales imprimées, forme
    ``{"titre": str, "puces": [str]}`` (figée ; servie au PDF par
    ``ci/blocs``, à la page publique — APDF19 — et au portail — APDF35).

    * devis C&I à variante (``data['cgv_ci']``, gelée à l'envoi ou vive,
      marqueurs {echeancier}/{retenue}/{tva_note} substitués par le builder)
      → SES puces et SON titre (``data['cgv_ci_titre']``) ;
    * sinon les puces société gelées ou vives (:func:`cgv_bullets_remplies`).
    Titre de repli : surcharge société (``doc_texts['cgv_titre']``), sinon
    celui du moteur dans la langue du document. Pure."""
    data = data or {}
    textes = data.get("doc_texts")
    textes = textes if isinstance(textes, dict) else {}
    langue = data.get("langue_sortie")
    titre = str(textes.get("cgv_titre") or "").strip()
    if not titre or titre == DEFAULT_DOC_TEXTS["cgv_titre"]:
        titre = (DEFAULT_DOC_TEXTS["cgv_titre"]
                 if i18n_labels.normaliser(langue) == "fr"
                 else i18n_labels.libelle("ci_cgv_titre", langue))
    ci = data.get("cgv_ci")
    puces_ci = ([str(p) for p in ci if str(p).strip()]
                if isinstance(ci, list) else [])
    if puces_ci:
        return {"titre": str(data.get("cgv_ci_titre") or "").strip() or titre,
                "puces": puces_ci}
    saisies = textes.get("cgv_bullets")
    if (str(data.get("mode_installation") or "").strip().lower() in MODES_CI
            and not data.get("regles_calcul_origine")
            and (not saisies or saisies == DEFAULT_DOC_TEXTS["cgv_bullets"])):
        # AMOT81 — repli C&I : validité, UNE puce échéancier, note de TVA.
        echeancier = puce_echeancier_ci(data, langue)
        return {"titre": titre, "puces": cgv_bullets_remplies(data, [
            "{validite_offre}",
            echeancier.replace("{", "{{").replace("}", "}}"), "{tva_note}"])}
    return {"titre": titre, "puces": cgv_bullets_remplies(data)}


def _conditions_echappees(data):
    """QJR668 / APDF13 — ``(clauses de l'affaire, conditions générales
    imprimées)``, textes SAISIS échappés ici (ERR37) : clauses gelées et
    variante C&I ; les puces société gardent leurs entités (le moteur ne les
    échappe pas)."""
    clauses = [
        {"nom": _esc(str(c.get("nom") or "")),
         "corps_texte": _esc(str(c.get("corps_texte") or ""))}
        for c in (data.get("clauses_cgv") or []) if isinstance(c, dict)]
    cgv_data = dict(data)
    if isinstance(data.get("cgv_ci"), list):
        cgv_data["cgv_ci"] = [_esc(p) for p in data["cgv_ci"]]
    if data.get("cgv_ci_titre"):
        cgv_data["cgv_ci_titre"] = _esc(data["cgv_ci_titre"])
    return clauses, cgv_imprimees(cgv_data)


# Fin de module (cycle d'import avec ``generate_devis_premium``, qui importe
# cette famille APRÈS avoir défini ces noms) : chargé en premier ou en
# second, chaque module trouve chez l'autre des noms DÉJÀ définis.
from .generate_devis_premium import (  # noqa: E402 — fin de module (anti-cycle) (D-ENF22)
    DEFAULT_DOC_TEXTS, _esc, _pct_echeance, _tva_note_par_defaut)
