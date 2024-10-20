import pandas as pd
import PyPDF2
import re
from pathlib import Path
import logging
from pdf2image import convert_from_path
import cv2
import numpy as np
import pytesseract
from PIL import Image

def convert_to_float(value):
    try:
        # Remove commas and convert to float
        return float(value.replace(',', ''))
    except Exception as e:
        # Return None if the conversion fails
        return None

class Extracter:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)

        # Create a logger with a unique name for each file (based on the file name)
        self.logger = logging.getLogger(file_path.stem)
        self.logger.setLevel(logging.DEBUG)

        # Prevent this logger's messages from propagating to the root logger
        self.logger.propagate = False

        # If logger already has handlers, remove them (to avoid duplicates)
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # Create a file handler for logging to a file in overwrite mode ('w')
        log_file = log_dir / f'{file_path.stem}.log'
        file_handler = logging.FileHandler(log_file, mode='w')  # Overwrite if file exists
        file_handler.setLevel(logging.DEBUG)

        # Create a log message format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # Add the file handler to the logger
        self.logger.addHandler(file_handler)

        # Test log to ensure everything works
        self.logger.debug("Logger initialized and logging to file.")
        self.logger.info(f'Initializing PDF reader for file: {file_path}')

    def preprocess_image(self, image):
        # Convert to grayscale
        gray = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
        # Apply thresholding
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        return Image.fromarray(thresh)

    def useOCR(self, pdf_path) -> str:
        images = convert_from_path(pdf_path)
        preprocessed_images = [self.preprocess_image(image) for image in images]
        extracted_text = ""
        for image in preprocessed_images:
            text = pytesseract.image_to_string(image)
            extracted_text += text + "\n"

        return extracted_text

    def extract_item_details(self, match, cleaned_matches, i):
        if match is not None:
            extract = match.group(1)
            cleaned_matches[i] = re.sub(rf"{re.escape(extract)}(?=$)", "", cleaned_matches[i], count=1).strip()
            return extract
        return None

    def extract_basic_info(self, page_text, pattern):
        match = re.search(pattern, page_text)
        if match:
            return match.group(1)
        return None

    def extract(self) -> dict:
        # Initialize the PDF reader
        try:
            self.pdf_reader = PyPDF2.PdfReader(str(self.file_path), strict=True)
            self.logger.info('PDF reader initialized successfully.')
        except Exception as e:
            self.logger.error(f'Error initializing PDF reader: {e}')
            raise
        
        # Check if the PDF contains only 1 page
        if len(self.pdf_reader.pages) > 1:
            self.logger.error("More than one page found!!")
            raise ValueError("More than one page found!!")
        self.logger.info("PDF contains only 1 page, Extracting data from PDF...")
        
        # Check if the PDF contains any text
        page_text = self.pdf_reader.pages[0].extract_text()
        if page_text == "":
            page_text = self.useOCR(pdf_path=str(self.file_path))
        if page_text == "":
            self.logger.error("No text found in PDF!!")
            raise RuntimeError("No text found in PDF!!")
        self.logger.debug(page_text)

        # Extract basic data
        invoice_number = self.extract_basic_info(page_text, r"Invoice #:\s*(\S+)")
        invoice_date = self.extract_basic_info(page_text, r"Invoice Date:\s*(\d{1,2} \w+ \d{4})")
        due_date = self.extract_basic_info(page_text, r"Due Date:\s*(\d{1,2} \w+ \d{4})")
        gstin = self.extract_basic_info(page_text, r"GSTIN\s*([\w\d]+)")
        total_amount = convert_to_float(self.extract_basic_info(page_text, r"Total\s*₹([\d,\.]+)"))
        place_of_supply = self.extract_basic_info(page_text, r"(\d{2}-[A-Z]*\s*[A-Z]*)")
        igst = re.search(r"igst", page_text, re.IGNORECASE)
        if igst:
            has_igst = True
        else:
            has_igst = False

        self.logger.info(f"Extracted basic data from PDF")

        self.logger.debug(f"Invoice Number: {invoice_number}")
        self.logger.debug(f"Invoice Date: {invoice_date}")
        self.logger.debug(f"Due Date: {due_date}")
        self.logger.debug(f"GSTIN: {gstin}")
        self.logger.debug(f"Total Amount: ₹{total_amount}")
        self.logger.debug(f"Place of Supply: {place_of_supply}")

        # pattern = r"#Item Rate / Item QtyTaxable ValueTax AmountAmount(.*?)Taxable Amount"
        pattern = r"(?<=Amount\n)(.*?)Taxable Amount"
        items = re.search(pattern, page_text, re.DOTALL)

        if items:
            items_str = items.group(1).strip()
            self.logger.debug(items_str)
        else:
            self.logger.warning("Items not found for this file!!")


        pattern = r"(\d[a-zA-Z][\s\S]+?)(?=\n\d+[a-zA-Z]|\Z)"
        matches = re.findall(pattern, items_str, re.MULTILINE)
        cleaned_matches = [re.sub(r'[\r\n]+', ' ', match) for match in matches]

        for i, match in enumerate(cleaned_matches):
            cleaned_matches[i] = match[1:].strip()

        sale_info = {
        'items': [],
        'rate': [],
        'cost_price': [],
        'discount': [],
        'quantity': [],
        'taxable_value': [],
        'tax_amount': [],
        'tax_percentage': [],
        'amount': [],
        'sgst_amount': [],
        'cgst_amount': [],
        'igst_amount': [],
        'sgst_rate': [],
        'cgst_rate': [],
        'igst_rate': [],
        }

        self.logger.info("Extracting data from list of items purchased...")

        for i in range(len(cleaned_matches)):
            self.logger.debug(f"{cleaned_matches[i]}")
            match = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})(?=$)", cleaned_matches[i])
            Amount = self.extract_item_details(match, cleaned_matches, i)
            sale_info['amount'].append(convert_to_float(Amount))
            
            match = re.search(r"(?<=\.\d{2})(\d{1,3}(?:,\d{2,3})*\.\d{2}\s\(\d{1,2}%\))(?=$)", cleaned_matches[i])
            Tax_amount = self.extract_item_details(match, cleaned_matches, i)
            match = re.search(r"\((\d{1,2}%)\)(?=$)", Tax_amount)
            Tax_percentage = convert_to_float(match.group(1).replace("%", ""))
            sale_info['tax_percentage'].append(Tax_percentage)
            Tax_amount = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})", Tax_amount).group(1)
            sale_info['tax_amount'].append(convert_to_float(Tax_amount))

            match = re.search(r"(?<=\w)(\d{1,3}(?:,\d{2,3})*\.\d{2})(?=$)", cleaned_matches[i])
            Taxable_value = self.extract_item_details(match, cleaned_matches, i)
            sale_info['taxable_value'].append(convert_to_float(Taxable_value))
            
            match = re.search(r"(\d+|\d+\s[A-Z]+)(?=$)", cleaned_matches[i])
            Quantity = self.extract_item_details(match, cleaned_matches, i)
            sale_info['quantity'].append(Quantity)

            match = re.search(r"(\(-\d{1,2}%\)|\(-\d{1,2}\.\d{1,2}%\))(?=$)", cleaned_matches[i])
            Discount = self.extract_item_details(match, cleaned_matches, i)
            Discount = Discount.strip('()') if Discount is not None else None
            sale_info['discount'].append(Discount)

            match = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})(?=$)", cleaned_matches[i])
            Cost_price = self.extract_item_details(match, cleaned_matches, i)
            sale_info['cost_price'].append(convert_to_float(Cost_price))

            match = re.search(r"(\d{1,3}(?:,\d{2,3})*\.\d{2})(?=$)", cleaned_matches[i])
            Rate = self.extract_item_details(match, cleaned_matches, i)
            if Rate is None:
                Rate = Cost_price
            sale_info['rate'].append(convert_to_float(Rate))

            Item = cleaned_matches[i]
            sale_info['items'].append(Item)


            if has_igst:
                sale_info['sgst_amount'].append(None)
                sale_info['cgst_amount'].append(None)
                sale_info['igst_amount'].append(convert_to_float(Tax_amount))
                sale_info['sgst_rate'].append(None)
                sale_info['cgst_rate'].append(None)
                sale_info['igst_rate'].append(Tax_percentage)
            else:
                sale_info['sgst_amount'].append(convert_to_float(Tax_amount) / 2)
                sale_info['cgst_amount'].append(convert_to_float(Tax_amount) / 2)
                sale_info['igst_amount'].append(None)
                sale_info['sgst_rate'].append(Tax_percentage)
                sale_info['cgst_rate'].append(Tax_percentage)
                sale_info['igst_rate'].append(None)

            self.logger.debug(f"Amount:{Amount}")
            self.logger.debug(f"Tax Pecentage:{Tax_percentage}")
            self.logger.debug(f"Tax Amount:{Tax_amount}")
            self.logger.debug(f"Taxable Value:{Taxable_value}")
            self.logger.debug(f"Quantity:{Quantity}")
            self.logger.debug(f"Discount:{Discount}")
            self.logger.debug(f"Cost Price:{Cost_price}")
            self.logger.debug(f"Rate:{Rate}")
            self.logger.debug(f"Item:{Item}")
            self.logger.debug(f"SGST Amount:{sale_info['sgst_amount'][i]}")
            self.logger.debug(f"CGST Amount:{sale_info['cgst_amount'][i]}")
            self.logger.debug(f"IGST Amount:{sale_info['igst_amount'][i]}")
            self.logger.debug(f"SGST Rate:{sale_info['sgst_rate'][i]}")
            self.logger.debug(f"CGST Rate:{sale_info['cgst_rate'][i]}")
            self.logger.debug(f"IGST Rate:{sale_info['igst_rate'][i]}")
            self.logger.debug("--------------------------")



        sale_summary = {
            'invoice_number': invoice_number,
            'invoice_date': invoice_date,
            'due_date': due_date,
            'gstin': gstin,
            'place_of_supply': place_of_supply,
            'total_amount': total_amount,
            'sale_info': sale_info
        }

        self.logger.info("Extracted data from list of items purchased.")

        return sale_summary
