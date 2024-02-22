import logging
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import MessageEntityType, ParseMode
import pickledb
db = pickledb.load('order.db', True)
import random
import os

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

orders = {}
is_close = True

def get_text_from_command(update:Update):
    entities = update.message.entities
    text = update.message.text
    for it in entities:
        if it.type == MessageEntityType.BOT_COMMAND:
            return text[it.length+1:]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}!",
        reply_markup=ForceReply(selective=True),
    )


async def close_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat.id)
    value = db.get(chat_id)
    if not value:
        value = {
            "isOpen": False,
            'orders' : {}
        }
    else:
        value['isOpen'] = False
    db.set(chat_id, value)
    await update.message.reply_text("✅ OK!")


async def open_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat.id)
    value = db.get(chat_id)
    if not value:
        value = {
            'isOpen' : True,
            'orders' : {}
        }
    else:
        value['isOpen'] = True
        value['orders'] = {}
        value['must_delete'] = {}
        

    db.set(chat_id, value)
    await update.message.reply_text("✅ OK!")


async def retract_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.message.chat.id)
    value = db.get(chat_id)
    if not value:
        return
    must_delete = value.get("must_delete")
    if must_delete:
        await context.bot.deleteMessage(message_id=must_delete['message_id'], chat_id=must_delete['chat_id'])

    fn = update.message.from_user.first_name if update.message.from_user.first_name else ""
    ln = update.message.from_user.last_name if update.message.from_user.last_name else ""
    _o_name = " ".join([fn, ln])
    orders = value['orders']
    orders.pop(_o_name)
    value['orders'] = orders
    db.set(chat_id, value)
    
    order_sum = "Tiểu nhị! cho gọi món:\n"
    goods = {}
    for participant in orders:
        order = orders[participant]
        if not order in goods:
            goods[order] = []
        goods[order].append(participant)

    for order in goods:
        order_sum += f"<b>{order}</b>: {','.join(goods[order])}\n"
    must_delete = await context.bot.send_message(update.effective_chat.id, order_sum,
                                   parse_mode=ParseMode.HTML)
    must_delete = {
        "message_id": must_delete.message_id,
        "chat_id": update.message.chat_id
    }
    value['must_delete'] = must_delete
    db.set(chat_id, value)
    return

async def order_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(update, context)
    chat_id = str(update.message.chat.id)
    value = db.get(chat_id)
    if not value:
        return
    is_close = not value['isOpen']
    orders = value['orders']
    if is_close:
        images = os.listdir("images")
        image_path = os.path.join("images", random.choice(images))
        await update.message.reply_photo(image_path)
        await update.message.reply_text("Đóng đơn rồi đó đá đa...")
        return
    
    must_delete = value.get("must_delete")
    if must_delete:
        await context.bot.deleteMessage(message_id=must_delete['message_id'], chat_id=must_delete['chat_id'])

    _order = get_text_from_command(update)
    _order = _order.lower().strip()
    if _order == "":
        return await update.message.reply_text("Món không hợp lệ.")
    fn = update.message.from_user.first_name if update.message.from_user.first_name else ""
    ln = update.message.from_user.last_name if update.message.from_user.last_name else ""
    _o_name = " ".join([fn, ln])

    orders[_o_name] = _order

    
    value['orders'] = orders

    order_sum = "Tiểu nhị! cho gọi món:\n"
    goods = {}
    for participant in orders:
        order = orders[participant]
        if not order in goods:
            goods[order] = []
        goods[order].append(participant)

    for order in goods:
        order_sum += f"<b>{order}</b>: {','.join(goods[order])}\n"
    must_delete = await context.bot.send_message(update.effective_chat.id, order_sum,
                                   parse_mode=ParseMode.HTML)
    must_delete = {
        "message_id": must_delete.message_id,
        "chat_id": update.message.chat_id
    }
    value['must_delete'] = must_delete
    db.set(chat_id, value)
    return


def main() -> None:
    application = Application.builder().token("6528017239:AAGN59Vgr3v8podnhIZoyobis7XqaERHIuo").build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("order", order_command))
    application.add_handler(CommandHandler("retract", retract_order_command))
    application.add_handler(CommandHandler("close", close_command))
    application.add_handler(CommandHandler("open", open_command))

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()