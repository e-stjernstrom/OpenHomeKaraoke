#!/usr/bin/env python3
"""Install the bgutil PO token provider for YouTube downloads (optional).

YouTube asks downloaders for a "proof of origin" (PO) token. bgutil makes these tokens the way a
browser does, so downloads are refused less often, without signing in to YouTube. It has two parts:
- the yt-dlp plugin (pip package bgutil-ytdlp-pot-provider, in requirements.txt)
- a small Node.js server that makes the tokens. This script fetches and builds it in
  third_party/bgutil; OpenHomeKaraoke starts it by itself (127.0.0.1:4416) when it finds it.

Needs git and Node.js 22 or newer. Run it again to update after VERSION changes:
    python scripts/setup_bgutil.py
"""
import os, shutil, subprocess, sys

VERSION = '2.0.2'  # keep equal to bgutil-ytdlp-pot-provider in requirements.txt
REPO = 'https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, 'third_party', 'bgutil')
SERVER = os.path.join(DEST, 'server')


def run(cmd, cwd=None):
	print('+', ' '.join(cmd), flush=True)
	subprocess.run(cmd, cwd=cwd, check=True, shell=sys.platform == 'win32')


def need(tool, hint):
	if not shutil.which(tool):
		sys.exit(f'{tool} not found. {hint}')


def main():
	need('git', 'Install git first.')
	need('node', 'Install Node.js 22 or newer first (https://nodejs.org).')
	need('npm', 'Install Node.js 22 or newer first (https://nodejs.org).')
	major = int(subprocess.run(['node', '-v'], capture_output=True, text=True).stdout.strip().lstrip('v').split('.')[0])
	if major < 22:
		sys.exit(f'bgutil needs Node.js 22 or newer, this is Node.js {major}.')

	if os.path.isdir(os.path.join(DEST, '.git')):
		run(['git', 'fetch', '--depth', '1', 'origin', 'tag', VERSION], cwd=DEST)
		run(['git', 'checkout', '-q', VERSION], cwd=DEST)
	else:
		os.makedirs(os.path.dirname(DEST), exist_ok=True)
		run(['git', '-c', 'advice.detachedHead=false', 'clone', '-q', '--depth', '1', '--branch', VERSION, REPO, DEST])
	run(['npm', 'ci', '--no-audit', '--no-fund'], cwd=SERVER)
	run(['npx', 'tsc'], cwd=SERVER)
	run([sys.executable, '-m', 'pip', 'install', f'bgutil-ytdlp-pot-provider=={VERSION}'])
	print(f'\nbgutil {VERSION} is ready in {DEST}. OpenHomeKaraoke starts it by itself (turn off with --no-pot).')


if __name__ == '__main__':
	main()
