from typing import Dict, List
from pathlib import Path
from langchain_core.documents import Document
from src.document_processor import DocumentProcessor
from src.vector_store import VectorStoreManager, VectorStoreError
from src.retriever import Retriever
from src.generator import Generator
from src.youtube_processor import YouTubeProcessor
from src.recommender import RecommendationEngine
from src.presentation_maker import PresentationMaker
from config.settings import RAW_DATA_DIR
import logging
import os
import re

logger = logging.getLogger(__name__)

NOT_COVERED_PHRASES = [
    "not covered in the course materials",
    "غير مذكور في المواد الدراسية",
    "i can only answer questions based on the provided documents",
    "لا أستطيع الإجابة إلا بناءً على المستندات المقدمة",
]

def _is_not_covered(answer: str) -> bool:
    answer_lower = answer.lower()
    return any(phrase in answer_lower for phrase in NOT_COVERED_PHRASES)

class RAGPipeline:
    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.vector_store_manager = VectorStoreManager()
        self.retriever = Retriever(vector_store_manager=self.vector_store_manager)
        self.generator = Generator()
        self.youtube_processor = YouTubeProcessor()
        self.recommender = RecommendationEngine()
        self.presentation_maker = PresentationMaker()
        self.is_initialized = False

    def initialize(self, data_path: str = None):
        """High-performance Incremental Sync Mode."""
        if data_path is None:
            data_path = str(RAW_DATA_DIR)

        logger.info("Initializing RAG pipeline (Incremental Sync Mode)...")
        
        # 1. Load existing vector store and get processed sources
        existing_sources = set()
        try:
            self.vector_store_manager.load_vector_store()
            existing_sources = self.vector_store_manager.get_all_sources()
            logger.info(f"Existing vector store found with {len(existing_sources)} files.")
        except Exception:
            logger.info("No existing vector store found or failed to load. Starting fresh.")

        # 2. Process documents, skipping those already in the store
        logger.info("Processing documents...")
        chunks = self.document_processor.process_courses_from_root(data_path, skip_sources=existing_sources)

        if not chunks:
            if existing_sources:
                logger.info("No new documents to process. Everything is up to date.")
                self.is_initialized = True
                return
            else:
                raise ValueError("No documents were processed. Check your data directory.")

        # 3. Add ONLY new chunks to the vector store
        logger.info(f"Adding {len(chunks)} new chunks to the vector store...")
        if existing_sources:
            self.vector_store_manager.add_documents(chunks)
        else:
            self.vector_store_manager.create_vector_store(chunks, overwrite=True)
            
        self.is_initialized = True
        logger.info("RAG pipeline initialized successfully!")

    def add_documents(self, source_path: str, course_code: str = None):
        """Add new documents to existing vector store."""
        logger.info(f"Adding documents from {source_path}")
        chunks = self.document_processor.process_documents(source_path, course_code=course_code)
        if not chunks:
            logger.warning("No new documents were processed")
            return
        self.vector_store_manager.add_documents(chunks)
        self.retriever.invalidate_bm25()
        logger.info("Documents added successfully!")

    # ================================================================== #
    # ★ الدالة الرئيسية المحدثة (Agentic Evaluate-and-Route + Smart Filter + Global Fallback) ★
    # ================================================================== #
    def query(
        self, 
        question: str, 
        history: list = None, 
        user_courses: List[str] = None,     # List of course codes (e.g. ["CS101", "MA111"])
        selected_course: str = None,         # A single course code to lock search to
        forced_documents: List[Document] = None, 
        image_paths: List[str] = None
    ) -> Dict:
        
        if not self.is_initialized:
            logger.info("Pipeline not initialized, loading existing vector store...")
            try:
                self.vector_store_manager.load_vector_store()
                self.is_initialized = True
            except VectorStoreError as e:
                logger.error(f"Failed to load vector store: {e}")
                return {"answer": "Vector store not found. Please run initialization first.", "sources": []}

        logger.info(f"Processing query: {question}")
        has_arabic = any('\u0600' <= char <= '\u06FF' for char in question)

        # -----------------------------------------------------------------
        # 0. Definitions & Memory
        # -----------------------------------------------------------------
        question_lower = question.lower().strip()
        presentation_keywords = ["presentation", "slides", "powerpoint", "pptx", "make a presentation", "عرض تقديمي", "شرائح", "بوربوينت", "اعمل عرض", "سوي بريزنتيشن", "slideshow", "slideshows", "deck"]
        recommendation_keywords = ["recommend", "suggest", "more resources", "other courses", "another video", "مقترح", "ترشيح", "مصادر أخرى", "كورس آخر", "نرشح", "زيدني"]
        approval_keywords = ["approved", "looks good", "go ahead", "proceed", "تمام", "اعتمد", "ممتاز", "موافق", "باشر", "good", "ok", "nice", "yes", "حلو", "ماشي", "اعمله", "done", "agree", "perfect", "yep", "sure"]

        logger.info("Agent 1 (Memory): Rewriting query...")
        rewritten_query = self.generator.rewrite_query_with_memory(question, history or [])
        logger.info(f"Rewritten Query: {rewritten_query}")

        is_presentation = any(keyword in question_lower for keyword in presentation_keywords)
        is_recommendation = any(keyword in question_lower for keyword in recommendation_keywords)
        is_approval = any(keyword in question_lower for keyword in approval_keywords)

        url_pattern = r'https?://(?:www\.)?youtube\.com/watch\?v=[0-9A-Za-z_-]{11}|https?://youtu\.be/[0-9A-Za-z_-]{11}'
        
        # YouTube Processing
        youtube_data = self.youtube_processor.process_url(question)
        video_meta = {"title": youtube_data.get("title"), "duration": youtube_data.get("duration")} if youtube_data else None

        # -----------------------------------------------------------------
        # ★ PRESENTATION ARCHITECT FLOW ★
        # -----------------------------------------------------------------
        if is_presentation or is_approval:
            # Detect Phase 2 (Approval or Adjustment)
            last_assistant_msg = ""
            if history:
                for msg in reversed(history):
                    if msg["role"] == "assistant":
                        last_assistant_msg = msg["content"]
                        break
            
            # More robust blueprint detection: scan entire recent history for a blueprint
            history_text = " ".join([m["content"].upper() for m in history]) if history else ""
            blueprint_markers = [
                "PHASE 1: THE BLUEPRINT", 
                "SLIDE-BY-SLIDE OUTLINE", 
                "PROPOSED SLIDES", 
                "BLUEPRINT",
                "المخطط المبدئي",
                "REVISED PRESENTATION"
            ]
            is_blueprint_context = any(marker in history_text for marker in blueprint_markers) or any(marker in last_assistant_msg.upper() for marker in blueprint_markers)
            
            is_phase_2 = is_approval and is_blueprint_context
            is_adjustment = not is_approval and is_blueprint_context and not is_presentation

            logger.info(f"Presentation Architect Flow: {'Phase 2' if is_phase_2 else 'Phase 1/Refinement'}")
            
            # Retrieve relevant content for the topic
            # IMPROVEMENT: In Phase 2, use the Blueprint as the search query to ensure we get the right materials
            search_query = rewritten_query
            if is_phase_2:
                # Extract first few lines of blueprint as a search hint
                search_query = "\n".join(last_assistant_msg.split("\n")[:10])
                logger.info(f"Phase 2 Search Hint: {search_query[:100]}...")

            raw_documents = forced_documents if forced_documents else self.retriever.retrieve(search_query)
            context_parts = []
            if youtube_data:
                context_parts.append(f"[YOUTUBE TRANSCRIPT]: {youtube_data.get('transcript', '')}")
            if raw_documents:
                context_parts.append("\n".join([d.page_content for d in raw_documents]))
            full_context = "\n\n".join(context_parts) if context_parts else rewritten_query

            if is_phase_2:
                # PHASE 2: Full Content Generation
                slides_data = self.generator.get_presentation_final_content(full_context, last_assistant_msg)
                user_images = [p for p in (image_paths or []) if p and os.path.exists(p)]
                pptx_path = self.presentation_maker.create_presentation(slides_data, user_images, "generated_presentation.pptx")
                
                if pptx_path:
                    msg = f"لقد قمت بإنشاء العرض التقديمي النهائي بناءً على المخطط المعتمد. يمكنك العثور عليه هنا: {pptx_path}" if has_arabic else f"I have generated the final presentation based on the approved blueprint. You can find it here: {pptx_path}"
                    return {"answer": msg, "sources": [], "presentation_path": pptx_path}
                return {"answer": "Error creating the presentation file.", "sources": []}
            elif is_adjustment:
                # REFINEMENT: Update Blueprint based on feedback
                blueprint = self.generator.get_presentation_blueprint(full_context, f"Adjust the previous blueprint based on this feedback: {question}\n\nPrevious Blueprint:\n{last_assistant_msg}")
                return {"answer": blueprint, "sources": []}
            else:
                # PHASE 1: Initial Blueprint Generation
                blueprint = self.generator.get_presentation_blueprint(full_context, question)
                return {"answer": blueprint, "sources": []}

        # -----------------------------------------------------------------
        # ★ FAST TRACK: الترشيحات ★
        # -----------------------------------------------------------------
        if is_recommendation:
            logger.info("Recommendation intent detected...")
            rec_query = rewritten_query
            if (not rec_query or rec_query == "general") and video_meta and video_meta['title'] != "Unknown Title":
                rec_query = video_meta['title']
            recommendation_data = self.recommender.get_all_recommendations(rec_query)
            answer = self.generator.generate_answer(question, "", is_youtube=bool(youtube_data), history=history, recommendations=recommendation_data)
            return {"answer": answer, "sources": []}


        # ==================================================================
        # ★ AGENTIC TRACK: سؤال عادي ★
        # ==================================================================

        # -----------------------------------------------------------------
        # 2. Smart Filtering Logic (Using Course Codes)
        # -----------------------------------------------------------------
        active_filter = None
        if selected_course:
            logger.info(f"UI Filter ON: Searching ONLY in course code '{selected_course}'")
            active_filter = [selected_course.upper().strip()]
        elif user_courses:
            logger.info(f"UI Filter OFF: Searching in ALL enrolled course codes: {user_courses}")
            active_filter = [c.upper().strip() for c in user_courses]
        else:
            logger.info("No course codes provided. Searching globally.")
        # -----------------------------------------------------------------

        # 3. Agent Retrieval (First Pass - Enrolled Courses)
        logger.info("Agent 2 (Retriever): Fetching docs...")
        if forced_documents:
            documents = forced_documents
        else:
            # CLEAN the query for retrieval: remove "presentation", "make a", etc. 
            # to prevent them from diluting the vector search.
            clean_search_query = rewritten_query
            for kw in presentation_keywords + ["make", "create", "about", "discussing", "regarding"]:
                clean_search_query = clean_search_query.lower().replace(kw, "").strip()
            
            if not clean_search_query: # Fallback if empty
                clean_search_query = rewritten_query
                
            logger.info(f"Cleaned Retrieval Query: {clean_search_query}")
            documents = self.retriever.retrieve(clean_search_query, user_courses=active_filter)

        # 4. Prepare YouTube Context if exists
        context_parts = []
        if youtube_data:
            meta_header = f"[VIDEO_TITLE: {video_meta['title']}]\n[VIDEO_DURATION: {video_meta['duration']}]\n"
            raw_transcript = youtube_data.get("transcript")
            
            # Smart Truncation for long transcripts (staying under Groq limits)
            if raw_transcript and len(raw_transcript) > 25000: # ~8000 tokens
                logger.info("Transcript too long, truncating to 25000 characters...")
                raw_transcript = raw_transcript[:25000] + "\n... [Transcript truncated for length] ..."
                
            content = raw_transcript if raw_transcript and "[ERROR:" not in str(raw_transcript) else "[No Transcript Available]"
            context_parts.append("[SOURCE: YOUTUBE_VIDEO_TRANSCRIPT]\n" + meta_header + content)

        # -----------------------------------------------------------------
        # 5. لو مفيش مستندات من المحاضرات
        # -----------------------------------------------------------------
        if not documents:
            logger.warning("No documents retrieved from vector store.")
            route = self.generator.route_query(question)
            if route == "college_specific":
                ans = "عذراً، لم أجد هذه المعلومات في المحاضرات المسجلة عليك. يرجى التواصل مع قسم الكلية أو السكرتارية للتأكد." if has_arabic else "Sorry, I couldn't find this info in your enrolled courses. Please contact your department."
                return {"answer": ans, "sources": []}
            else:
                if context_parts:
                    full_context = "\n\n---\n\n".join(context_parts)
                    return {"answer": self.generator.generate_answer(question, full_context, is_youtube=True, history=history), "sources": []}
                ans = self.generator.generate_general_answer(question, history)
                return {"answer": ans, "sources": []}

        # -----------------------------------------------------------------
        # 6. تجهيز Context من المحاضرات
        # -----------------------------------------------------------------
        course_text = "\n\n".join([
            f"[Chunk {i+1} | File: {doc.metadata.get('file_name', 'unknown')}]:\n{doc.page_content}"
            for i, doc in enumerate(documents)
        ])
        context_parts.append("[SOURCE: OFFICIAL_COURSE_MATERIALS]\n" + course_text)
        full_context = "\n\n" + "\n\n---\n\n".join(context_parts)

        # -----------------------------------------------------------------
        # 7. Agent Evaluator: هل الداتا دي صح ولا False Positive؟
        # -----------------------------------------------------------------
        logger.info("Agent 3 (Evaluator): Checking if docs contain the answer...")
        evaluation = self.generator.evaluate_documents(rewritten_query, course_text) 
        logger.info(f"Evaluation Result: {evaluation}")

        # -----------------------------------------------------------------
        # 8. Agent Routing & Generation
        # -----------------------------------------------------------------
        if evaluation == "Yes":
            # الحالة الآمنة: الداتا صحيحة
            logger.info("Routing to Course Materials Generator...")
            answer = self.generator.generate_answer(
                question, full_context, is_youtube=bool(youtube_data), history=history
            )
            
            # ★ إزالة تكرار المصادر (نفس الملف ونفس الصفحة) ★
            seen_sources = set()
            unique_sources = []
            for doc in documents:
                file_name = doc.metadata.get('file_name', 'unknown')
                page = doc.metadata.get('page', 'unknown')
                source_key = f"{file_name}_p{page}"
                if source_key not in seen_sources:
                    seen_sources.add(source_key)
                    unique_sources.append({
                        "content": doc.page_content[:200] + "...", 
                        "metadata": doc.metadata
                    })
            
            return {"answer": answer, "sources": unique_sources}

        else:
            # ==================================================================
            # ★ الحالة الحرجة: الداتا مش كفاية (False Positive / Not Found)
            # ==================================================================
            
            # ★ DISABLED Global Search Pass to strictly enforce registered course filtering ★
            should_search_globally = False
            
            if should_search_globally:
                logger.info("Agent 3.5: Trying Global Search (Second Pass)...")
                global_docs = self.retriever.retrieve(rewritten_query, user_courses=None)
                
                if global_docs:
                    global_course_text = "\n\n".join([
                        f"[Chunk {i+1} | File: {doc.metadata.get('file_name', 'unknown')}]:\n{doc.page_content}"
                        for i, doc in enumerate(global_docs)
                    ])
                    global_eval = self.generator.evaluate_documents(rewritten_query, global_course_text)
                    
                    if global_eval == "Yes":
                        logger.info("Global Search succeeded! Found answer in other university courses.")
                        
                        # تجهيز الـ Context للإجابة الشاملة
                        global_context_parts = []
                        if youtube_data:
                            meta_header = f"[VIDEO_TITLE: {video_meta['title']}]\n[VIDEO_DURATION: {video_meta['duration']}]\n"
                            raw_transcript = youtube_data.get("transcript")
                            content = raw_transcript if raw_transcript and "[ERROR:" not in str(raw_transcript) else "[No Transcript Available]"
                            global_context_parts.append("[SOURCE: YOUTUBE_VIDEO_TRANSCRIPT]\n" + meta_header + content)

                        global_context_parts.append("[SOURCE: OFFICIAL_COURSE_MATERIALS]\n" + global_course_text)
                        full_global_context = "\n\n---\n\n".join(global_context_parts)
                        
                        # رسالة تنبيه للطالب
                        sys_warning = "\n\nSystem Note to Student: This answer was found in another course in your faculty's materials, not specifically in your enrolled courses." if not has_arabic else "\n\nملاحظة النظام: تم العثور على هذه الإجابة في مواد أخرى لكلية، وليس في المواد المسجلة لديك."
                        
                        answer = self.generator.generate_answer(
                            question, full_global_context, is_youtube=bool(youtube_data), history=history
                        ) + sys_warning
                        
                        # ★ إزالة تكرار المصادر للبحث الشامل ★
                        seen_global_sources = set()
                        global_sources = []
                        for doc in global_docs:
                            file_name = doc.metadata.get('file_name', 'unknown')
                            page = doc.metadata.get('page', 'unknown')
                            source_key = f"{file_name}_p{page}"
                            if source_key not in seen_global_sources:
                                seen_global_sources.add(source_key)
                                global_sources.append({
                                    "content": doc.page_content[:200] + "...", 
                                    "metadata": doc.metadata
                                })
                        
                        return {"answer": answer, "sources": global_sources}

            # ==================================================================
            # إذا وصلنا هنا: (البحث الشامل فشل) أو (اليوزر كان محدد مادة معينة ولازم نحترم اختياره)
            # ==================================================================
            logger.info("Routing to Fallback Logic (Global search failed or UI locked to specific course)...")
            route = self.generator.route_query(question)
            
            if route == "college_specific":
                ans = "عذراً، المعلومات المسترجعة لا تحتوي على إجابة دقيقة لسؤالك المتعلق بالجامعة. يرجى التواصل مع القسم المختص." if has_arabic else "Sorry, the retrieved documents do not contain a precise answer to your university-related question. Please contact the relevant department."
                return {"answer": ans, "sources": []}
            
            else:
                # سؤال عام، والمحاضرات مشتغطيه
                raw_yt_transcript = youtube_data.get('transcript') if youtube_data else None
                if youtube_data and raw_yt_transcript and "[ERROR:" not in str(raw_yt_transcript):
                    logger.info("Falling back to YouTube Transcript...")
                    yt_context = context_parts[0] if context_parts else ""
                    answer = self.generator.generate_answer(question, yt_context, is_youtube=True, history=history)
                    return {"answer": answer, "sources": []}

                logger.info("Routing to General Knowledge Generator...")
                ans = self.generator.generate_general_answer(question, history)
                return {"answer": ans, "sources": []}