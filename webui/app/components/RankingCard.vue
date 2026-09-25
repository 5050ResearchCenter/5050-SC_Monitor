<script setup lang="ts">
import type { RankingEntry } from '~/types/api'

defineProps<{
  title: string
  icon: string
  entries: RankingEntry[]
  valueLabel: string
  value: (entry: RankingEntry) => string
}>()
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon :name="icon" class="size-5 text-primary" />
        <h3 class="font-semibold text-highlighted">{{ title }}</h3>
      </div>
    </template>
    <div v-if="entries.length" class="divide-y divide-default">
      <div
        v-for="(entry, index) in entries"
        :key="entry.userUid"
        class="grid grid-cols-[2rem_1fr_auto] items-center gap-3 py-3 first:pt-0 last:pb-0"
      >
        <span
          class="flex size-7 items-center justify-center rounded-lg text-sm font-semibold"
          :class="index < 3 ? 'bg-primary/10 text-primary' : 'text-muted'"
        >
          {{ index + 1 }}
        </span>
        <div class="min-w-0">
          <p class="truncate font-medium text-highlighted">{{ entry.nickname }}</p>
          <p class="text-xs text-muted">UID {{ entry.userUid }}</p>
        </div>
        <div class="text-right">
          <p class="font-semibold tabular-nums text-highlighted">{{ value(entry) }}</p>
          <p class="text-xs text-muted">{{ valueLabel }}</p>
        </div>
      </div>
    </div>
    <div v-else class="py-8 text-center text-sm text-muted">暂无排行数据</div>
  </UCard>
</template>
