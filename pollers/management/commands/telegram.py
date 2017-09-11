import logging
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, RegexHandler

from django.db import connection
from django.core.management.base import BaseCommand

from datetime import datetime
from dateutil.relativedelta import relativedelta
from pollers.common import get_keyboard_markup
from pollers.models import History, Card, Category

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telemoney.settings import TELEGRAM_BOT_API_TOKEN, TELEGRAM_CHAT_ID

logging.basicConfig(filename='telemoney.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


def get_report_markup(message_id, date):
    keyboard = []

    month = relativedelta(months=+1)

    prev_date = (date - month).strftime('%Y-%m')
    next_date = (date + month).strftime('%Y-%m')
    callback_data = '{} - {}'
    keyboard.append([
        InlineKeyboardButton("<", callback_data=callback_data.format(message_id, prev_date)),
        InlineKeyboardButton(">", callback_data=callback_data.format(message_id, next_date)),
    ])

    keyboard_markup = InlineKeyboardMarkup(keyboard)

    return keyboard_markup


def error(bot, update, error):
    logging.warning('Update "%s" caused error "%s"' % (update, error))


def start(bot, update):
    update.message.reply_text('Hello there {}!'.format(update.message.from_user.id))


def report(bot, update):
    bot.delete_message(chat_id=TELEGRAM_CHAT_ID, message_id=update.message.message_id)

    date = datetime.today().strftime('%Y-%m')
    get_report(bot, update.message.message_id, date, True)


def income(bot, update, groups):
    bot.delete_message(chat_id=TELEGRAM_CHAT_ID, message_id=update.message.message_id)

    details = ''
    amount = float(groups[0])
    if (len(groups[1]) > 0):
        details = groups[1];

    card = Card.objects.get(number=update.message.from_user.id)
    record = History.objects.create(amount=amount, card_id=card.id, details=details.strip(), type='Наличные')

    text = "{}\n\n{}р\n{} (/{})\n" \
           "--------------------------------------------------" \
        .format(record.card.name, amount, record.type, record.id)

    keyboard_markup = get_keyboard_markup(record.id, record.type)

    m = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard_markup)
    record.telegram_message_id = m.message_id
    record.card_id = card.id
    record.save()
    connection.close()


def edit(bot, update, groups):
    bot.delete_message(chat_id=TELEGRAM_CHAT_ID, message_id=update.message.message_id)

    hid = int(groups[0])
    record = History.objects.get(id=hid)
    text = "{}\n\n{}р\n{} ({}) (/{})\n" \
           "--------------------------------------------------" \
        .format(record.card.name, record.amount, record.type, record.details, record.id)
    bot.edit_message_text(text=text, chat_id=TELEGRAM_CHAT_ID,
                          message_id=record.telegram_message_id, reply_markup=get_keyboard_markup(hid, record.type))
    connection.close()


def button(bot, update):
    query = update.callback_query

    data = str(query.data).split(' ')

    if len(data) == 3:
        get_report(bot, query.message.message_id, data[2], False)
        return

    record = History.objects.get(id=data[0])

    try:
        category = Category.objects.get(id=data[1])
        category = {
            'id': category.id,
            'name': category.name,
        }
    except Category.DoesNotExist:
        category = {
            'id': None,
            'name': 'Отменен'
        }

    record.category_id = category['id']
    record.is_active = 1 if category['id'] else 0
    record.save()

    text = "{}\n\n{}р\n{} ({}) (/{})\n\n{}\n" \
           "--------------------------------------------------" \
        .format(record.card.name, record.amount, record.type, record.details, record.id, category['name'])

    bot.edit_message_text(text=text, chat_id=query.message.chat_id,
                          message_id=query.message.message_id)
    connection.close()


def get_report(bot, message_id, date, new=True):
    # print(message_id)
    # print(date)
    result = {
        'text': '',
        'total_in': 0,
        'total_out': 0,
    }

    date = datetime.strptime(date, '%Y-%m')
    rep = History.get_report(date.strftime('%Y-%m-01'), (date + relativedelta(months=+1)).strftime('%Y-%m-01'))

    for i in rep:
        if i['category_id'] == 10:
            result['total_in'] += i['amount']
        else:
            result['total_out'] += i['amount']
            result['text'] += "{}: *{}*\n\n".format(i['category__name'], i['amount'])

    text = "{}\n" \
           "--------------------------------------------------\n" \
           "{}" \
           "--------------------------------------------------\n" \
           "Расходов: {}\n" \
           "Пополнений: {}" \
        .format(date.strftime('%B, %Y'), result['text'], result['total_out'], result['total_in'])

    keyboard_markup = get_report_markup(message_id, date)

    if new:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard_markup, parse_mode='Markdown')
    else:
        bot.edit_message_text(message_id=message_id, chat_id=TELEGRAM_CHAT_ID, text=text, reply_markup=keyboard_markup, parse_mode='Markdown')
    connection.close()


class Command(BaseCommand):
    def handle(self, *args, **options):
        # print(print_report())
        # return

        updater = Updater(TELEGRAM_BOT_API_TOKEN)

        updater.dispatcher.add_handler(CommandHandler('start', start))
        updater.dispatcher.add_handler(CommandHandler('report', report))
        updater.dispatcher.add_handler(CallbackQueryHandler(button))
        updater.dispatcher.add_handler(RegexHandler('/([\d]*)', edit, pass_groups=True))
        # updater.dispatcher.add_handler(RegexHandler('^([\d]*)$', income, pass_groups=True))
        # updater.dispatcher.add_handler(RegexHandler('^(\d+(\.\d+)?)$', income, pass_groups=True))
        updater.dispatcher.add_handler(RegexHandler('^(\d+[\.\d]*)([\s\w]*)$', income, pass_groups=True))
        updater.dispatcher.add_error_handler(error)

        updater.start_polling()

        updater.idle()
