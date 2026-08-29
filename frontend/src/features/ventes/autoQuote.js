/* Création du « devis automatique » — logique PARTAGÉE entre le générateur
   complet (DevisGenerator) et le panneau devis inline de la fiche lead
   (LeadDevisPanel). Source unique : on ne duplique JAMAIS le calcul de prix.

   Sensible au marché du lead : résidentiel (historique), agricole (pompage,
   mêmes appels que le flux manuel) ou industriel (dimensionnement factures +
   étude d'autoconsommation). Lit le lead directement (pas d'état React). */
import { createDevis, addLigneDevis } from './store/ventesSlice'
// U3 — le devis résidentiel auto est COMPOSÉ ET CRÉÉ par le serveur
// (POST /ventes/devis/auto/) : cet écran ne compose plus de lignes
// résidentielles. Voir la branche `mode === 'residentiel'` plus bas.
import ventesApi from '../../api/ventesApi'
import {
  estimerMois, htFromTtc, ttcFromHt, optionTotalsTTC,
  autoFillLines, computeEtudeIndustrielle, panneauxPourKwc,
  autoFillPompage, pompageSelection, HEURES_POMPAGE_DEFAUT,
  KWH_PRICE, EFFICIENCY, DAY_USAGE_DEFAULTS,
  // Règle fondateur du 18/08 — dimensionnement par PALIERS de 5 kWc, retenus
  // au payback le plus court (jamais un panneau/900 MAD nu).
  estimerKwcDepuisFacture, arrondirAuPasKwc, optimalKwcByPayback,
  // PVMRQ — libellé FR d'un rôle, pour dire QUELLE marque épinglée manque.
  roleLabel,
  // PACT10/QF-REAL — consommation annuelle RÉELLE du lead, dérivée de ses
  // factures par l'inverse EXACT du barème (`kwhFromBill`, QF4). UNE seule
  // dérivation partagée : elle alimente à la fois le balayage de
  // dimensionnement (sans elle, l'économie ne sature pas) et
  // `etude_params.conso_annuelle` envoyée au serveur.
  consoAnnuelleDepuisFactures,
} from './solar'

// QX19 — préférence de structure du lead (acier/aluminium) → structureType
// d'autoFillLines/autoFillPompage. Défaut historique 'acier' quand non renseigné.
const structFromLead = (lead) =>
  (lead && lead.structure_pref === 'aluminium') ? 'aluminium' : 'acier'

// ERR107 — Cohérence d'arrondi écran : une ligne est ENREGISTRÉE en HT 2 déc.
// (htFromTtc), donc le TTC RÉAFFICHÉ d'une ligne est ttcFromHt(htFromTtc(ttc)),
// qui peut différer du TTC brut saisi d'1 MAD. Pour que le total d'étude affiché
// à l'écran corresponde exactement à la somme des lignes telles que l'écran les
// recompose, on aligne d'abord chaque prix_unit_ttc sur ce même aller-retour.
// (Écran uniquement — le PDF backend recalcule de façon autoritaire.)
const screenTtc = (r) => ttcFromHt(htFromTtc(r.prix_unit_ttc, r.taux_tva ?? 20), r.taux_tva ?? 20)
const roundTripRowsTtc = (rows) => rows.map((r) => ({ ...r, prix_unit_ttc: screenTtc(r) }))

// QX52 — parité 4 modes : `commercial` route désormais vers son PROPRE mode
// (plus le repli historique vers `industriel`). Aucun mode ne tombe dans un
// libellé/comportement d'un autre.
export const LEAD_TYPE_TO_MODE = {
  residentiel: 'residentiel', commercial: 'commercial',
  industriel: 'industriel', agricole: 'agricole',
}

// Paramètres d'étude pompage stockés avec le devis : chiffres canoniques
// calculés UNE fois, le PDF les rend tels quels. Partagé entre la création
// manuelle (DevisGenerator.handleSubmit) et le devis auto — mêmes expressions.
export const buildEtudePompage = (sel, { typePompe, alim, hmt, debit, heures,
                                         profondeur, distance }) => ({
  pompe_cv: String(sel.cv),
  pompe_kw: sel.kw,
  pompe_nom: sel.pump?.nom || null,
  type_pompe: typePompe,
  alim,
  hmt_m: hmt || null,
  debit_souhaite_m3h: debit || null,
  debit_hmt_m3h: sel.debitHmt,
  heures_pompage: sel.m3Jour != null ? (parseFloat(heures) || null) : null,
  m3_jour: sel.m3Jour,
  profondeur_m: profondeur || null,
  distance_m: distance || null,
  champ_kwc: sel.dims.champKwc,
})

/**
 * Crée un devis auto-dimensionné depuis un lead. Retourne l'id du devis créé.
 * Lève { detail } si le lead n'a pas les données requises (mêmes règles que la
 * garde serveur POST /devis-auto/).
 *
 * @param {object}   lead         Lead complet (facture_hiver, pompe_*, etc.)
 * @param {object[]} produits     Catalogue stock
 * @param {string}   discountStr  Remise globale en %
 * @param {function} dispatch     Redux dispatch
 * @param {number}   pumpHours    Heures de pompage/jour (réglage entreprise
 *                                agricole_pump_hours) ; défaut historique sinon
 * @param {function} onEtude      Rappel facultatif recevant les chiffres clés de
 *                                l'étude industrielle (autoconso/éco/payback)
 *                                AVANT enregistrement — pour les afficher
 * @param {string|number} targetKwc  EZ5 — puissance cible (kWc) demandée POUR
 *                                CE devis-là, sans toucher la fiche du lead.
 *                                Vide/absent = comportement historique (la
 *                                taille souhaitée du lead, sinon la facture).
 * @param {object}   marques      PVMRQ — marques préférées par rôle (gamme
 *                                active, `ParametresGammes.marques[slot]`) ;
 *                                transmise telle quelle à `optimalKwcByPayback`
 *                                et `autoFillLines`. Absente/vide = comportement
 *                                historique (aucune préférence).
 * @param {string[]} ordreLignes  PVORD (fondateur 19/08/2026) — ordre par
 *                                défaut des lignes (`ParametresGammes.
 *                                ordre_lignes`), transmis tel quel à
 *                                `autoFillLines`. Absente/vide = ordre
 *                                canonique du simulateur (comportement
 *                                historique).
 */
export async function createAutoQuote({ lead, produits, discountStr, dispatch,
                                        quoteLogic, pumpHours, onEtude,
                                        targetKwc, marques, ordreLignes }) {
  // Logique de devis éditable (Paramètres → Avancé) ; sans valeur = défauts.
  const kwhPrice = (Number(quoteLogic?.kwhPrice) > 0) ? Number(quoteLogic.kwhPrice) : KWH_PRICE
  const efficiency = (Number(quoteLogic?.efficiency) > 0) ? Number(quoteLogic.efficiency) : EFFICIENCY
  // U3-900 — `panneauxParTranche` (réglage Paramètres → Avancé de la règle des
  // 900 DH/mois) n'est plus lu ICI : la règle a été supprimée (fondateur
  // 29/08/2026). Voir la doc du paramètre lui-même (solar.js) pour son statut.
  // Heures de pompage effectives : réglage entreprise (agricole_pump_hours) si
  // fourni, sinon le défaut marché historique — comme le générateur manuel.
  const heuresPompage = (Number(pumpHours) > 0) ? Number(pumpHours) : HEURES_POMPAGE_DEFAUT
  const mode = LEAD_TYPE_TO_MODE[lead.type_installation] || 'residentiel'
  const extra = {}
  let rows
  if (mode === 'agricole') {
    const opts = {
      cv: lead.pompe_cv != null ? String(lead.pompe_cv) : '',
      alim: 'tri', typePompe: 'immergee', distance: '20',
      // QX19 — respecte la préférence de structure du lead (défaut acier).
      structureType: structFromLead(lead),
      hmt: lead.pompe_hmt_m != null ? String(lead.pompe_hmt_m) : '',
      debit: lead.pompe_debit_m3h != null ? String(lead.pompe_debit_m3h) : '',
      heures: String(heuresPompage),
    }
    rows = autoFillPompage(produits, opts)
    if (!rows.some(r => r.produit && parseFloat(r.quantite) > 0)) {
      throw {
        detail: 'Devis auto impossible : renseignez sur le lead la puissance '
          + 'pompe (CV) ou la HMT et le débit souhaité, puis réessayez.',
      }
    }
    extra.mode_installation = 'agricole'
    extra.etude_params = buildEtudePompage(
      pompageSelection(produits, opts), { ...opts, profondeur: '' })
  } else {
    const hiver = parseFloat(lead.facture_hiver) || 0
    // QX19 — priorité à la taille souhaitée par le lead (kWc) quand elle est
    // renseignée ; sinon dérivation depuis la facture d'hiver. EZ5 — une cible
    // saisie POUR CE DEVIS (« Devis automatique » de la fiche lead) passe
    // devant les deux : c'est un choix ponctuel du commercial, il ne réécrit
    // jamais `taille_souhaitee_kwc` sur le lead. Même conversion partagée
    // `panneauxPourKwc` — aucune formule recopiée.
    // Règle fondateur du 18/08 — une taille EXPLICITE (cible du devis ou
    // taille souhaitée du lead) est ramenée au palier de 5 kWc le plus proche
    // (`arrondirAuPasKwc`) : aucun devis auto ne peut sortir une taille hors
    // palier. Sans taille explicite, le besoin se lit sur la facture d'hiver
    // (`estimerKwcDepuisFacture`) et la taille retenue est le palier au
    // payback le plus court (`optimalKwcByPayback`) — jamais le plus gros qui
    // rentre sur le toit.
    const cibleKwc = parseFloat(targetKwc) || 0
    const explicitKwc = cibleKwc > 0 ? cibleKwc : (parseFloat(lead.taille_souhaitee_kwc) || 0)
    const tailleKwc = explicitKwc > 0 ? arrondirAuPasKwc(explicitKwc) : 0
    let panels = 0
    if (tailleKwc > 0) {
      panels = panneauxPourKwc(tailleKwc, 710)
    } else if (mode !== 'residentiel') {
      // U3-MOTEUR (fondateur 29/08/2026, « ALL sizing goes through the new
      // sizing tool ») — LE BALAYAGE LOCAL PAR PALIERS N'EST PLUS LA SOURCE DE
      // DIMENSIONNEMENT DU RÉSIDENTIEL. C'était le dernier contournement : au
      // -dessus du seuil de facture, cet écran chiffrait lui-même les paliers
      // de 5 kWc (`optimalKwcByPayback`) et expédiait le résultat en
      // `target_kwc` SOUVERAIN — ces devis-là ne touchaient jamais le moteur
      // horaire (PVGIS × consommation réelle heure par heure), donc deux
      // méthodes de dimensionnement coexistaient selon le montant de la
      // facture. Désormais, en résidentiel, `panels` reste à 0 : `target_kwc`
      // est OMIS plus bas et c'est `build_devis_auto` (moteur horaire) qui
      // dimensionne — ou refuse en NOMMANT la donnée manquante.
      // Une taille EXPLICITE (cible tapée pour ce devis, ou `taille_souhaitee_kwc`
      // du lead) reste SOUVERAINE : elle est traitée par la branche ci-dessus,
      // avant celle-ci, et part telle quelle. Seule la valeur AUTO-CALCULÉE
      // cesse d'être expédiée.
      // Industriel/commercial gardent ce balayage : aucun moteur serveur ne
      // les dimensionne (`build_devis_auto` ne gère que le résidentiel), et
      // sans lui ils n'auraient plus AUCUNE taille (voir le refus explicite
      // plus bas).
      const besoinKwc = estimerKwcDepuisFacture(hiver)
      if (besoinKwc > 0) {
        const eteVal = (lead.ete_differente && lead.facture_ete)
          ? parseFloat(lead.facture_ete) : hiver
        const dayUsagePct = mode === 'commercial' ? DAY_USAGE_DEFAULTS['Commerciale']
          : mode === 'industriel' ? DAY_USAGE_DEFAULTS['Industrielle']
            : DAY_USAGE_DEFAULTS['Résidentielle']
        // FINDING 25/08 — la CONSOMMATION RÉELLE entre dans le balayage. Sans
        // elle, `computeROI` ne plafonne pas l'économie à ce que le client
        // peut consommer : elle reste linéaire en kWc, chaque pas marginal se
        // « rembourse » et l'ascension ne s'arrête qu'au plafond du balayage
        // (mesuré : besoin 100 kWc → 100 kWc retenus, 522 341 MAD). C'est la
        // MÊME dérivation que `etude_params.conso_annuelle` posée plus bas —
        // désormais partagée (`consoAnnuelleDepuisFactures`), donc impossible
        // à faire diverger entre le dimensionnement et l'étude envoyée.
        const facturesBalayage = estimerMois(hiver, eteVal)
        const distributeurBalayage = ['onee', 'lydec', 'redal'].includes(lead.distributeur)
          ? lead.distributeur : undefined
        const opt = optimalKwcByPayback({
          produits, factures: facturesBalayage, dayUsagePct,
          panelW: 710, structureType: structFromLead(lead),
          discountPct: discountStr || '0', kwhPrice, efficiency, besoinKwc,
          marques,
          consoAnnuelleKwh: consoAnnuelleDepuisFactures(
            facturesBalayage, distributeurBalayage),
          utility: distributeurBalayage,
        })
        // U3-900 (fondateur 29/08/2026) — plus de repli `estimerPanneaux`
        // (panneaux/900 MAD, supprimé du backend le même jour). `panels`
        // reste à 0 quand l'optimiseur local n'a rien retenu : sur ces
        // marchés (industriel/commercial) c'est un refus EXPLICITE plus bas,
        // jamais une taille devinée sur une règle qui n'existe plus.
        panels = opt.nbPanneaux > 0 ? opt.nbPanneaux : 0
      }
      // besoinKwc <= 0 (facture sous le seuil du balayage local) : `panels`
      // reste à 0, MÊME raison — voir la note ci-dessus.
    }
    // U3-900 — un `panels` nul n'est PAS une composition « à 0 panneau » : en
    // résidentiel il veut dire « le serveur dimensionne » (target_kwc omis
    // plus bas) ; pour les autres marchés (aucun moteur serveur pour eux),
    // c'est un vrai refus explicite plus bas — jamais un devis vide créé en
    // silence.
    const kwpAuto = panels > 0 ? panels * 710 / 1000 : 0

    // ── U3 (fondateur 20/08/2026) — LE RÉSIDENTIEL NE COMPOSE PLUS ICI ─────
    // Ordre fondateur APPLIQUÉ par ce fichier : la composition n'a plus
    // qu'UNE source de vérité (le serveur) et cet écran la consomme.
    //
    // Il y en avait bien deux : cet écran composait le kit en JavaScript
    // (`autoFillLines`) pendant que le serveur le composait en Python
    // (`composition_residentielle`) — et les deux avaient divergé sur le
    // câble au mètre, les marques épinglées, l'ordre des lignes et l'arrondi
    // du nombre de panneaux. Désormais le devis résidentiel auto part au
    // serveur avec la SEULE chose que l'écran a décidée — la PUISSANCE CIBLE
    // — et c'est le serveur qui compose ET crée les lignes : catalogue,
    // ordre (PVORD), marques épinglées (PVMRQ), câble au mètre × paires (C4),
    // scénario batterie (U2). Aucune ligne, aucun prix, aucune marque ne
    // remonte d'ici : il n'y a plus rien à faire diverger.
    //
    // Ce qui reste À L'ÉCRAN est le DIMENSIONNEMENT (le balayage par palier
    // au payback le plus court ci-dessus) et l'étude PACT10 : ce sont des
    // décisions commerciales, pas une composition — elles voyagent en
    // paramètres, jamais en lignes.
    if (mode === 'residentiel') {
      const etudeExtra = {}
      // PACT10/QF-REAL — les 12 factures RÉELLES du client (et la
      // consommation annuelle qui s'en déduit) : sans elles, le PDF
      // reconstruit les « factures avant » depuis l'économie SUPPOSÉE, un
      // proxy circulaire. Le `scenario`, lui, n'est PLUS envoyé d'ici : le
      // serveur le décide depuis `lead.batterie_souhaitee` (défaut « les
      // deux » — U2), sinon on recréerait à l'instant la divergence qu'on
      // vient de supprimer.
      if (hiver > 0) {
        const eteReel = (lead.ete_differente && lead.facture_ete)
          ? parseFloat(lead.facture_ete) : hiver
        const facturesReelles = estimerMois(hiver, eteReel)
        const distributeurLead = ['onee', 'lydec', 'redal'].includes(lead.distributeur)
          ? lead.distributeur : undefined
        // Dérivation PARTAGÉE avec le dimensionnement ci-dessus (le balayage
        // par palier a besoin de la MÊME consommation pour que son modèle
        // d'économie sature) — une seule formule, jamais deux chiffres qui
        // pourraient diverger.
        const consoAnnuelleReelle = consoAnnuelleDepuisFactures(
          facturesReelles, distributeurLead)
        etudeExtra.factures_mensuelles_reelles = facturesReelles
        if (consoAnnuelleReelle > 0) etudeExtra.conso_annuelle = consoAnnuelleReelle
        if (distributeurLead) etudeExtra.distributeur = distributeurLead
      }
      let reponse
      try {
        reponse = await ventesApi.creerDevisAuto({
          lead: lead.id,
          remise_globale: discountStr || '0',
          // U3-MOTEUR — `kwpAuto` ne peut plus venir ici que d'une taille
          // EXPLICITEMENT choisie par un humain (cible tapée pour ce devis, ou
          // `taille_souhaitee_kwc` du lead) : elle reste souveraine et le
          // serveur en redérive le MÊME nombre de panneaux (plafond tolérant
          // au flottant, verrouillé des deux côtés par un test d'aller-retour).
          // Sans taille explicite, `kwpAuto` vaut 0 et `target_kwc` est OMIS :
          // c'est le moteur horaire de `build_devis_auto` qui dimensionne (et
          // refuse en nommant la donnée manquante) — plus AUCUNE puissance
          // auto-calculée côté écran n'est expédiée.
          ...(kwpAuto > 0 ? { target_kwc: kwpAuto } : {}),
          ...(Object.keys(etudeExtra).length ? { etude_params: etudeExtra } : {}),
        })
      } catch (err) {
        // Le serveur parle FRANÇAIS (422 : marque épinglée introuvable,
        // données de dimensionnement manquantes…) et ses appelants lisent
        // `err.detail` — on rend son message tel quel, jamais un nôtre.
        throw {
          detail: err?.response?.data?.detail
            || "Le devis automatique a échoué — vérifiez la fiche du lead et réessayez.",
        }
      }
      const id = reponse?.data?.id
      if (!id) {
        throw { detail: 'Devis créé sans identifiant — ouvrez-le depuis la liste des devis.' }
      }
      return id
    }

    // U3-900 (fondateur 29/08/2026) — industriel/commercial n'ont AUCUN
    // moteur serveur pour se dimensionner eux-mêmes ici (celui de
    // `build_devis_auto` ne gère que le résidentiel) : sans `estimerPanneaux`
    // pour deviner une taille (supprimé), un `panels` toujours nul créerait
    // silencieusement un devis SANS panneau. On refuse explicitement à la
    // place — même idiome que la garde agricole plus haut — plutôt que de
    // laisser passer un devis vide.
    if ((mode === 'industriel' || mode === 'commercial') && panels <= 0) {
      throw {
        detail: 'Devis auto impossible : renseignez sur le lead une facture '
          + "d'électricité exploitable (ou la taille souhaitée en kWc), puis réessayez.",
      }
    }

    rows = autoFillLines(produits, {
      kwp: kwpAuto, panelW: 710, nbPanneaux: panels,
      // QX19 — respecte la préférence de structure du lead (défaut acier).
      structureType: structFromLead(lead),
      marques,
      // PVORD — ordre par défaut de la société (voir la doc du paramètre
      // plus haut) ; absent/vide = ordre canonique inchangé.
      ordreLignes,
    })
    // PVMRQ — GARDE : une marque épinglée sans AUCUN candidat en stock laisse
    // des lignes PLACEHOLDER (aucun produit, 0 MAD) que le filtre
    // d'enregistrement plus bas (`r.produit && quantite > 0`) écarte
    // silencieusement — le devis partait SANS panneaux, à un prix effondré.
    // On refuse, avec EXACTEMENT le message du bandeau de DevisGenerator
    // (LeadDevisPanel rend `err.detail` tel quel).
    const marquesAbsentes = rows.marquesManquantes ?? []
    const panneauxSansProduit = rows.some(
      r => !r.produit && /panneau/i.test(r.designation || '')
        && parseFloat(r.quantite) > 0)
    if (marquesAbsentes.length) {
      throw {
        detail: `Marque épinglée introuvable au stock : ${marquesAbsentes
          .map(m => `${m.marque} (${roleLabel(m.role)})`).join(', ')}. `
          + 'Ajoutez le produit ou changez la marque dans Paramètres → Gammes.',
      }
    }
    if (panneauxSansProduit) {
      throw {
        detail: 'Devis auto impossible : aucun panneau du stock ne correspond '
          + 'à cette composition. Complétez le catalogue, puis réessayez.',
      }
    }
    // QX19 — scénario batterie SEMÉ depuis batterie_souhaitee du lead : porté
    // dans etude_params pour que le PDF (builder QF6) restreigne le document au
    // choix du client (« sans »/« avec »/« les deux »). Défaut « les deux »
    // (comportement historique) quand non renseigné.
    const _bat = lead.batterie_souhaitee
    extra.etude_params = {
      ...(extra.etude_params || {}),
      scenario: _bat === 'sans' ? 'Sans batterie'
        : _bat === 'avec' ? 'Avec batterie'
          : 'Les deux (Sans + Avec)',
    }
    // U3 — le bloc PACT10/QF-REAL (12 factures RÉELLES du client semées dans
    // `etude_params`) vivait ICI ; il a MIGRÉ dans la branche résidentielle
    // ci-dessus, qui part au serveur. Il n'est plus atteignable d'ici : à ce
    // point, `mode` ne peut plus valoir 'residentiel'.

    // QX52 — industriel ET commercial partagent l'étude d'autoconsommation ; le
    // day-share diffère (industriel 80 % vs commercial 80 % archétype par défaut)
    // et chaque mode garde SON `mode_installation` (jamais un repli croisé).
    if (mode === 'industriel' || mode === 'commercial') {
      const ete = (lead.ete_differente && lead.facture_ete)
        ? parseFloat(lead.facture_ete) : hiver
      const moisAuto = hiver > 0 ? estimerMois(hiver, ete) : []
      const avgAuto = moisAuto
        .reduce((s, v) => s + (parseFloat(v) || 0), 0) / 12
      const conso = (parseFloat(lead.conso_mensuelle_kwh) || 0)
        || (avgAuto > 0 ? Math.round(avgAuto / kwhPrice) : 0)
      extra.mode_installation = mode
      const _dayUsage = mode === 'commercial'
        ? DAY_USAGE_DEFAULTS['Commerciale'] : DAY_USAGE_DEFAULTS['Industrielle']
      const _scenarioPrev = extra.etude_params?.scenario
      const _etudeInd = (kwpAuto > 0 && conso > 0)
        ? computeEtudeIndustrielle({
            kwp: kwpAuto, consoMensuelleKwh: conso,
            dayUsagePct: _dayUsage,
            totalTtc: optionTotalsTTC(roundTripRowsTtc(rows), discountStr || '0').totalSans,
            kwhPrice, efficiency,
          })
        : null
      // QX19 — préserve le scénario batterie semé du lead (défaut industriel :
      // sans batterie, réseau) même quand l'étude industrielle est calculée.
      extra.etude_params = {
        ...(_etudeInd || {}),
        scenario: lead.batterie_souhaitee ? _scenarioPrev : 'Sans batterie',
      }
      // Surface les chiffres clés (taux d'autoconsommation, économies, payback)
      // AVANT enregistrement, pour que l'appelant puisse les afficher.
      if (extra.etude_params && typeof onEtude === 'function') {
        onEtude({
          taux_autoconso: extra.etude_params.taux_autoconso,
          economies_annuelles: extra.etude_params.economies_annuelles,
          payback: extra.etude_params.payback,
        })
      }
    }
  }
  const devis = await dispatch(createDevis({
    lead: lead.id,
    statut: 'brouillon',
    taux_tva: '20.00',
    remise_globale: discountStr || '0',
    note: null,
    ...extra,
  })).unwrap()
  // PVORD (fondateur 19/08/2026) — ordre PAR DÉFAUT des lignes = l'ordre
  // canonique du simulateur (celui produit par `rows`, éventuellement déjà
  // réordonné selon `ParametresGammes.ordre_lignes` — voir `autoFillLines`).
  // Les créations restent concurrentes (`Promise.all`) : sans `ordre`
  // explicite, le tri en base retombait sur `id` = ordre d'ARRIVÉE réseau
  // (une course), pas l'ordre voulu. `idx` est calculé de façon SYNCHRONE sur
  // le tableau filtré avant tout dispatch, donc déterministe malgré la
  // concurrence des requêtes.
  await Promise.all(rows
    .filter(r => r.produit && parseFloat(r.quantite) > 0)
    .map((r, idx) => dispatch(addLigneDevis({
      devis: devis.id,
      produit: parseInt(r.produit),
      designation: r.designation,
      quantite: String(r.quantite),
      prix_unitaire: htFromTtc(r.prix_unit_ttc, r.taux_tva ?? 20),
      remise: '0',
      taux_tva: String(r.taux_tva ?? 20),
      ordre: idx,
    })).unwrap()))
  return devis.id
}
