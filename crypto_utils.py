import os
import zipfile
from pypdf import PdfReader, PdfWriter
from loguru import logger

def decrypt_pdf(path, password):
    """Decrypts a PDF file in-place if it is encrypted."""
    try:
        reader = PdfReader(path)
        if not reader.is_encrypted:
            logger.info(f"PDF {path} is not encrypted.")
            return True
            
        res = reader.decrypt(password)
        if not res:
            logger.error(f"Failed to decrypt {path} with provided password.")
            return False
            
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
            
        temp_path = path + ".tmp"
        with open(temp_path, "wb") as f:
            writer.write(f)
            
        os.replace(temp_path, path)
        logger.info(f"Successfully decrypted {path}")
        return True
    except Exception as e:
        logger.error(f"Error decrypting {path}: {str(e)}")
        return False

def decrypt_zip(path, password, dest_path):
    """Extracts a password-protected ZIP and renames the extracted file."""
    try:
        extract_dir = path + "_extracted"
        with zipfile.ZipFile(path) as z:
            z.extractall(extract_dir, pwd=password.encode('utf-8'))
            
        extracted_files = os.listdir(extract_dir)
        if extracted_files:
            # Assume there is only one file inside (e.g. DOOPN2693H-2026.txt)
            extracted_file_path = os.path.join(extract_dir, extracted_files[0])
            os.replace(extracted_file_path, dest_path)
        
        # Clean up
        os.rmdir(extract_dir)
        os.remove(path)
        logger.info(f"Successfully decrypted and extracted {path} to {dest_path}")
        return True
    except Exception as e:
        logger.error(f"Error decrypting ZIP {path}: {str(e)}")
        return False

def process_client_files(pan, dob, output_dir):
    """Decrypts all downloaded files for a client."""
    logger.info(f"[{pan}] Starting decryption process...")
    
    # Passwords
    dob_clean = dob.replace("/", "").replace("-", "")
    pdf_password_ais = pan.lower() + dob_clean
    traces_password = dob_clean
    
    ais_path = os.path.join(output_dir, f"{pan}_ais.pdf")
    tis_path = os.path.join(output_dir, f"{pan}_tis.pdf")
    html_path = os.path.join(output_dir, f"{pan}_html.pdf")
    text_zip_path = os.path.join(output_dir, f"{pan}_text.zip")
    text_txt_path = os.path.join(output_dir, f"{pan}_text.txt")
    
    # Decrypt AIS and TIS
    if os.path.exists(ais_path):
        decrypt_pdf(ais_path, pdf_password_ais)
    if os.path.exists(tis_path):
        decrypt_pdf(tis_path, pdf_password_ais)
        
    # Decrypt HTML PDF (if encrypted)
    if os.path.exists(html_path):
        decrypt_pdf(html_path, traces_password)
        
    # Decrypt Text ZIP
    if os.path.exists(text_zip_path):
        decrypt_zip(text_zip_path, traces_password, text_txt_path)
        
    # Strictly enforce only 4 allowed files inside the directory
    allowed_files = {
        f"{pan}_ais.pdf",
        f"{pan}_tis.pdf",
        f"{pan}_html.pdf",
        f"{pan}_text.txt"
    }
    
    for filename in os.listdir(output_dir):
        if filename not in allowed_files:
            try:
                os.remove(os.path.join(output_dir, filename))
            except Exception as e:
                logger.error(f"Failed to remove extraneous file {filename}: {e}")
                
    logger.info(f"[{pan}] Finished decryption and strict cleanup process.")
