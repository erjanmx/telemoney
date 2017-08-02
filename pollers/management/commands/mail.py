# -*- coding: utf-8 -*-
import os
import httplib2
import telegram

from apiclient import errors, discovery
from oauth2client import tools
from oauth2client import client
from oauth2client.file import Storage

from django.utils import timezone
from django.core.management.base import BaseCommand

from pollers.models import History, Card
from pollers.common import get_keyboard_markup
from telemoney.settings import TELEGRAM_BOT_API_TOKEN, TELEGRAM_CHAT_ID


def get_authorization():
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'gmail-python.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets('client_secret.json', 'https://www.googleapis.com/auth/gmail.readonly')
        flow.user_agent = 'Gmail API Python'
        credentials = tools.run_flow(flow, store)

    return credentials.authorize(httplib2.Http())


def get_all_messages_list(service, user_id):
    try:
        response = service.users().messages().list(userId=user_id).execute()

        return response['messages']
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def get_message(service, user_id, message_id):
    try:
        message = service.users().messages().get(userId=user_id, id=message_id).execute()

        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)


def parse_message(content):
    message = dict()

    import re
    import datetime

    recomp = re.compile(r'(?P<card>VISA[\d]{4}?)\s(?P<datetime>[\s\d.:]{14}?)\s(?P<type>.*?) '
                        r'(?P<amount>[\d.]+?)р\s(?P<details>.*?)Баланс: (?P<balance>[\d.]+?)р', re.DOTALL)
    f = recomp.search(content)

    if f:
        message = {
            'card': f.group('card'),
            'type': f.group('type'),
            'amount': f.group('amount'),
            'balance': f.group('balance'),
            'details': f.group('details'),
            'datetime': timezone.make_aware(datetime.datetime.strptime(f.group('datetime'), '%d.%m.%y %H:%M'),
                                            timezone.get_current_timezone())
        }

    return message


class Command(BaseCommand):
    def handle(self, *args, **options):
        service = discovery.build('gmail', 'v1', http=get_authorization())
        messages = get_all_messages_list(service, 'me')

        for msg in messages:
            record = History.objects.filter(gmail_id=msg['id'])
            if not record:
                raw_content = get_message(service, 'me', msg['id'])['snippet']
                message = parse_message(raw_content)

                if message:
                    card = Card.objects.get(number=message['card'])

                    record = History.objects.create(datetime=message['datetime'], card_id=card.id,
                                                    amount=message['amount'], gmail_id=msg['id'],
                                                    details=message['details'], type=message['type'],
                                                    balance=message['balance'], raw_text=raw_content)

                    bot = telegram.Bot(TELEGRAM_BOT_API_TOKEN)
                    text = "{}\n\n{}р\n{} {}(/{})\n" \
                           "--------------------------------------------------"\
                        .format(record.card.name, record.amount, record.type, record.details, record.id)

                    similar = History.objects.filter(type=message['type'], details=message['details'],
                                                     category__isnull=False).exclude(details__exact='').last()

                    keyboard_markup = None
                    if message['type'] == 'зачисление':
                        record.is_active = 1
                        record.category_id = 10
                    elif similar:
                        record.is_active = 1
                        record.category_id = similar.category_id
                        text = "{}\n\n{}р\n{} {}(/{})\n\n{}\n" \
                               "--------------------------------------------------" \
                            .format(card.name, record.amount, record.type, record.details, record.id,
                                    similar.category.name)
                    else:
                        keyboard_markup = get_keyboard_markup(record.id, message['type'])

                    m = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard_markup)

                    record.telegram_message_id = m.message_id
                    record.save()

                    self.stdout.write(self.style.SUCCESS('Successfully added "%s"' % msg['id']))
