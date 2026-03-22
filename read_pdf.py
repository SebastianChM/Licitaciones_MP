import os

try:
    import PyPDF2
    with open(r"C:\Users\Sebastian\Licitaciones_MP\Professionalization Review of “Licitaciones Mercado Público” Automation System.pdf", "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    with open(r"C:\Users\Sebastian\Licitaciones_MP\pdf_output.txt", "w", encoding="utf-8") as out:
        out.write(text)
    print("Success")
except ImportError:
    print("PyPDF2 not installed. Trying fitz...")
    try:
        import fitz
        doc = fitz.open(r"C:\Users\Sebastian\Licitaciones_MP\Professionalization Review of “Licitaciones Mercado Público” Automation System.pdf")
        text = ""
        for page in doc:
            text += page.get_text() + "\n"
        with open(r"C:\Users\Sebastian\Licitaciones_MP\pdf_output.txt", "w", encoding="utf-8") as out:
            out.write(text)
        print("Success")
    except Exception as e2:
        print("Error with fitz:", e2)
except Exception as e:
    print("Error:", e)
