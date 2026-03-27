from typing import Annotated, Sequence, TypedDict, Union, Dict
from dotenv import load_dotenv  
from langchain_core.messages import BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from datetime import datetime
import os
import sqlite3
from langchain_core.messages import AIMessage
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from urllib.request import urlopen
   
load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
TARO_URL = os.getenv(
    "TARO_URL"
)
NUMEROLOGY_URL = os.getenv(
    "NUMEROLOGY_URL"
)
URL_TIMEOUT_SECONDS = int(os.getenv("URL_TIMEOUT_SECONDS", "15"))

class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_id: int

@tool
def numerology_code(birthdate: str) -> Union[int, str]:
    """
    Рассчитывает нумерологический код из даты рождения в формате ДД.ММ.ГГГГ.
    Проверяет, что дата существует, человеку от 15 до 100 лет.
    Пример: 16.04.1993 -> 6
    """
    try:
        birth = datetime.strptime(birthdate, "%d.%m.%Y").date()
        today = datetime.today().date()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))

        if age < 15:
            return f"Возраст {age} лет — слишком мало. Нужно минимум 15."
        elif age > 100:  
            return f"Возраст {age} лет — слишком много. Максимум 100."
        elif birth > today:
            return "Дата рождения из будущего недопустима."
    except ValueError:
        return "Неверный формат даты. Используйте ДД.ММ.ГГГГ."

    digits = [int(ch) for ch in birthdate if ch.isdigit()]
    total = sum(digits)
    while total > 9:
        digits = [int(ch) for ch in str(total)]
        total = sum(digits)
    return total 

@tool
def calculate_age(birthdate: str) -> Union[Dict[str, Union[int, str]], str]:
    """
Вычисляет возраст человека на сегодняшнюю дату по дате рождения.

КОГДА ИСПОЛЬЗОВАТЬ: 
1. Используй этот инструмент БЕЗУСЛОВНО, как только пользователь предоставил дату рождения в любом виде. 
2. Тебе запрещено самостоятельно подтверждать валидность даты или называть возраст, не получив ответ от этого инструмента. 
3. Любое упоминание даты рождения — это прямой сигнал к вызову calculate_age.
    """
    try:
        birth = datetime.strptime(birthdate, "%d.%m.%Y").date()
        today = datetime.today().date()
        if birth > today:
            return "Дата рождения из будущего недопустима."
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if age < 15:
            return f"Возраст {age} лет — слишком мало. Нужно минимум 15."
        elif age > 100:
            return f"Возраст {age} лет — слишком много. Максимум 100."
        return {"age": age, "message": f"Возраст {age} лет — допустимый."}
    except ValueError:
        return "Неверный формат даты. Используйте ДД.ММ.ГГГГ."

@tool
def get_taro() -> str:
    f"""{tool_get_taro}"""
    try:
        with urlopen(TARO_URL, timeout=URL_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8")
        return f"База даных (Taro):\n\n{text}"
    except Exception:
        return "Не удалось прочитать файл."


@tool
def get_numerology() -> str:
    f"""{tool_get_numerology}"""
    try:
        with urlopen(NUMEROLOGY_URL, timeout=URL_TIMEOUT_SECONDS) as response:
            text = response.read().decode("utf-8")
        return f"База даных (Numerology):\n\n{text}"
    except Exception:
        return "Не удалось прочитать файл."


tools = [numerology_code, calculate_age, get_taro, get_numerology]
model = ChatOpenAI(model=OPENAI_MODEL).bind_tools(tools)

PROMPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "promtgadalka.txt")
tool_get_taro = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_taro.txt")
tool_get_numerology = os.path.join(os.path.dirname(os.path.abspath(__file__)), "get_numerology.txt")
def model_call(state: AgentState) -> AgentState:
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        prompt_text = f.read()
    user_id = state.get("user_id")
    gender_value = get_gender(user_id) if user_id is not None else None
    if gender_value == "Мужской":
        gender_param = "man"
    elif gender_value == "Женский":
        gender_param = "woman"
    else:
        gender_param = "man"
    prompt_text = prompt_text.replace("{GENDER}", gender_param)
    system_prompt = SystemMessage(content=prompt_text)
    response = model.invoke([system_prompt] + state["messages"])
    return {"messages": state["messages"] + [response]}

def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "continue"
    return "end"


graph = StateGraph(AgentState)
graph.add_node("our_agent", model_call)
tool_node = ToolNode(tools=tools)
graph.add_node("tools", tool_node)
graph.set_entry_point("our_agent")
graph.add_conditional_edges("our_agent", should_continue, {"continue": "tools", "end": END})
graph.add_edge("tools", "our_agent")
app = graph.compile()

# Telegram Bot Part
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes


with open('promtgadalka.txt', 'r', encoding='utf-8') as f:
    content = f.read()

BOT_TOKEN = os.getenv("BOT_API")  


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS genders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gender TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_gender(user_id: int, gender: str):
    """Always save/overwrite gender for this user when they tap a button."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE genders SET gender = ? WHERE user_id = ?", (gender, user_id))
    if cur.rowcount == 0:
        cur.execute("INSERT INTO genders (user_id, gender) VALUES (?, ?)", (user_id, gender))
    conn.commit()
    conn.close()

def get_gender(user_id: int) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT gender FROM genders WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('''
🔮 Привет! Меня зовут Лира.
Я могу:
1️⃣ Рассказать, как работает наш сайт и чем он может помочь.
2️⃣ Сделать для тебя короткий разбор по твоему вопросу.
3️⃣ Толкование снов
✍️ Напиши, пожалуйста, что тебе нужно: помощь по сайту или разбор.
''')
    keyboard = [
        [InlineKeyboardButton("Мужской", callback_data="gender_male")],
        [InlineKeyboardButton("Женский", callback_data="gender_female")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Укажите ваш пол", reply_markup=reply_markup)

async def gender_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    if data == "gender_male":
        gender = "Мужской"
    elif data == "gender_female":
        gender = "Женский"
    else:
        return
    save_gender(user_id, gender)
    await query.edit_message_text("Сохранено")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    print(f"Message from {user_id} ---      {text} ---")

    if user_id not in user_states:
        user_states[user_id] = {"messages": []}

    state = user_states[user_id].copy()
    state["messages"] = list(state["messages"])
    state["messages"].append(HumanMessage(content=text))
    state["user_id"] = user_id

    async for step in app.astream(state, stream_mode="values"):
        last_msg = step["messages"][-1]
        
        if isinstance(last_msg, AIMessage) and last_msg.tool_calls:
            for tool_call in last_msg.tool_calls:
                print(f"🔧 TOOL CALL: {tool_call['name']} with args: {tool_call['args']}")
        
        if isinstance(last_msg, ToolMessage):
            print(f"📤 TOOL RESULT [{last_msg.name}]: {last_msg.content}")
        
        if isinstance(last_msg, AIMessage) and last_msg.content:
            await update.message.reply_text(f" {last_msg.content}")
            print(f"Response is ---{last_msg.content}---")
    user_states[user_id] = step



def main():
    init_db()
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))
    tg_app.add_handler(CallbackQueryHandler(gender_callback, pattern="^gender_"))
    tg_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot is running...")
    tg_app.run_polling()

if __name__ == "__main__":
    main()
