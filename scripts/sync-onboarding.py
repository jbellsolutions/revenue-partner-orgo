#!/usr/bin/env python3
"""Release the canonical shared module; keep each target's role manifest intact."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'role.json', 'release.json'}


def files(root):
    return sorted(p for p in (root / 'onboarding').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc' and p.name not in EXCLUDED)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release(root):
    return {'version': '2026.09.13.1', 'source_repository': 'jbellsolutions/revenue-partner-orgo',
            'hermes_commit': '939e45c91d751fadd94dcd1b873ac3cb44846213',
            'files': {str(p.relative_to(root)): digest(p) for p in files(root)},
            'launcher_sha256': digest(root / 'orgo-onboard')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, action='append', default=[])
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    expected = release(ROOT)
    if args.check:
        recorded = json.loads((ROOT / 'onboarding/release.json').read_text())
        if recorded != expected:
            raise SystemExit('Shared release drift detected; regenerate from the canonical repository.')
        for target in args.target:
            if release(target.resolve()) != expected:
                raise SystemExit('A target differs from the shared release.')
        print('Shared onboarding release is consistent.')
        return
    if json.loads((ROOT / 'onboarding/role.json').read_text())['id'] != 'revenue-partner':
        raise SystemExit('Maintain shared releases in Revenue Partner Orgo.')
    for target in args.target:
        target = target.resolve()
        role = json.loads((target / 'onboarding/role.json').read_text())
        if role['id'] not in {'head-of-ops', 'ai-cofounder', 'operator', 'go-to-market'}:
            raise SystemExit('Target is outside the approved five roles.')
        for source in files(ROOT):
            dest = target / source.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        shutil.copy2(ROOT / 'orgo-onboard', target / 'orgo-onboard')
        for plugin in ('latitude-observer',):
            if (target / 'plugins' / plugin).is_dir():
                shutil.copytree(ROOT / 'onboarding/plugins' / plugin, target / 'plugins' / plugin, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (target / 'onboarding/release.json').write_text(json.dumps(expected, indent=2) + '\n')
        (target / 'scripts').mkdir(exist_ok=True)
        shutil.copy2(__file__, target / 'scripts/sync-onboarding.py')
    (ROOT / 'onboarding/release.json').write_text(json.dumps(expected, indent=2) + '\n')


if __name__ == '__main__':
    main()
