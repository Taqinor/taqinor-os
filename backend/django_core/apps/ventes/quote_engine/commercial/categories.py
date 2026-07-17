# flake8: noqa
"""Métadonnées des catégories commerciales (QX46) — libellé, pictogramme,
accroche P1 et bloc conditionnel P2. Miroir informatif de
frontend/src/features/ventes/solar.js COMMERCIAL_CATEGORIES / _QUESTIONS.

Chaque contenu est QUALITATIF (aucun chiffre inventé) ; les nombres affichés
viennent des réponses du questionnaire (etude_params) quand elles existent.
Catégorie absente/inconnue → METADATA['autre'] (blocs génériques).
"""

# label, icône (emoji rendu par WeasyPrint via Noto), accroche P1.
METADATA = {
    "hotel":       {"label": "Hôtel / Riad", "icon": "🏨",
                    "accroche": "Chaque nuitée mieux margée : le solaire allège la climatisation, la piscine et la blanchisserie."},
    "restaurant":  {"label": "Restaurant / Café", "icon": "🍽️",
                    "accroche": "Sécurisez la chaîne du froid et maîtrisez le poste énergie de votre cuisine."},
    "commerce":    {"label": "Commerce / Supermarché", "icon": "🛒",
                    "accroche": "Froid alimentaire, éclairage et climatisation : votre base diurne couverte par le solaire."},
    "bureau":      {"label": "Bureau / Siège", "icon": "🏢",
                    "accroche": "Vos heures de bureau coïncident avec le soleil : autoconsommation élevée, peu d'export."},
    "sante":       {"label": "Santé (clinique / cabinet)", "icon": "🏥",
                    "accroche": "Continuité de service et maîtrise du coût énergie, en journée comme en garde."},
    "ecole":       {"label": "École privée", "icon": "🎓",
                    "accroche": "Consommation en période scolaire, production toute l'année : un budget énergie prévisible."},
    "hammam":      {"label": "Hammam / Spa / Gym", "icon": "🧖",
                    "accroche": "Chauffe de l'eau et confort thermique : le solaire allège votre poste énergie."},
    "boulangerie": {"label": "Boulangerie", "icon": "🥖",
                    "accroche": "Le solaire couvre le froid, l'éclairage et la clim de jour — en toute transparence sur la cuisson."},
    "froid":       {"label": "Entrepôt froid", "icon": "❄️",
                    "accroche": "Sécurisez votre chaîne du froid et abaissez le coût de la base 24 h."},
    "autre":       {"label": "Commerce", "icon": "🏪",
                    "accroche": "Le solaire couvre la consommation diurne de votre établissement en autoconsommation."},
}


def meta(category):
    return METADATA.get((category or "").strip().lower(), METADATA["autre"])


def _num(v):
    try:
        f = float(v)
        return f if f == f else None
    except (TypeError, ValueError):
        return None


def category_block(category, etude, C, fmt):
    """HTML du bloc P2 conditionnel par catégorie. `etude` porte les réponses du
    questionnaire (QX44). Retourne un bloc (string) — jamais None."""
    cat = (category or "").strip().lower()
    etude = etude or {}
    navy = C["navy"]
    gold = C["gold"]
    green = C["green"]
    green_bg = C.get("green_bg", "#E8F5EC")
    muted = C.get("muted", "#6B7280")
    line = C.get("line", "#E5E7EB")
    wash = C.get("wash", "#F7F9FC")

    def wrap(title, inner, badge=""):
        b = (f'<span class="c2b-badge">{badge}</span>' if badge else "")
        return (f'<div class="c2b"><div class="c2b-h">{title}{b}</div>'
                f'<div class="c2b-body">{inner}</div></div>')

    if cat == "hotel":
        chambres = _num(etude.get("chambres"))
        occ = _num(etude.get("occupation_pct"))
        piscine = etude.get("piscine")
        ch_txt = (f"{int(chambres)} chambres · " if chambres else "")
        occ_txt = (f"occupation ≈ {int(occ)} %" if occ else "occupation à confirmer")
        pool_txt = (" · piscine chauffée" if piscine else "")
        rows = (
            '<tr><td>Saison haute (été)</td><td>Climatisation + piscine à leur pic — '
            'production solaire maximale : alignement idéal.</td></tr>'
            '<tr><td>Saison basse</td><td>Base réduite (froid, éclairage, ECS) — '
            'le solaire couvre l\'essentiel de la journée.</td></tr>')
        inner = (
            f'<div class="c2b-meta">{ch_txt}{occ_txt}{pool_txt}</div>'
            f'<table class="c2b-tbl">{rows}</table>')
        return wrap("Saisonnalité hôtelière", inner, badge="Argument éco-OTA")

    if cat in ("restaurant", "commerce", "froid"):
        temp = _num(etude.get("temperature_consigne"))
        vol = _num(etude.get("volume_m3"))
        cf = _num(etude.get("chambres_froides"))
        det = []
        if cf:
            det.append(f"{int(cf)} chambres/meubles froids")
        if temp is not None:
            det.append(f"consigne {temp:g} °C")
        if vol:
            det.append(f"{int(vol)} m³")
        meta_txt = (" · ".join(det)) if det else "installation frigorifique"
        inner = (
            f'<div class="c2b-meta">{meta_txt}</div>'
            '<div class="c2b-li">Le solaire couvre la <b>base diurne</b> des groupes froids '
            '(le poste le plus lourd en journée).</div>'
            '<div class="c2b-li">Supervision + contrat O&amp;M : réduit le <b>risque de rupture</b> '
            'de la chaîne du froid.</div>')
        return wrap("Sécurisation de la chaîne du froid", inner)

    if cat == "boulangerie":
        four = etude.get("four")
        nocturne = etude.get("cuisson_nocturne")
        four_txt = (f"Four {four} · " if four else "")
        noct = ("Cuisson nocturne signalée : " if nocturne else "")
        inner = (
            f'<div class="c2b-meta">{four_txt}transparence sur la cuisson</div>'
            f'<div class="c2b-li">{noct}la <b>cuisson de nuit n\'est pas couverte</b> par le '
            'solaire sans stockage — nous ne le promettons pas.</div>'
            '<div class="c2b-li">Le solaire couvre le <b>froid, l\'éclairage et la '
            'climatisation de jour</b>.</div>')
        return wrap("Transparence sur la cuisson nocturne", inner)

    if cat == "ecole":
        internat = etude.get("internat")
        ete = etude.get("fermeture_estivale")
        eff = _num(etude.get("effectif"))
        eff_txt = (f"{int(eff)} élèves · " if eff else "")
        int_txt = ("internat" if internat else "externat")
        ete_line = (
            "Fermeture estivale : en juillet-août la production dépasse la "
            "consommation → <b>surplus injectable</b> (loi 82-21) selon éligibilité."
            if ete else
            "Hors période scolaire, le surplus de production est valorisable en "
            "<b>injection</b> (loi 82-21) selon éligibilité.")
        inner = (
            f'<div class="c2b-meta">{eff_txt}{int_txt}</div>'
            f'<div class="c2b-li">{ete_line}</div>'
            '<div class="c2b-li">Budget énergie <b>prévisible</b> sur l\'année scolaire.</div>')
        return wrap("Calendrier scolaire & injection", inner)

    if cat == "bureau":
        eff = _num(etude.get("effectif"))
        clim = etude.get("clim")
        eff_txt = (f"{int(eff)} postes · " if eff else "")
        clim_txt = ("climatisation centralisée" if clim else "climatisation locale")
        inner = (
            f'<div class="c2b-meta">{eff_txt}{clim_txt}</div>'
            '<div class="c2b-li">Vos heures de bureau (~9 h-18 h) <b>coïncident avec la '
            'production</b> solaire → autoconsommation élevée.</div>'
            '<div class="c2b-li">Peu d\'export : la quasi-totalité de l\'énergie est '
            'consommée sur place.</div>')
        return wrap("Alignement horaires / production", inner)

    # santé, hammam, autre → bloc générique honnête.
    inner = (
        '<div class="c2b-li">Le solaire couvre la <b>consommation diurne</b> de votre '
        'établissement (froid, éclairage, climatisation) en autoconsommation.</div>'
        '<div class="c2b-li">La <b>pointe du soir/nuit</b> n\'est sécurisée qu\'avec un '
        'stockage — non promise ici sans batterie.</div>')
    return wrap("Votre profil de consommation", inner)
