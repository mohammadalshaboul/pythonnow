import telebot
from telebot import types
from fpdf import FPDF
from PIL import Image, ImageEnhance
import arabic_reshaper
from pyarabic.araby import tokenize
import os
import re

warnings.filterwarnings("ignore", category=UserWarning, module="fpdf")

TOKEN = '8036700201:AAGpqoPxO2FcxDsgs38ZIqwMTaVTcqHY0Ko'
bot = telebot.TeleBot(TOKEN)

user_states = {}

class PDF(FPDF):
    def __init__(self):
        super().__init__()
        try:
            self.add_font('Amiri', '', '/storage/emulated/0/potpaython/Amiri-BoldItalic.ttf', uni=True)
            self.set_font('Amiri', size=14)
        except Exception as e:
            print(f"Error loading font: {e}")
        self.set_auto_page_break(auto=True, margin=15)

    def add_text(self, text):
        self.add_page()
        reshaped_lines = []
        for line in text.split('\n'):
            tokens = tokenize(line)
            reshaped_tokens = [arabic_reshaper.reshape(token) for token in tokens]
            visual_line = ' '.join(reshaped_tokens)[::-1]
            reshaped_lines.append(visual_line)
        final_text = '\n'.join(reshaped_lines)
        self.multi_cell(0, 10, final_text, align='R')

    def add_text_english(self, text):
        self.add_page()
        self.set_font('Amiri', size=14)
        self.multi_cell(0, 10, text, align='L')

    def add_image_to_pdf(self, image_path):
        self.add_page()
        self.image(image_path, x=10, y=10, w=190)

def create_pdf_from_text(text_arabic, text_english, filename):
    pdf = PDF()
    if text_arabic:
        pdf.add_text(text_arabic)
    if text_english:
        pdf.add_text_english(text_english)
    pdf.output(filename)

def enhance_image_once(image_path):
    try:
        img = Image.open(image_path)
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(2.0)
        return img
    except Exception as e:
        print(f"Error enhancing image {image_path}: {e}")
        return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_states[message.chat.id] = {"mode": None, "images": []}
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("تحويل النص العربي + الإنجليزي إلى PDF", "أرسل صورة")
    bot.send_message(message.chat.id, "أهلاً بك! اختر من الأزرار أدناه.", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text in ["تحويل النص العربي + الإنجليزي إلى PDF", "أرسل صورة"])
def choose_mode(message):
    chat_id = message.chat.id
    user_states[chat_id] = {"mode": None, "images": []}
    if message.text == "تحويل النص العربي + الإنجليزي إلى PDF":
        user_states[chat_id]["mode"] = "text"
        bot.send_message(chat_id, "أرسل النص العربي والإنجليزي (بدون رموز خاصة).")
    elif message.text == "أرسل صورة":
        user_states[chat_id]["mode"] = "images"
        bot.send_message(chat_id, "أرسل صورة أو أكثر. وعندما تنتهي، أرسل 'تم'.")

@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    mode = user_states.get(chat_id, {}).get("mode")

    if message.text == "تم" and mode == "images":
        images = user_states[chat_id]["images"]
        if not images:
            bot.send_message(chat_id, "لم ترسل أي صور بعد.")
            return

        pdf = PDF()
        for img_path in images:
            pdf.add_image_to_pdf(img_path)
            os.remove(img_path)
        pdf_path = "images_output.pdf"
        pdf.output(pdf_path)

        with open(pdf_path, "rb") as f:
            bot.send_document(chat_id, f)
        os.remove(pdf_path)
        bot.send_message(chat_id, "تم تحويل الصور إلى PDF.")
        user_states[chat_id]["images"] = []
        return

    if mode == "text":
        if re.search(r"[£\€\√\π\^\©\®\™\§\$\#\~]", message.text):
            bot.send_message(chat_id, "يرجى عدم استخدام رموز خاصة.")
            return

        arabic_text = ""
        english_text = ""
        for line in message.text.splitlines():
            if any(ord(c) > 128 for c in line):
                arabic_text += line + "\n"
            else:
                english_text += line + "\n"

        pdf_path = "text_output.pdf"
        create_pdf_from_text(arabic_text, english_text, pdf_path)

        with open(pdf_path, "rb") as f:
            bot.send_document(chat_id, f)
        os.remove(pdf_path)
        bot.send_message(chat_id, "تم تحويل النص إلى PDF.")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    mode = user_states.get(chat_id, {}).get("mode")
    if mode != "images":
        bot.send_message(chat_id, "يرجى اختيار 'أرسل صورة' أولاً.")
        return

    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    img_path = f"img_{file_id}.jpg"
    with open(img_path, 'wb') as f:
        f.write(downloaded_file)

    enhanced = enhance_image_once(img_path)
    if enhanced:
        enhanced_path = f"enhanced_{file_id}.jpg"
        enhanced.save(enhanced_path)
        os.remove(img_path)
        img_path = enhanced_path

    user_states[chat_id]["images"].append(img_path)
    bot.send_message(chat_id, "تم حفظ الصورة. أرسل 'تم' عندما تنتهي.")

bot.polling(none_stop=True)