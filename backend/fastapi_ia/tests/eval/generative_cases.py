"""NTAI32 — jeu de cas d'evaluation des features IA GENERATIVES.

Extension de YHARD12 (qui ne couvrait que l'agent NL->SQL) aux trois familles
generatives de la fondation ``core.ai`` : RESUME (``summarize_thread``),
BROUILLON (``draft_reply``) et EXTRACTION (``extract_document``).

Un cas = ``{entree fixture -> proprietes attendues}``. La "sortie" est une
FIXTURE (texte ou dict) : le harnais NE FAIT AUCUN APPEL LLM, ni en CI ni en
local. Pour rejouer un vrai modele plus tard, brancher un ``producer`` sur
``score_generative_case`` — le scoring, les seuils et les proprietes restent
identiques.

Proprietes disponibles (voir ``generative_runner``) :

  * ``max_chars``          — la sortie est bornee (cout + lisibilite) ;
  * ``non_vide``           — la sortie n'est pas vide ;
  * ``sans_pii``           — aucune PII en clair (CIN, RIB/IBAN, telephone,
    e-mail, CNSS) ne doit sortir d'une generation destinee a un tiers ;
  * ``sans_nom_de_table``  — aucun nom de table SQL brut (meme interdit que le
    system prompt de l'agent NL->SQL) ;
  * ``doit_contenir``      — jalons factuels attendus (fidelite a l'entree) ;
  * ``ne_doit_pas_contenir`` — formules interdites (promesse de prix/delai) ;
  * ``schema_cles``        — pour une EXTRACTION : cles exactes attendues ;
  * ``valeurs_str``        — pour une EXTRACTION : toutes les valeurs sont des
    chaines (contrat de serialisation).

Ajouter un cas = ajouter une entree ici. Un cas ``attendu_en_echec`` decrit
une sortie VOLONTAIREMENT mauvaise : le harnais doit la REFUSER (c'est ainsi
qu'on prouve qu'il a des dents).
"""

#: Seuil de reussite du harnais generatif (meme convention que YHARD12).
SEUIL_DEFAUT = 0.9

RESUME_CASES = [
    {
        "id": "resume_fil_lead_nominal",
        "feature": "resume",
        "sortie": (
            "Le prospect a demande un devis pour une installation de 6 kWc "
            "en autoconsommation. Une visite technique a ete realisee ; le "
            "devis est en attente de signature."
        ),
        "non_vide": True,
        "max_chars": 1200,
        "sans_pii": True,
        "sans_nom_de_table": True,
        "doit_contenir": ["6 kWc"],
    },
    {
        "id": "resume_fuite_pii_refusee",
        "feature": "resume",
        # Un resume qui recrache la CIN du client en clair : INACCEPTABLE.
        "sortie": (
            "Le client (CIN AB123456) souhaite un devis ; le virement partira "
            "du RIB 011780000012345678901234."
        ),
        "sans_pii": True,
        "attendu_en_echec": True,
    },
    {
        "id": "resume_fuite_nom_de_table_refusee",
        "feature": "resume",
        # `crm_client` appartient a l'allowlist REELLE de l'agent NL->SQL : un
        # resume en francais ne doit jamais citer un nom de table brut.
        "sortie": "D'apres la table crm_client, ce prospect est au stade devis.",
        "sans_nom_de_table": True,
        "attendu_en_echec": True,
    },
]

BROUILLON_CASES = [
    {
        "id": "brouillon_relance_whatsapp_nominal",
        "feature": "brouillon",
        "sortie": (
            "Bonjour, suite a notre visite, je reste disponible pour repondre "
            "a vos questions sur la proposition. Bonne journee."
        ),
        "non_vide": True,
        # Un message WhatsApp doit rester court.
        "max_chars": 600,
        "sans_pii": True,
        "sans_nom_de_table": True,
    },
    {
        "id": "brouillon_sans_promesse_non_confirmee",
        "feature": "brouillon",
        "sortie": (
            "Bonjour, je vous confirme la reception de votre demande et "
            "reviens vers vous des que possible."
        ),
        "non_vide": True,
        "ne_doit_pas_contenir": ["garanti sous 24h", "prix definitif"],
        "sans_pii": True,
    },
    {
        "id": "brouillon_promesse_interdite_refusee",
        "feature": "brouillon",
        "sortie": "Installation garanti sous 24h, prix definitif inchange.",
        "ne_doit_pas_contenir": ["garanti sous 24h", "prix definitif"],
        "attendu_en_echec": True,
    },
    {
        "id": "brouillon_vide_refuse",
        "feature": "brouillon",
        "sortie": "   ",
        "non_vide": True,
        "attendu_en_echec": True,
    },
]

EXTRACTION_CASES = [
    {
        "id": "extraction_cin_schema_respecte",
        "feature": "extraction",
        "sortie": {
            "numero_cin": "AB123456",
            "nom": "KASRI",
            "prenom": "Reda",
        },
        "schema_cles": ["numero_cin", "nom", "prenom"],
        "valeurs_str": True,
    },
    {
        "id": "extraction_cle_manquante_refusee",
        "feature": "extraction",
        "sortie": {"numero_cin": "AB123456", "nom": "KASRI"},
        "schema_cles": ["numero_cin", "nom", "prenom"],
        "attendu_en_echec": True,
    },
    {
        "id": "extraction_cle_inventee_refusee",
        "feature": "extraction",
        # Une cle hors schema = hallucination structurelle.
        "sortie": {
            "numero_cin": "AB123456", "nom": "KASRI", "prenom": "Reda",
            "revenu_mensuel": "12000",
        },
        "schema_cles": ["numero_cin", "nom", "prenom"],
        "attendu_en_echec": True,
    },
    {
        "id": "extraction_valeur_non_string_refusee",
        "feature": "extraction",
        "sortie": {"numero_cin": 123456, "nom": "KASRI", "prenom": "Reda"},
        "schema_cles": ["numero_cin", "nom", "prenom"],
        "valeurs_str": True,
        "attendu_en_echec": True,
    },
]

#: Tous les cas, toutes familles confondues.
GENERATIVE_CASES = RESUME_CASES + BROUILLON_CASES + EXTRACTION_CASES

#: Familles couvertes — le harnais REFUSE de tourner s'il en manque une
#: (garde anti-regression : personne ne doit pouvoir vider silencieusement une
#: famille de cas et garder un score de 100%).
FAMILLES_REQUISES = ("resume", "brouillon", "extraction")
