"""Seed starter SOP/template KB articles for solar installation procedures.

Creates a set of French-language internal knowledge-base articles covering:
  - Installation procedure SOP (résidentiel, industriel/commercial, pompage)
  - Dossier de raccordement ONEE checklist
  - Dossier loi 82-21 autoconsommation checklist

Articles are generic labelled placeholders/checklists that the founder edits
later — no regulatory specifics are invented. Content is intentionally concise
and clearly marked as templates.

Idempotent and strictly additive — modelled on ``seed_itp_solaire``:
  * each article is matched by the stable key ``(company, titre)`` via
    ``get_or_create`` — re-running creates no duplicates;
  * an article already present (even with edited fields) is left untouched;
  * no migrations are required — no schema changes.

Run (inside the django_core container or with DB env vars set):
  python manage.py seed_kb_templates            # all companies
  python manage.py seed_kb_templates --company taqinor-demo   # one company
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


# ── Article templates ─────────────────────────────────────────────────────────
# Each entry: (titre, categorie, tags, corps)
# Stable key: (company, titre) — never hardcode IDs.
# French apostrophes in Python strings: use double-quoted strings to avoid
# SyntaxError with single-quoted strings containing a literal apostrophe.
KB_TEMPLATES = [
    # ── 1. Procédure d'installation — Résidentiel ─────────────────────────
    (
        "Procédure d'installation — Résidentiel",
        "Installation",
        "sop,résidentiel,installation",
        """\
# Procédure d'installation — Résidentiel (gabarit)

> **GABARIT** — À adapter à chaque chantier. Supprimer les lignes inutiles.

## 1. Préparation du chantier
- [ ] Vérification des dimensions et de la résistance de la toiture
- [ ] Vérification du disjoncteur général et du tableau électrique existant
- [ ] Préparation et vérification du matériel livré (modules, onduleur, structure, câblage, protections)
- [ ] Commande et réception du matériel manquant

## 2. Pose de la structure et des modules
- [ ] Marquage et perçage des points d'ancrage selon le plan de calepinage
- [ ] Fixation des rails / crochets de toiture (étanchéité des pénétrations)
- [ ] Pose et serrage des modules (couples de serrage relevés)
- [ ] Pose de la mise à la terre du champ PV

## 3. Câblage DC / AC
- [ ] Câblage des chaînes PV (polarités vérifiées)
- [ ] Pose du coffret DC (parafoudre DC, section câble)
- [ ] Pose de l'onduleur et raccordement DC
- [ ] Câblage AC onduleur → tableau (disjoncteur dédié, parafoudre AC)

## 4. Raccordement et mise en service
- [ ] Vérification finale avant mise sous tension (POINT D'ARRÊT)
- [ ] Mise sous tension et démarrage de l'onduleur
- [ ] Relevé de production et vérification du monitoring
- [ ] Réglage de la limite d'injection si applicable

## 5. Clôture et remise au client
- [ ] Remplissage du PV de réception et signature client
- [ ] Remise des notices, garanties et fiches de suivi
- [ ] Photos du chantier finalisé (obligatoire pour le dossier)
""",
    ),

    # ── 2. Procédure d'installation — Industriel / Commercial ─────────────
    (
        "Procédure d'installation — Industriel/Commercial",
        "Installation",
        "sop,industriel,commercial,installation",
        """\
# Procédure d'installation — Industriel / Commercial (gabarit)

> **GABARIT** — À adapter à chaque chantier. Supprimer les lignes inutiles.

## 1. Études préalables
- [ ] Étude de structure (résistance toiture/sol, plan de charge)
- [ ] Étude électrique (note de calcul, schéma unifilaire)
- [ ] Étude autoconsommation (taux couverture, économies, payback)
- [ ] Validation par le bureau d'études

## 2. Réception du matériel
- [ ] Conformité des modules (marque, référence, quantité)
- [ ] Conformité des onduleurs / onduleurs-réseau (string ou central)
- [ ] Conformité de la structure (galva, type d'ancrage)
- [ ] Conformité des protections et compteur de production

## 3. Pose structure et modules
- [ ] Implantation selon plan de calepinage
- [ ] Fixation de la structure (ancrage/lestage contrôlé)
- [ ] Pose et serrage des modules (couples relevés et conformes)
- [ ] Mise à la terre du champ PV et liaisons équipotentielles

## 4. Câblage DC / AC / supervision
- [ ] Câblage chaînes et câble DC principal
- [ ] Pose coffret(s) DC et raccordement onduleurs
- [ ] Câblage AC (TGBT dédié ou jeu de barres) + compteur de production
- [ ] Câblage supervision (RS485, Ethernet ou GSM)

## 5. Raccordement et mise en service (POINTS D'ARRÊT)
- [ ] Contrôle isolement DC avant mise sous tension (POINT D'ARRÊT)
- [ ] Vérification calibres de protection et parafoudres
- [ ] Démarrage onduleurs et essai de production
- [ ] Validation zéro injection ou bridage consigne
- [ ] Essais supervision et monitoring

## 6. Clôture
- [ ] PV de réception signé (client + chef de projet)
- [ ] DOE (dossier des ouvrages exécutés) remis
- [ ] Procédure de maintenance et paramètres constructeur remis
""",
    ),

    # ── 3. Procédure d'installation — Pompage solaire ─────────────────────
    (
        "Procédure d'installation — Pompage solaire",
        "Installation",
        "sop,pompage,agricole,installation",
        """\
# Procédure d'installation — Pompage solaire (gabarit)

> **GABARIT** — À adapter à chaque chantier. Supprimer les lignes inutiles.

## 1. Études préalables
- [ ] Relevé HMT (hauteur manométrique totale) et débit souhaité
- [ ] Vérification de la profondeur du forage / puits
- [ ] Sélection de la pompe (courbe pompe vs HMT+débit)
- [ ] Dimensionnement du variateur et du champ PV

## 2. Réception du matériel
- [ ] Pompe (marque, modèle, puissance, tension)
- [ ] Variateur de fréquence (kW, tension : 220 V ou 380 V)
- [ ] Modules PV et structure
- [ ] Câble immergé (section et longueur adaptées à la profondeur)
- [ ] Coffret de protection et afficheur

## 3. Pose du champ PV
- [ ] Structure orientée et inclinée (plein Sud, inclinaison optimale)
- [ ] Modules posés et serrés aux couples
- [ ] Mise à la terre champ PV

## 4. Installation de la pompe
- [ ] Descente de la pompe au forage (profondeur notée)
- [ ] Fixation du câble immergé tous les X mètres
- [ ] Raccordement coffret variateur → pompe et PV → variateur

## 5. Raccordement et mise en service (POINTS D'ARRÊT)
- [ ] Contrôle câblage avant mise sous tension (POINT D'ARRÊT)
- [ ] Mise sous tension variateur et vérification paramètres
- [ ] Essai de démarrage et constat du débit
- [ ] Validation protection manque d'eau (sonde ou minuterie)

## 6. Clôture
- [ ] PV de réception signé
- [ ] Paramètres variateur consignés sur fiche de suivi
- [ ] Notice d'exploitation et coordonnées SAV remis
""",
    ),

    # ── 4. Dossier de raccordement ONEE ───────────────────────────────────
    (
        "Dossier de raccordement ONEE — Checklist",
        "Administrative",
        "onee,raccordement,dossier,administratif",
        """\
# Dossier de raccordement ONEE — Checklist (gabarit)

> **GABARIT** — Vérifier la liste exacte auprès de l'ONEE de la région concernée
> avant dépôt. Cette checklist est indicative et doit être confirmée au cas par cas.

## Documents identité / propriété
- [ ] Copie CIN du demandeur (recto/verso)
- [ ] Titre foncier ou contrat de bail (selon propriétaire)
- [ ] Procuration notariée si le dossier est déposé par un tiers

## Documents techniques de l'installation
- [ ] Note de calcul et dimensionnement (signée par installateur agréé)
- [ ] Schéma unifilaire de l'installation PV (signé)
- [ ] Plan de calepinage / plan de toiture
- [ ] Fiche technique des modules PV (datasheet constructeur)
- [ ] Fiche technique de l'onduleur (datasheet constructeur, certifié réseau)
- [ ] Fiche technique du parafoudre et du disjoncteur de découplage

## Formulaires ONEE
- [ ] Formulaire de demande de raccordement (fourni par l'ONEE)
- [ ] Déclaration de conformité de l'installateur
- [ ] Convention de raccordement (à signer après validation technique)

## Étapes de suivi
- [ ] Dépôt du dossier au guichet ONEE (prendre un accusé de réception)
- [ ] Visite de contrôle ONEE planifiée et effectuée
- [ ] Pose du compteur de production par l'ONEE
- [ ] Signature de la convention d'autoconsommation
- [ ] Premier relevé compteur et vérification facturation

> ⚠️ Délai indicatif de traitement ONEE : variable selon la région.
> Contacter le guichet local pour confirmer.
""",
    ),

    # ── 5. Dossier loi 82-21 — Autoconsommation ───────────────────────────
    (
        "Dossier loi 82-21 — Autoconsommation (Checklist)",
        "Administrative",
        "82-21,autoconsommation,dossier,administratif,réglementaire",
        """\
# Dossier loi 82-21 — Autoconsommation (gabarit)

> **GABARIT** — La loi 82-21 régit l'autoconsommation photovoltaïque au Maroc.
> Cette checklist est indicative. Vérifier les décrets d'application en vigueur
> et les exigences ANRE/ONEE applicables à la date du dossier.

## 1. Éligibilité et plafond de puissance
- [ ] Confirmer le régime applicable (BT ≤ 5 kWc — régime simplifié ou autre)
- [ ] Vérifier la puissance souscrite auprès de l'ONEE
- [ ] Confirmer l'injection zéro ou l'excédent injecté selon le contrat

## 2. Documents du demandeur
- [ ] CIN / registre de commerce (selon personne physique ou morale)
- [ ] Justificatif du site (titre foncier, bail ou acte de propriété)
- [ ] Dernière facture ONEE (pour référence du contrat de fourniture)

## 3. Documents techniques
- [ ] Note de dimensionnement et étude d'autoconsommation
  - Taux d'autoconsommation visé : ____%
  - Taux de couverture visé : ____%
  - Économie annuelle estimée : ____ MAD
- [ ] Schéma unifilaire et plan d'implantation
- [ ] Fiches techniques des équipements (modules, onduleur certifié réseau)
- [ ] Attestation de l'installateur agréé (si requis par décret)

## 4. Formulaires réglementaires
- [ ] Formulaire de déclaration/autorisation ANRE (si applicable à la puissance)
- [ ] Formulaire de demande d'autoconsommation ONEE
- [ ] Convention d'autoconsommation avec l'ONEE (à signer après visite)

## 5. Après raccordement
- [ ] Vérification des paramètres de bridage / zéro injection (si contrat ZI)
- [ ] Relevé de production lors du premier mois
- [ ] Archivage du dossier complet (obligatoire pour garanties et assurances)

> ℹ️ Les conditions tarifaires et le cadre réglementaire (loi 82-21 + décrets)
> peuvent évoluer. Toujours vérifier la version en vigueur sur le site ANRE
> (www.anre.ma) avant dépôt.
""",
    ),
]


class Command(BaseCommand):
    help = (
        "Seed starter SOP/template KB articles (installation procedures, "
        "ONEE and loi 82-21 dossier checklists) for every company or a "
        "single --company (idempotent, additive only)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', default=None,
            help="Slug of a single company to seed (default: all companies).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company
        from apps.kb.models import KbArticle

        slug = options.get('company')
        if slug:
            try:
                companies = [Company.objects.get(slug=slug)]
            except Company.DoesNotExist:
                raise CommandError(f"Company with slug '{slug}' not found.")
        else:
            companies = list(Company.objects.all())

        if not companies:
            self.stdout.write(self.style.WARNING(
                "No company to seed — nothing done."))
            return

        articles_created = 0

        for company in companies:
            for titre, categorie, tags, corps in KB_TEMPLATES:
                # Stable key: (company, titre) — re-running never duplicates
                # and never overwrites an article the team has since edited.
                _, is_new = KbArticle.objects.get_or_create(
                    company=company,
                    titre=titre,
                    defaults={
                        'categorie': categorie,
                        'tags': tags,
                        'corps': corps,
                        'statut': KbArticle.Statut.PUBLIE,
                    },
                )
                if is_new:
                    articles_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"KB templates seeded for {len(companies)} société(s): "
            f"{articles_created} article(s) created "
            f"(existing rows left untouched)."))
