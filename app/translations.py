TEXTS = {
    "ru": {
        "welcome": "Добро пожаловать. Пожалуйста, выберите язык.",
        "menu_consultation": "Консультация",
        "menu_terms": "Условия работы",
        "menu_qual": "Квалификация",
        "menu_about": "О психотерапии",
        "btn_online": "Онлайн",
        "btn_onsite": "Очно",
        "btn_individual": "Индивидуальная ({price})",
        "btn_couple": "Парная ({price})",
        "ask_timezone": "Пожалуйста, укажите ваш часовой пояс (например, UTC+3, Москва).",
        "ask_time": "Напишите желаемые дни и время для встречи.",
        "ask_problem": "Кратко опишите ваш запрос или проблему.",
        "ask_address": "Как к вам обращаться?",
        "ask_comm": "Предпочтительный способ связи (Telegram, WhatsApp)?",
        "skip": "Пропустить",
        "confirm_sent": "Ваш запрос отправлен. Я свяжусь с вами в ближайшее время.",
        "waitlist_intro": "К сожалению, сейчас нет свободных мест. Вы можете оставить заявку в лист ожидания.",
        "waitlist_contacts": "Оставьте ваши контакты для связи.",
        "error_generic": "Произошла ошибка. Попробуйте позже.",
        "negotiation_new": "Новое предложение от терапевта:\n\n{msg}",
        "btn_agree": "Согласиться",
        "btn_counter": "Предложить другое время",
        "negotiation_agreed": "Время согласовано: {time}",
        "negotiation_rejected": "Заявка отклонена.",
        "status_confirmed": "Встреча подтверждена!",
        "file_not_found": "Информация пока не добавлена.",
        "menu_home": "🏠 Домой",
        "welcome_back": "Вы вернулись в главное меню.",
        # 🔧 ADDED: Booking cancellation message
        "booking_cancelled": "Запись отменена. Вы вернулись в главное меню."
    },
    "am": {
        "welcome": "Բարի գալուստ: Խնդրում ենք ընտրել լեզուն:",
        "menu_consultation": "Խորհրդատվություն",
        "menu_terms": "Աշխատանքի պայմաններ",
        "menu_qual": "Որակավորում",
        "menu_about": "Հոգեթերապիայի մասին",
        "btn_online": "Առցանց",
        "btn_onsite": "Առկա",
        "btn_individual": "Անհատական ({price})",
        "btn_couple": "Զույգերի ({price})",
        "ask_timezone": "Նշեք ձեր ժամային գոտին:",
        "ask_time": "Նշեք ցանկալի օրերը և ժամերը:",
        "ask_problem": "Հակիրճ նկարագրեք ձեր խնդիրը:",
        "ask_address": "Ինչպե՞ս դիմել ձեզ:",
        "ask_comm": "Նախընտրելի կապի միջոց (Telegram, WhatsApp)?",
        "skip": "Բաց թողնել",
        "confirm_sent": "Ձեր հայտը ուղարկված է: Ես կկապնվեմ ձեզ հետ:",
        "waitlist_intro": "Ցավոք, այս պահին ազատ տեղեր չկան: Կարող եք գրանցվել սպասման ցուցակում:",
        "waitlist_contacts": "Թողեք ձեր կոնտակտային տվյալները:",
        "error_generic": "Տեղի է ունեցել սխալ:",
        "negotiation_new": "Նոր առաջարկ թերապևտից:\n\n{msg}",
        "btn_agree": "Համաձայնվել",
        "btn_counter": "Առաջարկել այլ ժամանակ",
        "negotiation_agreed": "Ժամանակը հաստատված է: {time}",
        "negotiation_rejected": "Հայտը մերժված է:",
        "status_confirmed": "Հանդիպումը հաստատված է!",
        "file_not_found": "Տեղեկատվությունը դեռ ավելացված չէ:",
        "menu_home": "🏠 Գլխավոր",
        "welcome_back": "Դուք վերադարձել եք գլխավոր մենյու:",
        # 🔧 ADDED: Booking cancellation message
        "booking_cancelled": "Ամրագրումը չեղարկվեց: Դուք վերադարձել եք գլխավոր մենյու:"
    }
}

def get_text(lang, key, **kwargs):
    text = TEXTS.get(lang, TEXTS['ru']).get(key, "")
    if kwargs:
        return text.format(**kwargs)
    return text