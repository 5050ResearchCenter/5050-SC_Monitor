<script setup lang="ts">
const tabs = [
  { label: '数据汇总', icon: 'i-lucide-chart-no-axes-combined', value: 'summary' },
  { label: 'SC 详情', icon: 'i-lucide-list', value: 'details' },
  { label: '年度汇总', icon: 'i-lucide-calendar-days', value: 'yearly' }
]

const activeTab = ref('summary')
</script>

<template>
  <UApp>
    <div class="min-h-screen">
      <header class="border-b border-default bg-default/85 backdrop-blur">
        <div class="mx-auto flex max-w-[1600px] items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div class="flex size-10 items-center justify-center rounded-xl bg-primary text-inverted shadow-sm">
            <UIcon name="i-lucide-radio-tower" class="size-5" />
          </div>
          <div>
            <h1 class="text-lg font-semibold text-highlighted">SC Monitor 数据中心</h1>
            <p class="text-xs text-muted">本机 SQLite 数据分析</p>
          </div>
        </div>
      </header>

      <main class="mx-auto max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8">
        <UTabs v-model="activeTab" :items="tabs" :content="false" class="mb-6 w-full" />

        <KeepAlive>
          <SummaryTab v-if="activeTab === 'summary'" />
          <DetailsTab v-else-if="activeTab === 'details'" />
          <ConstructionTab v-else />
        </KeepAlive>
      </main>
    </div>
  </UApp>
</template>
