import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { CacheProvider } from '@emotion/react';
import createCache from '@emotion/cache';
import { prefixer } from 'stylis';
import rtlPlugin from 'stylis-plugin-rtl';
import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import '@fontsource/roboto/latin-400.css';
import '@fontsource/roboto/latin-500.css';
import '@fontsource/roboto/latin-700.css';
import { getJson, type Config } from './api';
import { makeTheme } from './theme';
import { AppProvider } from './state';
import App from './App';
import { ConfirmProvider } from './components/Dialogs';

async function start() {
  const root = createRoot(document.getElementById('root')!);
  let config: Config;
  try {
    config = await getJson<Config>('/api/config');
  } catch {
    root.render(
      <p style={{ font: '16px system-ui', padding: 24, color: '#ccc', background: '#121212', minHeight: '100vh', margin: 0 }}>
        OpenHomeKaraoke is not reachable. Check that it is running, then reload this page.
      </p>,
    );
    return;
  }
  document.documentElement.lang = config.lang.replace('_', '-');
  document.documentElement.dir = config.dir;
  const cache = createCache({
    key: config.dir === 'rtl' ? 'muirtl' : 'mui',
    stylisPlugins: config.dir === 'rtl' ? [prefixer, rtlPlugin] : [prefixer],
  });
  root.render(
    <StrictMode>
      <CacheProvider value={cache}>
        <ThemeProvider theme={makeTheme(config.dir)} defaultMode="dark">
          <CssBaseline enableColorScheme />
          <AppProvider initialConfig={config}>
            <ConfirmProvider>
              <App />
            </ConfirmProvider>
          </AppProvider>
        </ThemeProvider>
      </CacheProvider>
    </StrictMode>,
  );
}

start();
