import email
import unittest
from email import policy

import bounce_robot


BOUNCE_MESSAGE = b'''From: Mail Delivery System <mailer-daemon@example.net>
To: sender@example.com
Subject: Mail delivery failed: returning message to sender
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="dsn"

--dsn
Content-Type: text/plain

The message could not be delivered.
--dsn
Content-Type: message/delivery-status

Reporting-MTA: dns; example.net
Original-Message-ID: <tracking-medsoft@example.com>

Final-Recipient: rfc822; invalid@example.com
Action: failed
Status: 5.1.1
Diagnostic-Code: smtp; 550 No such user

--dsn--
'''


class BounceRobotTest(unittest.TestCase):
    def test_extracts_permanent_delivery_failure(self):
        message = email.message_from_bytes(BOUNCE_MESSAGE, policy=policy.default)

        details = bounce_robot._bounce_details(message)

        self.assertEqual(
            details['message_ids'], ['<tracking-medsoft@example.com>']
        )
        self.assertEqual(details['recipients'], ['invalid@example.com'])
        self.assertIn('550 No such user', details['reason'])

    def test_ignores_regular_email(self):
        message = email.message_from_bytes(
            b'From: patient@example.com\nSubject: Hello\n\nMessage',
            policy=policy.default,
        )

        self.assertIsNone(bounce_robot._bounce_details(message))


if __name__ == '__main__':
    unittest.main()
