<script setup lang="ts">
import type { RankingEntry, SummaryResponse } from '~/types/api'

const { get, errorMessage } = useApi()
const selectedDate = ref(localDate())
const summary = ref<SummaryResponse | null>(null)
const loading = ref(false)
const error = ref('')

function localDate() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const currency = (value: number) =>
  new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(value)

async function load() {
  loading.value = true
  error.value = ''
  try {
    summary.value = await get<SummaryResponse>('/api/summary', { date: selectedDate.value })
  } catch (requestError) {
    error.value = errorMessage(requestError)
  } finally {
    loading.value = false
  }
}

watch(selectedDate, load)
onMounted(load)
</script>

<template>
  <section class="space-y-5">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-2xl font-semibold text-highlighted">数据汇总</h2>
        <p class="mt-1 text-sm text-muted">查看指定日期的 SC 表现</p>
      </div>
      <div class="flex items-end gap-2">
        <UFormField label="统计日期">
          <UInput v-model="selectedDate" type="date" icon="i-lucide-calendar" />
        </UFormField>
        <UButton
          label="刷新"
          icon="i-lucide-refresh-cw"
          variant="soft"
          :loading="loading"
          @click="load"
        />
      </div>
    </div>

    <UAlert v-if="error" color="error" icon="i-lucide-circle-alert" :description="error" />

    <div class="grid gap-4 sm:grid-cols-2">
      <UCard>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted">SC 总数</p>
            <p class="mt-2 text-3xl font-semibold tabular-nums text-highlighted">
              {{ summary?.totalCount ?? 0 }}
            </p>
          </div>
          <div class="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <UIcon name="i-lucide-message-square-more" class="size-6" />
          </div>
        </div>
      </UCard>
      <UCard>
        <div class="flex items-center justify-between">
          <div>
            <p class="text-sm text-muted">金额总数</p>
            <p class="mt-2 text-3xl font-semibold tabular-nums text-highlighted">
              {{ currency(summary?.totalAmount ?? 0) }}
            </p>
          </div>
          <div class="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <UIcon name="i-lucide-circle-dollar-sign" class="size-6" />
          </div>
        </div>
      </UCard>
    </div>

    <UCard>
      <template #header>
        <div>
          <h3 class="font-semibold text-highlighted">金额分布</h3>
          <p class="text-sm text-muted">按实际 SC 金额统计数量和占比</p>
        </div>
      </template>
      <div v-if="summary?.amountDistribution.length" class="space-y-4">
        <div
          v-for="entry in summary.amountDistribution"
          :key="entry.amount"
          class="grid grid-cols-[5rem_1fr_auto] items-center gap-3"
        >
          <span class="font-medium tabular-nums text-highlighted">{{ currency(entry.amount) }}</span>
          <div class="h-3 overflow-hidden rounded-full bg-elevated">
            <div
              class="h-full min-w-1 rounded-full bg-primary transition-[width]"
              :style="{ width: `${entry.percentage}%` }"
            />
          </div>
          <span class="min-w-28 text-right text-sm tabular-nums text-muted">
            {{ entry.count }} 条 · {{ entry.percentage.toFixed(1) }}%
          </span>
        </div>
      </div>
      <div v-else class="py-8 text-center text-sm text-muted">该日期暂无 SC 数据</div>
    </UCard>

    <div class="grid gap-4 xl:grid-cols-2">
      <RankingCard
        title="SC 总数排行榜"
        icon="i-lucide-list-ordered"
        :entries="summary?.countRanking ?? []"
        value-label="SC 数量"
        :value="(entry: RankingEntry) => `${entry.count} 条`"
      />
      <RankingCard
        title="SC 金额排行榜"
        icon="i-lucide-trophy"
        :entries="summary?.amountRanking ?? []"
        value-label="累计金额"
        :value="(entry: RankingEntry) => currency(entry.totalAmount)"
      />
    </div>
  </section>
</template>
