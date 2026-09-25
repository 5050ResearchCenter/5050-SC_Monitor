export default defineNuxtConfig({
  compatibilityDate: '2026-09-14',
  devtools: { enabled: false },
  modules: ['@nuxt/ui'],
  ui: { fonts: false },
  css: ['~/assets/css/main.css'],
  ssr: false,
  app: {
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      title: 'SC Monitor 数据中心',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'color-scheme', content: 'light dark' }
      ]
    }
  }
})
