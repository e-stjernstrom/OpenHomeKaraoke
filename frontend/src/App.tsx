import { useState } from 'react';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import Box from '@mui/material/Box';
import Container from '@mui/material/Container';
import Paper from '@mui/material/Paper';
import BottomNavigation from '@mui/material/BottomNavigation';
import BottomNavigationAction from '@mui/material/BottomNavigationAction';
import Badge from '@mui/material/Badge';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import Tooltip from '@mui/material/Tooltip';
import Alert from '@mui/material/Alert';
import Avatar from '@mui/material/Avatar';
import { useColorScheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import HomeRounded from '@mui/icons-material/HomeRounded';
import QueueMusicRounded from '@mui/icons-material/QueueMusicRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import LibraryMusicRounded from '@mui/icons-material/LibraryMusicRounded';
import SettingsRounded from '@mui/icons-material/SettingsRounded';
import AccountCircleRounded from '@mui/icons-material/AccountCircleRounded';
import LanguageRounded from '@mui/icons-material/LanguageRounded';
import DarkModeRounded from '@mui/icons-material/DarkModeRounded';
import LightModeRounded from '@mui/icons-material/LightModeRounded';
import BrightnessAutoRounded from '@mui/icons-material/BrightnessAutoRounded';
import EditRounded from '@mui/icons-material/EditRounded';
import CheckRounded from '@mui/icons-material/CheckRounded';
import { useApp, type Page } from './state';
import { S } from './strings';
import Snackbars from './components/Snackbars';
import { LanguageDialog, NameDialog } from './components/Dialogs';
import HomePage from './pages/Home';
import QueuePage from './pages/Queue';
import SearchPage from './pages/Search';
import LibraryPage from './pages/Library';
import SettingsPage from './pages/Settings';

const NAV: { page: Page; icon: React.ReactElement }[] = [
  { page: 'home', icon: <HomeRounded /> },
  { page: 'queue', icon: <QueueMusicRounded /> },
  { page: 'search', icon: <SearchRounded /> },
  { page: 'library', icon: <LibraryMusicRounded /> },
];

export default function App() {
  const { t, page, go, queue, user, needsName, connected } = useApp();
  const wide = useMediaQuery((th) => th.breakpoints.up('md'));
  const { mode, setMode } = useColorScheme();
  const [menuEl, setMenuEl] = useState<HTMLElement | null>(null);
  const [nameOpen, setNameOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);

  const label = (p: Page) =>
    ({ home: t(S.home), queue: t(S.queue), search: t(S.search), library: t(S.library), settings: t(S.settings) })[p];

  const navValue = NAV.some((n) => n.page === page) ? page : false;
  const queueIcon = (icon: React.ReactElement) => (
    <Badge badgeContent={queue.length} color="secondary" max={99}>
      {icon}
    </Badge>
  );

  return (
    <Box sx={{ minHeight: '100vh', bgcolor: 'background.default' }}>
      <AppBar position="sticky">
        <Toolbar sx={{ gap: 1 }}>
          <Box
            component="img"
            src="/static/app/icon.svg"
            alt=""
            sx={{ width: 32, height: 32, flexShrink: 0, cursor: 'pointer' }}
            onClick={() => go('home')}
          />
          {wide ? (
            <>
              <Typography variant="h6" component="div" sx={{ mr: 2, whiteSpace: 'nowrap' }}>
                {t(S.appName)}
              </Typography>
              <Tabs
                value={navValue}
                onChange={(_, v) => go(v)}
                textColor="inherit"
                indicatorColor="secondary"
                sx={{ flex: 1, minWidth: 0 }}
                variant="scrollable"
                scrollButtons={false}
              >
                {NAV.map((n) => (
                  <Tab
                    key={n.page}
                    value={n.page}
                    label={label(n.page)}
                    icon={n.page === 'queue' ? queueIcon(n.icon) : n.icon}
                    iconPosition="start"
                    sx={{ minHeight: 64 }}
                  />
                ))}
              </Tabs>
            </>
          ) : (
            <Typography variant="h6" component="h1" noWrap sx={{ flex: 1 }}>
              {label(page)}
            </Typography>
          )}
          <Tooltip title={t(S.settings)}>
            <IconButton color="inherit" aria-label={t(S.settings)} onClick={() => go('settings')}>
              <SettingsRounded />
            </IconButton>
          </Tooltip>
          <Tooltip title={user || t(S.yourName)}>
            <IconButton
              color="inherit"
              edge="end"
              aria-label={t(S.yourName)}
              aria-haspopup="menu"
              onClick={(e) => setMenuEl(e.currentTarget)}
            >
              {user ? (
                <Avatar sx={{ width: 30, height: 30, fontSize: 15, bgcolor: 'secondary.main', color: 'secondary.contrastText' }}>
                  {[...user.trim()][0]?.toUpperCase()}
                </Avatar>
              ) : (
                <AccountCircleRounded />
              )}
            </IconButton>
          </Tooltip>
        </Toolbar>
      </AppBar>

      <Menu
        anchorEl={menuEl}
        open={!!menuEl}
        onClose={() => setMenuEl(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <MenuItem
          onClick={() => {
            setMenuEl(null);
            setNameOpen(true);
          }}
        >
          <ListItemIcon>
            <EditRounded fontSize="small" />
          </ListItemIcon>
          <ListItemText primary={user || '—'} secondary={t(S.yourName)} />
        </MenuItem>
        <MenuItem
          onClick={() => {
            setMenuEl(null);
            setLangOpen(true);
          }}
        >
          <ListItemIcon>
            <LanguageRounded fontSize="small" />
          </ListItemIcon>
          <ListItemText primary={t(S.changeLanguage)} />
        </MenuItem>
        <Divider />
        <Typography variant="overline" sx={{ px: 2, color: 'text.secondary' }}>
          {t(S.theme)}
        </Typography>
        {(
          [
            ['dark', <DarkModeRounded fontSize="small" />, t(S.themeDark)],
            ['light', <LightModeRounded fontSize="small" />, t(S.themeLight)],
            ['system', <BrightnessAutoRounded fontSize="small" />, t(S.themeSystem)],
          ] as const
        ).map(([m, icon, text]) => (
          <MenuItem key={m} selected={mode === m} onClick={() => setMode(m)}>
            <ListItemIcon>{icon}</ListItemIcon>
            <ListItemText primary={text} />
            {mode === m && <CheckRounded fontSize="small" sx={{ ml: 2 }} />}
          </MenuItem>
        ))}
      </Menu>

      {!connected && (
        <Alert severity="warning" variant="filled" sx={{ borderRadius: 0 }}>
          {t(S.reconnecting)}
        </Alert>
      )}

      <Container component="main" maxWidth="md" sx={{ pt: 2, pb: wide ? 4 : 'calc(80px + env(safe-area-inset-bottom))', px: { xs: 1.5, sm: 2 } }}>
        {page === 'home' && <HomePage />}
        {page === 'queue' && <QueuePage />}
        {page === 'search' && <SearchPage />}
        {page === 'library' && <LibraryPage />}
        {page === 'settings' && <SettingsPage />}
      </Container>

      {!wide && (
        <Paper
          elevation={8}
          sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: (th) => th.zIndex.appBar, pb: 'env(safe-area-inset-bottom)' }}
        >
          <BottomNavigation showLabels value={navValue} onChange={(_, v) => go(v)} component="nav">
            {NAV.map((n) => (
              <BottomNavigationAction
                key={n.page}
                value={n.page}
                label={label(n.page)}
                icon={n.page === 'queue' ? queueIcon(n.icon) : n.icon}
              />
            ))}
          </BottomNavigation>
        </Paper>
      )}

      <Snackbars bottomOffset={wide ? 0 : 64} />
      <NameDialog open={needsName || nameOpen} onClose={() => setNameOpen(false)} required={needsName} />
      <LanguageDialog open={langOpen} onClose={() => setLangOpen(false)} />
    </Box>
  );
}
