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


class GroqFallbackWrapper:
    """Wraps the Groq client to provide automatic fallback to OpenRouter when limits are hit."""
    def __init__(self, groq_client):
        self.groq_client = groq_client
        self.chat = self.Chat(self)
        
    class Chat:
        def __init__(self, parent):
            self.completions = self.Completions(parent)
            
        class Completions:
            def __init__(self, parent):
                self.parent = parent
                
            def create(self, model, messages, max_tokens=1024, temperature=0.5):
                import os, requests
                try:
                    return self.parent.groq_client.chat.completions.create(
                        model=model, messages=messages, max_tokens=max_tokens, temperature=temperature
                    )
                except Exception as e:
                    logger.warning(f"Groq API failed: {e}. Falling back to OpenRouter (Qwen).")
                    or_key = os.getenv("NVIDIA_API_KEY")
                    if not or_key:
                        logger.error("OpenRouter API key (NVIDIA_API_KEY) not found in env.")
                        raise e
                    
                    headers = {
                        "Authorization": f"Bearer {or_key}",
                        "Content-Type": "application/json"
                    }
                    data = {
                        "model": "qwen/qwen-2.5-7b-instruct",
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    }
                    
                    try:
                        logger.info(f"Calling OpenRouter with model: {data['model']}")
                        res = requests.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers=headers,
                            json=data,
                            timeout=(10, 30)  # 10s connect timeout, 30s read timeout
                        )
                        if not res.ok:
                            logger.error(f"OpenRouter returned error {res.status_code}: {res.text}")
                            res.raise_for_status()
                        
                        resp_json = res.json()
                        content = resp_json["choices"][0]["message"]["content"]
                        logger.info("OpenRouter fallback succeeded.")
                        
                        # Mock the Groq response object structure so the rest of the code works unmodified
                        class MockMsg:
                            def __init__(self, content): self.content = content
                        class MockChoice:
                            def __init__(self, content): self.message = MockMsg(content)
                        class MockResponse:
                            def __init__(self, content): self.choices = [MockChoice(content)]
                            
                        return MockResponse(content)
                    except Exception as or_error:
                        logger.error(f"OpenRouter Fallback failed: {or_error}")
                        raise e

class Generator:
    def __init__(self):
        self.model   = GROQ_MODEL
        self.api_key = GROQ_API_KEY
        if GROQ_AVAILABLE and self.api_key:
            self.client = GroqFallbackWrapper(Groq(api_key=self.api_key))
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

    def get_presentation_blueprint_md(self, content: str, user_request: str, history: list = None) -> str:
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

        history_str = ""
        if history:
            # Get the last 20 messages of conversation to provide deep context (e.g., if user generated questions over multiple prompts)
            recent_history = history[-20:]
            history_str = "\n[CONVERSATION CONTEXT (Previous Messages)]\n"
            for msg in recent_history:
                history_str += f"{msg['role'].upper()}: {msg['content']}\n"

        prompt = f"""You are a Professional Presentation Architect.
Your ONLY job is to output a detailed slide-by-slide OUTLINE for a presentation.
NEVER explain, converse, or add any text outside the slide blocks.

MINIMUM REQUIREMENTS & RULES:
1. Usually generate AT LEAST 6 to 8 slides (not counting the cover and Thank You slides).
2. Each slide MUST have a clear, specific title.
3. Each slide MUST have 2 to 4 DESCRIPTIVE bullet points. Do not just use single keywords or names; use a full phrase that outlines what should be explained on that slide.
4. If the user requests an example or code, include dedicated slides for it.

OUTPUT FORMAT — FOLLOW EXACTLY:
- Separate each slide with: <!-- slide -->
- Each slide block starts with: # Slide Title
- Each bullet uses a single dash: - bullet point text
- FIRST slide = cover slide (title + 1-line subtitle)
- LAST slide = # Thank You with bullet: - Questions & Discussion
- NO extra text, NO markdown fences, NO explanation.

[CONTENT FROM COURSE MATERIALS]
{content[:5000]}
{history_str}
[USER REQUEST]
{user_request}

CRITICAL INSTRUCTION FOR THIS REQUEST (CHOOSE ONE PATH BASED ON USER REQUEST):

PATH A - NORMAL PRESENTATION (Default):
If the [USER REQUEST] asks for a presentation about a topic, lecture, or video, you MUST use the [CONTENT FROM COURSE MATERIALS] to generate a standard educational presentation explaining the topic. Follow the 6-slide minimum.

PATH B - QUIZ/QUESTIONS PRESENTATION (Only if explicitly requested):
If the [USER REQUEST] explicitly asks you to put specific questions/quiz items from the [CONVERSATION CONTEXT] into a presentation, you MUST STRICTLY build the presentation ONLY out of those questions. Do NOT generate a general explanation.
1. The FIRST slide MUST be a generic cover slide (e.g., "# Quiz Presentation"). Do NOT put a question on the cover slide.
2. Put the FIRST question on the second slide, the SECOND question on the third slide, and so on (exactly one slide per question).
3. The actual question text MUST be the first bullet point (e.g. "- Question: What is PCA?"). Then, if the question has multiple choices, include every choice as a separate bullet point, and explicitly state the correct answer at the bottom (e.g. "- Correct Answer: C"). Do NOT leave the question as plain text.
In this specific case, ignore the 6-slide minimum.

NOW generate the full blueprint based on the rules and instructions above:"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Blueprint (MD) generation failed: {e}")
            return "Error generating presentation blueprint."

    def adjust_presentation_blueprint_md(self, previous_blueprint: str, user_request: str, history: list = None) -> str:
        """
        Refinement — Adjust the existing blueprint based on user's feedback.
        """
        if not USE_GROQ or not GROQ_AVAILABLE or not self.client:
            return "Error: LLM not available for blueprint adjustment."

        history_str = ""
        if history:
            # Get the last 20 messages of conversation to provide deep context
            recent_history = history[-20:]
            history_str = "\n[CONVERSATION CONTEXT (Previous Messages)]\n"
            for msg in recent_history:
                history_str += f"{msg['role'].upper()}: {msg['content']}\n"

        prompt = f"""You are a Professional Presentation Architect.
Your ONLY job is to modify the existing presentation outline based on the user's request.
NEVER explain how to do it or talk to the user.

Here is the EXISTING COMPLETE presentation outline (you MUST keep ALL existing slides):
{previous_blueprint}
{history_str}
User request for adjustments:
{user_request}

CRITICAL RULES:
- Output the FULL updated blueprint including ALL original slides PLUS any additions/changes.
- Do NOT drop any existing slides unless the user explicitly asks to remove them.
- If the user asks to add slides (e.g., "add an example", "add code"), create DEDICATED slides for each request with 2-4 meaningful bullet points each.
- IMPORTANT FOR QUESTIONS: If you add questions, you MUST create a separate, dedicated slide for EACH question. Do NOT put multiple questions on one slide.
- For each question slide, the question text MUST be the first bullet point (e.g., "- Question: What is PCA?"). Then, include EVERY multiple choice option as a separate bullet point, and explicitly state the correct answer at the bottom (e.g., "- Correct Answer: A"). Do NOT omit choices or the question text.
- Append new slides BEFORE the final '# Thank You' slide.
- Each slide MUST have a clear title and 2-4 specific, descriptive bullet points.
- Separate each slide with: <!-- slide -->
- Each slide block starts with: # Slide Title
- Bullets use a single dash: - bullet point
- ABSOLUTELY NO EXTRA TEXT. Output ONLY the slide blocks.
- Do NOT wrap the output in ```markdown``` fences.

Updated Blueprint (full, including all original slides, no extra text):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
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
Your job is to expand the [APPROVED OUTLINE] below into a FULL slide deck.

[CONTENT SOURCE]
{content[:5000]}

[APPROVED OUTLINE]
{approved_blueprint}

GOLDEN RULE: The [APPROVED OUTLINE] is the LAW for structure, but you MUST EXPAND the content dramatically.
1. Include EVERY slide that appears in the outline — no additions, no deletions.
2. Keep each slide's EXACT title from the outline.
3. For the content of each slide, act as if the user asked you "Explain [Slide Title]" as a normal chatbot question. You MUST expand the short outline bullets into highly detailed, informative content using the [CONTENT SOURCE], explaining the concept deeply just like you would in a normal chatbot response.

OUTPUT FORMAT — YOU MUST FOLLOW THIS EXACTLY:
- Separate each slide with the HTML comment: <!-- slide -->
- Each slide block starts with: # Slide Title
- Each content slide MUST have 3 to 5 detailed explanatory points. Use: - point
- For NORMAL slides: instead of short bullet points, each `- ` MUST contain a FULL PARAGRAPH (2-3 sentences) explaining the concept in detail to a student. Act as if you are answering "Explain this to me".
  BAD:  "- Represents program in memory"
  GOOD: "- The text segment is a crucial part of memory that securely stores the compiled machine code instructions. When the program runs, the CPU reads these instructions sequentially to execute the program's logic."
- The FIRST slide (cover) keeps only the title and 1-line subtitle bullet.
- The LAST slide MUST EXACTLY match what is in the [APPROVED OUTLINE] for the last slide.
- Do NOT add any extra text, explanations, or headers outside the slide blocks.
- Do NOT wrap the output in ```markdown``` fences.

SPECIAL RULE FOR QUESTION/QUIZ SLIDES:
If a slide title contains a question (e.g., "Q1:", "Question", "?") or the slide is about a quiz question, you MUST format it carefully:
1. The question text MUST be the first bullet point (e.g. "- Question: What is PCA?"). Do NOT leave it as plain text.
2. Follow the question bullet with ALL the multiple choice options (A, B, C, D) as separate bullets.
3. Finally state the correct answer as the last bullet. Do NOT replace the question with generic topic content. Do NOT omit the choices.

SPECIAL RULE FOR CODE SLIDES:
If a slide title contains "Code", "Implementation", "Example", "Algorithm", "Snippet", "Solution", or "Walkthrough",
you MUST format the slide EXACTLY like this — no extra bullets before or after the code block:
```python
# actual working, complete code here
def example():
    pass
```
- One sentence explaining what the code demonstrates or its expected output.
DO NOT add any bullet point like "- Code Snippet:", "- Implementation:", or "- Here is the code:" before the fenced code block.
DO NOT add a title label bullet. The code block itself IS the main content. Only ONE explanation bullet after the code block is allowed.

CRITICAL FINAL REMINDER: YOU MUST WRITE FULL 2-3 SENTENCE PARAGRAPHS FOR EACH NORMAL BULLET POINT. DO NOT JUST COPY THE SHORT OUTLINE.

Full Markdown deck (no extra text):"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=3000,
                temperature=0.5,
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
            
            # If this slide has a code_block, drop any "label" bullets that are
            # just headings for the code (e.g. "Code Snippet:", "Implementation:").
            # These are artefacts from the LLM adding a bullet before the fence.
            if slide.get("code_block"):
                _CODE_LABEL_PATTERNS = (
                    "code snippet", "implementation", "here is the code",
                    "here's the code", "the code", "code:", "example code",
                    "code below", "following code", "code implementation",
                )
                slide["content"] = [
                    b for b in slide["content"]
                    if not any(pat in b.lower() for pat in _CODE_LABEL_PATTERNS)
                ]

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
12. إذا سأل الطالب عن مفهوم محدد، استخرج وقدم فقط ما يتعلق بهذا المفهوم وتجاهل المواضيع غير ذات الصلة. ولكن، إذا طلب الطالب شرحاً عاماً أو تلخيصاً للمحاضرة، يجب عليك شرح وتلخيص جميع المواضيع والمفاهيم التقنية الرئيسية الموجودة في المحتوى. لا تكتفِ بذكر المصادر، بل اشرح المادة العلمية نفسها.
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
12. If the user asks about a specific concept, extract and present ONLY what is directly relevant to that concept, ignoring unrelated topics. HOWEVER, if the user asks for a general explanation or summary of the lecture/document, you MUST summarize all the main technical topics and concepts present in the provided content. Do not just list resources; explain the actual course material itself.
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
        
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        
        if has_arabic:
            prompt = """أنت مساعد ذكي مهمتك الوحيدة هي إعادة صياغة أسئلة المستخدم للبحث في قاعدة بيانات باللغة الإنجليزية.
قواعد صارمة جداً:
1. يجب عليك ترجمة السؤال إلى اللغة الإنجليزية (لأن جميع الملفات والمحاضرات باللغة الإنجليزية، والبحث بالعربي لن يجد شيئاً).
2. قم بحذف أي كلمات حشو أو أسماء مواد من البحث. (مثلاً: إذا سأل "اشرح الانحدار الخطي من مادة تعلم الآلة"، يجب أن يكون المخرج فقط "Explain Linear Regression").
3. ممنوع تماماً الإجابة على السؤال.
4. ممنوع إدراج أي نص من إجابات المساعد السابقة.
5. أخرج السؤال المستقل المترجم فقط (باللغة الإنجليزية) بدون أي كلام إضافي.

السؤال الأخير:"""
        else:
            prompt = """You are a search query translator and rewriter. Your ONLY job is to rewrite the user's latest question so it can be searched in an English database.
Based on the chat history, rewrite the latest question as a standalone question that can be understood without the conversation history.

CRITICAL RULES:
1. DROP ALL conversational filler and course names! For example, if the user asks "Explain Linear Regression from Machine Learning subject", you MUST output ONLY: "Explain Linear Regression". (The system filters by course automatically, so including the course name breaks the exact match search).
2. DO NOT answer the question.
3. Output EXACTLY ONE LINE: the standalone, English rewritten question only.

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
            prompt = f"""أنت حَكَم أكاديمي. مهمتك التحقق مما إذا كان المحتوى المسترجع يغطي الموضوع الأساسي لسؤال الطالب.

قواعد:
1. أجب بـ "Yes" إذا كان المحتوى يشرح أو يناقش المفهوم المطلوب بشكل مباشر وذي معنى.
2. أجب بـ "No" إذا كان المحتوى يذكر فقط كلمات مشتركة بدون تغطية المفهوم المحدد:
   - مثال: السؤال عن "البيانات الضخمة (Big Data)" والمحتوى يتحدث عن معالجة بيانات عامة أو التعلم الآلي → "No"
   - مثال: السؤال عن "الشبكات العصبية" والمحتوى يتحدث فقط عن الانحدار الخطي → "No"
3. أمثلة على القبول ("Yes"):
   - السؤال عن "الانحدار الخطي" والمحتوى يشرح المعادلة أو دالة الخسارة أو الخوارزمية → "Yes"
   - السؤال عن "الشبكات العصبية" والمحتوى يشرح الطبقات أو التدريب → "Yes"
   - السؤال عن "أشجار القرار" والمحتوى يشرح الانتروبيا أو الانقسام → "Yes"
4. كن معقولاً — إذا كان المحتوى يحتوي على شرح ذي صلة (حتى لو لم يكن شاملاً)، أجب بـ "Yes".
5. أجب بكلمة واحدة فقط: Yes أو No. لا تضف أي شرح.

السؤال: {question}
المحتوى: {context[:16000]}"""
        else:
            prompt = f"""You are an academic relevance judge. Your job is to check if the retrieved content covers the core topic of the student's question.

RULES:
1. Output "Yes" if the content directly explains or discusses the concept asked about.
2. Output "No" if the content only mentions loosely related words without actually covering the specific concept:
   - Example: Question is about "Big Data" but content only discusses general data preprocessing or ML algorithms → "No"
   - Example: Question is about "Neural Networks" but content only covers Linear Regression → "No"
   - Example: Question is about "Blockchain" but content just mentions the word "blocks" in a different context → "No"
3. Examples that MUST return "Yes":
   - Question is about "Linear Regression" and content explains the formula, cost function, or optimization → "Yes"
   - Question is about "Neural Networks" and content explains layers, activation functions, or training → "Yes"
   - Question is about "Decision Trees" and content explains splits, entropy, or Gini index → "Yes"
4. Be reasonable — if the content has a meaningful, relevant explanation of the topic (even if not exhaustive), output "Yes".
5. Output EXACTLY one word: Yes or No. No explanation.

Question: {question}
Context: {context[:16000]}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=5, temperature=0.0
            )
            answer = response.choices[0].message.content.strip()
            return "Yes" if "yes" in answer.lower() else "No"
        except Exception as e:
            # Only reaches here if BOTH Groq and the OpenRouter fallback (in GroqFallbackWrapper) failed.
            # Re-raise so the caller (rag_pipeline) can decide the fallback behavior.
            logger.error(f"Evaluation agent failed on all providers: {e}")
            raise

    def route_query(self, question: str) -> str:
        """Agent 3: Router - هل السؤال أكاديمي/جامعي محض ولا معرفة عامة؟"""
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        
        if has_arabic:
            prompt = f"""صنف السؤال التالي إلى فئة واحدة فقط:
- college_specific: أسئلة فقط حول الشئون الإدارية، أسماء الدكاترة، مواعيد الامتحانات، الجداول، أو الدرجات.
- general_academic: أسئلة علمية، أو طلبات تلخيص وشرح المحاضرات، السلايدز، المناهج، أو مفاهيم الذكاء الاصطناعي والبرمجة.
أجب بكلمة واحدة فقط من الكلمتين أعلاه.

السؤال: {question}"""
        else:
            prompt = f"""Classify the following question into exactly one category:
- college_specific: Questions ONLY about administrative affairs, professors' names, exam dates, schedules, or grades.
- general_academic: Scientific questions, OR requests to summarize/explain lectures, slides, curriculum, programming, or engineering topics.
Output EXACTLY one word from the two options above.

Question: {question}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=20, temperature=0.0
            )
            ans = response.choices[0].message.content.strip().lower()
            return "general_academic" if "general_academic" in ans else "college_specific"
        except Exception as e:
            logger.error(f"Routing failed: {e}")
            return "general_academic"

    def detect_intent(self, question: str, history_text: str) -> str:
        """Agent: Intent Detector - intelligently classify user request to avoid keyword collisions."""
        prompt = f"""You are an Intent Detection Agent for an educational AI assistant.
Analyze the user's latest question in the context of their chat history (if any).
Classify the user's intent into EXACTLY ONE of the following categories:

- "create_presentation": The user wants to CREATE A BRAND NEW presentation / slides / slideshow from scratch (e.g., "create a presentation about AI", "make slides for machine learning"). Use this ONLY when there is NO existing blueprint in the chat history.
- "adjust_presentation": The user is asking to modify, add, remove, or change slides in an ALREADY EXISTING presentation blueprint in the chat history.
- "approve_presentation": The user wants to FINALIZE and DOWNLOAD the existing blueprint that was already shown to them. This includes phrases like: "looks good", "perfect", "generate it", "create it", "build it", "ok go ahead", "yes do it", "make the presentation", "download it" — when there IS an existing blueprint in the chat history.
- "recommendation": The user is asking for external resources, YouTube videos, or course recommendations to learn more.
- "general_question": A normal academic question, asking for an explanation, summary, quiz, questions, practice problems, or asking the bot to "go over slides" / "explain these slides". (This is NOT creating a presentation).

CRITICAL ANTI-HALLUCINATION RULES:
1. Generating QUIZ questions or practice questions (e.g., "give me 5 questions about X", "generate a quiz", "test me on", "ask me questions about") MUST ALWAYS be classified as "general_question". It is NOT a presentation request. NEVER classify quiz/test requests as "create_presentation".
2. "generate it" / "create it" / "make it" ONLY means "approve_presentation" if a blueprint (marked with <!-- slide --> or # Thank You) ALREADY EXISTS in the chat history. If there is no blueprint, treat it as "create_presentation" or "general_question" based on context.
3. Asking for an explanation, definition, or summary is ALWAYS "general_question".

IMPORTANT RULE: If the chat history already contains a presentation blueprint (marked with <!-- slide --> or # Thank You), then:
  - "generate it" / "create it" / "make it" = "approve_presentation" (finalize the existing one)
  - "add more slides" / "remove slide" / "change title" = "adjust_presentation"
  - A completely new presentation topic = "create_presentation"

Output EXACTLY ONE WORD from the quotes above. No other text.

Chat History Context:
{history_text[-1500:] if history_text else "None"}

Latest Question: {question}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=[{"role": "user", "content": prompt}], max_tokens=10, temperature=0.0
            )
            intent = response.choices[0].message.content.strip().lower()
            # Clean up the response just in case
            for valid_intent in ["create_presentation", "adjust_presentation", "approve_presentation", "recommendation", "general_question"]:
                if valid_intent in intent:
                    return valid_intent
            return "general_question"
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            return "general_question"


    def is_enrolled_course_topic(self, question: str, enrolled_courses: list) -> bool:
        """
        Uses an LLM call to check if the question is academically related
        to any of the student's enrolled/completed courses.
        Returns True  → topic is in enrolled courses (no disclaimer needed)
        Returns False → topic is outside enrolled courses (disclaimer needed)
        """
        if not enrolled_courses:
            return False
        # Deduplicate and take only readable names/codes (skip very short single-letter prefixes)
        readable = list({c for c in enrolled_courses if len(c) > 4})[:15]
        if not readable:
            readable = list({c for c in enrolled_courses if len(c) > 2})[:15]
        courses_str = ", ".join(readable)
        prompt = (
            f"A student is enrolled ONLY in these courses: {courses_str}\n"
            f"Is the following question specifically about a topic covered in these enrolled courses?\n"
            f"\n"
            f"STRICT RULES:\n"
            f"- Answer YES only if the question's topic is a subject matter taught in one of the listed courses.\n"
            f"- Answer NO if the question is about a topic from a DIFFERENT course not in the list.\n"
            f"- Examples:\n"
            f"  * Enrolled in [Machine Learning] + Question 'What is Big Data?' → NO (Big Data is a separate field)\n"
            f"  * Enrolled in [Machine Learning] + Question 'Explain Linear Regression' → YES\n"
            f"  * Enrolled in [Data Structures] + Question 'What is Blockchain?' → NO\n"
            f"  * Enrolled in [Data Structures] + Question 'How does a Binary Tree work?' → YES\n"
            f"\n"
            f"Question: {question}\n"
            f"Answer with only YES or NO."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0.0,
            )
            ans = response.choices[0].message.content.strip().upper()
            return "YES" in ans
        except Exception as e:
            logger.error(f"is_enrolled_course_topic failed: {e}")
            return True  # Default: assume enrolled topic to avoid false disclaimers

    def generate_enrolled_topic_answer(self, question: str, history: list = None) -> str:
        """
        Answer a question from general knowledge WITHOUT any disclaimer.
        Used when the topic is related to the student's enrolled courses but
        the specific material wasn't uploaded to the vector store yet.
        """
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        if has_arabic:
            sys_prompt = (
                "أنت مساعد تعليمي ذكي. أجب على السؤال التالي بشكل مفيد ومنظم واحترافي. "
                "يمكنك الإجابة من معرفتك العامة إذا كان السؤال أكاديمياً. "
                "لا تضع أي تحذير أو إخلاء مسؤولية في بداية إجابتك."
            )
        else:
            sys_prompt = (
                "You are a smart educational assistant. Answer the following question in a helpful, "
                "well-structured, and accurate way from your academic knowledge. "
                "Do NOT add any disclaimer or warning at the beginning of your answer."
            )
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
            logger.error(f"generate_enrolled_topic_answer failed: {e}")
            return "Error: Failed to generate a response."

    def generate_general_answer(self, question: str, history: list = None) -> str:
        """Agent 4: General Fallback - يجاوب من دماغه مع Disclaimer."""
        has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in question)
        
        if has_arabic:
            sys_prompt = """أنت مساعد تعليمي ذكي. السؤال الحالي ليس موجوداً في المحاضرات أو المواد الدراسية المرفوعة.
لذلك، مُنح لك صلاحية الإجابة من معرفتك العامة، ولكن فقط إذا كان السؤال يتعلق بعلوم الحاسب، الهندسة، الرياضيات، أو الدراسات الأكاديمية.
قواعد صارمة:
1. إذا كان السؤال عن الرياضة، الترفيه، السياسة، أو أي موضوع خارج نطاق علوم الحاسب والمعرفة الأكاديمية، يجب أن ترفض الإجابة وترد حرفياً بالتالي: "عذراً، يمكنني فقط تقديم إجابات من المواد الدراسية أو المعرفة المتعلقة بعلوم الحاسب." ولا تضف أي معلومات أخرى.
2. أجب بطريقة منظمة وسديدة ومفيدة جداً للطالب."""
            disclaimer = "⚠️ تنبيه: هذه الإجابة من معرفتي العامة وليست من ضمن المحاضرات المرفوعة، يرجى التحقق منها.\n\n"
        else:
            sys_prompt = """You are a smart educational assistant. The current question was NOT found in the uploaded course materials.
Therefore, you are granted permission to answer from your general knowledge, BUT ONLY if the question is related to Computer Science, Engineering, Mathematics, or Academic Studies.
STRICT RULES:
1. If the question is about sports, entertainment, politics, or any topic outside of Computer Science/Academic knowledge, you MUST refuse to answer and reply EXACTLY with: "Sorry, I only can provide answers from materials or computer science knowledge." Do not provide any other information.
2. Provide a helpful, well-structured, and accurate academic answer."""
            disclaimer = "⚠️ Disclaimer: This answer is from my general knowledge and is NOT from the uploaded lectures, please verify it.\n\n"

        messages = [{"role": "system", "content": sys_prompt}]
        if history:
            for turn in history[-3:]:
                messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": question})

        try:
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=1024, temperature=0.5
            )
            ans = response.choices[0].message.content.strip()
            
            # Only append disclaimer if the LLM didn't refuse to answer
            if "Sorry, I only can provide answers" in ans or "عذراً، يمكنني فقط تقديم إجابات" in ans:
                return ans
            return disclaimer + ans
        except Exception as e:
            logger.error(f"General generator failed: {e}")
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