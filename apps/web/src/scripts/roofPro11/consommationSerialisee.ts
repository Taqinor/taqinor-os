/**
 * ACAL780 — la CONSTRUCTION du bloc `consumption` du document (contrat CALX251), extraite de
 * `prefill.ts::serializeConsumption` (fichier-mur) pour y ajouter `charges` sans le faire grossir.
 * Même comportement qu'avant pour tout ce qui n'est pas `charges`.
 */
import { type Ctx } from './context';
import { type Appliance } from '../../lib/applianceConsumption';
import { chargesPourDocument, releireCharges, type ChargeAvenir } from './chargesAvenir';
import { baselineCurve, composeConsumption, emptyCurve } from '../../lib/applianceConsumption';
import { billToAnnualKwh } from '../../lib/estimatorBrainV2';
import { factureCarteDe } from './factureCarte';
import { facturesAEcrire, type FactureMois } from './consommationMois';
import { type SerializedConsumption as ConsommationBase } from './prefill';

/** ACAL1610 — le bloc, avec les factures mensuelles saisies (`$defs/consumption.factures_mois`). */
type SerializedConsumption = ConsommationBase & { factures_mois?: FactureMois[] };

/**
 * Les charges à venir à écrire : celles de l'écran (`ctx.consCharges`, posées par le panneau
 * « Mode expert ») si l'utilisateur y a touché, sinon celles RELUES du document, réémises telles
 * quelles ; `null` = rien à écrire (aucune clé `charges`).
 */
export function chargesAEcrire(ctx: Ctx): ChargeAvenir[] | null {
  const ecran = ctx.consCharges;
  if (Array.isArray(ecran)) return chargesPourDocument(ecran);
  const relues = releireCharges(ctx.documentRelu?.consumption);
  return relues.length ? chargesPourDocument(relues) : null;
}

/**
 * ACAL1609 — la courbe de BASE écrite : celle de l'écran quand elle porte de l'énergie (ou
 * qu'elle a été éditée à la main) ; sinon la courbe de la facture, composée comme
 * `consumption.ts::rebuildConsCurve` — socle de la session, à défaut la facture du lead servie
 * à l'atelier (`opts.factureMensuelleMad`, convertie comme la carte « Recommandation »). Une
 * charge ajoutée seule n'écrit plus une maison à zéro. Aucune facture ni socle (ACAL1962) : AUCUNE courbe (`undefined`, clé omise) — jamais 24 zéros
 * lus comme une valeur saisie ; seul un document RELU qui portait déjà sa courbe nulle la réémet telle quelle
 * (rouvrir puis enregistrer sans geste ne change aucun octet).
 */
function courbeDeBase(ctx: Ctx, appareils: Appliance[], consHandEdited: boolean): number[] | undefined {
  const ecran = Array.isArray(ctx.consCurve) && ctx.consCurve.length === 24 ? ctx.consCurve : null;
  if (ecran && (consHandEdited || ecran.some((v) => v > 0))) return ecran.slice();
  const socle = typeof ctx.consDailyTarget === 'number' && ctx.consDailyTarget > 0 ? ctx.consDailyTarget : 0;
  const facture = socle > 0 ? 0 : factureCarteDe(0, ctx.opts?.factureMensuelleMad);
  const jour = socle > 0 ? socle : facture > 0 ? billToAnnualKwh(facture) / 365 : 0;
  if (jour > 0) return composeConsumption(baselineCurve(jour), appareils);
  const relue = (ctx.documentRelu?.consumption as { courbe24?: unknown } | undefined)?.courbe24;
  // Seul un document relu qui portait DÉJÀ 24 zéros les réémet (aucun octet ne bouge sans geste) ; une courbe
  // réelle relue puis tombée à zéro par un geste n'écrit pas de zéros fantômes.
  const zerosStockes = Array.isArray(relue) && relue.length === 24 && relue.every((v) => v === 0);
  return zerosStockes ? emptyCurve() : undefined;
}

/** T4-U4-025 — la signature d'une consommation non relue, prise UNE fois par session : deux sérialisations sans geste
 *  rendent le même document (avant, `new Date()` à chaque lecture : le sondage du brouillon voyait « un changement »
 *  toutes les 4 s et envoyait un PUT, et la barre restait « Modifications non enregistrées » après l'enregistrement). */
function signatureSession(ctx: Ctx): string {
  if (typeof ctx.consSignatureSession !== 'string') ctx.consSignatureSession = new Date().toISOString();
  return ctx.consSignatureSession;
}

/** Le bloc `consumption` d'un `Ctx` « touché » (l'appelant a déjà écarté le cas vierge). */
export function construireConsommation(
  ctx: Ctx,
  appareilsSrc: Appliance[],
  consHandEdited: boolean,
  consSeasonal: boolean,
): SerializedConsumption {
  const courbe24 = courbeDeBase(ctx, appareilsSrc, consHandEdited);
  const methode: 'facture' | 'courbe' | 'appareils' = consHandEdited
    ? 'courbe'
    : appareilsSrc.length > 0
      ? 'appareils'
      : 'facture';
  const consumption: SerializedConsumption = {
    ...(courbe24 ? { courbe24 } : {}),
    methode,
    // ACAL26 — la provenance RELUE du document (`ctx.consSource`, posée par
    // `appliquerHydratationAuCtx`) voyage telle quelle : rouvrir puis enregistrer sans
    // geste ne réhorodate jamais la saisie. Sans provenance relue (saisie de cette
    // session), l'atelier signe le bloc.
    source:
      ctx.consSource && typeof ctx.consSource.origine === 'string' && typeof ctx.consSource.saisi_le === 'string'
        ? { origine: ctx.consSource.origine, saisi_le: ctx.consSource.saisi_le,
            ...(typeof ctx.consSource.bareme === 'string' ? { bareme: ctx.consSource.bareme } : {}) } // ACAL311
        : { origine: 'atelier', saisi_le: signatureSession(ctx) },
  };

  const summerFactor =
    typeof ctx.consSummerFactor === 'number' && Number.isFinite(ctx.consSummerFactor) ? ctx.consSummerFactor : null;
  const winterFactor =
    typeof ctx.consWinterFactor === 'number' && Number.isFinite(ctx.consWinterFactor) ? ctx.consWinterFactor : null;
  if (consSeasonal && summerFactor != null && winterFactor != null) {
    consumption.saisons = { ete: summerFactor, hiver: winterFactor };
  }

  // ACAL31 — une liste d'appareils VIDE relue du document repart vide (jamais retirée).
  const appareilsRelus = (ctx.documentRelu?.consumption as { appareils?: unknown } | undefined)?.appareils;
  if (appareilsSrc.length === 0 && ctx.consSource != null && Array.isArray(appareilsRelus) && appareilsRelus.length === 0) {
    consumption.appareils = [];
  }
  if (appareilsSrc.length > 0) {
    consumption.appareils = appareilsSrc.map((a) => ({
      kind: a.kind,
      label: a.label,
      dailyKwh: a.dailyKwh,
      startHour: a.startHour,
      endHour: a.endHour,
      billing: a.billing,
    }));
  }
  const charges = chargesAEcrire(ctx); // ACAL780
  if (charges) consumption.charges = charges;
  const factures = facturesAEcrire(ctx); // ACAL1610 — la grille « Mes factures », relue au rechargement
  if (factures) consumption.factures_mois = factures;
  return consumption;
}
