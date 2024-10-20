# Usuage
First, install the required packages to your environment using the following commad:
- pip install -r requirements.txt

Then, run the code using,
- python3 main.py --input-dir /path/to/your/input_directory --output-dir /path/to/your/output_directory

Make sure that your input and output directories already exists. The code defaults to the following:
- input-dir = Jan to May
- output-dir = extracts

# Documentation
## outputs.csv
This file resembles the required csv format file given in the question. Comprehensive report of the invoices. If possible refer the jsons in the extract folder.
The rates might be slightly deceiving, since different items have different tax rates, I have found the final tax rate by dividing the total tax amount by the taxable value and reported the percentage.

## report.txt
Refer this file for knowing about the accuracies obtained and the erroneous data for all the respective input files.

## extracts/ directory
This directory contains the detailed jsons corresponding to every file given as input.

## logs/ directory
As the name suggests this contains the detailed logs for every file stating everything the extracter does.

## extract.py
### Approach 1
This contains the Extracter class that I have used to parse and scrape information from the input PDFs.

If the pdf is structured, PyPDF converts the PDF into a big string, from which I have extracted the contents.
If there are scanned images/mixed type PDFs then pytesseract takes over and gets the string from OCR module.
After which, I have used "regex" to find out similar pattern pertaining to the required fields, (like invoice number, date, etc.)

This approach works totally using open-source libraries and hence, it is the most cost-effective approach. 
I have achieved 98-100% accuracies on the given test data.

### Approach 2
Using LLMs,
I tried using the Donut model which was supposed to work with image as well as structured PDFs. I tried this approach and the accuracy scores turned out to be very bad.
I belive using more training data can helpo fine-tuning the model after which the accuracy can be improved.

## accuracy_check.py
I have created a confidence score that tells on how much we can trust the extracted data.
I checked the following and each were given a set of weighted score:
 - The INV no. format, (10%)
 - The date formats, (18% - 2 dates)
 - Is due date later than Invoice date?, (2%)
 - Is the tax percentage valid tax percent or not? (10%)
 - Does each item in the bill have a quantity entry? (10%)
 - Does the total of individual items sum up to the actual extracted total from the bill? (50%)

## main.py
This file uses the above mentioned tools and outputs the report.txt, outputs.csv and updates the extracts/ and logs/ directory with the extracted jsons.



