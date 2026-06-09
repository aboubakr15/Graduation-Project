from typing import Dict, Optional
import logging
import re
import json
from config.settings import USE_GROQ, GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("Groq not installed. Install with: pip install groq")


QUESTION_TYPE_INSTRUCTIONS = {
    "mcq": {
        "en": "Select the correct option from the provided choices.",
        "ar": "اختر الإجابة الصحيحة من الخيارات المقدمة."
    },
    "fill_blank": {
        "en": "Provide only the missing word or phrase to complete the statement.",
        "ar": "أعط الكلمة أو العبارة المفقودة فقط لإكمال الجملة."
    },
    "explain": {
        "en": """Provide a well-structured, professional explanation using the following format:
- Start with a brief, clear definition or summary (1-2 sentences).
- Use markdown headers (###, ####) to organize sections logically.
- Use bullet points with **bold** labels for key characteristics or points.
- Include code blocks only if code exists in the provided materials.
- End with a concise one-sentence summary.
- Do NOT use "Step 1, Step 2" format. Do NOT number every paragraph.""",
        "ar": """قدم شرحاً منظماً واحترافياً بالتنسيق التالي:
- ابدأ بتعريف موجز وواضح (جملة أو جملتان).
- استخدم عناوين markdown لتنظيم الأقسام بشكل منطقي.
- استخدم النقاط مع تسميات بارزة للخصائص والنقاط الرئيسية.
- أضف كتل الكود فقط إذا كان الكود موجوداً في المواد المقدمة.
- اختم بجملة ملخصة موجزة.
- لا تستخدم تنسيق الخطوات المرقمة."""
    },
    "true_false": {
        "en": "State whether the statement is True or False, followed by a brief explanation.",
        "ar": "اذكر ما إذا كانت العبارة صحيحة أم خاطئة، متبوعاً بشرح موجز."
    },
    "code": {
        "en": """You are a technical mentor and programming expert. 
If the student asks to write, implement, or provide code:
- Provide the complete, functional, and well-commented code implementation first.
- Then, provide a structured analysis including the sections below.

If the student provides code to be analyzed:
- Provide a structured response including:
1. High-level Overview: What does this code do in simple terms?
2. Step-by-Step Walkthrough: How does it execute?
3. Variables & Functions: Explain the key components.
4. Control Flow: Identify loops, conditionals, or recursion.
5. Complexity Analysis: Estimate Time and Space complexity.
6. Edge Cases & Potential Issues: What could go wrong?
7. Improvements: Suggest optimizations or better practices.
If the code has errors, point them out clearly.""",
        "ar": """أنت معلم تقني وخبير برمجة.
إذا طلب الطالب كتابة أو تنفيذ أو تقديم كود:
- قدم الكود البرمجي الكامل والوظيفي والمشروح جيداً أولاً.
- ثم قدم تحليلاً منظماً يتضمن الأقسام المذكورة أدناه.

إذا قدم الطالب كوداً للتحليل:
- قدم استجابة منظمة تشمل:
1. نظرة عامة: ماذا يفعل هذا الكود بلمحة سريعة؟
2. شرح خطوة بخطوة: كيف يتم التنفيذ؟
3. المتغيرات والدوال: شرح المكونات الرئيسية.
4. تدفق التحكم: تحديد الحلقات (loops)، الشروط، أو التكرار (recursion).
5. تحليل التعقيد: تقدير التعقيد الزمني والمكاني (Complexity analysis).
6. الحالات الحادة والمشاكل المحتملة: ما الذي قد يفشل؟
7. التحسينات: اقتراح تحسينات أو أفضل الممارسات.
إذا كان الكود يحتوي على أخطاء، وضحها بوضوح."""
    }
}


class Generator:
    def __init__(self):
        self.model   = GROQ_MODEL
        self.api_key = GROQ_API_KEY
        if GROQ_AVAILABLE and self.api_key:
            self.client = Groq(api_key=self.api_key)
        else:
            self.client = None

    # ──────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────

    def generate_answer(
        self,
        question: str,
        context: str,
        question_type: str = None,
        is_youtube: bool = False,
        history: list = None,
        recommendations: dict = None,
    ) -> str:
        """Generate an answer from context using Groq or a simple fallback."""

        if question_type is None:
            question_type = self._detect_question_type(question)

        if USE_GROQ and GROQ_AVAILABLE and self.client:
            try:
                return self._generate_with_groq(
                    question, context, question_type, is_youtube, history, recommendations
                )
            except Exception as e:
                logger.error(f"Groq generation failed: {e}")
                logger.info("Falling back to simple context display")

        # Fallback
        return f"Based on the course materials:\n\n{context[:800]}..."

    # ================================================================== #
    # ★  MARKDOWN PRESENTATION ARCHITECT (replaces JSON-based flow)  ★
    # ================================================================== #

    def get_presentation_blueprint_md(self, content: str, user_request: str) -> str:
        """
        Phase 1 — Blueprint (Markdown format).
        Forces the LLM to output a Markdown outline using:
          # Slide Title
          - bullet
        separated by <!-- slide --> HTML comments.
        The user reviews this outline and approves/adjusts before Phase 2.
        """
        if not USE_GROQ or not GROQ_AVAILABLE or not self.client:
            return "Error: LLM not available for blueprint generation."

        prompt = f"""You are a Professional Presentation Architect.
Your ONLY job is to output a slide-by-slide OUTLINE for a presentation.
If the user asks to change or adjust an existing outline, you MUST output the completely updated outline in the correct format. NEVER explain how to do it or talk to the user.

OUTPUT FORMAT — YOU MUST FOLLOW THIS EXACTLY:
- Separate each slide with the HTML comment: <!-- slide -->
- Each slide block starts with a Markdown heading: # Slide Title
- Each slide block contains 1-3 SHORT bullet points (just the goal/topic, NOT full sentences).
  Use a single dash: - bullet
- The FIRST slide must always be a cover slide (title of the presentation + 1-line subtitle).
- The LAST slide must always be a closing slide with title: # Thank You
  and one bullet: - Questions & Discussion
- ABSOLUTELY NO EXTRA TEXT. Do NOT converse, do NOT explain, do NOT say "Here is your updated outline". Output ONLY the slide blocks.
- Do NOT wrap the output in ```markdown``` fences.

EXAMPLE OUTPUT (follow this structure exactly):
# Introduction to Neural Networks
- A beginner's guide to deep learning concepts

<!-- slide -->

# What is a Neural Network?
- Inspired by the human brain
- Layers of interconnected nodes

<!-- slide -->

# Thank You
- Questions & Discussion

NOW generate the blueprint for this request:

[CONTENT]
{content[:5000]}

[USER REQUEST]
{user_request}

Blueprint (Markdown only, no extra text):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Blueprint (MD) generation failed: {e}")
            return "Error generating presentation blueprint."

    def adjust_presentation_blueprint_md(self, previous_blueprint: str, user_request: str) -> str:
        """
        Refinement — Adjust the existing blueprint based on user's feedback.
        """
        if not USE_GROQ or not GROQ_AVAILABLE or not self.client:
            return "Error: LLM not available for blueprint adjustment."

        prompt = f"""You are a Professional Presentation Architect.
Your ONLY job is to modify the existing presentation outline based on the user's request.
NEVER explain how to do it or talk to the user.

Here is the existing presentation outline:
{previous_blueprint}

User request for adjustments:
{user_request}

OUTPUT FORMAT — YOU MUST FOLLOW THIS EXACTLY:
- Separate each slide with the HTML comment: <!-- slide -->
- Each slide block starts with a Markdown heading: # Slide Title
- Each slide block contains 1-3 SHORT bullet points (just the goal/topic, NOT full sentences).
  Use a single dash: - bullet
- The FIRST slide must always be a cover slide (title of the presentation + 1-line subtitle).
- ABSOLUTELY NO EXTRA TEXT. Do NOT converse, do NOT explain, do NOT say "Here is your updated outline". Output ONLY the slide blocks.
- Do NOT wrap the output in ```markdown``` fences.

Updated Blueprint (Markdown only, no extra text):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Blueprint adjustment failed: {e}")
            return "Error adjusting presentation blueprint."

    def get_presentation_final_md(self, content: str, approved_blueprint: str) -> str:
        """
        Phase 2 — Full slide content (Markdown format).
        Takes the approved Markdown blueprint and expands each slide into
        complete educational bullet points, still using the same Markdown
        # / - / <!-- slide --> format so the parser can build the PPTX.
        """
        if not USE_GROQ or not GROQ_AVAILABLE or not self.client:
            return ""

        prompt = f"""You are a Professional Presentation Architect.
Expand the approved outline below into a FULL slide deck with rich, educational content.

OUTPUT FORMAT — YOU MUST FOLLOW THIS EXACTLY:
- Separate each slide with the HTML comment: <!-- slide -->
- Each slide block starts with: # Slide Title
- Each content slide has 4-6 bullets. Use: - bullet
- Each bullet MUST be a COMPLETE EDUCATIONAL SENTENCE of 10-18 words that EXPLAINS a concept.
  BAD:  "- Represents program in memory"
  GOOD: "- The text segment stores the compiled machine code of the program that the CPU executes."
- The FIRST slide (cover) keeps only the title and 1-line subtitle bullet.
- The LAST slide (# Thank You) keeps only: - Questions & Discussion
- STICK TO SOURCE: only use ideas from [CONTENT SOURCE]. Do NOT add external topics.
- Do NOT add any extra text, explanations, headers, or code blocks outside the slide blocks.
- Do NOT wrap the output in ```markdown``` fences.

[CONTENT SOURCE]
{content[:5000]}

[APPROVED OUTLINE]
{approved_blueprint}

Full Markdown deck (no extra text):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.3,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Final MD generation failed: {e}")
            return ""

    # ── Deprecated stubs kept for backward compatibility ───────────────

    def get_presentation_blueprint(self, content: str, user_request: str) -> str:
        """Deprecated: use get_presentation_blueprint_md() instead."""
        return self.get_presentation_blueprint_md(content, user_request)

    def get_presentation_final_content(self, content: str, approved_outline: str) -> list:
        """Deprecated: returns empty list — use get_presentation_final_md() instead."""
        logger.warning("get_presentation_final_content() is deprecated. Use get_presentation_final_md().")
        return []

    def get_presentation_structure(self, content: str, title: str = "Presentation") -> list:
        """Deprecated: returns empty list — use the Markdown flow instead."""
        logger.warning("get_presentation_structure() is deprecated. Use the Markdown flow.")
        return []

    # ──────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────

    def _parse_json_array(self, text: str) -> list:
        """Robustly extract and parse a JSON array from LLM output."""
        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()

        # Try direct parse first
        try:
            result = json.loads(clean)
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

        # Try to extract the outermost [...] block
        match = re.search(r'\[\s*\{.*\}\s*\]', clean, re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("No valid JSON array found in LLM response.")

    def _validate_and_fix_slides(self, slides: list, title: str) -> list:
        """Ensure slides list has correct structure, cover, and closing slide."""
        valid_types = {"cover", "content", "two_column", "closing"}

        for slide in slides:
            # Normalise type
            if slide.get("type") not in valid_types:
                slide["type"] = "content"
            # Ensure content is a list
            if isinstance(slide.get("content"), str):
                slide["content"] = [slide["content"]]
            elif not isinstance(slide.get("content"), list):
                slide["content"] = []
            # Ensure notes is a string
            if not isinstance(slide.get("notes"), str):
                slide["notes"] = ""
            # Ensure title
            if not slide.get("title"):
                slide["title"] = "Slide"

        # Guarantee first slide is cover
        if not slides or slides[0].get("type") != "cover":
            slides.insert(0, {
                "type": "cover",
                "title": title,
                "content": ["A structured overview of the topic"],
                "notes": "Welcome the audience and introduce yourself.",
            })

        # Guarantee last slide is closing
        if len(slides) < 2 or slides[-1].get("type") != "closing":
            slides.append({
                "type": "closing",
                "title": "Thank You",
                "content": ["Questions & Discussion"],
                "notes": "Open the floor for questions.",
            })

        return slides

    def _detect_question_type(self, question: str) -> str:
        """Automatically detect question type based on heuristics."""
        question_lower = question.lower().strip()

        if re.search(r"\b[A-D]\)", question) or any(
            kw in question_lower for kw in ["choose", "which of the following", "اختر", "أي مما يلي"]
        ):
            return "mcq"

        if any(kw in question_lower for kw in ["true or false", "صح أم خطأ", "صح أو خطأ"]):
            return "true_false"

        if "____" in question or "..." in question or any(
            kw in question_lower for kw in ["complete", "fill in", "اكمل", "أكمل"]
        ):
            return "fill_blank"

        code_keywords = [
            "code", "function", "variable", "class", "loop", "algorithm",
            "complexity", "syntax", "debug", "refactor",
            "كود", "دالة", "متغير", "خوارزمية",
        ]
        if "```" in question or any(kw in question_lower for kw in code_keywords):
            return "code"

        return "explain"

    def _build_messages(
        self,
        question: str,
        context: str,
        question_type: str,
        history: list,
        rec_text: str,
        has_arabic: bool,
    ) -> list:
        """Build the messages list for the Groq chat completion call."""

        q_type      = question_type if question_type in QUESTION_TYPE_INSTRUCTIONS else "explain"
        instruction = QUESTION_TYPE_INSTRUCTIONS[q_type]["ar" if has_arabic else "en"]

        # ── System prompt ──────────────────────────────────────────────
        if has_arabic:
            system_prompt = f"""أنت مساعد تعليمي. معرفتك مقيدة تماماً بالمحتوى الموجود في [SOURCE: OFFICIAL_COURSE_MATERIALS] و [SOURCE: YOUTUBE_VIDEO_TRANSCRIPT] فقط.

قواعد صارمة يجب اتباعها دون استثناء:
1.  ممنوع الإجابة من معرفتك العامة الخاصة. لا يُسمح لك باستخدام أي معلومة خارج المواد الدراسية المقدمة.
2. إذا لم يُذكر الموضوع أو الإجابة في المحتوى المقدم، يجب أن تجيب فقط بـ:
   " هذا الموضوع غير مذكور في المواد الدراسية. لا أستطيع الإجابة إلا بناءً على المستندات المقدمة."
   لا تحاول الإجابة أو التخمين أو تقديم معلومات جزئية من خارج المواد.
3. الاستثناء الوحيد للقاعدة الأولى هو إذا كان السؤال عن بناء الجملة البرمجية (Syntax) أو تصحيح أخطاء كود موجود فعلاً في المواد الدراسية.
4. إذا سأل الطالب عن معلومة وقدم رابط فيديو، ابحث أولاً في [SOURCE: YOUTUBE_VIDEO_TRANSCRIPT] واذكر الوقت الدقيق (مثال: "ذكر المحاضر عند الدقيقة [00:12:30] أن...").
5. في حالة ملاحظة "[Transcription Blocked]" أو "[No Transcript Available]"، أخبر الطالب أنك لم تتمكن من قراءة التفاصيل واعرض المساعدة من مواد الكورس.
6. في حالة الأسئلة التي تطلب "ترشيحات"، استخدم بيانات [RECOMMENDED_RESOURCES] فقط.
7. لا تعرض الترشيحات إذا كان الطالب يطلب تلخيص الفيديو المقدم.
8. ممنوع تماماً تقديم أي روابط بحث عامة أو روابط لمواقع أخرى (ولكن يجب عليك كتابة وتضمين روابط اليوتيوب المحددة المذكورة في [RECOMMENDED_RESOURCES] كما هي مع الترشيحات).
9. استخدم سجل المحادثة لفهم الأسئلة المتابعة.
10. الإجابة يجب أن تكون منسقة ومنظمة (استخدم النقاط والعناوين الفرعية والكود عند الحاجة).
11. إذا كانت قائمة الترشيحات فارغة، قل فقط: "عذراً، لم أجد روابط يوتيوب مناسبة حالياً."
12. أجب فقط عن المفهوم المحدد الذي سأل عنه الطالب. المحتوى المسترجع قد يحتوي على عدة مفاهيم أو مواضيع في نفس الجزء — استخرج وقدم فقط ما يتعلق مباشرةً بسؤال الطالب. تجاهل المفاهيم غير ذات الصلة حتى لو كانت في نفس الجزء.
13. إذا كان إدخال الطالب عبارة عن تحية بسيطة (مثل "مرحباً"، "أهلاً"، "شكراً"، "كيف حالك")، قم بالرد بأدب واسأله كيف يمكنك مساعدته في دراسته. لا تقم بتلخيص أو ذكر المواد الدراسية في هذه الحالة.

تعليمات خاصة بنوع السؤال:
{instruction}"""
        else:
            system_prompt = f"""You are a helpful teaching assistant. Your knowledge is STRICTLY LIMITED to the content provided in [SOURCE: OFFICIAL_COURSE_MATERIALS] and [SOURCE: YOUTUBE_VIDEO_TRANSCRIPT] below.

STRICT RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:
1.  NEVER answer from your own general knowledge. You are NOT allowed to use any information outside the provided course materials.
2. If the topic or answer is NOT found in the provided content, you MUST respond ONLY with:
   " This topic is not covered in the course materials. I can only answer questions based on the provided documents."
   Do NOT attempt to answer, guess, or provide partial information from outside the materials.
3. The ONLY exception to rule 1 is if the question is about CODE SYNTAX or DEBUGGING of code that already appears in the course materials — in that case you may assist technically.
4. Answer from [SOURCE: YOUTUBE_VIDEO_TRANSCRIPT] first if a video link was provided. Include exact timestamps (e.g., "The speaker mentions at [00:05:20] that...").
5. If you see "[Transcription Blocked]" or "[No Transcript Available]", inform the user and offer to help using course materials instead.
6. If the student asks for "recommendations" or "resources", use ONLY the [RECOMMENDED_RESOURCES] section.
7. NEVER show recommendations when the user asks to summarize the provided video.
8. DO NOT provide general search links or links to other platforms (but you MUST include the specific YouTube links provided in [RECOMMENDED_RESOURCES] exactly as they are).
9. Use conversation history to understand follow-up questions.
10. Format all responses with markdown (bullet points, subheadings, code blocks where needed).
11. If the recommendations list is empty, say: "I'm sorry, I couldn't find any specific YouTube recommendations for this topic at the moment."
12. Answer ONLY the specific concept asked about. The retrieved content may contain multiple topics or concepts in the same chunk — extract and present ONLY what is directly relevant to the student's question. Silently ignore unrelated concepts even if they appear in the same chunk.
13. If the user's input is a simple conversational greeting (e.g., "hello", "hey", "thanks", "how are you"), respond politely and conversationally, asking how you can help them with their studies. Do NOT mention or summarize the course materials in this case.

Special instructions for this question type:
{instruction}"""

        # ── User content ───────────────────────────────────────────────
        if has_arabic:
            user_content = f"""المحتوى المقدم:
{context if context.strip() else "لا يوجد محتوى إضافي من المصادر."}

[RECOMMENDED_RESOURCES]
{rec_text if rec_text else "لا توجد ترشيحات متوفرة حالياً."}

سؤال الطالب: {question}"""
        else:
            user_content = f"""Provided Content:
{context if context.strip() else "No additional context from sources."}

[RECOMMENDED_RESOURCES]
{rec_text if rec_text else "No specific recommendations found currently."}

Student Question: {question}"""

        # ── Assemble messages (system → history → current user turn) ───
        messages = [{"role": "system", "content": system_prompt}]

        if history:
            for turn in history[-5:]:   # last 5 turns for context window efficiency
                role = "user" if turn["role"] == "user" else "assistant"
                messages.append({"role": role, "content": turn["content"]})

        messages.append({"role": "user", "content": user_content})
        return messages

    def _generate_with_groq(
        self,
        question: str,
        context: str,
        question_type: str,
        is_youtube: bool,
        history: list = None,
        recommendations: dict = None,
    ) -> str:
        """Generate an answer using the Groq cloud API."""

        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)

        # Format recommendations
        rec_text = ""
        if recommendations and recommendations.get("youtube"):
            rec_text = "YouTube Courses & Videos:\n"
            for rec in recommendations["youtube"]:
                rec_text += f"- {rec['title']} ({rec['duration']}): {rec['link']}\n"

        messages = self._build_messages(
            question, context, question_type, history or [], rec_text, has_arabic
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=2048,
                temperature=0.5,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Groq generation failed in _generate_with_groq: {e}")
            return "Error: Failed to generate a response using the Groq API."
    

    # ================================================================== #
    # ★ الـ AGENTIC TOOLS الجديدة (Approach 5 & Memory) ★
    # ================================================================== #

    def rewrite_query_with_memory(self, question: str, history: list) -> str:
        """Agent 1: Memory - يحول السؤال لسؤال مستقل بناءً على السياق."""
        if not history:
            return question
        
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        
        if has_arabic:
            prompt = """أنت مساعد ذكي مهمتك الوحيدة هي إعادة صياغة أسئلة المستخدم.
بناءً على محادثة المستخدم الحالية، قم بصياغة السؤال الأخير كـ 'سؤال مستقل' بحيث يمكن فهمه بدون باقي المحادثة.
قواعد صارمة:
1. ممنوع تماماً الإجابة على السؤال.
2. ممنوع إدراج أي نص من إجابات المساعد السابقة في مخرجاتك.
3. أخرج السؤال المستقل فقط بدون أي كلام إضافي.

السؤال الأخير:"""
        else:
            prompt = """You are a query rewriter. Your ONLY job is to rewrite the user's latest question.
Based on the chat history, rewrite the latest question as a standalone question that can be understood without the conversation history.
STRICT RULES:
1. DO NOT answer the question.
2. DO NOT include previous assistant responses in your output.
3. Output EXACTLY ONE LINE: the rewritten question only.

Latest question:"""

        messages = [{"role": "system", "content": prompt}]
        for turn in history[-3:]: 
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=100, temperature=0.1
            )
            return response.choices[0].message.content.strip('"').strip()
        except Exception as e:
            logger.error(f"Query rewrite failed: {e}")
            return question

    def evaluate_documents(self, question: str, context: str) -> str:
        """Agent 2: Evaluator - هل المحتوى المسترجع يحتوي بالفعل على الإجابة؟"""
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        
        if has_arabic:
            prompt = f"""أنت مساعد أكاديمي. انظر إلى سؤال الطالب والمحتوى المستخرج من المحاضرات.
هل المحتوى يحتوي على أي معلومات متعلقة بموضوع السؤال؟
إذا كان المحتوى يتحدث عن موضوع مختلف تماماً ولا علاقة له بالسؤال، أجب بـ "No".
إذا كان المحتوى يحتوي على الإجابة، أو جزء منها، أو حتى مفاهيم متعلقة تساعد في الشرح، أجب بـ "Yes".
أجب بكلمة واحدة فقط: Yes أو No.
 
السؤال: {question}
المحتوى: {context[:2000]}"""
        else:
            prompt = f"""You are an academic assistant. Look at the student's question and the retrieved lecture content.
Does this content contain ANY information related to the topic of the question?
If the content is completely irrelevant or about a different subject, output "No".
If it contains the answer, a partial answer, or relevant concepts that help explain the topic, output "Yes".
Output EXACTLY one word: Yes or No.

Question: {question}
Context: {context[:2000]}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=5, temperature=0.0
            )
            answer = response.choices[0].message.content.strip()
            return "Yes" if "yes" in answer.lower() else "No"
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return "No"

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=5, temperature=0.0
            )
            answer = response.choices[0].message.content.strip()
            return "Yes" if "yes" in answer.lower() else "No"
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return "No"

    def route_query(self, question: str) -> str:
        """Agent 3: Router - هل السؤال أكاديمي/جامعي محض ولا معرفة عامة؟"""
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        
        if has_arabic:
            prompt = f"""صنف السؤال التالي إلى فئة واحدة فقط:
1. college_specific: أسئلة عن الدرجات، المواعيد، سياسات القسم، أساتذة معينين، أو تسجيل المواد.
2. general_knowledge: أسئلة عن مفاهيم علمية، برمجة، رياضيات، أو نظريات يمكن الإجابة عليها من المعرفة العامة.
أجب فقط بكلمة واحدة: college_specific أو general_knowledge.

السؤال: {question}"""
        else:
            prompt = f"""Classify the following question into exactly one category:
1. college_specific: Questions about grades, schedules, department policies, specific professors, or course registration.
2. general_knowledge: Questions about scientific concepts, programming, math, or theories that can be answered from general knowledge.
Output EXACTLY one word: college_specific or general_knowledge.

Question: {question}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=20, temperature=0.0
            )
            answer = response.choices[0].message.content.strip().lower()
            if "college" in answer:
                return "college_specific"
            return "general_knowledge"
        except Exception as e:
            return "general_knowledge"

    def generate_general_answer(self, question: str, history: list = None) -> str:
        """Agent 4: General Fallback - يجاوب من دماغه مع Disclaimer."""
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        
        if has_arabic:
            sys_prompt = """أنت مساعد تعليمي ذكي. السؤال الحالي ليس موجوداً في المحاضرات أو المواد الدراسية المرفوعة.
لذلك، مُنح لك صلاحية الإجابة من معرفتك العامة، ولكن فقط إذا كان السؤال يتعلق بعلوم الحاسب، الهندسة، الرياضيات، أو الدراسات الأكاديمية.
قواعد صارمة:
1. إذا كان السؤال عن الرياضة، الترفيه، السياسة، أو أي موضوع خارج نطاق علوم الحاسب والمعرفة الأكاديمية، يجب أن ترفض الإجابة وترد حرفياً بالتالي: "عذراً، يمكنني فقط تقديم إجابات من المواد الدراسية أو المعرفة المتعلقة بعلوم الحاسب." ولا تضف أي معلومات أخرى.
2. إذا كان السؤال يتعلق بعلوم الحاسب/الدراسات الأكاديمية، يجب أن تبدأ إجابتك بالتحذير التالي بالضبط:
"⚠️ تنبيه: هذه الإجابة من معرفتي العامة وليست من ضمن المحاضرات المرفوعة، يرجى التحقق منها."
بعد التحذير، قدم إجابة مفيدة ومنظمة وسديدة."""
        else:
            sys_prompt = """You are a smart educational assistant. The current question was NOT found in the uploaded course materials.
Therefore, you are granted permission to answer from your general knowledge, BUT ONLY if the question is related to Computer Science, Engineering, Mathematics, or Academic Studies.
STRICT RULES:
1. If the question is about sports, entertainment, politics, or any topic outside of Computer Science/Academic knowledge, you MUST refuse to answer and reply EXACTLY with: "Sorry, I only can provide answers from materials or computer science knowledge." Do not provide any other information.
2. If the question IS related to Computer Science/Academics, you MUST start your answer with the EXACT disclaimer:
"⚠️ Disclaimer: This answer is from my general knowledge and is NOT from the uploaded lectures, please verify it."
After the disclaimer, provide a helpful, well-structured, and accurate answer."""

        messages = [{"role": "system", "content": sys_prompt}]
        if history:
            for turn in history[-3:]:
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=1024, temperature=0.5
            )
            return response.choices[0].message.content
        except Exception as e:
            return "Error: Failed to generate a general response."

    def generate_conversational_reply(self, message: str) -> str:
        """Return a friendly conversational reply for greetings and small-talk.
        No RAG context is used and no disclaimer is added."""
        has_arabic = any('\u0600' <= ch <= '\u06FF' for ch in message)

        if has_arabic:
            sys_prompt = (
                "أنت مساعد تعليمي ودود. الرسالة الحالية ليست سؤالاً أكاديمياً، "
                "بل تحية أو رسالة اجتماعية بسيطة. رد بأدب واحترافية، وأخبر الطالب "
                "أنك هنا لمساعدته في دراسته. لا تذكر أي مواد دراسية ولا تضع أي تحذيرات."
            )
        else:
            sys_prompt = (
                "You are a friendly educational assistant. The current message is a greeting "
                "or casual remark — NOT an academic question. Reply warmly and let the student "
                "know you're here to help with their studies. Do NOT mention course materials "
                "and do NOT add any disclaimers."
            )

        if not USE_GROQ or not GROQ_AVAILABLE or not self.client:
            return "Hey! I'm your study assistant. Feel free to ask me anything about your courses!"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": message},
                ],
                max_tokens=150,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Conversational reply failed: {e}")
            return "Hey! I'm your study assistant. Feel free to ask me anything about your courses!"

    def extract_recommendation_topic(self, question: str) -> str:

        """Extract the core search topic from a recommendation query."""
        if not USE_GROQ or not GROQ_AVAILABLE or not self.client:
            return question
            
        prompt = f"""You are a search query optimizer. 
Your task is to extract the core topic of interest from a user's recommendation query. 
This core topic will be searched on YouTube, so it must be short (1-3 words) and clean.
Do NOT include verbs like "recommend", "suggest", "find", "search", "ترشيح", "قترح", "ابحث".
Do NOT output any markdown, punctuation, or extra text. Output ONLY the extracted topic.

Examples:
Query: "Can you suggest some other courses or videos about data science?" -> Data Science
Query: "هل يمكنك ترشيح كورس آخر عن تعلم الآلة؟" -> تعلم الآلة
Query: "suggest more resources on advanced neural networks" -> Advanced Neural Networks
Query: "نرشح كورس برمجة بايثون" -> برمجة بايثون

Query: "{question}"
Optimized Topic:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.1,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Failed to extract recommendation topic: {e}")
            return question