export interface RankingEntry {
  userUid: number
  nickname: string
  count: number
  totalAmount: number
}

export interface AmountDistribution {
  amount: number
  count: number
  totalAmount: number
  percentage: number
}

export interface SummaryResponse {
  date: string
  totalCount: number
  totalAmount: number
  amountDistribution: AmountDistribution[]
  countRanking: RankingEntry[]
  amountRanking: RankingEntry[]
}

export interface UserSearchResult {
  userUid: number
  nickname: string
  aliases: string[]
  count: number
  totalAmount: number
  blacklistedCount: number
  amountDistribution: AmountDistribution[]
}

export interface SuperChat {
  id: number
  userUid: number
  nickname: string
  content: string
  amount: number
  sentAt: number
  bv: string | null
  videoTitle: string | null
  videoTags: string[]
  blacklisted: boolean
  blacklistMatches: string[]
}

export interface SuperChatPage {
  items: SuperChat[]
  total: number
  page: number
  pageSize: number
  pageCount: number
}
