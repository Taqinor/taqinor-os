"""AGR110 — LA table unique des hypothèses de pompage, chacune avec sa source.

Avant : le rendement groupe valait 0,5 « EST. » à l'écran (``solar.js``) mais
0,55/0,50 sur le site (``estimatorAgricole.ts``) ; le bassin 2× au serveur mais
1× sur le site — un même projet pouvait afficher deux puissances de pompe et
deux bassins (C2-18). Ici, UNE table : chaque entrée porte sa valeur, son
statut et sa source, et c'est la SEULE origine des constantes du moteur
``core.pompage``, de la réponse d'aperçu (``hypotheses`` du contrat
``etude_pompage_preview.json``) et de l'estimateur du site (AGW409, via
l'échantillon ``apps/ventes/contract_samples/hypotheses_pompage.json``, tenu
ÉGAL à :func:`export` par ``core/tests/test_agr110_hypotheses_pompage.py``).

Statuts : ``physique`` (constante physique) | ``source`` (source primaire
citée) | ``source_secondaire`` (citée de seconde main) | ``EST.`` (estimation
explicite, plage citée).
Usages : ``calcul`` | ``controle_conception`` | ``alerte`` | ``indication`` —
une entrée ``indication`` n'est JAMAIS la valeur par défaut d'un réglage.

NE PAS FAIRE (Groupe AGR) : AUCUN multiplicateur de bassin, AUCUN derate empilé
sur PVGIS (ses 14 % de pertes sont déjà compris), AUCUN seuil non sourcé.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple, Union

#: Version de l'export (champ ``version`` de ``hypotheses_pompage.json``).
VERSION_HYPOTHESES = 1

STATUTS = frozenset({"physique", "source", "source_secondaire", "EST."})
USAGES = frozenset({"calcul", "controle_conception", "alerte", "indication"})


@dataclass(frozen=True)
class Plage:
    """Une plage {min, max} (bornes incluses)."""

    min: float
    max: float

    def en_dict(self):
        return {"min": self.min, "max": self.max}


@dataclass(frozen=True)
class Hypothese:
    cle: str
    valeur: Union[float, int, Plage, Tuple[float, ...]]
    statut: str
    source: str
    usage: str
    # AGQ12 (C-AGQ-011) — ce que le CLIENT lit dans l'annexe (fr/en/ar) :
    # un libellé et une source publique (jamais un chemin du dépôt, un id de
    # tâche ni une décision interne) ; ``source`` reste la trace interne.
    libelle: Dict[str, str]
    source_client: Dict[str, str]

    def en_dict(self):
        if isinstance(self.valeur, Plage):
            valeur = self.valeur.en_dict()
        elif isinstance(self.valeur, tuple):
            valeur = list(self.valeur)
        else:
            valeur = self.valeur
        return {"cle": self.cle, "valeur": valeur, "statut": self.statut,
                "source": self.source, "usage": self.usage,
                "libelle": dict(self.libelle),
                "source_client": dict(self.source_client)}


def _t3(fr, en, ar):
    """AGQ12 — textes CLIENT fr/en/ar d'une entrée (libellé, source publique)."""
    return {"fr": fr, "en": en, "ar": ar}


TABLE = (
    Hypothese(
        cle="energie_hydraulique_wh_par_m3_m",
        valeur=2.725,
        statut="physique",
        source="ρ·g/3600 (ρ = 1000 kg/m³, g = 9,81 m/s²)",
        usage="calcul",
        libelle=_t3(
            'Énergie hydraulique par m³ et par mètre de hauteur (Wh)',
            'Hydraulic energy per m³ and per metre of head (Wh)',
            'الطاقة الهيدروليكية لكل م³ ولكل متر ارتفاع (واط·س)'),
        source_client=_t3(
            "Constante physique : masse volumique de l'eau × gravité (1 000 kg/m³ × 9,81 m/s²)",
            'Physical constant: water density × gravity (1,000 kg/m³ × 9.81 m/s²)',
            'ثابت فيزيائي: كثافة الماء × الجاذبية (1000 كغ/م³ × 9,81 م/ث²)'),
    ),
    Hypothese(
        cle="cv_vers_kw",
        valeur=0.7355,
        statut="physique",
        source="1 CV (cheval-vapeur métrique) = 735,5 W",
        usage="calcul",
        libelle=_t3(
            'Conversion cheval-vapeur → kilowatt',
            'Metric horsepower to kilowatt conversion',
            'تحويل الحصان البخاري إلى كيلوواط'),
        source_client=_t3(
            '1 CV métrique = 735,5 W (définition)',
            '1 metric hp = 735.5 W (definition)',
            '1 حصان متري = 735,5 واط (تعريف)'),
    ),
    Hypothese(
        cle="kw_moteur_normalises",
        valeur=(0.75, 1.1, 1.5, 2.2, 3, 4, 5.5, 7.5, 11, 15, 18.5, 22, 30,
                37, 45, 55, 75),
        statut="source",
        source=("IEC 60034-1 — puissances assignées normalisées des moteurs "
                "électriques (0,75 à 75 kW) : le kW d'une pompe connue par son "
                "seul CV est arrondi à la plus proche de ces puissances "
                "(AGQ6)"),
        usage="calcul",
        libelle=_t3(
            'Puissances normalisées des moteurs électriques (kW)',
            'Standard rated powers of electric motors (kW)',
            'القدرات المعيارية للمحركات الكهربائية (كيلوواط)'),
        source_client=_t3(
            'Norme IEC 60034-1 (puissances assignées de 0,75 à 75 kW)',
            'IEC 60034-1 standard (rated powers from 0.75 to 75 kW)',
            'المعيار IEC 60034-1 (قدرات مقننة من 0,75 إلى 75 كيلوواط)'),
    ),
    Hypothese(
        cle="rendement_groupe",
        valeur=0.35,
        statut="EST.",
        source=(
            "borne basse de la plage AMEE 0,35-0,55, Guide PSIA, PDF du 14/01/2019 (décision fondateur 03/10/2026 : "
            "seule valeur qui tient AMEE et SPIS à ± 20 %)"
        ),
        usage="calcul",
        libelle=_t3(
            'Rendement du groupe moto-pompe',
            'Motor-pump unit efficiency',
            'مردود مجموعة المحرك والمضخة'),
        source_client=_t3(
            ('Estimation prudente : borne basse de la plage 0,35 – 0,55 du guide AMEE sur le '
             'pompage solaire (2019)'),
            'Conservative estimate: low end of the 0.35 – 0.55 range of the AMEE solar pumping guide (2019)',
            'تقدير حذر: الحد الأدنى لمجال 0,35 – 0,55 في دليل AMEE للضخ الشمسي (2019)'),
    ),
    Hypothese(
        cle="ratio_champ_pompe_bande_alerte",
        valeur=Plage(1.2, 1.5),
        statut="source",
        source=("docs/superpowers/specs/"
                "2026-06-24-agricole-quote-redesign-design.md:58"),
        usage="alerte",
        libelle=_t3(
            'Rapport puissance du champ solaire / puissance de la pompe (bande usuelle)',
            'Solar array to pump power ratio (usual band)',
            'نسبة قدرة الحقل الشمسي إلى قدرة المضخة (المجال المعتاد)'),
        source_client=_t3(
            ('Règle de dimensionnement de la société : un champ de 1,2 à 1,5 fois la puissance de '
             'la pompe ; en dehors, le document le signale'),
            ('Company sizing rule: an array of 1.2 to 1.5 times the pump power; outside this band '
             'the document says so'),
            'قاعدة التحجيم لدى الشركة: حقل بين 1,2 و1,5 مرة قدرة المضخة؛ وخارج ذلك يذكره المستند'),
    ),
    Hypothese(
        cle="hazen_williams_c_pvc_pehd",
        valeur=150,
        statut="source",
        source="bulletin IPEX mis en ligne 08/2022 ; AWWA M23",
        usage="calcul",
        libelle=_t3(
            'Coefficient de rugosité des conduites PVC / PEHD (Hazen-Williams)',
            'Roughness coefficient of PVC / HDPE pipes (Hazen-Williams)',
            'معامل خشونة أنابيب PVC / PEHD (هازن-ويليامز)'),
        source_client=_t3(
            'Bulletin technique IPEX (2022) et manuel AWWA M23',
            'IPEX technical bulletin (2022) and AWWA M23 manual',
            'النشرة التقنية IPEX (2022) ودليل AWWA M23'),
    ),
    Hypothese(
        cle="pertes_pvgis_comprises_pct",
        valeur=14,
        statut="source",
        source=("backend/django_core/apps/parametres/pvgis_profils.py:128 "
                "(PVGIS_LOSS_PCT) — déjà comprises : AUCUN derate "
                "supplémentaire (les 0,82-0,90 de Water Mission sont "
                "refusés : double comptage)"),
        usage="calcul",
        libelle=_t3(
            'Pertes du système photovoltaïque déjà comprises dans la production PVGIS (%)',
            'Photovoltaic system losses already included in the PVGIS yield (%)',
            'خسائر النظام الكهروضوئي المحتسبة مسبقًا في إنتاج PVGIS (%)'),
        source_client=_t3(
            ("Réglage de pertes de l'outil PVGIS (Commission européenne) utilisé pour la "
             "production ; aucune perte n'est comptée deux fois"),
            ('Loss setting of the PVGIS tool (European Commission) used for the yield; no loss is '
             'counted twice'),
            'إعداد الخسائر في أداة PVGIS (المفوضية الأوروبية) المستعملة للإنتاج؛ لا تُحتسب أي خسارة مرتين'),
    ),
    Hypothese(
        cle="tolerance_conception_pct",
        valeur=Plage(-5, 20),
        statut="source_secondaire",
        source=("Water Mission 2019 citant IEC 62253:2011 (texte de la norme "
                "non lu) — contrôle de conception et affichage seulement, "
                "JAMAIS un seuil de recette (AGR606 : réglage société sans "
                "défaut)"),
        usage="controle_conception",
        libelle=_t3(
            'Tolérance de conception entre besoin et volume livré (%)',
            'Design tolerance between need and delivered volume (%)',
            'هامش التصميم بين الحاجة والحجم المُسلَّم (%)'),
        source_client=_t3(
            ("Pratique Water Mission (2019) d'après la norme IEC 62253 ; sert au contrôle de "
             "conception et à l'affichage, jamais de seuil de réception"),
            ('Water Mission practice (2019) after the IEC 62253 standard; used for design checks '
             'and display, never as an acceptance threshold'),
            ('ممارسة Water Mission (2019) وفق المعيار IEC 62253؛ تُستعمل لمراقبة التصميم والعرض '
             'وليست عتبة استلام')),
    ),
    Hypothese(
        cle="part_debit_essai_pct",
        valeur=Plage(80, 90),
        statut="source",
        source=("Water Mission 2021 — indication à côté du réglage société "
                "AGR107, jamais un défaut"),
        usage="indication",
        libelle=_t3(
            "Part du débit nominal attendue à l'essai de mise en service (%)",
            'Share of rated flow expected at the commissioning test (%)',
            'حصة الصبيب الاسمي المنتظرة في اختبار التشغيل (%)'),
        source_client=_t3(
            'Indication Water Mission (2021), à côté du réglage de la société ; jamais un défaut',
            'Water Mission indication (2021), beside the company setting; never a default',
            'إشارة Water Mission (2021) بجانب إعداد الشركة؛ وليست قيمة افتراضية'),
    ),
    Hypothese(
        cle="pression_goutte_a_goutte_bar",
        valeur=Plage(1.5, 3),
        statut="source",
        source="AMEE — indication à côté de la saisie, jamais un défaut",
        usage="indication",
        libelle=_t3(
            "Pression de service d'une irrigation goutte-à-goutte (bar)",
            'Operating pressure of a drip irrigation system (bar)',
            'ضغط التشغيل لنظام الري بالتنقيط (بار)'),
        source_client=_t3(
            'Guide AMEE sur le pompage solaire ; indication à côté de la saisie, jamais un défaut',
            'AMEE solar pumping guide; indication beside the entry, never a default',
            'دليل AMEE للضخ الشمسي؛ إشارة بجانب الإدخال وليست قيمة افتراضية'),
    ),
)


def hypothese(cle):
    """L'entrée ``cle`` de la table (``KeyError`` si elle n'existe pas)."""
    for entree in TABLE:
        if entree.cle == cle:
            return entree
    raise KeyError(cle)


def valeur(cle):
    """La valeur brute d'une hypothèse (une :class:`Plage` pour une plage)."""
    return hypothese(cle).valeur


def table():
    """La table entière, en dicts NEUFS (l'appelant peut les muter)."""
    return [entree.en_dict() for entree in TABLE]


def utilisees(cles):
    """Les entrées effectivement utilisées par un calcul, dans l'ordre de la
    table, recopiées telles quelles (``hypotheses`` de la réponse d'aperçu)."""
    voulues = set(cles)
    return [entree.en_dict() for entree in TABLE if entree.cle in voulues]


def export():
    """L'export complet — ÉGAL à ``exemple`` de ``hypotheses_pompage.json``."""
    return {"version": VERSION_HYPOTHESES, "hypotheses": table()}
