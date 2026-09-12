import datetime
import json
import os
import threading

from flask import Blueprint, jsonify, request, session

from tenant_context import current_company_id


internal_chat_api_bp = Blueprint('internal_chat_api', __name__)

_messages_by_company = {}
_next_message_id = 1
_lock = threading.Lock()
_max_messages_per_company = 200
_storage_path = os.path.join(os.path.dirname(__file__), 'tmp', 'internal_chat_messages.json')


def _load_storage():
    try:
        with open(_storage_path, 'r', encoding='utf-8') as file:
            payload = json.load(file)
        messages = payload.get('messages_by_company') or {}
        normalized = {}
        max_id = 0
        for company_id, items in messages.items():
            key = int(company_id)
            normalized[key] = list(items or [])[-_max_messages_per_company:]
            for item in normalized[key]:
                max_id = max(max_id, int(item.get('id') or 0))
        return normalized, max(max_id + 1, int(payload.get('next_message_id') or 1))
    except FileNotFoundError:
        return {}, 1
    except Exception:
        return {}, 1


def _save_storage():
    directory = os.path.dirname(_storage_path)
    os.makedirs(directory, exist_ok=True)
    payload = {
        'next_message_id': _next_message_id,
        'messages_by_company': {
            str(company_id): messages[-_max_messages_per_company:]
            for company_id, messages in _messages_by_company.items()
        },
    }
    tmp_path = _storage_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as file:
        json.dump(payload, file, ensure_ascii=False)
    os.replace(tmp_path, _storage_path)


def _reload_storage():
    global _messages_by_company, _next_message_id
    _messages_by_company, _next_message_id = _load_storage()


def _current_user_id():
    value = session.get('idusuario') or session.get('usuario') or '0'
    return str(value)


def _current_user_name():
    return str(session.get('usuario') or 'Usuario').strip() or 'Usuario'


def _serialize_message(message):
    return {
        'id': message['id'],
        'codclin': message['codclin'],
        'sender_id': message['sender_id'],
        'sender_name': message['sender_name'],
        'message': message['message'],
        'created_at': message['created_at'],
        'mine': message['sender_id'] == _current_user_id(),
    }


@internal_chat_api_bp.get('/api/internal-chat/me')
def internal_chat_me():
    try:
        return jsonify({
            'success': True,
            'idempresa': current_company_id(),
            'idusuario': _current_user_id(),
            'usuario': _current_user_name(),
        })
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400


@internal_chat_api_bp.get('/api/internal-chat/messages')
def internal_chat_messages():
    try:
        company_id = current_company_id()
        after_id = request.args.get('after_id', '').strip()
        try:
            after_value = int(after_id) if after_id else 0
        except ValueError:
            after_value = 0
        with _lock:
            _reload_storage()
            messages = list(_messages_by_company.get(company_id, []))
        if after_value:
            messages = [item for item in messages if item['id'] > after_value]
        else:
            messages = messages[-80:]
        return jsonify({'success': True, 'messages': [_serialize_message(item) for item in messages]})
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'message': 'Erro ao carregar chat interno: {}'.format(exc)}), 500


@internal_chat_api_bp.post('/api/internal-chat/messages')
def internal_chat_send_message():
    global _next_message_id
    data = request.get_json(silent=True) or {}
    text = str(data.get('message') or '').strip()
    if not text:
        return jsonify({'success': False, 'message': 'Digite uma mensagem.'}), 400
    if len(text) > 2000:
        return jsonify({'success': False, 'message': 'Mensagem muito longa.'}), 400
    try:
        company_id = current_company_id()
        with _lock:
            _reload_storage()
            message = {
                'id': _next_message_id,
                'codclin': company_id,
                'sender_id': _current_user_id(),
                'sender_name': _current_user_name(),
                'message': text,
                'created_at': datetime.datetime.now().astimezone().isoformat(),
            }
            _next_message_id += 1
            company_messages = _messages_by_company.setdefault(company_id, [])
            company_messages.append(message)
            if len(company_messages) > _max_messages_per_company:
                del company_messages[:-_max_messages_per_company]
            _save_storage()
        return jsonify({'success': True, 'message': _serialize_message(message)}), 201
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'message': 'Erro ao enviar mensagem interna: {}'.format(exc)}), 500


@internal_chat_api_bp.delete('/api/internal-chat/messages')
def internal_chat_clear_messages():
    try:
        company_id = current_company_id()
        with _lock:
            _reload_storage()
            _messages_by_company[company_id] = []
            _save_storage()
        return jsonify({'success': True, 'message': 'Historico do chat interno limpo.'})
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 400
    except Exception as exc:
        return jsonify({'success': False, 'message': 'Erro ao limpar chat interno: {}'.format(exc)}), 500
