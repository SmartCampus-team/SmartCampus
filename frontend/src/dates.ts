// Dates et créneaux du campus côté interface (SC-22, RG-03) :
// pas de 30 min, de 08:00 à 20:00, du lundi au samedi. L'API vérifie les mêmes règles.

export const OPENING = '08:00'
export const CLOSING = '20:00'
export const STEP_MINUTES = 30

export function toMinutes(time: string): number {
  const [hours, minutes] = time.split(':').map(Number)
  return hours * 60 + minutes
}

export function fromMinutes(total: number): string {
  const hours = Math.floor(total / 60)
  const minutes = total % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

/** « 10:00:00 » (format de l'API) → « 10:00 ». */
export function shortTime(time: string): string {
  return time.slice(0, 5)
}

/** Heures possibles de `from` à `to` inclus, par pas de 30 min. */
export function timeOptions(from = OPENING, to = CLOSING): string[] {
  const options: string[] = []
  for (let minutes = toMinutes(from); minutes <= toMinutes(to); minutes += STEP_MINUTES) {
    options.push(fromMinutes(minutes))
  }
  return options
}

/** Date locale au format AAAA-MM-JJ (sans passer par UTC, qui décalerait le jour). */
export function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${date.getFullYear()}-${month}-${day}`
}

export function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function isValidIsoDate(value: string | null): value is string {
  return !!value && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(parseIsoDate(value).getTime())
}

export function addDays(iso: string, days: number): string {
  const date = parseIsoDate(iso)
  date.setDate(date.getDate() + days)
  return isoDate(date)
}

/** Le campus ouvre du lundi au samedi : le dimanche (0) est fermé. */
export function isOpenDay(iso: string): boolean {
  return parseIsoDate(iso).getDay() !== 0
}

export function nextOpenDay(iso: string): string {
  return isOpenDay(iso) ? iso : addDays(iso, 1)
}

/** Lundi de la semaine qui contient ce jour. */
export function startOfWeek(iso: string): string {
  const weekday = (parseIsoDate(iso).getDay() + 6) % 7 // lundi = 0
  return addDays(iso, -weekday)
}

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1)
}

/** « Lundi 2 novembre 2026 » */
export function formatLongDate(iso: string): string {
  return capitalize(
    parseIsoDate(iso).toLocaleDateString('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }),
  )
}

/** « lun. 2 nov. » */
export function formatShortDay(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString('fr-FR', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

/** Premier créneau d'une heure proposé par défaut : à venir, dans les heures d'ouverture. */
export function defaultSlot(now = new Date()): { date: string; start: string; end: string } {
  const today = isoDate(now)
  const nowMinutes = now.getHours() * 60 + now.getMinutes()
  const nextStep = Math.ceil(nowMinutes / STEP_MINUTES) * STEP_MINUTES
  const start = Math.max(nextStep, toMinutes(OPENING))
  if (isOpenDay(today) && start + 60 <= toMinutes(CLOSING)) {
    return { date: today, start: fromMinutes(start), end: fromMinutes(start + 60) }
  }
  return { date: nextOpenDay(addDays(today, 1)), start: '10:00', end: '12:00' }
}
