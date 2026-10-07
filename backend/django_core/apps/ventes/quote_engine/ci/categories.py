"""CIQ330 — contenu par catégorie commerciale : UNE table trilingue
(réponses DÉCLARÉES du questionnaire → lignes), servie dans
``synthese_ci['categorie']`` au PDF (accroche de la page 1, bloc de la page
2) et à /proposition.

RÈGLES (constats C3-15, C3-10, W2-16, C2-VB-03 ; D-CIQ-4) :
  * Contenu QUALITATIF : aucun chiffre qui ne vienne pas d'une réponse
    déclarée ; aucune promesse physique non calculée (« alignement idéal »,
    « quasi-totalité consommée sur place », « peu d'export », « budget
    prévisible ») ; aucun jargon interne.
  * Une valeur de liste est TRADUITE (« électrique », « gaz »), jamais
    imprimée brute ; un titre ne parle d'une réponse que si elle est
    déclarée (pas de « cuisson nocturne » sans cuisson de nuit).
  * Injection : lue sur ``synthese_ci.argent.revente`` (sinon la tension) —
    basse tension ⇒ la revente n'est pas ouverte (ANRE 04/26), jamais
    « injectable » ni « valorisable » ; moyenne tension ⇒ la mention 82-21
    SOURCÉE de ``ci/mentions`` (CIQ201/CIQ305).
  * La saisonnalité est dite telle que le client l'a déclarée, jamais
    supposée.

Module PUR : dict → dict, aucune base, aucun statut touché (règle #4).
"""
from __future__ import annotations

from ..lecture_pure import nombre_normalise
from . import mentions

LANGUES = ("fr", "en", "ar")


def _t(fr, en, ar):
    return {"fr": fr, "en": en, "ar": ar}


#: Libellé et accroche par catégorie (clés de solar.js
#: ``COMMERCIAL_CATEGORIES``). Accroches QUALITATIVES, sans promesse.
CATEGORIES = {
    "hotel": {
        "libelle": _t("Hôtel / Riad", "Hotel / Riad", "فندق / رياض"),
        "accroche": _t(
            "Climatisation, piscine, blanchisserie : le solaire produit "
            "pendant la journée de votre établissement.",
            "Air conditioning, pool, laundry: solar produces during your "
            "establishment's daytime.",
            "التكييف والمسبح والمصبنة: تنتج الطاقة الشمسية خلال نهار "
            "مؤسستكم."),
    },
    "restaurant": {
        "libelle": _t("Restaurant / Café", "Restaurant / Café",
                      "مطعم / مقهى"),
        "accroche": _t(
            "Froid, éclairage et climatisation de journée : le poste que le "
            "solaire peut alléger.",
            "Daytime refrigeration, lighting and air conditioning: the load "
            "solar can lighten.",
            "التبريد والإنارة والتكييف خلال النهار: البند الذي يمكن للطاقة "
            "الشمسية تخفيفه."),
    },
    "commerce": {
        "libelle": _t("Commerce / Supermarché", "Shop / Supermarket",
                      "متجر / سوق ممتاز"),
        "accroche": _t(
            "Froid alimentaire, éclairage et climatisation pendant vos "
            "heures d'ouverture de jour.",
            "Food refrigeration, lighting and air conditioning during your "
            "daytime opening hours.",
            "التبريد الغذائي والإنارة والتكييف خلال ساعات فتحكم النهارية."),
    },
    "bureau": {
        "libelle": _t("Bureau / Siège", "Office / Headquarters",
                      "مكتب / مقر"),
        "accroche": _t(
            "Une activité de journée : le solaire produit pendant vos heures "
            "de bureau.",
            "A daytime activity: solar produces during your office hours.",
            "نشاط نهاري: تنتج الطاقة الشمسية خلال ساعات عملكم."),
    },
    "sante": {
        "libelle": _t("Santé (clinique / cabinet)",
                      "Healthcare (clinic / practice)",
                      "الصحة (مصحة / عيادة)"),
        "accroche": _t(
            "Le solaire allège la consommation de journée de votre "
            "établissement de santé.",
            "Solar lightens the daytime consumption of your healthcare "
            "facility.",
            "تخفف الطاقة الشمسية الاستهلاك النهاري لمؤسستكم الصحية."),
    },
    "ecole": {
        "libelle": _t("École privée", "Private school", "مدرسة خاصة"),
        "accroche": _t(
            "Une consommation de journée pendant l'année scolaire : le "
            "solaire produit pendant les cours.",
            "Daytime consumption during the school year: solar produces "
            "during class hours.",
            "استهلاك نهاري خلال السنة الدراسية: تنتج الطاقة الشمسية خلال "
            "ساعات الدراسة."),
    },
    "hammam": {
        "libelle": _t("Hammam / Spa / Gym", "Hammam / Spa / Gym",
                      "حمام / سبا / قاعة رياضة"),
        "accroche": _t(
            "Le solaire allège la part électrique de votre consommation de "
            "journée.",
            "Solar lightens the electric share of your daytime consumption.",
            "تخفف الطاقة الشمسية الجزء الكهربائي من استهلاككم النهاري."),
    },
    "boulangerie": {
        "libelle": _t("Boulangerie", "Bakery", "مخبزة"),
        "accroche": _t(
            "Froid, éclairage et climatisation de journée : ce que le "
            "solaire couvre, sans rien promettre sur la cuisson.",
            "Daytime refrigeration, lighting and air conditioning: what "
            "solar covers, with no promise on baking.",
            "التبريد والإنارة والتكييف خلال النهار: ما تغطيه الطاقة "
            "الشمسية، دون أي وعد بشأن الطهي."),
    },
    "froid": {
        "libelle": _t("Entrepôt froid", "Cold storage warehouse",
                      "مستودع تبريد"),
        "accroche": _t(
            "Les groupes froids tournent aussi de jour : le solaire en "
            "allège la part diurne.",
            "Refrigeration units also run by day: solar lightens their "
            "daytime share.",
            "تعمل وحدات التبريد نهارا أيضا: تخفف الطاقة الشمسية حصتها "
            "النهارية."),
    },
    "autre": {
        "libelle": _t("Autre commerce", "Other business", "نشاط تجاري آخر"),
        "accroche": _t(
            "Le solaire produit pendant la journée de votre établissement, "
            "en autoconsommation.",
            "Solar produces during your establishment's daytime, for "
            "self-consumption.",
            "تنتج الطاقة الشمسية خلال نهار مؤسستكم، للاستهلاك الذاتي."),
    },
}

#: Valeurs de liste du questionnaire, TRADUITES (jamais imprimées brutes).
ENERGIES = {
    "electrique": _t("électrique", "electric", "كهربائي"),
    "gaz": _t("au gaz", "gas", "بالغاز"),
}
HORAIRES = {
    "midi": _t("service du midi", "lunch service", "خدمة الغداء"),
    "soir": _t("service du soir", "evening service", "خدمة العشاء"),
    "continu": _t("service continu", "continuous service", "خدمة متواصلة"),
}

#: Revente BT (D-CIQ-4) — la phrase exacte du plan CIQ330.
TEXTES_SURPLUS_BT = _t(
    "Surplus d'été non valorisé : la revente n'est pas ouverte en basse "
    "tension (ANRE 04/26) — l'installation est dimensionnée sur les mois "
    "d'occupation.",
    "Summer surplus not remunerated: resale is not open on low voltage "
    "(ANRE 04/26) — the installation is sized on the months of occupancy.",
    "فائض الصيف غير مثمن: بيع الفائض غير مفتوح في الجهد المنخفض (الهيئة "
    "الوطنية لضبط الكهرباء 04/26) — المنشأة مصممة على أشهر الاشتغال.")

DECLARE = _t("déclaré", "declared", "مصرح به")


def _dict(v):
    return v if isinstance(v, dict) else {}


def _entier(valeur):
    n = nombre_normalise(valeur)
    if n is None or n <= 0:
        return None
    return f"{n:g}"


def _oui(valeur):
    """Réponse booléenne DÉCLARÉE : True / False, ou None si non déclarée."""
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, str):
        v = valeur.strip().lower()
        if v in ("true", "oui", "1", "yes"):
            return True
        if v in ("false", "non", "0", "no"):
            return False
    return None


def _choix(table, valeur):
    return table.get(str(valeur or "").strip().lower())


def _ligne(fr, en, ar):
    return {"textes": _t(fr, en, ar)}


def _ligne_declaree(morceaux):
    """Une ligne « a, b, c (déclaré) » à partir de morceaux trilingues."""
    if not morceaux:
        return None
    textes = {}
    for lg in LANGUES:
        phrase = ", ".join(m[lg] for m in morceaux) + f" ({DECLARE[lg]})."
        textes[lg] = phrase[:1].upper() + phrase[1:]
    return {"textes": textes}


def _revente(data, synthese):
    """'bt', 'mt' ou None — lue sur ``argent.revente`` (sinon la tension)."""
    revente = _dict(_dict(_dict(synthese).get("argent")).get("revente"))
    statut = revente.get("statut")
    if statut == "absente_bt":
        return "bt"
    if statut in ("calculee", "omise"):
        return "mt"
    tension = mentions._tension(data)
    if tension in ("mt", "ht"):
        return "mt"
    if tension == "bt":
        return "bt"
    return None


def _ligne_injection(data, synthese):
    regime = _revente(data, synthese)
    if regime == "bt":
        return {"textes": dict(TEXTES_SURPLUS_BT)}
    if regime == "mt":
        return {"textes": dict(mentions.TEXTES_82_21)}
    return None


# ── Bloc par catégorie ──────────────────────────────────────────────────────

def _hotel(e):
    m = []
    ch = _entier(e.get("chambres"))
    if ch:
        m.append(_t(f"{ch} chambres", f"{ch} rooms", f"{ch} غرفة"))
    occ = _entier(e.get("occupation_pct"))
    if occ:
        m.append(_t(f"occupation {occ} %", f"{occ} % occupancy",
                    f"نسبة الملء {occ} %"))
    if _oui(e.get("piscine")):
        m.append(_t("piscine chauffée", "heated pool", "مسبح مدفأ"))
    return _t("Votre hôtel", "Your hotel", "فندقكم"), [_ligne_declaree(m)]


def _restaurant(e):
    m = []
    cf = _entier(e.get("chambres_froides"))
    if cf:
        m.append(_t(f"{cf} chambres froides", f"{cf} cold rooms",
                    f"{cf} غرف تبريد"))
    horaires = _choix(HORAIRES, e.get("horaires"))
    if horaires:
        m.append(horaires)
    cuisson = _choix(ENERGIES, e.get("cuisson"))
    if cuisson:
        m.append(_t(f"cuisson {cuisson['fr']}", f"{cuisson['en']} cooking",
                    f"طهي {cuisson['ar']}"))
    lignes = [_ligne_declaree(m)]
    if str(e.get("horaires") or "").strip().lower() in ("soir", "continu"):
        lignes.append(_ligne(
            "Le service du soir n'est pas couvert par le solaire sans "
            "stockage.",
            "The evening service is not covered by solar without storage.",
            "خدمة المساء غير مغطاة بالطاقة الشمسية دون تخزين."))
    return _t("Votre restaurant", "Your restaurant", "مطعمكم"), lignes


def _commerce(e):
    m = []
    s = _entier(e.get("surface_vente_m2"))
    if s:
        m.append(_t(f"{s} m² de surface de vente", f"{s} m² sales area",
                    f"{s} م² مساحة البيع"))
    cf = _entier(e.get("chambres_froides"))
    if cf:
        m.append(_t(f"{cf} meubles ou chambres froids",
                    f"{cf} refrigerated units or cold rooms",
                    f"{cf} وحدات أو غرف تبريد"))
    return _t("Votre commerce", "Your shop", "متجركم"), [_ligne_declaree(m)]


def _bureau(e):
    m = []
    eff = _entier(e.get("effectif"))
    if eff:
        m.append(_t(f"{eff} postes", f"{eff} workstations",
                    f"{eff} منصب عمل"))
    clim = _oui(e.get("clim"))
    if clim is True:
        m.append(_t("climatisation centralisée", "central air conditioning",
                    "تكييف مركزي"))
    elif clim is False:
        m.append(_t("climatisation non centralisée",
                    "non-central air conditioning", "تكييف غير مركزي"))
    return _t("Vos bureaux", "Your offices", "مكاتبكم"), [_ligne_declaree(m)]


def _sante(e):
    m = []
    lits = _entier(e.get("lits"))
    if lits:
        m.append(_t(f"{lits} lits", f"{lits} beds", f"{lits} سرير"))
    garde = _oui(e.get("garde_nuit"))
    if garde is True:
        m.append(_t("garde de nuit", "night shift", "مداومة ليلية"))
    elif garde is False:
        m.append(_t("sans garde de nuit", "no night shift",
                    "بدون مداومة ليلية"))
    lignes = [_ligne_declaree(m)]
    if garde is True:
        lignes.append(_ligne(
            "La consommation de la garde de nuit reste achetée au réseau "
            "sans stockage.",
            "Night-shift consumption is still bought from the grid without "
            "storage.",
            "يبقى استهلاك المداومة الليلية مشترى من الشبكة دون تخزين."))
    return (_t("Votre établissement de santé", "Your healthcare facility",
               "مؤسستكم الصحية"), lignes)


def _ecole(e, data, synthese):
    m = []
    eff = _entier(e.get("effectif"))
    if eff:
        m.append(_t(f"{eff} élèves", f"{eff} pupils", f"{eff} تلميذ"))
    internat = _oui(e.get("internat"))
    if internat is True:
        m.append(_t("internat", "boarding", "داخلية"))
    elif internat is False:
        m.append(_t("externat", "day school", "خارجية"))
    ferme = _oui(e.get("fermeture_estivale"))
    if ferme is True:
        m.append(_t("fermée l'été", "closed in summer", "مغلقة صيفا"))
    elif ferme is False:
        m.append(_t("ouverte l'été", "open in summer", "مفتوحة صيفا"))
    lignes = [_ligne_declaree(m)]
    if ferme is True:
        lignes.append(_ligne_injection(data, synthese))
    return _t("Votre école", "Your school", "مدرستكم"), lignes


def _hammam(e):
    m = []
    s = _entier(e.get("surface_m2"))
    if s:
        m.append(_t(f"{s} m²", f"{s} m²", f"{s} م²"))
    chauffe = _choix(ENERGIES, e.get("chauffe"))
    if chauffe:
        m.append(_t(f"chauffe de l'eau {chauffe['fr']}",
                    f"{chauffe['en']} water heating",
                    f"تسخين الماء {chauffe['ar']}"))
    return (_t("Votre établissement", "Your establishment", "مؤسستكم"),
            [_ligne_declaree(m)])


def _boulangerie(e):
    m = []
    four = _choix(ENERGIES, e.get("four"))
    if four:
        m.append(_t(f"four {four['fr']}", f"{four['en']} oven",
                    f"فرن {four['ar']}"))
    nocturne = _oui(e.get("cuisson_nocturne"))
    if nocturne is True:
        m.append(_t("cuisson de nuit", "night baking", "طهي ليلي"))
    elif nocturne is False:
        m.append(_t("sans cuisson de nuit", "no night baking",
                    "بدون طهي ليلي"))
    lignes = [_ligne_declaree(m)]
    if nocturne is True:
        titre = _t("Transparence sur la cuisson nocturne",
                   "Transparency on night baking",
                   "شفافية بشأن الطهي الليلي")
        lignes.append(_ligne(
            "La cuisson de nuit n'est pas couverte par le solaire sans "
            "stockage — nous ne la promettons pas.",
            "Night baking is not covered by solar without storage — we do "
            "not promise it.",
            "الطهي الليلي غير مغطى بالطاقة الشمسية دون تخزين — لا نعد "
            "به."))
    else:
        titre = _t("Votre boulangerie", "Your bakery", "مخبزتكم")
    return titre, lignes


def _froid(e):
    m = []
    temp = nombre_normalise(e.get("temperature_consigne"))
    if temp is not None:
        m.append(_t(f"consigne {temp:g} °C", f"{temp:g} °C set point",
                    f"درجة الضبط {temp:g} °م"))
    vol = _entier(e.get("volume_m3"))
    if vol:
        m.append(_t(f"{vol} m³ de froid", f"{vol} m³ cold volume",
                    f"{vol} م³ تبريد"))
    if _oui(e.get("saisonnalite_recolte")):
        m.append(_t("pic saisonnier de récolte", "seasonal harvest peak",
                    "ذروة موسمية للجني"))
    return (_t("Votre entrepôt froid", "Your cold storage", "مستودع تبريدكم"),
            [_ligne_declaree(m)])


BLOCS = {
    "hotel": _hotel, "restaurant": _restaurant, "commerce": _commerce,
    "bureau": _bureau, "sante": _sante, "hammam": _hammam,
    "boulangerie": _boulangerie, "froid": _froid,
}


def _langue(textes, langue):
    return textes.get(langue) or textes["fr"]


def texte_ligne(ligne, langue="fr"):
    """Le texte d'une ligne du bloc dans la langue du document (repli fr)."""
    textes = _dict(_dict(ligne).get("textes"))
    return textes.get(langue) or textes.get("fr") or ""


def categorie_ci(data, synthese=None):
    """La forme ``synthese_ci['categorie']`` (contrat ``proposal_data.json``,
    CIQ4) : ``{cle, libelle, accroche, bloc{titre, lignes[{textes}]}}``.

    Catégorie absente ou inconnue ⇒ « autre ». ``synthese`` : la synthèse en
    cours (pour ``argent.revente``). Les lignes vides sont omises ; un bloc
    sans aucune ligne déclarée garde la note sur la pointe de la table des
    mentions (CIQ305)."""
    data = data if isinstance(data, dict) else {}
    etude = _dict(data.get("etude"))
    langue = data.get("langue_sortie") or "fr"
    cle = str(etude.get("categorie_commerciale") or "").strip().lower()
    if cle not in CATEGORIES:
        cle = "autre"
    meta = CATEGORIES[cle]
    # CIQ129 — les réponses DÉCLARÉES se lisent dans l'entrée v2 du moteur
    # C&I (``rythme.reponses_categorie``, contrat ``etude_ci_preview.json``),
    # jamais à plat dans l'étude (clés retirées du schéma).
    reponses = _dict(_dict(etude.get("rythme")).get("reponses_categorie"))
    if cle == "ecole":
        titre, lignes = _ecole(reponses, data, synthese)
    elif cle in BLOCS:
        titre, lignes = BLOCS[cle](reponses)
    else:
        titre, lignes = _t("Votre établissement", "Your establishment",
                           "مؤسستكم"), []
    lignes = [li for li in lignes if li]
    if not lignes:
        pointe = next((h for h in _dict(synthese).get("hypotheses") or []
                       if isinstance(h, dict) and h.get("cle") == "pointe"),
                      None)
        textes = _dict(_dict(pointe).get("textes")) \
            or dict(mentions.TEXTES_POINTE_SANS)
        lignes = [{"textes": dict(textes)}]
    return {
        "cle": cle,
        "libelle": _langue(meta["libelle"], langue),
        "accroche": _langue(meta["accroche"], langue),
        "bloc": {"titre": _langue(titre, langue), "lignes": lignes},
    }
