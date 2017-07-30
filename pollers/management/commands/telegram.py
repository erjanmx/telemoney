import logging
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, RegexHandler

from django.core.management.base import BaseCommand

from pollers.common import get_keyboard_markup
from pollers.models import History, Card, Category

from telemoney.settings import TELEGRAM_BOT_API_TOKEN, TELEGRAM_CHAT_ID


logging.basicConfig(filename='telemoney.log', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)


def error(bot, update, error):
    logging.warning('Update "%s" caused error "%s"' % (update, error))


def start(bot, update):
    update.message.reply_text('Hello there {}!'.format(update.message.from_user.id))


def income(bot, update, groups):
    bot.delete_message(chat_id=TELEGRAM_CHAT_ID, message_id=update.message.message_id)

    amount = int(groups[0])
    card = Card.objects.get(number=update.message.from_user.id)
    record = History.objects.create(amount=amount, card_id=card.id, details='', type='Наличные')

    text = "*{}*\n\n{}р\n{}(/{})\n" \
           "--------------------------------------------------" \
        .format(record.card.name, amount, record.type, record.id)

    keyboard_markup = get_keyboard_markup(record.id, record.type)

    m = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode='Markdown',
                         reply_markup=keyboard_markup)
    record.telegram_message_id = m.message_id
    record.card_id = card.id
    record.save()


def edit(bot, update, groups):
    bot.delete_message(chat_id=TELEGRAM_CHAT_ID, message_id=update.message.message_id)

    hid = int(groups[0])
    record = History.objects.get(id=hid)
    text = "*{}*\n\n{}р\n{} {}(/{})\n" \
           "--------------------------------------------------" \
        .format(record.card.name, record.amount, record.type, record.details, record.id)
    bot.edit_message_text(text=text, parse_mode='Markdown',
                          chat_id=TELEGRAM_CHAT_ID,
                          message_id=record.telegram_message_id, reply_markup=get_keyboard_markup(hid, record.type))


def button(bot, update):
    query = update.callback_query

    data = str(query.data).split(' ')

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

    text = "*{}*\n\n{}р\n{} {}(/{})\n\n{}\n" \
        "--------------------------------------------------" \
        .format(record.card.name, record.amount, record.type, record.details, record.id, category['name'])

    bot.edit_message_text(text=text, parse_mode='Markdown',
                          chat_id=query.message.chat_id,
                          message_id=query.message.message_id)


class Command(BaseCommand):
    def handle(self, *args, **options):

        updater = Updater(TELEGRAM_BOT_API_TOKEN)

        updater.dispatcher.add_handler(CommandHandler('start', start))
        updater.dispatcher.add_handler(CallbackQueryHandler(button))
        updater.dispatcher.add_handler(RegexHandler('/([\d]*)', edit, pass_groups=True))
        updater.dispatcher.add_handler(RegexHandler('^([\d]*)$', income, pass_groups=True))
        updater.dispatcher.add_error_handler(error)

        updater.start_polling()

        updater.idle()
