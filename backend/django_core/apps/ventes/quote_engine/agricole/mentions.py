"""AGR306 — les TEXTES RÉGLEMENTAIRES du devis agricole : la règle de l'aide
FDA (sans montant) et les formalités du client, en fr / en / ar.

POURQUOI. Le seul texte d'aide montré au client était la carte web « …
pouvant atteindre 30 % » (contraire à Q22) ; aucun texte ne rappelait
l'accord préalable AVANT travaux (le client qui fait poser tout de suite perd
l'aide), et rien ne disait les formalités de prélèvement d'eau (constat
W2-20). Ce module porte des constantes DATÉES, avec leur source écrite ici.

CE QU'IL REND (forme du contrat ``contract_samples/proposal_data.json`` ›
``exemple_agricole.synthese_agricole``) :

* :func:`regle_fda` → ``aide_fda`` = la RÈGLE (D-AGR-6) : conditions,
  plafonds, édition, source, date de relevé, textes fr/en/ar. Les CHIFFRES,
  la source et la date viennent de ``TariffSettings.regle_fda_pompage``
  (AGR207) quand la société l'a saisie (le builder la passe dans ``data``
  sous ``regle_fda_societe``), sinon du REPLI daté ci-dessous (Guide FDA
  2024, p.20-23) ;
* :func:`formalites` → ``formalites`` = déclaration 82-21 (installation hors
  réseau) et prélèvement d'eau (loi 36-15), à la charge du client ;
* :func:`phrase_provenance` → les phrases « déclaré par vous le … », « mesuré
  par … le … », « à confirmer par la visite », « besoin agronomique plein
  (FAO-56) ».

CE QU'IL NE FAIT JAMAIS (D-AGR-6, Q22) : un montant propre au client, un
délai, « jusqu'à 30 % » isolé, « cumulable », une logique d'injection ou de
revente (82-21 : hors réseau = déclaration). Le montant FDA indicatif reste un
écran INTERNE, hors de ce module. L'arabe est écrit maintenant et relu par
Reda ensuite (D-AGR-11, sans bloquer l'envoi). Module PUR : aucune I/O.
"""
from __future__ import annotations

LANGUES = ("fr", "en", "ar")

# ── Aide FDA : repli daté (D-AGR-6) ──────────────────────────────────────────
#: Repli utilisé tant que la société n'a pas saisi sa règle (AGR207). Relevé
#: dans le Guide FDA, édition 2024, p.20-23 (audit L3 du 02/10/2026).
REPLI_FDA = {
    "taux_pct": 30,
    "plafond_mad_par_ha": 3000,
    "plafond_mad_par_kwc": 3000,
    "plafond_mad_par_projet": 30000,
    "edition": "Guide FDA 2024",
    "source": "Guide FDA édition 2024, p.20-23",
    "releve_le": "2026-10-02",
}

PLAFONDS = ("taux_pct", "plafond_mad_par_ha", "plafond_mad_par_kwc",
            "plafond_mad_par_projet")

#: Conditions de la règle (D-AGR-6), dans l'ordre d'affichage.
CONDITIONS_FDA = (
    "remplacement d'une pompe au butane",
    "irrigation localisée",
    "compteur d'eau",
    "accord préalable obtenu AVANT les travaux",
    "aide non déduite du prix, versée après réalisation",
    "un seul projet par exploitation",
    "décision de la DPA/ORMVA, non garantie",
)

#: Le nom de l'installateur quand ``data['entreprise']`` n'en porte aucun.
NOM_PAR_DEFAUT = "TAQINOR"

# ── Formalités du client ────────────────────────────────────────────────────
#: Loi 36-15 relative à l'eau : l'article (26 et suivants, version consolidée
#: du 18/07/2024) n'est cité QUE lorsque l'URL du texte consolidé et la date
#: de lecture sont écrites ici ; sinon la mention reste « loi 36-15 » sans
#: numéro d'article (aucune référence non relue).
LOI_36_15_URL = None
LOI_36_15_LU_LE = None


def _nombre(valeur):
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        f = float(valeur)
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def _milliers(n, sep):
    entier = int(n) if float(n) == int(n) else n
    if isinstance(entier, int):
        return f"{entier:,}".replace(",", sep)
    return str(entier).replace(".", "," if sep != "," else ".")


def _textes_fda(plafonds, source, nom):
    t, ha, kwc, projet = (plafonds.get(c) for c in PLAFONDS)

    def fr(n):
        return _milliers(n, " ") if n is not None else "—"

    def en(n):
        return _milliers(n, ",") if n is not None else "—"

    return {
        "fr": (f"Aide de l'État (Fonds de développement agricole) au pompage "
               f"solaire : {fr(t)} % de l'investissement, plafonnée à "
               f"{fr(ha)} DH par hectare, {fr(kwc)} DH par kWc et "
               f"{fr(projet)} DH par projet. Conditions : remplacement d'une "
               f"pompe au butane, irrigation localisée, compteur d'eau. "
               f"Accord préalable à obtenir AVANT les travaux ; l'aide n'est "
               f"pas déduite du prix et elle est versée après réalisation ; "
               f"un seul projet par exploitation. Décision de la DPA/ORMVA, "
               f"non garantie ; {nom} n'est pas organisme subventionneur. "
               f"Source : {source}."),
        "en": (f"State aid (Agricultural Development Fund) for solar pumping: "
               f"{en(t)}% of the investment, capped at {en(ha)} MAD per "
               f"hectare, {en(kwc)} MAD per kWp and {en(projet)} MAD per "
               f"project. Conditions: replacement of a butane pump, localised "
               f"irrigation, water meter. Prior approval must be obtained "
               f"BEFORE the works; the aid is not deducted from the price and "
               f"is paid after completion; one project per farm. Decision of "
               f"the DPA/ORMVA, not guaranteed; {nom} is not a subsidising "
               f"body. Source: {source}."),
        "ar": (f"دعم الدولة (صندوق التنمية الفلاحية) للضخ بالطاقة الشمسية: "
               f"{fr(t)} % من الاستثمار، في حدود {fr(ha)} درهم للهكتار "
               f"و{fr(kwc)} درهم للكيلوواط ذروة و{fr(projet)} درهم للمشروع. "
               f"الشروط: تعويض مضخة تعمل بالبوطان، الري الموضعي، عداد الماء. "
               f"يجب الحصول على الموافقة المسبقة قبل الأشغال؛ لا يُخصم الدعم "
               f"من الثمن ويُصرف بعد الإنجاز؛ مشروع واحد لكل استغلالية. قرار "
               f"المديرية الإقليمية للفلاحة / المكتب الجهوي للاستثمار "
               f"الفلاحي، غير مضمون؛ {nom} ليست جهة مانحة للدعم. "
               f"المصدر: {source}."),
    }


def regle_fda(regle_societe=None, *, nom_societe=None):
    """D-AGR-6 — la RÈGLE de l'aide FDA (jamais un montant propre au client).

    ``regle_societe`` : ``TariffSettings.regle_fda_pompage`` validée (AGR207 :
    ``{taux_pct, plafond_mad_par_ha, plafond_mad_par_kwc,
    plafond_mad_par_projet, base, source, releve_le}``) ; vide ⇒ repli daté
    « Guide FDA 2024 ». Rend ``{conditions, plafonds, edition, source,
    releve_le, textes}``.
    """
    regle = regle_societe if isinstance(regle_societe, dict) else {}
    saisie = bool(regle.get("source"))
    base = regle if saisie else REPLI_FDA
    plafonds = {cle: _nombre(base.get(cle)) for cle in PLAFONDS}
    source = base.get("source") or REPLI_FDA["source"]
    # La règle saisie n'a pas de clé « édition » (AGR207) : sa source la
    # nomme (« édition et pages du Guide FDA »).
    edition = (base.get("edition") or source) if saisie \
        else REPLI_FDA["edition"]
    nom = (nom_societe or "").strip() or NOM_PAR_DEFAUT
    return {
        "conditions": list(CONDITIONS_FDA),
        "plafonds": plafonds,
        "edition": edition,
        "source": source,
        "releve_le": (base.get("releve_le") or None) if saisie
        else REPLI_FDA["releve_le"],
        "textes": _textes_fda(plafonds, source, nom),
    }


def _formalite_prelevement():
    if LOI_36_15_URL and LOI_36_15_LU_LE:
        ref_fr = ("loi 36-15, art. 26 et suivants, version consolidée du "
                  "18/07/2024")
        ref_en = ("Law 36-15, art. 26 et seq., consolidated version of "
                  "18/07/2024")
        ref_ar = "القانون 36-15، المادة 26 وما يليها، الصيغة المحينة بتاريخ 18/07/2024"
        source = "%s (%s, lu le %s)" % (
            ref_fr, LOI_36_15_URL, LOI_36_15_LU_LE)
    else:
        ref_fr, ref_en, ref_ar = "loi 36-15", "Law 36-15", "القانون 36-15"
        source = "Loi 36-15 relative à l'eau"
    return {
        "cle": "prelevement_3615",
        "textes": {
            "fr": (f"Forage et prélèvement d'eau : autorisation de l'agence "
                   f"de bassin hydraulique et compteur sur un prélèvement par "
                   f"pompage ({ref_fr}) — à la charge du client."),
            "en": (f"Borehole and water abstraction: authorisation from the "
                   f"river basin agency and a meter on any pumped abstraction "
                   f"({ref_en}) — the client's responsibility."),
            "ar": (f"الثقب وجلب المياه: ترخيص من وكالة الحوض المائي وعداد على "
                   f"كل جلب بالضخ ({ref_ar}) — على عاتق الزبون."),
        },
        "source": source,
    }


def formalites():
    """Les formalités du client (installation hors réseau + prélèvement
    d'eau). Aucune logique d'injection ni de revente (82-21, art. 3)."""
    return [
        {
            "cle": "declaration_8221",
            "textes": {
                "fr": ("Installation hors réseau : soumise à DÉCLARATION "
                       "(loi 82-21, art. 3)."),
                "en": ("Off-grid installation: subject to DECLARATION "
                       "(Law 82-21, art. 3)."),
                "ar": ("منشأة غير مرتبطة بالشبكة: تخضع للتصريح "
                       "(القانون 82-21، المادة 3)."),
            },
            "source": "Loi 82-21, art. 3",
        },
        _formalite_prelevement(),
    ]


#: Les phrases de provenance (contrat AGR2 › ``provenance``), par langue.
PHRASES_PROVENANCE = {
    "declare": {"fr": "déclaré par vous le {date}",
                "en": "declared by you on {date}",
                "ar": "صرحتم به بتاريخ {date}"},
    "mesure": {"fr": "mesuré par {societe} le {date}",
               "en": "measured by {societe} on {date}",
               "ar": "قاسته {societe} بتاريخ {date}"},
    "a_confirmer": {"fr": "à confirmer par la visite",
                    "en": "to be confirmed by the site visit",
                    "ar": "يجب تأكيده خلال الزيارة"},
    "agronomique": {"fr": "besoin agronomique plein (FAO-56)",
                    "en": "full agronomic need (FAO-56)",
                    "ar": "الحاجة الفلاحية الكاملة (FAO-56)"},
}


def _date_jjmmaaaa(date_iso):
    texte = str(date_iso or "")[:10]
    if len(texte) == 10 and texte[4] == "-" and texte[7] == "-":
        return "%s/%s/%s" % (texte[8:10], texte[5:7], texte[0:4])
    return None


def phrase_provenance(cle, langue="fr", *, date=None, nom_societe=None):
    """La phrase de provenance ``cle`` dans ``langue`` (fr par défaut).

    ``declare`` / ``mesure`` exigent une date : sans date lisible, la phrase
    retombe sur « à confirmer par la visite » (jamais une date inventée)."""
    langue = langue if langue in LANGUES else "fr"
    if cle in ("declare", "mesure"):
        jour = _date_jjmmaaaa(date)
        if jour is None:
            return PHRASES_PROVENANCE["a_confirmer"][langue]
        societe = (nom_societe or "").strip() or NOM_PAR_DEFAUT
        return PHRASES_PROVENANCE[cle][langue].format(date=jour,
                                                      societe=societe)
    return PHRASES_PROVENANCE[cle][langue]
