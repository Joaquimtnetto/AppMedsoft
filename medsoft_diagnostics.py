import datetime
import os
import traceback


LOG_PATH = r'C:\Medsoft\python\pMobile\medsoft_diagnostico.log'
MAX_LOG_BYTES = 5 * 1024 * 1024


def _rotate_if_needed():
    try:
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) >= MAX_LOG_BYTES:
            backup_path = LOG_PATH + '.1'
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.replace(LOG_PATH, backup_path)
    except Exception:
        pass


def log_event(category, message, **details):
    try:
        _rotate_if_needed()
        timestamp = datetime.datetime.now().isoformat(timespec='seconds')
        fields = ' '.join(
            '{}={}'.format(key, repr(value))
            for key, value in details.items()
            if value not in (None, '')
        )
        line = '[{}] {} {}'.format(timestamp, category, message)
        if fields:
            line += ' ' + fields
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            handle.write(line + '\n')
    except Exception:
        pass


def log_exception(category, message, exc=None, **details):
    try:
        _rotate_if_needed()
        timestamp = datetime.datetime.now().isoformat(timespec='seconds')
        fields = ' '.join(
            '{}={}'.format(key, repr(value))
            for key, value in details.items()
            if value not in (None, '')
        )
        with open(LOG_PATH, 'a', encoding='utf-8') as handle:
            line = '[{}] {} {}'.format(timestamp, category, message)
            if fields:
                line += ' ' + fields
            handle.write(line + '\n')
            if exc is not None:
                handle.write(''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
                handle.write('---\n')
    except Exception:
        pass
