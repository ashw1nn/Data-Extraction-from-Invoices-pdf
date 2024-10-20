from datetime import datetime
import re
import os
import logging

class Crosschecker:
    def __init__(self, sale_summary: dict, file_name: str, verbose: int = 0) -> None:
        self.sale_summary = sale_summary
        self.confidence_score = 0
        self.score = 0
        self.max_score = 100
        self.total_items = len(sale_summary["sale_info"]["items"])
        self.weighted_scores = {
            "invoice_num": 10,
            "date_checks": 20,
            "total_amount": 50,
            "tax_percentage": 10,
            "quantity": 10
        }
        self.verbose = verbose
        self.logger = logging.getLogger(file_name+".log")

        log_path = os.path.join("logs", file_name+".log")
        if not self.logger.hasHandlers():  # Avoid adding multiple handlers if already configured
            file_handler = logging.FileHandler(log_path, mode='a')
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(file_handler)
            self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = True 

    
    def log(self, message: str) -> None:
        if self.verbose:
            self.logger.debug(message)
    
    def calculate_confidence_score(self) -> float:
        invoice_number = self.sale_summary["invoice_number"]
        self.log(f"Checking invoice number: {invoice_number}")
        
        # Invoice Number Pattern Check
        try:
            if re.match(r"^INV-\d*$", invoice_number):
                self.score += self.weighted_scores["invoice_num"]
                self.log("Invoice number passed pattern check")
            else:
                self.log("Invoice number failed pattern check")
        except TypeError:
            self.log("Invoice number failed pattern check")

        # Date checks
        try:
            invoice_date = datetime.strptime(self.sale_summary["invoice_date"], "%d %b %Y")
            self.log(f"Parsed invoice date: {invoice_date}")
        except ValueError:
            self.log("Failed to parse invoice date")
        except TypeError:
            self.log("Failed to parse invoice date")

        try:
            due_date = datetime.strptime(self.sale_summary["due_date"], "%d %b %Y")
            self.log(f"Parsed due date: {due_date}")
        except ValueError:
            self.log("Failed to parse due date")
        except TypeError:
            self.log("Failed to parse due date")

        # Date Logic Check
        try:
            if 'invoice_date' in locals():
                self.score += self.weighted_scores["date_checks"]*0.45
                self.log("Invoice date check passed")
            if 'due_date' in locals():
                self.score += self.weighted_scores["date_checks"]*0.45
                self.log("Due date check passed")
            if 'invoice_date' in locals() and 'due_date' in locals() and due_date >= invoice_date:
                self.score += self.weighted_scores["date_checks"]*0.1
                self.log("Date logic check passed")
            else:
                self.log("Date logic check failed")
                self.log("Either wrong read or due date is before invoice date!")
        except TypeError:
            self.log("Date logic check failed")

        sale_info = self.sale_summary["sale_info"]

        # Total Amount Consistency Check
        total_amount = self.sale_summary["total_amount"]
        calculated_total = sum(sale_info["amount"])
        self.log(f"Calculated total amount: {calculated_total}, expected: {total_amount}")
        try:
            if abs(calculated_total - total_amount) < 1: # Rounding off(Ceil) is done in reality, I have taken a diff of Rs.1
                self.score += self.weighted_scores["total_amount"]
                self.log("Total amount consistency check passed")
            else:
                adjustment = (1 - (sale_info["amount"].count(None) / len(sale_info["amount"])))
                self.score += adjustment * self.weighted_scores["total_amount"]
                self.log(f"Total amount consistency check failed, adjusted score: {adjustment}")
        except TypeError:
            self.log("Total amount consistency check failed")

        if self.total_items > 0:
            # Tax Percentage Check
            tax_percentages = sale_info["tax_percentage"]
            valid_tax_percentages = [0, 5, 12, 18, 28]
            valid_tax_counts = 0
            for tax_per in tax_percentages:
                if tax_per in valid_tax_percentages:
                    valid_tax_counts += 1
            self.score += (valid_tax_counts/len(tax_percentages)) * self.weighted_scores["tax_percentage"]
            self.log(f"Valid tax percentage count: {valid_tax_counts}")

            # Quantity Check
            quantities = sale_info["quantity"]
            valid_quantities = 0
            for quantity in quantities:
                if (quantity is not None) and (re.match(r"^\d+\s*[A-Z]*$", quantity)):
                    valid_quantities += 1
            self.score += (valid_quantities/len(quantities)) * self.weighted_scores["quantity"]
            self.log(f"Valid quantity count: {valid_quantities}")
            
        self.confidence_score = self.score / self.max_score
        self.logger.info(f"Final confidence score: {self.confidence_score}")
        return round(self.confidence_score, 4)
