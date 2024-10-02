import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pdf2image import convert_from_path
import pytesseract

pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))

# Укажите путь к Tesseract, если необходимо
pytesseract.pytesseract.tesseract_cmd = r'D:\Programms\Tesseract-OCR\tesseract.exe'

def extract_text_from_image(image):
    """Распознавание текста на изображении с помощью Tesseract OCR"""
    try:
        return pytesseract.image_to_string(image, lang='rus+eng')
    except Exception as e:
        print(f"Error extracting text from image: {str(e)}")
        return ""

def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            text_pages = [page.extract_text() for page in reader.pages]

            # Если текст не найден на страницах, возможно это изображение
            for i, text in enumerate(text_pages):
                if not text.strip():
                    # Укажите путь к Poppler, если это необходимо
                    images = convert_from_path(pdf_path, first_page=i+1, last_page=i+1, poppler_path=r'D:\Programms\Poppler\Library\bin')
                    if images:
                        text_pages[i] = extract_text_from_image(images[0])
                    else:
                        print(f"Failed to convert page {i+1} to image in {pdf_path}")

            return text_pages
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {str(e)}")
        return []

def find_headers(text_pages):
    """Поиск заголовков в страницах текста"""
    headers = []
    header_pattern = re.compile(r'^(?:\d+(?:\.\d+)*\.?\s*)?([А-ЯA-Z][А-Яа-яA-Za-z\s]{2,}(?:[.:]|\n|$))', re.MULTILINE)
    for page_num, page_text in enumerate(text_pages, 1):
        lines = page_text.split('\n')
        for idx, line in enumerate(lines):
            line = line.strip()
            if (
                5 <= len(line) <= 100 and
                not line.isdigit() and
                not re.search(r'^\d+\.', line) and
                re.match(r'^[А-ЯA-Z]', line) and
                not re.search(r'[a-z]', line) and
                len(line.split()) >= 2
            ):
                # Проверка на позицию строки (например, первые 5 строк на странице)
                if idx < 5:
                    headers.append((line, page_num))
    return headers

def create_toc(headers):
    """Создание оглавления на основе заголовков"""
    toc = []
    for header, page in headers:
        header = re.sub(r'\s+', ' ', header).strip()  # Удаляем лишние пробелы
        toc.append(f"{header[:70].ljust(75, '.')} {page}")
    return "\n".join(toc)

def add_toc_to_pdf(input_path, output_path, toc):
    """Добавление оглавления в PDF файл"""
    reader = PdfReader(input_path)
    writer = PdfWriter()

    # Создаем PDF с оглавлением
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.setFont("DejaVuSans", 16)
    can.drawString(250, 750, "Оглавление")
    can.setFont("DejaVuSans", 10)
    y = 720
    for line in toc.split('\n'):
        can.drawString(50, y, line)
        y -= 12
        if y < 50:
            can.showPage()
            can.setFont("DejaVuSans", 10)
            y = 750
    can.save()

    # Вставляем оглавление перед основным содержимым
    packet.seek(0)
    new_pdf = PdfReader(packet)

    for page in new_pdf.pages:
        writer.add_page(page)
    for page in reader.pages:
        writer.add_page(page)

    # Сохраняем новый PDF
    with open(output_path, "wb") as output_file:
        writer.write(output_file)

def process_file(input_path, output_path):
    """Обработка одного PDF файла: извлечение текста, создание оглавления и сохранение с добавлением оглавления"""
    try:
        print(f"Processing {input_path}...")
        text_pages = extract_text_from_pdf(input_path)
        if text_pages:
            headers = find_headers(text_pages)
            if headers:
                toc = create_toc(headers)
                add_toc_to_pdf(input_path, output_path, toc)
                print(f"Saved processed file to {output_path}")
                return True
            else:
                print(f"No headers found in {input_path}, skipping TOC creation.")
        else:
            print(f"Skipping {input_path} due to extraction error")
        return False
    except Exception as e:
        print(f"Error processing {input_path}: {str(e)}")
        return False

def process_directory(input_dir, output_dir):
    """Обработка всех PDF файлов в заданной директории"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    pdf_files = [os.path.join(root, file)
                 for root, _, files in os.walk(input_dir)
                 for file in files if file.endswith('.pdf')]

    with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
        futures = []
        for input_path in pdf_files:
            relative_path = os.path.relpath(input_path, input_dir)
            output_path = os.path.join(output_dir, relative_path)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            futures.append(executor.submit(process_file, input_path, output_path))

        for future in as_completed(futures):
            future.result()

# Пример использования
input_directory = "train"
output_directory = "output"
process_directory(input_directory, output_directory)