import telebot
import gspread
import json
import pandas as pd
from datetime import datetime, timedelta
import os
import validators

bot = telebot.TeleBot('') #tg token
messenger = []


@bot.message_handler(commands=["start"])
def start(message):
    global messenger
    messenger.clear()
    start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)

    if not os.path.exists("tables.json"):
        start_markup.row("Подключить Google-таблицу")

    else:
        worksheet, b, df = access_current_sheet()
        subject = ""
        for i in df.index:
            subject += f"[{df.loc[i, 'subject']}]({df.loc[i, 'link']})\n"
        bot.send_message(message.chat.id, subject, parse_mode="MarkdownV2", disable_web_page_preview=True)

    start_markup.row("Посмотреть дедлайны на этой неделе")
    start_markup.row("Редактировать дедлайны")
    start_markup.row("Редактировать предметы")

    info = bot.send_message(message.chat.id, "Что хотите сделать?", reply_markup=start_markup)
    bot.register_next_step_handler(info, choose_action)


def convert_date(date: str = "01/01/00"):
    """ Конвертируем дату из строки в datetime """
    try:
        return datetime.strptime(date, "%d.%m.%Y")
    except ValueError:
        return False


def connect_table(message):
    """ Подключаемся к Google-таблице """
    url = message.text
    sheet_id = " " #google-sheet id
    try:
        with open("tables.json") as json_file:
            tables = json.load(json_file)
        title = len(tables) + 1
        tables[title] = {"url": url, "id": sheet_id}
    except FileNotFoundError:
        tables = {0: {"url": url, "id": sheet_id}}
    with open('tables.json', 'w') as json_file:
        json.dump(tables, json_file)
    bot.send_message(message.chat.id, "Таблица подключена!")
    start(message)


def access_current_sheet():
    """ Обращаемся к Google-таблице """
    with open("tables.json") as json_file:
        tables = json.load(json_file)

    sheet_id = tables[max(tables)]["id"]
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key(sheet_id)
    worksheet = sh.sheet1

    # Преобразуем Google-таблицу в таблицу pandas
    df = pd.DataFrame(worksheet.get_values(""), columns=worksheet.row_values(1))
    df = df.drop(0)
    df.index -= 1
    return worksheet, tables[max(tables)]["url"], df


def choose_action(message):
    """ Обрабатываем действия верхнего уровня """
    if message.text == "Подключить Google-таблицу":
        connect_table(message)

    elif message.text == "Редактировать предметы":
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        start_markup.row("Добавить новый предмет")
        start_markup.row("Отредактировать предмет или ссылку на ведомость")
        start_markup.row("Удалить предмет из списка")
        start_markup.row("Удалить ВСЕ")
        info = bot.send_message(message.chat.id, "Что хотите сделать?", reply_markup=start_markup)
        bot.register_next_step_handler(info, choose_subject_action)

    elif message.text == "Редактировать дедлайны":
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        start_markup.row("Добавить дедлайн")
        start_markup.row("Изменить дату одного из дедлайнов")
        start_markup.row("Удалить один из дедлайнов")
        info = bot.send_message(message.chat.id, "Что хотите сделать?", reply_markup=start_markup)
        bot.register_next_step_handler(info, choose_deadline_action)

    elif message.text == "Посмотреть дедлайны на этой неделе":
        bot.send_message(message.chat.id, "Сейчас посмотрю")
        today = datetime.today()
        week = today + timedelta(days=7)
        worksheet, b, df = access_current_sheet()
        deadlines = ""
        for i in range(2, len(worksheet.col_values(1)) + 1):
            for cur_deadline in worksheet.row_values(i)[2:]:
                if week >= convert_date(cur_deadline) >= today:
                    deadlines += f"{worksheet.cell(i, 1).value}: {cur_deadline}\n"
        if deadlines:
            bot.send_message(message.chat.id, f"Дедлайны в ближайшие дни:\n\n{deadlines}")
        else:
            bot.send_message(message.chat.id, "В ближайшие дни нет дедлайнов!")
        start(message)


def choose_subject_action(message):
    """ Выбираем действие в разделе Редактировать предметы """
    if message.text == "Добавить новый предмет":
        message = bot.send_message(message.chat.id, "Напишите название предмета и через пробел - ссылку на ведомость")
        bot.register_next_step_handler(message, add_new_subject)

    elif message.text == "Отредактировать предмет или ссылку на ведомость":
        worksheet, b, df = access_current_sheet()
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in df.subject:
            start_markup.row(el)
        info = bot.send_message(message.chat.id, "Какой предмет редактируем?", reply_markup=start_markup)
        bot.register_next_step_handler(info, update_subject)

    elif message.text == "Удалить предмет из списка":
        worksheet, b, df = access_current_sheet()
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in df.subject:
            start_markup.row(el)
        info = bot.send_message(message.chat.id, "Какой предмет удаляем?", reply_markup=start_markup)
        bot.register_next_step_handler(info, delete_subject)

    elif message.text == "Удалить ВСЕ":
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        start_markup.row("Да")
        start_markup.row("Нет")
        info = bot.send_message(message.chat.id, "Вы точно хотите удалить ВСЕ?", reply_markup=start_markup)
        bot.register_next_step_handler(info, choose_removal_option)


def choose_deadline_action(message):
    """ Выбираем действие в разделе Редактировать дедлайн """
    if message.text == "Добавить дедлайн":
        worksheet, b, df = access_current_sheet()
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in df.subject:
            start_markup.row(el)
        info = bot.send_message(message.chat.id, "Какому предмету добавляем?", reply_markup=start_markup)
        bot.register_next_step_handler(info, add_subject_deadline)

    elif message.text == "Изменить дату одного из дедлайнов":
        worksheet, b, df = access_current_sheet()
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in df.subject:
            start_markup.row(el)
        info = bot.send_message(message.chat.id, "Для какого предмета изменяем?", reply_markup=start_markup)
        bot.register_next_step_handler(info, update_subject_deadline)

    elif message.text == "Удалить один из дедлайнов":
        worksheet, b, df = access_current_sheet()
        start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for el in df.subject:
            start_markup.row(el)
        info = bot.send_message(message.chat.id, "У какого предмета удаляем дедлайн?", reply_markup=start_markup)
        bot.register_next_step_handler(info, delete_subject_deadline)


def choose_removal_option(message):
    """ Уточняем, точно ли надо удалить все """
    if message.text == "Да":
        bot.send_message(message.chat.id, "Наташ, мы все удалили, Наташ. Совсем все")
        clear_subject_list(message)
    elif message.text == "Нет":
        bot.send_message(message.chat.id, "Хорошо. Тогда возвращаю вас в главное меню")
        start(message)


def add_subject_deadline(message):
    """ Выбираем предмет, у которого надо отредактировать дедлайн """
    global messenger
    messenger.clear()
    messenger.append(message.text)
    inf = bot.send_message(message.chat.id, "Введите время в формате 'dd.mm.yyyy'")
    bot.register_next_step_handler(inf, add_subject_deadline2)


def add_subject_deadline2(message):
    global messenger
    if not convert_date(message.text):
        info = bot.send_message(message.chat.id,
                                "А это точно правильная дата?\nПожалуйста, введите в формате 'dd.mm.yyyy'")
        bot.register_next_step_handler(info, add_subject_deadline2)

    else:
        if convert_date(message.text) < datetime.today():
            info = bot.send_message(message.chat.id,
                                    "Ставить дедлайн в прошлое - идея классная, но не очень рабочая. Введите корректный дедлайн в формате 'dd.mm.yyyy'")
            bot.register_next_step_handler(info, add_subject_deadline2)
        else:
            worksheet, b, df = access_current_sheet()
            row = worksheet.find(messenger[0]).row
            n = len(worksheet.row_values(row))
            worksheet.update_cell(row, n + 1, message.text)
            if not worksheet.cell(1, n + 1).value:
                num = int(worksheet.cell(1, n).value)
                worksheet.update_cell(1, n + 1, num + 1)
            bot.send_message(message.chat.id, "Изменено!")
            start(message)


def update_subject_deadline(message):
    """ Обновляем дедлайн """
    global messenger
    messenger.clear()
    messenger.append(message.text)
    worksheet, b, df = access_current_sheet()
    start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for el in df.columns[2:]:
        start_markup.row(el)
    info = bot.send_message(message.chat.id, "Для какой лабораторной изменяем?", reply_markup=start_markup)
    bot.register_next_step_handler(info, update_subject_deadline2)


def update_subject_deadline2(message):
    global messenger
    messenger.append(message.text)
    info = bot.send_message(message.chat.id, "Введите дату в формате 'dd.mm.yyyy'")
    bot.register_next_step_handler(info, update_subject_deadline3)


def update_subject_deadline3(message):
    global messenger
    if not convert_date(message.text):
        info = bot.send_message(message.chat.id,
                                "А это точно правильная дата?\nПожалуйста, введите в формате 'dd.mm.yyyy'")
        bot.register_next_step_handler(info, update_subject_deadline3)

    else:
        if convert_date(message.text) < datetime.today():
            info = bot.send_message(message.chat.id,
                                    "Ставить дедлайн в прошлое - идея классная, но не очень рабочая. Введите корректный дедлайн в формате 'dd.mm.yyyy'")
            bot.register_next_step_handler(info, update_subject_deadline3)
        else:
            worksheet, b, df = access_current_sheet()
            row = worksheet.find(messenger[0]).row
            col = worksheet.find(messenger[1]).col
            worksheet.update_cell(row, col, message.text)
            bot.send_message(message.chat.id, "Изменено!")
            start(message)


def delete_subject_deadline(message):
    """ Обновляем дедлайн """
    global messenger
    messenger.clear()
    messenger.append(message.text)
    worksheet, b, df = access_current_sheet()
    start_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for el in df.columns[2:]:
        start_markup.row(el)
    info = bot.send_message(message.chat.id, "У какой лабораторной удаляем дедлайн?", reply_markup=start_markup)
    bot.register_next_step_handler(info, delete_subject_deadline2)


def delete_subject_deadline2(message):
    global messenger
    messenger.append(message.text)
    worksheet, b, df = access_current_sheet()
    row = worksheet.find(f"{messenger[0]}").row
    col = worksheet.find(f"{messenger[1]}").col
    worksheet.update_cell(row, col, "")
    bot.send_message(message.chat.id, "Дедлайн удалён!")
    start(message)


def add_new_subject(message):
    """ Вносим новое название предмета в Google-таблицу """
    try:
        name = message.text.split()[0]
        url = message.text.split()[1]
        if not validators.url(url):
            info = bot.send_message(message.chat.id,
                                    "Что-то не так с ссылкой на ведомость. Пожалуйста, отправьте снова название предмета и корректную ссылку")
            bot.register_next_step_handler(info, add_new_subject)
        else:
            worksheet, b, df = access_current_sheet()
            worksheet.append_row([name, url])
            bot.send_message(message.chat.id, "Добавлено!")
            start(message)
    except IndexError:
        info = bot.send_message(message.chat.id,
                                "Что-то не так. Название и ссылку нужно отправить в одном сообщении, через пробел")
        bot.register_next_step_handler(info, add_new_subject)


def update_subject(message):
    """ Обновляем информацию о предмете в Google-таблице """
    global messenger
    messenger.clear()
    messenger.append(message.text)
    info = bot.send_message(message.chat.id,
                            "Отправьте название предмета и ссылку на ведомость, отделив друг от друга пробелом. Если что-то из этого не должно изменяться, просто напишите его так, как и было")
    bot.register_next_step_handler(info, update_subject2)


def update_subject2(message):
    global messenger
    try:
        name = message.text.split()[0]
        url = message.text.split()[1]
        if not validators.url(url):
            info = bot.send_message(message.chat.id,
                                    "Что-то не так с ссылкой на ведомость. Пожалуйста, отправьте снова название предмета и корректную ссылку")
            bot.register_next_step_handler(info, update_subject2)
        else:
            worksheet, b, df = access_current_sheet()
            ind = df.loc[df.isin(messenger).any(axis=1)].index[0] + 2
            cell_list = worksheet.range(f'A{ind}:B{ind}')
            cell_list[0].value = name
            cell_list[1].value = url
            worksheet.update_cells(cell_list)
            bot.send_message(message.chat.id, "Изменено!")
            start(message)
    except IndexError:
        info = bot.send_message(message.chat.id,
                                "Что-то не так. Название и ссылку нужно отправить в одном сообщении, через пробел")
        bot.register_next_step_handler(info, update_subject2)


def delete_subject(message):
    """ Удаляем предмет в Google-таблице """
    worksheet, b, df = access_current_sheet()
    index = df.loc[df.isin([message.text]).any(axis=1)].index[0] + 2
    worksheet.delete_rows(int(index), int(index))
    bot.send_message(message.chat.id, "Удалено!")
    start(message)


def clear_subject_list(message):
    """ Удаляем все из Google-таблицы """
    with open("tables.json") as json_file:
        tables = json.load(json_file)
    sheet_id = tables[max(tables)]["id"]
    gc = gspread.service_account(filename="credentials.json")
    sh = gc.open_by_key(sheet_id)
    worksheet = sh.sheet1
    sh.del_worksheet(worksheet)
    start(message)


if __name__ == "__main__":
    bot.infinity_polling()
