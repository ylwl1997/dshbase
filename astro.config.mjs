// @ts-check
import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://dshbase.com',
  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'zh'],
    routing: {
      prefixDefaultLocale: false,
    },
  },
});
