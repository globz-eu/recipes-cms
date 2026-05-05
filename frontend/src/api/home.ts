import { apiFetch } from './client'

export interface HomePage {
  title: string
  description: string | null
}

export const homeQueryKey = ['home'] as const

export function fetchHome(): Promise<HomePage[]> {
  return apiFetch<HomePage[]>('/api/home/')
}
