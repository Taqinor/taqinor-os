"""Constantes du dossier contractuel (docs/contrats/conception.md § 3 à 5).

Aucune lecture de base ici : les listes de sections, les préfixes de
référence, les libellés et les défauts décidés par Reda (24/11/2026).
"""

LANGUES = ('fr', 'ar')
LANGUE_DEFAUT = 'fr'

CONTRAT = 'contrat_installation'
LIVRAISON = 'pv_livraison'
RECEPTION = 'pv_reception'
CLOTURE = 'cloture_garanties'
TYPES = (CONTRAT, LIVRAISON, RECEPTION, CLOTURE)

RESTE_A_REGLER = 'reste_a_regler'
TRANCHE_REGLEE = 'tranche_reglee'

BROUILLON = 'brouillon'
EMIS = 'emis'
SIGNE = 'signe'
ANNULE = 'annule'
STATUTS = (BROUILLON, EMIS, SIGNE, ANNULE)

#: Les cinq lignes du dossier : (type, variante, rang).
LIGNES_DOSSIER = (
    (CONTRAT, '', 1),
    (LIVRAISON, RESTE_A_REGLER, 2),
    (LIVRAISON, TRANCHE_REGLEE, 2),
    (RECEPTION, '', 3),
    (CLOTURE, '', 4),
)
RANGS = {CONTRAT: 1, LIVRAISON: 2, RECEPTION: 3, CLOTURE: 4}

TITRES = {
    CONTRAT: "Contrat d'installation",
    LIVRAISON: 'Livraison du matériel',
    RECEPTION: 'Réception des travaux',
    CLOTURE: 'Quitus et certificat de garantie',
}
TITRE_RESTE_A_REGLER = 'Livraison du matériel — reste à régler'
TITRE_TRANCHE_REGLEE = 'Livraison du matériel — {pourcentage} réglés'
TITRE_TRANCHE_REGLEE_SANS_DEVIS = (
    'Livraison du matériel — acompte et livraison réglés')

#: Préfixe de référence de chaque acte ; la suite est la référence du
#: chantier sans son propre préfixe (CHT-2026-11-0007 → CTR-2026-11-0007).
PREFIXES = {CONTRAT: 'CTR', LIVRAISON: 'LIV', RECEPTION: 'REC', CLOTURE: 'CLO'}

#: Source GED d'un acte figé (``source_id`` = l'id de l'acte).
SOURCE_GED = 'documents.acte_{type}'
SOURCE_GED_AR = 'documents.acte_{type}_ar'

#: Sections modifiables, dans l'ordre du contrat d'API
#: (contract_samples/acte_contractuel.json).
SECTIONS_MODIFIABLES = {
    CONTRAT: ('titre', 'lieu', 'date_document', 'societe', 'delais',
              'echeancier_textes', 'paiement', 'garanties', 'articles',
              'conditions_particulieres', 'options'),
    LIVRAISON: ('titre', 'lieu', 'date_document', 'livraison', 'constats',
                'reserves', 'echeancier_textes', 'paiement', 'articles',
                'conditions_particulieres', 'options'),
    RECEPTION: ('titre', 'lieu', 'date_document', 'reception', 'constats',
                'reserves', 'echeancier_textes', 'paiement', 'articles',
                'conditions_particulieres', 'options'),
    CLOTURE: ('titre', 'lieu', 'date_document', 'quitus', 'garanties',
              'articles', 'sav', 'conseils_intro', 'conseils', 'entretien'),
}

#: Sections de TEXTE : les seules qui se personnalisent par langue (la
#: traduction arabe). Dates, options, signataire, lieu, livraison, réception
#: et service après-vente sont communs aux deux langues (réglés en français).
SECTIONS_TEXTE = frozenset({
    'titre', 'articles', 'conditions_particulieres', 'constats', 'reserves',
    'quitus', 'conseils_intro', 'conseils', 'entretien', 'garanties',
    'echeancier_textes', 'delais', 'paiement',
})
SECTIONS_COMMUNES = frozenset({
    'lieu', 'date_document', 'societe', 'options', 'livraison', 'reception',
    'sav',
})

#: Libellés des sections (avertissements, messages d'erreur).
LIBELLES_SECTIONS = {
    'titre': 'titre', 'lieu': 'lieu', 'date_document': 'date du document',
    'societe': 'signataire de la société', 'delais': 'délais',
    'echeancier_textes': "textes de l'échéancier", 'paiement': 'paiement',
    'garanties': 'garanties', 'articles': 'articles',
    'conditions_particulieres': 'conditions particulières',
    'options': 'options', 'livraison': 'livraison', 'constats': 'constats',
    'reserves': 'réserves', 'reception': 'réception', 'quitus': 'quitus',
    'sav': 'service après-vente', 'conseils_intro': 'introduction des conseils',
    'conseils': 'conseils', 'entretien': 'entretien',
}

#: Clés permises dans les sections de forme dictionnaire. Aucune ne porte un
#: montant : un montant ne se modifie jamais dans un acte (choix C1).
CLES_SOCIETE = ('representant',)
CLES_DELAIS = ('resume', 'detail', 'date_limite')
#: En arabe, seul le détail des délais se traduit : la date limite est
#: commune (le résumé arabe se recalcule depuis elle).
CLES_DELAIS_AR = ('detail',)
#: En arabe, une ligne de garantie ne traduit que ses textes : les lignes,
#: les durées et les dates de fin viennent du français.
CLES_GARANTIE_TEXTE = ('designation', 'garant', 'detail')
CLES_LIVRAISON = ('date', 'suite', 'suite_detail', 'avec_series')
CLES_RECEPTION = ('date_mise_en_service', 'prononcee', 'delai_levee_reserves')
CLES_SAV = ('telephone', 'whatsapp', 'email', 'horaires')
#: Clés de texte du bloc ``paiement`` (jamais un montant) ; seule
#: ``modalites`` se modifie dans un acte (français et arabe).
CLES_PAIEMENT_TEXTE = ('modalites', 'engagement')
CLES_PAIEMENT_MODIFIABLES = ('modalites',)
CLES_OPTIONS = ('consommateur', 'reserve_propriete',
                'penalite_retard_pct', 'delai_execution_jours')
CLES_GARANTIE = ('cle', 'designation', 'duree_mois', 'duree_libelle',
                 'garant', 'detail', 'fin')
CLES_CONSEIL = ('rubrique', 'titre', 'texte')

#: Défauts décidés par Reda (conception § 9) et choix C5.
DELAI_EXECUTION_DEFAUT_JOURS = 30
GARANTIE_INSTALLATION_DEFAUT_MOIS = 24

#: Clés de tranche dues au plus tard à la livraison : la commande et la
#: livraison du matériel (échéancier résidentiel ``materiel``, jalons C&I
#: ``commande`` et ``livraison_materiel``).
CLES_TRANCHE_LIVRAISON = ('commande', 'materiel', 'livraison_materiel')

#: Codes d'erreur servis (contrat d'API).
CODE_ACTE_FIGE = 'acte_fige'
CODE_SOLDE_NON_REGLE = 'solde_non_regle'
CODE_CHANTIER_ANNULE = 'chantier_annule'
CODE_DEJA_SIGNE = 'deja_signe'
CODE_CONTENU_INVALIDE = 'contenu_invalide'
CODE_SANS_DEVIS = 'sans_devis'
CODE_ETAT = 'etat_invalide'
#: Un texte personnalisé cite un montant que la vente ne porte plus (409).
CODE_MONTANT_FIGE = 'montant_fige'
#: Variante « tranche réglée » sans les encaissements qu'elle affirme (409).
CODE_PAIEMENT_NON_ENREGISTRE = 'paiement_non_enregistre'
