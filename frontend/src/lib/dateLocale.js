// ADEV73 - date du jour LOCALE (Africa/Casablanca), jamais UTC.
//
// `new Date().toISOString().slice(0, 10)` rend la date UTC : entre minuit et 01 h
// (heure du Maroc) elle donne la VEILLE. Une date d'acceptation, de paiement ou de
// relance posee par defaut a « aujourd'hui » etait alors fausse d'un jour. Cette
// fonction est la forme unique ; la garde `scripts/check_date_jour_utc.py` interdit le
// motif UTC dans tout nouveau fichier.

const FUSEAU_MAROC = 'Africa/Casablanca'

/**
 * Date du jour `AAAA-MM-JJ` a Casablanca.
 * @param {Date} [maintenant] instant de reference (defaut : maintenant) - injectable en test.
 */
export function todayLocalIso(maintenant = new Date()) {
  const parties = new Intl.DateTimeFormat('en-CA', {
    timeZone: FUSEAU_MAROC, year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(maintenant)
  const get = (type) => parties.find((p) => p.type === type).value
  return `${get('year')}-${get('month')}-${get('day')}`
}
