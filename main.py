import argparse
import extract
import accuracy_check
import pandas as pd
import json
from pathlib import Path
from datetime import datetime
import logging
import sys


def setup_logging():
    # Configure logging to a file, disabling the default console output
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        # filename='main.log',  # Log file for the main script
        filemode='w'  # Overwrite the log file each time the script runs
    )

def process_pdf_files(input_dir: Path, output_dir: Path):
    # Create output directories if they don't exist
    sale_info_csv_dir = output_dir / 'sale_info_csv'
    sale_info_csv_dir.mkdir(parents=True, exist_ok=True)
    sale_info_json_dir = output_dir / 'sale_info_json'
    sale_info_json_dir.mkdir(parents=True, exist_ok=True)

    error_files = []
    accuracies = []
    required_entries = []

    report = {
        'error_files': error_files,
        'accuracies': accuracies
    }

    # Process each PDF file in the input directory
    for file_path in input_dir.glob('*.pdf'):
        logging.info(f"Processing {file_path.name}")
        extracter = extract.Extracter(file_path=file_path)
        try:
            sale_summary = extracter.extract()
        except ValueError as e:
            error_message = f"Error processing {file_path.name}: {e}"
            logging.error(error_message)
            error_files.append(error_message)
            continue
        except RuntimeError as e:
            error_message = f"No text found in {file_path.name}: {e}"
            logging.error(error_message)
            error_files.append(error_message)
            continue
        except Exception as e:
            error_message = f"An unexpected error occurred with {file_path.name}: {e}"
            logging.error(error_message)
            error_files.append(error_message)
            continue

        # Accuracy check
        checker = accuracy_check.Crosschecker(sale_summary=sale_summary, file_name=file_path.stem, verbose=1)
        accuracy = checker.calculate_confidence_score() * 100
        accuracies.append((file_path.name, accuracy))
        if accuracy < 90:
            error_message = f"Accuracy below 90% for {file_path.name}"
            logging.warning(error_message)
            error_files.append(error_message)
            continue

        # Write the extracted data to JSON
        json_output_path = sale_info_json_dir / f'{file_path.stem}.json'
        with open(json_output_path, 'w') as f:
            json.dump(sale_summary, f, indent=4)

        # Prepare required fields for CSV output and add to the list
        required = {
            'taxable_value': round(sum(x for x in sale_summary['sale_info']['taxable_value'] if x is not None), 2),
            'sgst_amount': round(sum(x for x in sale_summary['sale_info']['sgst_amount'] if x is not None), 2),
            'cgst_amount': round(sum(x for x in sale_summary['sale_info']['cgst_amount'] if x is not None), 2),
            'igst_amount': round(sum(x for x in sale_summary['sale_info']['igst_amount'] if x is not None), 2),
            'sgst_rate': None,
            'cgst_rate': None,
            'igst_rate': None,
            'tax_amount': round(sum(x for x in sale_summary['sale_info']['tax_amount'] if x is not None), 2),
            'tax_rate': None,
            'final_amount': sale_summary['total_amount'],
            'invoice_number': sale_summary['invoice_number'],
            'invoice_date': sale_summary['invoice_date'],
        }

        required['sgst_rate'] = round(required['sgst_amount'] / required['taxable_value'] * 100, 2)
        required['cgst_rate'] = round(required['cgst_amount'] / required['taxable_value'] * 100, 2)
        required['igst_rate'] = round(required['igst_amount'] / required['taxable_value'] * 100, 2)
        required['tax_rate'] = round(required['tax_amount'] / required['final_amount'] * 100, 2)

        required_entries.append(required)

    # Convert the list of dictionaries to a DataFrame and write to CSV
    if required_entries:
        df = pd.DataFrame(required_entries)
        csv_output_path = 'outputs.csv'
        df.to_csv(csv_output_path, index=False, mode='w', header=not Path(csv_output_path).exists())

    # Log the errors and accuracies if any
    if error_files or accuracies:
        logging.info(f"Number of errors: {len(error_files)}")
        logging.info(f"Processed {len(accuracies)} files with accuracies")
        with open("report.txt", "w") as f:
            f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write("Errors:\n")
            for item in error_files:
                f.write(f"{item}\n")
            f.write("\nAccuracies:\n")
            for file_name, acc in accuracies:
                f.write(f"{file_name}: {acc:.2f}%\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Process PDF files and extract data.")
    parser.add_argument('--input-dir', type=str, default='Jan to Mar', help='Directory of input PDF files.')
    parser.add_argument('--output-dir', type=str, default='extracts', help='Directory for output extracted data.')
    return parser.parse_args()

if __name__ == '__main__':
    setup_logging()
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Check if the input directory exists
    if not input_dir.exists() or not input_dir.is_dir():
        logging.error(f"Input directory '{input_dir}' does not exist or is not a directory.")
        sys.exit(1)

    # Process the PDF files
    process_pdf_files(input_dir, output_dir)
