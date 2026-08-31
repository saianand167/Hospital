import os
from PIL import Image, ImageDraw, ImageFont

def create_text_image(filename: str, text_lines: list, is_handwritten: bool = False):
    # Create a white canvas (simulating a paper document scan)
    width, height = 800, 1000
    img = Image.new('RGB', (width, height), color='#FFFFFF')
    draw = ImageDraw.Draw(img)

    # Use default font
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    # Margins and line height
    x_margin = 60
    y_margin = 60
    line_height = 30

    # Draw clinical header
    header_text = "MEDIKIOSK DIGITAL INTAKE PROTOTYPE"
    draw.text((x_margin, y_margin), header_text, fill='#3b82f6')
    draw.line((x_margin, y_margin + 20, width - x_margin, y_margin + 20), fill='#d1d5db', width=2)
    
    y = y_margin + 40

    # Draw document title
    title = filename.split('.')[0].upper().replace('_', ' ')
    draw.text((x_margin, y), f"DOCUMENT TYPE: {title}", fill='#1e293b')
    y += 50

    # Draw each text line
    for line in text_lines:
        if line == "---":
            draw.line((x_margin, y + 10, width - x_margin, y + 10), fill='#e5e7eb', width=1)
            y += 25
        else:
            # Emulate "handwritten" prescription layout/slurs slightly or just output clean text
            fill_color = '#1f2937' if not is_handwritten else '#047857'
            draw.text((x_margin, y), line, fill=fill_color)
            y += line_height

    # Save to path
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    img.save(filename)
    print(f"Generated synthetic image: {filename}")

def main():
    dest_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Lab Report
    lab_lines = [
        "METROPOLIS LABS - DIAGNOSTICS",
        "Patient Name: Ramesh Kumar",
        "Age / Gender: 45 Y / Male",
        "Date: 2026-08-15",
        "---",
        "Test Name                   Observed Value      Reference Range     Unit",
        "Hemoglobin                  10.2                12.0 - 16.0         g/dL",
        "White Blood Cells (WBC)     7500                4000 - 11000        /uL",
        "Platelets                   250000              150000 - 450000     /uL",
        "Random Blood Sugar          145                 70 - 140            mg/dL",
        "---",
        "Verification Status: Auto-generated raw records"
    ]
    create_text_image(os.path.join(dest_dir, "lab_report.png"), lab_lines)

    # 2. Printed Prescription
    printed_rx_lines = [
        "Apollo Clinics",
        "Dr. A. K. Sharma, MD",
        "Reg No: 54321-A",
        "Date: 2026-08-20",
        "---",
        "Rx:",
        "1. Tab Metformin 500 mg - 1-0-1 - Oral - After Food - 30 Days",
        "2. Tab Atorvastatin 10 mg - 0-0-1 - Oral - Bedtime - 15 Days",
        "---",
        "Signature: Dr. A. K. Sharma (Digitally Signed)"
    ]
    create_text_image(os.path.join(dest_dir, "prescription_printed.png"), printed_rx_lines)

    # 3. Handwritten Prescription
    handwritten_rx_lines = [
        "Max Health Care",
        "Dr. Sunita Rao",
        "Date: 2026-08-22",
        "---",
        "Rx",
        "Mtfrmn 500 - 1-0-1 - 5 days",
        "Amlodpn 5mg - 0-1-0 - 10 d",
        "---",
        "Note: Low confidence OCR transcription expected due to doctor's handwriting."
    ]
    create_text_image(os.path.join(dest_dir, "prescription_handwritten.png"), handwritten_rx_lines, is_handwritten=True)

    # 4. Discharge Summary
    discharge_lines = [
        "FORTIS HOSPITALS DELHI",
        "DISCHARGE SUMMARY",
        "---",
        "Patient: Sunita Sen",
        "Admission Date: 2026-08-01",
        "Discharge Date: 2026-08-07",
        "---",
        "Diagnosis: Acute Appendicitis",
        "Procedure: Laparoscopic Appendectomy on 2026-08-02",
        "Hospital Course: Uneventful recovery. Patient was mobilized on Day 2 post-op.",
        "Discharge Medications: Tab Paracetamol 650mg - PRN for pain, Tab Pantocid 40mg - once daily before food.",
        "Follow-up: Visit OPD after 7 days for suture removal."
    ]
    create_text_image(os.path.join(dest_dir, "discharge_summary.png"), discharge_lines)

    # 5. Radiology Report
    radiology_lines = [
        "CHANDIGARH SCANNING CENTRE",
        "DEPARTMENT OF RADIOLOGY",
        "---",
        "Modality: Chest X-Ray PA View",
        "Study Date: 2026-08-10",
        "---",
        "Findings: Lungs are clear. No focal consolidation, pleural effusion, or pneumothorax.",
        "Cardiac silhouette is normal in size and configuration.",
        "---",
        "Impression: Normal study of the chest."
    ]
    create_text_image(os.path.join(dest_dir, "radiology_report.png"), radiology_lines)

if __name__ == "__main__":
    main()
