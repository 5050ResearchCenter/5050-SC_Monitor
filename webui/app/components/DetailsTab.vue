<script setup lang="ts">
import type { SuperChatPage, UserSearchResult } from '~/types/api'

const { get, errorMessage } = useApi()
const data = ref<SuperChatPage>({ items: [], total: 0, page: 1, pageSize: 20, pageCount: 1 })
const page = ref(1)
const pageSize = ref(20)
const includeBlacklisted = ref(false)
const selectedUser = ref<UserSearchResult | null>(null)
const searchQuery = ref('')
const unmatchedQuery = ref(false)
const loading = ref(false)
const searching = ref(false)
const error = ref('')
const searchError = ref('')

const currency = (value: number) =>
  new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(value)

const sentAt = (timestamp: number) =>
  new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).format(new Date(timestamp * 1000))

async function load() {
  if (unmatchedQuery.value) {
    data.value = { items: [], total: 0, page: 1, pageSize: pageSize.value, pageCount: 1 }
    return
  }
  loading.value = true
  error.value = ''
  try {
    data.value = await get<SuperChatPage>('/api/super-chats', {
      page: page.value,
      pageSize: pageSize.value,
      userUid: selectedUser.value?.userUid,
      includeBlacklisted: includeBlacklisted.value ? 1 : 0
    })
  } catch (requestError) {
    error.value = errorMessage(requestError)
  } finally {
    loading.value = false
  }
}

async function searchUsers() {
  const query = searchQuery.value.trim()
  if (!query) {
    clearUser()
    return
  }
  searching.value = true
  searchError.value = ''
  try {
    const response = await get<{ items: UserSearchResult[] }>('/api/users', { q: query })
    const user = response.items[0]
    if (!user) {
      selectedUser.value = null
      unmatchedQuery.value = true
      data.value = { items: [], total: 0, page: 1, pageSize: pageSize.value, pageCount: 1 }
      searchError.value = '未找到匹配的投稿人，请检查昵称或 UID'
      return
    }
    unmatchedQuery.value = false
    selectedUser.value = user
    if (page.value === 1) await load()
    else page.value = 1
  } catch (requestError) {
    searchError.value = errorMessage(requestError)
  } finally {
    searching.value = false
  }
}

function clearUser() {
  selectedUser.value = null
  unmatchedQuery.value = false
  searchQuery.value = ''
  searchError.value = ''
  if (page.value === 1) load()
  else page.value = 1
}

watch([page, pageSize], load)
watch(includeBlacklisted, () => {
  if (page.value === 1) load()
  else page.value = 1
})
onMounted(load)
</script>

<template>
  <section class="space-y-5">
    <div class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 class="text-2xl font-semibold text-highlighted">SC 详情</h2>
        <p class="mt-1 text-sm text-muted">浏览全部记录，或按投稿人查看历史 SC</p>
      </div>
      <div class="flex items-center gap-4">
        <label class="flex cursor-pointer items-center gap-2 text-sm text-muted">
          <USwitch v-model="includeBlacklisted" color="error" />
          显示已屏蔽 SC
        </label>
        <UButton
          label="刷新"
          icon="i-lucide-refresh-cw"
          variant="soft"
          :loading="loading"
          @click="load"
        />
      </div>
    </div>

    <UCard>
      <div class="flex flex-wrap items-end gap-2">
        <UFormField label="投稿人昵称或 UID" class="min-w-64 flex-1">
          <UInput
            v-model="searchQuery"
            class="w-full"
            icon="i-lucide-search"
            placeholder="输入昵称关键词或完整 UID"
            @keyup.enter="searchUsers"
          />
        </UFormField>
        <UButton label="查询" :loading="searching" @click="searchUsers" />
        <UButton v-if="selectedUser" label="清除筛选" color="neutral" variant="soft" @click="clearUser" />
      </div>

      <UAlert
        v-if="searchError"
        class="mt-3"
        color="error"
        icon="i-lucide-circle-alert"
        :description="searchError"
      />

      <div v-if="selectedUser" class="mt-5 border-t border-default pt-4">
        <div class="flex flex-wrap items-center gap-2">
          <span class="font-semibold text-highlighted">{{ selectedUser.nickname }}</span>
          <UBadge color="primary" variant="soft">UID {{ selectedUser.userUid }}</UBadge>
          <span v-if="selectedUser.aliases.length > 1" class="text-xs text-muted">
            历史昵称：{{ selectedUser.aliases.join('、') }}
          </span>
        </div>

        <div class="mt-4 grid gap-3 sm:grid-cols-3">
          <div class="rounded-xl bg-elevated p-4">
            <p class="text-xs text-muted">历史 SC 总次数</p>
            <p class="mt-1 text-2xl font-semibold tabular-nums text-highlighted">
              {{ selectedUser.count }} <span class="text-sm font-normal text-muted">次</span>
            </p>
          </div>
          <div class="rounded-xl bg-elevated p-4">
            <p class="text-xs text-muted">历史总金额</p>
            <p class="mt-1 text-2xl font-semibold tabular-nums text-highlighted">
              {{ currency(selectedUser.totalAmount) }}
            </p>
          </div>
          <div class="rounded-xl border border-error/30 bg-error/10 p-4">
            <p class="text-xs font-medium text-error">已屏蔽 SC</p>
            <p class="mt-1 text-2xl font-semibold tabular-nums text-error">
              {{ selectedUser.blacklistedCount }} <span class="text-sm font-normal">次</span>
            </p>
          </div>
        </div>

        <div class="mt-3 rounded-xl bg-elevated p-4">
          <p class="text-xs text-muted">不同金额档位次数</p>
          <div class="mt-3 flex flex-wrap gap-2">
            <div
              v-for="entry in selectedUser.amountDistribution"
              :key="entry.amount"
              class="rounded-lg border border-default bg-default px-3 py-2"
            >
              <span class="font-semibold tabular-nums text-primary">{{ currency(entry.amount) }}</span>
              <span class="ml-2 text-sm tabular-nums text-toned">{{ entry.count }} 次</span>
            </div>
          </div>
        </div>
      </div>
    </UCard>

    <UAlert v-if="error" color="error" icon="i-lucide-circle-alert" :description="error" />

    <UCard :ui="{ body: 'p-0 sm:p-0' }">
      <div class="overflow-x-auto">
        <table class="w-full min-w-[1500px] text-left text-sm">
          <thead class="border-b border-default bg-elevated/60 text-xs text-muted">
            <tr>
              <th class="px-4 py-3 font-medium">ID</th>
              <th class="px-4 py-3 font-medium">发送时间</th>
              <th class="px-4 py-3 font-medium">UID</th>
              <th class="px-4 py-3 font-medium">昵称</th>
              <th class="px-4 py-3 font-medium">金额</th>
              <th class="px-4 py-3 font-medium">SC 内容</th>
              <th class="px-4 py-3 font-medium">BV</th>
              <th class="px-4 py-3 font-medium">视频标题</th>
              <th class="px-4 py-3 font-medium">视频标签</th>
              <th class="px-4 py-3 font-medium">黑名单</th>
              <th class="px-4 py-3 font-medium">命中关键词</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-default">
            <tr v-for="item in data.items" :key="item.id" class="align-top hover:bg-elevated/40">
              <td class="px-4 py-3 tabular-nums text-muted">{{ item.id }}</td>
              <td class="whitespace-nowrap px-4 py-3 text-toned">{{ sentAt(item.sentAt) }}</td>
              <td class="px-4 py-3 tabular-nums text-toned">{{ item.userUid }}</td>
              <td class="max-w-40 px-4 py-3 font-medium text-highlighted">{{ item.nickname }}</td>
              <td class="whitespace-nowrap px-4 py-3 font-semibold tabular-nums text-primary">
                {{ currency(item.amount) }}
              </td>
              <td class="max-w-96 whitespace-pre-wrap break-words px-4 py-3 text-toned">{{ item.content }}</td>
              <td class="whitespace-nowrap px-4 py-3 text-toned">{{ item.bv || '—' }}</td>
              <td class="max-w-72 whitespace-normal px-4 py-3 text-toned">{{ item.videoTitle || '—' }}</td>
              <td class="max-w-64 whitespace-normal px-4 py-3 text-toned">
                {{ item.videoTags.length ? item.videoTags.join('、') : '—' }}
              </td>
              <td class="px-4 py-3">
                <UBadge :color="item.blacklisted ? 'error' : 'neutral'" variant="soft">
                  {{ item.blacklisted ? '已屏蔽' : '否' }}
                </UBadge>
              </td>
              <td class="max-w-56 whitespace-normal px-4 py-3 text-toned">
                {{ item.blacklistMatches.length ? item.blacklistMatches.join('、') : '—' }}
              </td>
            </tr>
            <tr v-if="!loading && !data.items.length">
              <td colspan="11" class="px-4 py-12 text-center text-muted">暂无符合条件的 SC 数据</td>
            </tr>
          </tbody>
        </table>
      </div>
      <template #footer>
        <div class="flex flex-wrap items-center justify-between gap-3">
          <span class="text-sm text-muted">共 {{ data.total }} 条</span>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-sm text-muted">
              每页
              <select
                v-model.number="pageSize"
                class="rounded-md border border-default bg-default px-2 py-1.5 text-highlighted"
                @change="page = 1"
              >
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
            </label>
            <UPagination
              v-if="data.total"
              v-model:page="page"
              :items-per-page="pageSize"
              :total="data.total"
            />
          </div>
        </div>
      </template>
    </UCard>
  </section>
</template>
