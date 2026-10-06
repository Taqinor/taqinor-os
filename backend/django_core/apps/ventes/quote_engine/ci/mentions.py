"""CIQ305 — Mentions et hypothèses C&I : UNE table, sourcée et trilingue,
servie au PDF (``commercial/equip.py``, ``industriel/finance.py``, et les
couvertures en CIQ307) et à /proposition (``synthese_ci['hypotheses']``).

POURQUOI. La mention 82-21 était recopiée en dur dans les gabarits (« net des
frais réseau », « plafond en révision » — contredits par D-CIQ-4) au lieu de
lire ``MENTION_82_21`` ; la note « la pointe n'est sécurisée qu'avec un
stockage — non promise sans batterie » s'imprimait même quand l'offre servie
portait une batterie (C3-25) ; aucun document ne disait le tarif utilisé ni
sa source (C3-VB-02, C3-26, C3-27).

RÈGLES.
  * Les textes réglementaires (82-21, BT, art. 13) sont LUS dans
    ``constants_82_21`` (CIQ201) — jamais recopiés ici ; leurs versions
    anglaise et arabe sont des TRADUCTIONS de ces constantes (mêmes chiffres,
    aucun chiffre ajouté — règle F), à relire par Reda.
  * Le tarif cité est celui du bloc ``economie_ci`` servi (contrat CIQ11 :
    facture du client datée, sinon grille officielle étiquetée « repli »).
  * Jamais « heures les plus chères », jamais « puissance souscrite lissée ».
  * Module PUR : dict → liste, aucune base, aucun changement de statut
    (règle #4).

Forme d'une entrée (contrat ``proposal_data.json`` › ``synthese_ci``) :
``{cle, textes{fr, en, ar}, source, date}``.
"""
from __future__ import annotations

from ..constants_82_21 import (
    ANRE_PERIODE,
    ANRE_TARIF_SOURCE,
    MENTION_82_21,
    MENTION_ART13,
    MENTION_BT,
    PLAFOND_INJECTION_SOURCE,
)
from ..lecture_pure import nombre_normalise

LANGUES = ("fr", "en", "ar")

#: Date de la décision ANRE 04/26 (début de validité, ``ANRE_PERIODE``).
DATE_ANRE = ANRE_PERIODE[0].isoformat()

# ── Textes réglementaires : le français EST la constante (CIQ201) ───────────
TEXTES_82_21 = {
    "fr": MENTION_82_21,
    "en": ("ANRE surplus tariff (decision 04/26): 18 cDH/kWh off-peak, "
           "21 cDH/kWh peak, excl. VAT and system-services charge; legal cap "
           "20 % of annual production (law 82-21, art. 12); tariff fixed at "
           "the signature of the agreement, then indexed on the average "
           "general tariff"),
    "ar": ("تعريفة الفائض حسب الهيئة الوطنية لضبط الكهرباء (القرار 04/26): "
           "18 سنتيم درهم/كيلوواط ساعة خارج الذروة و21 سنتيم درهم/كيلوواط "
           "ساعة في الذروة، دون احتساب الرسوم وخدمات النظام؛ السقف القانوني "
           "20 % من الإنتاج السنوي (القانون 82-21، المادة 12)؛ تعريفة "
           "مثبتة عند توقيع الاتفاقية ثم مفهرسة على متوسط التعريفة العامة"),
}
TEXTES_BT = {
    "fr": MENTION_BT,
    "en": ("Surplus resale not open on low voltage to date — ANRE decision "
           "04/26; installation sized for self-consumption"),
    "ar": ("بيع الفائض غير مفتوح في الجهد المنخفض إلى حدود اليوم — قرار "
           "الهيئة الوطنية لضبط الكهرباء 04/26؛ المنشأة مصممة للاستهلاك "
           "الذاتي"),
}
TEXTES_ART13 = {
    "fr": MENTION_ART13,
    "en": ("System and distribution services charge provided for by art. 13 "
           "of law 82-21: not yet set by ANRE, not included"),
    "ar": ("مساهمة خدمات النظام والتوزيع المنصوص عليها في المادة 13 من "
           "القانون 82-21: لم تحددها الهيئة بعد، غير مدرجة"),
}

# ── Conventions du Groupe CIQ ───────────────────────────────────────────────
#: Convention 2 : la centrale réduit l'ÉNERGIE achetée, jamais la puissance.
TEXTES_PUISSANCE = {
    "fr": ("La centrale réduit l'énergie achetée ; la puissance souscrite et "
           "la prime fixe ne changent pas."),
    "en": ("The plant reduces the energy you buy; the subscribed power and "
           "the fixed charge do not change."),
    "ar": ("تقلص المحطة الطاقة المشتراة؛ القدرة المكتتبة والإتاوة الثابتة "
           "لا تتغيران."),
}
#: Note sur la pointe SANS batterie (texte des couvertures, C3-25).
TEXTES_POINTE_SANS = {
    "fr": ("La pointe (soir/nuit) n'est sécurisée qu'avec un stockage — non "
           "promise sans batterie."),
    "en": ("The evening/night peak is only secured with storage — not "
           "promised without a battery."),
    "ar": ("لا تُؤمَّن فترة الذروة (المساء/الليل) إلا بالتخزين — غير موعودة "
           "دون بطارية."),
}
#: Note sur la pointe AVEC batterie que le moteur ne chiffre pas.
TEXTES_POINTE_AVEC_NON_CHIFFREE = {
    "fr": "Couverture du soir selon la capacité installée — non chiffrée.",
    "en": "Evening coverage depending on the installed capacity — not "
          "quantified.",
    "ar": "تغطية المساء حسب السعة المركبة — غير مقدرة بالأرقام.",
}
#: D-CIQ-5 — tant que la visite n'a pas eu lieu.
TEXTES_VISITE = {
    "fr": "Estimation sous réserve de la visite technique.",
    "en": "Estimate subject to the technical site visit.",
    "ar": "تقدير رهين بالزيارة التقنية.",
}
SOURCE_CONVENTION_2 = "conventions Groupe CIQ (convention 2)"
SOURCE_POINTE = "composition de l'offre servie (CIQ302)"
SOURCE_VISITE = "D-CIQ-5"


def _dict(v):
    return v if isinstance(v, dict) else {}


def _entree(cle, textes, source, date=None):
    return {"cle": cle, "textes": dict(textes), "source": source,
            "date": date}


def texte(textes, langue="fr"):
    """Le texte d'une mention dans la langue du document (repli français)."""
    return textes.get(langue) or textes["fr"]


def texte_revente(langue="fr"):
    """La mention 82-21 imprimée sous une ligne d'injection (PDF)."""
    return texte(TEXTES_82_21, langue)


def _tension(data):
    etude_ci = _dict(_dict(data.get("etude")).get("etude_ci"))
    tension = _dict(_dict(etude_ci.get("entrees_resolues")).get(
        "tension")).get("valeur")
    if not isinstance(tension, str) or not tension.strip():
        # Sans moteur : la tension DÉCLARÉE à l'écran (une saisie).
        tension = _dict(data.get("etude")).get("tension_raccordement")
    if isinstance(tension, str) and tension.strip():
        return tension.strip().lower()
    contrat = str(_dict(_dict(data.get("economie_ci")).get("tarif")).get(
        "contrat") or "")
    if contrat == "mt_general":
        return "mt"
    if contrat.startswith("bt"):
        return "bt"
    return None


def _puissance_souscrite_declaree(data):
    etude_ci = _dict(_dict(data.get("etude")).get("etude_ci"))
    entree = _dict(etude_ci.get("entrees_resolues")).get(
        "puissance_souscrite_kva")
    valeur = _dict(entree).get("valeur") if isinstance(entree, dict) \
        else entree
    return valeur not in (None, "", 0)


def _mention_tarif(tarif):
    """Le tarif utilisé et sa source (contrat CIQ11), ou None."""
    origine = tarif.get("origine")
    postes = [p for p in tarif.get("tarifs_par_poste") or []
              if isinstance(p, dict)]
    date = next((p.get("releve_le") for p in postes if p.get("releve_le")),
                None)
    if origine == "declare_facture":
        textes = {
            "fr": "Prix du kWh : ceux de votre facture d'électricité.",
            "en": "kWh prices: those of your electricity bill.",
            "ar": "أثمنة الكيلوواط ساعة: تلك الواردة في فاتورة الكهرباء "
                  "الخاصة بكم.",
        }
    elif origine == "grille_officielle":
        textes = {
            "fr": ("Prix du kWh : grille officielle ONEE publiée (repli), en "
                   "attendant la lecture de votre facture."),
            "en": ("kWh prices: published official ONEE tariff (fallback), "
                   "until your bill is read."),
            "ar": ("أثمنة الكيلوواط ساعة: التعريفة الرسمية المنشورة للمكتب "
                   "الوطني (احتياطي) إلى حين قراءة فاتورتكم."),
        }
    else:
        return None
    source = tarif.get("mention") or (postes[0].get("source")
                                      if postes else None)
    return _entree("tarif", textes, source, date)


def _batterie_servie(data):
    if data.get("avec_batterie_differee"):
        return False
    servie = data.get("option_servie")
    if servie == "avec":
        return True
    if servie == "sans":
        return False
    return bool(data.get("avec_ok") and not data.get("sans_ok"))


def _mention_pointe(data):
    if not _batterie_servie(data):
        return _entree("pointe", TEXTES_POINTE_SANS, SOURCE_POINTE)
    # Batterie servie : SEULEMENT ce que le moteur chiffre (un texte qu'il
    # sert), sinon « non chiffrée » — jamais une promesse.
    chiffre = _dict(data.get("option_batterie")).get("valeur_chiffree")
    if isinstance(chiffre, dict) and isinstance(chiffre.get("textes"), dict) \
            and chiffre["textes"].get("fr"):
        return _entree("pointe", chiffre["textes"], "moteur C&I",
                       chiffre.get("date"))
    return _entree("pointe", TEXTES_POINTE_AVEC_NON_CHIFFREE, SOURCE_POINTE)


def mentions_ci(data, *, sous_reserve=False):
    """Les phrases client C&I d'un devis (liste ordonnée, forme du contrat).

    ``data`` : la charge utile de ``build_quote_data`` ; ``sous_reserve`` :
    ``statut_etude`` dit « estimation sous réserve de visite » (CIQ303).
    """
    data = data if isinstance(data, dict) else {}
    economie = _dict(data.get("economie_ci"))
    sortie = []
    tarif = _mention_tarif(_dict(economie.get("tarif")))
    if tarif is not None:
        sortie.append(tarif)
    tension = _tension(data)
    mt = tension in ("mt", "ht")
    if mt:
        revente = _dict(economie.get("revente"))
        injection = nombre_normalise(
            _dict(data.get("etude")).get("injection_dh_an"))
        if revente.get("statut") == "calculee" or (injection or 0) > 0:
            sortie.append(_entree(
                "revente", TEXTES_82_21,
                f"{ANRE_TARIF_SOURCE} ; {PLAFOND_INJECTION_SOURCE}",
                DATE_ANRE))
    elif tension == "bt":
        sortie.append(_entree("revente_bt", TEXTES_BT,
                              "décision ANRE n° 04/26", DATE_ANRE))
    sortie.append(_entree("contribution_art13", TEXTES_ART13,
                          "loi 82-21, art. 13"))
    if mt or _puissance_souscrite_declaree(data):
        sortie.append(_entree("puissance_souscrite", TEXTES_PUISSANCE,
                              SOURCE_CONVENTION_2))
    sortie.append(_mention_pointe(data))
    if sous_reserve:
        sortie.append(_entree("visite", TEXTES_VISITE, SOURCE_VISITE))
    return sortie
