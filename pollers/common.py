from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from .models import Category


def get_keyboard_markup(message_id, history_type=''):
    keyboard = []
    kb = []

    callback_data = "{} {}"
    history_type = history_type.lower()

    keyboard.append([InlineKeyboardButton("Пополнение", callback_data=callback_data.format(message_id, 10))])

    if history_type == 'зачисление':
        kb.append(InlineKeyboardButton("Подвердить", callback_data=callback_data.format(message_id, 10)))
    else:
        for category in Category.objects.filter(is_visible=1).order_by("position"):
            kb.append(InlineKeyboardButton(category.name, callback_data=callback_data.format(message_id, category.id)))
            if len(kb) == 2:
                keyboard.append(kb)
                kb = []

    keyboard.append(kb)
    keyboard.append([
        InlineKeyboardButton("Отменить", callback_data=callback_data.format(message_id, 0))
    ])
    keyboard_markup = InlineKeyboardMarkup(keyboard)

    return keyboard_markup

