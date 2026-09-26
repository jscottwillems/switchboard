const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatTimestamp(iso: string): string {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const day = String(date.getUTCDate()).padStart(2, '0')
  const hours = String(date.getUTCHours()).padStart(2, '0')
  const minutes = String(date.getUTCMinutes()).padStart(2, '0')
  const month = MONTHS[date.getUTCMonth()] ?? ''
  return `${day} ${month} ${date.getUTCFullYear()} ${hours}:${minutes} UTC`
}

export function formatDay(day: string): string {
  const date = new Date(`${day}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return day
  const month = MONTHS[date.getUTCMonth()] ?? ''
  return `${String(date.getUTCDate()).padStart(2, '0')} ${month}`
}

export function formatDuration(ms: number | null): string {
  if (ms === null) return '—'
  const total = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const seconds = total % 60
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`
}

export function formatOffset(ms: number): string {
  return formatDuration(ms)
}

export function campaignCaption(id: string | null, label: string | null): string {
  if (label) return label
  if (id) return id
  return 'No campaign'
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function formatUsd(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount)
}

export function formatClock(nowMs: number): string {
  const date = new Date(nowMs)
  const hours = String(date.getUTCHours()).padStart(2, '0')
  const minutes = String(date.getUTCMinutes()).padStart(2, '0')
  const seconds = String(date.getUTCSeconds()).padStart(2, '0')
  return `${hours}:${minutes}:${seconds} UTC`
}
