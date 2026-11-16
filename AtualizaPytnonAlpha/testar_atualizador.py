"""Teste isolado em Linux; usa somente repositórios e pastas temporárias."""
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = Path(__file__).with_name('atualizar_medsoft.py')


def run(*args, ok=True):
    result = subprocess.run(list(map(str, args)), text=True, capture_output=True)
    if (result.returncode == 0) != ok:
        raise AssertionError(result.stdout + result.stderr)
    return result


with tempfile.TemporaryDirectory(prefix='teste-medsoft-') as temporary:
    root = Path(temporary)
    origin, target = root / 'origem', root / 'destino'
    run('git', 'init', '--initial-branch=main', origin)
    run('git', '-C', origin, 'config', 'user.email', 'teste@example.invalid')
    run('git', '-C', origin, 'config', 'user.name', 'Teste isolado')
    source = origin / 'backend' / 'exemplo.py'
    source.parent.mkdir()

    def commit(content):
        source.write_text(content, encoding='utf-8')
        run('git', '-C', origin, 'add', '.')
        run('git', '-C', origin, 'commit', '-m', 'Versao de teste')

    def update(action='atualizar', ok=True):
        return run(sys.executable, SCRIPT, action, '--pasta', target,
                   '--repositorio', origin, ok=ok)

    commit('valor = 1\n')
    update()
    first = (target / 'atual').resolve()
    update()
    assert (target / 'atual').resolve() == first
    commit('valor = 2\n')
    update()
    second = (target / 'atual').resolve()
    assert second != first
    assert (target / 'anterior').resolve() == first
    update('voltar')
    assert (target / 'atual').resolve() == first
    assert (target / 'anterior').resolve() == second
    commit('valor = 4\n')
    update()
    assert not second.exists()
    assert len(list((target / 'versoes').iterdir())) == 2
    update('voltar')
    assert (target / 'atual').resolve() == first
    current_source = target / 'atual' / 'backend' / 'exemplo.py'
    current_source.write_text('valor = 3\n', encoding='utf-8')
    assert 'alterados' in update(ok=False).stderr
    assert (target / 'atual').resolve() == first
    current_source.write_text('valor = 1\n', encoding='utf-8')
    commit('def erro(\n')
    update(ok=False)
    assert (target / 'atual').resolve() == first
    update('status')
    print('OK: copia, repeticao, atualizacao, retorno e protecoes contra alteracoes e sintaxe invalida.')
