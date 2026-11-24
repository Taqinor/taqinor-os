// Les sections que l'éditeur d'un acte sait modifier. Pour chacune :
//   lire(contenu)  → le brouillon de saisie (chaînes pour les champs texte),
//   ecrire(brouillon, langue) → la valeur envoyée dans `surcharges[<section>]`
//   (en arabe, seuls les TEXTES partent : dates, durées et fins de garantie
//   viennent du français et ne sont jamais renvoyées).
// Les clés viennent du contrat (acte_contractuel.json : `sections_modifiables`) ;
// une section que le serveur ne liste pas pour l'acte n'est jamais montrée.
// Aucun montant ici : l'échéancier n'expose que « quand » et « note ».
import {
  nombreTape, paragraphesVersTexte, texteVersParagraphes,
} from './outils'

const chaine = (v) => (v === null || v === undefined ? '' : String(v))

export const SECTIONS = {
  titre: {
    libelle: 'Titre du document',
    lire: (c) => chaine(c.titre),
    ecrire: (d) => d,
  },
  lieu: {
    libelle: 'Lieu',
    lire: (c) => chaine(c.lieu),
    ecrire: (d) => d,
  },
  date_document: {
    libelle: 'Date du document',
    lire: (c) => chaine(c.date_document),
    ecrire: (d) => d,
  },
  societe: {
    libelle: 'Représentant de la société',
    lire: (c) => ({ representant: chaine(c.societe?.representant) }),
    ecrire: (d) => ({ representant: d.representant }),
  },
  delais: {
    libelle: 'Délais',
    lire: (c) => ({
      date_limite: chaine(c.delais?.date_limite),
      detail: chaine(c.delais?.detail),
    }),
    // En arabe la date limite est commune : seul le détail se règle.
    ecrire: (d, langue) => (langue === 'ar'
      ? { detail: d.detail }
      : { date_limite: d.date_limite || null, detail: d.detail }),
  },
  echeancier_textes: {
    libelle: 'Échéancier : les mots',
    lire: (c) => Object.fromEntries((c.echeancier ?? []).map((t) => [
      t.cle, { exigibilite: chaine(t.exigibilite), note: chaine(t.note) },
    ])),
    ecrire: (d) => d,
  },
  garanties: {
    libelle: 'Garanties',
    lire: (c) => (c.garanties ?? []).map((g) => ({ ...g, duree_mois: chaine(g.duree_mois) })),
    ecrire: (d, langue) => d.map((g) => (langue === 'ar'
      ? { cle: g.cle, designation: g.designation, garant: g.garant, detail: g.detail }
      : { ...g, duree_mois: nombreTape(g.duree_mois) })),
  },
  articles: {
    libelle: 'Articles',
    lire: (c) => (c.articles ?? []).map((a) => ({
      cle: a.cle, titre: chaine(a.titre), texte: paragraphesVersTexte(a.paragraphes),
    })),
    ecrire: (d) => d.map((a) => ({
      cle: a.cle, titre: a.titre, paragraphes: texteVersParagraphes(a.texte),
    })),
  },
  conditions_particulieres: {
    libelle: 'Conditions particulières',
    lire: (c) => chaine(c.conditions_particulieres),
    ecrire: (d) => d,
  },
  options: {
    libelle: 'Options',
    // `delai_execution_jours` n'est lu / envoyé que si le serveur le sert.
    lire: (c) => ({
      reserve_propriete: !!c.options?.reserve_propriete,
      ...('delai_execution_jours' in (c.options ?? {})
        ? { delai_execution_jours: chaine(c.options.delai_execution_jours) } : {}),
      penalite_retard_pct: chaine(c.options?.penalite_retard_pct),
    }),
    ecrire: (d) => ({
      reserve_propriete: d.reserve_propriete,
      ...('delai_execution_jours' in d
        ? { delai_execution_jours: nombreTape(d.delai_execution_jours) } : {}),
      penalite_retard_pct: nombreTape(d.penalite_retard_pct),
    }),
  },
  livraison: {
    libelle: 'Livraison',
    lire: (c) => ({
      ...c.livraison,
      date: chaine(c.livraison?.date),
      suite: chaine(c.livraison?.suite),
      suite_detail: chaine(c.livraison?.suite_detail),
    }),
    ecrire: (d) => d,
  },
  reception: {
    libelle: 'Réception',
    lire: (c) => ({
      ...c.reception,
      date_mise_en_service: chaine(c.reception?.date_mise_en_service),
      delai_levee_reserves: chaine(c.reception?.delai_levee_reserves),
      prononcee: !!c.reception?.prononcee,
    }),
    ecrire: (d) => d,
  },
  constats: {
    libelle: 'Constats',
    lire: (c) => (c.constats ?? []).map((k) => ({ ...k, texte: chaine(k.texte), cochee: !!k.cochee })),
    ecrire: (d) => d,
  },
  reserves: {
    libelle: 'Réserves',
    lire: (c) => (c.reserves ?? []).join('\n'),
    ecrire: (d) => d.split('\n').map((l) => l.trim()).filter(Boolean),
  },
  quitus: {
    libelle: 'Quitus',
    lire: (c) => paragraphesVersTexte(c.quitus),
    ecrire: (d) => texteVersParagraphes(d),
  },
  sav: {
    libelle: 'Service après-vente',
    lire: (c) => ({
      ...c.sav,
      telephone: chaine(c.sav?.telephone),
      whatsapp: chaine(c.sav?.whatsapp),
      email: chaine(c.sav?.email),
      horaires: chaine(c.sav?.horaires),
    }),
    ecrire: (d) => d,
  },
  conseils: {
    libelle: 'Conseils de consommation',
    lire: (c) => (c.conseils ?? []).map((k) => ({
      ...k, rubrique: chaine(k.rubrique), titre: chaine(k.titre), texte: chaine(k.texte),
    })),
    ecrire: (d) => d,
  },
  entretien: {
    libelle: 'Entretien',
    lire: (c) => paragraphesVersTexte(c.entretien),
    ecrire: (d) => texteVersParagraphes(d),
  },
}

// Ordre de lecture dans l'éditeur (celui du document imprimé).
export const ORDRE_SECTIONS = [
  'titre', 'lieu', 'date_document', 'societe', 'delais', 'echeancier_textes',
  'articles', 'garanties', 'conditions_particulieres', 'options',
  'livraison', 'reception', 'constats', 'reserves', 'quitus', 'sav',
  'conseils', 'entretien',
]

export function brouillonDe(contenu, sections) {
  return Object.fromEntries(
    sections.filter((k) => SECTIONS[k]).map((k) => [k, SECTIONS[k].lire(contenu ?? {})]),
  )
}

/** `{ section: valeur }` pour les seules sections modifiées par la saisie. */
export function surchargesModifiees(base, brouillon, sections, langue = 'fr') {
  const surcharges = {}
  for (const cle of sections) {
    if (!SECTIONS[cle]) continue
    if (JSON.stringify(base[cle]) !== JSON.stringify(brouillon[cle])) {
      surcharges[cle] = SECTIONS[cle].ecrire(brouillon[cle], langue)
    }
  }
  return surcharges
}
