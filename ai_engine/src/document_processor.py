from pathlib import Path
from datetime import datetime
from typing import List, Dict, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from io import BytesIO
import logging
import os
import json

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredPowerPointLoader,
    TextLoader
)

from config.settings import (
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    ENABLE_OCR,
    TESSERACT_CMD,
    OCR_SPARSE_TEXT_THRESHOLD,
    _MAX_LOADER_WORKERS
)
from src.document_cleaning import clean_documents
from src.course_mapping import get_course_code

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

OCR_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    import fitz

    if TESSERACT_CMD:
        if os.path.isabs(TESSERACT_CMD) and not os.path.exists(TESSERACT_CMD):
            logger.warning(f"Configured Tesseract executable not found at: {TESSERACT_CMD}")
        else:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    OCR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OCR libraries not installed: {e}")


class DocumentLoadError(Exception):
    pass

class DocumentProcessor:
    def __init__(
        self,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
        max_workers: int = _MAX_LOADER_WORKERS,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_workers = max_workers

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

        self.loader_mapping: Dict[str, Callable[[str], List[Document]]] = {
            ".pdf":  self._load_pdf,
            ".docx": self._load_docx,
            ".pptx": self._load_pptx,
            ".txt":  self._load_txt,
            ".png":  self._load_image,
            ".jpg":  self._load_image,
            ".jpeg": self._load_image,
        }

    # ------------------------------------------------------------------ #
    # Public pipeline                                                      #
    # ------------------------------------------------------------------ #

    def process_documents(self, source_path: str, course_code: Optional[str] = None) -> List[Document]:
        """Complete pipeline for a specific folder or file."""
        path = Path(source_path)
        if path.is_file():
            documents = self.load_document(str(path))
        elif path.is_dir():
            documents = self.load_directory(str(path))
        else:
            return []

        if not documents:
            return []

        if course_code:
            logger.info(f"Tagging documents with course_code: {course_code}")
            for doc in documents:
                doc.metadata["course_code"] = course_code.upper().strip()
                doc.metadata["doc_category"] = "course_specific"
        else:
            logger.info(f"No course_code provided. Tagging as campus_general.")
            for doc in documents:
                doc.metadata["doc_category"] = "campus_general"

        documents = clean_documents(documents)
        if not documents:
            return []

        return self.split_documents(documents)

    # ------------------------------------------------------------------ #
    # ★ الدالة الجديدة لقراءة هيكل المواد (Course-Based Structure) ★
    # ------------------------------------------------------------------ #
    def process_courses_from_root(self, root_data_path: str, skip_sources: set = None) -> List[Document]:
        """
        يقرأ فولدر الـ data الرئيسي، يكتشف فولدرات المواد جواه،
        ويعمل معالجة كاملة لكل مادة مع وضع كود المادة في الميتاداتا.
        """
        root = Path(root_data_path)
        if not root.is_dir():
            logger.error(f"Invalid root data path: {root_data_path}")
            return []

        all_chunks = []
        skip_sources = skip_sources or set()
        
        # 1. Process files directly in root as campus_general
        root_files = [f for f in root.iterdir() if f.is_file() and f.suffix.lower() in self.loader_mapping]
        for root_file in root_files:
            source_abs = str(root_file.resolve())
            if source_abs in skip_sources:
                continue
            logger.info(f"Processing general document: {root_file.name}")
            try:
                doc_chunks = self.process_documents(str(root_file), course_code=None)
                all_chunks.extend(doc_chunks)
            except Exception as e:
                logger.error(f"Error processing {root_file}: {e}")

        # 2. Process folders
        for item in root.iterdir():
            if not item.is_dir():
                continue
            
            # Skip internal system folders
            if item.name.lower() in ['processed', 'presentation_images']:
                continue
                
            if item.name.lower().startswith('year'):
                # Process year folders recursively
                logger.info(f"Scanning {item.name}...")
                departments = {'ai', 'it', 'is', 'cs', 'ds', 'general'}
                
                for sub_item in item.rglob("*"):
                    if sub_item.is_file() and sub_item.suffix.lower() in self.loader_mapping:
                        source_abs = str(sub_item.resolve())
                        if source_abs in skip_sources:
                            continue
                        
                        # Determine course folder name
                        rel_parts = sub_item.relative_to(item).parts
                        if len(rel_parts) >= 2 and rel_parts[0].lower() in departments:
                            course_folder = rel_parts[1]
                        else:
                            course_folder = rel_parts[0]
                        
                        course_code = get_course_code(course_folder)
                        logger.info(f"Processing: {sub_item.name} -> Code: {course_code}")
                        
                        try:
                            doc_chunks = self.process_documents(str(sub_item), course_code=course_code)
                            all_chunks.extend(doc_chunks)
                        except Exception as e:
                            logger.error(f"Error processing {sub_item}: {e}")
            else:
                # Process course folders directly at root
                course_code = get_course_code(item.name)
                logger.info(f"Scanning direct course folder: {item.name} -> Code: {course_code}")
                
                for sub_item in item.rglob("*"):
                    if sub_item.is_file() and sub_item.suffix.lower() in self.loader_mapping:
                        source_abs = str(sub_item.resolve())
                        if source_abs in skip_sources:
                            continue
                        
                        try:
                            doc_chunks = self.process_documents(str(sub_item), course_code=course_code)
                            all_chunks.extend(doc_chunks)
                        except Exception as e:
                            logger.error(f"Error processing {sub_item}: {e}")

        return all_chunks

    # ------------------------------------------------------------------ #
    # Cache helpers                                                        #
    # ------------------------------------------------------------------ #

    def save_chunks(self, chunks: List[Document], cache_path: str) -> None:
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                for chunk in chunks:
                    record = {"page_content": chunk.page_content, "metadata": chunk.metadata}
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error(f"Error saving chunks to cache: {e}")

    def load_chunks(self, cache_path: str) -> List[Document]:
        if not os.path.exists(cache_path):
            return []
        try:
            chunks = []
            with open(cache_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        record = json.loads(line)
                        chunks.append(Document(page_content=record["page_content"], metadata=record.get("metadata", {})))
                    except (json.JSONDecodeError, KeyError):
                        continue
            return chunks
        except OSError as e:
            return []

    # ------------------------------------------------------------------ #
    # Directory / Single loading                                           #
    # ------------------------------------------------------------------ #

    def load_directory(self, directory_path: str) -> List[Document]:
        path = Path(directory_path)
        supported_files = [fp for fp in path.rglob("*") if fp.is_file() and fp.suffix.lower() in self.loader_mapping]
        if not supported_files: return []

        all_documents = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # We use a dictionary to track futures
            future_to_path = {executor.submit(self.load_document, str(fp)): fp for fp in supported_files}
            
            for future in as_completed(future_to_path):
                fp = future_to_path[future]
                try:
                    # If a single file takes more than 30 seconds to load, it's likely corrupt or too complex
                    result = future.result(timeout=30) 
                    if result:
                        all_documents.extend(result)
                except TimeoutError:
                    print(f"  🛑 Timeout: Skipping {fp.name} (Taking too long to process)")
                except Exception as e:
                    print(f"  ❌ Error: Could not load {fp.name}: {e}")
                    
        return all_documents

    def load_document(self, file_path: str) -> List[Document]:
        path = Path(file_path)

        # Safety Check: Skip massive text files that cause hangs
        if path.suffix.lower() == ".txt" and path.stat().st_size > 10 * 1024 * 1024:
            print(f"  ⚠️ Skipping {path.name} (File too large: {path.stat().st_size // 1024 // 1024}MB)")
            return []

        print(f"  📄 Loading: {path.name}...")
        extension = path.suffix.lower()
        if extension not in self.loader_mapping: return []

        try:
            documents = self.loader_mapping[extension](file_path)
            self._enrich_metadata(documents, path)
            return documents
        except Exception as exc:
            raise DocumentLoadError(f"Error loading {file_path}: {exc}") from exc

    def split_documents(self, documents: List[Document]) -> List[Document]:
        return self.text_splitter.split_documents(documents)

    def _enrich_metadata(self, documents: List[Document], path: Path) -> None:
        absolute_source = str(path.resolve())
        for doc in documents:
            doc.metadata.update({
                "file_name": path.name,
                "file_type": path.suffix.lower(),
                "ingestion_timestamp": datetime.now().isoformat(),
                "source": absolute_source,
                # شلنا الـ academic_year عشان مش بنستخدمه في الهيكل الجديد
            })

    # ------------------------------------------------------------------ #
    # Specific loaders                                                    #
    # ------------------------------------------------------------------ #

    def _load_docx(self, file_path: str) -> List[Document]: return Docx2txtLoader(file_path).load()
    def _load_pptx(self, file_path: str) -> List[Document]: return UnstructuredPowerPointLoader(file_path).load()
    def _load_txt(self, file_path: str) -> List[Document]: return TextLoader(file_path, encoding="utf-8").load()

    def _load_image(self, file_path: str) -> List[Document]:
        if not (OCR_AVAILABLE and ENABLE_OCR): return []
        try:
            image = Image.open(file_path)
            ocr_text = pytesseract.image_to_string(image, lang="ara+eng")
            return [Document(page_content=ocr_text, metadata={"source": file_path})] if ocr_text.strip() else []
        except Exception: return []

    def _load_pdf(self, file_path: str) -> List[Document]:
        if ENABLE_OCR and OCR_AVAILABLE:
            try:
                documents = self._load_pdf_with_ocr(file_path)
                if documents: return documents
            except Exception: pass
        return PyPDFLoader(file_path).load()

    def _load_pdf_with_ocr(self, file_path: str) -> List[Document]:
        try:
            documents = []
            pdf_document = fitz.open(file_path)
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text = page.get_text()
                if len(text.strip()) < OCR_SPARSE_TEXT_THRESHOLD:
                    for img_index, img in enumerate(page.get_images()):
                        try:
                            base_image = pdf_document.extract_image(img[0])
                            ocr_text = pytesseract.image_to_string(Image.open(BytesIO(base_image["image"])), lang="ara+eng")
                            if ocr_text.strip(): text += f"\n[OCR from image {img_index + 1}]\n{ocr_text}"
                        except Exception: pass
                if text.strip():
                    documents.append(Document(page_content=text, metadata={"source": file_path, "page": page_num + 1}))
            pdf_document.close()
            return documents
        except Exception: return []