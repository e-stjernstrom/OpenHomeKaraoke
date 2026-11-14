// Material Design 2 theme for OpenHomeKaraoke.
// Colours come from the UI review (handover ui-review/md2-palette.json):
//   primary   "karaoke navy"  #375a7f (the old navbar), tones 200 / 900
//   secondary teal            #1abc9c (the old links), tones 200 / 800
//   highlight amber           #f1b70e (the old song titles), used for song titles only
// Dark is the default: the app is used in a dim room next to a TV.
import { createTheme, type Direction } from '@mui/material/styles';

declare module '@mui/material/styles' {
  interface Palette {
    highlight: Palette['primary'];
  }
  interface PaletteOptions {
    highlight?: PaletteOptions['primary'];
  }
}

const fontFamily = [
  'Roboto',
  '"Noto Sans"',
  '"Noto Sans CJK SC"',
  '"Noto Sans CJK TC"',
  '"PingFang SC"',
  '"PingFang TC"',
  '"Microsoft YaHei"',
  '"Microsoft JhengHei"',
  'system-ui',
  'sans-serif',
].join(',');

export function makeTheme(direction: Direction) {
  return createTheme({
    direction,
    cssVariables: { colorSchemeSelector: 'data' },
    colorSchemes: {
      light: {
        palette: {
          primary: { main: '#375a7f', dark: '#2b4663', light: '#7d94ac', contrastText: '#ffffff' },
          secondary: { main: '#1abc9c', dark: '#117c67', light: '#6ad3bf', contrastText: '#000000' },
          error: { main: '#b00020' },
          highlight: { main: '#7d5f07', light: '#9f7909', dark: '#5e4705', contrastText: '#ffffff' },
          background: { default: '#f5f5f5', paper: '#ffffff' },
        },
      },
      dark: {
        palette: {
          primary: { main: '#a5b5c5', dark: '#7d94ac', light: '#cdd6df', contrastText: '#000000' },
          secondary: { main: '#98e1d2', dark: '#6ad3bf', light: '#c6eee6', contrastText: '#000000' },
          error: { main: '#cf6679', contrastText: '#000000' },
          highlight: { main: '#f6d062', light: '#f9df93', dark: '#f3c337', contrastText: '#000000' },
          background: { default: '#121212', paper: '#121212' },
        },
      },
    },
    typography: {
      fontFamily,
      button: { fontWeight: 500, letterSpacing: '0.0892em' },
      overline: { letterSpacing: '0.1em', lineHeight: 1.6 },
    },
    shape: { borderRadius: 4 },
    components: {
      MuiAppBar: {
        defaultProps: { elevation: 4, color: 'primary', enableColorOnDark: false },
      },
      MuiButton: { defaultProps: { disableElevation: false } },
      MuiCard: { defaultProps: { elevation: 1 } },
      MuiListItemButton: { styleOverrides: { root: { minHeight: 56 } } },
      MuiBottomNavigationAction: {
        styleOverrides: { root: { minWidth: 64, paddingLeft: 4, paddingRight: 4 } },
      },
      MuiSlider: { defaultProps: { color: 'secondary' } },
      MuiSwitch: { defaultProps: { color: 'secondary' } },
      MuiTooltip: { defaultProps: { enterTouchDelay: 300 } },
    },
  });
}
