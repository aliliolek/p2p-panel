PLN_WARNINGS = {
    "BUY": {
        "uk": [
            (
                "❓ номер рахунку\n"
                "❓ номер телефону BLIK\n"
                "  (того самого банку)\n"
                "❓ назва банку\n"
                "«Щось одне» - НЕДОСТАТНЬО ❌ --- +48 609 819 779"
            ),
        ],
        "en": [
            (
                "I need ALL details:\n"
                "❓ account number IBAN\n"
                "❓ BLIK phone number\n"
                "  (same bank)\n"
                "❓ bank name\n"
                "Missing info = NO PAYMENT ❌ --- +48 609 819 779"
            ),
        ],
    },
    "SELL": {
        "uk": [
            (
                "Гроші від родичів/друзів = ЗАМОРОЖЕНІ ❌ ВТРАЧЕНІ ❌\n"
                "Переказ ЛИШЕ ВІД ТЕБЕ, ПІБ як в акаунті ✅👍"
            ),
            (
                "Копіюйте і вставляйте мої дані БЕЗ ЗМІН.\n"
                "Немає одержувача або титулу — ПОВЕРНЕННЯ НАСТУПНОГО РОБОЧОГО ДНЯ ❌."
            ),
            "Чек PDF + Твій номер телефону → В ЧАТ --- +48 609 819 779",
        ],
        "en": [
            (
                "Transfers from family/relatives/friends = LOST ❌ FROZEN ❌\n"
                "Send ONLY FROM YOUR OWN ACCOUNT — name must match your KYC ✅👍"
            ),
            (
                "Copy/paste my details EXACTLY.\n"
                "Missing receiver or title = REFUND NEXT BUSINESS DAY ❌."
            ),
            "Receipt PDF + Your phone number → IN CHAT --- +48 609 819 779",
        ],
    },
}


STATUS20 = {
    "en": {
        "BUY": (
            "DON'T release crypto!\n"
            "(only after money arrives)\n"
            "I pressed Paid to avoid auto-cancel.\n"
            "I will pay manually!"
        ),
        "SELL": (
            "I see You clicked Paid —\n"
            "please send PDF payment confirmation\n"
            "and Your PHONE NUMBER"
        ),
    },
    "uk": {
        "BUY": (
            "НЕ відпускай!\n"
            "(поки не побачиш гроші!)\n"
            "Я натиснув Оплачено, щоби ордер не скасувався.\n"
            "Скоро виконаю оплату"
        ),
        "SELL": (
            "Бачу, що Ви натиснули оплачено —\n"
            "прошу PDF-чек\n"
            "та Ваш номер телефону."
        ),
    },
}

INTRO_TEMPLATES = {
    "en": {
        "BUY":  {"line": "I BUY {token} {quantity} / {currency} {amount} – ({price})",  "header": "from:"},
        "SELL": {"line": "I SELL {token} {quantity} / {currency} {amount} – ({price})", "header": "to:"},
    },
    "uk": {
        "BUY":  {"line": "Я купую {token} {quantity} / {currency} {amount} – ({price})",  "header": "від:"},
        "SELL": {"line": "Я продаю {token} {quantity} / {currency} {amount} – ({price})", "header": "для:"},
    },
}

PAYMENT_LABELS = {
    "en": {
        "recipient": "Recipient (copy without changes)",
        "account":   "Account number",
        "or":        "AND",
        "phone":     "BLIK phone number",
        "title":     "Title",
    },
    "uk": {
        "recipient": "Назва отримувача (КОПІЮВАТИ БЕЗ ЗМІН)",
        "account":   "Номер рахунку",
        "or":        "І",
        "phone":     "Номер телефону BLIK",
        "title":     "Призначення платежу",
    },
}

ASK_SEQUENCES = {
    "ask_phone": {
        "uk": [
            "Номер телефону BLIK +48 🙏👀↘️",
            "Напиши свій номер телефону BLIK",
            "Можу відправити лише якщо даси номер телефону підключений в налаштуваннях BLIK для отримання переказів — польський +48",
            "Номер телефону BLIK +48 👀🙏↘️",
        ],
        "en": [
            "BLIK phone number +48 🙏👀↘️",
            "Please write your BLIK phone number",
            "I can only send payment once you provide a phone number registered in BLIK settings for receiving transfers — must be a Polish number +48",
            "BLIK phone number +48 🙏👀↘️",
        ],
        "max_repeats": 10,
    },
    "ask_account": {
        "uk": [
            "Номер рахунку 26 цифр 🙏👀↘️",
            "Напиши свій номер банківського рахунку (26 цифр)",
            "Можу відправити лише на рахунок у польському банку — 26 цифр (формат IBAN PL). Номер картки не підходить",
            "Номер рахунку 26 цифр 🙏👀↘️",
        ],
        "en": [
            "Account number 26 digits 🙏👀↘️",
            "Please write your bank account number (26 digits)",
            "I can only transfer to a Polish bank account — 26 digits (IBAN PL format). Card number will not work",
            "Account number 26 digits 🙏👀↘️",
        ],
        "max_repeats": 10,
    },
}


MESSAGES = {
    "en": {
        "bot_check":           "Bot is checking your payment details, found:",
        "bot_send":            "Bot will send payment details here (↓)\nNO 3rd person! COPY PASTE only! (↓)",
        "ask_bank":            "Please write Real Bank Name",
        "payment_complete":    "Thanks, all required payment details received.",
        "payment_missing":     "Payment details are missing; please share bank name, account number or phone, and payment title",
        "manual_payment_details": "Payment details will be provided manually.",
        "manual_details":      "Payment details will be provided manually in chat",
        "title_note":          "This title must be COPY/PASTED exactly into payment title. Order number is NOT enough. Changing the title = REFUND next business day",
    },
    "uk": {
        "bot_check":           "Бот перевіряє твої платіжні дані, знайшов:",
        "bot_send":            "Бот надішле реквізити тут (↓)\n КОПІЮВАТИ/ВСТАВЛЯТИ (↓)",
        "ask_bank":            "Напиши назву банку",
        "payment_complete":    "Дякую, всі необхідні платіжні дані отримано.",
        "payment_missing":     "Немає платіжних даних; надішли назву банку, номер рахунку, номер телефону blik (до того самого рахунку)",
        "manual_payment_details": "Реквізити надам вручну",
        "manual_details":      "Реквізити даю в чаті вручну",
        "title_note":          "Цей титул ОБОВ'ЯЗКОВО копіювати/вставляти БЕЗ ЗМІН у назву/призначення. Самого номеру НЕ достатньо. ЗМІНА ТИТУЛУ = ПОВЕРНУ наступного робочого дня",
    },
}
