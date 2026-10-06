import csv

HEADER = ["customer", "subtotal", "discount", "tax", "total", "due"]


def export_csv(invoices, path):
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        for invoice in invoices:
            writer.writerow([
                invoice.customer,
                f"{invoice.subtotal:.2f}",
                f"{invoice.discount:.2f}",
                f"{invoice.tax:.2f}",
                f"{invoice.total:.2f}",
                invoice.due.isoformat(),
            ])
