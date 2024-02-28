import logging
from telegram import ForceReply, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, JobQueue
from telegram.constants import MessageEntityType, ParseMode
import datetime, pytz
import pandas as pd
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
        db.set(chat_id, value)
        await update.message.reply_text("✅ OK!")
    else:
        candidates = list(value['orders'].keys())
        value['isOpen'] = False
        db.set(chat_id, value)
        await update.message.reply_text("✅ OK!")
        chat_id = update.effective_message.chat_id
        if str(chat_id) == "-4179085435": # group "Đặt cơm 2024"
            if len(candidates) > 0:
                pickup_persons = ', '.join(random.sample(candidates, k=len(candidates)//10+1))
                await update.message.reply_text(f"<b>{pickup_persons}</b> ơi, chúng tôi tin bạn 🙆‍♂️", parse_mode=ParseMode.HTML)


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
        await update.message.reply_sticker(image_path)
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


async def notify_lunch(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the notify"""
    job = context.job
    image_path = "images/image.jpeg"
    await context.bot.send_sticker(job.chat_id, image_path)

    df = pd.read_csv("vendors.csv")
    choosen_food = df.sample(1).iloc[0]["name"]
    await context.bot.send_message(job.chat_id, text=f"{choosen_food} đê")


async def notify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """set daily notify schedule"""
    chat_id = update.effective_message.chat_id
    value = get_text_from_command(update)
    chat_id_configs = db.get(str(chat_id))
    if not value in ["on", "off"]:
        
        status = "Bật" if chat_id_configs.get("is_daily_notify") else "Tắt"
        return await update.effective_message.reply_text(f"Thông báo hằng ngày đang {status}.")
    
    chat_id_configs["is_daily_notify"] = True if (value=="on") else False
    db.set(str(chat_id), chat_id_configs)
    job_name = f"notify_lunch_{str(chat_id)}"
    if value=="on":
        if len(context.job_queue.get_jobs_by_name(job_name)) == 0:
            context.job_queue.run_daily(notify_lunch,
                                        time=datetime.time(10, 30, 0, tzinfo=pytz.timezone('Asia/Ho_Chi_Minh')),
                                        days=tuple(range(1,6)), # ignore weekends
                                        chat_id=chat_id,
                                        name=job_name,
                                        )
    else:
        for current_job in context.job_queue.get_jobs_by_name(job_name):
            current_job.schedule_removal()
    
    return await update.effective_message.reply_text("✅ OK!")


def init_notify_schedule(application:Application):
    job_queue = application.job_queue
    chat_ids = db.getall()
    for chat_id in chat_ids:
        if not db.get(chat_id).get("is_daily_notify"):
            continue
        job_queue.run_daily(notify_lunch,
                            time=datetime.time(10,30,0, tzinfo=pytz.timezone('Asia/Ho_Chi_Minh')),
                            days=tuple(range(1,6)), # ignore weekends
                            chat_id=chat_id,
                            name=f"notify_lunch_{str(chat_id)}"
                            )


def main() -> None:
    token = None
    try:
        token = open("token.txt").read().strip()
    except:
        print("Fail to load token")
        exit(1)

    application = Application.builder().token(token).build()
    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("order", order_command))
    application.add_handler(CommandHandler("retract", retract_order_command))
    application.add_handler(CommandHandler("close", close_command))
    application.add_handler(CommandHandler("open", open_command))
    application.add_handler(CommandHandler("notify", notify_command))

    # 
    init_notify_schedule(application)

    # Run the bot until the user presses Ctrl-C
    application.run_polling()


if __name__ == "__main__":
    main()
