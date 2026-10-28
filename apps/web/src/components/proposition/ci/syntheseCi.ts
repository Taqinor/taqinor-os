/**
 * CPRW (27/10/2026) — déplacement PUR depuis src/lib/proposition.ts (aucune ligne de logique
 * changée) : la lecture de `synthese_ci` pour /proposition. Propriétaire : session CPRW.
 * `lib/proposition.ts` ré-exporte tout (`export *`) : les importeurs existants ne bougent pas.
 */
import {
  estRecord,
  nombreServi,
  resolveInstallMode,
  texteServi,
  type OptionKey,
  type ProposalResponse,
} from '../../../lib/proposition';

// ════════════════════════════════════════════════════════════════════════════
// CIW300 — Jumeau web du document C&I : `synthese_ci` (commercial / industriel).
//
// LA PAGE NE CALCULE RIEN. Le serveur sert `synthese_ci` (CIQ306 — la MÊME
// fonction pure du moteur que le PDF, contrat partagé `proposal_data.json` ›
// `exemple_commercial.synthese_ci` / `exemple_industriel.synthese_ci`). Cet
// extracteur la LIT, défensivement : clé absente → `null`, jamais un 0 fabriqué.
// Remplace le mini-cashflow linéaire, le cumul « économie × 25 ans » et les
// mentions 82-21 écrites dans la page (CIW300).
// ════════════════════════════════════════════════════════════════════════════

/** Un texte servi en trois langues (`textes{fr,en,ar}` du contrat). */
export interface TextesCi {
  fr: string;
  en: string;
  ar: string;
}

export interface SyntheseCiHypothese {
  cle: string;
  textes: TextesCi;
  source: string | null;
  date: string | null;
}

export interface SyntheseCiArgent {
  /** `calcule` | `omis` (servi tel quel). */
  statut: string | null;
  /** `ht` | `ttc` | `deux` — la base de l'économie (D-CIQ-3). */
  base: string | null;
  motifBase: string | null;
  /** Le tarif utilisé : phrase servie + la source de la 1re ligne de tarif. */
  tarif: { mention: string | null; source: string | null; origine: string | null; releveLe: string | null } | null;
  /** Économie de l'année 1 (MAD) — telle que servie, HT et/ou TTC. */
  economieAnnee1: { ht: number | null; ttc: number | null } | null;
  /** Retour sur investissement en années (servi : `indicateurs.retour_ans`). */
  retourAns: number | null;
  /** Revente du surplus (MT seulement) : `statut === 'calculee'` ou rien. */
  revente: { statut: string | null; kwhAn: number | null; valeurMadAn: number | null } | null;
  motifsOmission: string[];
  /** CIW308 — jalons de cumul net (années 5/10/15/20/25), tels que servis ; `[]` si absents. */
  jalons: Array<{ annee: number; cumul: number }>;
  /** Les mêmes jalons en TTC quand la base servie est « deux ». */
  jalonsTtc: Array<{ annee: number; cumul: number }>;
  /** CIW308 — indicateurs de rentabilité servis (aucun n'est calculé ici). */
  indicateurs: {
    triPct: number | null;
    triHorizonAns: number | null;
    lcoeMadKwh: number | null;
    tarifKwhEvite: number | null;
    vanMad: number | null;
    vanMotif: string | null;
  } | null;
  /** Taux d'actualisation DÉCLARÉ par le client (hypothèse du flux servi), jamais un défaut. */
  tauxActualisationPct: number | null;
  /** Sensibilités SAISIES par la société (industriel seulement) ; `[]` sans scénario. */
  sensibilites: Array<{ cle: string; variationPct: number | null; retourAns: number | null; triPct: number | null; motif: string | null }>;
  /** Offre de financement SERVIE (offre écrite), ou `null` — jamais un taux inventé. */
  financement: {
    libelleClient: string | null;
    echeanceMad: number | null;
    economieMensuelleMoyenneMad: number | null;
    ecartMensuelMad: number | null;
    dureeMois: number | null;
    source: string | null;
    /** CEC15 — apport et frais SAISIS sur l'offre (0 si absents ; imprimés seulement > 0). */
    apportMad: number | null;
    fraisMad: number | null;
    /** CEC15 — retour sur l'offre servi (au dixième), `null` quand la clé est absente : jamais recalculé. */
    retourOffreAns: number | null;
  } | null;
}

export interface SyntheseCi {
  version: number | null;
  segment: string | null;
  /** `estimation_sous_reserve_visite` | `offre_ferme`. */
  statutEtude: string | null;
  aConfirmer: Array<{ cle: string; libelle: string }>;
  /** CPRW13 — postes « à chiffrer après la visite » restés hors total (`synthese_ci.postes_hors_total`), jamais un prix. */
  postesHorsTotal: Array<{ role: string | null; designation: string; catalogue: boolean }>;
  systeme: { kwc: number | null; nbPanneaux: number | null; productionKwhAn: number | null } | null;
  energie: {
    autoconsoPct: number | null;
    couverturePct: number | null;
    /** Méthode servie (`horaire_declare`, `profil_type`…) — « estimation » quand elle le dit. */
    methode: string | null;
    definitions: { autoconso: string | null; couverture: string | null };
  } | null;
  argent: SyntheseCiArgent | null;
  /** L'offre que le document TITRE (`option_servie` : `sans_batterie` | `avec_batterie`), ou `null`. */
  optionServie: string | null;
  /** CPRW16 — échéancier de paiement SERVI (`synthese_ci.echeancier`), tel quel ; `[]` sans échéancier. */
  echeancier: Array<{ libelle: string | null; pct: number; montantTtc: number | null; jalon: string | null }>;
  /** CIW303 — la batterie d'un C&I est une OPTION : valeur chiffrée par le moteur, ou son motif. */
  optionBatterie: SyntheseCiOptionBatterie | null;
  /** CIW304 — services servis : l'option O&M nommée du devis et le délai de suivi (heures), si servis. */
  services: {
    omLibelle: string | null;
    suiviDelaiHeures: number | null;
    /** CPRW15 — garanties des fabricants SERVIES (`services.garanties[]`), durée extraite du texte ; jamais complétées. */
    garanties: Array<{ composant: string; annees: number | null }>;
    /** CPRW17 — l'option O&M NOMMÉE (`services.om_option`) : statut servi et lignes (prix HT seulement s'il est servi). */
    omOption: { statut: string | null; libelle: string; lignes: Array<{ designation: string | null; totalHt: number | null }> } | null;
    /** CPRW17 — suivi de production nommé ; son délai (heures) seulement s'il est servi. */
    suiviProduction: { delaiHeures: number | null } | null;
    /** CPRW17 — régime 82-21 servi (`services.raccordement.regime`) : la société monte le dossier de raccordement. */
    raccordementRegime: string | null;
  } | null;
  /** CIW306 — le bloc catégorie d'un devis commercial, tel que servi (`synthese_ci.categorie`). */
  categorie: SyntheseCiCategorie | null;
  /** CIW307 — décarbonation SERVIE (CIQ344) : `cbam` = drapeau serveur, `textes` = la phrase du PDF. */
  decarbonation: { cbam: boolean; textes: TextesCi } | null;
  /** CIW305 — la raison sociale du client entreprise si le devis la porte (pré-remplit le formulaire). */
  entrepriseClient: { raisonSociale: string | null; ice: string | null; interlocuteur: string | null; fonction: string | null } | null;
  hypotheses: SyntheseCiHypothese[];
  omissions: Array<{ bloc: string; motif: string }>;
}

export interface SyntheseCiCategorie {
  cle: string;
  libelle: string | null;
  accroche: string | null;
  /** Titre du bloc (`bloc.titre`, servi) et ses lignes trilingues (`bloc.lignes[].textes`). */
  titre: string | null;
  lignes: TextesCi[];
}

export interface SyntheseCiOptionBatterie {
  /** Texte servi de la valeur chiffrée par le moteur C&I (`valeur_chiffree.textes`), ou `null` = non chiffrée. */
  valeurChiffree: TextesCi | null;
  /** Motif servi (« valeur non chiffrée »…), ou `null`. */
  motif: string | null;
  /** CPRW18 — totaux servis de l'option (`option_batterie.totaux`), tels quels. */
  totaux: { htNet: number | null; tva: number | null; ttc: number | null } | null;
  /** CPRW18 — chiffres servis par le moteur C&I (`valeur_chiffree`) ; `null` = non chiffrée. L'économie est la TOTALE (HT) de l'option. */
  chiffres: {
    economieAnnuelleMad: number | null;
    retourSimpleAns: number | null;
    capaciteUtileKwh: number | null;
    restitueKwhAn: number | null;
  } | null;
}

/**
 * CPRW21 — définitions des deux taux dans les trois langues (`ci/synthese.py::DEFINITIONS`, garde de parité
 * dans `propositionSyntheseCiCIW300.test.ts`) : le serveur n'en sert qu'une langue, la page affiche les trois.
 */
export const DEFINITIONS_CI: Record<'fr' | 'en' | 'ar', { autoconso: string; couverture: string }> = {
  fr: {
    autoconso: 'part de la production consommée sur place',
    couverture: 'part de votre consommation couverte par le solaire',
  },
  en: {
    autoconso: 'share of the solar production consumed on site',
    couverture: 'share of your consumption covered by solar',
  },
  ar: {
    autoconso: 'حصة الإنتاج المستهلكة في عين المكان',
    couverture: 'حصة استهلاككم المغطاة بالطاقة الشمسية',
  },
};

function lireTextesCi(v: unknown): TextesCi | null {
  if (!estRecord(v)) return null;
  const fr = texteServi(v.fr);
  if (fr === null) return null;
  return { fr, en: texteServi(v.en) ?? fr, ar: texteServi(v.ar) ?? fr };
}

function lireCategorieCi(v: unknown): SyntheseCiCategorie | null {
  if (!estRecord(v)) return null;
  const cle = texteServi(v.cle);
  if (!cle) return null;
  const bloc = estRecord(v.bloc) ? v.bloc : null;
  const lignes: TextesCi[] = [];
  if (bloc && Array.isArray(bloc.lignes)) {
    for (const l of bloc.lignes) {
      const t = estRecord(l) ? lireTextesCi(l.textes) : null;
      if (t) lignes.push(t);
    }
  }
  return {
    cle,
    libelle: texteServi(v.libelle),
    accroche: texteServi(v.accroche),
    titre: bloc ? texteServi(bloc.titre) : null,
    lignes,
  };
}

// CE2E2 — `paybackPdf` = `mode_kpis.payback` servi (au dixième, celui du PDF) : il remplace
// l'entier `indicateurs.retour_ans` quand celui-ci est servi — jamais un calcul côté page.
function lireArgentCi(v: unknown, paybackPdf: number | null = null): SyntheseCiArgent | null {
  if (!estRecord(v) || Object.keys(v).length === 0) return null;
  const tarifBrut = estRecord(v.tarif) ? v.tarif : null;
  const premierePoste =
    tarifBrut && Array.isArray(tarifBrut.tarifs_par_poste) && estRecord(tarifBrut.tarifs_par_poste[0])
      ? (tarifBrut.tarifs_par_poste[0] as Record<string, unknown>)
      : null;
  const eco = estRecord(v.economie_annee1) ? v.economie_annee1 : null;
  const ind = estRecord(v.indicateurs) ? v.indicateurs : null;
  const rev = estRecord(v.revente) ? v.revente : null;
  const ht = eco ? nombreServi(eco.total_mad) : null;
  const ttc = eco ? nombreServi(eco.total_mad_ttc) : null;
  return {
    statut: texteServi(v.statut),
    base: texteServi(v.base),
    motifBase: texteServi(v.motif_base),
    tarif: tarifBrut
      ? {
          mention: texteServi(tarifBrut.mention),
          source: premierePoste ? texteServi(premierePoste.source) : null,
          origine: texteServi(tarifBrut.origine),
          releveLe: premierePoste ? texteServi(premierePoste.releve_le) : null,
        }
      : null,
    economieAnnee1: ht !== null || ttc !== null ? { ht, ttc } : null,
    retourAns: ind && nombreServi(ind.retour_ans) !== null ? (paybackPdf ?? nombreServi(ind.retour_ans)) : null,
    revente: rev
      ? { statut: texteServi(rev.statut), kwhAn: nombreServi(rev.kwh_an), valeurMadAn: nombreServi(rev.valeur_mad_an) }
      : null,
    motifsOmission: Array.isArray(v.motifs_omission)
      ? v.motifs_omission.filter((x): x is string => typeof x === 'string' && x.trim() !== '')
      : [],
    jalons: lireJalonsCi(v.jalons),
    jalonsTtc: lireJalonsCi(v.jalons_ttc),
    indicateurs: ind
      ? {
          triPct: nombreServi(ind.tri_pct),
          triHorizonAns: nombreServi(ind.tri_horizon_ans),
          lcoeMadKwh: nombreServi(ind.lcoe_mad_kwh),
          tarifKwhEvite: nombreServi(ind.tarif_kwh_evite_moyen),
          vanMad: nombreServi(ind.van_mad),
          vanMotif: texteServi(ind.van_motif),
        }
      : null,
    tauxActualisationPct: lireTauxActualisationCi(v),
    sensibilites: Array.isArray(v.sensibilites)
      ? v.sensibilites.filter(estRecord).flatMap((x) => {
          const cle = texteServi(x.cle);
          return cle
            ? [{
                cle,
                variationPct: nombreServi(x.variation_pct),
                retourAns: nombreServi(x.retour_ans),
                triPct: nombreServi(x.tri_pct),
                motif: texteServi(x.motif),
              }]
            : [];
        })
      : [],
    financement: estRecord(v.financement)
      ? {
          libelleClient: texteServi(v.financement.libelle_client),
          echeanceMad: nombreServi(v.financement.echeance_mad),
          economieMensuelleMoyenneMad: nombreServi(v.financement.economie_mensuelle_moyenne_mad),
          ecartMensuelMad: nombreServi(v.financement.ecart_mensuel_mad),
          dureeMois: nombreServi(v.financement.duree_mois),
          source: texteServi(v.financement.source),
          apportMad: nombreServi(v.financement.apport_mad),
          fraisMad: nombreServi(v.financement.frais_mad),
          retourOffreAns: nombreServi(v.financement.retour_offre_ans),
        }
      : null,
  };
}

function lireJalonsCi(v: unknown): Array<{ annee: number; cumul: number }> {
  if (!Array.isArray(v)) return [];
  return v.flatMap((j) => {
    if (!estRecord(j)) return [];
    const annee = nombreServi(j.annee);
    const cumul = nombreServi(j.cumul_mad);
    return annee !== null && cumul !== null ? [{ annee, cumul }] : [];
  });
}

function lireTauxActualisationCi(argent: Record<string, unknown>): number | null {
  for (const cle of ['flux_ht', 'flux_ttc']) {
    const flux = argent[cle];
    if (!estRecord(flux) || !Array.isArray(flux.hypotheses)) continue;
    for (const h of flux.hypotheses) {
      if (estRecord(h) && h.cle === 'taux_actualisation_pct') return nombreServi(h.valeur);
    }
  }
  return null;
}

function lireOmOptionCi(v: unknown): NonNullable<SyntheseCi['services']>['omOption'] {
  if (!estRecord(v)) return null;
  const libelle = texteServi(v.libelle);
  if (!libelle) return null;
  const lignes = Array.isArray(v.lignes)
    ? v.lignes.flatMap((l) => (estRecord(l) ? [{ designation: texteServi(l.designation), totalHt: nombreServi(l.total_ht) }] : []))
    : [];
  return { statut: texteServi(v.statut), libelle, lignes };
}

/** CPRW15 — durée d'une garantie servie : « Onduleur : 10 ans » ou l'ancien « Garantie constructeur 10 ans » → 10. */
export function anneesGarantieCi(texte: string | null): number | null {
  const m = texte ? /(\d+)\s*ans\b/i.exec(texte) : null;
  return m ? Number(m[1]) : null;
}

function lireGarantiesCi(v: unknown): Array<{ composant: string; annees: number | null }> {
  if (!Array.isArray(v)) return [];
  return v.flatMap((g) => {
    if (!estRecord(g)) return [];
    const composant = texteServi(g.composant);
    return composant ? [{ composant, annees: anneesGarantieCi(texteServi(g.texte)) }] : [];
  });
}

/**
 * CIW300 — extracteur PUR de `synthese_ci`. `null` hors commercial/industriel,
 * quand la clé est absente ou vide. Aucune valeur n'est calculée, convertie ni
 * complétée ici (une chaîne n'est jamais convertie en nombre).
 */
export function syntheseCi(
  p: Pick<ProposalResponse, 'mode_installation' | 'quote'> | null | undefined,
): SyntheseCi | null {
  if (!p) return null;
  const mode = resolveInstallMode(p);
  if (mode !== 'commercial' && mode !== 'industriel') return null;
  const brut = (p as { synthese_ci?: unknown }).synthese_ci;
  if (!estRecord(brut) || Object.keys(brut).length === 0) return null;

  const mk = (p as { mode_kpis?: unknown }).mode_kpis;
  const sys = estRecord(brut.systeme) ? brut.systeme : null;
  const en = estRecord(brut.energie) ? brut.energie : null;
  const defs = en && estRecord(en.definitions) ? en.definitions : {};
  const aConfirmer: Array<{ cle: string; libelle: string }> = [];
  if (Array.isArray(brut.a_confirmer)) {
    for (const a of brut.a_confirmer) {
      if (estRecord(a) && texteServi(a.cle) && texteServi(a.libelle)) {
        aConfirmer.push({ cle: a.cle as string, libelle: a.libelle as string });
      }
    }
  }
  const postesHorsTotal: SyntheseCi['postesHorsTotal'] = [];
  // CPRW23 — le payload public sert ces postes dans `a_confirmer[cle='a_chiffrer_visite'].postes` ; la clé
  // `postes_hors_total` n'est lue qu'en repli, si elle est servie. Les autres entrées de `a_confirmer` ne sont jamais réaffichées.
  const aChiffrer = Array.isArray(brut.a_confirmer)
    ? brut.a_confirmer.find((a) => estRecord(a) && a.cle === 'a_chiffrer_visite' && Array.isArray(a.postes))
    : undefined;
  const sourcePostes: unknown = aChiffrer ? (aChiffrer as Record<string, unknown>).postes : brut.postes_hors_total;
  if (Array.isArray(sourcePostes)) {
    for (const p of sourcePostes) {
      if (!estRecord(p)) continue;
      const designation = texteServi(p.designation);
      if (designation) postesHorsTotal.push({ role: texteServi(p.role), designation, catalogue: p.catalogue === true });
    }
  }
  const hypotheses: SyntheseCiHypothese[] = [];
  if (Array.isArray(brut.hypotheses)) {
    for (const h of brut.hypotheses) {
      if (!estRecord(h)) continue;
      const cle = texteServi(h.cle);
      const textes = lireTextesCi(h.textes);
      if (cle && textes) {
        hypotheses.push({ cle, textes, source: texteServi(h.source), date: texteServi(h.date) });
      }
    }
  }
  const omissions: Array<{ bloc: string; motif: string }> = [];
  if (Array.isArray(brut.omissions)) {
    for (const o of brut.omissions) {
      if (estRecord(o) && texteServi(o.bloc) && texteServi(o.motif)) {
        omissions.push({ bloc: o.bloc as string, motif: o.motif as string });
      }
    }
  }
  return {
    version: nombreServi(brut.version),
    segment: texteServi(brut.segment),
    statutEtude: texteServi(brut.statut_etude),
    aConfirmer,
    postesHorsTotal,
    systeme: sys
      ? {
          kwc: nombreServi(sys.kwc),
          nbPanneaux: nombreServi(sys.nb_panneaux),
          productionKwhAn: nombreServi(sys.production_kwh_an),
        }
      : null,
    energie: en
      ? {
          autoconsoPct: nombreServi(en.taux_autoconso_pct),
          couverturePct: nombreServi(en.taux_couverture_pct),
          methode: texteServi(en.methode),
          definitions: { autoconso: texteServi(defs.autoconso), couverture: texteServi(defs.couverture) },
        }
      : null,
    argent: lireArgentCi(brut.argent, nombreServi(estRecord(mk) ? mk.payback : null)),
    echeancier: Array.isArray(brut.echeancier)
      ? brut.echeancier.flatMap((e) => {
          if (!estRecord(e)) return [];
          const pct = nombreServi(e.pct);
          return pct === null ? [] : [{ libelle: texteServi(e.libelle), pct, montantTtc: nombreServi(e.montant_ttc), jalon: texteServi(e.jalon) }];
        })
      : [],
    optionServie: texteServi(brut.option_servie),
    optionBatterie: estRecord(brut.option_batterie)
      ? {
          valeurChiffree: estRecord(brut.option_batterie.valeur_chiffree)
            ? lireTextesCi(brut.option_batterie.valeur_chiffree.textes)
            : null,
          motif: texteServi(brut.option_batterie.motif),
          totaux: estRecord(brut.option_batterie.totaux)
            ? {
                htNet: nombreServi(brut.option_batterie.totaux.ht_net),
                tva: nombreServi(brut.option_batterie.totaux.tva),
                ttc: nombreServi(brut.option_batterie.totaux.ttc),
              }
            : null,
          chiffres: estRecord(brut.option_batterie.valeur_chiffree)
            ? {
                economieAnnuelleMad: nombreServi(brut.option_batterie.valeur_chiffree.economie_annuelle_mad),
                retourSimpleAns: nombreServi(brut.option_batterie.valeur_chiffree.retour_simple_ans),
                capaciteUtileKwh: nombreServi(brut.option_batterie.valeur_chiffree.capacite_utile_kwh),
                restitueKwhAn: nombreServi(brut.option_batterie.valeur_chiffree.restitue_kwh_an),
              }
            : null,
        }
      : null,
    services: estRecord(brut.services)
      ? {
          omLibelle: estRecord(brut.services.om_option) ? texteServi(brut.services.om_option.libelle) : null,
          suiviDelaiHeures: estRecord(brut.services.suivi_production)
            ? nombreServi(brut.services.suivi_production.delai_intervention)
            : null,
          garanties: lireGarantiesCi(brut.services.garanties),
          omOption: lireOmOptionCi(brut.services.om_option),
          suiviProduction: estRecord(brut.services.suivi_production)
            ? { delaiHeures: nombreServi(brut.services.suivi_production.delai_intervention) }
            : null,
          raccordementRegime: estRecord(brut.services.raccordement) ? texteServi(brut.services.raccordement.regime) : null,
        }
      : null,
    categorie: lireCategorieCi(brut.categorie),
    decarbonation: estRecord(brut.decarbonation) && lireTextesCi(brut.decarbonation.textes)
      ? { cbam: brut.decarbonation.cbam === true, textes: lireTextesCi(brut.decarbonation.textes)! }
      : null,
    entrepriseClient: estRecord(brut.entreprise_client)
      ? {
          raisonSociale: texteServi(brut.entreprise_client.raison_sociale),
          ice: texteServi(brut.entreprise_client.ice),
          interlocuteur: texteServi(brut.entreprise_client.interlocuteur),
          fonction: texteServi(brut.entreprise_client.fonction),
        }
      : null,
    hypotheses,
    omissions,
  };
}

/** L'argent C&I n'existe que si le serveur l'a CALCULÉ (`statut: 'calcule'`) et servi. */
export function argentCiCalcule(ci: SyntheseCi | null): SyntheseCiArgent | null {
  const a = ci?.argent ?? null;
  return a && a.statut === 'calcule' ? a : null;
}

/**
 * Économie de l'année 1 à mettre en avant, selon la base SERVIE : TTC quand la
 * base est `ttc`, sinon HT (`ht` ou `deux`, le TTC restant lisible à part).
 */
export function economieCiHero(a: SyntheseCiArgent | null): number | null {
  const e = a?.economieAnnee1 ?? null;
  if (!e) return null;
  const v = a!.base === 'ttc' ? (e.ttc ?? e.ht) : (e.ht ?? e.ttc);
  return v !== null && v > 0 ? v : null;
}

/**
 * Le bloc « Injection du surplus (loi 82-21) » d'un devis C&I : SEULEMENT si
 * `synthese_ci.argent.revente` est calculée (MT) — jamais sur la seule présence
 * d'une injection dans `mode_kpis`. La mention est le texte servi par
 * `synthese_ci.hypotheses[cle='revente']` (MENTION_82_21, CIQ305) ; sans elle, le
 * bloc est omis plutôt que d'écrire une mention dans la page.
 */
export function injectionCi(
  ci: SyntheseCi | null,
): { kwhAn: number | null; valeurMadAn: number | null; mention: TextesCi } | null {
  const rev = ci?.argent?.revente ?? null;
  if (!ci || !rev || rev.statut !== 'calculee') return null;
  const mention = ci.hypotheses.find((h) => h.cle === 'revente')?.textes ?? null;
  if (!mention) return null;
  return { kwhAn: rev.kwhAn, valeurMadAn: rev.valeurMadAn, mention };
}

// ── CIW303 — Options C&I : l'offre réseau d'abord, la batterie en option ─────

/**
 * CIW303 — le simulateur batterie (moteur horaire exécuté dans le NAVIGATEUR, calibré sur des
 * batteries Dyness 5/10 kWh, phrases résidentielles) n'est proposé qu'au RÉSIDENTIEL. En C&I,
 * la valeur d'une batterie est celle du moteur C&I (`synthese_ci.option_batterie`), jamais un
 * second moteur côté page.
 */
export function batterySimEligibleForMode(mode: string | null | undefined): boolean {
  return mode === 'residentiel';
}

/**
 * CPRW3 — bandeau « devis préliminaire » (décision fondateur 26/10/2026 : imprimé sur TOUT document
 * C&I, `quote_engine/ci/couverture.py::bandeau_reserve`). Le serveur ne sert l'hypothèse `visite`
 * que pour une étude sous réserve ; la page reprend alors MOT POUR MOT `ci/mentions.py::TEXTES_VISITE`
 * (garde de parité : `propositionSyntheseCiCIW300.test.ts`).
 */
export const CI_DEVIS_PRELIMINAIRE: TextesCi = {
  fr: 'Devis préliminaire — les prix pourront être ajustés après la visite technique.',
  en: 'Preliminary quote — prices may be adjusted after the technical site visit.',
  ar: 'عرض أولي — يمكن تعديل الأسعار بعد الزيارة التقنية.',
};

/** CPRW3 — texte du bandeau préliminaire : celui servi (hypothèse `visite`), sinon celui du PDF ; `null` hors C&I. */
export function bandeauPreliminaireCi(ci: SyntheseCi | null): TextesCi | null {
  if (!ci) return null;
  return ci.hypotheses.find((h) => h.cle === 'visite')?.textes ?? CI_DEVIS_PRELIMINAIRE;
}

// CPRW13 — mots du client pour le rôle d'un poste hors total : ceux du PDF (`i18n_labels.py` `ci_role_*`).
const ROLES_POSTES_CI: Record<string, TextesCi> = {
  cable_dc: { fr: 'câble DC', en: 'DC cable', ar: 'كابل التيار المستمر' },
  cable_ac: { fr: 'câble AC', en: 'AC cable', ar: 'كابل التيار المتردد' },
  structure_ci: { fr: 'structure de fixation', en: 'mounting structure', ar: 'هيكل التثبيت' },
  coffret_dc: { fr: 'coffret DC', en: 'DC box', ar: 'علبة التيار المستمر' },
  coffret_ac: { fr: 'coffret AC', en: 'AC box', ar: 'علبة التيار المتردد' },
  protection_ac: { fr: 'protection AC', en: 'AC protection', ar: 'حماية التيار المتردد' },
  onduleur_string_tri: { fr: 'onduleur', en: 'inverter', ar: 'العاكس' },
  onduleur_string_mono: { fr: 'onduleur', en: 'inverter', ar: 'العاكس' },
};

// CPRW13 — `i18n_labels.py` `ci_a_chiffrer_hors_total` (le PDF).
const A_CHIFFRER_HORS_TOTAL: TextesCi = {
  fr: 'À chiffrer après la visite technique (hors total) : ',
  en: 'To be priced after the site visit (not in the total): ',
  ar: 'يُسعَّر بعد الزيارة التقنية (خارج المجموع): ',
};

/**
 * CPRW13 — la ligne du PDF sous le bandeau préliminaire (`couverture.py::ligne_postes_hors_total`) :
 * « À chiffrer après la visite technique (hors total) : câble DC — <article>, structure de fixation ».
 * Rôle en mots simples, article du catalogue après « — » (non traduit, comme le PDF), un rôle inconnu
 * garde la désignation, doublons retirés, JAMAIS un montant. `null` sans poste servi.
 */
export function lignePostesHorsTotalCi(ci: SyntheseCi | null): TextesCi | null {
  const postes = ci?.postesHorsTotal ?? [];
  if (postes.length === 0) return null;
  const construire = (lg: keyof TextesCi): string => {
    const vus: string[] = [];
    for (const p of postes) {
      const role = p.role ? ROLES_POSTES_CI[p.role]?.[lg] : undefined;
      const texte = role === undefined ? p.designation : p.catalogue ? `${role} — ${p.designation}` : role;
      if (texte && !vus.includes(texte)) vus.push(texte);
    }
    return vus.join(', ');
  };
  return { fr: A_CHIFFRER_HORS_TOTAL.fr + construire('fr'), en: A_CHIFFRER_HORS_TOTAL.en + construire('en'), ar: A_CHIFFRER_HORS_TOTAL.ar + construire('ar') };
}

const NON_CHIFFREE: TextesCi = {
  fr: 'valeur non chiffrée',
  en: 'value not quantified',
  ar: 'القيمة غير مقدَّرة بالأرقام',
};

/**
 * CIW303 — la ligne « valeur » d'une option batterie C&I : le texte SERVI par le moteur quand
 * il chiffre la valeur ; sinon « valeur non chiffrée » (+ le motif servi). La page ne calcule
 * jamais une économie de batterie.
 */
export function valeurOptionBatterieCi(
  ci: SyntheseCi | null,
): { chiffree: boolean; textes: TextesCi; motif: string | null } | null {
  const ob = ci?.optionBatterie ?? null;
  if (!ob) return null;
  if (ob.valeurChiffree) return { chiffree: true, textes: ob.valeurChiffree, motif: null };
  return { chiffree: false, textes: NON_CHIFFREE, motif: ob.motif && ob.motif !== NON_CHIFFREE.fr ? ob.motif : null };
}

/** L'offre principale d'un devis C&I (réseau seul sauf `option_servie` = `avec_batterie`). */
export function offrePrincipaleCi(ci: SyntheseCi | null): OptionKey {
  return ci?.optionServie === 'avec_batterie' ? 'avec_batterie' : 'sans_batterie';
}

/** CIW305 — un devis C&I exige l'identité de l'entreprise à la signature (commercial / industriel). */
export function signatureEntrepriseRequise(mode: string | null | undefined): boolean {
  return mode === 'commercial' || mode === 'industriel';
}

/**
 * CIW306 — le bloc catégorie d'un devis COMMERCIAL, tel que servi (`synthese_ci.categorie`, CIQ330) :
 * titre, accroche et lignes FR/EN/AR. `null` hors commercial, sans catégorie servie, ou si rien
 * n'est lisible (libellé, accroche, titre et lignes tous absents) : le bloc est alors omis.
 */
export function categorieCi(ci: SyntheseCi | null): SyntheseCiCategorie | null {
  if (!ci || ci.segment === 'industriel') return null;
  const c = ci.categorie;
  if (!c) return null;
  if (!c.libelle && !c.accroche && !c.titre && c.lignes.length === 0) return null;
  return c;
}

// ── CIW307 — la carte industrielle de /proposition : les MÊMES textes que le PDF ─────────────

/** Les clés d'hypothèses servies que la carte industrielle reprend (CIQ305), dans cet ordre. */
const CLES_CARTE_INDUSTRIELLE = ['puissance_souscrite', 'pointe'] as const;

/**
 * CIW307 — la carte industrielle lit `synthese_ci` : (a) les hypothèses `puissance_souscrite`
 * (« la puissance souscrite et la prime fixe ne changent pas ») et `pointe` (« la pointe n'est
 * sécurisée qu'avec un stockage ») — le texte EXACT du PDF ; (b) la décarbonation servie
 * (CIQ344) : la phrase CBAM SEULEMENT si le serveur lève le drapeau `cbam` (export UE déclaré de
 * ciment ou d'engrais), sinon la phrase générique. Aucun texte n'est écrit dans la page ; aucun
 * CO₂ chiffré. `null` hors industriel.
 */
export function carteIndustrielleCi(
  ci: SyntheseCi | null,
): { hypotheses: SyntheseCiHypothese[]; decarbonation: { cbam: boolean; textes: TextesCi } | null } | null {
  if (!ci || ci.segment !== 'industriel') return null;
  const hypotheses = CLES_CARTE_INDUSTRIELLE.map((c) => ci.hypotheses.find((h) => h.cle === c)).filter(
    (h): h is SyntheseCiHypothese => !!h,
  );
  return { hypotheses, decarbonation: ci.decarbonation };
}

// ── CIW308 — la rentabilité d'un devis INDUSTRIEL : celle du PDF, lue telle quelle ───────────

/** Les jalons affichés (D-CIQ-10) : 5 / 10 / 15 / 20 / 25 ans. */
export const JALONS_RENTABILITE_ANS = [5, 10, 15, 20, 25] as const;

export interface RentabiliteCi {
  /** Base servie : `ht` | `ttc` | `deux`. */
  base: string | null;
  /** Jalons de cumul net dans la base principale (TTC seulement si la base servie est `ttc`). */
  jalons: Array<{ annee: number; cumul: number }>;
  /** Jalons TTC (base « deux » seulement). */
  jalonsTtc: Array<{ annee: number; cumul: number }>;
  triPct: number | null;
  /** « TRI sur N ans » — l'horizon SERVI. */
  triHorizonAns: number | null;
  /** LCOE servi et le prix moyen du kWh évité du client, face à face. */
  lcoeMadKwh: number | null;
  tarifKwhEvite: number | null;
  /** VAN seulement si servie (taux déclaré) ; sinon `null` — le bloc VAN est omis. */
  vanMad: number | null;
  tauxActualisationPct: number | null;
  sensibilites: SyntheseCiArgent['sensibilites'];
  financement: SyntheseCiArgent['financement'];
}

/**
 * CIW308 — la section rentabilité d'un devis INDUSTRIEL : `synthese_ci.argent` tel que servi
 * (jalons 5/10/15/20/25, TRI sur N ans, LCOE face au tarif, VAN et sensibilités seulement si
 * servies, financement s'il est servi). `null` hors industriel, argent omis/non calculé, ou si
 * rien d'exploitable n'est servi (aucun jalon, TRI, LCOE) : la section est alors omise.
 */
export function rentabiliteCi(ci: SyntheseCi | null): RentabiliteCi | null {
  if (!ci || ci.segment !== 'industriel') return null;
  const a = argentCiCalcule(ci);
  if (!a) return null;
  const garde = (j: Array<{ annee: number; cumul: number }>) =>
    JALONS_RENTABILITE_ANS.flatMap((an) => {
      const x = j.find((e) => e.annee === an);
      return x ? [x] : [];
    });
  const principal = a.base === 'ttc' && a.jalonsTtc.length > 0 ? a.jalonsTtc : a.jalons;
  const jalons = garde(principal);
  const ind = a.indicateurs;
  const r: RentabiliteCi = {
    base: a.base,
    jalons,
    jalonsTtc: a.base === 'deux' ? garde(a.jalonsTtc) : [],
    triPct: ind?.triPct ?? null,
    triHorizonAns: ind?.triHorizonAns ?? null,
    lcoeMadKwh: ind?.lcoeMadKwh ?? null,
    tarifKwhEvite: ind?.tarifKwhEvite ?? null,
    vanMad: ind?.vanMad ?? null,
    tauxActualisationPct: a.tauxActualisationPct,
    sensibilites: a.sensibilites,
    financement: a.financement,
  };
  if (r.jalons.length === 0 && r.triPct === null && r.lcoeMadKwh === null) return null;
  return r;
}
