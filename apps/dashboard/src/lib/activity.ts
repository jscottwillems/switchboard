import type { ActivityBucket } from '@/types/models'

export interface DayTotal {
  day: string
  count: number
}

export function rollupByDay(activity: ActivityBucket[]): DayTotal[] {
  const totals = new Map<string, number>()
  for (const bucket of activity) {
    totals.set(bucket.day, (totals.get(bucket.day) ?? 0) + bucket.count)
  }
  return [...totals.entries()]
    .sort((left, right) => left[0].localeCompare(right[0]))
    .map(([day, count]) => ({ day, count }))
}

export function activityDays(activity: ActivityBucket[]): string[] {
  return [...new Set(activity.map((bucket) => bucket.day))].sort((left, right) => right.localeCompare(left))
}

export function countFor(activity: ActivityBucket[], day: string, hour: number): number {
  const match = activity.find((bucket) => bucket.day === day && bucket.hour === hour)
  return match?.count ?? 0
}

export function maxActivityCount(activity: ActivityBucket[]): number {
  return activity.reduce((max, bucket) => Math.max(max, bucket.count), 0)
}
