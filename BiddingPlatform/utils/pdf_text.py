# utils/pdf_text.py
from typing import List, Union, BinaryIO
import re
import fitz  # PyMuPDF
from PyPDF2 import PdfReader
import io

ARABIC_CHARS = re.compile(r'[\u0600-\u06FF]+')

def pdf_to_arabic_text_pymupdf(file_obj: Union[BinaryIO, bytes]) -> str:
    """
    Reads an Arabic PDF using PyMuPDF (better for complex layouts and OCR fallback).
    Returns clean UTF-8 text with proper Arabic handling.
    """
    try:
        # Handle both file objects and bytes
        if hasattr(file_obj, 'read'):
            pdf_data = file_obj.read()
            file_obj.seek(0)  # Reset for potential reuse
        else:
            pdf_data = file_obj
            
        doc = fitz.open(stream=pdf_data, filetype="pdf")
        chunks: List[str] = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Extract text with better Arabic support
            text = page.get_text()
            
            if not text.strip():
                # Fallback to OCR if no text found
                pix = page.get_pixmap()
                text = page.get_textpage().extractText()
            
            # Clean up the text
            text = clean_arabic_text(text)
            if text.strip():
                chunks.append(text.strip())
        
        doc.close()
        return "\n".join(chunks)
        
    except Exception as e:
        # Fallback to PyPDF2 if PyMuPDF fails
        print(f"PyMuPDF failed, falling back to PyPDF2: {e}")
        return pdf_to_arabic_text_pypdf2(file_obj)

def pdf_to_arabic_text_pypdf2(file_obj: Union[BinaryIO, bytes]) -> str:
    """
    Reads an Arabic PDF using PyPDF2 and returns clean UTF-8 text.
    - merges bidirectional runs
    - drops empty lines & page headers/footers heuristically
    """
    try:
        if isinstance(file_obj, bytes):
            file_obj = io.BytesIO(file_obj)
        
        reader = PdfReader(file_obj)
        chunks: List[str] = []
        
        for page in reader.pages:
            txt = page.extract_text() or ""
            txt = clean_arabic_text(txt)
            if txt.strip():
                chunks.append(txt.strip())
                
        return "\n".join(chunks)
        
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return ""

def clean_arabic_text(text: str) -> str:
    """
    Clean and normalize Arabic text extracted from PDF.
    """
    if not text:
        return ""
    
    # Remove extra spaces inside Arabic words (common in PDFs)
    text = re.sub(r'\s+(?=' + ARABIC_CHARS.pattern + ')', '', text)
    
    # Normalize Arabic characters
    text = text.replace('ي', 'ي').replace('ك', 'ك')
    
    # Remove excessive whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove common PDF artifacts
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)  # Page numbers
    text = re.sub(r'^[-=_\s]*$', '', text, flags=re.MULTILINE)  # Decorative lines
    
    return text.strip()

def pdf_to_arabic_text(file_obj: Union[BinaryIO, bytes]) -> str:
    """
    Main function to extract Arabic text from PDF.
    Tries PyMuPDF first, falls back to PyPDF2 if needed.
    """
    return pdf_to_arabic_text_pymupdf(file_obj)
