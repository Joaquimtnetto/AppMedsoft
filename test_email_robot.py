import datetime
import unittest
from unittest import mock

from flask import Flask

import agenda_api
import email_robot


class EmailRobotTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.secret_key = 'test-secret'
        self.settings = {
            'smtp_host': 'smtp.example.com',
            'smtp_port': 587,
            'smtp_user': 'user',
            'smtp_password': 'password',
            'smtp_from': 'sender@example.com',
            'smtp_tls': True,
            'smtp_ssl': False,
            'minutes': 5,
            'message_code': 3,
            'birthday_minutes': 1440,
            'birthday_message_code': 7,
        }
        self.appointment = (
            15, datetime.date(2026, 7, 14), '09:30', 'Paciente Teste',
            'Dr Carlos', 'Consulta', 'paciente@example.com',
        )

    @mock.patch.object(email_robot, '_release_appointment')
    @mock.patch.object(email_robot, '_claim_appointment', return_value=object())
    @mock.patch.object(email_robot, '_mark_confirmation_requested')
    @mock.patch.object(email_robot, '_appointment')
    @mock.patch.object(email_robot, '_appointments')
    @mock.patch.object(email_robot, '_message_template', return_value='Confirme sua consulta.')
    @mock.patch.object(email_robot, '_company_configuration')
    @mock.patch.object(agenda_api, '_send_confirmation_email', return_value=(True, ''))
    def test_sends_five_minutes_before_appointment(
            self, send_email, configuration, _template, appointments,
            fresh_appointment, mark_requested, _claim, _release):
        configuration.return_value = self.settings
        appointments.return_value = [self.appointment]
        fresh_appointment.return_value = self.appointment

        sent = email_robot._process_company(
            self.app, 'medsoft_medmigra', 2, 'Clínica Teste',
            datetime.datetime(2026, 7, 14, 9, 25),
        )

        self.assertEqual(sent, 1)
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs['message_type'], 'Email Auto')
        self.assertEqual(kwargs['appointment_id'], 15)
        self.assertEqual(kwargs['message_code'], 3)
        mark_requested.assert_called_once_with('medsoft_medmigra', 2, 15)

    @mock.patch.object(email_robot, '_release_appointment')
    @mock.patch.object(email_robot, '_claim_appointment', return_value=object())
    @mock.patch.object(email_robot, '_mark_confirmation_requested')
    @mock.patch.object(email_robot, '_appointment')
    @mock.patch.object(email_robot, '_appointments')
    @mock.patch.object(email_robot, '_message_template', return_value='Confirme sua consulta.')
    @mock.patch.object(email_robot, '_company_configuration')
    @mock.patch.object(agenda_api, '_send_confirmation_email', return_value=(True, ''))
    def test_reloads_appointment_before_sending(
            self, send_email, configuration, _template, appointments,
            fresh_appointment, _mark, _claim, _release):
        configuration.return_value = self.settings
        appointments.return_value = [self.appointment]
        fresh_appointment.return_value = (
            15, datetime.date(2026, 7, 14), '09:32', 'Paciente Teste',
            'Dr Carlos', 'Consulta', 'paciente@example.com',
        )

        sent = email_robot._process_company(
            self.app, 'medsoft_medmigra', 2, 'Clínica Teste',
            datetime.datetime(2026, 7, 14, 9, 27),
        )

        self.assertEqual(sent, 1)
        message_context = send_email.call_args.args[1]
        self.assertEqual(message_context['hora'], '09:32')

    @mock.patch.object(email_robot, '_appointments')
    @mock.patch.object(email_robot, '_message_template', return_value='Confirme sua consulta.')
    @mock.patch.object(email_robot, '_company_configuration')
    @mock.patch.object(agenda_api, '_send_confirmation_email')
    def test_does_not_send_before_configured_time(
            self, send_email, configuration, _template, appointments):
        configuration.return_value = self.settings
        appointments.return_value = [self.appointment]

        sent = email_robot._process_company(
            self.app, 'medsoft_medmigra', 2, 'Clínica Teste',
            datetime.datetime(2026, 7, 14, 9, 24, 59),
        )

        self.assertEqual(sent, 0)
        send_email.assert_not_called()

    @mock.patch.object(email_robot, '_release_birthday')
    @mock.patch.object(email_robot, '_claim_birthday', return_value=object())
    @mock.patch.object(email_robot, '_birthday_patients')
    @mock.patch.object(
        email_robot, '_message_template',
        return_value=('Feliz aniversário, {paciente}!', False),
    )
    @mock.patch.object(email_robot, '_company_configuration')
    @mock.patch.object(agenda_api, '_send_confirmation_email', return_value=(True, ''))
    def test_sends_birthday_message_one_day_before(
            self, send_email, configuration, _template, patients,
            _claim, _release):
        configuration.return_value = self.settings
        patients.return_value = [(
            42, 'Paciente Teste', datetime.date(1964, 7, 14),
            'paciente@example.com',
        )]

        sent = email_robot._process_birthdays(
            self.app, 'medsoft_medmigra', 2, 'Clínica Teste',
            datetime.datetime(2026, 7, 13, 14, 0),
        )

        self.assertEqual(sent, 1)
        kwargs = send_email.call_args.kwargs
        self.assertEqual(kwargs['message_type'], 'Email Auto')
        self.assertIsNone(kwargs['appointment_id'])
        self.assertEqual(kwargs['message_code'], 7)
        self.assertIn('Paciente Teste', kwargs['subject'])

    @mock.patch.object(email_robot, '_birthday_patients')
    @mock.patch.object(
        email_robot, '_message_template',
        return_value=('Feliz aniversário, {paciente}!', False),
    )
    @mock.patch.object(email_robot, '_company_configuration')
    @mock.patch.object(agenda_api, '_send_confirmation_email')
    def test_does_not_send_birthday_before_configured_day(
            self, send_email, configuration, _template, patients):
        configuration.return_value = self.settings
        patients.return_value = [(
            42, 'Paciente Teste', datetime.date(1964, 7, 14),
            'paciente@example.com',
        )]

        sent = email_robot._process_birthdays(
            self.app, 'medsoft_medmigra', 2, 'Clínica Teste',
            datetime.datetime(2026, 7, 12, 23, 59, 59),
        )

        self.assertEqual(sent, 0)
        send_email.assert_not_called()

    @mock.patch.object(agenda_api, 'log_sent_message')
    def test_invalid_email_is_recorded_as_failed_attempt(self, log_message):
        sent, error = agenda_api._send_confirmation_email(
            'paciente@gmil.com',
            {
                'data': datetime.date(2026, 7, 14),
                'hora': '09:30',
                'paciente': 'Paciente Teste',
                'profissional': 'Dr Carlos',
            },
            self.settings,
            message_code=3,
            company_id=2,
            message_type='Email Auto',
            appointment_id=15,
            database_name='medsoft_medmigra',
        )

        self.assertFalse(sent)
        self.assertIn('digitado incorretamente', error)
        self.assertFalse(log_message.call_args.kwargs['sent'])
        self.assertEqual(log_message.call_args.kwargs['appointment_id'], 15)
        self.assertTrue(log_message.call_args.kwargs['error_reason'])


if __name__ == '__main__':
    unittest.main()
