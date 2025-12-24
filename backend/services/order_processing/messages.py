PLN_WARNINGS = {
    "BUY": {
        "uk": [
            """❓номер рахунку
❓номер телефону BLIK 
(того самого банку)
❓назва банку
«Щось одне» - НЕДОСТАТНЬО ❌ --- +48 609 819 779""",
        ],
        "en": [
            """I need ALL details: ❓account number IBAN
❓BLIK phone number
     (same bank) 
❓bank name.
Missing info = NO PAYMENT ❌--- +48 609 819 779""",
        ],
    },
    "SELL": {
        "uk": [
            """Не відправляйте гроші з рахунків третіх осіб ❌.
              Перекази від сім’ї, родичів, друзів = ЗАТРИМКА ❌ і потім заберете їх через ПРОКУРАТУРУ.
              Переказ ЛИШЕ ВІД СЕБЕ, ПІБ як в акаунті.""",
            """Копіюйте і вставляйте мої дані БЕЗ ЗМІН.
                Немає одержувача або титулу — ПОВЕРНЕННЯ НАСТУПНОГО РОБОЧОГО ДНЯ ❌.""",
            "Чек PDF + твій телефон → В ЧАТ. --- +48 609 819 779",
        ],
        "en": [
            """Do NOT send money from third-party accounts ❌.
              Transfers from family/relatives/friends = HELD ❌ and later reclaimed via the prosecutor’s office.
              Send ONLY FROM YOUR OWN ACCOUNT — name must match your KYC.""",
            """Copy/paste my details EXACTLY.
              Missing receiver or title = REFUND NEXT BUSINESS DAY ❌.""",
            "Receipt PDF + your phone → IN CHAT. --- +48 609 819 779",
        ],
    },
}


STATUS20 = {
    "en": {
        "BUY": "I pressed Paid to avoid auto-cancel. I will pay now. Please release only after money arrives!",
        "SELL": "I see you clicked Paid — please send PDF payment confirmation and your phone number.",
    },
    "uk": {
        "BUY": "Я натиснув Оплачено, щоб ордер не скасувався. Зараз виконаю оплату. Будь ласка, не відпускай до фактичного зарахування грошей!",
        "SELL": "Бачу, що ти натиснув оплачено — надішли PDF-чек та свій номер телефону.",
    },
}

INTRO_TEMPLATES = {
    "en": {
        "BUY": {"line": "I BUY {token} {quantity} / {currency} {amount} – ({price})", "header": "from:"},
        "SELL": {"line": "I SELL {token} {quantity} / {currency} {amount} – ({price})", "header": "to:"},
    },
    "uk": {
        "BUY": {"line": "Я купую {token} {quantity} / {currency} {amount} – ({price})", "header": "від:"},
        "SELL": {"line": "Я продаю {token} {quantity} / {currency} {amount} – ({price})", "header": "для:"},
    },
}

PAYMENT_LABELS = {
    "en": {
        "recipient": "Recipient (copy without changes)",
        "account": "Account number",
        "or": "AND",
        "phone": "BLIK phone number",
        "title": "Title",
    },
    "uk": {
        "recipient": "Назва отримувача (КОПІЮВАТИ БЕЗ ЗМІН)",
        "account": "Номер рахунку",
        "or": "І",
        "phone": "Номер телефону BLIK",
        "title": "Призначення платежу",
    },
}

MESSAGES = {
    "en": {
        "bot_check": "Bot is checking your payment details, found:",
        "bot_send": "Bot will send payment details here (↓)\nNO 3rd person! COPY PASTE only! (↓)",
        "ask_bank": "Please write Real Bank Name",
        "ask_account": "Please write Bank Account Number",
        "ask_phone": "Please write Blik Phone Number",
        "ask_separate": "Send each value as a separate message.",
        "payment_complete": "Thanks, all required payment details received.",
        "payment_missing": "Payment details are missing; please share bank name, account number or phone, and payment title",
        "manual_payment_details": "Payment details will be provided manually.",
        "manual_details": "Payment details will be provided manually in chat",
        "title_note": "This title must be COPY/PASTED exactly into payment title. Order number is NOT enough. Changing the title = REFUND next business day",
    },
    "uk": {
        "bot_check": "Бот перевіряє твої платіжні дані, знайшов:",
        "bot_send": "Бот надішле реквізити тут (↓)\nЛИШЕ КОПІЮВАТИ/ВСТАВЛЯТИ (↓)",
        "ask_bank": "Напиши назву банку",
        "ask_account": "Напиши номер рахунку",
        "ask_phone": "Напиши номер телефону BLIK",
        "ask_separate": "Надішли кожне значення окремим повідомленням.",
        "payment_complete": "Дякую, всі необхідні платіжні дані отримано.",
        "payment_missing": "Немає платіжних даних; надішли назву банку, номер рахунку, номер телефону blik (до того самого рахунку)",
        "manual_payment_details": "Реквізити надам вручну",
        "manual_details": "Реквізити даю в чаті вручну",
        "title_note": "Цей титул ОБОВ'ЯЗКОВО копіювати/вставляти БЕЗ ЗМІН у назву/призначення. Самого номеру НЕ достатньо. ЗМІНА ТИТУЛУ = ПОВЕРНУ наступного робочого дня",
    },
}
