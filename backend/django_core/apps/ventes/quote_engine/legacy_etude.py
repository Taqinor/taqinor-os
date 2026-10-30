# flake8: noqa
# D-ENF22 : exception de fichier entier signée — moteur de devis vendoré (règle #4 de CLAUDE.md), non réécrit pour le lint.
"""SPL169 — page d'ÉTUDE du moteur legacy et ses gardes d'optimum (move only).

Déplacés tels quels de ``generate_devis_premium.py`` : ``make_chart_etude``, le
bloc bancable PV77 (``_BANKABLE_POSTES_FR``, ``_bankable_pct``,
``_bankable_decrit_ce_champ``, ``_bankable_concorde_avec_la_page``,
``_bankable_block_html``), les capacités batterie vendues, les gardes
d'optimum (``TOLERANCE_CAPACITE_KWH``, ``_branche_nommee`` / ``_branche_phrase``,
``_config_identifiante``, ``_decrit``, ``_optimum_decrit_ce_devis``,
``_falaise_context``, ``_part_glitch_pct``), ``_phrase_methode_etude`` /
``_libelle_avec_minuscule`` (nés après le plan, lus par ce seul groupe) et
``page_etude`` — groupe clos : seuls ``build_html`` (→ ``page_etude``) et
``legacy_onepage.page_onepage`` (→ ``_falaise_context``) l'appellent, par import
LOCAL. ``TOLERANCE_KWC_SIMULATION`` / ``TOLERANCE_PRODUCTION_PAGE`` (imports de
``bankable``) restent liés dans ``generate_devis_premium``.

LIAISON TARDIVE (même règle que ``legacy_onepage``) : toute référence à un nom
de niveau module de ``generate_devis_premium`` s'écrit ``_g.NOM``. Seule
réécriture en plus : ``globals().get("ETUDE")`` devient
``getattr(_g, "ETUDE", None)`` — déplacée telle quelle, elle lirait le
dictionnaire de CE module, rendrait toujours True et désactiverait en silence
la garde PV77. Rendu seulement (règle #4).
"""
from . import generate_devis_premium as _g


#: ERR-RHOR8-PDF-AR-PAGES-ETUDE — interligne du document COMPLET arabe : celui
#: de « DM Sans » (ascendante 0,992 + descendante 0,310 em, sans interligne
#: ajouté), la police des documents fr/en.
INTERLIGNE_DM_SANS = "1.302"


def css_document_arabe():
    """ERR-RHOR8-PDF-AR-PAGES-ETUDE — CSS arabe du document COMPLET de ce
    moteur (cas résidentiel « + étude », C&I hérité) : la CSS arabe partagée
    (``_g._css_arabe``, inchangée) + l'interligne de « DM Sans ».

    Cause mesurée (devis 2007 / 2300 du rejeu RHOR8) : ``document=True`` pose
    « Noto Sans Arabic » sur TOUT le document ; son interligne ``normal``
    (≈ 1,7 em, contre 1,3 pour DM Sans) gonflait chaque ligne des tableaux
    d'équipements, le bloc ``flex-shrink:0`` de la page 2 ne tenait plus sous
    son en-tête et WeasyPrint fragmentait la page en trois feuilles (en-tête
    seul, tableaux, graphes) : 5 pages en arabe contre 3/4 en fr/en. Les
    interlignes posés explicitement par le gabarit restent les leurs. Le
    une-page (``legacy_onepage``, densité adaptative) n'est pas concerné."""
    return _g._css_arabe() + "body{line-height:%s;}" % INTERLIGNE_DM_SANS


# \u2500\u2500 \u00c9TUDE PAGE (mode Industriel/Commercial \u2014 autoconsommation) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def make_chart_etude(prod_m, conso_m):
    """Monthly production vs consumption chart for the \u00e9tude page."""
    fig, ax = _g.plt.subplots(figsize=(8.6, 2.6), dpi=150)
    fig.patch.set_facecolor("white"); ax.set_facecolor("white")
    x = list(range(12))
    ax.bar(x, conso_m, 0.60, color="#B5C0CE", alpha=0.65, zorder=2,
           linewidth=0, label="Consommation (kWh)")
    ax.plot(x, prod_m, color=_g.CA, linewidth=2.2, marker="o", markersize=5.5,
            markerfacecolor="white", markeredgewidth=1.8, markeredgecolor=_g.CA,
            zorder=4, solid_capstyle="round", label="Production PV (kWh)")
    ax.set_xticks(x); ax.set_xticklabels(_g.MONTHS, fontsize=9, color="#374151")
    ax.tick_params(axis="x", length=0, pad=5)
    ax.tick_params(axis="y", colors="#9BA3AE", labelsize=8)
    ax.set_ylabel("kWh / mois", fontsize=9, color="#9BA3AE", labelpad=6)
    ax.grid(axis="y", color="#F0F2F5", linewidth=0.65, zorder=0)
    ax.grid(axis="x", visible=False); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=8.5, frameon=True, loc="upper left",
              edgecolor="#E5E7EB", facecolor="white")
    _g.plt.tight_layout(pad=0.4)
    buf = _g.io.BytesIO()
    _g.plt.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    _g.plt.close(fig)
    return _g.b64(buf)


# \u2500\u2500 PV77 \u2014 \u00e9tude bancable (P50/P90 + cascade de pertes) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
# Libell\u00e9s FR des postes de perte du mod\u00e8le PR (apps.ventes.solar_design). Un
# poste inconnu garde sa cl\u00e9 (\u00e9chapp\u00e9e) : jamais de libell\u00e9 invent\u00e9.
_BANKABLE_POSTES_FR = {
    "temperature": "Temp\u00e9rature",
    "soiling": "Salissures",
    "shading": "Ombrage",
    "wiring": "C\u00e2blage",
    "inverter": "Onduleur",
    "mismatch": "Dispersion modules",
    "availability": "Disponibilit\u00e9",
    "lid": "LID (1re ann\u00e9e)",
    "reflection": "R\u00e9flexion (IAM)",
}


def _bankable_pct(valeur):
    """Pourcentage FR \u00e0 une d\u00e9cimale (\u00ab 8,0 \u00bb) ; illisible/absent \u2192 ''."""
    try:
        return f"{float(valeur):.1f}".replace(".", ",")
    except (TypeError, ValueError):
        return ""


def _bankable_decrit_ce_champ(bank):
    """QJR159 (b) — la simulation décrit-elle le champ PV RÉELLEMENT vendu ?

    La preuve est la seule dont on dispose sans recalculer quoi que ce soit :
    la somme des ``kwc`` des zones simulées doit égaler la puissance crête du
    document. Tout ce qui n'est pas prouvé — puissance du devis inconnue,
    zones absentes ou illisibles — rend ``False`` et le bloc est OMIS (jamais
    un productible de repli).
    """
    # AMOT35 — LA règle partagée (``bankable.decrit_le_champ``).
    from .bankable import decrit_le_champ
    if _g.PUISSANCE_INCONNUE:
        return False
    return decrit_le_champ(bank, _g.KWC)


def _bankable_concorde_avec_la_page(bank):
    """QJR115 \u2014 la P50 bancable dit-elle la M\u00caME production que la carte ?

    La page \u00c9tude imprime deux fois la production annuelle de la M\u00caME
    installation : la carte \u00ab Production annuelle \u00bb (``ETUDE
    ['production_annuelle']``, figure canonique du document \u2014 \u00e9tude saisie ou
    calepinage recal\u00e9) et, juste en dessous, \u00ab Production P50 (m\u00e9diane) \u00bb du
    bloc bancable (``etude_params['simulation']``, jou\u00e9 par ``apps.ventes.
    etude``). QJR114 a fait converger les deux CHA\u00ceNES de calcul (plus de
    double derate : la P50 vaut d\u00e9sormais ``productible \u00d7 PRODUCTION_DERATE``,
    la formule m\u00eame de ``pricing``) \u2014 mais rien n'oblige les deux SOURCES \u00e0
    d\u00e9crire le m\u00eame devis : le builder recopie ``simulation`` sans condition et
    cette cl\u00e9 ne fait pas partie des \u00e9tudes rafra\u00eechies, donc une \u00e9tude jou\u00e9e
    avant un redimensionnement (ou une production saisie \u00e0 la main) remet deux
    nombres contradictoires c\u00f4te \u00e0 c\u00f4te sur la feuille.

    On ne r\u00e9concilie rien ici \u2014 le moteur de rendu ne calcule aucune
    production : on PROUVE l'\u00e9galit\u00e9, et \u00e0 d\u00e9faut de preuve le bloc est OMIS
    (r\u00e8gle fondateur : omettre plut\u00f4t que publier deux v\u00e9rit\u00e9s).

    Rend ``True`` quand il n'y a rien \u00e0 contredire : page sans carte
    \u00ab Production annuelle \u00bb, ou bloc bancable sans P50 (il ne publie alors que
    la P90 \u2014 une autre grandeur, explicitement nomm\u00e9e \u2014 le ratio de performance
    et la cascade). Rend ``False`` d\u00e8s qu'un des deux nombres est illisible :
    l'\u00e9galit\u00e9 n'est pas prouv\u00e9e.
    """
    # ``ETUDE`` n'est écrite que par ``apply_quote_data`` : avant toute
    # ingestion le nom n'existe PAS dans le module (les tests unitaires du
    # bloc l'appellent dans cet état). Sans étude ingérée il n'y a pas de carte
    # « Production annuelle », donc rien à contredire.
    etude_page = getattr(_g, "ETUDE", None)
    prod_page = (etude_page.get("production_annuelle")
                 if isinstance(etude_page, dict) else None)
    # AMOT35 — LA règle partagée (``bankable.concorde_avec_la_production``).
    from .bankable import concorde_avec_la_production
    return concorde_avec_la_production(bank, prod_page)


def _bankable_block_html(bank):
    """PV77 \u2014 bloc ADDITIF de l'\u00e9tude bancable, DANS la page \u00c9tude existante.

    Rend une ligne compacte P50/P90 (+ ratio de performance) et la cascade des
    pertes du mod\u00e8le PR, en fran\u00e7ais. Le bloc vit \u00e0 l'INT\u00c9RIEUR de la page \u00c9tude
    (``.page`` est \u00e0 hauteur fixe) : il ne peut donc jamais changer le nombre de
    pages du document. Aucun montant, aucune VAN/TRI, aucun prix d'achat n'y
    figure (r\u00e8gle #4) \u2014 uniquement des grandeurs \u00e9nerg\u00e9tiques.

    Absent/illisible \u2192 '' : la page \u00c9tude reste EXACTEMENT celle d'aujourd'hui.

    QJR159 (b) \u2014 CE BLOC PROUVE QU'IL D\u00c9CRIT LE CHAMP PV VENDU. Il \u00e9tait publi\u00e9
    sans le moindre lien avec la composition : il n'acc\u00e9dait ni \u00e0 ``KWC`` ni \u00e0
    ``NB_PAN``, le builder recopie ``etude_params['simulation']`` SANS
    condition, et cette cl\u00e9 ne fait pas partie des \u00e9tudes rafra\u00eechies \u2014 un
    devis redimensionn\u00e9 APR\u00c8S l'\u00e9tude imprimait donc le productible d'un AUTRE
    champ PV juste \u00e0 c\u00f4t\u00e9 de sa vraie \u00ab Puissance cr\u00eate \u00bb. La somme des kWc des
    zones simul\u00e9es doit d\u00e9sormais \u00e9galer ``KWC`` (\u00e0 la tol\u00e9rance d'arrondi),
    sinon le bloc est OMIS.

    QJR115 \u2014 ET IL DIT LA M\u00caME PRODUCTION QUE LA CARTE JUSTE AU-DESSUS. D\u00e9crire
    le bon champ PV ne suffit pas : la page publie d\u00e9j\u00e0 \u00ab Production annuelle \u00bb
    depuis une AUTRE source. Le bloc n'est servi que si sa P50 co\u00efncide avec
    elle (``_bankable_concorde_avec_la_page``) \u2014 sinon la feuille porterait
    deux productions contradictoires pour une seule installation.
    """
    if not isinstance(bank, dict) or not bank:
        return ""
    # AMOT35 — ``bankable.bankable_imprimable`` (via les deux lecteurs du
    # module, qui gardent les globaux de rendu KWC / ETUDE hors de la règle).
    if not _bankable_decrit_ce_champ(bank):
        return ""
    if not _bankable_concorde_avec_la_page(bank):
        return ""
    pr = bank.get("pr") if isinstance(bank.get("pr"), dict) else {}

    morceaux = []
    p50 = pr.get("p50_kwh")
    if p50 not in (None, ""):
        morceaux.append(
            _g._L("lg_p50").format(v=_g.fnum(p50)))
    p90 = pr.get("p90_kwh")
    if p90 not in (None, ""):
        morceaux.append(
            _g._L("lg_p90").format(v=_g.fnum(p90)))
    ratio = pr.get("performance_ratio")
    try:
        if ratio not in (None, ""):
            morceaux.append(
                _g._L("lg_ratio_perf").format(v=_bankable_pct(float(ratio) * 100.0)))
    except (TypeError, ValueError):
        pass
    ligne = " \u00b7 ".join(morceaux)

    pertes = pr.get("loss_breakdown")
    puces = []
    if isinstance(pertes, dict):
        lisibles = []
        for poste, pct in pertes.items():
            texte = _bankable_pct(pct)
            if not texte:
                continue
            try:
                lisibles.append((float(pct), poste, texte))
            except (TypeError, ValueError):
                continue
        for _val, poste, texte in sorted(lisibles, key=lambda x: -x[0]):
            libelle = (_g._L(f"lg_poste_{poste}") if str(poste) in _BANKABLE_POSTES_FR
                       else _g._esc(poste))
            puces.append(
                f'<span style="display:inline-block;background:{_g.CG1};'
                f'border:1px solid {_g.CG2};border-radius:9px;padding:1px 6px;'
                f'margin:0 4px 3px 0;">{libelle}\u00a0{texte}\u00a0%</span>')
    total = _bankable_pct(pr.get("total_loss_pct"))
    if total:
        puces.append(
            f'<span style="display:inline-block;border-radius:9px;'
            f'padding:1px 6px;margin:0 4px 3px 0;color:{_g.CN};font-weight:700;">'
            f'{_g._L("lg_total_pct").format(v=total)}</span>')

    if not ligne and not puces:
        return ""

    ligne_html = (f'<div style="font-size:8pt;color:{_g.CN};">{ligne}</div>'
                  if ligne else "")
    pertes_html = (
        f'<div style="font-size:6.5pt;color:{_g.CG4};margin-top:5px;">'
        f'{_g._L("lg_cascade")}{"".join(puces)}</div>') if puces else ""
    return (
        f'<div style="background:white;border:1px solid {_g.CG2};'
        f'border-left:4px solid {_g.CA};border-radius:6px;padding:9px 12px;'
        f'margin-top:9px;">'
        f'<div style="font-size:5.5pt;letter-spacing:1.2px;color:{_g.CG4};'
        f'text-transform:uppercase;margin-bottom:4px;">'
        f'{_g._L("lg_bancable_titre")}</div>'
        f'{ligne_html}{pertes_html}</div>')


def _capacite_batterie_vendue():
    """QJR13 — capacité batterie (kWh) de la configuration que CE document vend.

    ``BATTERIE_KWH_TOTAL`` décrit l'option AVEC batterie. Quand le document ne
    chiffre QUE la branche SANS (``ONEPAGE_BRANCHE == 'sans'`` — format une
    page d'un devis sans alternative, scénario « Sans batterie »), la
    configuration facturée ne porte aucune batterie : la capacité vendue est
    alors 0, pas celle d'une option que ce document ne vend pas.
    """
    if _g.ONEPAGE_BRANCHE == "sans":
        return 0.0
    return float(_g.BATTERIE_KWH_TOTAL or 0.0)


def _capacite_batterie_utile_vendue():
    """QJR609 — la même configuration que :func:`_capacite_batterie_vendue`,
    mesurée en kWh UTILES (la grandeur des optimums du moteur et de la garde
    web). La valeur utile n'est retenue que pour le nominal qu'elle
    accompagne ; sinon (donnée absente ou d'un autre document), le nominal."""
    nominal = _capacite_batterie_vendue()
    if nominal <= 0:
        return nominal
    couple = _g.BATTERIE_KWH_UTILE_VENDUE
    if (isinstance(couple, tuple) and len(couple) == 2
            and abs(couple[0] - float(_g.BATTERIE_KWH_TOTAL or 0.0)) < 1e-9
            and couple[1] > 0):
        return couple[1]
    return nominal


#: QJR104 — tolérance de comparaison des capacités batterie, en kWh. MÊME
#: nombre que ``apps.ventes.dimensionnement.TOLERANCE_CAPACITE_KWH`` : un
#: arrondi d'affichage n'est pas un écart de palier.
TOLERANCE_CAPACITE_KWH = 0.05


def _branche_nommee():
    """QJR159 (c) — suffixe qui NOMME la branche décrite, ou ''.

    ``_capacite_batterie_vendue`` suit ``ONEPAGE_BRANCHE``, que le builder fixe
    à ``'avec'`` pour TOUT devis à deux options — y compris en
    ``pdf_mode='full'``. La garde QJR13 prouve donc l'appartenance à l'option
    AVEC sans jamais l'ÉCRIRE : sur un 3-pages qui présente les deux options,
    le client qui choisit « sans batterie » lisait un résiduel qui n'est pas le
    sien. On le dit dans le libellé.
    """
    if _g.SCENARIO != "Les deux (Sans + Avec)":
        return ""
    if _capacite_batterie_vendue() <= 0:
        return ""
    return _g._L("lg_branche_option").format(option=_libelle_avec_minuscule())


def _branche_phrase():
    """QJR159 (c) — la MÊME précision, en incise dans une phrase."""
    return (_g._L("lg_branche_incise").format(option=_libelle_avec_minuscule())
            if _branche_nommee() else "")


def _phrase_methode_etude():
    """AMOT22 (C-AMOT-020) — la phrase de méthode de la page « Étude »,
    composée depuis le DEVIS : ville de calcul (omise sans ville), phases
    seulement si les lignes d'onduleur les portent, « sans batterie » seulement
    pour un document sans batterie ; jamais une affirmation technique fixe
    (« irradiation moyenne du Maroc », « onduleur réseau, triphasé »)."""
    debut = "lg_methode_etude_ville" if _g.VILLE_CALCUL else "lg_methode_etude"
    precisions = []
    if _g.SCENARIO == "Sans batterie" or _capacite_batterie_vendue() <= 0:
        precisions.append(_g.i18n_labels.nom_option("Sans batterie", _g.LANGUE_SORTIE, minuscule=True))
    noms = " ".join(str(it.get("designation") or "").lower()
                    for it in list(_g.SANS_ITEMS) + list(_g.AVEC_ITEMS)
                    if _g.is_inverter(str(it.get("designation") or "")))
    if "triphas" in noms and "monophas" not in noms:
        precisions.append(_g._L("lg_racc_tri"))
    elif "monophas" in noms and "triphas" not in noms:
        precisions.append(_g._L("lg_racc_mono"))
    phrase = _g._L(debut).format(ville=_g._esc(_g.VILLE_CALCUL),
                              mode=_g.i18n_labels.nom_option(_g.INST_TYPE, _g.LANGUE_SORTIE))
    if precisions:
        phrase += " \u2014 " + ", ".join(precisions)
    return phrase + "."


def _libelle_avec_minuscule():
    """AMOT21 — le libellé serveur de l'option 2, en incise (« avec
    batterie » / « hybride, batterie plus tard »)."""
    return _g.i18n_labels.nom_option(_g.LIBELLE_AVEC, _g.LANGUE_SORTIE, minuscule=True)


def _config_identifiante(panneaux, batterie_kwh):
    """QJR104 — la CONFIGURATION IDENTIFIANTE d'une installation, ou ``None``.

    Deux nombres et deux seulement : le compte de panneaux et la capacité
    batterie. ``None`` dès que l'un des deux n'est pas lisible — un booléen
    est refusé explicitement (en Python ``int(True) == 1`` aurait fait passer
    un drapeau pour un compte de panneaux).
    """
    if isinstance(panneaux, bool) or not isinstance(panneaux, (int, float)):
        return None
    if (isinstance(batterie_kwh, bool)
            or not isinstance(batterie_kwh, (int, float))):
        return None
    return (int(panneaux), float(batterie_kwh))


def _decrit(config_optimum, config_vendue):
    """QJR104 — ``config_optimum`` décrit-elle bien l'installation VENDUE ?

    LA MÊME RÈGLE, MOT POUR MOT, que
    ``apps.ventes.dimensionnement.decrit`` : identité du compte de panneaux et
    égalité des capacités batterie à :data:`TOLERANCE_CAPACITE_KWH` près.

    POURQUOI UN JUMEAU, ET PAS UN IMPORT. Ce module est le moteur VENDORÉ : il
    n'importe RIEN de ``apps`` (voir ses imports — ``base64``, ``matplotlib``,
    et c'est tout) et il reste importable hors paquet. Lui faire importer
    ``apps.ventes.dimensionnement`` — qui cite ``apps.ventes.services`` — le
    rendrait indémarrable hors Django. Le jumeau est donc assumé, et il est
    ÉPINGLÉ : ``apps/ventes/tests/test_qjr_optimum_publie.py`` fait passer la
    MÊME table de cas dans les deux implémentations et exige le MÊME verdict —
    une divergence rougit au lieu de dormir dans un PDF client.
    """
    if config_optimum is None or config_vendue is None:
        return False
    if config_optimum[0] != config_vendue[0]:
        return False
    return abs(config_optimum[1] - config_vendue[1]) <= TOLERANCE_CAPACITE_KWH


def _optimum_decrit_ce_devis(combinaison):
    """QJR13 — ``combinaison`` (un optimum du moteur) décrit-elle CE devis ?

    Un dict d'optimum de dimensionnement (``meilleure_falaise``) porte SA
    configuration identifiante — ``panneaux``, ``kwc``, ``batterie_kwh`` : c'est
    une combinaison champ + stockage que le BALAYAGE a trouvée, sans aucun
    rapport garanti avec la taille et la batterie réellement vendues. Publier
    ses chiffres comme ceux « de ce dimensionnement » décrit au client une
    installation qu'il n'achète pas.

    Règle (zéro chiffre inventé, QJR104) : on ne publie que si la configuration
    de l'optimum ÉGALE la configuration vendue. Tout ce qui n'est pas prouvé —
    contrat malformé, compte de panneaux du devis inconnu, capacité illisible —
    rend ``False``, et l'appelant OMET la mention : jamais un chiffre de repli.
    """
    if not isinstance(combinaison, dict):
        return False
    if not _g.NB_PAN:  # configuration vendue inconnue ⇒ rien à prouver, on omet
        return False
    return _decrit(
        _config_identifiante(combinaison.get("panneaux"),
                             combinaison.get("batterie_kwh")),
        _config_identifiante(_g.NB_PAN, _capacite_batterie_utile_vendue()))


def _falaise_context():
    """CJ2b-bis — falaise tarifaire + remplissage batterie, lus À PLAT depuis
    ``etude_params['dimensionnement']`` (contrat DIM2 :
    ``apps.ventes.dimensionnement.recommander_taille`` / le même que sert
    ``POST /ventes/etude-horaire/preview/`` avec ``dimensionner: true`` — voir
    ``apps/ventes/contract_samples/etude_horaire.json``).

    QJR148 — CE BLOC EST LIVE. Cette docstring affirmait « à la date de ce
    lot, AUCUN devis réel ne porte cette clé » : c'est FAUX depuis T5
    (24/08/2026). ``services.rafraichir_dimensionnement_devis``
    (``apps/ventes/domain/etudes.py``) pose ``etude_params['dimensionnement']``
    sur les devis RÉSIDENTIELS, et ces chiffres atteignent de vrais clients.

    Deux choses à savoir avant d'y toucher :

    * le rafraîchisseur COURT-CIRCUITE quand l'empreinte des entrées concorde
      (QJR43) : le bloc servi peut décrire un état plus ancien du devis que la
      composition posée ;
    * ``_optimum_decrit_ce_devis`` (QJR13) est le SEUL rempart entre ce bloc et
      le document client : elle refuse de publier ``residuel_kwh_mois``,
      ``tranche_apres`` et ``remplissage.moyen`` quand l'optimum ne décrit pas
      la composition réellement vendue. Ne pas la relâcher, ne pas la
      « simplifier ».

    Clé absente ⇒ ``None`` ⇒ cette moitié de la page étude ne rend rien.
    Zero chiffre inventé : chaque valeur vient telle quelle du contrat, rien
    n'est recalculé ici (le moteur ne fait que RENDRE — règle #4).
    """
    dim = _g.ETUDE.get("dimensionnement")
    if not isinstance(dim, dict):
        return None
    falaise = dim.get("falaise")
    meilleure = dim.get("meilleure_falaise")
    tranche_actuelle = None
    if isinstance(falaise, dict):
        _ta = falaise.get("tranche_actuelle")
        if isinstance(_ta, dict):
            tranche_actuelle = _ta.get("libelle")
    residuel = tranche_apres = remplissage_pct = None
    # QJR13 — les trois valeurs ci-dessous décrivent la combinaison
    # ``meilleure_falaise`` du balayage, PAS le devis. Elles ne sont lues que
    # si cette combinaison est exactement la configuration vendue ; sinon la
    # carte et la phrase disparaissent (sur les DEUX formats, ce contexte étant
    # la source unique du 3-pages et du une-page). ``tranche_actuelle``, elle,
    # décrit la FACTURE ACTUELLE du client — vraie quel que soit le devis.
    if _optimum_decrit_ce_devis(meilleure):
        residuel = meilleure.get("residuel_kwh_mois")
        _tap = meilleure.get("tranche_apres")
        if isinstance(_tap, dict):
            tranche_apres = _tap.get("libelle")
        _rempl = meilleure.get("remplissage")
        if isinstance(_rempl, dict):
            _moyen = _rempl.get("moyen")
            if isinstance(_moyen, (int, float)):
                remplissage_pct = round(_moyen * 100)
    if tranche_actuelle is None and residuel is None:
        return None
    return {
        "tranche_actuelle": tranche_actuelle,
        "residuel_kwh_mois": residuel,
        "tranche_apres": tranche_apres,
        "remplissage_pct": remplissage_pct,
    }


def _part_glitch_pct():
    """CJ2b-bis — part des pointes (glitchs) rattrapée par la batterie, en %.

    Source RELLE et DÉJÀ PERSISTÉE (contrairement à ``_falaise_context``
    ci-dessus) : ``etude_params['etude_horaire']['annuel']`` est posé sur
    CHAQUE devis résidentiel par ``services.rafraichir_etude_horaire_devis``
    dès qu'un équipement à impulsions (piscine, clim…) est déclaré
    (``etude_horaire._finaliser_glitch``, clés ``part_glitch_*``). Le ratio
    rendu ici est une DIVISION de deux kWh annuels réels déjà calculés par
    le moteur — jamais un chiffre inventé : la part de l'énergie perdue en
    pointe (``part_glitch_sans_kwh``) que la batterie rattrape
    (``part_glitch_batterie_kwh``).

    QJR159 (a) — GARDE DE CONFIGURATION. Cette carte annonce le bénéfice d'un
    STOCKAGE : elle ne testait que ``_sans > 0``, ni ``BATTERIE_KWH_TOTAL``, ni
    ``_capacite_batterie_vendue()``, ni ``ONEPAGE_BRANCHE``. Sur un devis
    résidentiel SANS stockage mais avec un équipement à impulsions (piscine,
    clim), elle sortait « 0 % » et vendait le bénéfice d'un composant ABSENT du
    devis. La fonction jumelle existe précisément pour ce contrôle : on
    l'appelle.
    """
    if _capacite_batterie_vendue() <= 0:
        return None
    annuel = (_g.ETUDE.get("etude_horaire") or {}).get("annuel")
    if not isinstance(annuel, dict):
        return None
    _sans = annuel.get("part_glitch_sans_kwh")
    _batt = annuel.get("part_glitch_batterie_kwh")
    try:
        _sans = float(_sans)
        _batt = float(_batt)
    except (TypeError, ValueError):
        return None
    if _sans <= 0:
        return None
    return round(max(0.0, min(_batt, _sans)) / _sans * 100)


def etude_a_contenu():
    """RPDF20 \u2014 la page \u00c9tude porte-t-elle une VRAIE \u00e9tude ?

    Un devis r\u00e9sidentiel dont les \u00e9conomies viennent du mod\u00e8le horaire porte
    ``etude_params`` (``dimensionnement``, ``etude_horaire``) sans aucune \u00e9tude
    saisie : la page sortait avec la seule carte \u00ab Puissance cr\u00eate \u00bb (d\u00e9j\u00e0 en
    page 1) et la tranche actuelle (devis 1344 du 27/10, page 3 vide). M\u00eames
    conditions que ``page_etude`` pour chaque bloc ; ni la puissance ni la
    tranche actuelle seule ne suffisent. ``False`` \u21d2 la page n'est ni rendue ni
    compt\u00e9e (d\u00e9gradation 4 \u2192 3 pages de CLAUDE.md). Rendu seul (r\u00e8gle #4)."""
    e = getattr(_g, "ETUDE", None)
    if not isinstance(e, dict) or not e:
        return False
    if any(e.get(k) not in (None, "") for k in (
            "production_annuelle", "conso_annuelle", "prix_kwc", "economies_annuelles")):
        return True
    if len(e.get("prod_mensuelle") or []) == 12 and len(e.get("conso_mensuelle") or []) == 12:
        return True
    _ci = _g.CHIFFRES_CI if isinstance(_g.CHIFFRES_CI, dict) else None
    if _ci is not None and _ci.get("payback_ans") not in (None, ""):
        return True
    if _ci is None and e.get("payback") not in (None, ""):
        return True
    _f = _falaise_context() or {}
    if _f.get("residuel_kwh_mois") is not None or _f.get("remplissage_pct") is not None:
        return True
    return _part_glitch_pct() is not None or bool(_bankable_block_html(e.get("bankable")))


def etude_rendue():
    """RPDF20 \u2014 la page \u00c9tude est-elle rendue (et compt\u00e9e) ? Source unique du
    compte de pages (``apply_quote_data``) et du rendu (``build_html``)."""
    return bool(_g.INCLUDE_ETUDE and _g.ETUDE) and etude_a_contenu()


def page_etude():
    """\u00c9tude d'autoconsommation (industriel) : param\u00e8tres, taux, graphique."""
    e = _g.ETUDE
    prod_m = e.get("prod_mensuelle") or []
    conso_m = e.get("conso_mensuelle") or []
    img = (make_chart_etude(prod_m, conso_m)
           if len(prod_m) == 12 and len(conso_m) == 12 else "")

    def card(label, value, accent=False, fig=None):
        border = f"border-left:4px solid {_g.CA};" if accent else f"border-left:4px solid {_g.CG2};"
        _a = _g._ancre_figure(fig, value) if fig else ""
        return (f'<div style="flex:1;min-width:150px;border:1px solid {_g.CG2};{border}'
                f'border-radius:6px;padding:10px 12px;background:white;">'
                f'<div style="font-size:5.5pt;letter-spacing:1.2px;color:{_g.CG4};'
                f'text-transform:uppercase;margin-bottom:3px;">{label}</div>'
                f'<div class="serif" style="font-size:14pt;color:{_g.CN};">{value}</div>{_a}</div>')

    def _card_if(label, key, suffix="", accent=False, fig=None):
        """Card rendered ONLY when the value exists \u2014 a figure that cannot be
        computed is omitted entirely, never printed as a dash or a default."""
        v = e.get(key)
        if v in (None, ""):
            return ""
        return card(label, f"{v}{suffix}", accent=accent, fig=fig)

    # Sans consommation r\u00e9elle, les taux n'ont pas de sens : on les omet
    # (jamais d'\u00ab Autoconsommation 100 % \u00bb fabriqu\u00e9e).
    has_conso = e.get("conso_annuelle") not in (None, "", 0)
    cards1 = (
        card(_g._L("lg_puissance_crete"), f"{_g.kwc_fr(_g.KWC)}\u00a0kWc", accent=True,
             fig="puissance_kwc")
        + _card_if(_g._L("op_production_annuelle"), "production_annuelle", "\u00a0kWh",
                   fig="production_annuelle_kwh")
        + _card_if(_g._L("lg_conso_annuelle"), "conso_annuelle", "\u00a0kWh")
        + _card_if(_g._L("op_prix_par_kwc"), "prix_kwc", "\u00a0MAD")
    )
    # CIQ129 \u2014 les taux (et, en C&I, le retour) sont ceux du moteur C&I
    # (``CHIFFRES_CI`` = ``chiffres_cles(synthese_ci)``, la projection de la
    # couverture et de /proposition) : plus aucune cl\u00e9 d'\u00e9tude \u00e9cran v1. Hors
    # C&I, aucun taux d'\u00e9tude n'existe : cartes omises ; le retour reste celui
    # que le builder recalcule sur les totaux (QJR410).
    _ci = _g.CHIFFRES_CI if isinstance(_g.CHIFFRES_CI, dict) else None

    def _card_ci(label, cle, suffix, fig, accent=True):
        v = (_ci or {}).get(cle)
        if v in (None, ""):
            return ""
        return card(label, f"{v}{suffix}", accent=accent, fig=fig)

    cards2 = (
        (_card_ci(_g._L("lg_taux_autoconso"), "taux_autoconso_pct", "\u00a0%",
                  fig="autoconsommation_pct")
         if has_conso else "")
        + (_card_ci(_g._L("lg_taux_couverture"), "taux_couverture_pct", "\u00a0%",
                    fig="couverture_pct")
           if has_conso else "")
        + _card_if(_g._L("lg_eco_annuelles"), "economies_annuelles", "\u00a0MAD",
                   fig="economie_annuelle")
        + (_card_ci(_g._L("res_retour_invest"), "payback_ans", _g._L("lg_unite_ans"),
                    fig="payback_ans", accent=False)
           if _ci is not None else
           _card_if(_g._L("res_retour_invest"), "payback", _g._L("lg_unite_ans"),
                    fig="payback_ans"))
    )
    _rates_note = _g._L("lg_rates_note") if has_conso else ""
    # CJ2b-bis — falaise tarifaire / remplissage batterie / part des glitchs.
    # ADDITIF, comme le bloc bancable ci-dessous : absent des deux sources ⇒
    # '' → page BYTE-IDENTIQUE à avant ce lot (aucun des deux devis de test
    # existants ne change de rendu).
    _falaise_ctx = _falaise_context()
    _glitch_pct = _part_glitch_pct()
    # QJR159 (c) — la BRANCHE décrite est NOMMÉE : ces chiffres appartiennent à
    # l'option AVEC batterie sur un document qui présente les deux.
    _branche = _branche_nommee()
    falaise_cards = ""
    falaise_sentence = ""
    if _falaise_ctx or _glitch_pct is not None:
        _fcells = []
        if _falaise_ctx and _falaise_ctx.get("residuel_kwh_mois") is not None:
            _txt = _g._L("lg_kwh_mois").format(n=_g.fnum(_falaise_ctx['residuel_kwh_mois']))
            _fcells.append(card(_g._L("lg_residuel_marche").format(branche=_branche), _txt,
                                accent=True))
        if _falaise_ctx and _falaise_ctx.get("tranche_actuelle"):
            _fcells.append(
                card(_g._L("lg_tranche_actuelle"), _g._esc(_falaise_ctx["tranche_actuelle"])))
        if _falaise_ctx and _falaise_ctx.get("remplissage_pct") is not None:
            # Décision fondateur 24/08 — un ratio brut ≥ 100 % (le
            # générateur interne le montre tel quel) est ABSURDE côté
            # client : re-libellé en phrase qualitative, jamais un
            # pourcentage > 100 % ni un pourcentage plafonné inventé.
            _rpct = _falaise_ctx["remplissage_pct"]
            _rval = (_g._L("lg_batterie_remplit") if _rpct >= 100
                      else f"{_rpct} %")
            _fcells.append(
                card(_g._L("lg_remplissage").format(branche=_branche), _rval))
        if _glitch_pct is not None:
            _fcells.append(card(
                _g._L("lg_part_pointes").format(branche=_branche),
                f"{_glitch_pct} %"))
        if _fcells:
            falaise_cards = (
                f'<div style="display:flex;gap:9px;margin-top:9px;">'
                f'{"".join(_fcells)}</div>')
        if (_falaise_ctx and _falaise_ctx.get("tranche_actuelle")
                and _falaise_ctx.get("residuel_kwh_mois") is not None):
            _sous = (
                _g._L("lg_sous_marche").format(t=_g._esc(_falaise_ctx['tranche_apres']))
                if _falaise_ctx.get("tranche_apres") else "")
            falaise_sentence = (
                f'<div style="margin-top:8px;font-size:7pt;color:{_g.CG4};">'
                + _g._L("lg_falaise_phrase").format(
                    t=_g._esc(_falaise_ctx["tranche_actuelle"]), branche=_branche_phrase(),
                    n=_g.fnum(_falaise_ctx["residuel_kwh_mois"]), sous=_sous)
                + '</div>')
    # PV77 — bloc bancable ADDITIF : présent uniquement quand le devis porte
    # une simulation (etude_params['simulation']), sinon '' → page inchangée.
    bankable_html = _bankable_block_html(e.get("bankable"))
    chart_html = (
        f'<div style="background:{_g.CG1};border-radius:7px;padding:10px 12px;'
        f'border:1px solid {_g.CG2};margin-top:10px;">'
        f'<div style="font-size:7pt;font-weight:700;color:{_g.CN};text-transform:uppercase;'
        f'letter-spacing:.5px;margin-bottom:5px;">{_g._L("lg_chart_etude")}</div>'
        f'<img src="{img}" style="width:680px;height:200px;object-fit:contain;display:block;">'
        f'</div>'
    ) if img else ""

    return f"""
<div class="page">
  <div style="background:{_g.CN};padding:12px 24px;display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">
    <div>
      <div style="color:white;font-size:10pt;font-weight:700;">{_g._L("lg_etude_titre")}</div>
      <div style="color:rgba(255,255,255,0.45);font-size:7pt;margin-top:2px;">{_g._L("lg_devis_n_nbsp").format(ref=_g.REF)} \u2014 {_g.CLIENT_NAME} \u2014 {_g.DATE_STR}</div>
    </div>
    {_g.logo_html("entete")}
  </div>
  <div style="height:3px;background:{_g.CA};flex-shrink:0;"></div>

  <div style="padding:14px 24px;flex:1;min-height:0;">
    <div style="font-size:8pt;color:{_g.CG4};margin-bottom:10px;">
      {_phrase_methode_etude()}
    </div>
    <div style="display:flex;gap:9px;margin-bottom:9px;">{cards1}</div>
    <div style="display:flex;gap:9px;">{cards2}</div>
    {falaise_cards}
    {falaise_sentence}
    {bankable_html}
    {chart_html}
    <div style="margin-top:10px;font-size:6.5pt;color:{_g.CG4};font-style:italic;">
      {_rates_note}{_g._L("lg_estimations_nc")}
    </div>
  </div>

  <div style="background:{_g.CN};padding:6px 24px 5px;flex-shrink:0;display:flex;align-items:center;justify-content:space-between;">
    <div style="font-size:9pt;font-weight:800;color:{_g.CA};letter-spacing:1px;">{_g.ENT_NOM_MARQUE}</div>
    <div style="font-size:7pt;color:#888;">{_g.ENT_ETUDE_CONTACT}</div>
    <div style="font-size:7pt;color:#888;">{_g._L("lg_etude_pied").format(ref=_g.REF)}</div>
  </div>
</div>
"""
