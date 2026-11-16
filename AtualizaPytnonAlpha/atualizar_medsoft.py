#!/usr/bin/env python3
"""Copia/atualiza os fontes do GitHub no Alpha. Python 3.12+, Git, Linux.

Não instala dependências, não reinicia serviços e não acessa o banco.
Cada atualização cria uma pasta; os atalhos atual/anterior permitem retorno.
"""
import argparse
import ast
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

DEFAULT_REPO = 'https://github.com/Joaquimtnetto/AppMedsoft.git'
DEFAULT_ROOT = Path.home() / 'medsoft_backup'


def git(*args):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    result = subprocess.run(['git', *map(str, args)], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        raise RuntimeError('Falha no Git: ' + result.stderr.strip())
    return result.stdout.strip()


def manifest(folder):
    return json.loads((folder / '.origem_medsoft.json').read_text(encoding='utf-8'))


def tracked_files(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file() and not p.is_symlink()
            and p.name != '.origem_medsoft.json'
            and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def selected(root, name):
    link = root / name
    if not link.exists() and not link.is_symlink():
        return None
    if not link.is_symlink():
        raise RuntimeError(str(link) + ' já existe e não é um atalho do atualizador.')
    folder = link.resolve(strict=True)
    if folder.parent != (root / 'versoes').resolve():
        raise RuntimeError('Atalho aponta para fora da pasta de versões: ' + str(link))
    return folder


def point(root, name, folder):
    link = root / name
    if link.exists() and not link.is_symlink():
        raise RuntimeError('Não é seguro substituir ' + str(link))
    temporary = root / ('.' + name + '-' + str(os.getpid()))
    try:
        temporary.symlink_to(folder, target_is_directory=True)
        os.replace(temporary, link)
    finally:
        if temporary.is_symlink():
            temporary.unlink()


def ensure_unchanged(folder):
    if folder and tracked_files(folder) != manifest(folder)['arquivos']:
        raise RuntimeError('Existem arquivos alterados ou novos na versão atual. '
                           'Nenhum arquivo será substituído. Guarde as alterações antes de atualizar.')


def history(root, action, folder):
    entry = {'data_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'acao': action, 'commit': manifest(folder)['commit'], 'pasta': str(folder)}
    with (root / 'historico.jsonl').open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')


def prune_versions(root):
    """Remove somente snapshots gerenciados e intactos fora dos dois atalhos."""
    versions = root / 'versoes'
    if versions.is_symlink():
        raise RuntimeError('A pasta de versões não pode ser um atalho.')
    base = versions.resolve()
    if base.parent != root.resolve():
        raise RuntimeError('Pasta de versões fora do destino permitido.')
    keep = {selected(root, name) for name in ('atual', 'anterior')}
    if not versions.exists():
        return
    for candidate in versions.iterdir():
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        resolved = candidate.resolve(strict=True)
        if resolved in keep or resolved.parent != base:
            continue
        if not (resolved / '.origem_medsoft.json').is_file():
            continue
        ensure_unchanged(resolved)
        shutil.rmtree(resolved)
        print('Versão antiga removida: ' + candidate.name)


def update(root, repo, branch):
    if (root / 'versoes').is_symlink():
        raise RuntimeError('A pasta de versões não pode ser um atalho.')
    current = selected(root, 'atual')
    selected(root, 'anterior')  # Validate existing links before changing anything.
    ensure_unchanged(current)
    cache = root / 'repositorio.git'
    if not cache.exists():
        git('init', '--bare', cache)
        git('--git-dir', cache, 'remote', 'add', 'origin', repo)
    elif git('--git-dir', cache, 'remote', 'get-url', 'origin') != repo:
        raise RuntimeError('O repositório configurado nesta pasta é diferente do solicitado.')
    git('check-ref-format', '--branch', branch)
    print('Consultando o GitHub...', flush=True)
    git('--git-dir', cache, 'fetch', '--prune', 'origin',
        '+refs/heads/' + branch + ':refs/remotes/origin/' + branch)
    revision = git('--git-dir', cache, 'rev-parse', 'refs/remotes/origin/' + branch)
    if current and manifest(current)['commit'] == revision:
        prune_versions(root)
        print('Os fontes já estão atualizados: ' + revision[:12])
        return
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
    versions = root / 'versoes'
    versions.mkdir(exist_ok=True)
    folder = versions / (stamp + '_' + revision[:12])
    folder.mkdir()
    with tempfile.TemporaryDirectory(prefix='medsoft-') as temp:
        archive = Path(temp) / 'fontes.tar'
        git('--git-dir', cache, 'archive', '--format=tar', '--output', archive, revision)
        with tarfile.open(archive) as source:
            # Source snapshots must not create links outside their version folder.
            if any(not (member.isfile() or member.isdir()) for member in source.getmembers()):
                raise RuntimeError('O repositório contém links ou arquivos especiais; revisão necessária.')
            source.extractall(folder, filter='data')
    # Check syntax without importing the application or contacting its database.
    for source in (folder / 'backend').glob('*.py'):
        ast.parse(source.read_text(encoding='utf-8-sig'), filename=str(source))
    meta = {'repositorio': repo, 'branch': branch, 'commit': revision,
            'arquivos': tracked_files(folder)}
    (folder / '.origem_medsoft.json').write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    if current:
        point(root, 'anterior', current)
    point(root, 'atual', folder)
    history(root, 'atualizar', folder)
    prune_versions(root)
    print('Fontes copiados e conferidos: ' + revision[:12])
    print('Pasta de acesso: ' + str(root / 'atual'))
    print('Nenhuma dependência, serviço ou banco de dados foi alterado.')


def rollback(root):
    current, previous = selected(root, 'atual'), selected(root, 'anterior')
    if not previous:
        raise RuntimeError('Ainda não existe uma versão anterior para retornar.')
    ensure_unchanged(current)
    ensure_unchanged(previous)
    point(root, 'atual', previous)
    if current:
        point(root, 'anterior', current)
    history(root, 'voltar', previous)
    print('Atalho atual retornou para o commit ' + manifest(previous)['commit'][:12])
    print('Nenhum serviço foi reiniciado.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao', nargs='?', default='atualizar', choices=['atualizar', 'status', 'voltar'])
    parser.add_argument('--pasta', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--repositorio', default=DEFAULT_REPO)
    parser.add_argument('--branch', default='main')
    args = parser.parse_args()
    root = args.pasta.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.atualizacao.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Já existe uma atualização em andamento.')
        if args.acao == 'status':
            for name in ('atual', 'anterior'):
                folder = selected(root, name)
                print(name + ': ' + (manifest(folder)['commit'] + ' — ' + str(folder) if folder else 'não disponível'))
        elif args.acao == 'voltar':
            rollback(root)
        else:
            update(root, args.repositorio, args.branch)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, tarfile.TarError, SyntaxError) as error:
        print('ERRO: ' + str(error), file=sys.stderr)
        sys.exit(1)
